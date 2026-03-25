import { api } from '../api.js';
import { state } from '../state.js';
import { navigate } from '../nav.js';
import { esc, fmtDate, setMain } from '../utils.js';
import { openConfirmDialog } from '../confirm.js';
import { API } from '../state.js';

const PROVIDERS = ['github', 'gitlab', 'bitbucket'];

export async function renderAdminRepos() {
  const projects = await api('/projects');

  const projectFilterHtml = `
    <div style="margin-bottom:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <select id="admin-repo-project-filter" onchange="adminRepoProjectChange()" style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:6px 10px;border-radius:6px;font-size:13px">
        <option value="">— Select a project —</option>
        ${projects.map(p => `<option value="${p.id}" ${state.adminRepoProjectFilter == p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
      </select>
      <button class="btn btn-primary" onclick="adminRepoNew()">+ Add Repository</button>
      <button class="btn btn-outline" onclick="adminRepoScanAll()">Rescan All Repositories</button>
    </div>`;

  let repos = [];
  if (state.adminRepoProjectFilter) {
    repos = await api('/projects/' + state.adminRepoProjectFilter + '/repositories');
  }

  const editing = state.adminEditingRepo; // null = none, 0 = new, id = editing existing
  const editingRepo = editing > 0 ? repos.find(r => r.id === editing) : null;

  const providerOptions = PROVIDERS.map(p =>
    `<option value="${p}" ${editingRepo && editingRepo.provider_type === p ? 'selected' : ''}>${p}</option>`
  ).join('');

  const formHtml = (editing !== null) ? `
    <div class="admin-form">
      <div style="font-weight:600;margin-bottom:12px">${editing === 0 ? 'Add Repository' : 'Edit Repository'}</div>
      <div class="form-row">
        <div class="form-field" style="flex:2">
          <label>Project *</label>
          <select id="admin-repo-project-id" style="background:var(--surface);border:1px solid var(--border);color:var(--text);padding:7px 10px;border-radius:6px;font-size:13px;min-width:160px">
            <option value="">Select project…</option>
            ${projects.map(p => `<option value="${p.id}" ${(editingRepo ? editingRepo.project_id : state.adminRepoProjectFilter) == p.id ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
          </select>
        </div>
        <div class="form-field" style="flex:2">
          <label>Name *</label>
          <input type="text" id="admin-repo-name" placeholder="my-service" value="${esc(editingRepo ? editingRepo.name : '')}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-field" style="flex:3">
          <label>URL *</label>
          <input type="text" id="admin-repo-url" placeholder="https://github.com/org/repo" value="${esc(editingRepo ? editingRepo.url : '')}">
        </div>
        <div class="form-field">
          <label>Provider *</label>
          <select id="admin-repo-provider">
            <option value="">Select…</option>
            ${providerOptions}
          </select>
        </div>
        <div class="form-field">
          <label>Default branch</label>
          <input type="text" id="admin-repo-branch" placeholder="main" value="${esc(editingRepo ? (editingRepo.default_branch || '') : '')}">
        </div>
      </div>
      <div class="form-row">
        <div class="form-field">
          <label>Credentials username</label>
          <input type="text" id="admin-repo-cred-user" placeholder="username" value="${esc(editingRepo ? (editingRepo.credentials_username || '') : '')}">
        </div>
        <div class="form-field">
          <label>Token / password${editing > 0 ? ' (blank = clear)' : ''}</label>
          <input type="password" id="admin-repo-cred-token" placeholder="${editing > 0 ? 'Leave blank to clear' : 'Optional'}">
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="adminRepoSave(${editing})">Save</button>
        <button class="btn btn-outline" onclick="adminRepoCancel()">Cancel</button>
      </div>
    </div>` : '';

  let tableHtml;
  if (!state.adminRepoProjectFilter) {
    tableHtml = `<div class="empty"><div class="icon">📦</div><p>Select a project to manage its repositories.</p></div>`;
  } else if (!repos.length) {
    tableHtml = `<div class="empty"><div class="icon">📦</div><p>No repositories in this project yet.</p></div>`;
  } else {
    const rows = repos.map(r => `
      <tr>
        <td><div style="font-weight:600">${esc(r.name)}</div></td>
        <td style="font-size:11px;color:var(--text-muted);max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(r.url)}</td>
        <td><span class="tag">${esc(r.provider_type)}</span></td>
        <td style="color:var(--text-muted);font-size:12px">${esc(r.default_branch || '—')}</td>
        <td style="font-size:12px;color:var(--text-muted)">${fmtDate(r.created_at)}</td>
        <td onclick="event.stopPropagation()" style="white-space:nowrap">
          <button class="btn btn-outline" style="padding:3px 10px;font-size:12px" onclick="adminRepoScan(${r.id})">Rescan</button>
          <button class="btn btn-outline" style="padding:3px 10px;font-size:12px;margin-left:6px" onclick="adminRepoEdit(${r.id})">Edit</button>
          <button class="btn btn-outline" style="padding:3px 10px;font-size:12px;margin-left:6px" onclick="openEditTagsModal('repository', ${r.id}, ${esc(JSON.stringify(r.tags || []))}, ${esc(JSON.stringify(r.name))})">Edit tags</button>
          <button class="btn btn-danger" style="padding:3px 10px;font-size:12px;margin-left:6px" data-name="${esc(r.name)}" onclick="adminRepoDelete(${r.id}, this.dataset.name)">Delete</button>
        </td>
      </tr>`).join('');
    tableHtml = `
      <table>
        <thead><tr>
          <th>Name</th><th>URL</th><th>Provider</th><th>Branch</th><th>Created</th><th>Actions</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  setMain(`
    <div class="page-title">Admin: Repositories</div>
    <div class="page-subtitle">Create, edit and delete repositories</div>
    ${projectFilterHtml}
    ${formHtml}
    ${tableHtml}
  `);
}

window.adminRepoProjectChange = function() {
  const val = document.getElementById('admin-repo-project-filter').value;
  state.adminRepoProjectFilter = val ? parseInt(val, 10) : null;
  state.adminEditingRepo = null;
  window.render();
};

window.adminRepoNew = function() {
  state.adminEditingRepo = 0;
  window.render();
};

window.adminRepoEdit = function(id) {
  state.adminEditingRepo = id;
  window.render();
};

window.adminRepoCancel = function() {
  state.adminEditingRepo = null;
  window.render();
};

window.adminRepoSave = async function(id) {
  const projectId = parseInt(document.getElementById('admin-repo-project-id').value, 10);
  const name = document.getElementById('admin-repo-name').value.trim();
  const url = document.getElementById('admin-repo-url').value.trim();
  const provider_type = document.getElementById('admin-repo-provider').value;
  const default_branch = document.getElementById('admin-repo-branch').value.trim() || null;
  const credentials_username = document.getElementById('admin-repo-cred-user').value.trim() || null;
  const credentials_token = document.getElementById('admin-repo-cred-token').value || null;

  if (!name || !url || !provider_type) { alert('Name, URL and Provider are required.'); return; }

  if (id === 0) {
    if (!projectId) { alert('Please select a project.'); return; }
    await fetch(API + '/repositories', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, name, url, provider_type, default_branch, credentials_username, credentials_token, tags: [] }),
    });
    state.adminRepoProjectFilter = projectId;
  } else {
    await fetch(API + '/repositories/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, name, url, provider_type, default_branch, credentials_username, credentials_token }),
    });
  }
  state.adminEditingRepo = null;
  window.render();
};

window.adminRepoDelete = function(id, name) {
  openConfirmDialog(
    'Delete repository?',
    `This will permanently delete "${name}" and all its scans and analysis data.`,
    'Delete',
    async () => {
      await fetch(API + '/repositories/' + id, { method: 'DELETE' });
      navigate('admin-repos');
    }
  );
};

window.adminRepoScan = async function(id) {
  await fetch(API + '/repositories/' + id + '/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  alert('Scan queued.');
};

window.adminRepoScanAll = async function() {
  const res = await fetch(API + '/repositories/scan-all', { method: 'POST' });
  const scans = await res.json();
  alert(`${scans.length} scan(s) queued.`);
};
