import { state } from '../state.js';
import { api } from '../api.js';
import { esc, fmtDate, setMain, showError } from '../utils.js';

export async function renderLicenseReport() {
  setMain('<div class="empty"><span class="spinner"></span> Loading…</div>');
  const params = new URLSearchParams();
  if (state.licenseReportProjectId != null) params.set('project_id', state.licenseReportProjectId);
  if (state.licenseReportRepoId != null) params.set('repository_id', state.licenseReportRepoId);
  const query = params.toString();
  let projects = [];
  let repos = [];
  let report = { entries: [] };
  try {
    [projects, report] = await Promise.all([
      api('/projects'),
      api('/reports/license-dependencies' + (query ? '?' + query : '')),
    ]);
    if (state.licenseReportProjectId != null) {
      repos = await api('/projects/' + state.licenseReportProjectId + '/repositories');
    }
  } catch (e) {
    showError(e);
    return;
  }

  let entries = report.entries || [];
  if (state.licenseReportOnlyRisky) {
    entries = entries.filter(e => e.risky_count > 0);
  }

  let totalDeps = 0;
  let totalRisky = 0;
  const reposWithRiskySet = new Set();
  entries.forEach(e => {
    totalDeps += e.total;
    totalRisky += e.risky_count;
    if (e.risky_count > 0) reposWithRiskySet.add(e.repository_id);
  });

  const filterRow = `
    <div class="stats-row" style="margin-bottom:16px;flex-wrap:wrap;gap:12px;align-items:center">
      <label style="font-size:12px;color:var(--text-muted)">Project:</label>
      <select id="lr-project" onchange="state.licenseReportProjectId=this.value?parseInt(this.value,10):null; state.licenseReportRepoId=null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;min-width:180px">
        <option value="">All projects</option>
        ${(projects || []).map(p => '<option value="' + p.id + '" ' + (state.licenseReportProjectId === p.id ? 'selected' : '') + '>' + esc(p.name) + '</option>').join('')}
      </select>
      ${state.licenseReportProjectId != null ? `
      <label style="font-size:12px;color:var(--text-muted)">Repository:</label>
      <select id="lr-repo" onchange="state.licenseReportRepoId=this.value?parseInt(this.value,10):null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;min-width:180px">
        <option value="">All repositories</option>
        ${(repos || []).map(r => '<option value="' + r.id + '" ' + (state.licenseReportRepoId === r.id ? 'selected' : '') + '>' + esc(r.name) + '</option>').join('')}
      </select>
      ` : ''}
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer">
        <input type="checkbox" ${state.licenseReportOnlyRisky ? 'checked' : ''} onchange="state.licenseReportOnlyRisky=this.checked; render();">
        Only with risky deps
      </label>
    </div>`;

  const statsRow = `
    <div class="stats-row" style="margin-bottom:24px">
      <div class="stat-box">
        <div class="stat-label">Repos with risky deps</div>
        <div class="stat-value">${reposWithRiskySet.size}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Total dependencies</div>
        <div class="stat-value">${totalDeps}</div>
        <div class="stat-sub">across latest scan per repo</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Risky dependencies</div>
        <div class="stat-value" style="color:${totalRisky > 0 ? 'var(--red,#f87171)' : 'inherit'}">${totalRisky}</div>
      </div>
    </div>`;

  const rows = entries.map(e => {
    const scanDate = e.scan_completed_at || e.scan_started_at;
    const goScan = "navigate('scan', { projectId: " + e.project_id + ", repoId: " + e.repository_id + ", scanId: " + e.scan_id + ", tab: 'dependencies' })";
    const riskScore = e.risk_score;
    const riskColor = riskScore === 0 ? 'var(--green,#4ade80)' : riskScore < 10 ? 'var(--green,#4ade80)' : riskScore < 30 ? 'var(--yellow,#fbbf24)' : 'var(--red,#f87171)';
    const riskBadge = '<span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600;background:' + riskColor + '22;color:' + riskColor + '">' + riskScore + '%</span>';

    const ecosystemTags = Object.entries(e.ecosystem_counts || {}).map(([eco, cnt]) =>
      '<span class="tag">' + esc(eco) + ': ' + cnt + '</span>'
    ).join(' ');

    const riskyDepsList = e.risky_deps && e.risky_deps.length > 0
      ? '<details style="margin-top:6px"><summary style="cursor:pointer;font-size:12px;color:var(--text-muted)">' + e.risky_deps.length + ' risky package' + (e.risky_deps.length === 1 ? '' : 's') + '</summary><table style="margin-top:6px;font-size:12px;width:100%"><thead><tr><th>Package</th><th>Version</th><th>Ecosystem</th><th>License</th></tr></thead><tbody>' +
        e.risky_deps.map(d =>
          '<tr><td>' + esc(d.name) + '</td><td style="color:var(--text-muted)">' + esc(d.version || '—') + '</td><td>' + esc(d.ecosystem || '—') + '</td><td>' + esc(d.license_spdx || d.license_raw || '—') + '</td></tr>'
        ).join('') +
        '</tbody></table></details>'
      : '';

    return '<tr class="row-clickable" onclick="' + goScan + '">' +
      '<td>' + esc(e.project_name) + '</td>' +
      '<td>' + esc(e.repository_name) + '</td>' +
      '<td style="font-size:12px;color:var(--text-muted)">' + fmtDate(scanDate) + ' <a href="#" onclick="event.preventDefault();event.stopPropagation();' + goScan + '" class="link-style">#' + e.scan_id + '</a></td>' +
      '<td>' + e.total + '</td>' +
      '<td style="color:var(--green,#4ade80)">' + e.safe_count + '</td>' +
      '<td style="color:' + (e.risky_count > 0 ? 'var(--red,#f87171)' : 'inherit') + '">' + e.risky_count + '</td>' +
      '<td style="color:var(--text-muted)">' + e.unknown_count + '</td>' +
      '<td>' + riskBadge + '</td>' +
      '<td><div style="display:flex;flex-wrap:wrap;gap:4px">' + (ecosystemTags || '—') + '</div></td>' +
      '<td onclick="event.stopPropagation()">' + riskyDepsList + '</td>' +
      '<td onclick="event.stopPropagation()"><button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:12px" onclick="' + goScan + '">View deps →</button></td>' +
      '</tr>';
  }).join('');

  const tableHtml = entries.length ? `
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>Project</th><th>Repository</th><th>Last scan</th><th>Total</th><th>Safe</th><th>Risky</th><th>Unknown</th><th>Risk score</th><th>Ecosystems</th><th>Risky packages</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    </div>` : '<div class="empty"><div class="icon">📦</div><p>No repositories with completed scans match the filters. Run scans to see license data here.</p></div>';

  setMain(`
    <h1 class="page-title">License Dependencies Report</h1>
    <p class="page-subtitle">License risk breakdown by project and repository (latest completed scan per repo).</p>
    ${filterRow}
    ${statsRow}
    ${tableHtml}
  `);
}
