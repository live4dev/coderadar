import { API } from './state.js';
import { showError, esc, fmtDate } from './utils.js';

let renderCallback = null;
let editTagsModalEntity = null;

export function initModal(renderCb) {
  renderCallback = renderCb;
}

export function openEditTagsModal(entityType, entityId, currentTags, entityName) {
  editTagsModalEntity = { type: entityType, id: entityId };
  document.getElementById('edit-tags-modal-title').textContent = 'Edit tags' + (entityName ? ': ' + entityName : '');

  if (entityType === 'repository') {
    document.getElementById('edit-tags-simple').style.display = 'none';
    document.getElementById('edit-tags-rich').style.display = 'block';
    _renderTagRows(currentTags || []);
  } else {
    document.getElementById('edit-tags-rich').style.display = 'none';
    document.getElementById('edit-tags-simple').style.display = 'block';
    const names = (currentTags || []).map(t => (t && typeof t === 'object' ? t.name : t));
    document.getElementById('edit-tags-input').value = names.length ? names.join(', ') : '';
  }

  document.getElementById('edit-tags-modal').style.display = 'flex';
}

function _renderTagRows(tags) {
  const list = document.getElementById('edit-tags-list');
  list.innerHTML = '';
  tags.forEach(t => _appendTagRow(t.name || '', t.description || '', t.date || null));
  if (!tags.length) _appendTagRow('', '', null);
}

function _appendTagRow(name, description, date) {
  const list = document.getElementById('edit-tags-list');
  const row = document.createElement('div');
  row.className = 'tag-row';
  row.style.cssText = 'display:flex;gap:6px;align-items:flex-start;margin-bottom:6px;';
  const dateStr = date ? fmtDate(date) : '';
  row.innerHTML = `
    <div style="flex:1;display:flex;flex-direction:column;gap:4px;">
      <input type="text" class="modal-input tag-name-input" placeholder="Tag name" value="${esc(name)}" style="margin:0">
      <input type="text" class="modal-input tag-desc-input" placeholder="Description (optional)" value="${esc(description)}" style="margin:0;font-size:12px">
      ${dateStr ? `<span style="font-size:11px;color:var(--text-muted)">Added: ${esc(dateStr)}</span>` : ''}
    </div>
    <button type="button" class="btn btn-outline" style="padding:4px 8px;font-size:12px;margin-top:2px" onclick="this.closest('.tag-row').remove()">✕</button>
  `;
  list.appendChild(row);
}

export function addTagRow() {
  _appendTagRow('', '', null);
}

export function closeEditTagsModal() {
  document.getElementById('edit-tags-modal').style.display = 'none';
  editTagsModalEntity = null;
}

export async function saveEditTagsModal() {
  if (!editTagsModalEntity) return;

  let body;
  if (editTagsModalEntity.type === 'repository') {
    const rows = document.querySelectorAll('#edit-tags-list .tag-row');
    const tags = [];
    rows.forEach(row => {
      const name = row.querySelector('.tag-name-input').value.trim();
      const description = row.querySelector('.tag-desc-input').value.trim() || null;
      if (name) tags.push({ name, description });
    });
    body = { tags };
  } else {
    const raw = document.getElementById('edit-tags-input').value || '';
    const tags = raw.split(',').map(s => s.trim()).filter(Boolean);
    body = { tags };
  }

  const path = editTagsModalEntity.type === 'project' ? '/projects/' + editTagsModalEntity.id + '/tags'
    : editTagsModalEntity.type === 'repository' ? '/repositories/' + editTagsModalEntity.id + '/tags'
    : '/developers/' + editTagsModalEntity.id + '/tags';

  try {
    const res = await fetch(API + path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(await res.text() || res.status);
    closeEditTagsModal();
    if (renderCallback) renderCallback();
  } catch (e) { showError(e); }
}
