<template>
  <div class="data-show-page">
    <!-- Controls -->
    <div class="controls" ref="controlsRef">
      <div class="controls-left">
        <div style="min-width: 120px; max-width: 240px;">
          <el-select v-model="granularity" placeholder="选择粒度" style="width:100%">
            <el-option label="年度" value="年度" />
            <el-option label="季度" value="季度" />
            <el-option label="月度" value="月度" />
          </el-select>
        </div>

        <div style="min-width: 120px; max-width: 240px;">
          <el-input-number
            v-model="years"
            :min="1"
            :max="20"
            controls-position="right"
            style="width:100%"
            placeholder="年数 (1 - 20)"
          />
        </div>

        <div style="min-width: 120px; max-width: 240px;">
          <el-checkbox-group v-model="selectedClasses" style="display:flex; gap:8px;">
            <el-checkbox label="large">大运量（100条）</el-checkbox>
            <el-checkbox label="medium">中运量（400条）</el-checkbox>
            <el-checkbox label="small">小运量(加总)</el-checkbox>
            <el-checkbox label="all">全国（总体）</el-checkbox>
          </el-checkbox-group>
        </div>
      </div>

      <div class="controls-right">
        <div style="min-width: 100px; max-width: 180px;">
          <el-select v-model="viewMode" style="width:100%">
            <el-option label="表格视图" value="table" />
            <el-option label="聚合总量" value="aggregate" />
            <el-option label="热力图" value="heatmap" />
          </el-select>
        </div>

        <div class="btn-col" style="min-width: 100px; max-width: 180px;">
          <el-button type="primary" @click="loadForecast" :loading="loading">加载运力预测结果</el-button>
        </div>
      </div>
    </div>

    <!-- Main content -->
    <div class="content">
      <div class="chart-area-wrap">
        <!-- 表格视图: 使用普通带滚动条的容器 -->
        <div
          v-if="viewMode === 'table'"
          class="table-wrap"
          ref="tableWrapRef"
          style="overflow: auto; max-height: 520px;"
        >
          <el-table
            :data="panelRows"
            stripe
            size="small"
            style="min-width: 900px; width: 100%;"
            v-loading="loading"
          >
            <el-table-column prop="route" label="预测结果" min-width="120" fixed />
            <el-table-column
              v-for="col in tableColumns"
              :key="col.key"
              :prop="col.key"
              :label="col.label"
              min-width="90"
            />
          </el-table>
        </div>

        <!-- 图表区域（聚合/热力） -->
        <div
          v-show="viewMode !== 'table'"
          ref="chartRef"
          class="chart-area"
          style="overflow: auto; min-width: 800px;"
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
            <el-descriptions-item label="总计算航线数">{{ total_count }}</el-descriptions-item>
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
            <el-button class="side-action-btn" size="small" type="warning" @click="HistoryDialog">数据更新</el-button>
            <el-button class="side-action-btn" size="small" type="primary" @click="exportData" :disabled="!hasData">数据导出</el-button>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 数据更新弹窗 -->
    <el-dialog
      v-model="updateDialogVisible"
      title="数据更新记录"
      width="600px"
    >
      <el-table :data="updateLogs" stripe size="small" style="width: 100%">
        <el-table-column prop="start_time" label="开始时间" width="180" />
        <el-table-column prop="end_time" label="结束时间" width="180" />
        <el-table-column prop="status" label="状态" min-width="120" />
      </el-table>

      <div style="text-align:center; margin-top: 20px;">
        <el-button
          type="primary"
          :disabled="!canUpdate"
          @click="doUpdate"
        >
          执行更新
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'

/* ------------------ update dialog ------------------ */
const updateDialogVisible = ref(false)
const updateLogs = ref([])
const canUpdate = ref(false)

const HistoryDialog = () => {
  updateDialogVisible.value = true
  loadUpdateStatus()
}

const loadUpdateStatus = async () => {
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.LOGS)
    const res = await axios.get(url)
    if (res.data?.success) {
      const data = res.data.data
      updateLogs.value = data.logs || []
      canUpdate.value = data.can_update
    }
  } catch (err) {
    console.error('加载更新记录失败:', err)
  }
}

