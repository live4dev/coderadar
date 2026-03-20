import { state } from '../state.js';
import { api } from '../api.js';
import { esc } from '../utils.js';

export async function buildDependenciesTab() {
  let summary, deps;
  try {
    [summary, deps] = await Promise.all([
      api('/scans/' + state.scanId + '/license-summary'),
      api('/scans/' + state.scanId + '/dependencies'),
    ]);
  } catch (e) {
    return `<div class="empty"><p>Could not load dependency data.</p></div>`;
  }

  if (!deps.length) {
    return `<div class="empty"><div class="icon">📦</div><p>No dependencies detected in this scan.</p></div>`;
  }

  // ── Summary stats ──────────────────────────────────────────────────────────
  const statBoxes = [
    { label: 'Total', value: summary.total },
    { label: 'Direct', value: summary.direct_count },
    { label: 'Transitive', value: summary.transitive_count },
    { label: 'Safe', value: summary.safe_count, color: 'var(--green)' },
    { label: 'Risky', value: summary.risky_count, color: 'var(--red)' },
    { label: 'Unknown', value: summary.unknown_count, color: 'var(--text-muted)' },
  ].map(s =>
    `<div class="stat-box" style="min-width:100px">
      <div class="stat-label">${s.label}</div>
      <div class="stat-value" style="${s.color ? 'color:' + s.color : ''}">${s.value}</div>
    </div>`
  ).join('');

  // ── Risk score bar ─────────────────────────────────────────────────────────
  const riskClass = summary.risk_score >= 30 ? 'low' : summary.risk_score >= 10 ? 'mid' : 'high';
  const riskBar = `
    <div style="margin-bottom:20px">
      <div style="font-size:12px;color:var(--text-muted);margin-bottom:4px">
        License risk score: <strong>${summary.risk_score}/100</strong>
        <span style="color:var(--text-muted);font-weight:400"> (% of risky licences)</span>
      </div>
      <div class="score-bar" style="max-width:320px">
        <div class="score-fill ${riskClass}" style="width:${summary.risk_score}%"></div>
      </div>
    </div>`;

  // ── Top licences breakdown ─────────────────────────────────────────────────
  const topLicenses = Object.entries(summary.license_counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([id, count]) =>
      `<span class="tag" style="margin-right:4px;margin-bottom:4px">${esc(id)} <strong>${count}</strong></span>`
    ).join('');

  // ── Table rows ─────────────────────────────────────────────────────────────
  const rows = deps.map(d => {
    const directBadge = d.is_direct
      ? `<span class="badge medium" style="background:rgba(34,197,94,0.15);color:#4ade80;font-size:10px">direct</span>`
      : `<span class="badge low" style="font-size:10px">transitive</span>`;

    const licenseBadge = d.license_spdx
      ? `<code style="font-size:11px;background:var(--surface2);padding:2px 6px;border-radius:3px">${esc(d.license_spdx)}</code>`
      : `<span style="color:var(--text-muted);font-size:12px">—</span>`;

    let riskBadge;
    if (d.license_risk === 'safe') {
      riskBadge = `<span class="badge" style="background:rgba(34,197,94,0.15);color:#4ade80">Safe</span>`;
    } else if (d.license_risk === 'risky') {
      riskBadge = `<span class="badge critical">Risky</span>`;
    } else {
      riskBadge = `<span class="badge low">Unknown</span>`;
    }

    return `<tr>
      <td style="font-weight:500">${esc(d.name)}</td>
      <td><span class="tag" style="font-size:11px">${esc(d.ecosystem || '—')}</span></td>
      <td style="font-size:12px;color:var(--text-muted)">${esc(d.version || '—')}</td>
      <td>${directBadge}</td>
      <td>${licenseBadge}</td>
      <td>${riskBadge}</td>
      <td style="font-size:11px;color:var(--text-muted)">${esc(d.manifest_file || '—')}</td>
    </tr>`;
  }).join('');

  return `
    <div class="stats-row" style="margin-bottom:20px;flex-wrap:wrap">${statBoxes}</div>
    ${riskBar}
    <div style="margin-bottom:20px;display:flex;flex-wrap:wrap;gap:4px">${topLicenses}</div>
    <table>
      <thead><tr>
        <th>Package</th>
        <th>Ecosystem</th>
        <th>Version</th>
        <th>Type</th>
        <th>Licence</th>
        <th>Risk</th>
        <th>Manifest</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
