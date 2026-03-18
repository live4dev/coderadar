import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, tagsChips, setMain } from '../utils.js';
import { LANG_COLORS } from '../constants.js';

function devSortIcon(col) {
  if (state.devSortBy !== col) return ' <span style="opacity:0.4">↕</span>';
  return state.devSortOrder === 'asc' ? ' <span style="font-size:10px">↑</span>' : ' <span style="font-size:10px">↓</span>';
}

let devSearchDebounce = null;

export function devSort(col) {
  if (state.devSortBy === col) state.devSortOrder = state.devSortOrder === 'asc' ? 'desc' : 'asc';
  else { state.devSortBy = col; state.devSortOrder = (col === 'name' ? 'asc' : 'desc'); }
  window.render();
}

export function devSearchInput() {
  state.devSearch = document.getElementById('dev-search').value;
  if (devSearchDebounce) clearTimeout(devSearchDebounce);
  devSearchDebounce = setTimeout(() => { devSearchDebounce = null; window.render(); }, 280);
}

export async function renderDevelopersSummary() {
  const params = new URLSearchParams();
  if (state.projectFilter != null) params.set('project_id', state.projectFilter);
  params.set('sort_by', state.devSortBy);
  params.set('order', state.devSortOrder);
  if (state.devSearch && state.devSearch.trim()) params.set('q', state.devSearch.trim());
  const query = params.toString();
  const [devs, projects] = await Promise.all([
    api('/developers' + (query ? '?' + query : '')),
    api('/projects'),
  ]);

  const totalCommits = devs.reduce((s, d) => s + d.total_commits, 0);
  const topOne = devs.length ? devs[0] : null;

  const filterHtml = `
    <input type="text" id="dev-search" placeholder="Search by name or email…" value="${esc(state.devSearch)}" oninput="devSearchInput();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;width:200px;margin-right:12px">
    ${projects.length ? `
    <label style="font-size:12px;color:var(--text-muted);margin-right:8px">Project:</label>
    <select id="dev-project-filter" onchange="state.projectFilter=this.value?parseInt(this.value,10):null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px">
      <option value="">All projects</option>
      ${projects.map(p => `<option value="${p.id}" ${state.projectFilter === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
    </select>` : ''}`;

  const statsRow = `
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Developers</div>
        <div class="stat-value">${devs.length}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Total commits</div>
        <div class="stat-value">${fmt(totalCommits)}</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Top contributor</div>
        <div class="stat-value" style="font-size:14px">${topOne && topOne.profiles && topOne.profiles[0] ? esc(topOne.profiles[0].display_name || topOne.profiles[0].canonical_username) : '—'}</div>
        <div class="stat-sub">${topOne && topOne.project_name ? esc(topOne.project_name) : ''}</div>
      </div>
      <div class="stat-box" style="align-self:flex-end">${filterHtml}</div>
    </div>`;

  let barHtml = '';
  if (devs.length && totalCommits > 0) {
    const segments = devs.slice(0, 20).map((d, i) => {
      const pct = (d.total_commits / totalCommits * 100).toFixed(2);
      const label = d.profiles && d.profiles[0] ? (d.profiles[0].display_name || d.profiles[0].canonical_username) : '—';
      return `<div class="lang-segment" style="width:${pct}%;background:${LANG_COLORS[i % LANG_COLORS.length]}" title="${esc(label)} ${pct}%"></div>`;
    }).join('');
    barHtml = `<div class="section-title" style="margin-bottom:8px">Commit share</div><div class="lang-bar">${segments}</div>`;
  }

  let tableRows = '';
  if (devs.length) {
    tableRows = devs.map(d => {
      const share = totalCommits > 0 ? (d.total_commits / totalCommits * 100).toFixed(1) : 0;
      const first = d.profiles && d.profiles[0];
      const devName = first ? (first.display_name || first.canonical_username) : '—';
      const devEmail = first ? (first.primary_email || '') : '';
      const extraProfiles = d.profiles && d.profiles.length > 1 ? `<div style="font-size:10px;color:var(--text-muted)">+${d.profiles.length - 1} profile(s)</div>` : '';
      const tags = d.tags || [];
      return `<tr class="row-clickable" onclick="navigate('developer', { developerId: ${d.id} })">
        <td>
          <div style="font-weight:600">${esc(devName)}</div>
          <div style="font-size:11px;color:var(--text-muted)">${esc(devEmail)}</div>
          ${extraProfiles}
        </td>
        <td>${fmt(d.total_commits)}</td>
        <td>
          <div class="score-bar-wrap">
            <div class="score-bar"><div class="score-fill high" style="width:${Math.min(share, 100)}%"></div></div>
            <span style="min-width:36px;text-align:right;font-size:12px">${share}%</span>
          </div>
        </td>
        <td>${fmt(d.total_insertions)}</td>
        <td>${fmt(d.total_deletions)}</td>
        <td>${fmt(d.files_changed)}</td>
        <td>${fmt(d.active_days)}</td>
        <td style="font-size:11px;color:var(--text-muted)">${fmtDate(d.last_commit_at)}</td>
        <td onclick="event.stopPropagation()">${tagsChips(tags)}<button class="btn btn-outline" style="margin-top:4px;padding:2px 8px;font-size:11px" onclick="openEditTagsModal('developer', ${d.id}, ${JSON.stringify(tags)}, ${JSON.stringify(devName)})">Edit tags</button></td>
      </tr>`;
    }).join('');
  }

  const tableHtml = devs.length ? `
    <table>
      <thead><tr>
        <th class="sortable" onclick="devSort('name')" title="Sort by name">Developer${devSortIcon('name')}</th>
        <th class="sortable" onclick="devSort('commits')" title="Sort by commits">Commits${devSortIcon('commits')}</th>
        <th>Share</th>
        <th class="sortable" onclick="devSort('insertions')" title="Sort by insertions">Insertions${devSortIcon('insertions')}</th>
        <th class="sortable" onclick="devSort('deletions')" title="Sort by deletions">Deletions${devSortIcon('deletions')}</th>
        <th class="sortable" onclick="devSort('files_changed')" title="Sort by files">Files${devSortIcon('files_changed')}</th>
        <th class="sortable" onclick="devSort('active_days')" title="Sort by active days">Active days${devSortIcon('active_days')}</th>
        <th class="sortable" onclick="devSort('last_commit_at')" title="Sort by last commit">Last commit${devSortIcon('last_commit_at')}</th>
        <th>Tags</th>
      </tr></thead>
      <tbody>${tableRows}</tbody>
    </table>` : `<div class="empty"><div class="icon">👥</div><p>${state.devSearch && state.devSearch.trim() ? 'No developers match your search.' : 'No developers yet. Run scans on repositories to see contributors.'}</p></div>`;

  setMain(`
    <div class="page-title">Developers</div>
    <div class="page-subtitle">All developers across projects and repositories · aggregated by scan</div>
    ${statsRow}
    ${barHtml ? '<div style="margin-bottom:24px">' + barHtml + '</div>' : ''}
    ${tableHtml}
  `);
}
