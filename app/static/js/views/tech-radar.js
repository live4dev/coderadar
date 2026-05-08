import { api } from '../api.js';
import { API } from '../state.js';
import { setMain, esc } from '../utils.js';

let _projectFilter = '';
let _radarData = null;

const RINGS = ['adopt', 'trial', 'assess', 'hold'];
const QUADRANTS = ['languages', 'frameworks', 'infrastructure', 'dependencies'];
const QUADRANT_LABELS = {
  languages: 'Languages',
  frameworks: 'Frameworks',
  infrastructure: 'Infrastructure',
  dependencies: 'Dependencies',
};

const RING_COLORS = { adopt: '#22c55e', trial: '#6366f1', assess: '#f59e0b', hold: '#ef4444' };
const RING_BG = { adopt: '#f0fdf4', trial: '#eef2ff', assess: '#fffbeb', hold: '#fef2f2' };
const RING_OUTER = [65, 125, 192, 260];

const CENTER = 290;
const SVG_SIZE = 580;

// Quadrant angle ranges in SVG convention (y-down, clockwise, radians)
// top-right=Q0(languages), top-left=Q1(frameworks), bottom-left=Q2(infrastructure), bottom-right=Q3(dependencies)
const Q_ANGLES = {
  languages:      { start: -Math.PI / 2, end: 0 },
  dependencies:   { start: 0,            end: Math.PI / 2 },
  infrastructure: { start: Math.PI / 2,  end: Math.PI },
  frameworks:     { start: Math.PI,      end: Math.PI * 3 / 2 },
};

export function techRadarProjectChange() {
  const sel = document.getElementById('tech-radar-project');
  if (sel) _projectFilter = sel.value;
  _loadAndRender();
}

export function techRadarSetRing(name, quadrant, currentRing) {
  const key = `${name}|${quadrant}`;
  const row = document.querySelector(`[data-row="${CSS.escape(key)}"]`);
  if (!row) return;

  const rings = RINGS.map(r =>
    `<option value="${r}"${r === currentRing ? ' selected' : ''}>${r.charAt(0).toUpperCase() + r.slice(1)}</option>`
  ).join('');

  row.querySelector('.ring-action').innerHTML = `
    <select id="ring-sel-${CSS.escape(key)}" style="font-size:11px;padding:2px 4px;border:1px solid var(--border);border-radius:3px;background:var(--surface);color:var(--text)">${rings}</select>
    <input type="text" id="ring-note-${CSS.escape(key)}" placeholder="Notes (optional)" style="font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;width:130px;background:var(--surface);color:var(--text)">
    <button class="btn btn-primary" style="font-size:11px;padding:2px 8px" onclick="techRadarSaveOverride(${JSON.stringify(name)}, ${JSON.stringify(quadrant)})">Save</button>
    <button class="btn btn-outline" style="font-size:11px;padding:2px 6px" onclick="techRadarCancelEdit(${JSON.stringify(key)})">Cancel</button>
  `;
}

export function techRadarCancelEdit(key) {
  _renderRadarData(_radarData);
}

export async function techRadarSaveOverride(name, quadrant) {
  const key = `${name}|${quadrant}`;
  const sel = document.getElementById(`ring-sel-${CSS.escape(key)}`);
  const noteEl = document.getElementById(`ring-note-${CSS.escape(key)}`);
  if (!sel) return;

  await api('/tech-radar/overrides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tech_name: name,
      quadrant,
      ring: sel.value,
      project_id: _projectFilter ? parseInt(_projectFilter) : null,
      notes: noteEl?.value || null,
    }),
  });
  await _loadAndRender();
}

export async function techRadarDeleteOverride(name, quadrant) {
  // Find override id from current data
  const blip = _radarData?.blips?.find(b => b.name === name && b.quadrant === quadrant);
  if (!blip?.is_overridden) return;

  // Fetch current overrides to find the id
  const projectParam = _projectFilter ? `?project_id=${_projectFilter}` : '';
  const overrides = await api(`/tech-radar/overrides${projectParam}`);
  const ov = overrides.find(o => o.tech_name === name && o.quadrant === quadrant);
  if (!ov) return;

  await fetch(API + `/tech-radar/overrides/${ov.id}`, { method: 'DELETE' });
  await _loadAndRender();
}

