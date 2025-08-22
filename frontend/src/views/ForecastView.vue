<template>
  <div class="model-container">
    <el-tabs v-model="activeTab" type="card" stretch>
      <el-tab-pane label="数据预测" name="forecast">
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
                  :options="filteredDestinationOptions"
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

              <!-- 已选任务列表 -->
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
                      </template>
                      <template v-else>
                        <div>模型：{{ task.modelType }}</div>
                      </template>
                    </div>
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
      </el-tab-pane>
      <el-tab-pane label="模型训练" name="model">
        <div class="model-train-panel">
          <el-form
            :model="trainForm"
            ref="trainFormRef"
            label-width="120px"
            label-position="left"
            class="train-form"
          >
            <el-form-item label="选择航线" required>
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-cascader
                    v-model="trainForm.originCity"
                    :options="locationOptions"
                    :props="cascaderProps"
                    clearable
                    placeholder="请选择起点城市"
                    style="width: 100%;"
                  />
                </el-col>
                <el-col :span="12">
                  <el-cascader
                    v-model="trainForm.destinationCity"
                    :options="filteredDestinationOptions"
                    :props="cascaderProps"
                    clearable
                    placeholder="请选择终点城市"
                    style="width: 100%;"
                  />
                </el-col>
              </el-row>
            </el-form-item>

            <el-form-item label="时间粒度" required>
              <el-select v-model="trainForm.timeGranularity" clearable placeholder="请选择时间粒度" style="width: 100%;">
                <el-option label="年度" value="年度" />
                <el-option label="季度" value="季度" />
                <el-option label="月度" value="月度" />
              </el-select>
            </el-form-item>

            <el-form-item v-if="showHistoryPrediction" label="历史训练结果">
              <div class="history-prediction-table">
                <el-table
                  :data="historyPredictions"
                  stripe
                  border
                  style="width: 100%;"
                  max-height="200"
                >
                  <el-table-column prop="date" label="日期" width="160" />
                  <el-table-column label="模型" width="280">
                    <template #default="scope">
                      <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span>{{ scope.row.model }}</span>
                        <el-link type="primary" @click="showModelDetail(scope.row)">详情</el-link>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="mae" label="MAE" width="140" />
                  <el-table-column prop="mape" label="MAPE (%)" width="140" />
                  <el-table-column prop="rmse" label="RMSE" width="140" />
                </el-table>
              </div>
            </el-form-item>

            <el-form-item label="选择模型" required>
              <el-radio-group v-model="trainForm.selectedModel">
                <el-radio-button label="XGBoost" />
                <el-radio-button label="LightGBM" />
              </el-radio-group>
            </el-form-item>

            <el-form-item label="组合时序模型">
              <el-radio-group v-model="trainForm.comboModel">
                <el-radio label="">不使用</el-radio>
                <el-radio label="sarima">SARIMA</el-radio>
                <el-radio label="svr">SVR</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="模型超参数">
              <el-divider content-position="left" style="margin:16px 0 24px 0;">{{ trainForm.selectedModel }} 参数</el-divider>
              <el-row :gutter="20" align="middle" style="margin-bottom:24px;">
                <!-- XGBoost 参数 -->
                <template v-if="trainForm.selectedModel === 'XGBoost'">
                  <el-col :span="4" v-for="(item, idx) in [
                    {label:'学习率', model:'learningRate', min:0.01, max:1, step:0.01},
                    {label:'最大深度', model:'maxDepth', min:1, max:20},
                    {label:'子采样比例', model:'subsample', min:0.1, max:1, step:0.1},
                    {label:'特征采样比例', model:'colsampleBytree', min:0.1, max:1, step:0.1},
                    {label:'正则化参数', model:'regAlpha', min:0, step:0.1},
                    {label:'L2正则化', model:'regLambda', min:0, step:0.1}
                  ]" :key="idx">
                    <div class="param-label">{{ item.label }}</div>
                    <el-input-number
                      v-model="trainForm.hyperParams.xgboost[item.model]"
                      :min="item.min"
                      :max="item.max"
                      :step="item.step || 1"
                      controls-position="right"
                      style="width:100%"
                    />
                  </el-col>
                </template>

                <!-- LightGBM 参数 -->
                <template v-if="trainForm.selectedModel === 'LightGBM'">
                  <el-col :span="4" v-for="(item, idx) in [
                    {label:'学习率', model:'learningRate', min:0.01, max:1, step:0.01},
                    {label:'叶子数量', model:'numLeaves', min:10, max:500},
                    {label:'特征采样比例', model:'featureFraction', min:0.1, max:1, step:0.1},
                    {label:'数据采样比例', model:'baggingFraction', min:0.1, max:1, step:0.1},
                    {label:'最小数据量', model:'minDataInLeaf', min:1, max:100},
                    {label:'L1正则化', model:'lambdaL1', min:0, step:0.1}
                  ]" :key="idx">
                    <div class="param-label">{{ item.label }}</div>
                    <el-input-number
                      v-model="trainForm.hyperParams.lightgbm[item.model]"
                      :min="item.min"
                      :max="item.max"
                      :step="item.step || 1"
                      controls-position="right"
                      style="width:100%"
                    />
                  </el-col>
                </template>

                <!-- SARIMA 参数 -->
                <template v-if="trainForm.comboModel === 'sarima'">
                  <el-divider content-position="left" style="margin:24px 0 24px 0;">SARIMA 参数</el-divider>
                  <el-col :span="4">
                    <div class="param-label">d</div>
                    <el-input-number v-model="trainForm.hyperParams.sarima.d" :min="0" :max="3" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">p</div>
                    <el-input-number v-model="trainForm.hyperParams.sarima.p" :min="0" :max="10" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">q</div>
                    <el-input-number v-model="trainForm.hyperParams.sarima.q" :min="0" :max="10" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">季节性周期</div>
                    <el-input-number v-model="trainForm.hyperParams.sarima.seasonal" :min="1" :max="52" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4"></el-col>
                  <el-col :span="4"></el-col>
                </template>

                <!-- SVR 参数 -->
                <template v-if="trainForm.comboModel === 'svr'">
                  <el-divider content-position="left" style="margin:24px 0 24px 0;">SVR 参数</el-divider>
                  <el-col :span="4">
                    <div class="param-label">核函数</div>
                    <el-select v-model="trainForm.hyperParams.svr.kernel" placeholder="选择核函数" style="width:100%;">
                      <el-option label="rbf" value="rbf"/>
                      <el-option label="linear" value="linear"/>
                      <el-option label="poly" value="poly"/>
                      <el-option label="sigmoid" value="sigmoid"/>
                    </el-select>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">C</div>
                    <el-input-number v-model="trainForm.hyperParams.svr.C" :min="0.1" :max="100" :step="0.1" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">epsilon</div>
                    <el-input-number v-model="trainForm.hyperParams.svr.epsilon" :min="0.001" :max="1" :step="0.001" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">gamma</div>
                    <el-input-number v-model="trainForm.hyperParams.svr.gamma" :min="0.001" :max="1" :step="0.001" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4"></el-col>
                  <el-col :span="4"></el-col>
                </template>
              </el-row>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="isTraining"
                @click="openTrainingDialog"
                :disabled="isTraining || !trainForm.originCity || !trainForm.destinationCity"
              >
                开始训练
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>
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
                  :content="`MAE: ${m.test_mae}, RMSE: ${m.test_rmse}, MAPE: ${m.test_mape}, R²: ${m.test_r2}`"
                >
                  <span>{{ m.model_id }}</span>
                </el-tooltip>
              </template>
            </el-option>
          </el-select>
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
                  :content="`MAE: ${m.test_mae}, RMSE: ${m.test_rmse}, MAPE: ${m.test_mape}, R²: ${m.test_r2}`"
                >
                  <span>{{ m.model_id }}</span>
                </el-tooltip>
              </template>
            </el-option>
          </el-select>
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
      </div>
      <div v-if="loadingModels" style="margin-top:6px; font-size:12px; color:#999;">加载模型中...</div>
      <template #footer>
        <el-button @click="showModelDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmModel">确定</el-button>
      </template>
    </el-dialog>
    <!-- 训练评估结果弹窗 -->
    <el-dialog v-model="showTrainingDialog" title="模型训练评估结果" width="700px" :close-on-click-modal="false">
      <div v-if="trainingDialogLoading">模型训练中，请稍候...</div>
      <div v-else>
        <el-table :data="evaluationResults" style="margin: 24px 0;">
          <el-table-column prop="date" label="日期" />
          <el-table-column prop="model" label="模型" />
          <el-table-column prop="mae" label="MAE" />
          <el-table-column prop="mape" label="MAPE (%)" />
          <el-table-column prop="rmse" label="RMSE" />
        </el-table>
        <div style="text-align:right;">
          <el-button type="primary" @click="saveModel" :loading="savingModel" style="margin-top:16px;">保存模型</el-button>
        </div>
      </div>
    </el-dialog>
    <!-- 模型详情弹窗 -->
    <el-dialog v-model="showDetailDialog" title="模型参数详情" width="500px" :close-on-click-modal="false">
      <div v-if="detailModel">
        <el-descriptions :title="detailModel.model" :column="1" border>
          <el-descriptions-item label="日期">{{ detailModel.date }}</el-descriptions-item>
          <el-descriptions-item label="MAE">{{ detailModel.mae }}</el-descriptions-item>
          <el-descriptions-item label="MAPE">{{ detailModel.mape }}</el-descriptions-item>
          <el-descriptions-item label="RMSE">{{ detailModel.rmse }}</el-descriptions-item>
          <el-descriptions-item label="参数">
            <div v-if="detailModel.params">
              <div v-for="(val, key) in detailModel.params" :key="key">
                <strong>{{ key }}:</strong> {{ val }}
              </div>
            </div>
            <div v-else>无参数信息</div>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import * as XLSX from 'xlsx'

