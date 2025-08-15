<template>
  <div class="forecast-container">
    <div class="forecast-content">
      <!-- 左侧控制面板 -->
      <div class="control-panel">
        <h2 class="panel-title">预测任务配置</h2>

        <!-- 时间粒度 -->
        <div class="form-group" :disabled="isConfigured">
          <label>预测时间粒度</label>
          <el-select v-model="timeRange" placeholder="选择时间粒度" class="large-select" :disabled="isConfigured">
            <el-option label="年度" value="年度" />
            <el-option label="季度" value="季度" />
            <el-option label="月度" value="月度" />
          </el-select>
        </div>

        <!-- 预测时间长度 -->
        <div class="form-group small-input" :disabled="isConfigured">
          <label>预测时间长度</label>
          <el-input-number v-model="numFeatures" :min="1" :controls="false" class="small-number" :disabled="isConfigured" />
        </div>

        <!-- 选择起点 -->
        <div class="form-group">
          <label>选择起点</label>
          <el-select v-model="selectedFrom" placeholder="请选择起点" class="large-select">
            <el-option v-for="city in cities" :key="'from-'+city" :label="city" :value="city" />
          </el-select>
        </div>

        <!-- 选择终点 -->
        <div class="form-group">
          <label>选择终点</label>
          <el-select v-model="selectedTo" placeholder="请选择终点" class="large-select">
            <el-option v-for="city in cities" :key="'to-'+city" :label="city" :value="city" />
          </el-select>
        </div>

        <!-- 选择模型 -->
        <div class="form-group">
          <label>选择模型</label>
          <el-select v-model="modelType" placeholder="选择模型" class="large-select">
            <el-option label="选择最优模型" value="选择最优模型" />
            <el-option label="ARIMA" value="ARIMA" />
            <el-option label="LSTM" value="LSTM" />
            <el-option label="Prophet" value="Prophet" />
          </el-select>
        </div>

        <!-- 按钮行 -->
        <div class="button-row">
          <el-button type="primary" class="run-btn" @click="addTask">添加预测任务</el-button>
          <el-button type="success" class="run-btn" @click="runForecast">运行预测</el-button>
        </div>

        <!-- 已选任务列表 -->
        <div class="task-list" v-if="tasks.length">
          <h3>已选预测任务</h3>
          <div v-for="(task, index) in tasks" :key="index" class="task-item">
            <div class="task-route">
              <span><strong>{{ task.from }} → {{ task.to }}</strong></span>
            </div>
            <div class="task-config">
              <span>模型：{{ task.modelType }}</span>
              <el-button size="mini" type="danger" @click="removeTask(index)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧图表和结果 -->
      <div class="result-area">
        <div class="chart-header">
          <el-checkbox v-model="showTrain">显示历史数据</el-checkbox>
        </div>
        <div class="chart-area" ref="chartRef"></div>

        <div class="stat-card">
          <h3>预测性能指标</h3>
          <el-table
            v-if="performanceTable.length"
            :data="performanceTable"
            stripe
            style="max-width:100%; overflow-x:auto; display:block;"
            :header-cell-style="{background:'#f5f7fa'}"
          >
            <el-table-column prop="route" label="航线" min-width="180" />
            <el-table-column prop="model" label="模型" width="150" />
            <el-table-column prop="r2" label="R²" width="100" />
            <el-table-column prop="mape" label="MAPE (%)" width="100" />
            <el-table-column prop="rmse" label="RMSE" width="120" />
          </el-table>
          <div v-else class="empty-wrap">
            <el-empty description="暂无预测结果" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const cities = ['北京', '上海', '广州', '深圳', '成都', '杭州']
const selectedFrom = ref('')
const selectedTo = ref('')
const timeRange = ref('月度')
const numFeatures = ref(3)
const modelType = ref('ARIMA')
const showTrain = ref(true)
const isConfigured = ref(false) // Track if timeRange and numFeatures have been configured
const tasks = ref([])
const performanceTable = ref([])

const chartRef = ref(null)
let chartInstance = null

// 检查输入是否完整
function validateInputs() {
  if (!selectedFrom.value || !selectedTo.value || !timeRange.value || !numFeatures.value || !modelType.value) {
    alert('请完整配置起点、终点、时间粒度、时间长度和模型')
    return false
  }
  if (selectedFrom.value === selectedTo.value) {
    alert('起点和终点不能相同')
    return false
  }
  return true
}

// 添加预测任务
function addTask() {
  if (!validateInputs()) return
  if (!isConfigured.value) {
    isConfigured.value = true // Mark configuration as done after the first task
  }
  const exists = tasks.value.some(r => r.from === selectedFrom.value && r.to === selectedTo.value)
  if (!exists) {
    tasks.value.push({
      from: selectedFrom.value,
      to: selectedTo.value,
      modelType: modelType.value,
    })
  }
}

// 删除预测任务
function removeTask(index) {
  tasks.value.splice(index, 1)
  if (tasks.value.length === 0) {
    isConfigured.value = false // Reset configuration if all tasks are removed
  }
}