export async function renderTechRadar() {
  const projects = await api('/projects');
  const items = projects.items || projects;
  const projectOptions = `<option value="">All projects</option>` +
    items.map(p => `<option value="${p.id}"${String(p.id) === _projectFilter ? ' selected' : ''}>${esc(p.name)}</option>`).join('');

  setMain(`
    <div class="page-header">
      <div class="page-title">Tech Radar</div>
      <select id="tech-radar-project" onchange="techRadarProjectChange()" style="font-size:13px;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text)">
        ${projectOptions}
      </select>
    </div>
    <div id="radar-root"><div class="empty"><span class="spinner"></span> Loading…</div></div>
    <div id="radar-tooltip" style="position:fixed;display:none;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:10px 14px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.18);pointer-events:none;max-width:260px;z-index:9999;line-height:1.5"></div>
  `);

  await _loadAndRender();
}

async function _loadAndRender() {
  const root = document.getElementById('radar-root');
  if (!root) return;
  root.innerHTML = '<div class="empty"><span class="spinner"></span> Loading…</div>';

  const url = _projectFilter
    ? `/analytics/tech-radar?project_id=${_projectFilter}`
    : '/analytics/tech-radar';
  _radarData = await api(url);
  _renderRadarData(_radarData);
}

function _renderRadarData(data) {
  const root = document.getElementById('radar-root');
  if (!root || !data) return;

  const blips = data.blips || [];
  if (!blips.length) {
    root.innerHTML = '<div class="empty"><div class="icon">📡</div><p>No technology data yet — scan some repositories first.</p></div>';
    return;
  }

  // Assign per-quadrant numbers for blip labels
  const blipNum = {};
  let n = 1;
  QUADRANTS.forEach(q => {
    blips.filter(b => b.quadrant === q).forEach(b => {
      blipNum[`${b.name}|${b.quadrant}`] = n++;
    });
  });

  const svgHtml = _buildSVG(blips, blipNum);
  const legendHtml = _buildLegend(blips, blipNum);
  const tableHtml = _buildTable(blips, blipNum);

  const ts = data.generated_at ? new Date(data.generated_at).toLocaleString() : '';
  root.innerHTML = `
    <div style="font-size:12px;color:var(--text-muted);margin-bottom:16px">
      ${data.total_repos} repositor${data.total_repos === 1 ? 'y' : 'ies'} analysed
      ${ts ? `&bull; generated ${ts}` : ''}
    </div>
    <div style="display:flex;gap:32px;align-items:flex-start;flex-wrap:wrap;margin-bottom:32px">
      <div style="flex-shrink:0">${svgHtml}</div>
      <div style="flex:1;min-width:220px">${legendHtml}</div>
    </div>
    ${tableHtml}
  `;

  // Tooltip on blip dots
  root.querySelectorAll('[data-tip]').forEach(el => {
    el.addEventListener('mouseenter', e => _showTip(e, el.dataset.tip, blips));
    el.addEventListener('mousemove', _moveTip);
    el.addEventListener('mouseleave', _hideTip);
  });
}

// ── SVG radar ──────────────────────────────────────────────────────────────

function _polarToXY(r, angle) {
  return [CENTER + r * Math.cos(angle), CENTER + r * Math.sin(angle)];
}

function _arcPath(innerR, outerR, startAngle, endAngle) {
  const [ox1, oy1] = _polarToXY(outerR, startAngle);
  const [ox2, oy2] = _polarToXY(outerR, endAngle);
  const [ix1, ix2] = [_polarToXY(innerR, startAngle), _polarToXY(innerR, endAngle)];
  const large = (endAngle - startAngle > Math.PI) ? 1 : 0;
  if (innerR <= 0) {
    return `M ${CENTER} ${CENTER} L ${ox1} ${oy1} A ${outerR} ${outerR} 0 ${large} 1 ${ox2} ${oy2} Z`;
  }
  return `M ${ox1} ${oy1} A ${outerR} ${outerR} 0 ${large} 1 ${ox2} ${oy2} L ${ix2[0]} ${ix2[1]} A ${innerR} ${innerR} 0 ${large} 0 ${ix1[0]} ${ix1[1]} Z`;
}