// 城市和省份数据结构
const cityMap = ref({})

// 省市级联选项
const locationOptions = computed(() => [
  ...Object.keys(cityMap.value).map(province => ({
    label: province,
    value: province,
    children: (cityMap.value[province] || []).map(city => ({
      label: city,
      value: city
    }))
  }))
])
const cascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false,
  emitPath: false,
  value: 'value',
  label: 'label',
  children: 'children',
}

// 加载城市数据
async function loadCityData() {
  try {
    const response = await fetch('/src/assets/城市经纬度.xlsx')
    const arrayBuffer = await response.arrayBuffer()
    const workbook = XLSX.read(arrayBuffer, { type: 'array' })
    const sheet = workbook.Sheets[workbook.SheetNames[0]]
    const data = XLSX.utils.sheet_to_json(sheet)
    const cityMapTemp = {}
    data.forEach((row) => {
      const province = row['省份']
      const city = row['城市']
      if (!cityMapTemp[province]) cityMapTemp[province] = []
      cityMapTemp[province].push(city)
    })
    cityMap.value = cityMapTemp
    locationOptions.value = Object.keys(cityMapTemp).map(province => ({
      label: province,
      value: province,
      children: cityMapTemp[province].map(city => ({
        label: city,
        value: city
      }))
    }))
  } catch (error) {
    console.error('加载城市数据失败:', error)
    alert('加载城市数据失败，请刷新页面重试')
  }
}

