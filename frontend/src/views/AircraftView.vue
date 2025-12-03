<template>
  <div class="aircraft-view-page">
    <!-- Controls -->
    <div class="controls" ref="controlsRef">
      <el-row :gutter="12" align="middle" wrap>
        <el-col :xs="24" :sm="8" :md="4">
          <el-input-number
            v-model="years"
            :min="2024"
            :max="2050"
            controls-position="right"
            style="width:100%"
            placeholder="预测年数"
          />
        </el-col>

        <el-col :xs="24" :sm="16" :md="8" style="margin-top:8px; margin-bottom:8px;">
          <el-radio-group v-model="selectedClass" class="radio-group-flex" size="medium">
            <el-radio label="large">大运量（100条）</el-radio>
            <el-radio label="medium">中运量（400条）</el-radio>
            <el-radio label="all">全国</el-radio>
          </el-radio-group>
        </el-col>

        <el-col :xs="24" :sm="12" :md="4" style="margin-bottom:8px;">
          <el-select v-model="viewMode" style="width:100%">
            <el-option label="表格视图" value="table" />
            <el-option label="堆叠柱状图" value="stacked" />
          </el-select>
        </el-col>

        <el-col :xs="24" :sm="12" :md="8" class="btn-col" style="gap: 8px;">
          <el-button plain @click="productivityDialogVisible = true" style="flex: 1 1 auto;">
            单机生产率配置
          </el-button>
          <el-button
            type="primary"
            @click="loadForecast"
            :loading="loading"
            style="flex: 1 1 auto;"
          >
            加载机队预测结果
          </el-button>
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
              @click="exportData"
              :disabled="!hasData"
              >数据导出</el-button
            >
          </div>
        </el-card>
      </div>
    </div>

    <el-dialog
      v-model="productivityDialogVisible"
      title="单机生产率配置"
      width="800px"
      :modal-append-to-body="false"
      :close-on-click-modal="false"
      :before-close="() => { btnLoading.value || (productivityDialogVisible.value = false) }"
      @open="fetchProductivityConfig"
      class="custom-productivity-dialog"
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
              :disabled="btnLoading"
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
              :disabled="btnLoading"
            />
          </template>
        </el-table-column>
        <el-table-column label="平均日利用率（h）" width="200">
          <template #default="{ row }">
            <el-input-number
              v-model="row.flightHours"
              :min="0"
              :step="1"
              style="width: 100%"
              :disabled="btnLoading"
            />
          </template>
        </el-table-column>
      </el-table>

      <!-- 弹窗底部按钮 -->
      <template #footer>
        <el-button
          :loading="btnLoading"
          type="primary"
          @click="saveProductivityConfig"
          style="float: right;"
        >
          保存配置
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'

// 响应式状态
const years = ref(2025)
const selectedClass = ref('large')
const viewMode = ref('table')

const loading = ref(false)
const loadingProductivity = ref(false)
const btnLoading = ref(false)

const productivityDialogVisible = ref(false)

const panelRows = ref([])
const tableColumns = ref([])
const total_count = ref(0)
const hasData = ref(false)
const productivityData = ref([])

const pieChartDom = ref(null)
const stackedDom = ref(null)

let pieChartInstance = null
let stackedChartInstance = null

// 表格内容最大高度，响应窗口调整
const contentTableMaxHeight = ref(520)

const updateContentTableMaxHeight = () => {
  const windowHeight = window.innerHeight
  const controlsHeight = 100 // 估算
  const footerHeight = 80
  const padding = 40
  const maxHeight = windowHeight - controlsHeight - footerHeight - padding
  contentTableMaxHeight.value = maxHeight > 300 ? maxHeight : 300
}
window.addEventListener('resize', updateContentTableMaxHeight)

// 模拟接口数据
const mockPieChartData = [
  { value: 40, name: '大运量' },
  { value: 30, name: '中运量' },
  { value: 30, name: '其他' },
]

const mockForecastData = {
  tableData: [
    { route: '北京-上海', small: 10, medium: 15, large: 5 },
    { route: '上海-广州', small: 5, medium: 20, large: 10 },
    { route: '北京-广州', small: 8, medium: 12, large: 7 }
  ],
  columns: [
    { key: 'small', label: '小型窄体客机' },
    { key: 'medium', label: '中型窄体客机' },
    { key: 'large', label: '大型宽体客机' }
  ],
  totalCount: 3,
  stackedData: {
    categories: ['北京-上海', '上海-广州', '北京-广州'],
    series: [
      {
        name: '小型窄体客机',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [10, 5, 8]
      },
      {
        name: '中型窄体客机',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [15, 20, 12]
      },
      {
        name: '大型宽体客机',
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: [5, 10, 7]
      }
    ]
  }
}

// 获取生产率配置
const fetchProductivityConfig = async () => {
  loadingProductivity.value = true
  try {
    const res = await fetch('你的接口URL')
    const json = await res.json()
    if (json.success && Array.isArray(json.data)) {
      // 接口字段 fleet_type 改为 machineType，avg_uti 改为 flightHours 方便绑定
      productivityData.value = json.data.map(item => ({
        machineType: item.fleet_type,
        avgSeats: item.avg_seats,
        avgSpeed: item.avg_speed,
        flightHours: item.avg_uti
      }))
    } else {
      productivityData.value = []
      console.error('接口返回格式错误或无数据')
    }
  } catch (error) {
    console.error('请求生产率配置失败:', error)
    productivityData.value = []
  } finally {
    loadingProductivity.value = false
  }
}

