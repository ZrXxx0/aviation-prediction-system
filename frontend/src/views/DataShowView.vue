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
            placeholder="年数 (1 - 20)"
          />
        </el-col>

        <el-col :span="7">
          <el-checkbox-group v-model="selectedClasses" style="display:flex; gap:8px;">
            <el-checkbox label="large">大运量（100条）</el-checkbox>
            <el-checkbox label="medium">中运量（400条）</el-checkbox>
            <el-checkbox label="small">小运量(加总)</el-checkbox>
          </el-checkbox-group>
        </el-col>

        <el-col :span="4">
          <el-select v-model="viewMode" style="width:100%">
            <el-option label="表格视图" value="table" />
            <el-option label="聚合总量" value="aggregate" />
            <el-option label="热力图" value="heatmap" />
          </el-select>
        </el-col>

        <el-col :span="2" class="btn-col">
          <!-- 点击加载时使用内部静态数据假装后端返回；已保留注释的真实请求示例 -->
          <el-button type="primary" @click="loadForecast" :loading="loading">加载</el-button>
        </el-col>
      </el-row>

      <el-row style="margin-top:10px;" align="middle">
        <el-col :span="18">
          <div class="small-help">说明：长度按“年”计（最大 20 年）；视图包括：表格/聚合/热力图展示</div>
        </el-col>
      </el-row>
    </div>

    <!-- Main content -->
    <div class="content">
      <div class="chart-area-wrap">
        <!-- 表格视图 -->
        <div
          v-if="viewMode === 'table'"
          class="table-wrap draggable"
          ref="tableWrapRef"
          :style="{ overflow: 'auto' }"
        >
          <!-- inner container enforces wide min-width so horizontal scrollbar appears when needed -->
          <div class="table-inner" :style="{ minWidth: tableMinWidth }">
            <el-table
              :data="panelRows"
              stripe
              size="small"
              style="width:100%;"
              :max-height="520"
              v-loading="loading"
            >
              <el-table-column prop="route" label="预测结果" min-width="120" fixed />
              <el-table-column
                v-for="col in tableColumns"
                :key="col.key"
                :prop="col.key"
                :label="col.label"
                :min-width="90"
              />
            </el-table>
          </div>
        </div>

        <!-- 图表区域（聚合/热力） -->
        <div
          v-show="viewMode !== 'table'"
          ref="chartRef"
          class="chart-area draggable"
          :style="{ overflow: 'auto', minWidth: chartMinWidth }"
        ></div>
      </div>

      <div class="side-panel">
        <el-card>
          <template #header>
            <div class="card-header">关键统计</div>
          </template>
          <el-descriptions column="1" border>
            <el-descriptions-item label="选择粒度">{{ granularity }}</el-descriptions-item>
            <el-descriptions-item label="长度（年）">{{ years }}</el-descriptions-item>
            <el-descriptions-item label="周期数">{{ periods }}</el-descriptions-item>
            <el-descriptions-item label="总计算航线数">{{ preparedCount }}</el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card style="margin-top:12px;">
          <template #header>
            <div class="card-header">汇总统计</div>
          </template>
          <el-table :data="summaryTable" stripe size="small" style="width:100%">
            <el-table-column prop="classLabel" label="类别" width="100" />
            <el-table-column prop="total" label="总运力" :formatter="fmtNumber" />
            <el-table-column prop="avg" label="平均/周期" :formatter="fmtNumber" />
            <el-table-column prop="growth" label="年化增长" :formatter="fmtPct" width="130" />
          </el-table>
        </el-card>

        <el-card style="margin-top:12px;">
          <template #header>
            <div class="card-header">操作</div>
          </template>
          <div class="side-actions">
            <el-button class="side-action-btn" size="small" type="warning" @click="resetResults" :disabled="!hasData">结果重置</el-button>
            <el-button class="side-action-btn" size="small" type="primary" @click="exportData" :disabled="!hasData">数据导出</el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios' // 保留：切换到后端时可以使用
import apiConfig from '@/config/api.js' // 保留：示例（未必立即使用）
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'

const granularity = ref('年度')
const years = ref(10)
const selectedClasses = ref(['large', 'medium', 'small'])
const viewMode = ref('table') // 默认表格
const loading = ref(false)

