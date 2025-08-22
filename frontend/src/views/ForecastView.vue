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
                  <el-table-column 
                    prop="mae" 
                    label="MAE" 
                    min-width="100"
                    :formatter="(row) => row.mae.toFixed(2)"
                  />
                  <el-table-column 
                    prop="rmse" 
                    label="RMSE" 
                    min-width="100"
                    :formatter="(row) => row.rmse.toFixed(2)"
                  />
                  <el-table-column 
                    prop="mape" 
                    label="MAPE (%)" 
                    min-width="100"
                    :formatter="(row) => (row.mape * 100).toFixed(2) + '%'"
                  />
                  <el-table-column 
                    prop="r2" 
                    label="R²" 
                    min-width="100"
                    :formatter="(row) => row.r2.toFixed(2)"
                  />
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
                    :options="locationOptions"
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
                  <el-table-column label="模型" width="300">
                    <template #default="scope">
                      <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span>{{ scope.row.model }}</span>
                        <el-link type="primary" @click="showModelDetail(scope.row)">详情</el-link>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column 
                    prop="mae" 
                    label="MAE" 
                    width="140" 
                    :formatter="(row) => row.mae.toFixed(2)"
                  />
                  <el-table-column 
                    prop="mape" 
                    label="MAPE (%)" 
                    width="140" 
                    :formatter="(row) => (row.mape * 100).toFixed(2) + '%'"
                  />
                  <el-table-column 
                    prop="rmse" 
                    label="RMSE" 
                    width="140" 
                    :formatter="(row) => row.rmse.toFixed(2)"
                  />
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
                <el-radio label="arima">ARIMA</el-radio>
                <el-radio label="svr">SVR</el-radio>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="模型超参数">
              <el-divider content-position="left" style="margin:16px 0 24px 0;">{{ trainForm.selectedModel }} 参数</el-divider>
              <el-row :gutter="20" align="middle" style="margin-bottom:24px;">
                <!-- XGBoost 参数 -->
                <template v-if="trainForm.selectedModel === 'XGBoost'">
                  <el-col :span="4" v-for="(item, idx) in [
                    {label:'提升树数量', model:'n_estimators', min:50, max:1000, step:5},
                    {label:'学习率', model:'learning_rate', min:0.01, max:0.5, step:0.05},
                    {label:'单棵树最大深度', model:'max_depth', min:2, max:20, step:1},
                    {label:'样本权重约束', model:'min_child_weight', min:1, max:10, step:1},
                    {label:'采样比例', model:'subsample', min:0.6, step:1},
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
                  <el-col :span="4"></el-col>
                </template>

                <!-- LightGBM 参数 -->
                <template v-if="trainForm.selectedModel === 'LightGBM'">
                  <el-col :span="4" v-for="(item, idx) in [
                    {label:'提升树数量', model:'n_estimators', min:5, max:1000, step:5},
                    {label:'学习率', model:'learning_rate', min:0.01, max:0.5, step:0.05},
                    {label:'单棵树最大深度', model:'max_depth', min:-1, max:20, step:1},
                    {label:'叶子节点数', model:'num_leaves', min:5, max:300, step:10},
                    {label:'叶子最小样本数', model:'min_data_in_leaf', min:5, max:100},
                    {label:'最小分裂增益阈值', model:'min_split_gain', min:0, max:1}
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

                <!-- ARIMA 参数 -->
                <template v-if="trainForm.comboModel === 'arima'">
                  <el-divider content-position="left" style="margin:24px 0 24px 0;">ARIMA 参数</el-divider>
                  <el-col :span="4">
                    <div class="param-label">d</div>
                    <el-input-number v-model="trainForm.hyperParams.arima.d" :min="0" :max="3" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">p</div>
                    <el-input-number v-model="trainForm.hyperParams.arima.p" :min="0" :max="10" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4">
                    <div class="param-label">q</div>
                    <el-input-number v-model="trainForm.hyperParams.arima.q" :min="0" :max="10" controls-position="right" style="width:100%"/>
                  </el-col>
                  <el-col :span="4"></el-col>
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
      <!-- 层级预测校正或普通模型选择 -->
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
    <!-- 训练评估结果弹窗 -->
    <el-dialog v-model="showTrainingDialog" title="模型训练评估结果" width="700px" :close-on-click-modal="false">
      <div v-if="trainingDialogLoading">模型训练中，请稍候...</div>
      <div v-else>
        <el-table :data="evaluationResults" style="margin: 24px 0;">
          <!-- MAE 保留 2 位小数 -->
          <el-table-column prop="test_mae" label="MAE">
            <template #default="scope">
              {{ Number(scope.row.test_mae).toFixed(2) }}
            </template>
          </el-table-column>
          <!-- MAPE 转百分比并保留 2 位小数 -->
          <el-table-column prop="test_mape" label="MAPE (%)">
            <template #default="scope">
              {{ (Number(scope.row.test_mape) * 100).toFixed(2) }}%
            </template>
          </el-table-column>
          <!-- RMSE 保留 2 位小数 -->
          <el-table-column prop="test_rmse" label="RMSE">
            <template #default="scope">
              {{ Number(scope.row.test_rmse).toFixed(2) }}
            </template>
          </el-table-column>
          <!-- R² 保留 4 位小数 -->
          <el-table-column prop="test_r2" label="R²">
            <template #default="scope">
              {{ Number(scope.row.test_r2).toFixed(4) }}
            </template>
          </el-table-column>
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
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'
import * as XLSX from 'xlsx'

