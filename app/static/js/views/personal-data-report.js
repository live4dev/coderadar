import { state } from '../state.js';
import { api } from '../api.js';
import { esc, fmtDate, setMain, showError } from '../utils.js';

export async function renderPersonalDataReport() {
  setMain('<div class="empty"><span class="spinner"></span> Loading…</div>');
  const params = new URLSearchParams();
  if (state.pdnReportProjectId != null) params.set('project_id', state.pdnReportProjectId);
  if (state.pdnReportRepoId != null) params.set('repository_id', state.pdnReportRepoId);
  const query = params.toString();
  let projects = [];
  let repos = [];
  let report = { entries: [] };
  try {
    [projects, report] = await Promise.all([
      api('/projects'),
      api('/reports/personal-data' + (query ? '?' + query : '')),
    ]);
    if (state.pdnReportProjectId != null) {
      repos = await api('/projects/' + state.pdnReportProjectId + '/repositories');
    }
  } catch (e) {
    showError(e);
    return;
  }
  let entries = report.entries || [];
  if (state.pdnReportOnlyWithFindings) {
    entries = entries.filter(e => {
      const total = (e.counts || []).reduce((sum, c) => sum + c.count, 0);
      return total > 0;
    });
  }
  const projectIdsWithFindings = new Set();
  let reposWithFindingsCount = 0;
  let totalFindings = 0;
  entries.forEach(e => {
    const total = (e.counts || []).reduce((sum, c) => sum + c.count, 0);
    if (total > 0) {
      projectIdsWithFindings.add(e.project_id);
      reposWithFindingsCount += 1;
      totalFindings += total;
    }
  });
  const filterRow = `
    <div class="stats-row" style="margin-bottom:16px;flex-wrap:wrap;gap:12px;align-items:center">
      <label style="font-size:12px;color:var(--text-muted)">Project:</label>
      <select id="pdn-report-project" onchange="state.pdnReportProjectId=this.value?parseInt(this.value,10):null; state.pdnReportRepoId=null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;min-width:180px">
        <option value="">All projects</option>
        ${(projects || []).map(p => '<option value="' + p.id + '" ' + (state.pdnReportProjectId === p.id ? 'selected' : '') + '>' + esc(p.name) + '</option>').join('')}
      </select>
      ${state.pdnReportProjectId != null ? `
      <label style="font-size:12px;color:var(--text-muted)">Repository:</label>
      <select id="pdn-report-repo" onchange="state.pdnReportRepoId=this.value?parseInt(this.value,10):null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;min-width:180px">
        <option value="">All repositories</option>
        ${(repos || []).map(r => '<option value="' + r.id + '" ' + (state.pdnReportRepoId === r.id ? 'selected' : '') + '>' + esc(r.name) + '</option>').join('')}
      </select>
      ` : ''}
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer">
        <input type="checkbox" ${state.pdnReportOnlyWithFindings ? 'checked' : ''} onchange="state.pdnReportOnlyWithFindings=this.checked; render();">
        Only with findings
      </label>
    </div>`;
  const statsRow = `
    <div class="stats-row" style="margin-bottom:24px">
      <div class="stat-box">
        <div class="stat-label">Projects with findings</div>
        <div class="stat-value">${projectIdsWithFindings.size}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Repositories with findings</div>
        <div class="stat-value">${reposWithFindingsCount}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Total findings</div>
        <div class="stat-value">${totalFindings}</div>
        <div class="stat-sub">across latest scan per repo</div>
      </div>
    </div>`;
  const rows = entries.map(e => {
    const total = (e.counts || []).reduce((sum, c) => sum + c.count, 0);
    const countTags = (e.counts || []).map(c => '<span class="tag">' + esc(c.pdn_type) + ': ' + c.count + '</span>').join(' ');
    const scanDate = e.scan_completed_at || e.scan_started_at;
    const goScan = "navigate('scan', { projectId: " + e.project_id + ", repoId: " + e.repository_id + ", scanId: " + e.scan_id + ", tab: 'personal-data' })";
    const sourceLink = e.repository_source_url ? '<a href="' + esc(e.repository_source_url) + '" target="_blank" rel="noopener noreferrer" class="link-style">Open in source</a>' : '—';
    return '<tr class="row-clickable" onclick="' + goScan + '"><td>' + esc(e.project_name) + '</td><td>' + esc(e.repository_name) + '</td><td style="font-size:12px;color:var(--text-muted)">' + fmtDate(scanDate) + ' <a href="#" onclick="event.preventDefault();event.stopPropagation();' + goScan + '" class="link-style">#' + e.scan_id + '</a></td><td>' + total + '</td><td><div style="display:flex;flex-wrap:wrap;gap:4px">' + (countTags || '—') + '</div></td><td onclick="event.stopPropagation()">' + sourceLink + '</td><td onclick="event.stopPropagation()"><button type="button" class="btn btn-outline" style="padding:4px 10px;font-size:12px" onclick="' + goScan + '">View scan →</button></td></tr>';
  }).join('');
  const tableHtml = entries.length ? `
    <table>
      <thead><tr>
        <th>Project</th><th>Repository</th><th>Last scan</th><th>Findings</th><th>By type</th><th>Source</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>` : '<div class="empty"><div class="icon">📋</div><p>No repositories with completed scans match the filters. Run scans and complete them to see personal data findings here.</p></div>';
  setMain(`
    <h1 class="page-title">Personal Data Report</h1>
    <p class="page-subtitle">Findings by project and repository (latest completed scan per repo).</p>
    ${filterRow}
    ${statsRow}
    ${tableHtml}
  `);
}
