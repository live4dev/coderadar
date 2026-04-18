import { state } from '../state.js';
import { api } from '../api.js';
import { scoreClass, esc } from '../utils.js';

const DOMAIN_LABELS = {
  code_quality:     'Code Quality',
  test_quality:     'Test Quality',
  doc_quality:      'Doc Quality',
  delivery_quality: 'Delivery Quality',
  maintainability:  'Maintainability',
};

const DOMAIN_WEIGHTS = {
  code_quality:     '25%',
  test_quality:     '20%',
  doc_quality:      '15%',
  delivery_quality: '20%',
  maintainability:  '20%',
};

function parseDetails(raw) {
  if (!raw) return {};
  try { return typeof raw === 'string' ? JSON.parse(raw) : raw; }
  catch { return {}; }
}

function renderSignals(domain, details) {
  const signals = [];

  if (domain === 'code_quality') {
    if (details.large_files_penalty != null)
      signals.push({ neg: true,  text: `Large files (≥500 LOC): ${details.large_files_count ?? '?'} file(s) — −${details.large_files_penalty} pts` });
    if (details.large_functions_penalty != null)
      signals.push({ neg: true,  text: `Large functions (≥50 LOC) — −${details.large_functions_penalty} pts` });
    if (details.avg_loc_penalty != null)
      signals.push({ neg: true,  text: `Average file LOC > 300 — −${details.avg_loc_penalty} pts` });
    if (details.avg_loc_ok)
      signals.push({ neg: false, text: 'Average file LOC < 150 — within healthy range' });
    if (details.linters?.length)
      signals.push({ neg: false, text: `Linters detected: ${details.linters.join(', ')} — +10 pts` });
    if (details.formatters?.length)
      signals.push({ neg: false, text: `Formatters detected: ${details.formatters.join(', ')} — +5 pts` });
  }

  if (domain === 'test_quality') {
    if (details.has_tests === false)
      signals.push({ neg: true,  text: 'No test files found' });
    if (details.has_tests === true)
      signals.push({ neg: false, text: 'Test files present — +50 pts' });
    if (details.test_ratio != null) {
      const pct = (details.test_ratio * 100).toFixed(0);
      const bonus = details.test_ratio >= 0.3 ? 30 : details.test_ratio >= 0.15 ? 15 : details.test_ratio >= 0.05 ? 5 : 0;
      signals.push({ neg: bonus === 0, text: `Test-to-source ratio: ${pct}%${bonus ? ` — +${bonus} pts` : ''}` });
    }
  }

  if (domain === 'doc_quality') {
    if (details.has_docs === false)
      signals.push({ neg: true,  text: 'No documentation files found' });
    if (details.has_readme)
      signals.push({ neg: false, text: 'README present — +20 pts' });
    if (details.has_install_docs)
      signals.push({ neg: false, text: 'Install / setup docs — +15 pts' });
    if (details.has_architecture_docs)
      signals.push({ neg: false, text: 'Architecture docs or ADRs — +15 pts' });
    if (details.has_changelog)
      signals.push({ neg: false, text: 'CHANGELOG or HISTORY — +15 pts' });
    if (details.has_runbook)
      signals.push({ neg: false, text: 'Runbook — +10 pts' });
  }

  if (domain === 'delivery_quality') {
    if (details.has_ci) {
      const provider = details.ci_provider ? ` (${details.ci_provider})` : '';
      signals.push({ neg: false, text: `CI pipeline${provider} — +40 pts` });
    }
    if (details.has_docker)
      signals.push({ neg: false, text: 'Dockerfile present — +30 pts' });
    if (details.has_infra_as_code)
      signals.push({ neg: false, text: 'Kubernetes / Helm / Terraform config — +20 pts' });
    if (details.has_requirements) {
      const file = details.requirements_file ? ` (${details.requirements_file})` : '';
      signals.push({ neg: false, text: `Dependency manifest${file} — +10 pts` });
      if (details.requirements_pinned === true)
        signals.push({ neg: false, text: 'Dependencies have pinned versions — +10 pts' });
      else if (details.requirements_pinned === false)
        signals.push({ neg: true,  text: 'Dependency versions are not fully pinned' });
    } else {
      signals.push({ neg: true,  text: 'No dependency manifest detected' });
    }
    if (!details.has_ci && !details.has_docker && !details.has_infra_as_code && !details.has_requirements)
      signals.push({ neg: true,  text: 'No CI, Docker, IaC or dependency manifest detected' });
  }

  if (domain === 'maintainability') {
    if (details.single_dev)
      signals.push({ neg: true,  text: 'Single contributor — −20 pts' });
    if (details.multi_dev)
      signals.push({ neg: false, text: '3+ contributors — +10 pts' });
    if (details.top_dev_share != null) {
      const pct = (details.top_dev_share * 100).toFixed(0);
      const penalty = details.top_dev_share > 0.80 ? 20 : details.top_dev_share > 0.60 ? 10 : 0;
      signals.push({ neg: penalty > 0, text: `Top contributor share: ${pct}%${penalty ? ` — −${penalty} pts` : ''}` });
    }
    if (details.high_complexity)
      signals.push({ neg: true,  text: 'High complexity: >10 files above threshold — −10 pts' });
  }

  if (!signals.length) return '';

  const chips = signals.map(s => {
    const color = s.neg ? 'var(--red)' : 'var(--green)';
    const icon  = s.neg ? '↓' : '↑';
    return `<span style="display:inline-flex;align-items:center;gap:4px;font-size:11px;padding:2px 8px;border-radius:4px;border:1px solid ${color};color:${color};white-space:nowrap">
      <span style="font-weight:700">${icon}</span>${esc(s.text)}
    </span>`;
  }).join('');

  return `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">${chips}</div>`;
}

