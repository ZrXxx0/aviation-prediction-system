<template>
  <div class="data-show-page">
    <div class="controls">
      <el-row :gutter="12" align="middle">
        <el-col :span="5">
          <el-select v-model="granularity" placeholder="选择粒度" clearable style="width:100%">
            <el-option label="月度" value="月度" />
            <el-option label="季度" value="季度" />
            <el-option label="年度" value="年度" />
          </el-select>
        </el-col>

        <el-col :span="6">
          <el-radio-group v-model="dataset" size="small">
            <el-radio-button label="large">大运量 (100)</el-radio-button>
            <el-radio-button label="medium">中运量 (400)</el-radio-button>
            <el-radio-button label="small">小运量 (合计)</el-radio-button>
            <el-radio-button label="all">全部</el-radio-button>
          </el-radio-group>
        </el-col>

        <el-col :span="6">
          <el-select v-model="viewMode" style="width:100%">
            <el-option label="聚合总量 (总和 / 堆叠)" value="aggregate" />
            <el-option label="Top-N 单航线 (按总量排序)" value="topn" />
            <el-option label="热力图 (航线 × 时间)" value="heatmap" />
            <el-option label="表格 (分页)" value="table" />
          </el-select>
        </el-col>

        <el-col :span="3" v-if="viewMode === 'topn'">
          <el-input-number v-model="topN" :min="1" :max="50" controls-position="right" style="width:100%" />
        </el-col>

        <el-col :span="2">
          <el-button type="primary" @click="loadForecast" :loading="loading">加载预测</el-button>
        </el-col>

        <el-col :span="2">
          <el-button @click="exportCsv" :disabled="!hasData">导出</el-button>
        </el-col>
      </el-row>
    </div>

    <div class="visuals">
      <div class="left-panel">
        <div class="chart-card">
          <div ref="chartRef" class="chart-area"></div>
        </div>
      </div>

      <div class="right-panel">
        <el-card>
          <div slot="header" class="card-header">
            <span>汇总统计 (未来20年)</span>
          </div>

          <el-table :data="summaryTable" stripe style="width:100%">
            <el-table-column prop="classLabel" label="等级" width="140" />
            <el-table-column prop="route" label="航线 / 描述" min-width="160" />
            <el-table-column prop="total" label="总运力合计" :formatter="fmtNumber" />
            <el-table-column prop="avg" label="平均/周期" :formatter="fmtNumber" />
            <el-table-column prop="first" label="首值" :formatter="fmtNumber" />
            <el-table-column prop="last" label="末值" :formatter="fmtNumber" />
          </el-table>

          <div style="margin-top:12px;">
            <el-collapse>
              <el-collapse-item title="展示说明" name="1">
                - 聚合: 显示所选类别的时间序列总和或堆叠图。  
                - Top-N: 按时间序列总和降序，默认显示 Top 10（可调整）。  
                - 热力图: 航线（行）× 时间（列），适合大量航线概览。  
                - 表格: 按航线列出完整序列，支持分页导出。
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-card>

        <el-card style="margin-top:12px;">
          <div slot="header" class="card-header">路由筛选 / 导出</div>
          <div style="margin-bottom:8px;">
            <el-input v-model="routeFilter" placeholder="按航线名筛选" clearable @input="applyRouteFilter" />
          </div>
          <div style="display:flex; gap:8px; align-items:center;">
            <el-button size="small" @click="showAllRoutes">显示所有路由</el-button>
            <el-button size="small" @click="collapseAll">折叠图例</el-button>
            <el-button size="small" @click="resetZoom">重置缩放</el-button>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 表格分页弹窗（当 viewMode=table 时） -->
    <el-dialog v-model="tableDialogVisible" width="80%" title="航线时间序列表">
      <el-table
        :data="pagedTableData"
        stripe
        style="width:100%"
      >
        <el-table-column prop="route" label="航线" width="220" />
        <el-table-column
          v-for="(lbl, idx) in labelSample"
          :key="idx"
          :prop="`v_${idx}`"
          :label="lbl"
          min-width="100"
        />
      </el-table>

      <div style="display:flex; justify-content:space-between; align-items:center; margin-top:12px;">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :total="tableData.length"
          :page-size="pageSize"
          :current-page.sync="currentPage"
          @size-change="onPageSizeChange"
        />
        <div>
          <el-button @click="downloadTableCsv" :disabled="!tableData.length">导出当前表格</el-button>
          <el-button @click="tableDialogVisible = false">关闭</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'

