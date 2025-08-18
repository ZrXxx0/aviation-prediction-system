<template>
  <div class="manage-container">
    <el-tabs v-model="activeTab" type="card" stretch>
      <!-- 模型训练 Tab -->
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

            <!-- 新增：时间粒度选择 -->
            <el-form-item label="时间粒度" required>
              <el-select v-model="trainForm.timeGranularity" clearable placeholder="请选择时间粒度" style="width: 100%;">
                <el-option label="年度" value="年度" />
                <el-option label="季度" value="季度" />
                <el-option label="月度" value="月度" />
              </el-select>
            </el-form-item>

            <!-- 历史预测结果表格：仅当航线和时间粒度都选中时显示 -->
            <el-form-item
              v-if="showHistoryPrediction"
              label="历史预测结果"
            >
              <div class="history-prediction-table">
                <el-table
                  :data="historyPredictions"
                  stripe
                  border
                  style="width: 100%;"
                  max-height="200"
                >
                  <el-table-column prop="date" label="日期" width="160" />
                  <el-table-column prop="model" label="模型" width="280" />
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

            <el-form-item label="组合模型">
              <el-checkbox v-model="trainForm.useSarima">使用SARIMA作为组合模型</el-checkbox>
            </el-form-item>

            <el-form-item label="模型超参数">
              <el-row :gutter="100">
                <!-- 左侧：主模型超参数 -->
                <el-col :span="trainForm.useSarima ? 9 : 24">
                  <el-divider content-position="left">{{ trainForm.selectedModel }} 参数</el-divider>
                  <!-- XGBoost 模型超参数 -->
                  <div v-if="trainForm.selectedModel === 'XGBoost'" class="model-params-container">
                    <el-row :gutter="12">
                      <el-col :span="24">
                        <div class="param-label">学习率</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.learningRate"
                          :min="0.01"
                          :max="1"
                          :step="0.01"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">最大深度</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.maxDepth"
                          :min="1"
                          :max="20"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" style="margin-top: 12px;">
                      <el-col :span="24">
                        <div class="param-label">子采样比例</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.subsample"
                          :min="0.1"
                          :max="1"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">特征采样比例</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.colsampleBytree"
                          :min="0.1"
                          :max="1"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" style="margin-top: 12px;">
                      <el-col :span="24">
                        <div class="param-label">正则化参数</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.regAlpha"
                          :min="0"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">L2正则化</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.xgboost.regLambda"
                          :min="0"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                  </div>

                  <!-- LightGBM 模型超参数 -->
                  <div v-if="trainForm.selectedModel === 'LightGBM'" class="model-params-container">
                    <el-row :gutter="12">
                      <el-col :span="24">
                        <div class="param-label">学习率</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.learningRate"
                          :min="0.01"
                          :max="1"
                          :step="0.01"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">叶子数量</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.numLeaves"
                          :min="10"
                          :max="500"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" style="margin-top: 12px;">
                      <el-col :span="24">
                        <div class="param-label">特征采样比例</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.featureFraction"
                          :min="0.1"
                          :max="1"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">数据采样比例</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.baggingFraction"
                          :min="0.1"
                          :max="1"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" style="margin-top: 12px;">
                      <el-col :span="24">
                        <div class="param-label">最小数据量</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.minDataInLeaf"
                          :min="1"
                          :max="100"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">L1正则化</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.lightgbm.lambdaL1"
                          :min="0"
                          :step="0.1"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                  </div>

                </el-col>

                <!-- 右侧：SARIMA 组合模型超参数 -->
                <el-col v-if="trainForm.useSarima" :span="12" :offset="3">
                  <div class="model-params-container">
                    <el-divider content-position="left">SARIMA 参数</el-divider>
                    <el-row :gutter="12">
                      <el-col :span="24">
                        <div class="param-label">差分阶数 (d)</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.sarima.d"
                          :min="0"
                          :max="3"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">自回归阶数 (p)</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.sarima.p"
                          :min="0"
                          :max="10"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                    <el-row :gutter="12" style="margin-top: 12px;">
                      <el-col :span="24">
                        <div class="param-label">移动平均阶数 (q)</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.sarima.q"
                          :min="0"
                          :max="10"
                          controls-position="right"
                        />
                      </el-col>
                      <el-col :span="24" style="margin-top: 12px;">
                        <div class="param-label">季节性周期</div>
                        <el-input-number
                          v-model="trainForm.hyperParams.sarima.seasonal"
                          :min="1"
                          :max="52"
                          controls-position="right"
                        />
                      </el-col>
                    </el-row>
                  </div>
                </el-col>
              </el-row>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="isTraining"
                @click="startTraining"
                :disabled="isTraining || !trainForm.originCity || !trainForm.destinationCity"
              >
                开始训练
              </el-button>
            </el-form-item>
          </el-form>

          <el-card class="training-status" v-if="trainingStatus.visible">
            <p><strong>训练状态：</strong> {{ trainingStatus.message }}</p>
            <el-progress
              :percentage="trainingStatus.progress"
              v-if="trainingStatus.progress !== null"
              :status="trainingStatus.status"
            ></el-progress>
          </el-card>

          <div v-if="evaluationResults.length" class="eval-result">
            <h4>训练评估结果</h4>
            <el-table
              :data="evaluationResults"
              stripe
              border
              style="width: 100%;"
              max-height="320"
            >
              <el-table-column prop="date" label="日期" width="140" />
              <el-table-column prop="model" label="模型" width="160" />
              <el-table-column prop="mae" label="MAE" width="120" />
              <el-table-column prop="mape" label="MAPE (%)" width="140" />
              <el-table-column prop="rmse" label="RMSE" width="120" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <!-- 数据管理 Tab -->
      <el-tab-pane label="数据管理" name="data">
        <div class="data-manage-panel">
          <el-button
            type="primary"
            icon="el-icon-download"
            @click="downloadTemplate"
            class="download-btn"
          >
            下载数据模板（CSV）
          </el-button>

          <el-upload
            class="upload-demo"
            drag
            multiple
            :show-file-list="true"
            :before-upload="beforeUpload"
            :on-change="handleFileChange"
            :file-list="fileList"
            :auto-upload="false"
            accept=".csv"
          >
            <i class="el-icon-upload"></i>
            <div class="el-upload__text">拖拽或点击上传CSV数据文件</div>
            <div class="el-upload__tip" slot="tip">只能上传CSV格式文件，且不超过5MB</div>
          </el-upload>

          <div v-if="previewData.length" class="preview-table">
            <h4>数据预览（前10行）</h4>
            <el-table
              :data="previewData"
              max-height="300"
              stripe
              border
              style="width: 100%;"
            >
              <el-table-column
                v-for="col in previewColumns"
                :key="col"
                :label="col"
                :prop="col"
              />
            </el-table>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed, onMounted } from 'vue'
