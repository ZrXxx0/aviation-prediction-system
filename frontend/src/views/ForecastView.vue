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
          <el-select v-model="modelType" placeholder="选择模型" class="large-select" :disabled="loadingModels || !models.length">
            <el-option
              v-for="m in models"
              :key="m.model_id"
              :label="m.model_id"
              :value="m.model_id"
            >
              <template #default>
                <el-tooltip
                  effect="dark"
                  placement="right"
                  :content="`MAE: ${m.test_mae}, RMSE: ${m.test_rmse}, MAPE: ${m.test_mape}, R²: ${m.test_r2}`"
                >
                  <span>{{ m.model_id }}</span>
                </el-tooltip>
              </template>
            </el-option>
          </el-select>
          <div v-if="loadingModels" style="margin-top:6px; font-size:12px; color:#999;">加载模型中...</div>
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
            <el-table-column prop="model" label="模型" min-width="150" />
            <el-table-column prop="mae" label="MAE" min-width="100" />
            <el-table-column prop="rmse" label="RMSE" min-width="100" />
            <el-table-column prop="mape" label="MAPE (%)" min-width="100" />
            <el-table-column prop="r2" label="R²" min-width="100" />
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
import axios from 'axios'

const cities = ['北京', '上海', '广州', '深圳', '成都', '杭州']
const selectedFrom = ref('')
const selectedTo = ref('')
const timeRange = ref('月度')
const numFeatures = ref(3)
const modelType = ref('')
const models = ref([])
const loadingModels = ref(false)
const showTrain = ref(true)
const isConfigured = ref(false)
const tasks = ref([])
const performanceTable = ref([])

const chartRef = ref(null)
let chartInstance = null

watch([selectedFrom, selectedTo, timeRange, numFeatures], async ([from, to, granularity, length]) => {
  if (!from || !to || !granularity || !length) {
    models.value = []
    modelType.value = ''   // 清空选择的模型
    return
  }

  const granularityMap = { '年度': 'yearly', '季度': 'quarterly', '月度': 'monthly' }
  const mappedGranularity = granularityMap[granularity] || 'monthly'

  loadingModels.value = true
  try {
    // 真实请求
    // const res = await axios.get(`/predict/forecast/models/`, {
    //   params: {
    //     origin_airport: from,
    //     destination_airport: to,
    //     time_granularity: mappedGranularity
    //   }
    // })
    // if (res.data.success) {
    //   models.value = res.data.data.models
    // }

    // ==== 模拟返回数据 ====
    models.value = [
      {"model_id": "CAN_PEK_20250813233015", "train_mae": 33651.78, "train_rmse": 41485.83, "train_mape": 0.02, "train_r2": 1.0, "test_mae": 66841.01, "test_rmse": 67048.82, "test_mape": 0.05, "test_r2": -2.6, "train_start_time": "2011-01-01", "train_end_time": "2024-01-01", "composite_score": 0.3998}]
    
    modelType.value = ''   // 每次重新获取模型列表时清空选择
  } catch (err) {
    console.error('获取模型失败:', err)
    models.value = []
    modelType.value = ''
  } finally {
    loadingModels.value = false
  }
})

// 检查输入
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

// 添加任务
function addTask() {
  if (!validateInputs()) return
  if (!isConfigured.value) isConfigured.value = true
  const exists = tasks.value.some(r => r.from === selectedFrom.value && r.to === selectedTo.value)
  if (!exists) {
    tasks.value.push({
      from: selectedFrom.value,
      to: selectedTo.value,
      modelType: modelType.value,
    })
  }
}

// 删除任务
function removeTask(index) {
  tasks.value.splice(index, 1)
  if (tasks.value.length === 0) {
    isConfigured.value = false
  }
}

// 渲染图表
function renderChart(timeLabels = [], seriesData = []) {
  if (!chartRef.value) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)
  chartInstance.clear()

  if (!seriesData.length) {
    chartInstance.setOption({
      graphic: [{
        type: 'text',
        left: 'center',
        top: 'center',
        style: { text: '暂无预测结果', fontSize: 18, fill: '#9aa4ad' }
      }]
    })
    return
  }

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: function (params) {
        const time = params[0].axisValue
        let tooltipText = time + '<br/>'
        params.forEach(p => {
          if (p.data != null) { // 只显示有值的点
            tooltipText += `<span style="display:inline-block;width:10px;height:10px;background-color:${p.color};margin-right:5px;border-radius:50%"></span> ${p.seriesName}: ${p.data}<br/>`
          }
        })
        return tooltipText
      }
    },
    legend: {
      type: 'scroll',
      data: [...new Set(seriesData.map(s => s.name))],
      bottom: 0
    },
    grid: { left: '3%', right: '4%', bottom: '12%', containLabel: true },
    xAxis: { type: 'category', data: timeLabels, axisLabel: { rotate: 0 } },
    yAxis: { type: 'value' },
    series: seriesData
  })
}