// 状态
const granularity = ref('月度')
const dataset = ref('large') // large / medium / small / all
const viewMode = ref('aggregate') // aggregate / topn / heatmap / table
const topN = ref(10)
const loading = ref(false)

const chartRef = ref(null)
let chartInstance = null

// 原始数据结构： { large: {routes: [...], labels: [...] , data: [[...],...]}, medium:..., small: { ... single aggregate ... } }
const dataStore = reactive({ large: null, medium: null, small: null })
const labels = ref([])

// 筛选/表格
const routeFilter = ref('')
const tableDialogVisible = ref(false)
const tableData = ref([]) // [{route, values:[]}, ...]
const pageSize = ref(20)
const currentPage = ref(1)

// 计算
const hasData = computed(() => {
  return !!(labels.value.length && (arrayLength(dataStore.large) || arrayLength(dataStore.medium) || arrayLength(dataStore.small)))
})
function arrayLength(d) {
  if (!d) return 0
  if (d.routes) return d.routes.length
  if (Array.isArray(d)) return d.length
  return 0
}

const classLabelMap = { large: '大运量', medium: '中运量', small: '小运量(合计)' }

const labelSample = computed(() => labels.value.slice(0, Math.min(12, labels.value.length)))

// 加载接口并解析后端返回的“面板”格式
async function loadForecast() {
  if (!granularity.value) {
    ElMessage.warning('请选择粒度')
    return
  }
  loading.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints?.PREDICT?.CAPACITY_FORECAST || apiConfig.endpoints?.PREDICT?.FORECAST || '/predict/capacity_forecast/')
    const payload = {
      granularity: granularity.value === '年度' ? 'yearly' : granularity.value === '季度' ? 'quarterly' : 'monthly',
      periods: granularity.value === '年度' ? 20 : granularity.value === '季度' ? 80 : 240
    }
    const res = await axios.post(url, payload, { timeout: 60000 })
    const resp = res.data && (res.data.data || res.data)
    // 兼容两种后端返回格式：
    // 1) series: [{cls:'large', labels:[], routes:[], data: [[...],[...]]}, ...]
    // 2) panels: {large: table-like, medium: table-like, small: table-like}
    parseBackend(resp)
    prepareVisualData()
    renderChart()
  } catch (err) {
    console.error(err)
    ElMessage.error('加载预测失败')
  } finally {
    loading.value = false
  }
}

