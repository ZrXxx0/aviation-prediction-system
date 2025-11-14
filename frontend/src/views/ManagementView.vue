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
              <el-popover placement="bottom" trigger="click" width="500px">
                <template #reference>
                  <el-button type="primary" size="small" :disabled="showProcessing">选择显示列</el-button>
                </template>
                <div style="text-align: right; margin-top: 10px;">
                  <el-button size="small" @click="selectAllColumns">全选</el-button>
                  <el-button size="small" @click="clearAllColumns">清空</el-button>
                </div>
                <el-checkbox-group v-model="selectedColumns" class="column-list">
                  <el-checkbox v-for="col in allColumns" :key="col" :label="col">{{ col }}</el-checkbox>
                </el-checkbox-group>
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
          <div class="download-buttons">
            <el-button type="primary" @click="downloadTemplate" :disabled="showProcessing">
              下载数据模板（CSV）
            </el-button>
            <el-button type="info" @click="downloadTemplateGuide" :disabled="showProcessing">
              下载模板说明（PDF）
            </el-button>
          </div>

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
        <el-dialog v-model="conflictDialog" title="检测到数据冲突" width="1400px">
          <div class="conflict-dialog-content">
            <p style="margin-bottom: 15px;">以下数据在数据库中已存在，请选择是否覆盖：</p>
            
            <!-- 批量操作栏 -->
            <div class="batch-actions" style="margin-bottom: 15px;">
              <el-checkbox v-model="selectAllConflicts" @change="handleSelectAllConflicts">
                全选
              </el-checkbox>
              <el-button 
                type="primary" 
                size="small" 
                :disabled="selectedConflictIds.length === 0"
                @click="batchReplaceConflicts"
              >
                批量替换 ({{ selectedConflictIds.length }})
              </el-button>
              <el-button 
                size="small" 
                :disabled="selectedConflictIds.length === 0"
                @click="batchKeepConflicts"
              >
                批量保留 ({{ selectedConflictIds.length }})
              </el-button>
            </div>

            <!-- 冲突数据表格 -->
            <el-table 
              ref="conflictTableRef"
              :data="pagedConflictData" 
              border 
              stripe
              row-key="id"
              @selection-change="handleConflictSelectionChange"
            >
              <el-table-column type="selection" width="55" />
              <el-table-column prop="origin" label="起点" width="120" />
              <el-table-column prop="destination" label="终点" width="120" />
              <el-table-column prop="year_month" label="时间" width="120" />
              <el-table-column prop="conflict_key" label="唯一标识" width="180" show-overflow-tooltip />
              <el-table-column label="操作" width="280" fixed="right">
                <template #default="{ row }">
                  <el-button 
                    type="primary" 
                    plain 
                    size="small" 
                    @click="showConflictDetail(row)"
                  >
                    查看详情
                  </el-button>
                  <el-button 
                    type="success" 
                    plain 
                    size="small" 
                    :class="{ 'is-active': row.action === 'keep' }"
                    @click="setConflictAction(row, 'keep')"
                  >
                    保留
                  </el-button>
                  <el-button 
                    type="danger" 
                    plain 
                    size="small" 
                    :class="{ 'is-active': row.action === 'replace' }"
                    @click="setConflictAction(row, 'replace')"
                  >
                    替换
                  </el-button>
                </template>
              </el-table-column>
            </el-table>

            <!-- 分页 -->
            <div class="conflict-pagination">
              <el-pagination
                v-model:current-page="conflictPagination.currentPage"
                v-model:page-size="conflictPagination.pageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="conflictPagination.total"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="handleConflictSizeChange"
                @current-change="handleConflictPageChange"
              />
            </div>
          </div>

          <template #footer>
            <el-button @click="conflictDialog = false">取消</el-button>
            <el-button type="primary" @click="submitConflictResolution">确认提交</el-button>
          </template>
        </el-dialog>

        <!-- 冲突详情弹窗 -->
        <el-dialog 
          v-model="conflictDetailDialog" 
          title="冲突详情对比" 
          width="1000px"
          :close-on-click-modal="false"
        >
          <div class="conflict-detail-content" v-if="currentConflictDetail">
            <div class="detail-header">
              <p><strong>起点：</strong>{{ currentConflictDetail.origin }}</p>
              <p><strong>终点：</strong>{{ currentConflictDetail.destination }}</p>
              <p><strong>时间：</strong>{{ currentConflictDetail.year_month || currentConflictDetail.date }}</p>
            </div>
            
            <el-table :data="conflictDetailFields" border stripe style="margin-top: 20px;">
              <el-table-column prop="field" label="字段" width="200" />
              <el-table-column label="原有数据" min-width="250">
                <template #default="{ row }">
                  <div :class="{ 'diff-highlight': row.hasDiff }" class="detail-value-cell">
                    <pre v-if="isJsonString(row.oldValue)" class="json-value">{{ row.oldValue }}</pre>
                    <span v-else>{{ row.oldValue }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="上传数据" min-width="250">
                <template #default="{ row }">
                  <div :class="{ 'diff-highlight': row.hasDiff }" class="detail-value-cell">
                    <pre v-if="isJsonString(row.newValue)" class="json-value">{{ row.newValue }}</pre>
                    <span v-else>{{ row.newValue }}</span>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <template #footer>
            <el-button @click="conflictDetailDialog = false">关闭</el-button>
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
import templateCsvUrl from '@/assets/data_template.csv?url'
import templatePdfUrl from '@/assets/模板说明.pdf?url'
// import Papa from 'papaparse'

/* --- 基础状态 --- */
const activeTab = ref('query')
const showProcessing = ref(false)
const confirmUploadDialog = ref(false)
const conflictDialog = ref(false)
const conflictData = ref([])
const conflictDetailDialog = ref(false)
const currentConflictDetail = ref(null)
const conflictDetailFields = ref([])
const selectedConflictIds = ref([])
const selectAllConflicts = ref(false)
const conflictTableRef = ref(null)

/* --- 冲突数据分页 --- */
const conflictPagination = reactive({
  currentPage: 1,
  pageSize: 20,
  total: 0
})

const pagedConflictData = computed(() => {
  const start = (conflictPagination.currentPage - 1) * conflictPagination.pageSize
  const end = conflictPagination.currentPage * conflictPagination.pageSize
  return conflictData.value.slice(start, end)
})

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
const selectedColumns = ref(['year_month','origin','destination','route_total_flights','route_total_seats'])
watch(fullData, (val) => {
  if (val.length > 0) {
    allColumns.value = Object.keys(val[0])
    // 只在第一次查询时设置默认列，后续保留用户选择
    if (selectedColumns.value.length === 0) {
      selectedColumns.value = ['year_month', 'origin', 'destination']
    }
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
      conflictData.value = result.conflicts.map(i => {
        const oldData = i.old || {}
        const newData = i.new || {}
        return {
          id: i.key, // 用于批量选择
          conflict_key: i.key,
          origin: oldData.origin_code || newData.origin_code || oldData.origin || newData.origin || '-',
          destination: oldData.destination_code || newData.destination_code || oldData.destination || newData.destination || '-',
          year_month: oldData.year_month || newData.year_month || oldData.date || newData.date || oldData.month || newData.month || '-',
          old_data: oldData,
          new_data: newData,
          action: null  // 初始状态未选择，需要用户明确选择
        }
      })
      conflictPagination.total = conflictData.value.length
      conflictPagination.currentPage = 1
      selectedConflictIds.value = []
      selectAllConflicts.value = false
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

/* --- 冲突处理相关函数 --- */
function isJsonString(str) {
  if (typeof str !== 'string') return false
  try {
    const parsed = JSON.parse(str)
    return typeof parsed === 'object' && parsed !== null
  } catch {
    return false
  }
}

function showConflictDetail(row) {
  currentConflictDetail.value = row
  const oldData = row.old_data || {}
  const newData = row.new_data || {}
  
  // 获取所有字段
  const allFields = new Set([...Object.keys(oldData), ...Object.keys(newData)])
  
  // 构建对比字段数组
  conflictDetailFields.value = Array.from(allFields).map(field => {
    const oldValue = oldData[field]
    const newValue = newData[field]
    
    // 格式化值显示
    const formatValue = (val) => {
      if (val === null || val === undefined) return '(空)'
      if (typeof val === 'object') {
        try {
          return JSON.stringify(val, null, 2)
        } catch {
          return String(val)
        }
      }
      return String(val)
    }
    
    const formattedOldValue = formatValue(oldValue)
    const formattedNewValue = formatValue(newValue)
    const hasDiff = formattedOldValue !== formattedNewValue
    
    return {
      field,
      oldValue: formattedOldValue,
      newValue: formattedNewValue,
      hasDiff
    }
  })
  
  conflictDetailDialog.value = true
}

function handleConflictSelectionChange(selection) {
  selectedConflictIds.value = selection.map(item => item.id)
  // 更新全选状态
  selectAllConflicts.value = selection.length === pagedConflictData.value.length && pagedConflictData.value.length > 0
}

function handleSelectAllConflicts(val) {
  if (conflictTableRef.value) {
    if (val) {
      // 全选当前页
      pagedConflictData.value.forEach(row => {
        conflictTableRef.value.toggleRowSelection(row, true)
      })
    } else {
      // 取消全选
      conflictTableRef.value.clearSelection()
    }
  }
}

function batchReplaceConflicts() {
  if (selectedConflictIds.value.length === 0) return
  conflictData.value.forEach(item => {
    if (selectedConflictIds.value.includes(item.id)) {
      item.action = 'replace'
    }
  })
  ElMessage.success(`已批量设置为替换 (${selectedConflictIds.value.length}条)`)
  if (conflictTableRef.value) {
    conflictTableRef.value.clearSelection()
  }
  selectedConflictIds.value = []
  selectAllConflicts.value = false
}

function batchKeepConflicts() {
  if (selectedConflictIds.value.length === 0) return
  conflictData.value.forEach(item => {
    if (selectedConflictIds.value.includes(item.id)) {
      item.action = 'keep'
    }
  })
  ElMessage.success(`已批量设置为保留 (${selectedConflictIds.value.length}条)`)
  if (conflictTableRef.value) {
    conflictTableRef.value.clearSelection()
  }
  selectedConflictIds.value = []
  selectAllConflicts.value = false
}

function setConflictAction(row, action) {
  row.action = action
  handleConflictActionChange(row)
}

function handleConflictActionChange(row) {
  // 当单个操作改变时，从选中列表中移除（如果存在）
  const index = selectedConflictIds.value.indexOf(row.id)
  if (index > -1) {
    selectedConflictIds.value.splice(index, 1)
  }
}

function handleConflictSizeChange(size) {
  conflictPagination.pageSize = size
  conflictPagination.currentPage = 1
  if (conflictTableRef.value) {
    conflictTableRef.value.clearSelection()
  }
  selectedConflictIds.value = []
  selectAllConflicts.value = false
}

function handleConflictPageChange(page) {
  conflictPagination.currentPage = page
  if (conflictTableRef.value) {
    conflictTableRef.value.clearSelection()
  }
  selectedConflictIds.value = []
  selectAllConflicts.value = false
}

async function submitConflictResolution() {
  // 检查是否有未选择的项
  const unselectedItems = conflictData.value.filter(r => !r.action)
  if (unselectedItems.length > 0) {
    ElMessage.warning(`还有 ${unselectedItems.length} 条冲突数据未选择操作，请先选择"保留"或"替换"`)
    return
  }
  
  const userDecisions = conflictData.value.map(r => ({ key: r.conflict_key, action: r.action === 'replace' ? 'replace' : 'keep' }))
  conflictDialog.value = false
  showProcessing.value = true
  try {
    const res = await fetch(apiConfig.getUrl(apiConfig.endpoints.PREDICT.UPLOAD_RESOLVE), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        decisions: userDecisions,
        content: uploadedFileContent  // 发送完整的 CSV 内容
      })
    })
    const result = await res.json()
    showProcessing.value = false
    if (result.success) {
      ElMessage.success('冲突数据处理完成')
      fileList.value = []
      previewData.value = []
      previewColumns.value = []
      uploadedFileContent = ''
    } else ElMessage.error(result.message || '冲突处理失败')
  } catch (err) {
    showProcessing.value = false
    ElMessage.error('提交失败，请检查网络')
    console.error(err)
  }
}

/* --- 下载模板 --- */
async function downloadTemplate() {
  try {
    const response = await fetch(templateCsvUrl)
    if (!response.ok) {
      throw new Error('模板文件加载失败')
    }
    const csvContent = await response.text()
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = 'data_template.csv'
    link.click()
    URL.revokeObjectURL(link.href)
    ElMessage.success('模板下载成功')
  } catch (err) {
    ElMessage.error('模板下载失败：' + err.message)
    console.error(err)
  }
}

async function downloadTemplateGuide() {
  try {
    const response = await fetch(templatePdfUrl)
    if (!response.ok) {
      throw new Error('模板说明文件加载失败')
    }
    const blob = await response.blob()
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = '模板说明.pdf'
    link.click()
    URL.revokeObjectURL(link.href)
    ElMessage.success('模板说明下载成功')
  } catch (err) {
    ElMessage.error('模板说明下载失败：' + err.message)
    console.error(err)
  }
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
.download-buttons {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}

/* 冲突处理相关样式 */
.conflict-dialog-content {
  padding: 10px 0;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.conflict-pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.conflict-detail-content {
  padding: 10px 0;
}

.detail-header {
  display: flex;
  gap: 30px;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
}

.detail-header p {
  margin: 0;
  font-size: 14px;
}

.diff-highlight {
  color: #f56c6c;
  font-weight: 600;
  background-color: #fef0f0;
  padding: 2px 4px;
  border-radius: 2px;
}

.detail-value-cell {
  padding: 4px 0;
  word-break: break-word;
}

.json-value {
  margin: 0;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 操作按钮样式 */
.el-table-column:last-child .el-button {
  margin-right: 8px;
}

.el-table-column:last-child .el-button.is-active {
  background-color: var(--el-button-bg-color);
  border-color: var(--el-button-border-color);
}

.el-table-column:last-child .el-button[type="primary"].is-active {
  background-color: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
  color: var(--el-color-primary);
}

.el-table-column:last-child .el-button[type="success"].is-active {
  background-color: var(--el-color-success-light-9);
  border-color: var(--el-color-success);
  color: var(--el-color-success);
}

.el-table-column:last-child .el-button[type="danger"].is-active {
  background-color: var(--el-color-danger-light-9);
  border-color: var(--el-color-danger);
  color: var(--el-color-danger);
}
</style>