// 获取饼图数据
const fetchPieChartData = async () => {
  try {
    const data = mockPieChartData
    if (pieChartInstance) {
      pieChartInstance.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 10 },
        series: [
          {
            name: '航线类别分布',
            type: 'pie',
            radius: '50%',
            data,
            emphasis: {
              itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' }
            }
          }
        ]
      })
    }
  } catch (err) {
    console.error('获取饼图数据失败:', err)
  }
}

// 加载预测数据
const loadForecast = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    const { tableData, columns, totalCount, stackedData } = mockForecastData

    panelRows.value = tableData
    tableColumns.value = columns
    total_count.value = totalCount
    hasData.value = Array.isArray(tableData) && tableData.length > 0

    await nextTick()
    renderStackedChart(stackedData)
  } catch (err) {
    console.error('加载预测数据失败:', err)
  } finally {
    loading.value = false
  }
}

// 监听视图切换，渲染图表
watch(viewMode, (newMode) => {
  if (newMode === 'stacked' && panelRows.value.length > 0) {
    renderStackedChart()
  }
})

// 渲染堆积柱状图
const renderStackedChart = (stackedData) => {
  if (!stackedChartInstance && stackedDom.value) {
    stackedChartInstance = echarts.init(stackedDom.value)
  }
  if (!stackedChartInstance) return

  if (!stackedData) {
    stackedData = {
      categories: panelRows.value.map(row => row.route),
      series: tableColumns.value.map(col => ({
        name: col.label,
        type: 'bar',
        stack: 'total',
        emphasis: { focus: 'series' },
        data: panelRows.value.map(row => row[col.key] || 0)
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

// 导出CSV
const exportData = () => {
  if (!panelRows.value.length || !tableColumns.value.length) return

  const headers = ['航线', ...tableColumns.value.map(c => c.label)]
  const csvRows = [headers.join(',')]

  for (const row of panelRows.value) {
    const line = [row.route]
    for (const col of tableColumns.value) {
      line.push(row[col.key] ?? 0)
    }
    csvRows.push(line.join(','))
  }

  const csvString = csvRows.join('\n')
  const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' })

  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.href = url
  link.setAttribute('download', `forecast_${years.value}_${selectedClass.value}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

// 保存生产率配置
const saveProductivityConfig = async () => {
  btnLoading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 300))
    alert('配置保存成功')
    productivityDialogVisible.value = false
  } catch (err) {
    console.error('保存生产率配置失败:', err)
    alert('保存失败，请重试')
  } finally {
    btnLoading.value = false
  }
}

// 页面初始化
onMounted(() => {
  updateContentTableMaxHeight()

  if (pieChartDom.value) {
    pieChartInstance = echarts.init(pieChartDom.value)
  }
  if (stackedDom.value) {
    stackedChartInstance = echarts.init(stackedDom.value)
  }

  fetchProductivityConfig()
  fetchPieChartData()
})
</script>

<style scoped>
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

/* 让控件区域内布局在小屏幕下换行 */
.el-row {
  flex-wrap: wrap;
}

/* flex 布局优化按钮和控件组间距 */
.radio-group-flex {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

/* 小提示文字 */
.small-help {
  font-size: 12px;
  color: #666;
}

/* 主内容区域 */
.content {
  display: flex;
  flex: 1;
  gap: 16px;
  min-height: 400px;
  height: calc(100vh - 130px);
}

/* 图表和表格包裹容器 */
.chart-area-wrap {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgb(0 0 0 / 0.1);
  overflow: hidden;
  height: 100%;
}

/* 表格容器 */
.table-wrap {
  flex: 1 1 auto;
  overflow: auto;
  padding: 12px;
}

/* 表格内部，最小宽度 */
.table-inner {
  min-width: 800px;
}

/* el-table 样式适配 */
.el-table {
  max-height: var(--table-max-height, 520px);
  overflow-y: auto;
}

/* 堆叠柱状图容器 */
.chart-area {
  flex: 1 1 auto;
  overflow: auto;
  background: #fff;
  border-radius: 6px;
  box-shadow: 0 1px 6px rgb(0 0 0 / 0.1);
  position: relative;
}

/* 图表内部样式 */
.chart-inner {
  height: 100% !important;
  min-width: 700px;
}

/* 右侧侧边栏 */
.side-panel {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  height: 100%;
}

/* card标题统一样式 */
.card-header {
  font-weight: 600;
  font-size: 16px;
  color: #333;
}

/* pie chart 容器，指定固定高度 */
.pie-chart {
  width: 100%;
  height: 240px;
  margin-top: 12px;
}

/* 操作按钮区域 */
.side-actions {
  display: flex;
  justify-content: flex-start;
  gap: 12px;
}

/* 操作按钮统一小号样式 */
.side-action-btn {
  font-size: 14px;
}

/* 按钮列布局 */
.btn-col {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 拖拽类容器占位，便于以后实现拖动功能 */
.draggable {
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

/* 解决 el-dialog 内滚动问题 */
.custom-productivity-dialog {
  max-width: 90vw !important;
}

.custom-productivity-dialog .el-dialog__body {
  max-height: 60vh;
  overflow-y: auto;
}

/* 调整按钮间距 */
.el-button + .el-button {
  margin-left: 8px;
}

/* 让控件和按钮在小屏幕时更适应 */
@media (max-width: 768px) {
  .btn-col {
    flex-direction: column;
    gap: 8px;
  }
  .radio-group-flex {
    flex-direction: column;
    gap: 8px;
  }
}
</style>