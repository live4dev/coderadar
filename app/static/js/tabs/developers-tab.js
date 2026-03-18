import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, tagsChips } from '../utils.js';

export async function buildDevelopersTab() {
  const devs = await api('/scans/' + state.scanId + '/developers');
  if (!devs.length) return `<div class="empty"><div class="icon">👥</div><p>No developer data.</p></div>`;

  const total = devs.reduce((s, d) => s + d.commit_count, 0);

  const rows = devs.map(d => {
    const share = total > 0 ? (d.commit_count / total * 100).toFixed(1) : 0;
    const p = d.profile || {};
    const name = p.display_name || p.canonical_username || '—';
    const tags = d.tags || [];
    return `<tr class="row-clickable" onclick="navigate('developer', { developerId: ${d.developer_id} })">
      <td>
        <div style="font-weight:600">${esc(name)}</div>
        <div style="font-size:11px;color:var(--text-muted)">${esc(p.primary_email || '')}</div>
      </td>
      <td>${fmt(d.commit_count)}</td>
      <td>
        <div class="score-bar-wrap">
          <div class="score-bar"><div class="score-fill high" style="width:${share}%"></div></div>
          <span style="min-width:36px;text-align:right;font-size:12px">${share}%</span>
        </div>
      </td>
      <td>${fmt(d.insertions)}</td>
      <td>${fmt(d.deletions)}</td>
      <td>${fmt(d.files_changed)}</td>
      <td>${fmt(d.active_days)} days</td>
      <td style="font-size:11px;color:var(--text-muted)">${fmtDate(d.last_commit_at)}</td>
      <td onclick="event.stopPropagation()">${tagsChips(tags)}<button class="btn btn-outline" style="margin-top:4px;padding:2px 8px;font-size:11px" onclick="openEditTagsModal('developer', ${d.developer_id}, ${JSON.stringify(tags)}, ${JSON.stringify(name)})">Edit tags</button></td>
      <td onclick="event.stopPropagation()"><button class="btn btn-outline" style="padding:4px 10px;font-size:12px" onclick="navigate('developer', { developerId: ${d.developer_id} })">Profile →</button></td>
    </tr>`;
  }).join('');

  return `
    <p style="font-size:12px;color:var(--text-muted);margin-bottom:12px">Scan-only view. <a href="#" onclick="navigate('developers'); return false;" style="color:var(--accent-hover)">View all developers across projects →</a></p>
    <table>
      <thead><tr>
        <th>Developer</th><th>Commits</th><th>Share</th>
        <th>Insertions</th><th>Deletions</th><th>Files</th>
        <th>Active days</th><th>Last commit</th><th>Tags</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
