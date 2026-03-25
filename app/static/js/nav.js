import { state } from './state.js';
import { stateToPath } from './router.js';
import { esc } from './utils.js';

let renderCallback = null;
let scanDetailCallback = null;

export function initNav(renderCb, scanDetailCb) {
  renderCallback = renderCb;
  scanDetailCallback = scanDetailCb;
}

export function navigate(view, ids = {}) {
  Object.assign(state, { view, ...ids });
  history.pushState(null, '', stateToPath(state));
  if (renderCallback) renderCallback();
}

export function showTab(tab) {
  state.tab = tab;
  history.pushState(null, '', stateToPath(state));
  if (scanDetailCallback) scanDetailCallback();
}

export function updateNav() {
  const bc = document.getElementById('breadcrumb');
  const parts = [];

  if (state.view !== 'projects') {
    parts.push(`<a onclick="navigate('projects')">Projects</a>`);
  }
  if (state.view === 'scans-queue') parts.push('<span class="sep">/</span><span>Scans Queue</span>');
  if (state.view === 'analytics') parts.push('<span class="sep">/</span><span>Analytics</span>');
  if (state.view === 'personal-data-report') parts.push('<span class="sep">/</span><span>Personal Data Report</span>');
  if (state.view === 'license-report') parts.push('<span class="sep">/</span><span>License Report</span>');
  if (state.view === 'tech-map') parts.push('<span class="sep">/</span><span>Tech Map</span>');
  if (state.view === 'developers') parts.push('<span class="sep">/</span><span>Developers</span>');
  if (state.view === 'developer' && state.developerId != null) {
    parts.push('<span class="sep">/</span><a onclick="navigate(\'developers\')">Developers</a>');
    parts.push('<span class="sep">/</span><span>Profile</span>');
  }
  if (state.view === 'admin-projects') parts.push('<span class="sep">/</span><span>Admin</span><span class="sep">/</span><span>Projects</span>');
  if (state.view === 'admin-repos') parts.push('<span class="sep">/</span><span>Admin</span><span class="sep">/</span><span>Repositories</span>');
  if (state.view === 'admin-developers') parts.push('<span class="sep">/</span><span>Admin</span><span class="sep">/</span><span>Developers</span>');
  if (state.view === 'repos' && state.projectId != null) {
    const pName = state.projectName != null ? esc(state.projectName) : '…';
    parts.push('<span class="sep">/</span><span>' + pName + '</span>');
  }
  if (state.view === 'scans' && state.projectId != null && state.repoId != null) {
    const pName = state.projectName != null ? esc(state.projectName) : '…';
    const rName = state.repoName != null ? esc(state.repoName) : '…';
    parts.push('<span class="sep">/</span><a onclick="navigate(\'repos\', { projectId: ' + state.projectId + ' })">' + pName + '</a>');
    parts.push('<span class="sep">/</span><a onclick="navigate(\'scans\', { projectId: ' + state.projectId + ', repoId: ' + state.repoId + ' })">' + rName + '</a>');
    parts.push('<span class="sep">/</span><span>Scans</span>');
  }
  if (state.view === 'scan' && state.projectId != null && state.repoId != null && state.scanId != null) {
    const pName = state.projectName != null ? esc(state.projectName) : '…';
    const rName = state.repoName != null ? esc(state.repoName) : '…';
    parts.push('<span class="sep">/</span><a onclick="navigate(\'repos\', { projectId: ' + state.projectId + ' })">' + pName + '</a>');
    parts.push('<span class="sep">/</span><a onclick="navigate(\'scans\', { projectId: ' + state.projectId + ', repoId: ' + state.repoId + ' })">' + rName + '</a>');
    parts.push('<span class="sep">/</span><a onclick="navigate(\'scans\', { projectId: ' + state.projectId + ', repoId: ' + state.repoId + ' })">Scans</a>');
    parts.push('<span class="sep">/</span><span>Scan #' + state.scanId + '</span>');
  }

  const showRepoSection = ['scans', 'scan'].includes(state.view);
  document.getElementById('sidebar-repo-section').style.display = showRepoSection ? '' : 'none';
  document.getElementById('sidebar-scan-section').style.display = state.view === 'scan' ? '' : 'none';

  ['projects', 'developers-list', 'analytics', 'personal-data-report', 'license-report', 'tech-map', 'scans-queue', 'scans', 'summary', 'languages', 'scores', 'risks', 'developers', 'admin-projects', 'admin-repos', 'admin-developers'].forEach(id => {
    const el = document.getElementById('nav-' + id);
    if (el) el.classList.toggle('active', false);
  });

  if (state.view === 'projects') document.getElementById('nav-projects').classList.add('active');
  if (state.view === 'scans-queue') document.getElementById('nav-scans-queue')?.classList.add('active');
  if (state.view === 'developers' || state.view === 'developer') document.getElementById('nav-developers-list').classList.add('active');
  if (state.view === 'analytics') document.getElementById('nav-analytics').classList.add('active');
  if (state.view === 'personal-data-report') document.getElementById('nav-personal-data-report').classList.add('active');
  if (state.view === 'license-report') document.getElementById('nav-license-report')?.classList.add('active');
  if (state.view === 'tech-map') document.getElementById('nav-tech-map').classList.add('active');
  if (state.view === 'scans') document.getElementById('nav-scans').classList.add('active');
  if (state.view === 'scan') {
    const el = document.getElementById('nav-' + state.tab);
    if (el) el.classList.add('active');
  }
  if (state.view === 'admin-projects')   document.getElementById('nav-admin-projects')?.classList.add('active');
  if (state.view === 'admin-repos')      document.getElementById('nav-admin-repos')?.classList.add('active');
  if (state.view === 'admin-developers') document.getElementById('nav-admin-developers')?.classList.add('active');

  bc.innerHTML = parts.join('');
}
