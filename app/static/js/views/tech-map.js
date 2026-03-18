import { api } from '../api.js';
import { setMain } from '../utils.js';

function badge(text, cls = '') {
  return `<span class="badge ${cls}">${text}</span>`;
}

function pill(text) {
  return `<span style="display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;background:var(--surface2);color:var(--text-muted);margin:1px">${text}</span>`;
}

function ciLabel(ci) {
  const map = {
    gitlab: 'GitLab CI',
    bitbucket: 'Bitbucket Pipelines',
    github_actions: 'GitHub Actions',
    jenkins: 'Jenkins',
    circleci: 'CircleCI',
  };
  return map[ci] || ci;
}

function typeLabel(t) {
  const map = {
    backend_service: 'Backend',
    frontend_application: 'Frontend',
    library: 'Library',
    cli_tool: 'CLI',
    infra_config: 'Infra',
    monolith: 'Monolith',
    monorepo: 'Monorepo',
    unknown: '—',
  };
  return map[t] || t || '—';
}

function countBar(counts, label) {
  const entries = Object.entries(counts);
  if (!entries.length) return '';
  const max = entries[0][1];
  return `
    <div style="margin-bottom:20px">
      <div style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">${label}</div>
      ${entries.map(([name, count]) => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
          <div style="width:140px;font-size:12px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${name}">${name}</div>
          <div style="flex:1;background:var(--surface2);border-radius:3px;height:8px;overflow:hidden">
            <div style="width:${Math.round(count / max * 100)}%;height:100%;background:var(--accent);border-radius:3px"></div>
          </div>
          <div style="font-size:12px;color:var(--text-muted);width:24px;text-align:right">${count}</div>
        </div>
      `).join('')}
    </div>`;
}

export async function renderTechMap() {
  setMain(`<h1 class="page-title">Tech Map</h1><div class="empty"><span class="spinner"></span> Loading…</div>`);

  const data = await api('/analytics/tech-map');

  if (!data.repos || !data.repos.length) {
    setMain(`
      <h1 class="page-title">Tech Map</h1>
      <p class="page-subtitle">Technology stack overview across all repositories (latest completed scan per repo).</p>
      <div class="empty"><p>No scan data yet. Run scans on repositories to see the Tech Map.</p></div>
    `);
    return;
  }

  const { repos, tech_counts } = data;
  const tc = tech_counts;

  const summaryHtml = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-bottom:28px">
      ${statCard('Repositories', repos.length)}
      ${statCard('Languages', Object.keys(tc.languages).length)}
      ${statCard('Frameworks', Object.keys(tc.frameworks).length)}
      ${statCard('With Docker', repos.filter(r => r.has_docker).length)}
      ${statCard('With CI/CD', repos.filter(r => r.ci_provider).length)}
    </div>
  `;

  const chartsHtml = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:24px;margin-bottom:32px">
      <div class="card" style="padding:16px">${countBar(tc.languages, 'Primary Languages')}</div>
      <div class="card" style="padding:16px">${countBar(tc.frameworks, 'Frameworks')}</div>
      <div class="card" style="padding:16px">${countBar(tc.ci_providers, 'CI/CD Providers')}${countBar(tc.package_managers, 'Package Managers')}</div>
      <div class="card" style="padding:16px">${countBar(tc.infra_tools, 'Infrastructure Tools')}</div>
    </div>
  `;

  const tableRows = repos.map(r => `
    <tr>
      <td style="font-weight:500">${r.project_name}</td>
      <td>${r.repo_name}</td>
      <td>${r.primary_language ? pill(r.primary_language) : '<span style="color:var(--text-muted)">—</span>'}</td>
      <td><span style="font-size:11px;color:var(--text-muted)">${typeLabel(r.project_type)}</span></td>
      <td>${r.frameworks.map(pill).join('') || '<span style="color:var(--text-muted)">—</span>'}</td>
      <td>${r.ci_provider ? pill(ciLabel(r.ci_provider)) : '<span style="color:var(--text-muted)">—</span>'}</td>
      <td style="text-align:center">${r.has_docker ? '✓' : '<span style="color:var(--text-muted)">·</span>'}</td>
      <td style="text-align:center">${r.has_kubernetes ? '✓' : '<span style="color:var(--text-muted)">·</span>'}</td>
      <td style="text-align:center">${r.has_terraform ? '✓' : '<span style="color:var(--text-muted)">·</span>'}</td>
      <td>${r.linters.map(pill).join('') || '<span style="color:var(--text-muted)">—</span>'}</td>
    </tr>
  `).join('');

  setMain(`
    <h1 class="page-title">Tech Map</h1>
    <p class="page-subtitle">Technology stack overview across all repositories (latest completed scan per repo).</p>
    ${summaryHtml}
    ${chartsHtml}
    <div class="card" style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Repository</th>
            <th>Language</th>
            <th>Type</th>
            <th>Frameworks</th>
            <th>CI/CD</th>
            <th title="Docker">🐳</th>
            <th title="Kubernetes">☸</th>
            <th title="Terraform">🌍</th>
            <th>Linters</th>
          </tr>
        </thead>
        <tbody>${tableRows}</tbody>
      </table>
    </div>
  `);
}

function statCard(label, value) {
  return `
    <div class="card" style="padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:var(--accent)">${value}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${label}</div>
    </div>
  `;
}
