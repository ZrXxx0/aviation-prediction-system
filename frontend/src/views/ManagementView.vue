<template>
  <div class="manage-container">
    <el-tabs v-model="activeTab" type="card" stretch :class="{ 'disabled-tabs': showProcessing }">
      
      <!-- 数据查询 Tab -->
      <el-tab-pane label="数据查询" name="query" :disabled="showProcessing">
        <div class="query-panel">
          <el-form :model="queryForm" ref="queryFormRef" label-width="100px" inline>
            
            <el-form-item label="起点机场">
              <el-cascader
                v-model="queryForm.originCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择起点机场"
                :disabled="showProcessing"
              />
            </el-form-item>

            <el-form-item label="终点机场">
              <el-cascader
                v-model="queryForm.destinationCity"
                :options="filteredDestinationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择终点机场"
                :disabled="showProcessing"
              />
            </el-form-item>

            <el-form-item label="时间范围">
              <el-date-picker
                v-model="queryForm.dateRange"
                type="monthrange"
                start-placeholder="开始月份"
                end-placeholder="结束月份"
                value-format="YYYY-MM"
                clearable
                :disabled="showProcessing"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="searchData" :disabled="showProcessing">查询</el-button>
              <el-button @click="resetQuery" :disabled="showProcessing">重置</el-button>
            </el-form-item>
          </el-form>

          <!-- 查询结果 -->
          <div class="query-table" v-if="pagedData.length">
            <div class="toolbar">
              <el-popover placement="bottom" trigger="click" width="250px">
                <template #reference>
                  <el-button type="primary" size="small" :disabled="showProcessing">选择显示列</el-button>
                </template>

                <el-checkbox-group v-model="selectedColumns" class="column-list">
                  <el-checkbox v-for="col in allColumns" :key="col" :label="col">{{ col }}</el-checkbox>
                </el-checkbox-group>

                <div style="text-align: right; margin-top: 10px;">
                  <el-button size="small" @click="selectAllColumns">全选</el-button>
                  <el-button size="small" @click="clearAllColumns">清空</el-button>
                </div>
              </el-popover>

              <div style="display: flex; align-items: center; gap: 10px;">
                <el-pagination
                  background
                  layout="prev, pager, next, sizes, total"
                  :page-sizes="[10, 20, 50, 100]"
                  :page-size="pagination.pageSize"
                  :current-page="pagination.currentPage"
                  :total="pagination.total"
                  @size-change="handleSizeChange"
                  @current-change="handleCurrentChange"
                />
                <el-button type="success" @click="exportData" :disabled="showProcessing">
                  导出查询结果
                </el-button>
              </div>
            </div>

            <el-table :data="pagedData" border stripe style="width: 100%">
              <el-table-column
                v-for="col in selectedColumns"
                :key="col"
                :prop="col"
                :label="col"
                min-width="100"
              />
            </el-table>
          </div>

          <div v-else class="empty-data">
            <el-empty description="暂无查询结果" />
          </div>
        </div>
      </el-tab-pane>

      <!-- 数据上传 Tab -->
      <el-tab-pane label="数据上传" name="upload" :disabled="showProcessing">
        <div class="data-manage-panel">
          <el-button type="primary" @click="downloadTemplate" class="download-btn" :disabled="showProcessing">
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
            :disabled="showProcessing"
          >
            <div class="el-upload__text">拖拽或点击上传CSV数据文件</div>
            <div class="el-upload__tip">只能上传CSV格式文件，且不超过5MB</div>
          </el-upload>

          <div v-if="previewData.length" class="preview-table">
            <h4>数据预览（前10行）</h4>
            <el-table :data="previewData" max-height="300" stripe border style="width: 100%;">
              <el-table-column v-for="col in previewColumns" :key="col" :label="col" :prop="col" />
            </el-table>

            <div style="text-align: right; margin-top: 10px;">
              <el-button type="primary" @click="uploadData" :disabled="showProcessing">上传数据</el-button>
            </div>
          </div>
        </div>

        <!-- 正在处理遮罩 -->
        <el-dialog v-model="showProcessing" width="300px" :close-on-click-modal="false" :show-close="false">
          <div style="text-align: center; padding: 20px;">
            <el-icon class="is-loading" size="40"><Loading /></el-icon>
            <div style="margin-top: 10px;">正在处理数据，请稍候...</div>
          </div>
        </el-dialog>

        <!-- 确认上传 -->
        <el-dialog v-model="confirmUploadDialog" title="确认上传" width="400px">
          <span>数据检查通过，是否确认上传？</span>
          <template #footer>
            <el-button @click="confirmUploadDialog = false">取消</el-button>
            <el-button type="primary" @click="confirmUpload">确认</el-button>
          </template>
        </el-dialog>

        <!-- 冲突处理 -->
        <el-dialog v-model="conflictDialog" title="检测到数据冲突" width="800px">
          <p style="margin-bottom: 10px;">以下数据在数据库中已存在，请选择是否覆盖：</p>
          <el-table :data="conflictData" border stripe>
            <el-table-column prop="conflict_key" label="唯一标识" width="160" />
            <el-table-column label="原有数据">
              <template #default="{ row }"><pre>{{ row.old_data }}</pre></template>
            </el-table-column>
            <el-table-column label="上传数据">
              <template #default="{ row }"><pre>{{ row.new_data }}</pre></template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-radio-group v-model="row.action">
                  <el-radio label="keep">保留原</el-radio>
                  <el-radio label="replace">覆盖</el-radio>
                </el-radio-group>
              </template>
            </el-table-column>
          </el-table>
          <template #footer>
            <el-button @click="conflictDialog = false">取消</el-button>
            <el-button type="primary" @click="submitConflictResolution">确认提交</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import apiConfig from '@/config/api.js'
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
// import Papa from 'papaparse'