// 解析后端返回，尽量通用
function parseBackend(resp) {
  // reset
  dataStore.large = dataStore.medium = dataStore.small = null
  labels.value = []

  if (!resp) return

  // 优先支持 resp.series 格式
  if (Array.isArray(resp.series) && resp.series.length) {
    resp.series.forEach(s => {
      const key = (s.cls || s.class || s.name || '').toLowerCase()
      const obj = { labels: s.labels || s.time || [], routes: s.routes || (s.data ? s.data.map(r => r.name) : []), data: s.values || s.data || [] }
      if (key.includes('large')) dataStore.large = obj
      else if (key.includes('medium')) dataStore.medium = obj
      else if (key.includes('small')) dataStore.small = obj
    })
    // choose labels from any available
    labels.value = (dataStore.large?.labels || dataStore.medium?.labels || dataStore.small?.labels || [])
    return
  }

  // 如果是按面板返回（表格形式）：每个面板可能是二维 array，首行为日期，首列为航线名
  const panels = ['large','medium','small']
  panels.forEach(k => {
    const panel = resp[k] || resp[k + '_panel'] || null
    if (!panel) return
    // panel could be: { headers: [...], rows: [[route, v1, v2...], ...] } or 2D array
    if (panel.headers && panel.rows) {
      const hdr = panel.headers
      labels.value = hdr.slice(1)
      const routes = panel.rows.map(r => r[0])
      const data = panel.rows.map(r => r.slice(1).map(v => Number(v) || 0))
      dataStore[k] = { labels: labels.value, routes, data }
      return
    }
    if (Array.isArray(panel) && panel.length > 1 && Array.isArray(panel[0])) {
      // first row as header (dates), subsequent rows: [route, ...values]
      const hdr = panel[0]
      labels.value = hdr.slice(1)
      const rows = panel.slice(1)
      const routes = rows.map(r => r[0])
      const data = rows.map(r => r.slice(1).map(v => Number(v) || 0))
      dataStore[k] = { labels: labels.value, routes, data }
      return
    }
    // 如果是已经聚合成单列数组（small），支持直接数组
    if (Array.isArray(panel)) {
      // if length matches periods, treat as aggregate single series
      if (panel.length && (panel.length === (granularity.value === '年度' ? 20 : granularity.value === '季度' ? 80 : 240))) {
        labels.value = genLabels(granularity.value)
        dataStore[k] = { labels: labels.value, routes: ['合计'], data: [panel.map(v => Number(v) || 0)] }
        return
      }
    }
  })

  // fallback: if resp has labels and large/medium small as series arrays
  if (!labels.value.length && resp.labels && Array.isArray(resp.labels)) labels.value = resp.labels
  if (!dataStore.large && resp.large && resp.large.data) dataStore.large = resp.large
  if (!dataStore.medium && resp.medium && resp.medium.data) dataStore.medium = resp.medium
  if (!dataStore.small && resp.small && resp.small.data) dataStore.small = resp.small
}

// 根据当前 dataset/viewMode 组织图表数据
function prepareVisualData() {
  // ensure labels exists
  if (!labels.value.length) labels.value = genLabels(granularity.value)

  // helper to build series objects
  function buildSeriesFromStore(store, cls) {
    const out = []
    if (!store) return out
    const routes = store.routes || []
    const data = store.data || []
    for (let i = 0; i < routes.length; i++) {
      out.push({ route: routes[i], values: data[i] || [], cls })
    }
    return out
  }

  let combined = []
  if (dataset.value === 'all') {
    combined = [
      ...buildSeriesFromStore(dataStore.large, 'large'),
      ...buildSeriesFromStore(dataStore.medium, 'medium'),
      ...buildSeriesFromStore(dataStore.small, 'small')
    ]
  } else {
    combined = buildSeriesFromStore(dataStore[dataset.value], dataset.value)
  }

  // apply filter
  if (routeFilter.value) {
    combined = combined.filter(r => r.route && r.route.includes(routeFilter.value))
  }

  // save tableData used by table view
  tableData.value = combined.map(r => ({ route: r.route, values: r.values }))
  // compute summaryTable
  // attach to reactive store for renderChart use
  dataStore._prepared = combined
}

