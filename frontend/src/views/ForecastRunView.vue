<template>
  <div class="model-container">
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
            <label>航线起点</label>
            <el-cascader
              v-model="selectedFrom"
              :options="locationOptions"
              :props="cascaderProps"
              placeholder="请选择起点城市"
              class="large-select"
              clearable
            />
          </div>

          <!-- 选择终点 -->
          <div class="form-group">
            <label>航线终点</label>
            <el-cascader
              v-model="selectedTo"
              :options="locationOptions"
              :props="cascaderProps"
              placeholder="请选择终点城市"
              class="large-select"
              clearable
            />
          </div>

          <!-- 按钮行 -->
          <div class="button-row">
            <el-button type="primary" class="run-btn" @click="openModelDialog">选择预测模型</el-button>
            <el-button type="success" class="run-btn" @click="runForecast">运行预测</el-button>
          </div>

          <!-- 已选预测任务 -->
          <div class="task-list" v-if="tasks.length">
            <h3>已选预测任务</h3>
            <div v-for="(task, index) in tasks" :key="index" class="task-item">
              <div class="task-route">
                <span><strong>{{ task.from }} → {{ task.to }}</strong></span>
              </div>
              <div class="task-config">
                <div class="task-info">
                  <template v-if="task.hierarchical">
                    <div>层级校正</div>
                    <div>月度模型：{{ task.monthlyModel }}</div>
                    <div>季度模型：{{ task.quarterlyModel }}</div>
                    <div v-if="task.economic_tail_method === 'linear'">
                      经济指标预测：线性回归
                    </div>
                    <div v-else-if="task.economic_tail_method === 'growth_rate'">
                      经济指标预测：增长率 {{ task.economic_growth_rate}}%
                    </div>
                  </template>
                  <template v-else>
                    <div>模型：{{ task.modelType }}</div>
                    <div v-if="task.economic_tail_method === 'linear'">
                      经济指标预测：线性回归
                    </div>
                    <div v-else-if="task.economic_tail_method === 'growth_rate'">
                      经济指标预测：增长率 {{ task.economic_growth_rate}}%
                    </div>
                  </template>
                </div>
                <el-button size="small" type="danger" @click="removeTask(index)">删除</el-button>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧图表和结果 -->
        <div class="result-area">
          <div class="chart-header" style="display: flex; align-items: center; justify-content: space-between; padding-right: 10px;">
            <el-checkbox v-model="showTrain">显示历史数据</el-checkbox>
            <el-button 
              type="primary" 
              size="small" 
              :disabled="!forecastResults.length || showProcessing" 
              @click="updateForecastResult"
            >
              更新预测结果
            </el-button>
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
              <el-table-column 
                prop="mae" 
                label="MAE" 
                min-width="100"
                :formatter="(row) => row.mae != null ? Number(row.mae).toFixed(2) : '-'"
              />
              <el-table-column 
                prop="rmse" 
                label="RMSE" 
                min-width="100"
                :formatter="(row) => row.rmse != null ? Number(row.rmse).toFixed(2) : '-'"
              />
              <el-table-column 
                prop="mape" 
                label="MAPE (%)" 
                min-width="100"
                :formatter="(row) => row.mape != null ? (Number(row.mape) * 100).toFixed(2) + '%' : '-'"
              />
              <el-table-column 
                prop="r2" 
                label="R²" 
                min-width="100"
                :formatter="(row) => row.r2 != null ? Number(row.r2).toFixed(2) : '-'"
              />
            </el-table>
            <div v-else class="empty-wrap">
              <el-empty description="暂无预测结果" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 选择模型弹窗 -->
    <el-dialog v-model="showModelDialog" title="选择预测模型" width="400px">
      <el-checkbox v-model="hierarchicalMode" style="margin-bottom:16px;">
        层级预测校正（需分别选择月度和季度模型）
      </el-checkbox>
      <div v-if="hierarchicalMode">
        <div style="margin-bottom:12px;">
          <label style="font-weight:600;">月度模型</label>
          <el-select v-model="tempMonthlyModel" placeholder="选择月度模型" style="width:100%;" :disabled="loadingModels || !monthlyModels.length">
            <el-option
              v-for="m in monthlyModels"
              :key="m.model_id"
              :label="m.model_id"
              :value="m.model_id"
            >
              <template #default>
                <el-tooltip
                  effect="dark"
                  placement="right"
                  :content="`MAE: ${m.train_mae}, RMSE: ${m.train_rmse}, MAPE: ${m.train_mape}, R²: ${m.train_r2}`"
                >
                  <span>{{ m.model_id }}</span>
                </el-tooltip>
              </template>
            </el-option>
          </el-select>
          <div v-if="!loadingModels && monthlyModels.length === 0" style="margin-top:4px; color:#f56c6c; font-size:12px;">
            未找到月度模型，请先训练模型
          </div>
        </div>
        <div>
          <label style="font-weight:600;">季度模型</label>
          <el-select v-model="tempQuarterlyModel" placeholder="选择季度模型" style="width:100%;" :disabled="loadingModels || !quarterlyModels.length">
            <el-option
              v-for="m in quarterlyModels"
              :key="m.model_id"
              :label="m.model_id"
              :value="m.model_id"
            >
              <template #default>
                <el-tooltip
                  effect="dark"
                  placement="right"
                  :content="`MAE: ${m.train_mae}, RMSE: ${m.train_rmse}, MAPE: ${m.train_mape}, R²: ${m.train_r2}`"
                >
                  <span>{{ m.model_id }}</span>
                </el-tooltip>
              </template>
            </el-option>
          </el-select>
          <div v-if="!loadingModels && quarterlyModels.length === 0" style="margin-top:4px; color:#f56c6c; font-size:12px;">
            未找到季度模型，请先训练模型
          </div>
        </div>
      </div>
      <div v-else>
        <el-select v-model="tempModelType" placeholder="选择模型" style="width:100%;" :disabled="loadingModels || !models.length">
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
        <div v-if="!loadingModels && models.length === 0" style="margin-top:8px; color:#f56c6c; font-size:12px;">
          未找到可用的预测模型，请先训练模型
        </div>
      </div>

      <!-- 经济数据预测方法 -->
      <div style="margin-top:16px;">
        <label style="font-weight:600;">经济数据预测方法</label>
        <el-radio-group v-model="economic_tail_method" style="margin-top:8px;">
          <el-radio label="linear">回归预测</el-radio>
          <el-radio label="growth_rate">指定增长率</el-radio>
        </el-radio-group>

        <el-input-number
          v-if="economic_tail_method === 'growth_rate'"
          v-model="economic_growth_rate"
          placeholder="请输入增长率(%)"
          :min="0"
          :max="100"
          :step="0.1"
          style="width:100%; margin-top:8px;"
        />
      </div>
      <div v-if="loadingModels" style="margin-top:6px; font-size:12px; color:#999;">加载模型中...</div>
      <template #footer>
        <el-button @click="showModelDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmModel">确定</el-button>
      </template>
    </el-dialog>

    <!-- 处理中的提示弹窗 -->
    <el-dialog
      v-model="showProcessing"
      title="提示"
      width="300px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      align-center
    >
      <div style="text-align: center; padding: 20px;">
        <el-icon class="is-loading" size="32"><Loading /></el-icon>
        <p style="margin-top: 12px;">正在预测中，请稍候...</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'

