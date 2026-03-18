import { state } from '../state.js';
import { api } from '../api.js';
import { esc } from '../utils.js';

export async function buildRisksTab() {
  const risks = await api('/scans/' + state.scanId + '/risks');
  if (!risks.length) return `<div class="empty"><div class="icon">✅</div><p>No risks detected.</p></div>`;

  const counts = {};
  risks.forEach(r => counts[r.severity] = (counts[r.severity] || 0) + 1);

  const summary = ['critical', 'high', 'medium', 'low'].filter(s => counts[s]).map(s =>
    `<div class="stat-box" style="min-width:100px">
      <div class="stat-label">${s}</div>
      <div class="stat-value" style="font-size:28px">${counts[s]}</div>
    </div>`
  ).join('');

  const rows = risks.map(r => `<tr>
    <td><span class="badge ${r.severity}">${r.severity}</span></td>
    <td style="font-weight:500">${esc(r.title)}</td>
    <td style="color:var(--text-muted);font-size:12px">${esc(r.description || '')}</td>
    <td><span class="tag" style="font-size:11px">${esc(r.entity_type || 'project')}</span></td>
  </tr>`).join('');

  return `
    <div class="stats-row" style="margin-bottom:24px">${summary}</div>
    <table>
      <thead><tr><th>Severity</th><th>Risk</th><th>Description</th><th>Scope</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
