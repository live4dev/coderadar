import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, tagsChips, setMain } from '../utils.js';
import { LANG_COLORS } from '../constants.js';

export async function renderDeveloperProfile() {
  const [dev, contributions, languages, modules] = await Promise.all([
    api('/developers/' + state.developerId),
    api('/developers/' + state.developerId + '/contributions'),
    api('/developers/' + state.developerId + '/languages'),
    api('/developers/' + state.developerId + '/modules'),
  ]);

  const statsRow = `
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Commits</div>
        <div class="stat-value">${fmt(contributions.commit_count)}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Insertions</div>
        <div class="stat-value">${fmt(contributions.insertions)}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Deletions</div>
        <div class="stat-value">${fmt(contributions.deletions)}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Files changed</div>
        <div class="stat-value">${fmt(contributions.files_changed)}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Active days</div>
        <div class="stat-value">${contributions.active_days}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Share in project</div>
        <div class="stat-value">${contributions.share_pct != null ? contributions.share_pct.toFixed(1) + '%' : '—'}</div>
        <div class="stat-sub">${contributions.project_total_commits != null ? 'of ' + fmt(contributions.project_total_commits) + ' commits' : ''}</div>
      </div>
    </div>`;

  let langsHtml = '';
  if (languages.length) {
    const totalLoc = languages.reduce((s, l) => s + (l.loc_added || 0), 0);
    const segments = languages.map((l, i) => {
      const pct = totalLoc > 0 ? (l.loc_added / totalLoc * 100).toFixed(2) : 0;
      return `<div class="lang-segment" style="width:${pct}%;background:${LANG_COLORS[i % LANG_COLORS.length]}"></div>`;
    }).join('');
    const rows = languages.map(l => `<tr>
      <td>${esc(l.language)}</td>
      <td>${fmt(l.commit_count)}</td>
      <td>${fmt(l.files_changed)}</td>
      <td>${fmt(l.loc_added)}</td>
      <td><div class="score-bar-wrap"><div class="score-bar"><div class="score-fill high" style="width:${l.percentage}%"></div></div><span class="score-num">${l.percentage.toFixed(1)}%</span></div></td>
    </tr>`).join('');
    langsHtml = `
      <div class="section-header"><div class="section-title">By language</div></div>
      <div class="lang-bar" style="margin-bottom:12px">${segments}</div>
      <table>
        <thead><tr><th>Language</th><th>Commits</th><th>Files</th><th>LOC added</th><th>Share</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  let modsHtml = '';
  if (modules.length) {
    const rows = modules.map(m => `<tr>
      <td><code style="font-size:11px">${esc(m.module_path)}</code></td>
      <td>${esc(m.module_name)}</td>
      <td>${fmt(m.commit_count)}</td>
      <td>${fmt(m.files_changed)}</td>
      <td>${fmt(m.loc_added)}</td>
      <td>${m.percentage.toFixed(1)}%</td>
    </tr>`).join('');
    modsHtml = `
      <div class="section-header"><div class="section-title">By module</div></div>
      <table>
        <thead><tr><th>Path</th><th>Module</th><th>Commits</th><th>Files</th><th>LOC added</th><th>Share</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  const profiles = dev.profiles || [];
  const primaryName = profiles[0] ? (profiles[0].display_name || profiles[0].canonical_username) : ('Developer #' + dev.id);
  const devTags = dev.tags || [];
  const tagsBlock = `
    <div class="section-header" style="margin-top:20px"><div class="section-title">Tags</div></div>
    <div style="margin-bottom:20px">
      ${tagsChips(devTags)}
      <button class="btn btn-outline" style="margin-top:8px;padding:4px 12px;font-size:12px" onclick="openEditTagsModal('developer', ${dev.id}, ${JSON.stringify(devTags)}, ${JSON.stringify(primaryName)})">Edit tags</button>
    </div>`;
  const profilesBlock = profiles.length ? `
    <div class="section-header" style="margin-top:20px"><div class="section-title">Profiles (${profiles.length})</div></div>
    <div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px">
      ${profiles.map(p => `
        <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px 16px;min-width:180px">
          <div style="font-weight:600;font-size:13px">${esc(p.display_name || p.canonical_username)}</div>
          <div style="font-size:11px;color:var(--text-muted);margin-top:4px">${esc(p.canonical_username)}</div>
          ${p.primary_email ? `<div style="font-size:11px;color:var(--text-muted)">${esc(p.primary_email)}</div>` : ''}
        </div>
      `).join('')}
    </div>` : '';

  setMain(`
    <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:20px">
      <div>
        <div class="page-title">${esc(primaryName)}</div>
        <div class="page-subtitle">Developer #${dev.id}${profiles.length > 0 ? ' · ' + profiles.length + ' profile(s)' : ''}</div>
      </div>
      <button class="btn btn-outline" onclick="navigate('developers')">← Back to developers</button>
    </div>
    ${tagsBlock}
    ${profilesBlock}
    <div style="margin-bottom:16px;font-size:12px;color:var(--text-muted)">
      First commit: ${fmtDate(contributions.first_commit_at)} · Last commit: ${fmtDate(contributions.last_commit_at)}
    </div>
    ${statsRow}
    ${langsHtml}
    ${modsHtml ? '<div style="margin-top:28px">' + modsHtml + '</div>' : ''}
  `);
}
