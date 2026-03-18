import { api } from '../api.js';
import { state } from '../state.js';
import { esc, setMain } from '../utils.js';
import { openConfirmDialog } from '../confirm.js';
import { API } from '../state.js';

export async function renderAdminDevelopers() {
  const devs = await api('/developers');

  // For any expanded rows, load their override/profile data
  const expandedData = {};
  for (const dev of devs) {
    const mode = state.adminDevExpanded[dev.id];
    if (mode === 'overrides') {
      try {
        expandedData[dev.id] = { overrides: await api('/developers/' + dev.id + '/identity-overrides') };
      } catch { expandedData[dev.id] = { overrides: [] }; }
    }
  }

  // Collect all projects for override project selector
  let projects = [];
  try { projects = await api('/projects'); } catch { /* ignore */ }

  const rows = devs.map(dev => {
    const profile = dev.profiles && dev.profiles[0];
    const displayName = profile ? (profile.display_name || profile.canonical_username) : `Developer #${dev.id}`;
    const email = profile ? (profile.primary_email || '—') : '—';
    const mode = state.adminDevExpanded[dev.id] || null;

    let expandedRow = '';
    if (mode === 'profile') {
      const profileForms = (dev.profiles || []).map(p => `
        <div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border)">
          <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">Profile: <code>${esc(p.canonical_username)}</code></div>
          <div class="form-row">
            <div class="form-field">
              <label>Display name</label>
              <input type="text" id="admin-dev-name-${p.id}" value="${esc(p.display_name || '')}">
            </div>
            <div class="form-field">
              <label>Primary email</label>
              <input type="text" id="admin-dev-email-${p.id}" value="${esc(p.primary_email || '')}">
            </div>
            <div class="form-field" style="justify-content:flex-end">
              <button class="btn btn-primary" style="margin-top:18px" onclick="adminDevSaveProfile(${p.id})">Save</button>
            </div>
          </div>
        </div>`).join('');
      expandedRow = `
        <tr class="admin-expanded-row">
          <td colspan="4">
            <div class="admin-form" style="margin-bottom:0">
              <div style="font-weight:600;margin-bottom:12px">Edit Profiles</div>
              ${profileForms || '<p style="color:var(--text-muted)">No profiles.</p>'}
            </div>
          </td>
        </tr>`;
    } else if (mode === 'overrides') {
      const overrides = (expandedData[dev.id] || {}).overrides || [];
      const overrideRows = overrides.map(o => `
        <tr>
          <td style="font-size:12px">${esc(o.raw_name || '—')}</td>
          <td style="font-size:12px">${esc(o.raw_email || '—')}</td>
          <td style="font-size:12px">${esc(o.canonical_username)}</td>
          <td style="font-size:12px;color:var(--text-muted)">${esc(o.note || '—')}</td>
          <td>
            <button class="btn btn-danger" style="padding:2px 8px;font-size:11px" onclick="adminDevDeleteOverride(${o.id}, ${dev.id})">Delete</button>
          </td>
        </tr>`).join('');

      const projectOptions = projects.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');

      expandedRow = `
        <tr class="admin-expanded-row">
          <td colspan="4">
            <div style="margin-bottom:12px">
              <table style="margin-bottom:12px">
                <thead><tr>
                  <th>Raw name</th><th>Raw email</th><th>Canonical username</th><th>Note</th><th></th>
                </tr></thead>
                <tbody>${overrideRows || '<tr><td colspan="5" style="color:var(--text-muted);text-align:center">No overrides.</td></tr>'}</tbody>
              </table>
              <div class="admin-form" style="margin-bottom:0">
                <div style="font-weight:600;margin-bottom:12px">Add Override</div>
                <div class="form-row">
                  <div class="form-field">
                    <label>Project *</label>
                    <select id="admin-override-project-${dev.id}">
                      <option value="">Select…</option>
                      ${projectOptions}
                    </select>
                  </div>
                  <div class="form-field">
                    <label>Raw name</label>
                    <input type="text" id="admin-override-rawname-${dev.id}" placeholder="John Doe">
                  </div>
                  <div class="form-field">
                    <label>Raw email</label>
                    <input type="text" id="admin-override-rawemail-${dev.id}" placeholder="john@example.com">
                  </div>
                  <div class="form-field">
                    <label>Canonical username *</label>
                    <input type="text" id="admin-override-username-${dev.id}" value="${esc(dev.profiles && dev.profiles[0] ? dev.profiles[0].canonical_username : '')}">
                  </div>
                  <div class="form-field">
                    <label>Note</label>
                    <input type="text" id="admin-override-note-${dev.id}" placeholder="Optional note">
                  </div>
                </div>
                <div class="form-actions">
                  <button class="btn btn-primary" onclick="adminDevAddOverride(${dev.id})">Add override</button>
                </div>
              </div>
            </div>
          </td>
        </tr>`;
    }

    return `
      <tr>
        <td>
          <div style="font-weight:600">${esc(displayName)}</div>
          ${dev.profiles && dev.profiles.length > 1 ? `<div style="font-size:11px;color:var(--text-muted)">${dev.profiles.length} profiles</div>` : ''}
        </td>
        <td style="font-size:12px;color:var(--text-muted)">${esc(email)}</td>
        <td style="font-size:12px;color:var(--text-muted)">${dev.total_commits != null ? dev.total_commits + ' commits' : '—'}</td>
        <td onclick="event.stopPropagation()" style="white-space:nowrap">
          <button class="btn btn-outline" style="padding:3px 10px;font-size:12px" onclick="adminDevToggle(${dev.id}, 'profile')">${mode === 'profile' ? '▲ Close' : 'Edit Profile'}</button>
          <button class="btn btn-outline" style="padding:3px 10px;font-size:12px;margin-left:6px" onclick="adminDevToggle(${dev.id}, 'overrides')">${mode === 'overrides' ? '▲ Close' : 'Overrides'}</button>
        </td>
      </tr>
      ${expandedRow}`;
  }).join('');

  const tableHtml = devs.length ? `
    <table>
      <thead><tr>
        <th>Developer</th><th>Email</th><th>Activity</th><th>Actions</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>` : `<div class="empty"><div class="icon">👤</div><p>No developers yet. Run a scan to discover contributors.</p></div>`;

  setMain(`
    <div class="page-title">Admin: Developers</div>
    <div class="page-subtitle">Edit developer profiles and manage identity overrides</div>
    ${tableHtml}
  `);
}