// 渲染图表（根据 viewMode）
function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()

  const prepared = dataStore._prepared || []
  if (!prepared.length) {
    chartInstance.setOption({
      graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '暂无可展示数据', fontSize: 14, fill: '#909399' } }]
    })
    return
  }

  // AGGREGATE: sum across routes, optionally stacked area per-class if dataset=all
  if (viewMode.value === 'aggregate') {
    if (dataset.value === 'all') {
      // group by cls and sum series
      const groups = { large: null, medium: null, small: null }
      prepared.forEach(s => {
        const arr = s.values || []
        if (!groups[s.cls]) groups[s.cls] = new Array(labels.value.length).fill(0)
        for (let i = 0; i < labels.value.length; i++) groups[s.cls][i] = (groups[s.cls][i] || 0) + (Number(arr[i]) || 0)
      })
      const series = Object.keys(groups).filter(k => groups[k]).map(k => ({
        name: classLabelMap[k],
        type: 'line',
        stack: 'total',
        areaStyle: {},
        data: groups[k],
        smooth: true
      }))
      chartInstance.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: series.map(s => s.name) },
        xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length / 12) } },
        yAxis: { type: 'value' },
        series
      }, true)
      return
    }
    // single dataset aggregate: sum all selected routes
    const sum = new Array(labels.value.length).fill(0)
    prepared.forEach(s => {
      for (let i = 0; i < labels.value.length; i++) sum[i] += Number(s.values[i]) || 0
    })
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: [classLabelMap[dataset.value]] },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length / 12) } },
      yAxis: { type: 'value' },
      series: [{
        name: classLabelMap[dataset.value],
        type: 'line',
        data: sum,
        smooth: true,
        areaStyle: { opacity: 0.25 }
      }]
    }, true)
    return
  }

  // TOP-N: show top N routes by total sum
  if (viewMode.value === 'topn') {
    const ranked = prepared.map(s => ({ ...s, total: (s.values || []).reduce((a, b) => a + (Number(b) || 0), 0) }))
      .sort((a, b) => b.total - a.total)
    const top = ranked.slice(0, topN.value || 10)
    const series = top.map(s => ({ name: s.route, type: 'line', data: s.values, smooth: true, lineStyle: { width: 1.5 } }))
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: series.map(s => s.name), type: 'scroll', bottom: 0 },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length / 12) } },
      yAxis: { type: 'value' },
      series
    }, true)
    return
  }

  // HEATMAP: route × time matrix (suitable for many routes)
  if (viewMode.value === 'heatmap') {
    // prepare matrix: rows = routes, cols = time
    const rows = prepared
    const heatData = []
    for (let i = 0; i < rows.length; i++) {
      const vals = rows[i].values || []
      for (let j = 0; j < labels.value.length; j++) {
        heatData.push([j, i, Number(vals[j] || 0)])
      }
    }
    const option = {
      tooltip: { position: 'top', formatter: params => `时间: ${labels.value[params.value[0]]}<br/>航线: ${rows[params.value[1]].route}<br/>值: ${params.value[2]}` },
      grid: { left: 120, right: 80, bottom: 80, containLabel: true },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length / 12) } },
      yAxis: { type: 'category', data: rows.map(r => r.route), axisLabel: { interval: 0 } },
      visualMap: { min: 0, max: Math.max(...heatData.map(d => d[2]), 1), calculable: true, orient: 'vertical', right: 10, top: 'center' },
      series: [{
        name: 'heat',
        type: 'heatmap',
        data: heatData,
        progressive: 2000,
        emphasis: { itemStyle: { borderColor: '#333', borderWidth: 1 } }
      }]
    }
    chartInstance.setOption(option, true)
    return
  }

  // TABLE mode opens dialog with pagedTableData
  if (viewMode.value === 'table') {
    // prepare tableData and open dialog
    tableDialogVisible.value = true
    return
  }
}

// 辅助：生成标签（和之前逻辑一致）
function periodsByGranularity(g) {
  if (g === '年度') return 20
  if (g === '季度') return 20 * 4
  return 20 * 12
}
function genLabels(g) {
  const now = new Date()
  const startYear = now.getFullYear()
  const periodCount = periodsByGranularity(g)
  const out = []
  if (g === '年度') {
    for (let i = 0; i < periodCount; i++) out.push(String(startYear + i))
    return out
  }
  if (g === '季度') {
    for (let y = 0; y < 20; y++) {
      const year = startYear + y
      for (let q = 1; q <= 4; q++) out.push(`${year}-Q${q}`)
    }
    return out
  }
  for (let y = 0; y < 20; y++) {
    const year = startYear + y
    for (let m = 1; m <= 12; m++) out.push(`${year}-${String(m).padStart(2,'0')}`)
  }
  return out
}