const doUpdate = async () => {
  if (!canUpdate.value) return
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPDATE_ALL)
    const res = await axios.post(url)
    if (res.data.code === 200) {
      ElMessage.success('更新已开始')
      loadUpdateStatus()
    }
  } catch (err) {
    ElMessage.error('更新失败')
  }
}

/* ------------------ main state ------------------ */
const granularity = ref('年度')
const years = ref(10)
const total_count = ref(null)
const selectedClasses = ref(['large'])
const viewMode = ref('table')
const loading = ref(false)

const chartRef = ref(null)
const tableWrapRef = ref(null)
let chartInstance = null

const dataStore = reactive({ large: null, medium: null, small: null, _prepared: [] })
const labels = ref([])

const periods = computed(() => {
  const y = Math.max(1, Math.min(20, Number(years.value) || 1))
  if (granularity.value === '年度') return y
  if (granularity.value === '季度') return y * 4
  return y * 12
})

const hasData = computed(() => Array.isArray(dataStore._prepared) && dataStore._prepared.length > 0)

/* ------------------ fetch / parse / prepare ------------------ */
async function loadForecast() {
  if (!selectedClasses.value.length) {
    ElMessage.warning('请选择至少一种统计对象（大/中/小/全部）')
    return
  }
  loading.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.SHOW)
    const res = await axios.get(url, {
      params: {
        panels: selectedClasses.value.join(','),
        time_granularity:
          granularity.value === '年度'
            ? 'yearly'
            : granularity.value === '季度'
            ? 'quarterly'
            : 'monthly',
        steps: years.value
      },
      timeout: 60000
    })
    console.log('后端返回数据:', res.data)

    if (!res.data.data || !res.data.data.panels) {
      throw new Error('后端返回数据格式错误：缺少 panels')
    }
    total_count.value = res.data.data.route_length || null
    parseBackend(res.data.data)
    prepareVisualData()

    // 切换视图时渲染图表（如果不是表格视图）
    if (viewMode.value !== 'table') renderChart()
    nextTick(() => chartInstance?.resize())

    ElMessage.success(`数据加载成功，更新时间：${res.data.data.forecast_time || '未知'}`)
  } catch (err) {
    console.error(err)
    ElMessage.error('加载失败，请检查网络或后台接口')
  } finally {
    loading.value = false
  }
}

function parseBackend(resp) {
  dataStore.large = dataStore.medium = dataStore.small = dataStore.all = null
  labels.value = []
  if (!resp) return

  if (Array.isArray(resp.time_points) && resp.time_points.length > 0) {
    labels.value = resp.time_points.slice()
  }

  const panels = resp.panels || {}

  ;['large', 'medium', 'small', 'all'].forEach(cls => {
    const panel = panels[cls]
    if (!panel || !Array.isArray(panel.rows)) return
    const rows = panel.rows
    const routes = rows.map(row => row[0])
    const data = rows.map(row =>
      row.slice(1).map(v => (isNaN(Number(v)) ? 0 : Number(v)))
    )
    dataStore[cls] = {
      labels: labels.value.slice(),
      routes,
      data
    }
  })
}

function prepareVisualData() {
  if (!Array.isArray(labels.value) || labels.value.length === 0) {
    labels.value = []
  }

  const build = (store, cls) => {
    if (!store) return []
    const out = []
    for (let i = 0; i < store.routes.length; i++) {
      out.push({
        route: store.routes[i],
        values: store.data[i] || [],
        cls
      })
    }
    return out
  }

  let combined = []
  if (selectedClasses.value.includes('large'))
    combined = combined.concat(build(dataStore.large, 'large'))
  if (selectedClasses.value.includes('medium'))
    combined = combined.concat(build(dataStore.medium, 'medium'))
  if (selectedClasses.value.includes('small'))
    combined = combined.concat(build(dataStore.small, 'small'))
  if (selectedClasses.value.includes('all'))
    combined = combined.concat(build(dataStore.all, 'all'))   // 修复：不再写成 dataStore.small
  dataStore._prepared = Array.isArray(combined) ? combined : []
}

