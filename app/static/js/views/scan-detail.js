import { state } from '../state.js';
import { api } from '../api.js';
import { fmtDate, esc, setMain, showError } from '../utils.js';
import { updateNav } from '../nav.js';
import { buildSummaryTab } from '../tabs/summary.js';
import { buildLanguagesTab } from '../tabs/languages.js';
import { buildScoresTab } from '../tabs/scores.js';
import { buildRisksTab } from '../tabs/risks.js';
import { buildDevelopersTab } from '../tabs/developers-tab.js';
import { buildPersonalDataTab } from '../tabs/personal-data-tab.js';
import { buildGitTagsTab } from '../tabs/git-tags.js';
import { buildDependenciesTab } from '../tabs/dependencies-tab.js';

export async function renderScanDetail() {
  updateNav();
  setMain('<div class="empty"><span class="spinner"></span> Loading…</div>');

  try {
    const [scan, project, repo] = await Promise.all([
      api('/scans/' + state.scanId + '/summary'),
      api('/projects/' + state.projectId),
      api('/repositories/' + state.repoId),
    ]);
    state.projectName = project.name;
    state.repoName = repo.name;

    let content = '';
    if (state.tab === 'summary')        content = await buildSummaryTab(scan);
    if (state.tab === 'languages')      content = await buildLanguagesTab();
    if (state.tab === 'scores')         content = await buildScoresTab(scan);
    if (state.tab === 'risks')          content = await buildRisksTab();
    if (state.tab === 'developers')     content = await buildDevelopersTab();
    if (state.tab === 'personal-data')  content = await buildPersonalDataTab(scan);
    if (state.tab === 'git-tags')       content = await buildGitTagsTab();
    if (state.tab === 'dependencies')   content = await buildDependenciesTab();

    const tabLabels = { summary: 'Summary', languages: 'Languages', scores: 'Scores', risks: 'Risks', developers: 'Developers', 'personal-data': 'Personal Data', 'git-tags': 'Git Tags', dependencies: 'Dependencies' };
    const tabs = ['summary', 'languages', 'scores', 'risks', 'developers', 'personal-data', 'git-tags', 'dependencies']
      .map(t => `<div class="tab ${state.tab === t ? 'active' : ''}" onclick="showTab('${t}')">${tabLabels[t]}</div>`).join('');

    const failedBlock = scan.status === 'failed' ? `
      <div class="error-banner" style="margin-bottom:20px">
        <div style="font-weight:600;margin-bottom:8px">Scan failed</div>
        <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">${scan.completed_at ? 'Failed at ' + fmtDate(scan.completed_at) : ''}</div>
        <pre style="margin:0;white-space:pre-wrap;word-break:break-word;font-size:12px;max-height:300px;overflow:auto">${esc(scan.error_message || 'No error message recorded.')}</pre>
      </div>` : '';

    setMain(`
      <div class="page-title">Scan #${state.scanId}</div>
      <div class="page-subtitle">
        <span class="status ${scan.status}">${scan.status}</span>
        &nbsp;·&nbsp; Branch: <code>${esc(scan.branch)}</code>
        ${scan.commit_sha ? '&nbsp;·&nbsp; <code style="font-size:11px">' + esc(scan.commit_sha.slice(0, 8)) + '</code>' : ''}
        &nbsp;·&nbsp; ${fmtDate(scan.started_at)}
      </div>
      ${failedBlock}
      <div class="tabs">${tabs}</div>
      ${content}
    `);
    updateNav();
  } catch (e) { showError(e); }
}
