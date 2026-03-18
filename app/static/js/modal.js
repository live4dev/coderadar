import { API } from './state.js';
import { showError } from './utils.js';

let renderCallback = null;
let editTagsModalEntity = null;

export function initModal(renderCb) {
  renderCallback = renderCb;
}

export function openEditTagsModal(entityType, entityId, currentTags, entityName) {
  editTagsModalEntity = { type: entityType, id: entityId };
  document.getElementById('edit-tags-modal-title').textContent = 'Edit tags' + (entityName ? ': ' + entityName : '');
  document.getElementById('edit-tags-input').value = (currentTags && currentTags.length) ? currentTags.join(', ') : '';
  document.getElementById('edit-tags-modal').style.display = 'flex';
}

export function closeEditTagsModal() {
  document.getElementById('edit-tags-modal').style.display = 'none';
  editTagsModalEntity = null;
}

export async function saveEditTagsModal() {
  if (!editTagsModalEntity) return;
  const raw = document.getElementById('edit-tags-input').value || '';
  const tags = raw.split(',').map(s => s.trim()).filter(Boolean);
  const path = editTagsModalEntity.type === 'project' ? '/projects/' + editTagsModalEntity.id + '/tags'
    : editTagsModalEntity.type === 'repository' ? '/repositories/' + editTagsModalEntity.id + '/tags'
    : '/developers/' + editTagsModalEntity.id + '/tags';
  try {
    const res = await fetch(API + path, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tags }) });
    if (!res.ok) throw new Error(await res.text() || res.status);
    closeEditTagsModal();
    if (renderCallback) renderCallback();
  } catch (e) { showError(e); }
}