/* --- 基础状态 --- */
const activeTab = ref('query')
const showProcessing = ref(false)
const confirmUploadDialog = ref(false)
const conflictDialog = ref(false)
const conflictData = ref([])

/* --- 查询表单 --- */
const queryForm = reactive({
  originCity: [],
  destinationCity: [],
  dateRange: []
})

const tableData = ref([])
const pagination = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})
const fullData = ref([])

/* --- 动态列控制 --- */
const allColumns = ref([])
const selectedColumns = ref([])
watch(fullData, (val) => {
  if (val.length > 0) {
    allColumns.value = Object.keys(val[0])
    if (selectedColumns.value.length === 0) selectedColumns.value = [...allColumns.value]
  }
})
function selectAllColumns() { selectedColumns.value = [...allColumns.value] }
function clearAllColumns() { selectedColumns.value = [] }

/* --- 分页显示 --- */
const pagedData = computed(() => {
  const start = (pagination.currentPage - 1) * pagination.pageSize
  const end = pagination.currentPage * pagination.pageSize
  return fullData.value.slice(start, end)
})

function handleSizeChange(size) { pagination.pageSize = size }
function handleCurrentChange(page) { pagination.currentPage = page }

/* --- 加载机场数据 --- */
const locationOptions = ref([])
const cascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false,
  emitPath: true,
  value: 'value',
  label: 'label',
  children: 'children'
}
const filteredDestinationOptions = computed(() => {
  if (!queryForm.originCity?.length || queryForm.originCity.length !== 3) return locationOptions.value
  const [_, __, originIATA] = queryForm.originCity
  return locationOptions.value.map(p => ({
    ...p,
    children: p.children.map(c => ({
      ...c,
      children: c.children.filter(a => a.value !== originIATA)
    }))
  }))
})
async function loadAirportData() {
  try {
    const res = await fetch('/src/assets/iata_city_airport_mapping.json')
    const data = await res.json()
    const provinceMap = {}
    Object.entries(data).forEach(([iata, info]) => {
      const { province, city, airport } = info
      if (!provinceMap[province]) provinceMap[province] = {}
      if (!provinceMap[province][city]) provinceMap[province][city] = []
      provinceMap[province][city].push({ label: airport, value: iata })
    })
    locationOptions.value = Object.entries(provinceMap).map(([p, cities]) => ({
      label: p,
      value: p,
      children: Object.entries(cities).map(([c, airports]) => ({
        label: c,
        value: c,
        children: airports
      }))
    }))
  } catch {
    ElMessage.error('加载机场数据失败')
  }
}