function _simpleHash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
  return Math.abs(h);
}

function _blipXY(name, quadrant, ringIdx) {
  const h = _simpleHash(name + quadrant + ringIdx);
  const { start, end } = Q_ANGLES[quadrant];
  const innerR = ringIdx === 0 ? 8 : RING_OUTER[ringIdx - 1] + 6;
  const outerR = RING_OUTER[ringIdx] - 8;
  const span = end - start;
  const angle = start + (0.12 + ((h & 0xff) / 255) * 0.76) * span;
  const radius = innerR + (((h >> 8) & 0xff) / 255) * Math.max(0, outerR - innerR);
  return _polarToXY(radius, angle);
}

function _buildSVG(blips, blipNum) {
  const sectors = [];
  const blipEls = [];

  RINGS.forEach((ring, ri) => {
    const innerR = ri === 0 ? 0 : RING_OUTER[ri - 1];
    const outerR = RING_OUTER[ri];
    QUADRANTS.forEach(q => {
      const { start, end } = Q_ANGLES[q];
      const fill = { adopt: '#dcfce7', trial: '#e0e7ff', assess: '#fef9c3', hold: '#fee2e2' }[ring];
      sectors.push(`<path d="${_arcPath(innerR, outerR, start, end)}" fill="${fill}" stroke="var(--border)" stroke-width="0.5"/>`);
    });
  });

  // Dividing lines
  const lines = [
    `<line x1="${CENTER}" y1="0" x2="${CENTER}" y2="${SVG_SIZE}" stroke="var(--border)" stroke-width="1"/>`,
    `<line x1="0" y1="${CENTER}" x2="${SVG_SIZE}" y2="${CENTER}" stroke="var(--border)" stroke-width="1"/>`,
  ];

  // Ring labels along top axis
  const ringLabels = RINGS.map((ring, ri) => {
    const innerR = ri === 0 ? 0 : RING_OUTER[ri - 1];
    const midR = innerR + (RING_OUTER[ri] - innerR) / 2;
    const [x, y] = _polarToXY(midR, -Math.PI / 2);
    return `<text x="${x}" y="${y + 4}" text-anchor="middle" font-size="10" fill="${RING_COLORS[ring]}" font-weight="600" pointer-events="none">${ring.toUpperCase()}</text>`;
  });

  // Quadrant labels at corners
  const qLabelPos = {
    languages:      [SVG_SIZE - 8, 14],
    frameworks:     [8, 14],
    infrastructure: [8, SVG_SIZE - 6],
    dependencies:   [SVG_SIZE - 8, SVG_SIZE - 6],
  };
  const qLabelAnchor = {
    languages: 'end', frameworks: 'start', infrastructure: 'start', dependencies: 'end',
  };
  const quadrantLabels = QUADRANTS.map(q => {
    const [x, y] = qLabelPos[q];
    return `<text x="${x}" y="${y}" text-anchor="${qLabelAnchor[q]}" font-size="11" fill="var(--text-muted)" font-weight="600" pointer-events="none">${QUADRANT_LABELS[q]}</text>`;
  });

  // Blip dots
  blips.forEach(b => {
    const ri = RINGS.indexOf(b.ring);
    if (ri < 0) return;
    const [x, y] = _blipXY(b.name, b.quadrant, ri);
    const num = blipNum[`${b.name}|${b.quadrant}`] || '';
    const color = RING_COLORS[b.ring];
    const tipKey = `${b.name}|${b.quadrant}`;
    const overrideMarker = b.is_overridden
      ? `<circle cx="${x + 7}" cy="${y - 7}" r="4" fill="var(--surface)" stroke="${color}" stroke-width="1.5"/><text x="${x + 7}" y="${y - 4}" text-anchor="middle" font-size="6" fill="${color}">✎</text>`
      : '';
    blipEls.push(`
      <g data-tip="${esc(tipKey)}" style="cursor:pointer">
        <circle cx="${x}" cy="${y}" r="11" fill="${color}" opacity="0.9"/>
        <text x="${x}" y="${y + 4}" text-anchor="middle" font-size="9" font-weight="700" fill="white" pointer-events="none">${num}</text>
        ${overrideMarker}
      </g>
    `);
  });

  return `
    <svg viewBox="0 0 ${SVG_SIZE} ${SVG_SIZE}" width="${SVG_SIZE}" height="${SVG_SIZE}" style="max-width:100%;border-radius:8px;overflow:hidden">
      ${sectors.join('')}
      ${lines.join('')}
      ${ringLabels.join('')}
      ${quadrantLabels.join('')}
      ${blipEls.join('')}
    </svg>
  `;
}

