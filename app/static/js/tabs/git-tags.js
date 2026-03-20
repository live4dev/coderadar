import { api } from '../api.js';
import { esc, fmtDate } from '../utils.js';
import { state } from '../state.js';

export async function buildGitTagsTab() {
  const tags = await api('/repositories/' + state.repoId + '/git-tags');

  if (!tags.length) {
    return `<div class="empty"><div class="icon">🏷</div><p>No git tags found. Run a scan to fetch tags from the repository.</p></div>`;
  }

  const rows = tags.map(t => `
    <tr>
      <td><strong>${esc(t.name)}</strong></td>
      <td>${t.sha ? `<code style="font-size:11px">${esc(t.sha.slice(0, 8))}</code>` : '—'}</td>
      <td>${esc(t.message || '—')}</td>
      <td>${t.tagger_name ? esc(t.tagger_name) : '—'}</td>
      <td>${fmtDate(t.tagged_at)}</td>
    </tr>`).join('');

  return `
    <table>
      <thead><tr>
        <th>Tag</th><th>Commit</th><th>Message</th><th>Tagger</th><th>Date</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