/* --- 查询功能 --- */
async function searchData() {
  try {
    showProcessing.value = true
    const params = new URLSearchParams()
    if (queryForm.originCity?.length === 3) params.append('origin', queryForm.originCity[2])
    if (queryForm.destinationCity?.length === 3) params.append('destination', queryForm.destinationCity[2])
    if (queryForm.dateRange?.length === 2) {
      params.append('start_date', queryForm.dateRange[0])
      params.append('end_date', queryForm.dateRange[1])
    }
    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.FLIGHTDATA) + `?${params.toString()}`
    const res = await fetch(url)
    const result = await res.json()
    showProcessing.value = false

    if (!result.success) return ElMessage.error('数据请求失败')
    const rawData = result.data || []
    pagination.total = rawData.length

    // 动态字段解析
    fullData.value = rawData.map(item => {
      const flat = {}
      for (const [k, v] of Object.entries(item)) {
        flat[k] = (typeof v === 'object' && v?.code) ? v.code : v
      }
      return flat
    })
  } catch (err) {
    showProcessing.value = false
    ElMessage.error('查询失败，请检查网络或后端服务')
    console.error(err)
  }
}
function resetQuery() {
  queryForm.originCity = []
  queryForm.destinationCity = []
  queryForm.dateRange = []
  fullData.value = []
  selectedColumns.value = []
  pagination.currentPage = 1
}

