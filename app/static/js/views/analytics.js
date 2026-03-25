import { state } from '../state.js';
import { api } from '../api.js';
import { fmt, setMain } from '../utils.js';

export let treemapChartInstance = null;
let stateTreemapMetric = 'loc';

export let activityTreeChartInstance = null;
let stateActivityMetric = 'commits';
let stateActivityPeriod = '1y';

export function activityPeriodChange() {
  const sel = document.getElementById('activity-period');
  if (sel) stateActivityPeriod = sel.value;
  renderAnalytics();
}

export function disposeActivityTree() {
  if (activityTreeChartInstance) {
    activityTreeChartInstance.dispose();
    activityTreeChartInstance = null;
  }
}

export function activityMetricChange() {
  const sel = document.getElementById('activity-metric');
  if (sel) stateActivityMetric = sel.value;
  renderAnalytics();
}

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
      <label for="treemap-metric" style="font-size:13px;color:#64748b">Size by</label>
      <select id="treemap-metric" class="modal-input" style="width:120px;margin:0" onchange="treemapMetricChange()">
        <option value="loc" ${stateTreemapMetric === 'loc' ? 'selected' : ''}>LOC</option>
        <option value="files" ${stateTreemapMetric === 'files' ? 'selected' : ''}>Files</option>
      </select>
    </div>
    <div id="treemap-chart"></div>
    <h2 style="margin-top:32px;margin-bottom:4px;font-size:15px;color:var(--text)">Activity Map</h2>
    <p class="page-subtitle">Color intensity = developer activity per repository (from latest completed scan per repo).</p>
    <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px">
      <label for="activity-metric" style="font-size:13px;color:#64748b">Color by</label>
      <select id="activity-metric" class="modal-input" style="width:140px;margin:0" onchange="activityMetricChange()">
        <option value="commits" ${stateActivityMetric === 'commits' ? 'selected' : ''}>Commits</option>
        <option value="lines" ${stateActivityMetric === 'lines' ? 'selected' : ''}>Lines added</option>
      </select>
      <label for="activity-period" style="font-size:13px;color:#64748b;margin-left:16px">Period</label>
      <select id="activity-period" class="modal-input" style="width:120px;margin:0" onchange="activityPeriodChange()">
        <option value="1m" ${stateActivityPeriod === '1m' ? 'selected' : ''}>1 month</option>
        <option value="3m" ${stateActivityPeriod === '3m' ? 'selected' : ''}>3 months</option>
        <option value="6m" ${stateActivityPeriod === '6m' ? 'selected' : ''}>6 months</option>
        <option value="1y" ${stateActivityPeriod === '1y' ? 'selected' : ''}>1 year</option>
      </select>
    </div>
    <div id="activity-tree-chart" style="width:100%;height:500px"></div>
  `);

  const params = new URLSearchParams({ metric: stateTreemapMetric, group_by: 'projects_repos' });
  const actParams = new URLSearchParams({ metric: stateActivityMetric, period: stateActivityPeriod });
  const [tree, activityTree] = await Promise.all([
    api('/analytics/treemap?' + params.toString()),
    api('/analytics/activity-tree?' + actParams.toString()),
  ]);

  // --- existing treemap ---
  const root = treeToECharts(tree);
  if (!root || root.value === 0) {
    document.getElementById('treemap-chart').innerHTML = '<div class="empty"><p>No scan data yet. Run scans on repositories to see the treemap.</p></div>';
  } else {
    const chartEl = document.getElementById('treemap-chart');
    if (!window.echarts) {
      chartEl.innerHTML = '<div class="empty"><p>ECharts failed to load.</p></div>';
    } else {
      treemapChartInstance = echarts.init(chartEl, 'dark');
      treemapChartInstance.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'item', formatter: function(info) {
          const v = info.value;
          const pct = root.value ? ((v / root.value) * 100).toFixed(1) : 0;
          const path = info.treePathInfo || [];
          const displayName = path.length >= 2 ? path[0].name + ' / ' + info.name : info.name;
          return displayName + '<br/>' + (stateTreemapMetric === 'loc' ? 'LOC' : 'Files') + ': ' + fmt(v) + ' (' + pct + '%)';
        }},
        series: [{
          type: 'treemap',
          data: root.children || [],
          roam: false,
          nodeClick: 'zoomToNode',
          breadcrumb: { show: true, itemStyle: { color: '#22263a' }, textStyle: { color: '#64748b' } },
          label: { show: true, formatter: function(info) { return info.name; } },
          itemStyle: { borderColor: '#2e3350', borderWidth: 1 },
          levels: [
            { itemStyle: { borderColor: '#2e3350', borderWidth: 2 }, upperLabel: { show: true, fontSize: 12, color: '#94a3b8', padding: [4, 8] } },
            { itemStyle: { borderColor: '#2e3350', borderWidth: 1 } },
          ],
        }],
      });
    }
  }

  // --- activity tree ---
  const activityRoot = treeToECharts(activityTree);
  const actEl = document.getElementById('activity-tree-chart');
  if (!activityRoot || activityRoot.value === 0) {
    actEl.innerHTML = '<div class="empty"><p>No activity data yet. Run scans to see the activity map.</p></div>';
    return;
  }
  if (!window.echarts) return;
  activityTreeChartInstance = echarts.init(actEl, 'dark');
  const actLabel = stateActivityMetric === 'commits' ? 'Commits' : 'Lines added';
  activityTreeChartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: (info) => {
      const path = info.treePathInfo || [];
      const displayName = path.length >= 2 ? path[0].name + ' / ' + info.name : info.name;
      return `${displayName}<br/>${actLabel}: ${fmt(info.value)}`;
    }},
    series: [{
      type: 'treemap',
      data: activityRoot.children || [],
      roam: false,
      nodeClick: 'zoomToNode',
      colorMappingBy: 'value',
      color: ['#161b22', '#0e4429', '#006d32', '#26a641', '#39d353'],
      breadcrumb: { show: true, itemStyle: { color: '#22263a' }, textStyle: { color: '#64748b' } },
      label: { show: true, formatter: (info) => info.name },
      itemStyle: { borderColor: '#2e3350', borderWidth: 1 },
      levels: [
        { itemStyle: { borderColor: '#2e3350', borderWidth: 2 }, upperLabel: { show: true, fontSize: 12, color: '#94a3b8', padding: [4, 8] } },
        { itemStyle: { borderColor: '#2e3350', borderWidth: 1 } },
      ],
    }],
  });
}
