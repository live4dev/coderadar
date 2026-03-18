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
  const [project, repo, scans] = await Promise.all([
    api('/projects/' + state.projectId),
    api('/repositories/' + state.repoId),
    api('/repositories/' + state.repoId + '/scans'),
  ]);
  state.projectName = project.name;
  state.repoName = repo.name;

  const tabLabels = { scans: 'Scans', 'git-tags': 'Git Tags' };
  const tabs = ['scans', 'git-tags']
    .map(t => `<div class="tab ${repoTab === t ? 'active' : ''}" onclick="showRepoTab('${t}')">${tabLabels[t]}</div>`)
    .join('');

  let content = '';
  if (repoTab === 'scans') {
    if (!scans.length) {
      content = `<div class="empty"><div class="icon">🔍</div><p>No scans yet. Click "Run Scan" to start.</p></div>`;
    } else {
      content = `<table>
        <thead><tr>
          <th>ID</th><th>Branch</th><th>Status</th>
          <th>Files</th><th>LOC</th><th>Language</th>
          <th>Started</th><th></th>
        </tr></thead><tbody>`;
      for (const s of scans) {
        const scanNav = "navigate('scan', {projectId: " + state.projectId + ", repoId: " + state.repoId + ", scanId: " + s.id + ", tab:'summary'})";
        content += `<tr class="row-clickable" onclick="${scanNav}">
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
      content += '</tbody></table>';
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