const filteredDestinationOptions = computed(() => {
  if (!trainForm.originCity?.length || trainForm.originCity.length !== 2) {
    return locationOptions.value
  }
  const [originProvince, originCity] = trainForm.originCity
  return locationOptions.value
    .map(province => {
      const filteredChildren = province.children.filter(city => 
        !(province.value === originProvince && city.value === originCity)
      )
      return filteredChildren.length ? { ...province, children: filteredChildren } : null
    })
    .filter(Boolean)
})

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

const showModelDialog = ref(false)
const tempModelType = ref('')
const hierarchicalMode = ref(false)
const tempMonthlyModel = ref('')
const tempQuarterlyModel = ref('')
const monthlyModels = ref([])
const quarterlyModels = ref([])

const chartRef = ref(null)
let chartInstance = null

// 获取模型列表（粒度可选）
async function fetchModels(granularity) {
  // granularity: 'monthly' | 'quarterly'
  // 真实请求可用如下代码
  // const url = api.getUrl(api.endpoints.PREDICT.FORECAST + 'models/')
  // const res = await axios.get(url, {
  //   params: {
  //     origin_airport: selectedFrom.value,
  //     destination_airport: selectedTo.value,
  //     time_granularity: granularity
  //   },
  //   timeout: api.getTimeout()
  // })
  // if (res.data.success) return res.data.data.models

  // ==== 模拟返回数据 ====
  if (granularity === 'monthly') {
    return [
      { model_id: "CAN_PEK_monthly_01", test_mae: 10000, test_rmse: 12000, test_mape: 0.03, test_r2: 0.98 },
      { model_id: "CAN_PEK_monthly_02", test_mae: 11000, test_rmse: 13000, test_mape: 0.04, test_r2: 0.97 }
    ]
  } else {
    return [
      { model_id: "CAN_PEK_quarterly_01", test_mae: 9000, test_rmse: 11000, test_mape: 0.02, test_r2: 0.99 },
      { model_id: "CAN_PEK_quarterly_02", test_mae: 9500, test_rmse: 11500, test_mape: 0.025, test_r2: 0.985 }
    ]
  }
}