// 运行预测
async function runForecast() {
  if (!tasks.value.length) {
    alert('请先添加至少一条预测任务')
    return
  }

  try {
    // 真实请求
    // const res = await axios.post(`/predict/forecast/run`, { tasks: tasks.value })
    // if (res.data.success) {
    // }
    // ==== 静态模拟返回数据 ====
    const res = {
      success: true,
      data: [
        {
          model_info: {
            origin_airport: "CAN",
            destination_airport: "PEK",
            model_id: "CAN_PEK_20250813233015",
            model_type: "lgb",
            train_mae: 33651.78,
            train_rmse: 41485.83,
            train_mape: 0.02,
            train_r2: 1.0,
            test_mae: 66841.01,
            test_rmse: 67048.82,
            test_mape: 0.05,
            test_r2: -2.6
          },
          prediction_results: {
            historical_data: [
              { time_point: "2024-01", value: 7645 },
              { time_point: "2024-02", value: 28280 },
              { time_point: "2024-03", value: 8280 },
              { time_point: "2024-04", value: 9280 },
              { time_point: "2024-05", value: 23239 }
            ],
            future_predictions: [
              { time_point: "2024-06", value: 23395 },
              { time_point: "2024-07", value: 25165 },
              { time_point: "2024-08", value: 7187 }
            ]
          }
        },
        {
          model_info: {
            origin_airport: "CAN",
            destination_airport: "PVG",
            model_id: "CAN_PVG_20250813233021",
            model_type: "lgb",
            train_mae: 2818.41,
            train_rmse: 5937.08,
            train_mape: 0.03,
            train_r2: 0.99,
            test_mae: 66757.35,
            test_rmse: 73711.61,
            test_mape: 0.29,
            test_r2: -3.31
          },
          prediction_results: {
            historical_data: [
              { time_point: "2024-01", value: 14222 },
              { time_point: "2024-02", value: 13837 },
              { time_point: "2024-03", value: 14837 },
              { time_point: "2024-04", value: 16837 },
              { time_point: "2024-05", value: 14932 }
            ],
            future_predictions: [
              { time_point: "2024-06", value: 8526 },
              { time_point: "2024-07", value: 3518 },
              { time_point: "2024-08", value: 9173 }
            ]
          }
        }
      ]
    }

    const allSeries = []
    let xLabels = []
    const performance = []

    res.data.forEach(item => {
      const { origin_airport, destination_airport, model_type, test_mae, test_rmse, test_mape, test_r2 } = item.model_info
      const hist = item.prediction_results.historical_data.map(d => ({ ...d, type: 'train' }))
      const pred = item.prediction_results.future_predictions.map(d => ({ ...d, type: 'predict' }))
      const allData = [...hist, ...pred]

      const labels = allData.map(d => d.time_point)
      xLabels = showTrain.value ? labels : pred.map(d => d.time_point)

      if (showTrain.value) {
        allSeries.push({
          name: `${origin_airport}→${destination_airport} (${model_type})`,
          type: 'line',
          smooth: true,
          data: [...hist.map(d => d.value), ...Array(pred.length).fill(null)],
          lineStyle: { type: 'solid' }
        })
        allSeries.push({
          name: `${origin_airport}→${destination_airport} (${model_type})`,
          type: 'line',
          smooth: true,
          data: [...Array(hist.length).fill(null), ...pred.map(d => d.value)],
          lineStyle: { type: 'dashed' }
        })
      } else {
        allSeries.push({
          name: `${origin_airport}→${destination_airport} (${model_type})`,
          type: 'line',
          smooth: true,
          data: pred.map(d => d.value),
          lineStyle: { type: 'solid' }
        })
      }

      performance.push({
        route: `${origin_airport} → ${destination_airport}`,
        model: model_type,
        mae: test_mae,
        rmse: test_rmse,
        mape: test_mape,
        r2: test_r2
      })
    })

    renderChart(xLabels, allSeries)
    performanceTable.value = performance

  } catch (err) {
    console.error('预测失败:', err)
  }
}

watch(showTrain, async () => {
  if (performanceTable.value.length) {
    runForecast()
  }
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