import { state } from './state.js';
import { pathToState, stateToPath } from './router.js';
import { initNav, navigate, showTab, updateNav } from './nav.js';
import { initModal, openEditTagsModal, closeEditTagsModal, saveEditTagsModal, addTagRow } from './modal.js';
import { renderAdminProjects } from './views/admin-projects.js';
import { renderAdminRepos } from './views/admin-repos.js';
import { renderAdminDevelopers } from './views/admin-developers.js';
import { closeConfirmDialog, runConfirmAction } from './confirm.js';
import { renderProjects, projSort, projSearchInput } from './views/projects.js';
import { renderRepos, repoSort, repoSearchInput } from './views/repos.js';
import { renderScans, triggerScan } from './views/scans.js';
import { renderScanDetail } from './views/scan-detail.js';
import { renderDevelopersSummary, devSort, devSearchInput } from './views/developers.js';
import { renderDeveloperProfile } from './views/developer-profile.js';
import { renderAnalytics, treemapMetricChange, disposeTreemap, treemapChartInstance } from './views/analytics.js';
import { renderPersonalDataReport } from './views/personal-data-report.js';
import { renderTechMap } from './views/tech-map.js';
import { setMain, showError } from './utils.js';

async function render() {
  disposeTreemap();
  updateNav();
  setMain('<div class="empty"><span class="spinner"></span> Loading…</div>');
  try {
    if (state.view === 'projects')             await renderProjects();
    else if (state.view === 'repos')           await renderRepos();
    else if (state.view === 'scans')           await renderScans();
    else if (state.view === 'scan')            await renderScanDetail();
    else if (state.view === 'developers')      await renderDevelopersSummary();
    else if (state.view === 'developer')       await renderDeveloperProfile();
    else if (state.view === 'analytics')       await renderAnalytics();
    else if (state.view === 'personal-data-report') await renderPersonalDataReport();
    else if (state.view === 'tech-map')            await renderTechMap();
    else if (state.view === 'admin-projects')   await renderAdminProjects();
    else if (state.view === 'admin-repos')      await renderAdminRepos();
    else if (state.view === 'admin-developers') await renderAdminDevelopers();
  } catch (e) { showError(e); }
}

// Expose on window for inline onclick= handlers in rendered HTML
window.navigate = navigate;
window.showTab = showTab;
window.openEditTagsModal = openEditTagsModal;
window.closeEditTagsModal = closeEditTagsModal;
window.saveEditTagsModal = saveEditTagsModal;
window.addTagRow = addTagRow;
window.projSort = projSort;
window.projSearchInput = projSearchInput;
window.repoSort = repoSort;
window.repoSearchInput = repoSearchInput;
window.devSort = devSort;
window.devSearchInput = devSearchInput;
window.treemapMetricChange = treemapMetricChange;
window.triggerScan = triggerScan;
window.render = render;
window.state = state;
window.closeConfirmDialog = closeConfirmDialog;
window.runConfirmAction = runConfirmAction;

// Initialize callback injections
initModal(render);
initNav(render, renderScanDetail);

// Wire sidebar nav items (remove inline onclick from HTML)
document.getElementById('nav-projects').addEventListener('click', () => navigate('projects'));
document.getElementById('nav-developers-list').addEventListener('click', () => navigate('developers'));
document.getElementById('nav-analytics').addEventListener('click', () => navigate('analytics'));
document.getElementById('nav-personal-data-report').addEventListener('click', () => navigate('personal-data-report'));
document.getElementById('nav-tech-map').addEventListener('click', () => navigate('tech-map'));
document.getElementById('nav-scans').addEventListener('click', () => navigate('scans'));
document.getElementById('nav-admin-projects').addEventListener('click', () => navigate('admin-projects'));
document.getElementById('nav-admin-repos').addEventListener('click', () => navigate('admin-repos'));
document.getElementById('nav-admin-developers').addEventListener('click', () => navigate('admin-developers'));
document.querySelector('.logo').addEventListener('click', () => navigate('projects'));

// Boot
const parsed = pathToState(location.pathname);
Object.assign(state, parsed);
history.replaceState(null, '', stateToPath(state));
render();

window.addEventListener('popstate', () => {
  Object.assign(state, pathToState(location.pathname));
  render();
});

window.addEventListener('resize', () => {
  if (treemapChartInstance) treemapChartInstance.resize();
});
