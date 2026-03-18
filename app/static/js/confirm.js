let _confirmAction = null;

export function openConfirmDialog(title, body, okLabel, action) {
  _confirmAction = action;
  document.getElementById('confirm-dialog-title').textContent = title;
  document.getElementById('confirm-dialog-body').textContent = body;
  document.getElementById('confirm-dialog-ok').textContent = okLabel || 'Delete';
  document.getElementById('confirm-dialog').style.display = 'flex';
}

export function closeConfirmDialog() {
  document.getElementById('confirm-dialog').style.display = 'none';
  _confirmAction = null;
}

export async function runConfirmAction() {
  if (!_confirmAction) return;
  const fn = _confirmAction;
  closeConfirmDialog();
  try { await fn(); } catch (e) { console.error(e); }
}
