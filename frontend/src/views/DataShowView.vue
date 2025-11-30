<template>
  <div class="data-show-page">
    <!-- Controls -->
    <div class="controls" ref="controlsRef">
      <el-row :gutter="12" align="middle">
        <el-col :span="6">
          <el-select v-model="granularity" placeholder="选择粒度" style="width:100%">
            <el-option label="年度" value="年度" />
            <el-option label="季度" value="季度" />
            <el-option label="月度" value="月度" />
          </el-select>
        </el-col>

        <el-col :span="5">
          <el-input-number
            v-model="years"
            :min="1"
            :max="20"
            controls-position="right"
            style="width:100%"
            :placeholder="'年数 (1 - 20)'"
          />
        </el-col>

        <el-col :span="7">
          <el-checkbox-group v-model="selectedClasses" style="display:flex; gap:8px;">
            <el-checkbox label="large">大运量</el-checkbox>
            <el-checkbox label="medium">中运量</el-checkbox>
            <el-checkbox label="small">小运量(合计)</el-checkbox>
          </el-checkbox-group>
        </el-col>

        <el-col :span="4">
          <el-select v-model="viewMode" style="width:100%">
            <el-option label="聚合总量" value="aggregate" />
            <el-option label="Top‑N 单航线" value="topn" />
            <el-option label="热力图" value="heatmap" />
          </el-select>
        </el-col>

        <el-col :span="2" class="btn-col">
          <el-button type="primary" @click="loadForecast" :loading="loading">加载</el-button>
        </el-col>
      </el-row>

      <el-row style="margin-top:10px;" align="middle">
        <el-col :span="6">
          <el-input-number v-if="viewMode === 'topn'" v-model="topN" :min="1" :max="50" style="width:120px" />
          <span v-if="viewMode === 'topn'" style="margin-left:8px; color:#909399">Top-N</span>
        </el-col>

        <el-col :span="12">
          <div class="small-help">说明：长度按“年”计（最大 20 年）。请求会把年数转换为对应的月/季/年周期数发送到后端。</div>
        </el-col>
      </el-row>
    </div>

    <!-- Main content -->
    <div class="content">
      <div class="chart-area-wrap">
        <div ref="chartRef" class="chart-area"></div>
      </div>

      <div class="side-panel">
        <el-card>
          <div slot="header" class="card-header">关键统计</div>
          <el-descriptions column="1" border>
            <el-descriptions-item label="选择粒度">{{ granularity }}</el-descriptions-item>
            <el-descriptions-item label="年数">{{ years }}</el-descriptions-item>
            <el-descriptions-item label="周期数">{{ periods }}</el-descriptions-item>
            <el-descriptions-item label="已加载航线数">
              {{ preparedCount }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card style="margin-top:12px;">
          <div slot="header" class="card-header">汇总（所选类别）</div>
          <el-table :data="summaryTable" stripe size="small" style="width:100%">
            <el-table-column prop="classLabel" label="等级" width="100" />
            <el-table-column prop="routeCount" label="航线数" width="90" />
            <el-table-column prop="total" label="总运力" :formatter="fmtNumber" />
            <el-table-column prop="avg" label="平均/周期" :formatter="fmtNumber" />
            <el-table-column prop="growth" label="首末年化增长" :formatter="fmtPct" width="130" />
          </el-table>
        </el-card>

        <el-card style="margin-top:12px;">
          <div slot="header" gap=10px class="card-header">操作</div>
          <div class="side-actions">
            <el-button class="side-action-btn" gap=10px size="small" type="warning" @click="resetResults" :disabled="!hasData">结果重置</el-button>
            <el-button class="side-action-btn" gap=10px size="small" type="primary" @click="exportData" :disabled="!hasData">数据导出</el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'

const granularity = ref('年度')
const years = ref(20) // 默认 1-20
const selectedClasses = ref(['large', 'medium', 'small'])
const viewMode = ref('aggregate') // aggregate/topn/heatmap
const topN = ref(10)
const loading = ref(false)

const chartRef = ref(null)
const controlsRef = ref(null)
let chartInstance = null
let ro = null

// backend data stores
const dataStore = reactive({ large: null, medium: null, small: null, _prepared: [] })
const labels = ref([])

// computed periods (总周期数) based on granularity & years
const periods = computed(() => {
  const y = Math.max(1, Math.min(20, Number(years.value) || 1))
  if (granularity.value === '年度') return y
  if (granularity.value === '季度') return y * 4
  return y * 12
})

// convenience
const hasData = computed(() => (dataStore._prepared && dataStore._prepared.length > 0))
const preparedCount = computed(() => dataStore._prepared ? dataStore._prepared.length : 0)

// 请求后端并解析兼容面板格式（保留向后端接口）
async function loadForecast() {
  if (!selectedClasses.value.length) {
    ElMessage.warning('请选择至少一种统计对象（大/中/小）')
    return
  }
  loading.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints?.PREDICT?.CAPACITY_FORECAST || apiConfig.endpoints?.PREDICT?.FORECAST || '/predict/capacity_forecast/')
    const payload = {
      classes: selectedClasses.value,
      granularity: granularity.value === '年度' ? 'yearly' : granularity.value === '季度' ? 'quarterly' : 'monthly',
      periods: periods.value
    }
    const res = await axios.post(url, payload, { timeout: 60000 })
    const resp = res.data && (res.data.data || res.data)
    parseBackend(resp)
    prepareVisualData()
    renderChart()
    nextTick(() => chartInstance?.resize())
  } catch (err) {
    console.error(err)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// parse backend (compatible with "panels" or "series")
function parseBackend(resp) {
  dataStore.large = dataStore.medium = dataStore.small = null
  labels.value = []

  if (!resp) return

  if (Array.isArray(resp.series) && resp.series.length) {
    resp.series.forEach(s => {
      const key = (s.cls || s.class || s.name || '').toLowerCase()
      const obj = { labels: s.labels || s.time || [], routes: s.routes || (s.data ? s.data.map(r => r.name) : []), data: s.values || s.data || [] }
      if (key.includes('large')) dataStore.large = obj
      else if (key.includes('medium')) dataStore.medium = obj
      else if (key.includes('small')) dataStore.small = obj
    })
    labels.value = dataStore.large?.labels || dataStore.medium?.labels || dataStore.small?.labels || genLabels()
    return
  }

  // panels: each panel may be 2D array or {headers, rows}
  const panels = ['large','medium','small']
  panels.forEach(k => {
    const panel = resp[k] || resp[k + '_panel'] || null
    if (!panel) return
    if (panel.headers && panel.rows) {
      const hdr = panel.headers
      labels.value = hdr.slice(1)
      const routes = panel.rows.map(r => r[0])
      const data = panel.rows.map(r => r.slice(1).map(v => Number(v) || 0))
      dataStore[k] = { labels: labels.value, routes, data }
      return
    }
    if (Array.isArray(panel) && panel.length > 1 && Array.isArray(panel[0])) {
      const hdr = panel[0]
      labels.value = hdr.slice(1)
      const rows = panel.slice(1)
      const routes = rows.map(r => r[0])
      const data = rows.map(r => r.slice(1).map(v => Number(v) || 0))
      dataStore[k] = { labels: labels.value, routes, data }
      return
    }
    // single aggregated series (small)
    if (Array.isArray(panel) && panel.length === periods.value) {
      labels.value = genLabels()
      dataStore[k] = { labels: labels.value, routes: ['合计'], data: [panel.map(v => Number(v) || 0)] }
      return
    }
  })

  if (!labels.value.length && resp.labels) labels.value = resp.labels
  if (!labels.value.length) labels.value = genLabels()
}

// prepare combined series used for visualization
function prepareVisualData() {
  if (!labels.value.length) labels.value = genLabels()
  function build(store, cls) {
    const out = []
    if (!store) return out
    const routes = store.routes || []
    const data = store.data || []
    for (let i = 0; i < routes.length; i++) out.push({ route: routes[i], values: data[i] || [], cls })
    return out
  }

  let combined = []
  if (selectedClasses.value.includes('large')) combined = combined.concat(build(dataStore.large, 'large'))
  if (selectedClasses.value.includes('medium')) combined = combined.concat(build(dataStore.medium, 'medium'))
  if (selectedClasses.value.includes('small')) combined = combined.concat(build(dataStore.small, 'small'))

  dataStore._prepared = combined
}

// render chart (aggregate / topn / heatmap)
function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()
  const prepared = dataStore._prepared || []
  if (!prepared.length) {
    chartInstance.setOption({ graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '暂无数据，请点击加载', fontSize: 14, fill: '#909399' } }] })
    return
  }

  if (viewMode.value === 'aggregate') {
    const sum = new Array(labels.value.length).fill(0)
    prepared.forEach(s => { for (let i=0;i<labels.value.length;i++) sum[i] += Number(s.values[i]) || 0 })
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length/12) } },
      yAxis: { type: 'value' },
      series: [{ name: '总运力', type: 'line', data: sum, smooth: true, areaStyle: { opacity: 0.2 } }]
    }, true)
    return
  }

  if (viewMode.value === 'topn') {
    const ranked = prepared.map(s => ({ ...s, total: (s.values||[]).reduce((a,b)=>a+(Number(b)||0),0) })).sort((a,b)=>b.total-a.total)
    const top = ranked.slice(0, topN.value || 10)
    const series = top.map(t => ({ name: t.route, type: 'line', data: t.values, smooth: true }))
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: series.map(s => s.name), type: 'scroll', bottom: 0 },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length/12) } },
      yAxis: { type: 'value' },
      series
    }, true)
    return
  }

  // heatmap
  if (viewMode.value === 'heatmap') {
    const rows = prepared
    const heatData = []
    for (let i=0;i<rows.length;i++){
      for (let j=0;j<labels.value.length;j++){
        heatData.push([j, i, Number(rows[i].values[j] || 0)])
      }
    }
    chartInstance.setOption({
      tooltip: { position: 'top', formatter: p => `时间: ${labels.value[p.value[0]]}<br/>航线: ${rows[p.value[1]].route}<br/>值: ${p.value[2]}` },
      grid: { left: 140, right: 60, bottom: 80, containLabel: true },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length/12) } },
      yAxis: { type: 'category', data: rows.map(r => r.route), axisLabel: { interval: 0 } },
      visualMap: { min: 0, max: Math.max(...heatData.map(d=>d[2]),1), calculable: true, orient:'vertical', right:10, top:'center' },
      series: [{ name:'heat', type:'heatmap', data:heatData, progressive:2000 }]
    }, true)
    return
  }
}

