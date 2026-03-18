import { state } from '../state.js';
import { api } from '../api.js';
import { esc, fmtDate } from '../utils.js';

export async function buildPersonalDataTab(scan) {
  if (scan.status !== 'completed') {
    return '<div class="empty"><div class="icon">🔍</div><p>Run a scan and wait for it to complete to see personal data findings.</p></div>';
  }
  let data;
  try {
    data = await api('/scans/' + state.scanId + '/personal-data');
  } catch (e) {
    return '<div class="empty"><div class="icon">⚠️</div><p>Could not load personal data results.</p></div>';
  }
  const counts = data.counts || [];
  const findings = data.findings || [];
  if (!counts.length && !findings.length) {
    return '<div class="empty"><div class="icon">✅</div><p>No personal data identifiers found in this scan.</p></div>';
  }
  const countBoxes = counts.map(c =>
    `<div class="stat-box" style="min-width:100px"><div class="stat-label">${esc(c.pdn_type)}</div><div class="stat-value">${c.count}</div></div>`
  ).join('');
  const rows = findings.map(f => {
    const pathLine = esc(f.file_path) + ':' + f.line_number;
    const sourceLink = f.source_url ? '<a href="' + esc(f.source_url) + '" target="_blank" rel="noopener noreferrer" class="link-style">Open in source</a>' : '';
    return `<tr>
      <td><span class="tag">${esc(f.pdn_type)}</span></td>
      <td><code style="font-size:12px">${esc(f.matched_identifier)}</code></td>
      <td style="font-size:12px;word-break:break-all">${pathLine}</td>
      <td>${sourceLink}</td>
    </tr>`;
  }).join('');
  return `
    <div class="stats-row" style="margin-bottom:20px;flex-wrap:wrap">${countBoxes}</div>
    <table>
      <thead><tr><th>Data type</th><th>Variable name</th><th>Path:Line</th><th>Source</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