import api from '@/config/api.js'
import * as XLSX from 'xlsx'

// 1. 基础状态管理
const activeTab = ref('model')
const isTraining = ref(false)
const fileList = ref([])
const previewData = ref([])
const previewColumns = ref([])
const evaluationResults = ref([])
const historyPredictions = ref([])

// 2. 城市数据相关
const cityMap = ref({})
const locationOptions = ref([])
const cascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false,
  emitPath: true,
  value: 'value',
  label: 'label',
  children: 'children',
}

// 3. 训练状态管理
const trainingStatus = reactive({
  visible: false,
  message: '',
  progress: null,
  status: 'success'
})

// 4. 表单数据管理
const trainForm = reactive({
  // 航线信息
  originCity: [],
  destinationCity: [],
  timeGranularity: '',
  
  // 模型选择
  selectedModel: 'XGBoost',
  useSarima: false,
  
  // 模型超参数
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
    }
  }
})

// 5. 计算属性
// 过滤终点城市选项
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

// 控制历史预测结果显示
const showHistoryPrediction = computed(() => {
  return trainForm.originCity?.length === 2 && 
         trainForm.destinationCity?.length === 2 && 
         !!trainForm.timeGranularity
})

// 6. 监听器
// 监听起点城市变化
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

// 监听终点城市变化
watch(
  () => trainForm.destinationCity,
  (newVal) => {
    if (!newVal?.length || newVal.length !== 2) {
      trainForm.timeGranularity = ''
      historyPredictions.value = []
      return
    }

    // 检查是否与起点城市相同
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

// 监听航线和时间粒度变化，加载历史预测结果
watch(
  [() => trainForm.originCity, () => trainForm.destinationCity, () => trainForm.timeGranularity],
  ([originArr, destinationArr, granularity]) => {
    if (!originArr?.length || !destinationArr?.length || !granularity) {
      historyPredictions.value = []
      return
    }

    const origin = originArr[1]
    const destination = destinationArr[1]
    
    if (origin && destination && granularity) {
      loadHistoryPredictions(origin, destination, granularity)
    }
  },
  { immediate: true, deep: true }
)

// 7. 方法定义
// 城市数据加载
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

// CSV相关功能
function downloadTemplate() {
  const csvContent =
    '航线起点,航线终点,时间,运力,运量,航班数\n北京,上海,2024-01,1000,900,30\n上海,广州,2024-01,1200,1100,28\n'
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '数据模板.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

function beforeUpload(file) {
  const isCSV = file.type === 'text/csv' || file.name.endsWith('.csv')
  const isLt5M = file.size / 1024 / 1024 < 5
  
  if (!isCSV) {
    alert('只能上传CSV文件')
    return false
  }
  if (!isLt5M) {
    alert('文件大小不能超过5MB')
    return false
  }
  
  return true
}

function handleFileChange(file, fileListNew) {
  fileList.value = fileListNew
  if (!file.raw) return
  
  const reader = new FileReader()
  reader.onload = e => {
    parseCSVPreview(e.target.result)
  }
  reader.readAsText(file.raw)
}

function parseCSVPreview(csvText) {
  const lines = csvText.split(/\r?\n/)
  const previewLines = lines.slice(0, 11)
  
  if (previewLines.length < 2) {
    previewData.value = []
    previewColumns.value = []
    return
  }
  
  const headers = previewLines[0].split(',')
  previewColumns.value = headers
  
  const rows = previewLines.slice(1).map(line => {
    const vals = line.split(',')
    const obj = {}
    headers.forEach((h, idx) => {
      obj[h] = vals[idx]
    })
    return obj
  })
  
  previewData.value = rows.filter(r => Object.values(r).some(v => v))
}

// 获取历史预测结果
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

// 开始训练模型
async function startTraining() {
  if (!trainForm.originCity?.length || !trainForm.destinationCity?.length) {
    alert('请选择起点和终点城市')
    return
  }

  isTraining.value = true
  trainingStatus.visible = true
  trainingStatus.message = '训练开始...'
  trainingStatus.progress = 0
  trainingStatus.status = 'active'
  evaluationResults.value = []

  let progress = 0
  const interval = setInterval(() => {
    progress = Math.min(progress + 10, 90)
    trainingStatus.progress = progress
  }, 500)

  try {
    const payload = {
      origin: trainForm.originCity[1],
      destination: trainForm.destinationCity[1],
      model: trainForm.selectedModel,
      useSarima: trainForm.useSarima,
      params: trainForm.hyperParams,
    }

    // 模拟训练过程
    await new Promise(resolve => setTimeout(resolve, 3000))
    
    const modelName = trainForm.useSarima ? 
      `${trainForm.selectedModel}+SARIMA` : 
      trainForm.selectedModel

    evaluationResults.value = [{
      date: new Date().toISOString().slice(0, 10),
      model: modelName,
      mae: (Math.random() * 10 + 10).toFixed(2),
      mape: (Math.random() * 3 + 1).toFixed(2),
      rmse: (Math.random() * 15 + 15).toFixed(2)
    }]

    trainingStatus.message = '训练完成'
    trainingStatus.progress = 100
    trainingStatus.status = 'success'
  } catch (error) {
    console.error('训练失败:', error)
    trainingStatus.message = '训练失败'
    trainingStatus.status = 'exception'
  } finally {
    clearInterval(interval)
    isTraining.value = false
  }
}

// 初始化
onMounted(() => {
  loadCityData()
})
</script>

<style scoped>
.manage-container {
  padding: 1rem 2rem;
  max-width: 1100px;
  margin: 0 auto;
}

/* 数据管理面板 */
.data-manage-panel {
  padding: 20px 10px;
}

.download-btn {
  margin-bottom: 20px;
  height: 32px;
  font-size: 14px;
  padding: 0 20px;
}

/* 预览表格样式 */
.preview-table h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 15px;
}

.preview-table .el-table {
  font-size: 14px;
}

.preview-table .el-table th {
  height: 40px;
  font-size: 14px;
  text-align: center;
  font-weight: 500;
}

.preview-table .el-table td {
  height: 40px;
  font-size: 14px;
  text-align: center;
}

/* 预览表格 */
.preview-table {
  margin-top: 20px;
}

/* 模型训练面板 */
.model-train-panel {
  padding: 10px 15px;
}

.train-form {
  max-width: 700px;
  margin-bottom: 20px;
}

.train-form .el-form-item {
  margin-bottom: 20px;
}

/* 统一选择框样式 */
.train-form .el-select {
  width: 100%;
}

.train-form .el-select .el-input__inner {
  height: 32px;
  line-height: 32px;
  font-size: 14px;
}

/* 统一按钮样式 */
.train-form .el-button {
  height: 32px;
  font-size: 14px;
  padding: 0 20px;
}

/* 统一单选框组样式 */
.train-form .el-radio-group .el-radio-button__inner {
  height: 32px;
  line-height: 30px;
  font-size: 14px;
  padding: 0 20px;
}

/* 统一复选框样式 */
.train-form .el-checkbox .el-checkbox__label {
  font-size: 14px;
  line-height: 32px;
}

.train-form .el-form-item__label {
  text-align: left;
  line-height: 1.4;
  font-weight: 500;
  font-size: 14px;
  height: 32px;
  display: flex;
  align-items: center;
}

/* 训练状态 */
.training-status {
  margin-bottom: 20px;
}

.training-status p {
  font-size: 14px;
  line-height: 1.4;
  margin: 0 0 10px 0;
}

/* 评估结果表格样式 */
.eval-result h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 15px;
}

.eval-result .el-table {
  font-size: 14px;
}

.eval-result .el-table th {
  height: 40px;
  font-size: 14px;
  text-align: center;
  font-weight: 500;
}

.eval-result .el-table td {
  height: 40px;
  font-size: 14px;
  text-align: center;
}

/* 路由列表删除按钮 */
.delete-btn {
  margin-left: 8px;
}

/* 超参数标签样式 */
.param-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 500;
  text-align: left;
  line-height: 1.4;
  height: 20px;
  display: flex;
  align-items: center;
}

/* 模型参数容器样式 */
.model-params-container {
  min-height: 200px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

/* 统一输入框样式 */
.model-params-container .el-input-number {
  width: 180px;
  height: 32px;
}

.model-params-container .el-input-number .el-input__inner {
  height: 32px;
  line-height: 32px;
  font-size: 14px;
}

/* 历史预测结果表格 */
.history-prediction-table {
  margin-top: 10px;
}

.history-prediction-table .el-table {
  font-size: 14px;
}

.history-prediction-table .el-table th {
  text-align: center;
  font-weight: 500;
  height: 40px;
  font-size: 14px;
}

.history-prediction-table .el-table td {
  text-align: center;
  height: 40px;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 准确率样式 */
.accuracy-high {
  color: #67c23a;
  font-weight: bold;
  text-align: center;
  font-size: 14px;
}

.accuracy-medium {
  color: #e6a23c;
  font-weight: bold;
  text-align: center;
  font-size: 14px;
}

.accuracy-low {
  color: #f56c6c;
  font-weight: bold;
  text-align: center;
  font-size: 14px;
}

@media (max-width: 900px) {
  .manage-container {
    padding: 1rem 1rem;
  }
  .train-form {
    max-width: 100%;
  }
}
</style>