// 城市和省份数据结构
const locationOptions = ref([])
const cascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false,
  emitPath: true,
  value: 'value',
  label: 'label',
  children: 'children'
}

// 加载城市数据
async function loadCityData() {
  try {
    const response = await fetch('/src/assets/iata_city_airport_mapping.json')
    const data = await response.json()

    const provinceMap = {}
    Object.entries(data).forEach(([iata, info]) => {
      const { province, city, airport } = info
      if (!provinceMap[province]) provinceMap[province] = {}
      if (!provinceMap[province][city]) provinceMap[province][city] = []
      provinceMap[province][city].push({
        label: airport,
        value: iata
      })
    })

    locationOptions.value = Object.entries(provinceMap).map(([province, cities]) => ({
      label: province,
      value: province,
      children: Object.entries(cities).map(([city, airports]) => ({
        label: city,
        value: city,
        children: airports
      }))
    }))
  } catch (error) {
    console.error('加载机场数据失败:', error)
    ElMessage.error('加载机场数据失败，请刷新页面重试')
  }
}

// 预测相关 state
const selectedFrom = ref('')
const selectedTo = ref('')
const timeRange = ref('年度')
const numFeatures = ref(20)
const economic_tail_method = ref('linear')
const economic_growth_rate = ref(5)
const modelType = ref('')
const models = ref([])
const loadingModels = ref(false)
const showTrain = ref(false)
const isConfigured = ref(false)
const tasks = ref([])
const forecastResults = ref([])
const performanceTable = ref([])

