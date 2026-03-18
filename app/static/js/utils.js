export function esc(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function fmt(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return String(n);
}

export function fmtDate(s) {
  if (!s) return '—';
  return new Date(s).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function fmtBytes(n) {
  if (n == null) return '—';
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
  if (n >= 1024) return (n / 1024).toFixed(1) + ' KB';
  return n + ' B';
}

export function tagsChips(tags) {
  if (!tags || !tags.length) return '—';
  return '<div class="tags-chips">' + tags.map(t => {
    if (t && typeof t === 'object') {
      const tooltip = t.description ? ` title="${esc(t.description)}"` : '';
      return `<span class="tag"${tooltip}>${esc(t.name)}</span>`;
    }
    return '<span class="tag">' + esc(t) + '</span>';
  }).join('') + '</div>';
}

export function scoreClass(s) {
  return s >= 70 ? 'high' : s >= 40 ? 'mid' : 'low';
}

export function setMain(html) {
  document.getElementById('main-content').innerHTML = html;
}

export function showError(err) {
  setMain(`<div class="error-banner">⚠ ${err.message || err}</div>`);
}
