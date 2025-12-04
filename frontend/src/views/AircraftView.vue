<template>
  <div class="aircraft-view-page">
    <!-- Controls -->
    <div class="controls" ref="controlsRef">
      <el-row :gutter="12" align="middle" class="controls-row">

        <!-- 年份 -->
        <el-col :xs="24" :sm="6" :md="4">
          <el-input-number
            v-model="years"
            :min="2024"
            :max="2050"
            controls-position="right"
            style="width:100%"
          />
        </el-col>

        <!-- 单选框组 -->
        <el-col :xs="24" :sm="10" :md="8">
          <el-radio-group
            v-model="selectedClass"
            class="radio-group-flex"
            size="small"
            style="width:100%;"
          >
            <el-radio label="large">大运量（100条）</el-radio>
            <el-radio label="medium">中运量（400条）</el-radio>
            <el-radio label="all">全国</el-radio>
          </el-radio-group>
        </el-col>

        <el-col :xs="24" :sm="8" :md="12" class="actions-right">
          <div class="actions-right-inner">
            
            <!-- 视图切换 -->
            <el-select v-model="viewMode" style="width:160px;">
              <el-option label="表格视图" value="table" />
              <el-option label="堆叠柱状图" value="stacked" />
            </el-select>

            <!-- 按钮A -->
            <el-button plain @click="openProductivityDialog">
              单机生产率配置
            </el-button>

            <!-- 按钮B -->
            <el-button
              type="primary"
              @click="loadForecast"
              :loading="loading"
            >
              加载机队预测结果
            </el-button>

          </div>
        </el-col>

      </el-row>

      <el-row>
        <el-col :span="24">
          <div class="small-help" style="margin-top: 6px;">
            说明：仅支持选择一种航线类别；选择后点击“加载”显示预测。
          </div>
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
        >
          <div class="table-inner">
            <el-table
              :data="panelRows"
              stripe
              size="small"
              style="width: 100%"
              :max-height="contentTableMaxHeight"
              v-loading="loading"
            >
              <el-table-column prop="route" label="航线" min-width="120" fixed />
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

        <!-- 堆叠柱状图 -->
        <div
          v-if="viewMode === 'stacked'"
          ref="stackedDom"
          class="chart-area draggable chart-inner"
        ></div>
      </div>

      <div class="side-panel">
        <!-- 汇总统计 -->
        <el-card>
          <template #header>
            <div class="card-header">汇总统计</div>
          </template>
          <div>航线数量：{{ total_count }}</div>
          <div ref="pieChartDom" class="pie-chart"></div>
        </el-card>

        <!-- 操作 -->
        <el-card class="action-card">
          <template #header>
            <div class="card-header">操作</div>
          </template>
          <div class="side-actions">
            <el-button
              class="side-action-btn"
              type="primary"
              size="small"
              @click="exportData"
              :disabled="!hasData"
              >数据导出</el-button
            >
          </div>
        </el-card>
      </div>
    </div>

    <!-- 生产率弹窗 -->
    <el-dialog
      v-model="productivityDialogVisible"
      title="单机生产率配置"
      width="800px"
      :before-close="handleProductivityBeforeClose"
      @open="fetchProductivityConfig"
      class="custom-productivity-dialog"
      :close-on-click-modal="false"
      :destroy-on-close="false"
    >
      <el-table
        v-loading="loadingProductivity"
        :data="productivityData"
        size="small"
        style="width: 100%"
        border
      >
        <el-table-column prop="machineType" label="座级" width="180" />
        <el-table-column label="平均座位数（座）" width="200">
          <template #default="{ row }">
            <el-input-number
              v-model="row.avgSeats"
              :min="0"
              :step="1"
              style="width: 100%"
              :disabled="btnLoading || loadingProductivity"
            />
          </template>
        </el-table-column>
        <el-table-column label="平均速度（KM/h）" width="200">
          <template #default="{ row }">
            <el-input-number
              v-model="row.avgSpeed"
              :min="0"
              :step="1"
              style="width: 100%"
              :disabled="btnLoading || loadingProductivity"
            />
          </template>
        </el-table-column>
        <el-table-column label="平均日利用率（h）" width="200">
          <template #default="{ row }">
            <el-input-number
              v-model="row.flightHours"
              :min="0"
              :step="0.1"
              style="width: 100%"
              :disabled="btnLoading || loadingProductivity"
            />
          </template>
        </el-table-column>
      </el-table>

      <template #footer>
        <div style="display:flex; justify-content:space-between; align-items:center; width:100%">
          <div style="color:#999; font-size:12px;">编辑后请点击“保存配置”提交到后端</div>

          <div>
            <el-button
              :disabled="btnLoading"
              @click="handleProductivityCancel"
            >
              取消
            </el-button>
            <el-button
              type="primary"
              :loading="btnLoading"
              @click="saveProductivityConfig"
            >
              保存配置
            </el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { ElMessage } from 'element-plus'