// 城市和省份数据结构
const locationOptions = ref([])
const cascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false,
  emitPath: true,      // 返回选中完整路径
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

    // 遍历 JSON 构造省→市→机场三级结构
    Object.entries(data).forEach(([iata, info]) => {
      const { province, city, airport } = info

      if (!provinceMap[province]) provinceMap[province] = {}
      if (!provinceMap[province][city]) provinceMap[province][city] = []

      provinceMap[province][city].push({
        label: airport,   // 显示机场名
        value: iata       // 传给后端 IATA 码
      })
    })

    // 转换成 Cascader 格式
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
    alert('加载机场数据失败，请刷新页面重试')
  }
}

// 预测相关
const selectedFrom = ref('')
const selectedTo = ref('')
const timeRange = ref('月度')
const numFeatures = ref(3)
const economic_tail_method = ref('linear') // 默认回归预测
const economic_growth_rate = ref(5)    // 指定增长率
const modelType = ref('')
const models = ref([])
const loadingModels = ref(false)
const showTrain = ref(false)
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

const showProcessing = ref(false)
const chartRef = ref(null)
let chartInstance = null

// 获取模型列表（粒度可选）
async function fetchModels(granularity) {
  try {
    // 三级 Cascader 中机场 IATA 码在数组的第 3 个位置
    const originIATA = selectedFrom.value[2]
    const destinationIATA = selectedTo.value[2]

    // 接口 URL
    const url = `http://localhost:8000/predict/forecast/models/`
    const res = await axios.get(url, {
      params: {
        origin_airport: originIATA,
        destination_airport: destinationIATA,
        time_granularity: granularity
      },
      timeout: 10000 // 设置超时时间为 10 秒
    })

    if (res.data.success) {
      return res.data.data.models
    } else {
      console.error('获取模型失败:', res.data)
      return []
    }
  } catch (error) {
    console.error('请求模型接口失败:', error)
    return []
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
  if (!selectedFrom.value[2] || !selectedTo.value[2] || !timeRange.value || !numFeatures.value) {
    alert('请完整配置起点、终点、时间粒度和时间长度')
    return
  }
  if (selectedFrom.value[2] === selectedTo.value[2]) {
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
  economic_tail_method.value = 'linear' // 重置经济数据预测方法
  economic_growth_rate.value = 5 // 重置增长率
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
  const fromCity = selectedFrom.value[2]
  const toCity = selectedTo.value[2]
  // 判断是否完全重复
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
    showProcessing.value = true
    const payload = {
      predictions: tasks.value.map(task => {
        return {
          hierarchy_reconcile: task.hierarchical,
          origin_airport: task.from,   // 三字码
          destination_airport: task.to,
          time_granularity: timeRange.value === '年度' 
            ? 'yearly' 
            : timeRange.value === '季度' 
              ? 'quarterly' 
              : 'monthly',
          prediction_periods: numFeatures.value, // 预测期数
          economic_tail_method: task.economic_tail_method, // 'linear' 或 'growth_rate'
          economic_growth_rate: task.economic_tail_method === 'growth_rate'
            ? task.economic_growth_rate / 100 // 转成小数，例如 5% → 0.05
            : null,
          // 模型 ID，根据是否层级校正决定
          ...(task.hierarchical
            ? {
                monthly_model_id: task.monthlyModel,
                quarterly_model_id: task.quarterlyModel
              }
            : {
                model_id: task.modelType
              })
        }
      })
    }
    console.log('预测请求参数:', payload)
    const url = 'http://localhost:8000/predict/forecast/run/'
    const res = await axios.post(url, payload)
    console.log('预测返回结果:', res)

    // 正确的取法：res.data.data 是数组
    const results = res.data.data

    const allSeries = []
    let xLabels = []
    const performance = []

    results.forEach(item => {
      // 注意这里要从 item.data 里取
      const { model_info, prediction_results } = item.data || {}
      const { origin_airport, destination_airport, model_type, test_mae, test_rmse, test_mape, test_r2 } = model_info
      const hist = prediction_results.historical_data.map(d => ({ ...d, type: 'train' }))
      const pred = prediction_results.future_predictions.map(d => ({ ...d, type: 'predict' }))
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
    showProcessing.value = false // 请求完成后关闭
    
  } catch (err) {
    console.error('预测失败:', err)
  }
}

watch(showTrain, async () => {
  if (performanceTable.value.length) {
    runForecast()
  }
})

// 模型训练相关
const activeTab = ref('forecast')
const isTraining = ref(false)
const evaluationResults = ref([])
const historyPredictions = ref([])

const trainForm = reactive({
  originCity: [],
  destinationCity: [],
  timeGranularity: '',
  selectedModel: 'XGBoost',
  comboModel: '', // '', 'arima', 'svr'
  hyperParams: {
    xgboost: {
      n_estimators: 100,
      learning_rate: 0.1,
      max_depth: 3,
      min_child_weight: 1,
      subsample: 0.8,
    },
    lightgbm: {
      n_estimators: 100,
      learning_rate: 0.1,
      max_depth: 7,
      num_leaves: 31,
      min_data_in_leaf: 20,
      min_split_gain: 0
    },
    arima: {
      d: 1,
      p: 1,
      q: 1,
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
const pretrainModelId = ref(null)

// 显示模型详情
function showModelDetail(row) {
  let params = {}
  if (row.model.includes('XGBoost')) {
    params = { ...trainForm.hyperParams.xgboost }
  } else if (row.model.includes('LightGBM')) {
    params = { ...trainForm.hyperParams.lightgbm }
  }
  if (row.model.includes('ARIMA')) {
    params = { ...params, ...trainForm.hyperParams.arima }
  }
  if (row.model.includes('SVR')) {
    params = { ...params, ...trainForm.hyperParams.svr }
  }
  detailModel.value = { ...row, params }
  showDetailDialog.value = true
}

const showHistoryPrediction = computed(() => {
  return trainForm.originCity?.length === 3 && 
         trainForm.destinationCity?.length === 3 && 
         !!trainForm.timeGranularity
})

watch(
  () => trainForm.originCity,
  (newVal) => {
    if (!newVal?.length || newVal.length !== 3) {
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
    if (!newVal?.length || newVal.length !== 3) {
      trainForm.timeGranularity = ''
      historyPredictions.value = []
      return
    }
    if (
      trainForm.originCity?.length === 3 &&
      newVal.length === 3 &&
      trainForm.originCity[2] === newVal[2]
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
    const origin = originArr[2]
    const destination = destinationArr[2]
    if (origin && destination && granularity) {
      loadHistoryPredictions(origin, destination, granularity)
    }
  },
  { immediate: true, deep: true }
)

async function loadHistoryPredictions(origin, destination, granularity) {
  const granularityMap = {
    '年度': 'yearly',
    '季度': 'quarterly',
    '月度': 'monthly'
  }
  const granularityEn = granularityMap[granularity] || 'monthly'
  try {
    const url = 'http://localhost:8000/predict/forecast/models/'
    const res = await axios.get(url, {
      params: {
        origin_airport: origin,
        destination_airport: destination,
        time_granularity: granularityEn
      },
      timeout: 10000
    })
    console.log('历史预测结果:', res)
    if (res.data?.success && res.data.data?.models && Array.isArray(res.data.data.models)) {
      historyPredictions.value = res.data.data.models.map(item => ({
        date: item.train_end_time,    // 使用训练结束时间
        model: item.model_id,
        mae: item.test_mae,
        mape: item.test_mape,
        rmse: item.test_rmse
      }))
    } else {
      console.warn('格式异常', res)
      historyPredictions.value = []
    }
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
    // 获取三字码（假设 originCity / destinationCity 是数组 [省,市,三字码]）
    const originIATA = trainForm.originCity[2] || null
    const destIATA = trainForm.destinationCity[2] || null

    // 模型名称映射
    let modelType = ''
    if (trainForm.selectedModel == 'XGBoost'){
      modelType = 'xgb'
    } else if (trainForm.selectedModel == 'LightGBM') {
      modelType = 'lgb'
    } else {
      throw new Error('未知的模型类型: ' + trainForm.selectedModel)
    }

    const granularityMap = {
      '年度': 'yearly',
      '季度': 'quarterly',
      '月度': 'monthly'
    }
    const granularityEn = granularityMap[trainForm.timeGranularity] || 'monthly'

    // 组装 payload
    const payload = {
      origin: originIATA,
      destination: destIATA,
      config: {
        time_granularity: granularityEn,
        model_type: modelType,
        test_size: 12,
        add_ts_forecast: trainForm.comboModel === 'arima',  // 如果组合了 ARIMA，则启用
        arima_order: [
          trainForm.hyperParams.arima.p,
          trainForm.hyperParams.arima.d,
          trainForm.hyperParams.arima.q
        ],
        ...(modelType === 'xgb' ? { xgb_params: trainForm.hyperParams.xgboost } : {}),
        ...(modelType === 'lgb' ? { lgb_params: trainForm.hyperParams.lightgbm } : {})
      }
    }

    console.log("训练请求 payload:", payload)

    // 发请求
    const res = await fetch('http://localhost:8000/predict/pretrain/model/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
    const result = await res.json()

    if (!result.success) {
      alert('训练失败: ' + (result.message || '未知错误'))
      return
    }
    console.log('训练返回结果:', result)
    // 假设后端返回 { success:true, results:[{date, model, mae, mape, rmse}, ...] }
    evaluationResults.value = result.training_result ? [result.training_result] : []
    pretrainModelId.value = result.record_id || null
    console.log('评估结果:', evaluationResults.value)
    console.log('预训练记录 ID:', pretrainModelId.value)
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
    const payload = {
      pretrain_record_id: pretrainModelId.value,
      remark: "正式训练测试"
    }
    console.log("保存模型请求 payload:", payload)
    // 发送保存请求
    const response = await axios.post(
      "http://localhost:8000/predict/formal/train/",
      payload
    )

    if (response.data.success) {
      showTrainingDialog.value = false
    } else {
      alert('保存失败: ' + (response.data.message || '未知错误'))
    }
  } catch (e) {
    console.error(e)
    alert('请求出错，无法保存模型')
  } finally {
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