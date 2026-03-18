import { fmt, fmtBytes, esc } from '../utils.js';

export async function buildSummaryTab(scan) {
  return `
    <div class="stats-row">
      <div class="stat-box">
        <div class="stat-label">Files</div>
        <div class="stat-value">${fmt(scan.total_files)}</div>
        <div class="stat-sub">${fmt(scan.file_count_source)} source · ${fmt(scan.file_count_test)} test</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Lines of Code</div>
        <div class="stat-value">${fmt(scan.total_loc)}</div>
        <div class="stat-sub">avg ${Math.round(scan.avg_file_loc || 0)} per file</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Size</div>
        <div class="stat-value">${fmtBytes(scan.size_bytes)}</div>
        <div class="stat-sub">${fmt(scan.large_files_count)} large files</div>
      </div>
      <div class="stat-box">
        <div class="stat-label">Project type</div>
        <div class="stat-value" style="font-size:15px;padding-top:4px">${esc(scan.project_type || '—')}</div>
        <div class="stat-sub">${esc(scan.primary_language || '—')}</div>
      </div>
    </div>
  `;
}