/* =============================
   基础状态
============================= */
const years = ref(2025)
const selectedClass = ref('large')   // large / medium / all
const viewMode = ref('table')

const loading = ref(false)
const loadingProductivity = ref(false)
const btnLoading = ref(false)

const productivityDialogVisible = ref(false)

/* =============================
   数据区域
============================= */
const panelRows = ref([])
const tableColumns = ref([])
const total_count = ref(0)
const hasData = ref(false)
const productivityData = ref([])

const pieChartDom = ref(null)
const stackedDom = ref(null)

let pieChartInstance = null
let stackedChartInstance = null

/* =============================
   UI 控制量
============================= */
const contentTableMaxHeight = ref(520)

const updateContentTableMaxHeight = () => {
  const vh = window.innerHeight
  const available = Math.max(320, vh - 160)
  contentTableMaxHeight.value = available
}
window.addEventListener('resize', updateContentTableMaxHeight)

/* =============================
   工具函数
============================= */
const clearForecastData = () => {
  panelRows.value = []
  tableColumns.value = []
  total_count.value = 0
  hasData.value = false
  renderStackedChart(null)
}

const parsePanelData = (payload) => {
  const key = selectedClass.value   // ⭐ 动态取 large / medium / all
  const headers = payload?.panels?.[key]?.headers || []
  const rows = payload?.panels?.[key]?.rows || []

  if (!Array.isArray(headers) || !Array.isArray(rows) || headers.length < 2) {
    return { columns: [], rows: [] }
  }

  const seatHeaders = headers.slice(1)

  const tableColumnsParsed = seatHeaders.map((h, idx) => ({
    key: `col_${idx + 1}`,
    label: h,
    minWidth: 90
  }))

  const tableRowsParsed = rows.map(r => {
    const obj = { route: r[0] }
    for (let i = 1; i < headers.length; i++) {
      obj[`col_${i}`] = r[i] ?? 0
    }
    return obj
  })

  return { columns: tableColumnsParsed, rows: tableRowsParsed }
}

const buildStackedSeries = (headers, rows) => {
  const seatHeaders = headers.slice(1)
  return seatHeaders.map((h, idx) => {
    const colIndex = idx + 1
    return {
      name: h,
      type: 'bar',
      stack: 'total',
      data: rows.map(r => r[colIndex] ?? 0),
      emphasis: { focus: 'series' }
    }
  })
}

/* =============================
   API: 加载预测数据
============================= */
const loadForecast = async () => {
  loading.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.AIRCRAFTS)
    const params = { year: years.value, panels: selectedClass.value }
    console.log('请求预测数据参数:', params)

    const res = await axios.get(url, { params })
    console.log('预测数据返回:', res.data)
    if (!res.data || res.data.success !== true) {
      clearForecastData()
      return
    }

    const payload = res.data.data || {}
    const key = selectedClass.value

    const headers = payload?.panels?.[key]?.headers || []
    const rows = payload?.panels?.[key]?.rows || []

    if (!headers.length || !rows.length) {
      clearForecastData()
      return
    }

    const parsed = parsePanelData(payload)
    tableColumns.value = parsed.columns
    panelRows.value = parsed.rows
    total_count.value = parsed.rows.length
    hasData.value = parsed.rows.length > 0

    const series = buildStackedSeries(headers, rows)

    await nextTick()
    renderStackedChart({
      categories: panelRows.value.map(r => r.route),
      series
    })

    renderPieChart()
  } catch (err) {
    console.error('加载预测数据失败:', err)
    clearForecastData()
    ElMessage.error('加载预测数据失败，请重试')
  } finally {
    loading.value = false
  }
}