// 生成日期标签
function generateDateLabels(trainLen, predictLen, timeRange) {
  const baseDate = getBaseDate()
  const totalLen = trainLen + predictLen
  let labels = []

  for (let i = 0; i < totalLen; i++) {
    let date
    if (timeRange === '年度') {
      date = new Date(baseDate.getFullYear() - totalLen + i + 1, 0, 1)
      labels.push(`${date.getFullYear()}年`)
    } else if (timeRange === '季度') {
      const curYear = baseDate.getFullYear()
      const curMonth = baseDate.getMonth()
      const curQuarter = Math.floor(curMonth / 3) + 1
      const startQuarterNum = (curYear * 4 + curQuarter) - totalLen + i + 1
      const year = Math.floor(startQuarterNum / 4)
      let quarter = startQuarterNum % 4
      if (quarter === 0) {
        quarter = 4
      }
      labels.push(`${year}Q${quarter}`)
    } else {
      date = addMonths(baseDate, i - totalLen)
      labels.push(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`)
    }
  }
  return labels
}

// 获取基础日期
function getBaseDate() {
  const d = new Date()
  d.setDate(1)
  d.setHours(0, 0, 0, 0)
  return d
}

// 增加月份
function addMonths(date, months) {
  const d = new Date(date)
  d.setMonth(d.getMonth() + months)
  return d
}

// 模拟API请求
function mockApiRequest() {
  return new Promise(resolve => {
    setTimeout(() => {
      const trainLen = 5
      const predictLen = numFeatures.value
      const totalLen = trainLen + predictLen

      const allLabels = generateDateLabels(trainLen, predictLen, timeRange.value)
      const labelsToShow = showTrain.value ? allLabels : allLabels.slice(trainLen)

      const series = []
      const performance = []

      tasks.value.forEach(task => {
        const trainData = Array.from({ length: trainLen }, () => Math.round(Math.random() * 800 + 200))
        const predictData = Array.from({ length: predictLen }, () => Math.round(Math.random() * 800 + 200))

        if (showTrain.value) {
          series.push({
            name: `${task.from} → ${task.to} (${task.modelType})`, // Modified legend name to include model
            type: 'line',
            smooth: true,
            data: [...trainData, ...Array(predictLen).fill(null)],
            lineStyle: { type: 'solid' }
          })
          series.push({
            name: `${task.from} → ${task.to} (${task.modelType})`, // Modified legend name to include model
            type: 'line',
            smooth: true,
            data: [...Array(trainLen).fill(null), ...predictData],
            lineStyle: { type: 'dashed' }
          })
        } else {
          series.push({
            name: `${task.from} → ${task.to} (${task.modelType})`, // Modified legend name to include model
            type: 'line',
            smooth: true,
            data: predictData,
            lineStyle: { type: 'solid' }
          })
        }

        performance.push({
          route: `${task.from} → ${task.to}`,
          model: task.modelType,
          r2: (Math.random() * 0.3 + 0.7).toFixed(3),
          mape: (Math.random() * 10 + 5).toFixed(2),
          rmse: (Math.random() * 50 + 100).toFixed(2)
        })
      })

      resolve({
        timeLabels: labelsToShow,
        series,
        performance
      })
    }, 800)
  })
}

// 渲染图表
function renderChart(timeLabels = [], seriesData = []) {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()

  if (!seriesData.length) {
    chartInstance.setOption({
      graphic: [{ type: 'text', left: 'center', top: 'center', style: { text: '暂无预测结果', fontSize: 18, fill: '#9aa4ad' } }]
    })
    return
  }

  chartInstance.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { type: 'scroll', data: [...new Set(seriesData.map(s => s.name))], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: timeLabels, axisLabel: { rotate: 0 } },
    yAxis: { type: 'value' },
    series: seriesData
  })
}

async function runForecast() {
  if (!tasks.value.length) {
    alert('请先添加至少一条预测任务')
    return
  }

  const { timeLabels, series, performance } = await mockApiRequest()
  renderChart(timeLabels, series)
  performanceTable.value = performance
}

watch(showTrain, async () => {
  if (!tasks.value.length) return
  const { timeLabels, series, performance } = await mockApiRequest()
  renderChart(timeLabels, series)
  performanceTable.value = performance
})

onMounted(() => {
  renderChart([], [], [])
  window.addEventListener('resize', () => chartInstance?.resize())
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.forecast-container {
  padding: 1rem 2rem;
  width: 100%;
}

.forecast-content {
  display: flex;
  gap: 2rem;
  margin-top: 1rem;
}

.control-panel {
  flex: 0 0 320px;
  background: #ffffff;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.panel-title {
  margin-top: 0;
  margin-bottom: 0.6rem;
  font-size: 1.15rem;
  font-weight: 600;
  color: #2c3e50;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  color: #34495e;
  font-weight: 600;
}

.button-row {
  display: flex;
  justify-content: space-between;
  gap: 4%;
  margin-top: 0.6rem;
}

.run-btn {
  width: 48%;
  display: inline-flex;
  justify-content: center;
  align-items: center;
}

.task-list {
  margin-top: 0.8rem;
}

.task-item {
  margin-bottom: 1rem;
}

.task-route {
  font-size: 1rem;
  font-weight: bold;
}

.task-config {
  font-size: 0.9rem;
  color: #7f8c8d;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.chart-header {
  padding-bottom: 0.6rem;
  display: flex;
  justify-content: flex-start;
  align-items: center;
  background: #ffffff;
  border-radius: 8px 8px 0 0;
  padding-left: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.chart-area {
  height: 420px;
  background: #f8f9fa;
  border-radius: 0 0 8px 8px;
  padding: 8px;
}

.stat-card {
  background: #ffffff;
  border-radius: 8px;
  padding: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  max-width: 100%;
  overflow-x: auto;
}

.stat-card h3 {
  margin: 0 0 8px 0;
  color: #7f8c8d;
  font-size: 1rem;
}

.empty-wrap {
  padding: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
}

@media (max-width: 900px) {
  .forecast-content {
    flex-direction: column;
  }
  .control-panel {
    width: 100%;
  }
}
</style>