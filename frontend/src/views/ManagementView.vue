<template>
  <div class="manage-container">
    <el-tabs v-model="activeTab" type="card" stretch>
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
              <el-select
                v-model="trainForm.selectedRoutes"
                multiple
                filterable
                placeholder="请选择一个或多个航线"
                :options="routeOptions"
                style="width: 100%;"
              >
                <el-option
                  v-for="item in routeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="选择模型" required>
              <el-radio-group v-model="trainForm.selectedModel">
                <el-radio-button label="ARIMA" />
                <el-radio-button label="LSTM" />
                <el-radio-button label="Prophet" />
              </el-radio-group>
            </el-form-item>

            <el-form-item label="模型超参数">
              <el-row :gutter="12">
                <el-col :span="12">
                  <el-input-number
                    v-model="trainForm.hyperParams.learningRate"
                    :min="0.0001"
                    :step="0.0001"
                    label="学习率"
                    style="width: 100%;"
                    controls-position="right"
                  >
                    <template #append>学习率</template>
                  </el-input-number>
                </el-col>
                <el-col :span="12">
                  <el-input-number
                    v-model="trainForm.hyperParams.epochs"
                    :min="1"
                    label="训练轮数"
                    style="width: 100%;"
                    controls-position="right"
                  >
                    <template #append>轮次</template>
                  </el-input-number>
                </el-col>
              </el-row>

              <el-row :gutter="12" style="margin-top: 12px;">
                <el-col :span="12">
                  <el-input-number
                    v-model="trainForm.hyperParams.batchSize"
                    :min="1"
                    label="批次大小"
                    style="width: 100%;"
                    controls-position="right"
                  >
                    <template #append>批次</template>
                  </el-input-number>
                </el-col>
                <el-col :span="12">
                  <el-input-number
                    v-model="trainForm.hyperParams.dropout"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    label="Dropout"
                    style="width: 100%;"
                    controls-position="right"
                  >
                    <template #append>比例</template>
                  </el-input-number>
                </el-col>
              </el-row>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="isTraining"
                @click="startTraining"
                :disabled="isTraining || !trainForm.selectedRoutes.length"
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
              <el-table-column prop="route" label="航线" min-width="160" />
              <el-table-column prop="model" label="模型" width="120" />
              <el-table-column prop="r2" label="R²" width="100" />
              <el-table-column prop="mape" label="MAPE (%)" width="120" />
              <el-table-column prop="rmse" label="RMSE" width="120" />
            </el-table>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

// Tab
const activeTab = ref('data')

// 数据上传相关
const fileList = ref([])
const previewData = ref([])
const previewColumns = ref([])

function downloadTemplate() {
  // 模板CSV示例，前端直接生成下载文件
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
  if (!isCSV) {
    alert('只能上传CSV文件')
    return false
  }
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isLt5M) {
    alert('文件大小不能超过5MB')
    return false
  }
  return true
}

function handleFileChange(file, fileListNew) {
  fileList.value = fileListNew

  // 简单读取CSV前10行做预览
  if (!file.raw) return

  const reader = new FileReader()
  reader.onload = e => {
    const text = e.target.result
    parseCSVPreview(text)
  }
  reader.readAsText(file.raw)
}

function parseCSVPreview(csvText) {
  const lines = csvText.split(/\r?\n/)
  const previewLines = lines.slice(0, 11) // 10行数据+header

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

// 模型训练相关
const routeOptions = [
  { label: '北京 → 上海', value: '北京→上海' },
  { label: '上海 → 广州', value: '上海→广州' },
  { label: '广州 → 深圳', value: '广州→深圳' },
  { label: '深圳 → 成都', value: '深圳→成都' },
  { label: '成都 → 杭州', value: '成都→杭州' }
]

const trainForm = reactive({
  selectedRoutes: [],
  selectedModel: 'ARIMA',
  hyperParams: {
    learningRate: 0.001,
    epochs: 20,
    batchSize: 32,
    dropout: 0.2
  }
})

const isTraining = ref(false)
const trainingStatus = reactive({
  visible: false,
  message: '',
  progress: null,
  status: 'success'
})

const evaluationResults = ref([])

function startTraining() {
  if (trainForm.selectedRoutes.length === 0) {
    alert('请选择至少一个航线')
    return
  }
  isTraining.value = true
  trainingStatus.visible = true
  trainingStatus.message = '训练开始...'
  trainingStatus.progress = 0
  trainingStatus.status = 'active'
  evaluationResults.value = []

  // 模拟训练过程，5秒完成
  let progress = 0
  const interval = setInterval(() => {
    progress += 10
    trainingStatus.progress = progress
    if (progress >= 100) {
      clearInterval(interval)
      trainingStatus.message = '训练完成'
      trainingStatus.status = 'success'
      isTraining.value = false

      // 生成模拟评估结果
      evaluationResults.value = trainForm.selectedRoutes.map(route => ({
        route,
        model: trainForm.selectedModel,
        r2: (Math.random() * 0.3 + 0.7).toFixed(3),
        mape: (Math.random() * 10 + 5).toFixed(2),
        rmse: (Math.random() * 50 + 100).toFixed(2)
      }))
    }
  }, 500)
}
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

/* 训练状态 */
.training-status {
  margin-bottom: 20px;
}

/* 路由列表删除按钮 */
.delete-btn {
  margin-left: 8px;
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