const chartRef = ref(null)
const tableWrapRef = ref(null)
let chartInstance = null
let ro = null

// 存储解析后的数据
const dataStore = reactive({ large: null, medium: null, small: null, _prepared: [] })
const labels = ref([])

const periods = computed(() => {
  const y = Math.max(1, Math.min(20, Number(years.value) || 1))
  if (granularity.value === '年度') return y
  if (granularity.value === '季度') return y * 4
  return y * 12
})

const hasData = computed(() => (Array.isArray(dataStore._prepared) && dataStore._prepared.length > 0))
const preparedCount = computed(() => (Array.isArray(dataStore._prepared) ? dataStore._prepared.length : 0))

/**
 * loadForecast
 * - 内部使用静态数据模拟后端返回（写在此函数内）
 * - 同时保留了被注释的真实请求示例，切换到真实后端时取消注释并调整 apiConfig
 */
async function loadForecast() {
  if (!selectedClasses.value.length) {
    ElMessage.warning('请选择至少一种统计对象（大/中/小）')
    return
  }
  loading.value = true
  try {
    // ======= 真实后端请求示例（注释） =======
    // const url = apiConfig.getUrl(apiConfig.endpoints?.PREDICT?.CAPACITY_FORECAST)
    // const payload = {
    //   classes: selectedClasses.value,
    //   granularity: granularity.value === '年度' ? 'yearly' : granularity.value === '季度' ? 'quarterly' : 'monthly',
    //   periods: periods.value
    // }
    // const res = await axios.post(url, payload, { timeout: 60000 })
    // const resp = res.data && (res.data.data || res.data)
    // parseBackend(resp)
    // =========================================

    // ======= 本地静态 mock（用于前端调试） =======
    const mock = (() => {
      const y = new Date().getFullYear()
      const months = []
      for (let m = 1; m <= 12; m++) months.push(`${y}-${String(m).padStart(2, '0')}`)
      return {
        panels: {
          large: {
            headers: ['route', ...months],
            rows: [
              ['SHA-PEK', 1200,1300,1250,1400,1500,1600,1550,1620,1580,1700,1680,1750],
              ['PVG-CAN', 900,920,880,950,1000,1020,1010,1050,1030,1100,1080,1120]
            ]
          },
          medium: {
            headers: ['route', ...months],
            rows: [
              ['SHA-CTU', 420,430,410,450,480,500,495,510,505,520,515,530],
              ['PEK-KMG', 360,370,350,380,400,410,405,420,415,430,425,440]
            ]
          },
          small: {
            headers: ['route', ...months],
            rows: [
              ['小运力（加总）', 2400,2500,2450,2600,2700,2800,2755,2870,2820,2950,2900,3020]
            ]
          }
        }
      }
    })()

    // parse mock panels (直接把 mock 放在调用处，满足“点击加载后使用内部静态数据”的要求)
    parseBackend({
      large: mock.panels.large,
      medium: mock.panels.medium,
      small: mock.panels.small
    })
    prepareVisualData()
    // 根据选择视图渲染图或展示表格
    if (viewMode.value !== 'table') renderChart()
    nextTick(() => chartInstance?.resize())
    ElMessage.success('预测数据加载成功')
  } catch (err) {
    console.error(err)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 解析后端（兼容 panels / series）
// 添加更严格的类型判断以避免 labels 被设置成非数组（导致 template 中 .map 报错）
function parseBackend(resp) {
  dataStore.large = dataStore.medium = dataStore.small = null
  labels.value = []

  if (!resp) return

  if (Array.isArray(resp.series) && resp.series.length) {
    resp.series.forEach(s => {
      const key = (s.cls || s.class || s.name || '').toLowerCase()
      const obj = {
        labels: Array.isArray(s.labels) ? s.labels.slice() : (Array.isArray(s.time) ? s.time.slice() : []),
        routes: Array.isArray(s.routes) ? s.routes.slice() : (Array.isArray(s.data) ? s.data.map(r => r.name) : []),
        data: Array.isArray(s.values) ? s.values.slice() : (Array.isArray(s.data) ? s.data.slice() : [])
      }
      if (key.includes('large')) dataStore.large = obj
      else if (key.includes('medium')) dataStore.medium = obj
      else if (key.includes('small')) dataStore.small = obj
    })
    labels.value = Array.isArray(dataStore.large?.labels) ? dataStore.large.labels.slice()
      : Array.isArray(dataStore.medium?.labels) ? dataStore.medium.labels.slice()
      : Array.isArray(dataStore.small?.labels) ? dataStore.small.labels.slice()
      : genLabels()
    return
  }

  const panels = ['large','medium','small']
  panels.forEach(k => {
    const panel = resp[k] || resp[k + '_panel'] || null
    if (!panel) return
    if (panel.headers && panel.rows && Array.isArray(panel.rows)) {
      const hdr = Array.isArray(panel.headers) ? panel.headers.slice() : []
      labels.value = Array.isArray(hdr) ? hdr.slice(1) : genLabels()
      const routes = panel.rows.map(r => r[0])
      const data = panel.rows.map(r => (Array.isArray(r) ? r.slice(1).map(v => Number(v) || 0) : []))
      dataStore[k] = { labels: labels.value.slice(), routes, data }
      return
    }
    if (Array.isArray(panel) && panel.length > 1 && Array.isArray(panel[0])) {
      const hdr = panel[0]
      labels.value = Array.isArray(hdr) ? hdr.slice(1) : genLabels()
      const rows = panel.slice(1)
      const routes = rows.map(r => r[0])
      const data = rows.map(r => r.slice(1).map(v => Number(v) || 0))
      dataStore[k] = { labels: labels.value.slice(), routes, data }
      return
    }
    if (Array.isArray(panel) && panel.length === periods.value) {
      labels.value = genLabels()
      dataStore[k] = { labels: labels.value.slice(), routes: ['合计'], data: [panel.map(v => Number(v) || 0)] }
      return
    }
  })

  if (!Array.isArray(labels.value) || !labels.value.length) {
    if (Array.isArray(resp.labels)) labels.value = resp.labels.slice()
    else labels.value = genLabels()
  }
}

function prepareVisualData() {
  if (!Array.isArray(labels.value) || !labels.value.length) labels.value = genLabels()
  const build = (store, cls) => {
    const out = []
    if (!store) return out
    const routes = Array.isArray(store.routes) ? store.routes : []
    const data = Array.isArray(store.data) ? store.data : []
    for (let i = 0; i < routes.length; i++) out.push({ route: routes[i], values: data[i] || [], cls })
    return out
  }

  let combined = []
  if (selectedClasses.value.includes('large')) combined = combined.concat(build(dataStore.large, 'large'))
  if (selectedClasses.value.includes('medium')) combined = combined.concat(build(dataStore.medium, 'medium'))
  if (selectedClasses.value.includes('small')) combined = combined.concat(build(dataStore.small, 'small'))

  dataStore._prepared = Array.isArray(combined) ? combined : []
}

function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()
  const prepared = Array.isArray(dataStore._prepared) ? dataStore._prepared : []
  if (!prepared.length) {
    chartInstance.setOption({ graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '暂无数据，请点击加载', fontSize: 22, fill: '#909399' } }] })
    return
  }

  if (viewMode.value === 'aggregate') {
    const sum = new Array(labels.value.length).fill(0)
    prepared.forEach(s => { for (let i=0;i<labels.value.length;i++) sum[i] += Number((s.values || [])[i]) || 0 })
    chartInstance.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: labels.value, axisLabel: { interval: Math.ceil(labels.value.length/12) } },
      yAxis: { type: 'value' },
      series: [{ name: '总运力', type: 'line', data: sum, smooth: true, areaStyle: { opacity: 0.18 } }]
    }, true)
    return
  }

  if (viewMode.value === 'heatmap') {
    const rows = prepared
    const heatData = []
    for (let i=0;i<rows.length;i++){
      for (let j=0;j<labels.value.length;j++){
        heatData.push([j, i, Number((rows[i].values || [])[j] || 0)])
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

function exportData() {
  const prepared = Array.isArray(dataStore._prepared) ? dataStore._prepared : []
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

// 表格列与行（用于表格视图）
// 增加类型守护，避免 labels 被误设置成非数组导致 .map 报错
const tableColumns = computed(() => {
  if (!Array.isArray(labels.value)) return []
  return labels.value.map(l => ({ key: l, label: l }))
})
const panelRows = computed(() => {
  const prepared = Array.isArray(dataStore._prepared) ? dataStore._prepared : []
  if (!prepared.length) return []
  const cols = Array.isArray(labels.value) ? labels.value : []
  return prepared.map(s => {
    const obj = { route: s.route }
    cols.forEach((l, idx) => { obj[l] = (s.values && s.values[idx] != null) ? s.values[idx] : 0 })
    return obj
  })
})

// 表格/图表 最小宽度：根据列数动态计算，保证足够宽度以触发横向滚动
const tableMinWidth = computed(() => {
  const cols = Array.isArray(labels.value) ? labels.value.length : 0
  // 基础宽度 + 每列宽度
  const base = 200 // route + padding
  const per = 100
  const w = Math.max(800, base + cols * per)
  return w + 'px'
})
const chartMinWidth = computed(() => {
  const points = Array.isArray(labels.value) ? labels.value.length : 12
  const per = 80
  const w = Math.max(800, points * per)
  return w + 'px'
})

// summary table
const summaryTable = computed(() => {
  const rows = []
  const classes = { large: '大运量', medium: '中运量', small: '小运量(加总)' }
  selectedClasses.value.forEach(cls => {
    const store = dataStore[cls]
    if (!store) {
      rows.push({ classLabel: classes[cls], routeCount: 0, total: 0, avg: 0, growth: 0 })
      return
    }
    const routes = Array.isArray(store.routes) ? store.routes : []
    const data = Array.isArray(store.data) ? store.data : []
    const periodsCnt = Array.isArray(labels.value) && labels.value.length ? labels.value.length : periods.value
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

function fmtNumber(_, __, v) { return (v === null || v === undefined) ? '-' : Number(v).toLocaleString() }
function fmtPct(_, __, v) { return (v === null || v === undefined) ? '-' : (v*100).toFixed(2) + '%' }

// DRAG-TO-SCROLL 支持：返回 cleanup 函数
function enableDragScroll(el) {
  if (!el) return () => {}
  let isDown = false
  let startX = 0
  let startY = 0
  let scrollLeft = 0
  let scrollTop = 0

  const onMouseDown = (e) => {
    // only left button
    if (e.button !== undefined && e.button !== 0) return
    isDown = true
    el.classList.add('dragging')
    startX = e.pageX - el.offsetLeft
    startY = e.pageY - el.offsetTop
    scrollLeft = el.scrollLeft
    scrollTop = el.scrollTop
    // prevent text selection
    document.body.style.userSelect = 'none'
  }
  const onMouseMove = (e) => {
    if (!isDown) return
    const x = e.pageX - el.offsetLeft
    const y = e.pageY - el.offsetTop
    const walkX = x - startX
    const walkY = y - startY
    el.scrollLeft = scrollLeft - walkX
    el.scrollTop = scrollTop - walkY
  }
  const onMouseUp = () => {
    if (!isDown) return
    isDown = false
    el.classList.remove('dragging')
    document.body.style.userSelect = ''
  }

  const onTouchStart = (e) => {
    isDown = true
    el.classList.add('dragging')
    const t = e.touches[0]
    startX = t.pageX - el.offsetLeft
    startY = t.pageY - el.offsetTop
    scrollLeft = el.scrollLeft
    scrollTop = el.scrollTop
  }
  const onTouchMove = (e) => {
    if (!isDown) return
    const t = e.touches[0]
    const x = t.pageX - el.offsetLeft
    const y = t.pageY - el.offsetTop
    const walkX = x - startX
    const walkY = y - startY
    el.scrollLeft = scrollLeft - walkX
    el.scrollTop = scrollTop - walkY
  }
  const onTouchEnd = () => {
    if (!isDown) return
    isDown = false
    el.classList.remove('dragging')
  }

  // Wheel with shift to scroll horizontally (default behavior exists) - keep native
  el.addEventListener('mousedown', onMouseDown, { passive: true })
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  window.addEventListener('mouseup', onMouseUp, { passive: true })
  el.addEventListener('touchstart', onTouchStart, { passive: false })
  el.addEventListener('touchmove', onTouchMove, { passive: false })
  el.addEventListener('touchend', onTouchEnd, { passive: true })
  // return cleanup
  return () => {
    el.removeEventListener('mousedown', onMouseDown)
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseup', onMouseUp)
    el.removeEventListener('touchstart', onTouchStart)
    el.removeEventListener('touchmove', onTouchMove)
    el.removeEventListener('touchend', onTouchEnd)
  }
}

let dragCleanups = []

onMounted(() => {
  // 图表初始化占位
  setTimeout(() => {
    if (chartRef.value) {
      chartInstance = echarts.init(chartRef.value)
      chartInstance.setOption({ graphic: [{ type:'text', left:'center', top:'center', style:{ text:'请点击“加载”获取示例数据（前端模拟）', fontSize:14, fill:'#909399' }}] })
    }
  }, 50)

  const onWinResize = () => chartInstance?.resize()
  window.addEventListener('resize', onWinResize)

  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => chartInstance?.resize())
    nextTick(() => {
      if (chartRef.value && chartRef.value.parentElement) ro.observe(chartRef.value.parentElement)
    })
  }

  // 设置拖动滚动监听（如果元素存在）
  nextTick(() => {
    if (tableWrapRef.value) {
      dragCleanups.push(enableDragScroll(tableWrapRef.value))
    }
    if (chartRef.value) {
      // chartRef is the chart container element (div) that can overflow; make it draggable
      dragCleanups.push(enableDragScroll(chartRef.value))
    }
  })
})

onBeforeUnmount(() => {
  try { window.removeEventListener('resize', () => chartInstance?.resize()) } catch (e) { /* ignore */ }
  if (ro) { try { ro.disconnect() } catch (e) { } ro = null }
  chartInstance?.dispose()
  chartInstance = null
  // cleanup drag handlers
  dragCleanups.forEach(fn => { try { fn() } catch (e) {} })
  dragCleanups = []
})

// 当视图切换到图表模式并有数据时重绘图表
watch(viewMode, (v) => {
  nextTick(() => {
    // ensure drag handlers are attached to the correct visible element
    // clear previous drag handlers, then reattach for visible containers
    dragCleanups.forEach(fn => { try { fn() } catch (e) {} })
    dragCleanups = []
    if (v === 'table') {
      if (tableWrapRef.value) dragCleanups.push(enableDragScroll(tableWrapRef.value))
    } else {
      if (chartRef.value) dragCleanups.push(enableDragScroll(chartRef.value))
      if (hasData.value) renderChart()
      chartInstance?.resize()
    }
  })
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

/* Content area */
.content {
  display: flex;
  gap: 16px;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
  min-height: calc(100vh - 200px);
}

/* Chart & table area */
.chart-area-wrap {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.table-wrap {
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  margin-bottom: 12px;
  overflow: auto;
  max-height: 520px;
}
/* inner wrapper ensures horizontal scroll when many columns */
.table-inner { width: 100%; white-space: nowrap; }

.chart-area {
  width: 100%;
  flex: 1 1 auto;
  min-height: 360px;
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  box-sizing: border-box;
  overflow: auto; /* allow chart container to scroll both axes if large */
}

/* draggable visual cues */
.draggable { cursor: grab; -webkit-user-select: none; -ms-user-select: none; user-select: none; }
.draggable.dragging { cursor: grabbing !important; }

/* Side panel */
.side-panel {
  width: 360px;
  flex: 0 0 360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.small-help { color:#909399; font-size:12px; margin-left:6px }

@media (max-width: 1100px) {
  .content { flex-direction: column; min-height: auto; }
  .side-panel { width: 100%; flex: 0 0 auto; }
  .chart-area { min-height: 320px; }
}

@media (max-width: 640px) {
  .controls .el-col { width: 100% !important; display: block; margin-bottom: 8px; }
  .chart-area { min-height: 280px; padding: 6px; }
  .side-panel { padding-bottom: 8px; }
}

/* side actions */
.side-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
  width: 100%;
  box-sizing: border-box;
  padding: 0;
}
.side-actions .side-action-btn,
.side-actions .el-button {
  width: 100%;
  margin: 0;
  max-width: none;
  box-sizing: border-box;
  text-align: center;
}

.card-header { font-weight:600; color:#333 }
.btn-col { display:flex; align-items:center; justify-content:flex-end }
</style>