window.adminDevToggle = function(devId, mode) {
  state.adminDevExpanded[devId] = state.adminDevExpanded[devId] === mode ? null : mode;
  window.render();
};

window.adminDevSaveProfile = async function(profileId) {
  const display_name = document.getElementById('admin-dev-name-' + profileId).value.trim() || null;
  const primary_email = document.getElementById('admin-dev-email-' + profileId).value.trim() || null;
  await fetch(API + '/developers/profiles/' + profileId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name, primary_email }),
  });
  window.render();
};

window.adminDevDeleteOverride = function(overrideId, devId) {
  openConfirmDialog(
    'Delete identity override?',
    'This will remove the identity mapping. The developer\'s git commits will no longer be merged under this identity.',
    'Delete',
    async () => {
      await fetch(API + '/developers/identity-overrides/' + overrideId, { method: 'DELETE' });
      window.render();
    }
  );
};

window.adminDevAddOverride = async function(devId) {
  const project_id = parseInt(document.getElementById('admin-override-project-' + devId).value, 10);
  const raw_name = document.getElementById('admin-override-rawname-' + devId).value.trim() || null;
  const raw_email = document.getElementById('admin-override-rawemail-' + devId).value.trim() || null;
  const canonical_username = document.getElementById('admin-override-username-' + devId).value.trim();
  const note = document.getElementById('admin-override-note-' + devId).value.trim() || null;

  if (!project_id || !canonical_username) { alert('Project and Canonical username are required.'); return; }
  await fetch(API + '/developers/identity-overrides', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id, raw_name, raw_email, canonical_username, note }),
  });
  window.render();
};
