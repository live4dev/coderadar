import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, scoreClass, tagsChips, setMain } from '../utils.js';

function projSortIcon(col) {
  if (state.projSortBy !== col) return ' <span style="opacity:0.4">↕</span>';
  return state.projSortOrder === 'asc' ? ' <span style="font-size:10px">↑</span>' : ' <span style="font-size:10px">↓</span>';
}

let projSearchDebounce = null;

export function projSort(col) {
  if (state.projSortBy === col) state.projSortOrder = state.projSortOrder === 'asc' ? 'desc' : 'asc';
  else { state.projSortBy = col; state.projSortOrder = (col === 'name' || col === 'id' ? 'asc' : 'desc'); }
  window.render();
}

export function projSearchInput() {
  state.projSearch = document.getElementById('proj-search').value;
  if (projSearchDebounce) clearTimeout(projSearchDebounce);
  projSearchDebounce = setTimeout(() => { projSearchDebounce = null; window.render(); }, 280);
}

export async function renderProjects() {
  const params = new URLSearchParams();
  params.set('sort_by', state.projSortBy);
  params.set('order', state.projSortOrder);
  if (state.projSearch && state.projSearch.trim()) params.set('q', state.projSearch.trim());
  if (state.projHasScans) params.set('has_scans', 'true');
  const query = params.toString();
  const projects = await api('/projects/summary' + (query ? '?' + query : ''));
  const hasFilters = (state.projSearch && state.projSearch.trim()) || state.projHasScans;
  let html = `
    <div class="page-title">Projects</div>
    <div class="page-subtitle">${projects.length} project${projects.length !== 1 ? 's' : ''}</div>
    <div class="stats-row" style="margin-bottom:16px;flex-wrap:wrap;gap:12px">
      <input type="text" id="proj-search" placeholder="Search by name or description…" value="${esc(state.projSearch)}" oninput="projSearchInput();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;width:240px">
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer">
        <input type="checkbox" ${state.projHasScans ? 'checked' : ''} onchange="state.projHasScans=this.checked; render();">
        With scans only
      </label>
    </div>
  `;

  if (!projects.length) {
    html += `<div class="empty"><div class="icon">📂</div><p>${hasFilters ? 'No projects match your filters.' : 'No projects yet. Add one via the API.'}</p></div>`;
  } else {
    const rows = projects.map(p => {
      const hasScans = p.repos_with_completed_scan > 0;
      const scanHealth = p.repo_count > 0 ? p.repos_with_completed_scan + '/' + p.repo_count : '—';
      const scoreCls = p.avg_score != null ? scoreClass(p.avg_score) : '';
      const tags = p.tags || [];
      return `<tr class="row-clickable" onclick="navigate('repos', {projectId: ${p.id}})">
        <td>
          <div style="font-weight:600">${esc(p.name)}</div>
          <div style="font-size:11px;color:var(--text-muted)">${esc(p.description || 'No description')}</div>
        </td>
        <td style="font-size:12px;color:var(--text-muted)">${p.id}</td>
        <td>${p.repo_count}</td>
        <td>${scanHealth}</td>
        <td>${hasScans && p.total_loc != null ? fmt(p.total_loc) : '—'}</td>
        <td>${hasScans && p.total_files != null ? fmt(p.total_files) : '—'}</td>
        <td>${p.avg_score != null ? `<div class="score-bar-wrap"><div class="score-bar"><div class="score-fill ${scoreCls}" style="width:${p.avg_score}%"></div></div><span class="score-num">${p.avg_score.toFixed(0)}</span></div>` : '—'}</td>
        <td style="font-size:11px;color:var(--text-muted)">${p.last_scan_at ? fmtDate(p.last_scan_at) : '—'}</td>
        <td onclick="event.stopPropagation()">${tagsChips(tags)}<button class="btn btn-outline" style="margin-top:4px;padding:2px 8px;font-size:11px" onclick="openEditTagsModal('project', ${p.id}, ${JSON.stringify(tags)}, ${JSON.stringify(p.name)})">Edit tags</button></td>
        <td><span class="tag accent">View repos →</span></td>
      </tr>`;
    }).join('');
    html += `
    <table>
      <thead><tr>
        <th class="sortable" onclick="projSort('name')" title="Sort by name">Project${projSortIcon('name')}</th>
        <th class="sortable" onclick="projSort('id')" title="Sort by ID">ID${projSortIcon('id')}</th>
        <th class="sortable" onclick="projSort('repo_count')" title="Sort by repos">Repos${projSortIcon('repo_count')}</th>
        <th class="sortable" onclick="projSort('scanned')" title="Sort by scanned">Scanned${projSortIcon('scanned')}</th>
        <th class="sortable" onclick="projSort('loc')" title="Sort by LOC">LOC${projSortIcon('loc')}</th>
        <th class="sortable" onclick="projSort('files')" title="Sort by files">Files${projSortIcon('files')}</th>
        <th class="sortable" onclick="projSort('avg_score')" title="Sort by score">Avg score${projSortIcon('avg_score')}</th>
        <th class="sortable" onclick="projSort('last_scan_at')" title="Sort by last scan">Last scan${projSortIcon('last_scan_at')}</th>
        <th>Tags</th>
        <th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
  setMain(html);
}
