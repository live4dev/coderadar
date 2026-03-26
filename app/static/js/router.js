import { VALID_TABS, UI_BASE } from './constants.js';

export function pathToState(pathname) {
  const raw = pathname.replace(/^\/ui\/?/, '').replace(/\/$/, '');
  const segments = raw ? raw.split('/').filter(Boolean) : [];
  const tabFromQuery = () => {
    const params = new URLSearchParams(location.search);
    const t = params.get('tab');
    return t && VALID_TABS.includes(t) ? t : 'summary';
  };

  if (segments.length === 0 || (segments.length === 1 && segments[0] === 'projects')) {
    return { view: 'projects', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments.length === 1 && segments[0] === 'personal-data') {
    return { view: 'personal-data-report', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments.length === 1 && segments[0] === 'license-report') {
    return { view: 'license-report', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] === 'scans-queue') {
    return { view: 'scans-queue', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] === 'analytics') {
    return { view: 'analytics', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] === 'tech-map') {
    return { view: 'tech-map', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] === 'developers') {
    if (segments.length === 1) return { view: 'developers', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
    const devId = parseInt(segments[1], 10);
    if (segments.length === 2 && !isNaN(devId)) return { view: 'developer', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: devId, projectFilter: null };
    return { view: 'developers', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] === 'admin') {
    const viewMap = { projects: 'admin-projects', repos: 'admin-repos', developers: 'admin-developers' };
    const view = viewMap[segments[1]];
    if (view) return { view, projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };
  }
  if (segments[0] !== 'projects' || segments.length < 2) return { view: 'projects', projectId: null, repoId: null, scanId: null, tab: 'summary', developerId: null, projectFilter: null };

  const projectId = parseInt(segments[1], 10);
  if (isNaN(projectId) || segments.length === 2) return { view: 'repos', projectId, repoId: null, scanId: null, tab: 'summary' };
  if (segments[2] !== 'repos' || segments.length < 4) return { view: 'repos', projectId, repoId: null, scanId: null, tab: 'summary' };

  const repoId = parseInt(segments[3], 10);
  if (isNaN(repoId) || segments.length === 4) return { view: 'scans', projectId, repoId, scanId: null, tab: 'summary' };
  if (segments[4] !== 'scans' || segments.length < 6) return { view: 'scans', projectId, repoId, scanId: null, tab: 'summary' };

  const scanId = parseInt(segments[5], 10);
  if (isNaN(scanId)) return { view: 'scans', projectId, repoId, scanId: null, tab: 'summary' };
  const tab = segments[6] && VALID_TABS.includes(segments[6]) ? segments[6] : tabFromQuery();
  return { view: 'scan', projectId, repoId, scanId, tab };
}

export function stateToPath(s) {
  if (s.view === 'projects') return UI_BASE + '/projects';
  if (s.view === 'personal-data-report') return UI_BASE + '/personal-data';
  if (s.view === 'license-report') return UI_BASE + '/license-report';
  if (s.view === 'scans-queue') return UI_BASE + '/scans-queue';
  if (s.view === 'analytics') return UI_BASE + '/analytics';
  if (s.view === 'tech-map') return UI_BASE + '/tech-map';
  if (s.view === 'admin-projects')   return UI_BASE + '/admin/projects';
  if (s.view === 'admin-repos')      return UI_BASE + '/admin/repos';
  if (s.view === 'admin-developers') return UI_BASE + '/admin/developers';
  if (s.view === 'developers') return UI_BASE + '/developers';
  if (s.view === 'developer' && s.developerId != null) return `${UI_BASE}/developers/${s.developerId}`;
  if (s.view === 'repos' && s.projectId != null) return `${UI_BASE}/projects/${s.projectId}/repos`;
  if (s.view === 'scans' && s.projectId != null && s.repoId != null) return `${UI_BASE}/projects/${s.projectId}/repos/${s.repoId}/scans`;
  if (s.view === 'scan' && s.projectId != null && s.repoId != null && s.scanId != null) {
    const base = `${UI_BASE}/projects/${s.projectId}/repos/${s.repoId}/scans/${s.scanId}`;
    return (s.tab && s.tab !== 'summary') ? `${base}/${s.tab}` : base;
  }
  return UI_BASE + '/projects';
}