function exportData() {
  if (!fullData.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  if (!selectedColumns.value.length) {
    ElMessage.warning('请先选择要导出的列')
    return
  }

  // 组装 CSV 字符串
  const header = selectedColumns.value.join(',')
  const rows = fullData.value.map(row => 
    selectedColumns.value.map(col => {
      const cell = row[col] ?? ''
      // 处理包含逗号、引号等特殊字符的字段，使用双引号包裹并转义引号
      const escaped = String(cell).replace(/"/g, '""')
      return `"${escaped}"`
    }).join(',')
  )
  const csvContent = [header, ...rows].join('\r\n')

  // 生成下载链接
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `查询结果_${new Date().toISOString().slice(0,10)}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
}

/* --- CSV 上传 --- */
const fileList = ref([])
const previewData = ref([])
const previewColumns = ref([])
let uploadedFileContent = ''

function beforeUpload(file) {
  const isCSV = file.name.endsWith('.csv')
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isCSV) {
    ElMessage.error('只能上传CSV文件')
    return false
  }
  if (!isLt5M) {
    ElMessage.error('文件大小不能超过5MB')
    return false
  }
  return true
}

function handleFileChange(file, list) {
  fileList.value = list
  if (!file.raw) return

  const reader = new FileReader()
  reader.onload = e => {
    uploadedFileContent = e.target.result

    // 调用自定义 CSV 解析函数
    const { headers, rows } = parseCSV(uploadedFileContent)

    previewColumns.value = headers
    previewData.value = rows.slice(0, 10) // 预览前 10 行
  }
  reader.readAsText(file.raw, 'utf-8')
}

function parseCSV(csvText) {
  const rows = []
  let currentRow = []
  let currentField = ''
  let insideQuotes = false
  for (let i = 0; i < csvText.length; i++) {
    const char = csvText[i]
    const nextChar = csvText[i + 1]
    if (char === '"' && insideQuotes && nextChar === '"') {
      // 连续两个双引号 → 转义为一个引号
      currentField += '"'
      i++
    } else if (char === '"') {
      // 切换引号状态
      insideQuotes = !insideQuotes
    } else if (char === ',' && !insideQuotes) {
      // 字段结束
      currentRow.push(currentField.trim())
      currentField = ''
    } else if ((char === '\n' || char === '\r') && !insideQuotes) {
      // 行结束（忽略空行）
      if (currentField || currentRow.length > 0) {
        currentRow.push(currentField.trim())
        rows.push(currentRow)
      }
      currentRow = []
      currentField = ''
    } else {
      currentField += char
    }
  }
  // 添加最后一个字段
  if (currentField || currentRow.length > 0) {
    currentRow.push(currentField.trim())
    rows.push(currentRow)
  }
  // 取首行为表头
  const headers = rows.shift() || []
  // 构建对象数组
  const dataObjects = rows
    .filter(r => r.length > 0 && r.some(x => x.trim() !== ''))
    .map(r => {
      const obj = {}
      headers.forEach((key, i) => (obj[key] = r[i] || ''))
      return obj
    })
  return { headers, rows: dataObjects }
}


async function uploadData() {
  if (!uploadedFileContent) return ElMessage.warning('请先选择CSV文件')
  showProcessing.value = true
  try {
    // 暂无接口
    const res = await fetch(apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPLOAD_CHECK), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: uploadedFileContent })
    })
    const result = await res.json()
    showProcessing.value = false

    if (result.status === 1) confirmUploadDialog.value = true
    else if (result.status === 2) {
      conflictData.value = result.conflicts.map(i => ({
        conflict_key: i.key,
        old_data: JSON.stringify(i.old, null, 2),
        new_data: JSON.stringify(i.new, null, 2),
        action: 'keep'
      }))
      conflictDialog.value = true
    } else if (result.status === 3) ElMessage.error('文件格式错误')
    else ElMessage.error('上传失败')
  } catch (err) {
    showProcessing.value = false
    ElMessage.error('上传失败，请检查网络')
    console.error(err)
  }
}

async function confirmUpload() {
  confirmUploadDialog.value = false
  showProcessing.value = true
  try {
    // 暂无接口
    const res = await fetch(apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPLOAD_INSERT), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: uploadedFileContent })
    })
    const result = await res.json()
    showProcessing.value = false
    if (result.success) {
      ElMessage.success('数据上传成功')
      fileList.value = []
      previewData.value = []
      previewColumns.value = []
    } else ElMessage.error('数据插入失败')
  } catch {
    showProcessing.value = false
    ElMessage.error('上传失败')
  }
}

async function submitConflictResolution() {
  const userDecisions = conflictData.value.map(r => ({ key: r.conflict_key, action: r.action }))
  conflictDialog.value = false
  showProcessing.value = true
  try {
    // 暂无接口
    const res = await fetch(apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPLOAD_RESOLVE), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decisions: userDecisions })
    })
    const result = await res.json()
    showProcessing.value = false
    if (result.success) {
      ElMessage.success('冲突数据处理完成')
      fileList.value = []
      previewData.value = []
      previewColumns.value = []
    } else ElMessage.error('冲突处理失败')
  } catch {
    showProcessing.value = false
    ElMessage.error('提交失败')
  }
}

/* --- 下载模板 --- */
function downloadTemplate() {
  const csv = '航线起点,航线终点,时间,运力,运量,航班数\n北京,上海,2024-01,1000,900,30\n'
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '数据模板.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

onMounted(loadAirportData)
</script>

<style scoped>
.manage-container {
  padding: 2rem 2.5rem;
  max-width: 1600px;
  margin: 0 auto;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.disabled-tabs {
  pointer-events: none;
  opacity: 0.6;
}
.query-panel { 
  padding: 24px 20px; 
  background: #fafafa; 
  border-radius: 8px; 
}
.el-cascader, .el-date-picker { 
  width: 240px; 
}
.query-table { 
  margin-top: 24px; 
  background: #fff; 
  border-radius: 8px; 
  padding: 16px; }
.toolbar { 
  display: flex; 
  justify-content: space-between; 
  align-items: center; 
  margin-bottom: 12px; }
.empty-data { 
  margin-top: 40px; 
}
.data-manage-panel { 
  padding: 24px; 
}
.preview-table { 
  margin-top: 24px; 
}
.download-btn { 
  margin-bottom: 20px; 
}
</style>
