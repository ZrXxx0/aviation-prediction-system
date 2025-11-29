<template>
  <div class="model-container">
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

    <!-- 训练评估结果弹窗 -->
    <el-dialog v-model="showTrainingDialog" title="模型训练评估结果" width="700px" :close-on-click-modal="false">
      <div v-if="trainingDialogLoading">模型训练中，请稍候...</div>
      <div v-else>
        <el-table :data="evaluationResults" style="margin: 24px 0;">
          <el-table-column prop="test_mae" label="MAE">
            <template #default="scope">
              {{ Number(scope.row.test_mae).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="test_mape" label="MAPE (%)">
            <template #default="scope">
              {{ (Number(scope.row.test_mape) * 100).toFixed(2) }}%
            </template>
          </el-table-column>
          <el-table-column prop="test_rmse" label="RMSE">
            <template #default="scope">
              {{ Number(scope.row.test_rmse).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="test_r2" label="R²">
            <template #default="scope">
              {{ Number(scope.row.test_r2).toFixed(4) }}
            </template>
          </el-table-column>
        </el-table>
        <div style="text-align:right; display: flex; gap: 12px; justify-content: flex-end;">
          <el-button type="success" @click="downloadReport" :disabled="!reportPdfPath" style="margin-top:16px;">
            <el-icon><Download /></el-icon>
            下载训练报告
          </el-button>
          <el-button type="info" @click="downloadData" :disabled="!dataPath" style="margin-top:16px;">
            <el-icon><Download /></el-icon>
            下载数据文件
          </el-button>
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
        <p style="margin-top: 12px;">正在预测/训练中，请稍候...</p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed } from 'vue'
import axios from 'axios'
import apiConfig from '@/config/api.js'
import { Download, Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

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

// 加载城市数据（复用项目 assets JSON）
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

// 表单与状态
const trainForm = reactive({
  originCity: [],
  destinationCity: [],
  timeGranularity: '',
  selectedModel: 'XGBoost',
  comboModel: '',
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

const isTraining = ref(false)
const evaluationResults = ref([])
const historyPredictions = ref([])
const showTrainingDialog = ref(false)
const trainingDialogLoading = ref(false)
const savingModel = ref(false)
const showDetailDialog = ref(false)
const detailModel = ref(null)
const pretrainModelId = ref(null)
const reportPdfPath = ref('')
const dataPath = ref('')
const showProcessing = ref(false)

const showHistoryPrediction = computed(() => {
  return trainForm.originCity?.length === 3 &&
         trainForm.destinationCity?.length === 3 &&
         !!trainForm.timeGranularity
})

// 监听 origin/destination changes for validation & history
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
      ElMessage.warning('起点和终点城市不能相同！')
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
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.MODELS)
    const res = await axios.get(url, {
      params: {
        origin_airport: origin,
        destination_airport: destination,
        time_granularity: granularityEn
      },
      timeout: 10000
    })
    if (res.data?.success) {
      if (res.data.data === null || res.data.data === undefined) {
        historyPredictions.value = []
        return
      }
      if (res.data.data?.models && Array.isArray(res.data.data.models)) {
        historyPredictions.value = res.data.data.models.map(item => ({
          date: item.train_end_time,
          model: item.model_id,
          mae: item.test_mae,
          mape: item.test_mape,
          rmse: item.test_rmse
        }))
      } else {
        historyPredictions.value = []
      }
    } else {
      historyPredictions.value = []
    }
  } catch (error) {
    console.error('加载历史预测结果失败:', error)
    historyPredictions.value = []
  }
}

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

function openTrainingDialog() {
  if (
    !trainForm.originCity?.length ||
    !trainForm.destinationCity?.length
  ) {
    ElMessage.warning('请选择起点和终点城市')
    return
  }
  if (!trainForm.timeGranularity) {
    ElMessage.warning('请选择时间粒度')
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
    const originIATA = trainForm.originCity[2] || null
    const destIATA = trainForm.destinationCity[2] || null

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

    const payload = {
      origin: originIATA,
      destination: destIATA,
      config: {
        time_granularity: granularityEn,
        model_type: modelType,
        test_size: 12,
        add_ts_forecast: trainForm.comboModel === 'arima',
        arima_order: [
          trainForm.hyperParams.arima.p,
          trainForm.hyperParams.arima.d,
          trainForm.hyperParams.arima.q
        ],
        ...(modelType === 'xgb' ? { xgb_params: trainForm.hyperParams.xgboost } : {}),
        ...(modelType === 'lgb' ? { lgb_params: trainForm.hyperParams.lightgbm } : {})
      }
    }

    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.PRETRAIN)
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`)
    const result = await res.json()

    if (!result.success) {
      ElMessage.error('训练失败: ' + (result.message || '未知错误'))
      return
    }

    evaluationResults.value = result.training_result ? [result.training_result] : []
    pretrainModelId.value = result.record_id || null
    reportPdfPath.value = result.download_urls?.report_pdf || ''
    dataPath.value = result.download_urls?.data_path || ''
  } catch (error) {
    console.error(error)
    ElMessage.error('训练失败')
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
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.TRAIN)
    const response = await axios.post(url, payload)
    if (response.data.success) {
      showTrainingDialog.value = false
      ElMessage.success('模型保存成功')
    } else {
      ElMessage.error('保存失败: ' + (response.data.message || '未知错误'))
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('请求出错，无法保存模型')
  } finally {
    savingModel.value = false
  }
}

async function downloadReport() {
  if (!reportPdfPath.value) {
    ElMessage.warning('没有可下载的训练报告')
    return
  }
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.DOWNLOAD_TRAIN_FILE)
    const response = await axios.post(url, {
      file_path: reportPdfPath.value,
      file_type: 'report_pdf'
    }, {
      responseType: 'blob'
    })
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `训练报告_${new Date().getTime()}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(blobUrl)
  } catch (error) {
    console.error('下载训练报告失败:', error)
    ElMessage.error('下载训练报告失败')
  }
}

async function downloadData() {
  if (!dataPath.value) {
    ElMessage.warning('没有可下载的数据文件')
    return
  }
  try {
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.DOWNLOAD_TRAIN_FILE)
    const response = await axios.post(url, {
      file_path: dataPath.value,
      file_type: 'data_with_features'
    }, {
      responseType: 'blob'
    })
    const blob = new Blob([response.data], { type: 'text/csv' })
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `数据文件_${new Date().getTime()}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(blobUrl)
  } catch (error) {
    console.error('下载数据文件失败:', error)
    ElMessage.error('下载数据文件失败')
  }
}

onMounted(() => {
  loadCityData()
})

</script>

<style scoped>
.model-container {
  padding: 1rem 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.model-train-panel {
  padding: 10px 15px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}

.param-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
  line-height: 1.5;
}

.history-prediction-table {
  margin-top: 10px;
}
.history-prediction-table .el-table th,
.history-prediction-table .el-table td {
  text-align: center;
  height: 40px;
  font-size: 14px;
}

@media (max-width: 900px) {
  .model-train-panel { padding: 12px; }
}
</style>