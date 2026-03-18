import { api } from '../api.js';
import { state } from '../state.js';
import { navigate } from '../nav.js';
import { esc, fmtDate, setMain } from '../utils.js';
import { openConfirmDialog } from '../confirm.js';
import { API } from '../state.js';

export async function renderAdminProjects() {
  const projects = await api('/projects');

  const editing = state.adminEditingProject; // null = none, 0 = new, id = editing existing
  const editingProject = editing > 0 ? projects.find(p => p.id === editing) : null;

  const formHtml = (editing !== null) ? `
    <div class="admin-form">
      <div style="font-weight:600;margin-bottom:12px">${editing === 0 ? 'New Project' : 'Edit Project'}</div>
      <div class="form-row">
        <div class="form-field" style="flex:2">
          <label>Name *</label>
          <input type="text" id="admin-proj-name" placeholder="Project name" value="${esc(editingProject ? editingProject.name : '')}">
        </div>
        <div class="form-field" style="flex:3">
          <label>Description</label>
          <input type="text" id="admin-proj-desc" placeholder="Optional description" value="${esc(editingProject ? (editingProject.description || '') : '')}">
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary" onclick="adminProjSave(${editing})">Save</button>
        <button class="btn btn-outline" onclick="adminProjCancel()">Cancel</button>
      </div>
    </div>` : '';

  const rows = projects.map(p => `
    <tr>
      <td><div style="font-weight:600">${esc(p.name)}</div></td>
      <td style="color:var(--text-muted);font-size:12px">${esc(p.description || '—')}</td>
      <td style="font-size:12px;color:var(--text-muted)">${fmtDate(p.created_at)}</td>
      <td onclick="event.stopPropagation()" style="white-space:nowrap">
        <button class="btn btn-outline" style="padding:3px 10px;font-size:12px" onclick="adminProjScanAll(${p.id})">Rescan Repos</button>
        <button class="btn btn-outline" style="padding:3px 10px;font-size:12px;margin-left:6px" onclick="adminProjEdit(${p.id})">Edit</button>
        <button class="btn btn-danger" style="padding:3px 10px;font-size:12px;margin-left:6px" onclick="adminProjDelete(${p.id}, ${JSON.stringify(esc(p.name))})">Delete</button>
      </td>
    </tr>`).join('');

  const tableHtml = projects.length ? `
    <table>
      <thead><tr>
        <th>Name</th>
        <th>Description</th>
        <th>Created</th>
        <th>Actions</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>` : `<div class="empty"><div class="icon">📂</div><p>No projects yet.</p></div>`;

  setMain(`
    <div class="page-title">Admin: Projects</div>
    <div class="page-subtitle">Create, edit and delete projects</div>
    <div style="margin-bottom:16px">
      <button class="btn btn-primary" onclick="adminProjNew()">+ New Project</button>
    </div>
    ${formHtml}
    ${tableHtml}
  `);
}

window.adminProjNew = function() {
  state.adminEditingProject = 0;
  window.render();
};

window.adminProjEdit = function(id) {
  state.adminEditingProject = id;
  window.render();
};

window.adminProjCancel = function() {
  state.adminEditingProject = null;
  window.render();
};

window.adminProjSave = async function(id) {
  const name = document.getElementById('admin-proj-name').value.trim();
  if (!name) { alert('Name is required.'); return; }
  const description = document.getElementById('admin-proj-desc').value.trim() || null;
  if (id === 0) {
    await fetch(API + '/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, tags: [] }),
    });
  } else {
    await fetch(API + '/projects/' + id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description }),
    });
  }
  state.adminEditingProject = null;
  window.render();
};

window.adminProjDelete = function(id, name) {
  openConfirmDialog(
    'Delete project?',
    `This will permanently delete "${name}" and all its repositories and scans.`,
    'Delete',
    async () => {
      await fetch(API + '/projects/' + id, { method: 'DELETE' });
      navigate('admin-projects');
    }
  );
};

window.adminProjScanAll = async function(id) {
  const res = await fetch(API + '/projects/' + id + '/scan-all', { method: 'POST' });
  const scans = await res.json();
  alert(`${scans.length} scan(s) queued.`);
};