// helpers
function genLabels() {
  const cnt = periods.value
  const out = []
  const start = new Date().getFullYear()
  if (granularity.value === '年度') {
    for (let i=0;i<cnt;i++) out.push(String(start + i))
    return out
  }
  if (granularity.value === '季度') {
    for (let y=0;y<years.value;y++) {
      const yr = start + y
      for (let q=1;q<=4;q++) out.push(`${yr}-Q${q}`)
    }
    return out
  }
  for (let y=0;y<years.value;y++) {
    const yr = start + y
    for (let m=1;m<=12;m++) out.push(`${yr}-${String(m).padStart(2,'0')}`)
  }
  return out
}

function zoomToRecent() {
  if (!chartInstance || !labels.value.length) return
  const total = labels.value.length
  const start = Math.max(0, total - Math.min(48, total)) // 聚焦最近最多 48 点
  chartInstance.dispatchAction({ type: 'dataZoom', start: Math.round(start/total*100), end: 100 })
}
function resetChart() {
  if (!chartInstance) return
  chartInstance.clear()
  chartInstance.setOption({ graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '请选择条件并加载预测', fontSize: 14, fill: '#909399' } }] })
}

// 新增：重置结果（清空数据与图表）
function resetResults() {
  dataStore.large = dataStore.medium = dataStore.small = null
  dataStore._prepared = []
  labels.value = []
  if (chartInstance) {
    chartInstance.clear()
    chartInstance.setOption({ graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '结果已重置', fontSize: 14, fill: '#909399' } }] })
  }
  ElMessage.success('已重置结果')
}