// 监听城市选择变化，获取模型列表
watch([selectedFrom, selectedTo, timeRange, numFeatures], async ([from, to, granularity, length]) => {
  if (!from || !to || !granularity || !length) {
    models.value = []
    modelType.value = ''
    return
  }

  const granularityMap = { '年度': 'yearly', '季度': 'quarterly', '月度': 'monthly' }
  const mappedGranularity = granularityMap[granularity] || 'monthly'

  loadingModels.value = true
  models.value = await fetchModels(mappedGranularity)
  loadingModels.value = false
})

// 层级模式切换时加载月度和季度模型
watch(hierarchicalMode, async (val) => {
  if (val) {
    loadingModels.value = true
    monthlyModels.value = await fetchModels('monthly')
    quarterlyModels.value = await fetchModels('quarterly')
    loadingModels.value = false
  }
})

// 校验输入并弹窗
async function openModelDialog() {
  if (!selectedFrom.value || !selectedTo.value || !timeRange.value || !numFeatures.value) {
    alert('请完整配置起点、终点、时间粒度和时间长度')
    return
  }
  if (selectedFrom.value === selectedTo.value) {
    alert('起点和终点不能相同')
    return
  }
  tempModelType.value = ''
  tempMonthlyModel.value = ''
  tempQuarterlyModel.value = ''
  hierarchicalMode.value = false
  showModelDialog.value = true
  loadingModels.value = true
  models.value = await fetchModels(
    { '年度': 'yearly', '季度': 'quarterly', '月度': 'monthly' }[timeRange.value] || 'monthly'
  )
  loadingModels.value = false
}

// 确认选择模型并添加任务
function confirmModel() {
  if (hierarchicalMode.value) {
    if (!tempMonthlyModel.value || !tempQuarterlyModel.value) {
      alert('请分别选择月度和季度模型')
      return
    }
    modelType.value = ''
    addTask(true)
  } else {
    if (!tempModelType.value) {
      alert('请选择模型')
      return
    }
    modelType.value = tempModelType.value
    addTask(false)
  }
  showModelDialog.value = false
}

function addTask(isHierarchical) {
  if (!selectedFrom.value || !selectedTo.value || !timeRange.value || !numFeatures.value || (!modelType.value && !isHierarchical)) {
    alert('请完整配置所有参数和模型')
    return
  }
  if (selectedFrom.value === selectedTo.value) {
    alert('起点和终点不能相同')
    return
  }
  if (!isConfigured.value) isConfigured.value = true
  const fromCity = selectedFrom.value
  const toCity = selectedTo.value
  // 判断是否完全重复
  let exists;
  if (isHierarchical) {
    exists = tasks.value.some(r =>
      r.from === fromCity &&
      r.to === toCity &&
      r.hierarchical &&
      r.monthlyModel === tempMonthlyModel.value &&
      r.quarterlyModel === tempQuarterlyModel.value
    )
  } else {
    exists = tasks.value.some(r =>
      r.from === fromCity &&
      r.to === toCity &&
      !r.hierarchical &&
      r.modelType === modelType.value
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
      })
    } else {
      tasks.value.push({
        from: fromCity,
        to: toCity,
        modelType: modelType.value,
        hierarchical: false,
      })
    }
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