/* =============================
   图表渲染
============================= */
const renderStackedChart = (stackedData) => {
  if (!stackedChartInstance && stackedDom.value) {
    stackedChartInstance = echarts.init(stackedDom.value)
  }
  if (!stackedChartInstance) return

  if (!stackedData) {
    stackedData = {
      categories: panelRows.value.map(r => r.route),
      series: tableColumns.value.map(col => ({
        name: col.label,
        type: 'bar',
        stack: 'total',
        data: panelRows.value.map(r => r[col.key] ?? 0)
      }))
    }
  }

  stackedChartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: stackedData.series.map(s => s.name), top: 20 },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: stackedData.categories, axisLabel: { rotate: 45 } },
    yAxis: { type: 'value' },
    series: stackedData.series
  })
}

const renderPieChart = () => {
  if (!pieChartDom.value) return
  if (!pieChartInstance) pieChartInstance = echarts.init(pieChartDom.value)

  if (!tableColumns.value.length || !panelRows.value.length) {
    pieChartInstance.setOption({ series: [{ data: [] }] })
    return
  }

  const data = tableColumns.value.map(col => {
    const total = panelRows.value.reduce((s, r) => s + (Number(r[col.key]) || 0), 0)
    return { name: col.label, value: total }
  })

  pieChartInstance.setOption({
    tooltip: {
      trigger: 'item',
      formatter: params =>
        `${params.name}<br/>数量：${params.value}<br/>占比：${params.percent}%`
    },

    legend: {
      type: 'plain',
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      padding: [5, 10],
      itemWidth: 14,
      itemHeight: 10,
      textStyle: { fontSize: 12 }
    },

    series: [
      {
        name: '座级数量',
        type: 'pie',

        /** ★ 放大饼图 */
        radius: ['45%', '85%'],

        /** ★ 上移消除顶部空白 & 居中 */
        top: '-20%',
        left: 'center',

        label: { show: false },
        labelLine: { show: false },

        emphasis: { label: { show: false } },

        data
      }
    ]
  })
}