/* ------------------ chart / view rendering ------------------ */
function renderChart() {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()

  const prepared = Array.isArray(dataStore._prepared) ? dataStore._prepared : []
  if (!prepared.length) {
    chartInstance.setOption({
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'center',
          style: { text: '暂无数据，请点击加载', fontSize: 22, fill: '#909399' }
        }
      ]
    })
    return
  }

  if (viewMode.value === 'aggregate') {
    const sum = new Array(labels.value.length).fill(0)
    prepared.forEach(s => {
      for (let i = 0; i < labels.value.length; i++) {
        sum[i] += Number((s.values || [])[i]) || 0
      }
    })
    chartInstance.setOption(
      {
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: labels.value,
          axisLabel: { interval: Math.ceil(labels.value.length / 12) }
        },
        yAxis: { type: 'value' },
        series: [
          {
            name: '总运力',
            type: 'line',
            data: sum,
            smooth: true,
            areaStyle: { opacity: 0.18 }
          }
        ]
      },
      true
    )
    return
  }

  if (viewMode.value === 'heatmap') {
    const rows = prepared
    const heatData = []
    for (let i = 0; i < rows.length; i++) {
      for (let j = 0; j < labels.value.length; j++) {
        heatData.push([j, i, Number((rows[i].values || [])[j] || 0)])
      }
    }
    chartInstance.setOption(
      {
        tooltip: {
          position: 'top',
          formatter: p =>
            `时间: ${labels.value[p.value[0]]}<br/>航线: ${rows[p.value[1]].route}<br/>值: ${p.value[2]}`
        },
        grid: { left: 140, right: 60, bottom: 80, containLabel: true },
        xAxis: {
          type: 'category',
          data: labels.value,
          axisLabel: { interval: Math.ceil(labels.value.length / 12) }
        },
        yAxis: {
          type: 'category',
          data: rows.map(r => r.route),
          axisLabel: { interval: 0 }
        },
        visualMap: {
          min: 0,
          max: Math.max(...heatData.map(d => d[2]), 1),
          calculable: true,
          orient: 'vertical',
          right: 10,
          top: 'center'
        },
        series: [{ name: 'heat', type: 'heatmap', data: heatData, progressive: 2000 }]
      },
      true
    )
    return
  }
}

/* ------------------ helpers / export ------------------ */
function exportData() {
  const prepared = Array.isArray(dataStore._prepared) ? dataStore._prepared : []
  if (!prepared.length) {
    ElMessage.info('无可导出数据')
    return
  }
  const header = ['route', ...labels.value]
  const rows = prepared.map(s => [
    s.route,
    ...(s.values || []).map(v => (v === null || v === undefined ? '' : v))
  ])
  const aoa = [header, ...rows]
  try {
    const ws = XLSX.utils.aoa_to_sheet(aoa)
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'forecast')
    XLSX.writeFile(wb, `ASK预测_${granularity.value}_${years.value}y_${Date.now()}.xlsx`)
    ElMessage.success('导出成功')
  } catch (e) {
    console.error('导出失败', e)
    ElMessage.error('导出失败')
  }
}

/* ------------------ table computed ------------------ */
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
    cols.forEach((l, idx) => {
      obj[l] = s.values && s.values[idx] != null ? s.values[idx] : 0
    })
    return obj
  })
})

const summaryTable = computed(() => {
  const rows = []
  const classes = { large: '大运量', medium: '中运量', small: '小运量(加总)', all: '全国（总体）' }
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
    data.forEach(arr => {
      for (let i = 0; i < periodsCnt; i++) agg[i] += Number(arr[i] || 0)
    })
    const total = agg.reduce((s, v) => s + v, 0)
    const avg = periodsCnt ? total / periodsCnt : 0
    const first = agg[0] || 0
    const last = agg[agg.length - 1] || 0
    const growth = first > 0 ? Math.pow(last / first || 1, 1 / Math.max(1, years.value)) - 1 : last > 0 ? 1 : 0
    rows.push({ classLabel: classes[cls], routeCount: routes.length, total, avg, growth })
  })
  return rows
})