export async function buildScoresTab(scan) {
  const scores = await api('/scans/' + state.scanId + '/scores');
  const overall = scores.find(s => s.domain === 'overall');

  const rows = scores.filter(s => s.domain !== 'overall').map(s => {
    const cls     = scoreClass(s.score);
    const color   = cls === 'high' ? 'var(--green)' : cls === 'mid' ? 'var(--yellow)' : 'var(--red)';
    const details = parseDetails(s.details);
    const signals = renderSignals(s.domain, details);
    const label   = DOMAIN_LABELS[s.domain] ?? s.domain.replace(/_/g, ' ');
    const weight  = DOMAIN_WEIGHTS[s.domain] ?? '';

    return `<tr>
      <td style="font-weight:500;vertical-align:top;padding-top:14px">
        <div>${esc(label)}</div>
        ${weight ? `<div style="font-size:11px;color:var(--text-muted);margin-top:2px">weight ${weight}</div>` : ''}
      </td>
      <td>
        <div class="score-bar-wrap">
          <div class="score-bar"><div class="score-fill ${cls}" style="width:${s.score}%"></div></div>
          <span class="score-num" style="color:${color}">${s.score.toFixed(1)}</span>
        </div>
        ${signals}
      </td>
    </tr>`;
  }).join('');

  const ov    = overall ? overall.score : 0;
  const ovCls = scoreClass(ov);
  const ovColor = ovCls === 'high' ? 'var(--green)' : ovCls === 'mid' ? 'var(--yellow)' : 'var(--red)';

  const wipBanner = `
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:20px;padding:12px 16px;background:rgba(var(--yellow-rgb,200,160,0),0.08);border:1px solid var(--yellow,#c8a000);border-radius:8px;color:var(--yellow,#c8a000);font-size:13px">
      <span style="font-size:16px;line-height:1.4">⚠</span>
      <div>
        <strong>Work in progress</strong> — The scoring model is under active development.
        Weights, thresholds, and signal definitions may change between scans.
      </div>
    </div>`;

  return `
    ${wipBanner}
    <div style="display:flex;align-items:center;gap:24px;margin-bottom:28px;padding:20px;background:var(--surface);border:1px solid var(--border);border-radius:10px">
      <div style="text-align:center;min-width:80px">
        <div style="font-size:42px;font-weight:800;color:${ovColor}">${ov.toFixed(0)}</div>
        <div style="font-size:12px;color:var(--text-muted)">Overall</div>
      </div>
      <div style="flex:1">
        <div class="score-bar" style="height:10px"><div class="score-fill ${ovCls}" style="width:${ov}%"></div></div>
        <div style="font-size:11px;color:var(--text-muted);margin-top:6px">
          Weighted average of all five quality domains
        </div>
      </div>
    </div>
    <table>
      <thead><tr><th>Domain</th><th>Score &amp; Signals</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
