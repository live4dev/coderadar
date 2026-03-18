import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, setMain } from '../utils.js';

export let treemapChartInstance = null;
let stateTreemapMetric = 'loc';

export function disposeTreemap() {
  if (treemapChartInstance) {
    treemapChartInstance.dispose();
    treemapChartInstance = null;
  }
}

export function treemapMetricChange() {
  const sel = document.getElementById('treemap-metric');
  if (sel) stateTreemapMetric = sel.value;
  renderAnalytics();
}

function treeToECharts(node) {
  if (!node) return null;
  const name = node.name === 'root' ? 'All projects' : node.name;
  const n = { name, value: Number(node.value) || 0 };
  if (node.children && node.children.length) n.children = node.children.map(treeToECharts).filter(Boolean);
  return n;
}

export async function renderAnalytics() {
  setMain(`
    <h1 class="page-title">Analytics</h1>
    <p class="page-subtitle">Treemap: LOC or files by project and repository (from latest completed scan per repo).</p>
    <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px">
      <label for="treemap-metric" style="font-size:13px;color:var(--text-muted)">Size by</label>
      <select id="treemap-metric" class="modal-input" style="width:120px;margin:0" onchange="treemapMetricChange()">
        <option value="loc" ${stateTreemapMetric === 'loc' ? 'selected' : ''}>LOC</option>
        <option value="files" ${stateTreemapMetric === 'files' ? 'selected' : ''}>Files</option>
      </select>
    </div>
    <div id="treemap-chart"></div>
  `);
  const params = new URLSearchParams({ metric: stateTreemapMetric, group_by: 'projects_repos' });
  const tree = await api('/analytics/treemap?' + params.toString());
  const root = treeToECharts(tree);
  if (!root || root.value === 0) {
    document.getElementById('treemap-chart').innerHTML = '<div class="empty"><p>No scan data yet. Run scans on repositories to see the treemap.</p></div>';
    return;
  }
  const chartEl = document.getElementById('treemap-chart');
  if (!window.echarts) {
    chartEl.innerHTML = '<div class="empty"><p>ECharts failed to load.</p></div>';
    return;
  }
  treemapChartInstance = echarts.init(chartEl, 'dark');
  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: function(info) {
      const v = info.value;
      const pct = root.value ? ((v / root.value) * 100).toFixed(1) : 0;
      return info.name + '<br/>' + (stateTreemapMetric === 'loc' ? 'LOC' : 'Files') + ': ' + fmt(v) + ' (' + pct + '%)';
    }},
    series: [{
      type: 'treemap',
      data: [root],
      roam: false,
      nodeClick: 'zoomToNode',
      breadcrumb: { show: true, itemStyle: { color: 'var(--surface2)' }, textStyle: { color: 'var(--text-muted)' } },
      label: { show: true, formatter: function(info) { return info.name; } },
      itemStyle: { borderColor: 'var(--border)', borderWidth: 1 },
      levels: [
        { itemStyle: { borderColor: 'var(--border)' }, upperLabel: { show: true } },
        { itemStyle: { borderColor: 'var(--border)' } },
      ],
    }],
  };
  treemapChartInstance.setOption(option);
}