// ── Legend ──────────────────────────────────────────────────────────────────

function _buildLegend(blips, blipNum) {
  const byQuadrant = {};
  QUADRANTS.forEach(q => { byQuadrant[q] = {}; });
  RINGS.forEach(r => QUADRANTS.forEach(q => { byQuadrant[q][r] = []; }));
  blips.forEach(b => {
    if (byQuadrant[b.quadrant]?.[b.ring]) byQuadrant[b.quadrant][b.ring].push(b);
  });

  return QUADRANTS.map(q => {
    const qBlips = RINGS.flatMap(r => byQuadrant[q][r]);
    if (!qBlips.length) return '';
    const ringGroups = RINGS.map(r => {
      const items = byQuadrant[q][r];
      if (!items.length) return '';
      const rows = items.map(b => {
        const num = blipNum[`${b.name}|${b.quadrant}`] || '';
        const color = RING_COLORS[r];
        return `<div style="display:flex;align-items:flex-start;gap:6px;padding:2px 0">
          <span style="flex-shrink:0;width:18px;height:18px;border-radius:50%;background:${color};display:inline-flex;align-items:center;justify-content:center;font-size:9px;font-weight:700;color:#fff">${num}</span>
          <span style="font-size:12px;color:var(--text)">${esc(b.name)}${b.is_overridden ? ' <span title="Manually placed" style="color:var(--text-muted)">✎</span>' : ''}</span>
        </div>`;
      }).join('');
      return `<div style="margin-bottom:4px">
        <div style="font-size:10px;font-weight:600;color:${RING_COLORS[r]};text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px">${r}</div>
        ${rows}
      </div>`;
    }).filter(Boolean).join('');

    return `<div style="margin-bottom:20px">
      <div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:8px;padding-bottom:4px;border-bottom:1px solid var(--border)">${QUADRANT_LABELS[q]}</div>
      ${ringGroups}
    </div>`;
  }).join('');
}

// ── Table ───────────────────────────────────────────────────────────────────

function _ringPill(ring) {
  const color = RING_COLORS[ring] || '#888';
  return `<span style="display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;background:${color}22;color:${color};border:1px solid ${color}44">${ring}</span>`;
}