// 新增：导出当前准备好的序列数据为 Excel（每行：route + 时间序列）
function exportData() {
  const prepared = dataStore._prepared || []
  if (!prepared.length) {
    ElMessage.info('无可导出数据')
    return
  }
  const header = ['route', ...labels.value]
  const rows = prepared.map(s => [s.route, ...(s.values || []).map(v => (v === null || v === undefined) ? '' : v)])
  const aoa = [header, ...rows]
  try {
    const ws = XLSX.utils.aoa_to_sheet(aoa)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'forecast')
    XLSX.writeFile(wb, `forecast_export_${granularity.value}_${years.value}y_${Date.now()}.xlsx`)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}

// summary table computed
const summaryTable = computed(() => {
  const rows = []
  const classes = { large: '大运量', medium: '中运量', small: '小运量(合计)' }
  selectedClasses.value.forEach(cls => {
    const store = dataStore[cls]
    if (!store) {
      rows.push({ classLabel: classes[cls], routeCount: 0, total: 0, avg: 0, growth: 0 })
      return
    }
    const routes = store.routes || []
    const data = store.data || []
    const periodsCnt = labels.value.length || periods.value
    // aggregate per-time
    const agg = new Array(periodsCnt).fill(0)
    data.forEach(arr => { for (let i=0;i<periodsCnt;i++) agg[i] += Number(arr[i] || 0) })
    const total = agg.reduce((s,v)=>s+v,0)
    const avg = periodsCnt ? total / periodsCnt : 0
    const first = agg[0] || 0
    const last = agg[agg.length-1] || 0
    const growth = first > 0 ? Math.pow(last/first || 1, 1/Math.max(1, years.value)) - 1 : (last>0 ? 1 : 0)
    rows.push({ classLabel: classes[cls], routeCount: routes.length, total, avg, growth })
  })
  return rows
}) 

