import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, scoreClass, tagsChips, setMain } from '../utils.js';
import { updateNav } from '../nav.js';

function repoSortIcon(col) {
  if (state.repoSortBy !== col) return ' <span style="opacity:0.4">↕</span>';
  return state.repoSortOrder === 'asc' ? ' <span style="font-size:10px">↑</span>' : ' <span style="font-size:10px">↓</span>';
}

let repoSearchDebounce = null;

export function repoSort(col) {
  if (state.repoSortBy === col) state.repoSortOrder = state.repoSortOrder === 'asc' ? 'desc' : 'asc';
  else { state.repoSortBy = col; state.repoSortOrder = (col === 'name' || col === 'id' ? 'asc' : 'desc'); }
  window.render();
}

export function repoSearchInput() {
  state.repoSearch = document.getElementById('repo-search').value;
  if (repoSearchDebounce) clearTimeout(repoSearchDebounce);
  repoSearchDebounce = setTimeout(() => { repoSearchDebounce = null; window.render(); }, 280);
}

export async function renderRepos() {
  const params = new URLSearchParams();
  params.set('sort_by', state.repoSortBy);
  params.set('order', state.repoSortOrder);
  if (state.repoSearch && state.repoSearch.trim()) params.set('q', state.repoSearch.trim());
  if (state.repoHasScans) params.set('has_scans', 'true');
  const query = params.toString();
  const [project, allRepos, activity] = await Promise.all([
    api('/projects/' + state.projectId),
    api('/projects/' + state.projectId + '/repositories/with-latest-scan' + (query ? '?' + query : '')),
    api('/projects/' + state.projectId + '/activity'),
  ]);
  const hasFilters = (state.repoSearch && state.repoSearch.trim()) || state.repoHasScans;

  // Calendar config (last 365 days)
  const today = new Date();
  const yearAgo = new Date(today);
  yearAgo.setFullYear(today.getFullYear() - 1);
  const calStart = yearAgo.toISOString().slice(0, 10);
  const calEnd = today.toISOString().slice(0, 10);
  const calData = activity.map(d => [d.date, d.count]);
  const maxCount = calData.reduce((m, d) => Math.max(m, d[1]), 0);
  const calendarHtml = activity.length ? `
    <div style="margin-bottom:24px">
      <div class="section-header"><div class="section-title">Commit activity</div></div>
      <div id="proj-contrib-calendar" style="height:160px;width:100%"></div>
    </div>` : '';

  let html = `
    <div class="page-title">${esc(project.name)}</div>
    <div class="page-subtitle">${esc(project.description || '')} · ${allRepos.length} repositor${allRepos.length !== 1 ? 'ies' : 'y'}</div>
    ${calendarHtml}
    <div class="stats-row" style="margin-bottom:16px;flex-wrap:wrap;gap:12px">
      <input type="text" id="repo-search" placeholder="Search by name or URL…" value="${esc(state.repoSearch)}" oninput="repoSearchInput();" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px;width:240px">
      <label style="display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--text-muted);cursor:pointer">
        <input type="checkbox" ${state.repoHasScans ? 'checked' : ''} onchange="state.repoHasScans=this.checked; render();">
        With scans only
      </label>
    </div>
  `;

  if (!allRepos.length) {
    html += `<div class="empty"><div class="icon">📦</div><p>${hasFilters ? 'No repositories match your filters.' : 'No repositories. Add one via the API or create a scan with local_scan.py.'}</p></div>`;
  } else {
    const rows = allRepos.map(r => {
      const ls = r.latest_scan;
      const lastUpdated = ls && (ls.completed_at || ls.started_at);
      const score = ls && ls.overall_score != null ? ls.overall_score : null;
      const scoreCls = score != null ? scoreClass(score) : '';
      const tags = r.tags || [];
      return `<tr class="row-clickable" onclick="navigate('scans', { projectId: ${state.projectId}, repoId: ${r.id} })">
        <td>
          <div style="font-weight:600">${esc(r.name)}</div>
          <div style="font-size:11px;color:var(--text-muted)">${esc(r.provider_type)}${r.default_branch ? ' · ' + esc(r.default_branch) : ''}</div>
        </td>
        <td>${ls && ls.total_loc != null ? fmt(ls.total_loc) : '—'}</td>
        <td>${ls && ls.total_files != null ? fmt(ls.total_files) : '—'}</td>
        <td style="text-transform:capitalize">${ls && ls.project_type ? esc(String(ls.project_type).replace(/_/g, ' ')) : '—'}</td>
        <td style="font-size:12px;color:var(--text-muted)">${fmtDate(lastUpdated)}</td>
        <td>${ls && ls.primary_language ? esc(ls.primary_language) : '—'}</td>
        <td>${score != null ? `<div class="score-bar-wrap"><div class="score-bar"><div class="score-fill ${scoreCls}" style="width:${score}%"></div></div><span class="score-num">${score.toFixed(0)}</span></div>` : '—'}</td>
        <td onclick="event.stopPropagation()">${tagsChips(tags)}<button class="btn btn-outline" style="margin-top:4px;padding:2px 8px;font-size:11px" onclick="openEditTagsModal('repository', ${r.id}, ${JSON.stringify(tags)}, ${JSON.stringify(r.name)})">Edit tags</button></td>
        <td onclick="event.stopPropagation()">
            <a href="#" onclick="navigate('scans', { projectId: ${state.projectId}, repoId: ${r.id} })" class="link-style">View →</a>
        </td>
      </tr>`;
    }).join('');
    html += `
    <table>
      <thead><tr>
        <th class="sortable" onclick="repoSort('name')" title="Sort by name">Repository${repoSortIcon('name')}</th>
        <th class="sortable" onclick="repoSort('loc')" title="Sort by LOC">Lines of code${repoSortIcon('loc')}</th>
        <th class="sortable" onclick="repoSort('files')" title="Sort by files">Files${repoSortIcon('files')}</th>
        <th class="sortable" onclick="repoSort('project_type')" title="Sort by project type">Project type${repoSortIcon('project_type')}</th>
        <th class="sortable" onclick="repoSort('last_updated')" title="Sort by last updated">Last updated${repoSortIcon('last_updated')}</th>
        <th class="sortable" onclick="repoSort('primary_language')" title="Sort by language">Primary language${repoSortIcon('primary_language')}</th>
        <th class="sortable" onclick="repoSort('score')" title="Sort by score">Score${repoSortIcon('score')}</th>
        <th></th>
        <th>Tags</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
  }
  state.projectName = project.name;
  setMain(html);
  updateNav();

  const calEl = document.getElementById('proj-contrib-calendar');
  if (calEl && window.echarts) {
    const chart = window.echarts.init(calEl, null, { renderer: 'svg' });
    chart.setOption({
      tooltip: {
        formatter: p => `${p.data[0]}<br/><b>${p.data[1]} commit${p.data[1] !== 1 ? 's' : ''}</b>`,
      },
      visualMap: {
        show: false,
        min: 0,
        max: Math.max(maxCount, 1),
        inRange: { color: ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353'] },
      },
      calendar: {
        range: [calStart, calEnd],
        cellSize: [13, 13],
        left: 36,
        right: 12,
        top: 20,
        bottom: 10,
        itemStyle: { borderColor: '#0d1117', borderWidth: 2 },
        splitLine: { show: false },
        yearLabel: { show: false },
        monthLabel: { color: 'var(--text-muted)', fontSize: 11 },
        dayLabel: {
          firstDay: 1,
          nameMap: ['', 'Mon', '', 'Wed', '', 'Fri', ''],
          color: 'var(--text-muted)',
          fontSize: 10,
        },
      },
      series: [{ type: 'heatmap', coordinateSystem: 'calendar', data: calData }],
    });
    window.addEventListener('resize', () => chart.resize());
  }
}
