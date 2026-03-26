import { api } from '../api.js';
import { fmt, fmtBytes, setMain } from '../utils.js';

export let treemapChartInstance = null;
let stateTreemapMetric = 'loc';

export let activityTreeChartInstance = null;
let stateActivityMetric = 'commits';
let stateActivityPeriod = '1y';

export let sizeHistoryChartInstance = null;
let stateSizeMetric = 'loc';

let analyticsTab = 'code-size';

export function showAnalyticsTab(tab) {
  analyticsTab = tab;
  disposeTreemap();
  disposeActivityTree();
  disposeSizeHistory();
  renderAnalytics();
}

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

export function disposeSizeHistory() {
  if (sizeHistoryChartInstance) {
    sizeHistoryChartInstance.dispose();
    sizeHistoryChartInstance = null;
  }
}

export function sizeMetricChange() {
  const sel = document.getElementById('size-history-metric');
  if (sel) stateSizeMetric = sel.value;
  renderAnalytics();
}

function treeToECharts(node) {
  if (!node) return null;
  const name = node.name === 'root' ? 'All projects' : node.name;
  const n = { name, value: Number(node.value) || 0 };
  if (node.children && node.children.length) n.children = node.children.map(treeToECharts).filter(Boolean);
  return n;
}

const tabDefs = [
  { key: 'code-size', label: 'Code Size' },
  { key: 'activity', label: 'Activity Map' },
  { key: 'size-history', label: 'Size History' },
];

export async function renderAnalytics() {
  const tabs = tabDefs
    .map(t => `<div class="tab ${analyticsTab === t.key ? 'active' : ''}" onclick="showAnalyticsTab('${t.key}')">${t.label}</div>`)
    .join('');

  let contentHtml = '';
  if (analyticsTab === 'code-size') {
    contentHtml = `
      <p class="page-subtitle">LOC or files by project and repository (from latest completed scan per repo).</p>
      <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px">
        <label for="treemap-metric" style="font-size:13px;color:#64748b">Size by</label>
        <select id="treemap-metric" class="modal-input" style="width:120px;margin:0" onchange="treemapMetricChange()">
          <option value="loc" ${stateTreemapMetric === 'loc' ? 'selected' : ''}>LOC</option>
          <option value="files" ${stateTreemapMetric === 'files' ? 'selected' : ''}>Files</option>
        </select>
      </div>
      <div id="treemap-chart"></div>`;
  } else if (analyticsTab === 'activity') {
    contentHtml = `
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
      <div id="activity-tree-chart" style="width:100%;height:500px"></div>`;
  } else {
    contentHtml = `
      <p class="page-subtitle">Codebase size month by month over the last 5 years, stacked by repository.</p>
      <div style="margin-bottom:12px;display:flex;align-items:center;gap:12px">
        <label for="size-history-metric" style="font-size:13px;color:#64748b">Metric</label>
        <select id="size-history-metric" class="modal-input" style="width:120px;margin:0" onchange="sizeMetricChange()">
          <option value="loc" ${stateSizeMetric === 'loc' ? 'selected' : ''}>LOC</option>
          <option value="files" ${stateSizeMetric === 'files' ? 'selected' : ''}>Files</option>
          <option value="bytes" ${stateSizeMetric === 'bytes' ? 'selected' : ''}>Size</option>
        </select>
      </div>
      <div id="size-history-chart" style="width:100%;height:400px"></div>`;
  }

  setMain(`
    <h1 class="page-title">Analytics</h1>
    <div class="tabs">${tabs}</div>
    ${contentHtml}
  `);

  if (analyticsTab === 'code-size') {
    const params = new URLSearchParams({ metric: stateTreemapMetric, group_by: 'projects_repos' });
    const tree = await api('/analytics/treemap?' + params.toString());
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
            upperLabel: {show: true},
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
  } else if (analyticsTab === 'activity') {
    const actParams = new URLSearchParams({ metric: stateActivityMetric, period: stateActivityPeriod });
    const activityTree = await api('/analytics/activity-tree?' + actParams.toString());
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
        upperLabel: {show: true},
        levels: [
          { itemStyle: { borderColor: '#2e3350', borderWidth: 2 }, upperLabel: { show: true, fontSize: 12, color: '#94a3b8', padding: [4, 8] } },
          { itemStyle: { borderColor: '#2e3350', borderWidth: 1 } },
        ],
      }],
    });
  } else {
    const sizeParams = new URLSearchParams({ metric: stateSizeMetric });
    const sizeHistory = await api('/analytics/size-history?' + sizeParams.toString());
    const sizeEl = document.getElementById('size-history-chart');
    if (!sizeHistory || !sizeHistory.repos || sizeHistory.repos.length === 0 || sizeHistory.totals.every(v => v === 0)) {
      sizeEl.innerHTML = '<div class="empty"><p>No scan history yet. Run scans on repositories to see size trends.</p></div>';
      return;
    }
    if (!window.echarts) return;

    const fmtVal = stateSizeMetric === 'bytes' ? fmtBytes : fmt;

    const monthNames = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const xLabels = sizeHistory.months.map(m => {
      const [y, mo] = m.split('-');
      return monthNames[parseInt(mo, 10) - 1] + ' ' + y;
    });

    const palette = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#84cc16','#ec4899','#14b8a6'];
    const series = sizeHistory.repos.map((repo, i) => ({
      name: repo.name,
      type: 'line',
      stack: 'total',
      smooth: true,
      areaStyle: { opacity: 0.6 },
      lineStyle: { width: 1 },
      color: palette[i % palette.length],
      data: repo.values.map(v => v ?? 0),
      emphasis: { focus: 'series' },
    }));

    sizeHistoryChartInstance = echarts.init(sizeEl, 'dark');
    sizeHistoryChartInstance.setOption({
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params) => {
          const month = params[0]?.axisValue || '';
          const total = params.reduce((s, p) => s + (p.value || 0), 0);
          const lines = params
            .filter(p => p.value > 0)
            .sort((a, b) => b.value - a.value)
            .map(p => `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:4px"></span>${p.seriesName}: ${fmtVal(p.value)}`)
            .join('<br/>');
          return `<b>${month}</b><br/>Total: ${fmtVal(total)}<br/>${lines}`;
        },
      },
      legend: { type: 'scroll', bottom: 0, textStyle: { color: '#94a3b8', fontSize: 11 } },
      grid: { left: 60, right: 20, top: 20, bottom: 50 },
      xAxis: {
        type: 'category',
        data: xLabels,
        axisLabel: {
          color: '#64748b',
          fontSize: 10,
          interval: (idx) => idx % 6 === 0,
          rotate: 30,
        },
        axisLine: { lineStyle: { color: '#2e3350' } },
      },
      yAxis: {
        type: 'value',
        axisLabel: { color: '#64748b', fontSize: 10, formatter: fmtVal },
        splitLine: { lineStyle: { color: '#1e2235' } },
      },
      series,
    });
  }
}
