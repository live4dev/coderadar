import { api } from '../api.js';
import { fmt, setMain } from '../utils.js';

let stateTechMapProject = '';  // '' = all projects

export function techMapProjectChange() {
  const sel = document.getElementById('tech-map-project');
  if (sel) stateTechMapProject = sel.value;
  renderTechMap();
}

const LANG_COLORS = [
  '#6366f1', '#22c55e', '#f59e0b', '#38bdf8', '#f97316',
  '#a78bfa', '#34d399', '#fb7185', '#60a5fa', '#facc15',
];

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

// Build a color map for language names (stable across the page)
function buildColorMap(langNames) {
  const map = {};
  langNames.forEach((name, i) => { map[name] = LANG_COLORS[i % LANG_COLORS.length]; });
  return map;
}

function langBar(languages, colorMap) {
  if (!languages || !languages.length) return '<span style="color:var(--text-muted)">—</span>';
  const top = languages.slice(0, 4);
  return top.map(l => {
    const color = colorMap[l.name] || '#888';
    return `<span style="display:inline-flex;align-items:center;gap:3px;margin:1px 3px 1px 0;font-size:11px;color:var(--text)">
      <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0"></span>
      ${l.name} <span style="color:var(--text-muted)">${l.percentage.toFixed(0)}%</span>
    </span>`;
  }).join('');
}

function locBar(entries, maxLoc) {
  // entries: array of [name, {total_loc, total_files, repo_count}]
  if (!entries.length) return '';
  return entries.map(([name, stat], i) => {
    const color = LANG_COLORS[i % LANG_COLORS.length];
    const pct = maxLoc ? Math.max(4, Math.round(stat.total_loc / maxLoc * 100)) : 4;
    return `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
        <div style="display:flex;align-items:center;gap:5px;width:140px;min-width:0">
          <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0"></span>
          <span style="font-size:12px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${name}">${name}</span>
        </div>
        <div style="flex:1;background:var(--surface2);border-radius:3px;height:8px;overflow:hidden">
          <div style="width:${pct}%;height:100%;background:${color};border-radius:3px"></div>
        </div>
        <div style="font-size:11px;color:var(--text-muted);width:80px;text-align:right;white-space:nowrap">
          ${fmt(stat.total_loc)} LOC
        </div>
        <div style="font-size:11px;color:var(--text-muted);width:56px;text-align:right;white-space:nowrap">
          ${stat.repo_count} repo${stat.repo_count !== 1 ? 's' : ''}
        </div>
      </div>`;
  }).join('');
}

function countBarSimple(counts, label) {
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

function statCard(label, value) {
  return `
    <div class="card" style="padding:16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:var(--accent)">${value}</div>
      <div style="font-size:12px;color:var(--text-muted);margin-top:4px">${label}</div>
    </div>`;
}

export async function renderTechMap() {
  setMain(`<h1 class="page-title">Tech Map</h1><div class="empty"><span class="spinner"></span> Loading…</div>`);

  const [projects, data] = await Promise.all([
    api('/projects'),
    api('/analytics/tech-map' + (stateTechMapProject ? `?project_id=${stateTechMapProject}` : '')),
  ]);

  const projectFilter = `
    <div style="margin-bottom:20px;display:flex;align-items:center;gap:12px">
      <label for="tech-map-project" style="font-size:13px;color:var(--text-muted)">Project</label>
      <select id="tech-map-project" class="modal-input" style="width:220px;margin:0" onchange="techMapProjectChange()">
        <option value="">All projects</option>
        ${(projects || []).map(p => `<option value="${p.id}" ${String(p.id) === stateTechMapProject ? 'selected' : ''}>${p.name}</option>`).join('')}
      </select>
    </div>`;

  if (!data.repos || !data.repos.length) {
    setMain(`
      <h1 class="page-title">Tech Map</h1>
      <p class="page-subtitle">Accumulated language usage across all repositories.</p>
      ${projectFilter}
      <div class="empty"><p>No scan data yet. Run scans on repositories to see the Tech Map.</p></div>
    `);
    return;
  }

  const { repos, tech_counts: tc } = data;

  // Build stable color map from global language order
  const allLangNames = Object.keys(tc.languages);
  const colorMap = buildColorMap(allLangNames);

  // Total LOC across all languages
  const totalLoc = Object.values(tc.languages).reduce((s, l) => s + l.total_loc, 0);
  const langEntries = Object.entries(tc.languages);
  const maxLoc = langEntries.length ? langEntries[0][1].total_loc : 0;

  const summaryHtml = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:28px">
      ${statCard('Repositories', repos.length)}
      ${statCard('Total LOC', fmt(totalLoc))}
      ${statCard('Languages', allLangNames.length)}
      ${statCard('With Docker', repos.filter(r => r.has_docker).length)}
      ${statCard('With CI/CD', repos.filter(r => r.ci_provider).length)}
    </div>`;

  const langChartHtml = `
    <div class="card" style="padding:16px;margin-bottom:24px">
      <div style="font-size:12px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px">
        Language Usage — Accumulated LOC across all repositories
      </div>
      ${locBar(langEntries, maxLoc)}
    </div>`;

  const otherChartsHtml = `
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:24px;margin-bottom:32px">
      <div class="card" style="padding:16px">${countBarSimple(tc.frameworks, 'Frameworks')}</div>
      <div class="card" style="padding:16px">${countBarSimple(tc.ci_providers, 'CI/CD Providers')}${countBarSimple(tc.package_managers, 'Package Managers')}</div>
      <div class="card" style="padding:16px">${countBarSimple(tc.infra_tools, 'Infrastructure Tools')}</div>
    </div>`;

  const tableRows = repos.map(r => `
    <tr>
      <td style="font-weight:500">${r.project_name}</td>
      <td>${r.repo_name}</td>
      <td style="min-width:180px">${langBar(r.languages, colorMap)}</td>
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
    <p class="page-subtitle">Accumulated language usage across all repositories (latest completed scan per repo).</p>
    ${projectFilter}
    ${summaryHtml}
    ${langChartHtml}
    ${otherChartsHtml}
    <div class="card" style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Repository</th>
            <th>Languages</th>
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
