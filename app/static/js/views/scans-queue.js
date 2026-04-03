import { api } from '../api.js';
import { fmtDatetime, esc, setMain, showError } from '../utils.js';
import { updateNav } from '../nav.js';

const LIMIT = 100;

let _refreshTimer = null;
const _expandedRows = new Set();
let _allScans = [];
let _offset = 0;
let _hasMore = true;
let _loading = false;
const _filters = { project: '', repository: '', status: 'pending' };
const _sort = { by: 'id', order: 'desc' };
let _scrollObserver = null;
let _filterDebounce = null;

export function stopQueueRefresh() {
  if (_refreshTimer) { clearInterval(_refreshTimer); _refreshTimer = null; }
}

export async function renderScansQueue() {
  _allScans = [];
  _offset = 0;
  _hasMore = true;
  _loading = false;
  _expandedRows.clear();
  _filters.project = '';
  _filters.repository = '';
  _filters.status = 'pending';
  _sort.by = 'id';
  _sort.order = 'desc';
  stopQueueRefresh();
  updateNav();
  await _loadMore();
  _startRefreshIfNeeded();
}

function _buildUrl(offset, limit) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    sort_by: _sort.by,
    sort_order: _sort.order,
  });
  if (_filters.project) params.set('project', _filters.project);
  if (_filters.repository) params.set('repository', _filters.repository);
  if (_filters.status) params.set('status', _filters.status);
  return '/scans/queue?' + params.toString();
}

async function _loadMore() {
  if (_loading || !_hasMore) return;
  _loading = true;
  _render();
  try {
    const batch = await api(_buildUrl(_offset, LIMIT));
    if (batch.length < LIMIT) _hasMore = false;
    _allScans = [..._allScans, ...batch];
    _offset += batch.length;
  } catch (e) {
    showError(e);
  } finally {
    _loading = false;
    _render();
  }
}

async function _refresh() {
  try {
    const reloadCount = Math.max(LIMIT, _offset);
    const batch = await api(_buildUrl(0, reloadCount));
    _allScans = batch;
    _offset = batch.length;
    _hasMore = batch.length >= reloadCount;
    const ids = new Set(batch.map(s => s.id));
    for (const id of [..._expandedRows]) {
      if (!ids.has(id)) _expandedRows.delete(id);
    }
    _render();
    _startRefreshIfNeeded();
  } catch (_e) {
    // silent background refresh failure
  }
}

function _startRefreshIfNeeded() {
  const hasActive = _allScans.some(s => s.status === 'pending' || s.status === 'running');
  if (hasActive && !_refreshTimer) {
    _refreshTimer = setInterval(_refresh, 5000);
  } else if (!hasActive && _refreshTimer) {
    stopQueueRefresh();
  }
}

function _duration(s) {
  if (!s.started_at) return '—';
  const start = new Date(s.started_at);
  const end = s.completed_at ? new Date(s.completed_at) : new Date();
  const secs = Math.floor((end - start) / 1000);
  if (secs < 60) return secs + 's';
  const m = Math.floor(secs / 60), r = secs % 60;
  return m + 'm ' + r + 's';
}

function _logHtml(scan) {
  if (!scan.scan_log || !scan.scan_log.length) {
    return '<div style="padding:8px 12px;color:var(--text-muted);font-size:12px">No log entries yet.</div>';
  }
  const rows = scan.scan_log.map(e => {
    const ts = e.ts ? new Date(e.ts).toLocaleTimeString() : '';
    return `<div style="display:flex;gap:12px;padding:3px 0;font-size:12px;line-height:1.4">
      <span style="color:var(--text-muted);white-space:nowrap;min-width:70px">${esc(ts)}</span>
      <span>${esc(e.msg)}</span>
    </div>`;
  }).join('');
  return `<div style="padding:8px 12px;font-family:monospace;background:var(--bg-code,#1a1a2e);border-top:1px solid var(--border)">${rows}</div>`;
}

function _sortIndicator(col) {
  if (_sort.by !== col) return '<span style="color:var(--text-muted);font-size:10px"> ⇅</span>';
  return _sort.order === 'asc'
    ? '<span style="font-size:10px"> ↑</span>'
    : '<span style="font-size:10px"> ↓</span>';
}