const showModelDialog = ref(false)
const tempModelType = ref('')
const hierarchicalMode = ref(false)
const tempMonthlyModel = ref('')
const tempQuarterlyModel = ref('')
const monthlyModels = ref([])
const quarterlyModels = ref([])

const showProcessing = ref(false)
const chartRef = ref(null)
let chartInstance = null

// 获取模型列表
async function fetchModels(granularity) {
  try {
    const originIATA = selectedFrom.value[2]
    const destinationIATA = selectedTo.value[2]
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.MODELS)
    const res = await axios.get(url, {
      params: {
        origin_airport: originIATA,
        destination_airport: destinationIATA,
        time_granularity: granularity
      },
      timeout: 10000
    })
    if (res.data.success) {
      if (res.data.data === null || res.data.data === undefined) return []
      return res.data.data.models || []
    } else {
      console.error('获取模型失败:', res.data)
      return []
    }
  } catch (error) {
    console.error('请求模型接口失败:', error)
    return []
  }
}

// 监听城市/参数变化获取模型
watch([selectedFrom, selectedTo, timeRange, numFeatures], async ([from, to, granularity, length]) => {
  if (!from || !to || !granularity || !length) {
    models.value = []
    modelType.value = ''
    return
  }
  const granularityMap = { '年度': 'yearly', '季度': 'quarterly', '月度': 'monthly' }
  const mapped = granularityMap[granularity] || 'monthly'
  loadingModels.value = true
  const result = await fetchModels(mapped)
  models.value = result || []
  loadingModels.value = false
})

// 层级模式加载月度/季度模型
watch(hierarchicalMode, async (val) => {
  if (val) {
    loadingModels.value = true
    const monthlyResult = await fetchModels('monthly')
    const quarterlyResult = await fetchModels('quarterly')
    monthlyModels.value = monthlyResult || []
    quarterlyModels.value = quarterlyResult || []
    loadingModels.value = false
  }
})

function openModelDialog() {
  if (!selectedFrom.value[2] || !selectedTo.value[2] || !timeRange.value || !numFeatures.value) {
    ElMessage.warning('请完整配置起点、终点、时间粒度和时间长度')
    return
  }
  if (selectedFrom.value[2] === selectedTo.value[2]) {
    ElMessage.warning('起点和终点不能相同')
    return
  }
  tempModelType.value = ''
  tempMonthlyModel.value = ''
  tempQuarterlyModel.value = ''
  hierarchicalMode.value = false
  showModelDialog.value = true
  loadingModels.value = true
  fetchModels({ '年度': 'yearly', '季度': 'quarterly', '月度': 'monthly' }[timeRange.value] || 'monthly')
    .then(r => { models.value = r || [] })
    .finally(() => { loadingModels.value = false })
}

function confirmModel() {
  if (hierarchicalMode.value) {
    if (!tempMonthlyModel.value || !tempQuarterlyModel.value) {
      ElMessage.warning('请分别选择月度和季度模型')
      return
    }
    modelType.value = ''
    addTask(true)
  } else {
    if (!tempModelType.value) {
      ElMessage.warning('请选择模型')
      return
    }
    modelType.value = tempModelType.value
    addTask(false)
  }
  showModelDialog.value = false
  economic_tail_method.value = 'linear'
  economic_growth_rate.value = 5
}