/* =============================
   导出 CSV
============================= */
const exportData = () => {
  if (!panelRows.value.length || !tableColumns.value.length) return

  const headers = ['航线', ...tableColumns.value.map(c => c.label)]
  const csvRows = [headers.join(',')]

  panelRows.value.forEach(row => {
    csvRows.push([
      row.route,
      ...tableColumns.value.map(c => row[c.key] ?? 0)
    ].join(','))
  })

  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `forecast_${years.value}_${selectedClass.value}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

/* =============================
   生产率配置
============================= */
const fetchProductivityConfig = async () => {
  loadingProductivity.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.URATE)
    const res = await axios.get(url)

    if (res.data?.success && Array.isArray(res.data.data)) {
      productivityData.value = res.data.data.map(item => ({
        machineType: item.fleet_type ?? '',
        avgSeats: item.avg_seats ?? 0,
        avgSpeed: item.avg_speed ?? 0,
        flightHours: item.avg_uti ?? 0
      }))
    } else {
      productivityData.value = []
    }

  } catch (e) {
    console.error('请求生产率配置失败:', e)
    productivityData.value = []
  } finally {
    loadingProductivity.value = false
  }
}

const saveProductivityConfig = async () => {
  btnLoading.value = true
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.URATE_UPDATE)

    const payload = productivityData.value.map(row => ({
      fleet_type: row.machineType,
      avg_seats: Number(row.avgSeats) || 0,
      avg_speed: Number(row.avgSpeed) || 0,
      avg_uti: Number(row.flightHours) || 0
    }))

    const res = await axios.post(url, { data: payload })

    if (res.data?.success) {
      ElMessage.success('配置保存成功')
      productivityDialogVisible.value = false
    } else {
      ElMessage.error(res.data?.message || '保存失败')
    }

  } catch (err) {
    console.error('保存生产率配置失败:', err)
    ElMessage.error('保存失败，请重试')
  } finally {
    btnLoading.value = false
  }
}

function handleProductivityBeforeClose(done) {
  if (btnLoading.value) {
    ElMessage.warning('配置正在保存，请稍候...')
    return
  }
  done()
}

function handleProductivityCancel() {
  if (btnLoading.value) {
    ElMessage.warning('配置正在保存，请稍候...')
    return
  }
  productivityDialogVisible.value = false
}

function openProductivityDialog() {
  productivityDialogVisible.value = true
}

/* =============================
   生命周期
============================= */
onMounted(() => {
  updateContentTableMaxHeight()
  if (pieChartDom.value) pieChartInstance = echarts.init(pieChartDom.value)
  if (stackedDom.value) stackedChartInstance = echarts.init(stackedDom.value)

  fetchProductivityConfig()
  loadForecast()
})

/* =============================
   ⭐ 自动重新加载 API：视图 + 舱位切换
============================= */
watch(viewMode, () => {
  loadForecast()       // 切图 => 自动刷新数据 & 重绘
})

watch(selectedClass, () => {
  loadForecast()       // 切 large/medium/all => 自动重新加载
})
</script>

<style scoped>
/* 整体页面布局 */
.aircraft-view-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 12px 16px;
  box-sizing: border-box;
  font-family: "Helvetica Neue", Arial, sans-serif;
  background: #f9f9f9;
  user-select: none;
}

/* 控件区域 */
.controls {
  background: #fff;
  padding: 12px 16px;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgb(0 0 0 / 0.1);
  margin-bottom: 12px;
  user-select: text;
}

.el-row {
  flex-wrap: wrap;
}

.radio-group-flex {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.small-help {
  font-size: 12px;
  color: #666;
}

/* =======================
    主内容区（左右结构）
======================= */
.content {
  display: flex;
  flex: 1;
  gap: 16px;

  /* 控制左右区高度保持一致 */
  height: calc(100vh - 130px);
  min-height: 400px;
  overflow: hidden;
}

/* =======================
      左侧（图表/表格）
======================= */
.chart-area-wrap {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgb(0 0 0 / 0.1);
  overflow: hidden;
  height: 100%;   /* 与右侧对齐 */
}

/* 表格视图外层 */
.table-wrap {
  flex: 1;         
  display: flex;
  flex-direction: column;
  overflow: hidden;   /* 禁止外层滚动条 */
  padding: 12px;
}

/* 表格内部（唯一滚动区域） */
.table-inner {
  flex: 1;
  overflow-y: auto;    /* 唯一滚动条 */
  overflow-x: auto;
  min-width: 800px;
}

/* 让 el-table 撑满容器，不产生它自己的滚动条 */
.el-table {
  height: 100% !important;
  max-height: none !important;
  overflow: visible !important;   /* 禁止表格内部产生滚动条 */
}

/* 图表内容区（热力图/堆叠柱状图） */
.chart-area {
  flex: 1;
  overflow: auto;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgb(0 0 0 / 0.1);
  position: relative;
  height: 100%;
}

.chart-inner {
  height: 100% !important;
  min-width: 700px;
}


/* =======================
         右侧栏
======================= */
.side-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  height: 100%;   /* 与左侧对齐 */
}

.card-header {
  font-weight: 600;
  font-size: 16px;
  color: #333;
}

/* =======================
        饼图样式优化
======================= */
.pie-chart {
  width: 100%;
  height: 420px; /* 更大的可视区域 */
  margin-top: 12px;
}

.summary-card {
  padding-bottom: 12px;
}

/* 按钮 */
.side-actions {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
}

.side-action-btn {
  font-size: 14px;
  width: 100%;
}

.btn-col {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 拖拽占位 */
.draggable {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* Dialog 滚动问题修复 */
.custom-productivity-dialog {
  max-width: 90vw !important;
}

.custom-productivity-dialog .el-dialog__body {
  max-height: 60vh;
  overflow-y: auto;
}

.el-button + .el-button {
  margin-left: 8px;
}

/* 统一控件高度 */
.controls-row .el-col {
  display: flex;
  align-items: center;
}

/* 视图切换框右对齐 */
.select-align-right {
  display: flex;
  justify-content: flex-end; /* 关键：右对齐 */
}

.select-right-wrapper {
  width: 100%;
  display: flex;
  justify-content: flex-end; /* 保证内部控件也靠右 */
}

/* 按钮右对齐布局 */
.controls-actions {
  display: flex;
  justify-content: flex-end;
}

.controls-actions-inner {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  width: 100%;
}

/* 保证按钮高度一致 */
.controls-actions-inner .el-button {
  min-width: 130px;
}

/* ========== 响应式 ========== */
@media (max-width: 768px) {
  .btn-col {
    flex-direction: column;
    gap: 8px;
  }
  .radio-group-flex {
    flex-direction: column;
    gap: 8px;
  }
  .side-panel {
    width: 100%;
  }
}
</style>