function _render() {
  if (_scrollObserver) { _scrollObserver.disconnect(); _scrollObserver = null; }

  const statusOptions = ['', 'pending', 'running', 'completed', 'failed', 'cancelled']
    .map(v => `<option value="${v}" ${_filters.status === v ? 'selected' : ''}>${v || 'All statuses'}</option>`)
    .join('');

  let html = `<div class="section-header"><div class="page-title">Scans Queue</div></div>`;

  html += `<div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
    <input type="text" placeholder="Filter by project…" value="${esc(_filters.project)}"
      style="padding:4px 8px;font-size:12px;border:1px solid var(--border);border-radius:4px;background:var(--bg-input,var(--bg));color:var(--text);min-width:150px"
      oninput="queueFilterProject(this.value)">
    <input type="text" placeholder="Filter by repository…" value="${esc(_filters.repository)}"
      style="padding:4px 8px;font-size:12px;border:1px solid var(--border);border-radius:4px;background:var(--bg-input,var(--bg));color:var(--text);min-width:150px"
      oninput="queueFilterRepository(this.value)">
    <select style="padding:4px 8px;font-size:12px;border:1px solid var(--border);border-radius:4px;background:var(--bg-input,var(--bg));color:var(--text)"
      onchange="queueFilterStatus(this.value)">${statusOptions}</select>
  </div>`;

  if (!_allScans.length && !_loading) {
    html += `<div class="empty"><div class="icon">✅</div><p>No scans found.</p></div>`;
  } else {
    html += `<table style="table-layout:fixed;width:100%">
      <colgroup>
        <col style="width:50px">
        <col style="width:130px">
        <col style="width:150px">
        <col style="width:110px">
        <col style="width:100px">
        <col style="width:150px">
        <col style="width:150px">
        <col style="width:70px">
        <col style="width:90px">
      </colgroup>
      <thead><tr>
        <th style="cursor:pointer;user-select:none" onclick="queueSort('id')">#${_sortIndicator('id')}</th>
        <th>Project</th>
        <th>Repository</th>
        <th>Branch</th>
        <th style="cursor:pointer;user-select:none" onclick="queueSort('status')">Status${_sortIndicator('status')}</th>
        <th style="cursor:pointer;user-select:none" onclick="queueSort('queued')">Queued${_sortIndicator('queued')}</th>
        <th style="cursor:pointer;user-select:none" onclick="queueSort('started')">Started${_sortIndicator('started')}</th>
        <th style="cursor:pointer;user-select:none" onclick="queueSort('duration')">Duration${_sortIndicator('duration')}</th>
        <th></th>
      </tr></thead><tbody>`;

    for (const s of _allScans) {
      const isCancelling = s.cancel_requested;
      const isActive = s.status === 'pending' || s.status === 'running';
      const isExpanded = _expandedRows.has(s.id);
      const hasLog = s.scan_log && s.scan_log.length > 0;

      html += `<tr style="cursor:pointer" onclick="toggleScanLog(${s.id})">
        <td style="font-size:12px;color:var(--text-muted)">${s.id}</td>
        <td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(s.project_name)}">${esc(s.project_name)}</td>
        <td style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${esc(s.repository_name)}">${esc(s.repository_name)}</td>
        <td><code style="font-size:12px">${esc(s.branch || '—')}</code></td>
        <td><span class="status ${s.status}">${esc(s.status)}${isCancelling ? ' (cancelling…)' : ''}</span></td>
        <td style="font-size:12px">${fmtDatetime(s.created_at)}</td>
        <td style="font-size:12px">${fmtDatetime(s.started_at)}</td>
        <td style="font-size:12px">${_duration(s)}</td>
        <td onclick="event.stopPropagation()" style="white-space:nowrap">
          ${hasLog ? `<button class="btn btn-outline btn-sm" style="padding:2px 8px;font-size:11px" onclick="toggleScanLog(${s.id})">
            ${isExpanded ? '▲ Logs' : '▼ Logs'}
          </button> ` : ''}
          ${isActive && !isCancelling ? `<button class="btn btn-danger btn-sm" onclick="cancelScan(${s.id})">■ Stop</button>` : ''}
        </td>
      </tr>`;

      if (isExpanded) {
        html += `<tr><td colspan="9" style="padding:0;border-top:none">${_logHtml(s)}</td></tr>`;
      }
    }

    html += '</tbody></table>';

    if (_loading) {
      html += `<div id="scroll-sentinel" style="padding:12px;text-align:center;color:var(--text-muted);font-size:12px"><span class="spinner"></span> Loading…</div>`;
    } else if (_hasMore) {
      html += `<div id="scroll-sentinel" style="padding:4px"></div>`;
    } else {
      const hasActive = _allScans.some(s => s.status === 'pending' || s.status === 'running');
      html += `<div style="margin-top:8px;font-size:12px;color:var(--text-muted)">Showing ${_allScans.length} scan${_allScans.length !== 1 ? 's' : ''}.${!hasActive ? ' Auto-refresh paused.' : ''}</div>`;
    }
  }

  setMain(html);

  if (_hasMore && !_loading) {
    const sentinel = document.getElementById('scroll-sentinel');
    if (sentinel) {
      _scrollObserver = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) _loadMore();
      }, { rootMargin: '100px' });
      _scrollObserver.observe(sentinel);
    }
  }
}

function _resetAndReload() {
  if (_scrollObserver) { _scrollObserver.disconnect(); _scrollObserver = null; }
  stopQueueRefresh();
  _allScans = [];
  _offset = 0;
  _hasMore = true;
  _loading = false;
  _loadMore().then(() => _startRefreshIfNeeded());
}

export function queueFilterProject(val) {
  _filters.project = val;
  if (_filterDebounce) clearTimeout(_filterDebounce);
  _filterDebounce = setTimeout(_resetAndReload, 300);
}

export function queueFilterRepository(val) {
  _filters.repository = val;
  if (_filterDebounce) clearTimeout(_filterDebounce);
  _filterDebounce = setTimeout(_resetAndReload, 300);
}

export function queueFilterStatus(val) {
  _filters.status = val;
  _resetAndReload();
}

export function queueSort(col) {
  if (_sort.by === col) {
    _sort.order = _sort.order === 'desc' ? 'asc' : 'desc';
  } else {
    _sort.by = col;
    _sort.order = 'desc';
  }
  _resetAndReload();
}

export function toggleScanLog(scanId) {
  if (_expandedRows.has(scanId)) {
    _expandedRows.delete(scanId);
  } else {
    _expandedRows.add(scanId);
  }
  _render();
}

export async function cancelScan(scanId) {
  try {
    await api('/scans/' + scanId + '/cancel', { method: 'POST' });
    await _refresh();
  } catch (e) {
    showError(e);
  }
}