function addTask(isHierarchical) {
  if (!selectedFrom.value || !selectedTo.value || !timeRange.value || !numFeatures.value || (!modelType.value && !isHierarchical)) {
    ElMessage.warning('请完整配置所有参数和模型')
    return
  }
  if (selectedFrom.value === selectedTo.value) {
    ElMessage.warning('起点和终点不能相同')
    return
  }
  if (!isConfigured.value) isConfigured.value = true
  const fromCity = selectedFrom.value[2]
  const toCity = selectedTo.value[2]

  let exists;
  if (isHierarchical) {
    exists = tasks.value.some(r =>
      r.from === fromCity &&
      r.to === toCity &&
      r.hierarchical &&
      r.monthlyModel === tempMonthlyModel.value &&
      r.quarterlyModel === tempQuarterlyModel.value &&
      r.economic_tail_method === economic_tail_method.value &&
      r.economic_growth_rate === (economic_tail_method.value === 'growth_rate' ? economic_growth_rate.value : null)
    )
  } else {
    exists = tasks.value.some(r =>
      r.from === fromCity &&
      r.to === toCity &&
      !r.hierarchical &&
      r.modelType === modelType.value &&
      r.economic_tail_method === economic_tail_method.value &&
      r.economic_growth_rate === (economic_tail_method.value === 'growth_rate' ? economic_growth_rate.value : null)
    )
  }
  if (!exists) {
    if (isHierarchical) {
      tasks.value.push({
        from: fromCity,
        to: toCity,
        hierarchical: true,
        monthlyModel: tempMonthlyModel.value,
        quarterlyModel: tempQuarterlyModel.value,
        economic_tail_method: economic_tail_method.value,
        economic_growth_rate: economic_tail_method.value === 'growth_rate' ? economic_growth_rate.value : null
      })
    } else {
      tasks.value.push({
        from: fromCity,
        to: toCity,
        modelType: modelType.value,
        hierarchical: false,
        economic_tail_method: economic_tail_method.value,
        economic_growth_rate: economic_tail_method.value === 'growth_rate' ? economic_growth_rate.value : null
      })
    }
  }
}

function removeTask(index) {
  tasks.value.splice(index, 1)
  if (tasks.value.length === 0) {
    isConfigured.value = false
  }
}

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
          if (p.data != null) {
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

async function runForecast() {
  if (!tasks.value.length) {
    ElMessage.warning('请先添加至少一条预测任务')
    return
  }
  try {
    showProcessing.value = true
    const payload = {
      predictions: tasks.value.map(task => ({
        hierarchy_reconcile: task.hierarchical,
        origin_airport: task.from,
        destination_airport: task.to,
        time_granularity: timeRange.value === '年度' 
          ? 'yearly' 
          : timeRange.value === '季度' 
            ? 'quarterly' 
            : 'monthly',
        prediction_periods: numFeatures.value,
        economic_tail_method: task.economic_tail_method,
        economic_growth_rate: task.economic_tail_method === 'growth_rate'
          ? task.economic_growth_rate / 100
          : null,
        ...(task.hierarchical
          ? {
              monthly_model_id: task.monthlyModel,
              quarterly_model_id: task.quarterlyModel
            }
          : {
              model_id: task.modelType
            })
      }))
    }

    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.FORECAST)
    const res = await axios.post(url, payload)
    forecastResults.value = res.data.data || []
    renderFromResults()
  } catch (err) {
    console.error('预测失败:', err)
    ElMessage.error('预测请求失败')
  } finally {
    showProcessing.value = false
  }
}

