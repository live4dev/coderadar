import { state } from '../state.js';
import { api } from '../api.js';
import { scoreClass, esc } from '../utils.js';

export async function buildScoresTab(scan) {
  const scores = await api('/scans/' + state.scanId + '/scores');
  const overall = scores.find(s => s.domain === 'overall');

  const rows = scores.filter(s => s.domain !== 'overall').map(s => {
    const cls = scoreClass(s.score);
    return `<tr>
      <td style="text-transform:capitalize;font-weight:500">${esc(s.domain.replace(/_/g, ' '))}</td>
      <td style="width:60%">
        <div class="score-bar-wrap">
          <div class="score-bar"><div class="score-fill ${cls}" style="width:${s.score}%"></div></div>
          <span class="score-num" style="color:var(--${cls === 'high' ? 'green' : cls === 'mid' ? 'yellow' : 'red'})">${s.score.toFixed(1)}</span>
        </div>
      </td>
    </tr>`;
  }).join('');

  const ov = overall ? overall.score : 0;
  const ovCls = scoreClass(ov);

  return `
    <div style="display:flex;align-items:center;gap:24px;margin-bottom:28px;padding:20px;background:var(--surface);border:1px solid var(--border);border-radius:10px">
      <div style="text-align:center;min-width:80px">
        <div style="font-size:42px;font-weight:800;color:var(--${ovCls === 'high' ? 'green' : ovCls === 'mid' ? 'yellow' : 'red'})">${ov.toFixed(0)}</div>
        <div style="font-size:12px;color:var(--text-muted)">Overall</div>
      </div>
      <div style="flex:1">
        <div class="score-bar" style="height:10px"><div class="score-fill ${ovCls}" style="width:${ov}%"></div></div>
      </div>
    </div>
    <table>
      <thead><tr><th>Domain</th><th>Score</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}