// formatters
function fmtNumber(_, __, v) { return (v === null || v === undefined) ? '-' : Number(v).toLocaleString() }
function fmtPct(_, __, v) { return (v === null || v === undefined) ? '-' : (v*100).toFixed(2) + '%' }

onMounted(() => {
  // init chart
  setTimeout(() => {
    if (chartRef.value) {
      chartInstance = echarts.init(chartRef.value)
      chartInstance.setOption({ graphic: [{ type:'text', left:'center', top:'center', style:{ text:'请选择条件并加载预测', fontSize:14, fill:'#909399' }}] })
    }
  }, 50)

  // window resize handler (keep for compatibility)
  const onWinResize = () => chartInstance?.resize()
  window.addEventListener('resize', onWinResize)

  // ResizeObserver to detect chart container size change and call resize
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => {
      chartInstance?.resize()
    })
    // observe chart wrapper so that when layout stacks/changes size, chart resizes
    nextTick(() => {
      if (chartRef.value && chartRef.value.parentElement) ro.observe(chartRef.value.parentElement)
      if (controlsRef.value && controlsRef.value.parentElement) {
        // observe controls height changes to adjust layout if needed
        ro.observe(controlsRef.value.parentElement)
      }
    })
  }

  // cleanup on unmount
  onBeforeUnmount(() => {
    window.removeEventListener('resize', onWinResize)
    if (ro) {
      try { ro.disconnect() } catch (e) { /* ignore */ }
      ro = null
    }
  })
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.data-show-page {
  padding: 12px;
  width: 100%;
  box-sizing: border-box;
}

/* Controls */
.controls {
  background: #fff;
  padding: 12px;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  margin-bottom: 12px;
}

/* Content area fills remaining viewport height */
.content {
  display: flex;
  gap: 16px;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
  /* ensure content can grow vertically and use available viewport */
  min-height: calc(100vh - 200px);
}

/* Chart area should be responsive and flexible */
.chart-area-wrap {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.chart-area {
  width: 100%;
  flex: 1 1 auto;
  min-height: 320px;
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  box-sizing: border-box;
}

/* Side panel fixed width on wide screens, collapses on small screens */
.side-panel {
  width: 360px;
  flex: 0 0 360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* small helpers */
.small-help { color:#909399; font-size:12px; margin-left:6px }

/* layout for small screens: stack controls and panels */
@media (max-width: 1100px) {
  .content {
    flex-direction: column;
    min-height: auto;
  }
  .side-panel {
    width: 100%;
    flex: 0 0 auto;
  }
  .chart-area {
    min-height: 360px;
  }
}

/* very small screens adjustments */
@media (max-width: 640px) {
  .controls .el-col { width: 100% !important; display: block; margin-bottom: 8px; }
  .chart-area { min-height: 320px; padding: 6px; }
  .side-panel { padding-bottom: 8px; }
}

/* align side action buttons full width and flush left */
.side-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
  padding: 0; /* ensure no extra inset */
}
.side-actions .side-action-btn,
.side-actions .el-button {
  width: 100%;
  margin: 0;
  max-width: none;
  box-sizing: border-box;
  text-align: center;
}

/* ensure el-card header style consistent */
.card-header { font-weight:600; color:#333 }
.btn-col { display:flex; align-items:center; justify-content:flex-end }
</style>