// 表格分页相关
const pagedTableData = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const slice = tableData.value.slice(start, start + pageSize.value)
  // transform to objects with v_0..v_n for el-table columns
  return slice.map(row => {
    const obj = { route: row.route }
    for (let i = 0; i < Math.min(12, labels.value.length); i++) {
      obj[`v_${i}`] = (row.values && row.values[i] !== undefined) ? row.values[i] : ''
    }
    return obj
  })
})
function onPageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
}
function downloadTableCsv() {
  if (!tableData.value.length) return
  const header = ['route', ...labels.value]
  const rows = tableData.value.map(r => [r.route, ...(r.values || [])])
  const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'table')
  XLSX.writeFile(wb, `routes_table_${new Date().getTime()}.xlsx`)
}

// 导出当前可见图表数据（按 labels）
function exportCsv() {
  if (!hasData.value) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  // export labels + top selected series or aggregate
  if (viewMode.value === 'aggregate') {
    // export totals per time
    const prepared = dataStore._prepared || []
    const sum = new Array(labels.value.length).fill(0)
    prepared.forEach(s => { for (let i=0;i<labels.value.length;i++) sum[i] += Number(s.values[i]||0) })
    const header = ['time', 'total']
    const rows = labels.value.map((t, idx) => [t, sum[idx]])
    const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'aggregate')
    XLSX.writeFile(wb, `aggregate_${new Date().getTime()}.xlsx`)
    return
  }
  // topn or heatmap or table: export tableData
  const header = ['route', ...labels.value]
  const rows = tableData.value.map(r => [r.route, ...(r.values || [])])
  const ws = XLSX.utils.aoa_to_sheet([header, ...rows])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'series')
  XLSX.writeFile(wb, `series_${new Date().getTime()}.xlsx`)
}

// 小工具
function applyRouteFilter() {
  prepareVisualData()
  renderChart()
}
function showAllRoutes() {
  routeFilter.value = ''
  prepareVisualData()
  renderChart()
}
function collapseAll() {
  chartInstance && chartInstance.dispatchAction({ type: 'legendUnSelectAll' })
}
function resetZoom() {
  chartInstance && chartInstance.dispatchAction({ type: 'dataZoom', start: 0, end: 100 })
}

const summaryTable = computed(() => {
  const rows = []
  const prepared = dataStore._prepared || []
  prepared.forEach(s => {
    const total = (s.values || []).reduce((a, b) => a + (Number(b) || 0), 0)
    const avg = (labels.value.length ? total / labels.value.length : 0)
    rows.push({
      classLabel: classLabelMap[s.cls] || s.cls || '',
      route: s.route,
      total, avg,
      first: (s.values && s.values.length) ? s.values[0] : null,
      last: (s.values && s.values.length) ? s.values[s.values.length - 1] : null
    })
  })
  // for compactness show only top lines in summary; sort by total desc
  return rows.sort((a,b) => b.total - a.total).slice(0, 50)
})

function fmtNumber(row, column, cellValue) {
  if (cellValue === null || cellValue === undefined) return '-'
  return Number(cellValue).toLocaleString()
}

onMounted(() => {
  chartInstance = null
  setTimeout(() => {
    if (chartRef.value) {
      chartInstance = echarts.init(chartRef.value)
      chartInstance.setOption({ graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '请选择参数并加载预测', fontSize: 14, fill: '#909399' } }] })
    }
  }, 50)
  window.addEventListener('resize', () => chartInstance?.resize())
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.data-show-page { padding: 16px 24px; max-width: 1400px; margin: 0 auto; }
.controls { margin-bottom: 12px; background: #fff; padding: 12px; border-radius: 6px; box-shadow: 0 1px 6px rgba(0,0,0,0.04); }
.visuals { display:flex; gap:16px; align-items:flex-start }
.left-panel { flex: 2; }
.right-panel { width: 420px; flex: 0 0 420px; }
.chart-card { background: #fff; border-radius: 6px; padding: 12px; box-shadow: 0 1px 6px rgba(0,0,0,0.04); min-height: 520px; }
.chart-area { height: 520px; width: 100%; }
.card-header { font-weight: 600; color: #333; }
</style>