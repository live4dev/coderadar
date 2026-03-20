import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, fmtDate, esc, setMain, showError } from '../utils.js';
import { updateNav } from '../nav.js';
import { buildGitTagsTab } from '../tabs/git-tags.js';

let repoTab = 'scans';

export function showRepoTab(tab) {
  repoTab = tab;
  renderScans();
}

export async function renderScans() {
  const [project, repo, scans, activity] = await Promise.all([
    api('/projects/' + state.projectId),
    api('/repositories/' + state.repoId),
    api('/repositories/' + state.repoId + '/scans'),
    api('/repositories/' + state.repoId + '/activity'),
  ]);
  state.projectName = project.name;
  state.repoName = repo.name;

  const tabLabels = { scans: 'Scans', 'git-tags': 'Git Tags' };
  const tabs = ['scans', 'git-tags']
    .map(t => `<div class="tab ${repoTab === t ? 'active' : ''}" onclick="showRepoTab('${t}')">${tabLabels[t]}</div>`)
    .join('');

  // Build calendar data
  const today = new Date();
  const yearAgo = new Date(today);
  yearAgo.setFullYear(today.getFullYear() - 1);
  const calStart = yearAgo.toISOString().slice(0, 10);
  const calEnd = today.toISOString().slice(0, 10);
  const calData = activity.map(d => [d.date, d.count]);
  const maxCount = calData.reduce((m, d) => Math.max(m, d[1]), 0);

  let content = '';
  if (repoTab === 'scans') {
    const calendarHtml = scans.length ? `
      <div style="margin-bottom:24px">
        <div class="section-header"><div class="section-title">Commit activity</div></div>
        <div id="repo-contrib-calendar" style="height:160px;width:100%"></div>
      </div>` : '';

    if (!scans.length) {
      content = `<div class="empty"><div class="icon">🔍</div><p>No scans yet. Click "Run Scan" to start.</p></div>`;
    } else {
      let table = `<table>
        <thead><tr>
          <th>ID</th><th>Branch</th><th>Status</th>
          <th>Files</th><th>LOC</th><th>Language</th>
          <th>Started</th><th></th>
        </tr></thead><tbody>`;
      for (const s of scans) {
        const scanNav = "navigate('scan', {projectId: " + state.projectId + ", repoId: " + state.repoId + ", scanId: " + s.id + ", tab:'summary'})";
        table += `<tr class="row-clickable" onclick="${scanNav}">
          <td><a href="#" onclick="event.stopPropagation(); ${scanNav}" class="link-style">#${s.id}</a></td>
          <td><code style="font-size:12px">${esc(s.branch)}</code></td>
          <td><span class="status ${s.status}">${esc(s.status)}</span></td>
          <td>${fmt(s.total_files)}</td>
          <td>${fmt(s.total_loc)}</td>
          <td>${esc(s.primary_language || '—')}</td>
          <td>${fmtDate(s.started_at)}</td>
          <td>
            <a href="#" onclick="event.stopPropagation(); ${scanNav}" class="link-style">View →</a>
          </td>
        </tr>`;
      }
      table += '</tbody></table>';
      content = calendarHtml + table;
    }
  } else if (repoTab === 'git-tags') {
    content = await buildGitTagsTab();
  }

  setMain(`
    <div class="section-header">
      <div>
        <div class="page-title">${esc(repo.name)}</div>
        <div class="page-subtitle">${esc(repo.url)}</div>
      </div>
      <button class="btn btn-primary" id="scan-btn" onclick="triggerScan()">▶ Run Scan</button>
    </div>
    <div class="tabs">${tabs}</div>
    ${content}
  `);
  updateNav();

  // Render ECharts contribution calendar (only on scans tab with data)
  const calEl = document.getElementById('repo-contrib-calendar');
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
        inRange: {
          color: ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353'],
        },
      },
      calendar: {
        range: [calStart, calEnd],
        cellSize: [13, 13],
        left: 36,
        right: 12,
        top: 20,
        bottom: 10,
       itemStyle: { color: '#191C26', borderColor: '#0d1117', borderWidth: 2 },
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
      series: [{
        type: 'heatmap',
        coordinateSystem: 'calendar',
        data: calData,
      }],
    });
    window.addEventListener('resize', () => chart.resize());
  }
}

export async function triggerScan() {
  const btn = document.getElementById('scan-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Starting…'; }
  try {
    const result = await api('/repositories/' + state.repoId + '/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    await pollScan(result.scan_id || result.id);
    await renderScans();
  } catch (e) {
    showError(e);
  }
}

export async function pollScan(scanId) {
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const scan = await api('/scans/' + scanId);
    if (scan.status === 'completed' || scan.status === 'failed') return scan;
    const btn = document.getElementById('scan-btn');
    if (btn) btn.innerHTML = '<span class="spinner"></span> Scanning…';
  }
}
