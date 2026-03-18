import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, esc } from '../utils.js';
import { LANG_COLORS } from '../constants.js';

export async function buildLanguagesTab() {
  const langs = await api('/scans/' + state.scanId + '/languages');
  if (!langs.length) return '<div class="empty"><div class="icon">🌐</div><p>No language data.</p></div>';

  const segments = langs.map((l, i) =>
    `<div class="lang-segment" style="width:${l.percentage.toFixed(1)}%;background:${LANG_COLORS[i % LANG_COLORS.length]}"></div>`
  ).join('');

  const dots = langs.map((l, i) =>
    `<span><span class="lang-dot" style="background:${LANG_COLORS[i % LANG_COLORS.length]}"></span>${esc(l.language)} ${l.percentage.toFixed(1)}%</span>`
  ).join('');

  const rows = langs.map(l => `<tr>
    <td>${esc(l.language)}</td>
    <td>${fmt(l.file_count)}</td>
    <td>${fmt(l.loc)}</td>
    <td>
      <div class="score-bar-wrap">
        <div class="score-bar"><div class="score-fill high" style="width:${l.percentage.toFixed(1)}%"></div></div>
        <span class="score-num" style="font-size:12px">${l.percentage.toFixed(1)}%</span>
      </div>
    </td>
  </tr>`).join('');

  return `
    <div class="lang-bar">${segments}</div>
    <div class="lang-colors" style="margin-bottom:24px">${dots}</div>
    <table>
      <thead><tr><th>Language</th><th>Files</th><th>LOC</th><th>Share</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