function renderFromResults() {
  const allSeries = []
  let xLabels = []
  const performance = []

  forecastResults.value.forEach(item => {
    const { model_info, prediction_results } = item.data || {}
    const { origin_airport, destination_airport, model_type, train_mae, train_rmse, train_mape, train_r2 } = model_info || {}
    if (!prediction_results) return

    const hist = (prediction_results.historical_data || []).map(d => ({ ...d, type: 'train' }))
    const pred = (prediction_results.future_predictions || []).map(d => ({ ...d, type: 'predict' }))
    const existed = (prediction_results.existed_data || []).map(d => ({ ...d, type: 'existed' }))
    const allData = [...hist, ...pred, ...existed]

    // xLabels 按需设定，保证覆盖所有时间点
    const histTimes = hist.map(d => d.time_point)
    const predTimes = pred.map(d => d.time_point)
    const existedTimes = existed.map(d => d.time_point)

    // 取联合时间轴（去重并排序）
    xLabels = Array.from(new Set([...histTimes, ...predTimes, ...existedTimes])).sort()

    if (showTrain.value) {
      // 1. 历史+预测，历史实线，预测虚线
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Predict`,
        type: 'line',
        smooth: true,
        data: xLabels.map(time => {
          const found = hist.find(d => d.time_point === time)
          return found ? found.value : null
        }),
        lineStyle: { type: 'solid' }
      })
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Predict`,
        type: 'line',
        smooth: true,
        data: xLabels.map(time => {
          const found = pred.find(d => d.time_point === time)
          return found ? found.value : null
        }),
        lineStyle: { type: 'dashed' }
      })

      // 2. 历史+已存在，历史实线，已存在虚线
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Existed`,
        type: 'line',
        smooth: true,
        data: xLabels.map(time => {
          const found = hist.find(d => d.time_point === time)
          return found ? found.value : null
        }),
        lineStyle: { type: 'solid' },
        lineStyle: { type: 'solid', opacity: 0.5 } // 可以稍微调淡一点区分两组历史线
      })
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Existed`,
        type: 'line',
        smooth: true,
        data: xLabels.map(time => {
          const found = existed.find(d => d.time_point === time)
          return found ? found.value : null
        }),
        lineStyle: { type: 'dashed' }
      })
    } else {
      // 不显示历史，只画预测和已存在虚线
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Predict`,
        type: 'line',
        smooth: true,
        data: pred.map(d => d.value),
        lineStyle: { type: 'solid' }
      })
      allSeries.push({
        name: `${origin_airport}→${destination_airport} (${model_type}) - Existed`,
        type: 'line',
        smooth: true,
        data: existed.map(d => d.value),
        lineStyle: { type: 'solid' }
      })
    }

    performance.push({
      route: `${origin_airport} → ${destination_airport}`,
      model: model_type,
      mae: train_mae,
      rmse: train_rmse,
      mape: train_mape,
      r2: train_r2
    })
  })

  renderChart(xLabels, allSeries)
  performanceTable.value = performance
}

async function updateForecastResult() {
  if (!forecastResults.value.length) {
    ElMessage.warning('暂无预测结果，无法更新')
    return
  }

  try {
    showProcessing.value = true
    console.log('更新预测结果的请求体:', {
      time_granularity: timeRange.value,
      results: forecastResults.value
    })
  //   const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPDATE_FORECAST) // 你需要确认后端对应的接口地址
  //   const res = await axios.post(url, {
  //     forecastResults: forecastResults.value
  //   })

  //   if (res.data.success) {
  //     ElMessage.success('预测结果更新成功')
  //   } else {
  //     ElMessage.error('更新预测结果失败')
  //     console.error('更新失败：', res.data)
  //   }
  } catch (error) {
    ElMessage.error('请求更新失败')
    console.error(error)
  } finally {
    showProcessing.value = false
  }
}

watch(showTrain, async () => {
  if (performanceTable.value.length) {
    renderFromResults()
  }
})

// 生命周期 - 注意：所有 lifecycle hooks 必须在 setup 顶部调用
onMounted(() => {
  loadCityData()
  renderChart([], [])
  nextTick(() => {
    window.addEventListener('resize', () => chartInstance?.resize())
  })
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
  window.removeEventListener('resize', () => chartInstance?.resize())
})
</script>

<style scoped>
.model-container {
  padding: 1rem 2rem;
  max-width: 1600px;
  margin: 0 auto;
}

.forecast-container {
  padding: 1rem 2rem;
  width: 100%;
}

.forecast-content {
  display: flex;
  gap: 2rem;
}

.control-panel {
  flex: 0 0 320px;
  background: #fff;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
}

.panel-title {
  margin: 0 0 0.6rem 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: #2c3e50;
}

.form-group { margin-bottom: 1rem; }
.form-group label { display: block; margin-bottom: 0.4rem; color: #34495e; font-weight: 600; }

.large-select { width: 100%; min-width: 220px; box-sizing: border-box; }

.button-row { display: flex; justify-content: space-between; gap: 4%; margin-top: 0.6rem; }
.run-btn { width: 48%; display: inline-flex; justify-content: center; align-items: center; }

.task-list { margin-top: 0.8rem; }
.task-item { margin-bottom: 1rem; }
.task-route { font-size: 1rem; font-weight: bold; }
.task-config { font-size: 0.9rem; color: #7f8c8d; display: flex; justify-content: space-between; align-items: center; }

.result-area { flex: 1; display: flex; flex-direction: column; gap: 1rem; }

.chart-header { display: flex; align-items: center; justify-content: flex-start; padding: 0 0 0.6rem 8px; background: #fff; border-radius: 8px 8px 0 0; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
.chart-area { height: 420px; background: #f8f9fa; border-radius: 0 0 8px 8px; padding: 8px; }

.stat-card { background: #fff; border-radius: 8px; padding: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); max-width: 100%; overflow-x: auto; }
.stat-card h3 { margin: 0 0 8px 0; color: #7f8c8d; font-size: 1rem; }
.empty-wrap { padding: 24px; display: flex; justify-content: center; align-items: center; }

@media (max-width: 900px) {
  .forecast-content { flex-direction: column; }
  .control-panel { width: 100%; max-width: 100%; }
}
</style>