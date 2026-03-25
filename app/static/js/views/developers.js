import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, tagsChips, setMain } from '../utils.js';
import { LANG_COLORS } from '../constants.js';

function devSortIcon(col) {
  if (state.devSortBy !== col) return ' <span style="opacity:0.4">↕</span>';
  return state.devSortOrder === 'asc' ? ' <span style="font-size:10px">↑</span>' : ' <span style="font-size:10px">↓</span>';
}

let devSearchDebounce = null;
let devScrollListener = null;
let devLoading = false;

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

function buildDevParams(offset) {
  const params = new URLSearchParams();
  if (state.projectFilter != null) params.set('project_id', state.projectFilter);
  params.set('sort_by', state.devSortBy);
  params.set('order', state.devSortOrder);
  if (state.devSearch && state.devSearch.trim()) params.set('q', state.devSearch.trim());
  if (state.devTagFilter) params.set('tag', state.devTagFilter);
  params.set('offset', offset);
  params.set('limit', 200);
  return params.toString();
}

export function devTagToggle(tag) {
  state.devTagFilter = state.devTagFilter === tag ? null : tag;
  window.render();
}

function devRowHtml(d, totalCommits) {
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
    <td onclick="event.stopPropagation()">${tagsChips(tags)}</td>
  </tr>`;
}

async function loadMoreDevelopers() {
  if (!state.devHasMore || devLoading) return;
  devLoading = true;
  const sentinel = document.getElementById('dev-load-more-sentinel');
  if (sentinel) sentinel.textContent = 'Loading…';

  state.devOffset += 200;
  const data = await api('/developers?' + buildDevParams(state.devOffset));
  state.devItems = state.devItems.concat(data.items);
  state.devHasMore = data.has_more;
  devLoading = false;

  const tbody = document.querySelector('#dev-table tbody');
  if (tbody) {
    tbody.insertAdjacentHTML('beforeend', data.items.map(d => devRowHtml(d, state.devTotalCommitsAll)).join(''));
  }

  if (sentinel) {
    sentinel.textContent = state.devHasMore ? '' : '';
    if (!state.devHasMore) sentinel.style.display = 'none';
  }
}

function attachDevScroll() {
  if (devScrollListener) window.removeEventListener('scroll', devScrollListener);
  devScrollListener = function onDevScroll() {
    const sentinel = document.getElementById('dev-load-more-sentinel');
    if (!sentinel) return;
    const rect = sentinel.getBoundingClientRect();
    if (rect.top < window.innerHeight + 300) loadMoreDevelopers();
  };
  window.addEventListener('scroll', devScrollListener);
}

export async function renderDevelopersSummary() {
  if (devScrollListener) {
    window.removeEventListener('scroll', devScrollListener);
    devScrollListener = null;
  }
  state.devOffset = 0;
  state.devItems = [];
  state.devHasMore = false;
  devLoading = false;

  const [data, projects, allTags] = await Promise.all([
    api('/developers?' + buildDevParams(0)),
    api('/projects'),
    api('/developers/tags'),
  ]);

  state.devItems = data.items;
  state.devHasMore = data.has_more;
  state.devTotalCount = data.total;
  state.devTotalCommitsAll = data.total_commits_all;

  const totalCommits = state.devTotalCommitsAll;
  const topOne = state.devItems.length ? state.devItems[0] : null;

  const tagChipsHtml = allTags.length ? `
    <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:10px">
      <span style="font-size:12px;color:var(--text-muted);margin-right:4px">Tag:</span>
      ${allTags.map(t => {
        const active = state.devTagFilter === t;
        return `<span onclick="devTagToggle(${JSON.stringify(t)})" style="cursor:pointer;font-size:11px;padding:2px 8px;border-radius:4px;border:1px solid ${active ? 'var(--accent)' : 'var(--border)'};background:${active ? 'rgba(99,102,241,0.15)' : 'var(--surface2)'};color:${active ? 'var(--accent-hover)' : 'var(--text-muted)'}">${esc(t)}</span>`;
      }).join('')}
    </div>` : '';

  const filterHtml = `
    <input type="text" id="dev-search" placeholder="Search by name or email…" value="${esc(state.devSearch)}" oninput="devSearchInput();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;width:200px;margin-right:12px">
    ${projects.length ? `
    <label style="font-size:12px;color:var(--text-muted);margin-right:8px">Project:</label>
    <select id="dev-project-filter" onchange="state.projectFilter=this.value?parseInt(this.value,10):null; render();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px">
      <option value="">All projects</option>
      ${projects.map(p => `<option value="${p.id}" ${state.projectFilter === p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
    </select>` : ''}
    ${tagChipsHtml}`;

  const statsRow = `
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Developers</div>
        <div class="stat-value">${fmt(state.devTotalCount)}</div>
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
  if (state.devItems.length && totalCommits > 0) {
    const segments = state.devItems.slice(0, 20).map((d, i) => {
      const pct = (d.total_commits / totalCommits * 100).toFixed(2);
      const label = d.profiles && d.profiles[0] ? (d.profiles[0].display_name || d.profiles[0].canonical_username) : '—';
      return `<div class="lang-segment" style="width:${pct}%;background:${LANG_COLORS[i % LANG_COLORS.length]}" title="${esc(label)} ${pct}%"></div>`;
    }).join('');
    barHtml = `<div class="section-title" style="margin-bottom:8px">Commit share</div><div class="lang-bar">${segments}</div>`;
  }

  let tableHtml = '';
  if (state.devItems.length) {
    const tableRows = state.devItems.map(d => devRowHtml(d, totalCommits)).join('');
    tableHtml = `
    <table id="dev-table">
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
    </table>
    <div id="dev-load-more-sentinel" style="text-align:center;padding:16px;color:var(--text-muted);font-size:13px">${state.devHasMore ? '' : ''}</div>`;
  } else {
    tableHtml = `<div class="empty"><div class="icon">👥</div><p>${(state.devSearch && state.devSearch.trim()) || state.devTagFilter ? 'No developers match your filters.' : 'No developers yet. Run scans on repositories to see contributors.'}</p></div>`;
  }

  setMain(`
    <div class="page-title">Developers</div>
    <div class="page-subtitle">All developers across projects and repositories · aggregated by scan</div>
    ${statsRow}
    ${barHtml ? '<div style="margin-bottom:24px">' + barHtml + '</div>' : ''}
    ${tableHtml}
  `);

  if (state.devHasMore) attachDevScroll();
}
