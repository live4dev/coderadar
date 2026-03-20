import { api } from '../api.js';
import { fmtDate, esc, setMain, showError } from '../utils.js';
import { updateNav } from '../nav.js';

let _refreshTimer = null;

export function stopQueueRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
}

export async function renderScansQueue() {
  await _load();
  stopQueueRefresh();
  _refreshTimer = setInterval(_load, 5000);
  updateNav();
}

async function _load() {
  try {
    const scans = await api('/scans/queue');
    let html = `<div class="section-header"><div class="page-title">Scans Queue</div></div>`;
    if (!scans.length) {
      html += `<div class="empty"><div class="icon">✅</div><p>No pending or running scans.</p></div>`;
    } else {
      html += `<table>
        <thead><tr>
          <th>ID</th><th>Repository</th><th>Branch</th><th>Status</th>
          <th>Queued</th><th>Started</th><th></th>
        </tr></thead><tbody>`;
      for (const s of scans) {
        const isCancelling = s.cancel_requested;
        html += `<tr>
          <td>#${s.id}</td>
          <td>${esc(s.repository_name)}</td>
          <td><code style="font-size:12px">${esc(s.branch || '—')}</code></td>
          <td><span class="status ${s.status}">${esc(s.status)}${isCancelling ? ' (cancelling…)' : ''}</span></td>
          <td>${fmtDate(s.created_at)}</td>
          <td>${s.started_at ? fmtDate(s.started_at) : '—'}</td>
          <td>${isCancelling ? '' : `<button class="btn btn-danger btn-sm" onclick="cancelScan(${s.id})">■ Stop</button>`}</td>
        </tr>`;
      }
      html += '</tbody></table>';
    }
    setMain(html);
  } catch (e) {
    showError(e);
  }
}

export async function cancelScan(scanId) {
  try {
    await api('/scans/' + scanId + '/cancel', { method: 'POST' });
    await _load();
  } catch (e) {
    showError(e);
  }
}