// 运行预测
async function runForecast() {
  if (!tasks.value.length) {
    alert('请先添加至少一条预测任务')
    return
  }

  try {
    // 真实请求（目前注释掉，前端直接使用静态数据）
    // const url = api.getUrl(api.endpoints.PREDICT.FORECAST + 'run/')
    // const res = await axios.post(url, { predictions: tasks.value }, { timeout: api.getTimeout() })
    
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

// 新增模型训练tab相关变量和方法（与ManagementView一致）
const activeTab = ref('forecast')
const isTraining = ref(false)
const evaluationResults = ref([])
const historyPredictions = ref([])

const trainForm = reactive({
  originCity: [],
  destinationCity: [],
  timeGranularity: '',
  selectedModel: 'XGBoost',
  comboModel: '', // '', 'sarima', 'svr'
  hyperParams: {
    xgboost: {
      learningRate: 0.1,
      maxDepth: 6,
      subsample: 0.8,
      colsampleBytree: 0.8,
      regAlpha: 0,
      regLambda: 1
    },
    lightgbm: {
      learningRate: 0.1,
      numLeaves: 31,
      featureFraction: 0.8,
      baggingFraction: 0.8,
      minDataInLeaf: 20,
      lambdaL1: 0
    },
    sarima: {
      d: 1,
      p: 1,
      q: 1,
      seasonal: 12
    },
    svr: {
      kernel: 'rbf',
      C: 1,
      epsilon: 0.1,
      gamma: 0.1
    }
  }
})

const showTrainingDialog = ref(false)
const trainingDialogLoading = ref(false)
const savingModel = ref(false)
const showDetailDialog = ref(false)
const detailModel = ref(null)

function showModelDetail(row) {
  let params = {}
  if (row.model.includes('XGBoost')) {
    params = { ...trainForm.hyperParams.xgboost }
  } else if (row.model.includes('LightGBM')) {
    params = { ...trainForm.hyperParams.lightgbm }
  }
  if (row.model.includes('SARIMA')) {
    params = { ...params, ...trainForm.hyperParams.sarima }
  }
  if (row.model.includes('SVR')) {
    params = { ...params, ...trainForm.hyperParams.svr }
  }
  detailModel.value = { ...row, params }
  showDetailDialog.value = true
}

const showHistoryPrediction = computed(() => {
  return trainForm.originCity?.length === 2 && 
         trainForm.destinationCity?.length === 2 && 
         !!trainForm.timeGranularity
})

watch(
  () => trainForm.originCity,
  (newVal) => {
    if (!newVal?.length || newVal.length !== 2) {
      trainForm.destinationCity = []
      trainForm.timeGranularity = ''
      historyPredictions.value = []
    }
  },
  { immediate: true }
)

watch(
  () => trainForm.destinationCity,
  (newVal) => {
    if (!newVal?.length || newVal.length !== 2) {
      trainForm.timeGranularity = ''
      historyPredictions.value = []
      return
    }
    if (
      trainForm.originCity?.length === 2 &&
      newVal.length === 2 &&
      trainForm.originCity[0] === newVal[0] &&
      trainForm.originCity[1] === newVal[1]
    ) {
      trainForm.destinationCity = []
      alert('起点和终点城市不能相同！')
    }
  },
  { immediate: true }
)

watch(
  [() => trainForm.originCity, () => trainForm.destinationCity, () => trainForm.timeGranularity],
  ([originArr, destinationArr, granularity]) => {
    if (!originArr?.length || !destinationArr?.length || !granularity) {
      historyPredictions.value = []
      return
    }
    const origin = originArr
    const destination = destinationArr
    if (origin && destination && granularity) {
      loadHistoryPredictions(origin, destination, granularity)
    }
  },
  { immediate: true, deep: true }
)

async function loadHistoryPredictions(origin, destination, granularity) {
  try {
    historyPredictions.value = [
      { 
        date: '2024-01', 
        model: `${origin}-${destination} XGBoost`, 
        mae: (Math.random() * 5 + 15).toFixed(2), 
        mape: (Math.random() * 1 + 1.5).toFixed(2), 
        rmse: (Math.random() * 5 + 20).toFixed(2) 
      },
      { 
        date: '2024-01', 
        model: `${origin}-${destination} LightGBM`, 
        mae: (Math.random() * 5 + 15).toFixed(2), 
        mape: (Math.random() * 1 + 1.5).toFixed(2), 
        rmse: (Math.random() * 5 + 20).toFixed(2)
      },
      { 
        date: '2024-01', 
        model: `${origin}-${destination} XGBoost+SARIMA`, 
        mae: (Math.random() * 5 + 10).toFixed(2), 
        mape: (Math.random() * 0.8 + 1).toFixed(2), 
        rmse: (Math.random() * 5 + 15).toFixed(2)
      },
      { 
        date: '2024-01', 
        model: `${origin}-${destination} LightGBM+SARIMA`, 
        mae: (Math.random() * 5 + 10).toFixed(2), 
        mape: (Math.random() * 0.8 + 1).toFixed(2), 
        rmse: (Math.random() * 5 + 15).toFixed(2)
      }
    ]
  } catch (error) {
    console.error('加载历史预测结果失败:', error)
    historyPredictions.value = []
  }
}

function openTrainingDialog() {
  if (
    !trainForm.originCity?.length ||
    !trainForm.destinationCity?.length
  ) {
    alert('请选择起点和终点城市')
    return
  }
  if (!trainForm.timeGranularity) {
    alert('请选择时间粒度')
    return
  }
  showTrainingDialog.value = true
  startTraining()
}

async function startTraining() {
  isTraining.value = true
  trainingDialogLoading.value = true
  evaluationResults.value = []
  try {
    await new Promise(resolve => setTimeout(resolve, 2000))
    let modelName = trainForm.selectedModel
    if (trainForm.comboModel === 'sarima') {
      modelName += '+SARIMA'
    } else if (trainForm.comboModel === 'svr') {
      modelName += '+SVR'
    }
    evaluationResults.value = [{
      date: new Date().toISOString().slice(0, 10),
      model: modelName,
      mae: (Math.random() * 10 + 10).toFixed(2),
      mape: (Math.random() * 3 + 1).toFixed(2),
      rmse: (Math.random() * 15 + 15).toFixed(2)
    }]
  } catch (error) {
    alert('训练失败')
  } finally {
    isTraining.value = false
    trainingDialogLoading.value = false
  }
}

async function saveModel() {
  savingModel.value = true
  try {
    setTimeout(() => {
      showTrainingDialog.value = false
      savingModel.value = false
    }, 1000)
  } catch (e) {
    alert('保存失败')
    savingModel.value = false
  }
}

onMounted(() => {
  loadCityData()
  renderChart([], [], [])
  window.addEventListener('resize', () => chartInstance?.resize())
})

onBeforeUnmount(() => {
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
/* ===== 容器基础布局 ===== */
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
  /* margin-top: 1rem; */
}

/* ===== 左侧控制面板 ===== */
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

.form-group {
  margin-bottom: 1rem;
}
.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  color: #34495e;
  font-weight: 600;
}

.large-select {
  width: 100%;
  min-width: 220px;
  box-sizing: border-box;
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

/* ===== 右侧结果区域 ===== */
.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 0 0 0.6rem 8px;
  background: #fff;
  border-radius: 8px 8px 0 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.chart-area {
  height: 420px;
  background: #f8f9fa;
  border-radius: 0 0 8px 8px;
  padding: 8px;
}

.stat-card {
  background: #fff;
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

/* ===== 模型训练面板 ===== */
.model-train-panel {
  padding: 10px 15px;
}

.param-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
  line-height: 1.5;
}

.model-params-container .el-input-number {
  width: 180px;
  height: 32px;
}

/* 历史预测结果表格 */
.history-prediction-table {
  margin-top: 10px;
}
.history-prediction-table .el-table th,
.history-prediction-table .el-table td {
  text-align: center;
  height: 40px;
  font-size: 14px;
}

/* ===== 响应式布局 ===== */
@media (max-width: 900px) {
  .forecast-content {
    flex-direction: column;
  }
  .control-panel {
    width: 100%;
    max-width: 100%;
  }
}
</style>