function _buildTable(blips, blipNum) {
  const rows = blips.map(b => {
    const key = `${b.name}|${b.quadrant}`;
    const num = blipNum[key] || '';
    const overrideNote = b.is_overridden
      ? `<span style="font-size:10px;color:var(--text-muted)" title="Auto: ${b.auto_ring}"> (was: ${b.auto_ring})</span>`
      : '';
    const qualStr = b.quality_signal != null
      ? `<span style="color:${b.quality_signal < 35 ? '#ef4444' : b.quality_signal < 60 ? '#f59e0b' : '#22c55e'}">${b.quality_signal}</span>`
      : '<span style="color:var(--text-muted)">—</span>';
    const licStr = b.license_risk === 'high'
      ? '<span style="color:#ef4444;font-weight:600">high</span>'
      : b.license_risk
        ? `<span style="color:var(--text-muted)">${b.license_risk}</span>`
        : '<span style="color:var(--text-muted)">—</span>';
    const notesStr = b.notes ? `<div style="font-size:11px;color:var(--text-muted);margin-top:1px">${esc(b.notes)}</div>` : '';

    return `<tr data-row="${esc(key)}">
      <td style="width:32px;color:var(--text-muted);font-size:12px">${num}</td>
      <td><strong>${esc(b.name)}</strong>${notesStr}</td>
      <td style="font-size:12px;color:var(--text-muted)">${QUADRANT_LABELS[b.quadrant]}</td>
      <td>${_ringPill(b.ring)}${overrideNote}</td>
      <td style="font-size:12px;text-align:right">${b.repo_count}</td>
      <td style="text-align:right">${qualStr}</td>
      <td style="text-align:center">${licStr}</td>
      <td class="ring-action" style="white-space:nowrap">
        <button class="btn btn-outline" style="font-size:11px;padding:2px 8px" onclick="techRadarSetRing(${JSON.stringify(b.name)}, ${JSON.stringify(b.quadrant)}, ${JSON.stringify(b.ring)})">
          ${b.is_overridden ? 'Edit' : 'Override'}
        </button>
        ${b.is_overridden ? `<button class="btn btn-outline" style="font-size:11px;padding:2px 6px;color:#ef4444;border-color:#ef444455;margin-left:4px" onclick="techRadarDeleteOverride(${JSON.stringify(b.name)}, ${JSON.stringify(b.quadrant)})">Reset</button>` : ''}
      </td>
    </tr>`;
  }).join('');

  return `
    <div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:10px">All technologies</div>
    <div style="overflow-x:auto">
    <table class="data-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Name</th>
          <th>Quadrant</th>
          <th>Ring</th>
          <th style="text-align:right">Repos</th>
          <th style="text-align:right">Quality</th>
          <th style="text-align:center">License</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    </div>
  `;
}

// ── Tooltip ──────────────────────────────────────────────────────────────────

function _showTip(e, tipKey, blips) {
  const [name, quadrant] = tipKey.split('|');
  const b = blips.find(bl => bl.name === name && bl.quadrant === quadrant);
  if (!b) return;

  const tip = document.getElementById('radar-tooltip');
  if (!tip) return;

  const qualLine = b.quality_signal != null
    ? `<div>Avg quality: <strong style="color:${b.quality_signal < 35 ? '#ef4444' : b.quality_signal < 60 ? '#f59e0b' : '#22c55e'}">${b.quality_signal}</strong>/100</div>`
    : '';
  const licLine = b.license_risk === 'high'
    ? `<div>License risk: <strong style="color:#ef4444">high</strong></div>`
    : '';
  const overrideLine = b.is_overridden
    ? `<div style="color:var(--text-muted);font-size:11px">Auto ring: ${b.auto_ring} (manually overridden)</div>`
    : '';
  const notesLine = b.notes ? `<div style="margin-top:4px;font-size:11px;color:var(--text-muted)">${esc(b.notes)}</div>` : '';

  tip.innerHTML = `
    <div style="font-weight:600;margin-bottom:4px">${esc(b.name)}</div>
    <div>${QUADRANT_LABELS[b.quadrant]} &bull; ${_ringPill(b.ring)}</div>
    <div>Used in <strong>${b.repo_count}</strong> repo${b.repo_count !== 1 ? 's' : ''}</div>
    ${qualLine}${licLine}${overrideLine}${notesLine}
  `;
  tip.style.display = 'block';
  _moveTip(e);
}

function _moveTip(e) {
  const tip = document.getElementById('radar-tooltip');
  if (!tip || tip.style.display === 'none') return;
  tip.style.left = (e.clientX + 14) + 'px';
  tip.style.top = (e.clientY - 10) + 'px';
}

function _hideTip() {
  const tip = document.getElementById('radar-tooltip');
  if (tip) tip.style.display = 'none';
}