function fmtNumber(_, __, v) {
  return v === null || v === undefined ? '-' : Number(v).toLocaleString()
}
function fmtPct(_, __, v) {
  return v === null || v === undefined ? '-' : (v * 100).toFixed(2) + '%'
}

watch(
  () => dataStore._prepared,
  (newVal) => {
    if (viewMode.value !== 'table' && hasData.value) {
      renderChart()
      nextTick(() => chartInstance?.resize())
    }
  },
  { deep: true }
)

// 监听视图切换，自动渲染图表视图
watch(viewMode, (newVal) => {
  if (newVal !== 'table' && hasData.value) {
    renderChart()
    nextTick(() => chartInstance?.resize())
  }
})

onMounted(() => {
  setTimeout(() => {
    if (chartRef.value) {
      chartInstance = echarts.init(chartRef.value)
      chartInstance.setOption({
        graphic: [
          {
            type: 'text',
            left: 'center',
            top: 'center',
            style: { text: '加载中...', fontSize: 14, fill: '#909399' }
          }
        ]
      })
    }
  }, 50)

  loadForecast()
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
  box-sizing: border-box;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

/* 左侧容器：下拉、数字输入、复选框，左对齐 */
.controls-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  justify-content: flex-start;
  flex: 1 1 auto;
}

/* 里面的 el-col 保证宽度 */
.controls-left > * {
  min-width: 120px;
  max-width: 240px;
}

/* 右侧容器：视图选择和按钮，右对齐 */
.controls-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: nowrap;
  justify-content: flex-end;
  flex: 0 0 auto;
}

/* 里面的 el-col 也限制宽度 */
.controls-right > * {
  min-width: 100px;
  max-width: 180px;
}

/* 保持按钮容器布局 */
.btn-col {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

/* 其他已有样式保留 */
.content {
  display: flex;
  gap: 16px;
  align-items: stretch;
  width: 100%;
  min-height: calc(100vh - 200px);
  box-sizing: border-box;
}

.chart-area-wrap {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.table-wrap {
  height: 100%;
  max-height: 700px;
  min-height: 660px;
  overflow: hidden;
  background: #fff;
  border-radius: 6px;
  padding: 0;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  width: 100%;
  display: flex;
  flex-direction: column;
}

.table-inner {
  flex: 1;
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: auto;
  box-sizing: border-box;
}

.table-inner .el-table {
  height: 100% !important;
  width: 100%;
}

.el-table {
  margin: 0 !important;
}

.chart-area {
  flex: 1 1 auto;
  min-height: 360px;
  max-height: 700px;
  background: #fff;
  border-radius: 6px;
  padding: 8px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.04);
  box-sizing: border-box;
  overflow: auto;
  width: 100%;
}

.side-panel {
  flex: 0 0 360px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-sizing: border-box;
}

.small-help {
  color: #909399;
  font-size: 12px;
  margin-left: 6px;
}

@media (max-width: 1100px) {
  .content {
    flex-direction: column;
    min-height: auto;
  }
  .side-panel {
    flex: 0 0 auto;
    width: 100%;
  }
  .chart-area {
    min-height: 320px;
    max-height: 500px;
  }
}

@media (max-width: 640px) {
  .controls-left > * {
    min-width: 100px;
  }
  .controls-right > * {
    min-width: 80px;
  }
  .controls {
    flex-wrap: wrap;
  }
  .chart-area {
    min-height: 280px;
    max-height: 400px;
    padding: 6px;
  }
  .side-panel {
    padding-bottom: 8px;
  }
}

.side-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding: 0;
  box-sizing: border-box;
}

.side-actions .side-action-btn,
.side-actions .el-button {
  width: 100%;
  margin: 0;
  max-width: none;
  text-align: center;
  box-sizing: border-box;
}

.card-header {
  font-weight: 600;
  color: #333;
}
</style>