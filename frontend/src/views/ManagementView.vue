<template>
  <div class="manage-container">
    <el-tabs v-model="activeTab" type="card" stretch>

      <!-- 数据查询 Tab -->
      <el-tab-pane label="数据查询" name="query">
        <div class="query-panel">
          <el-form :model="queryForm" ref="queryFormRef" label-width="100px" inline>
            
            <el-form-item label="起点机场">
              <el-cascader
                v-model="queryForm.originCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择起点机场"
              />
            </el-form-item>

            <el-form-item label="终点机场">
              <el-cascader
                v-model="queryForm.destinationCity"
                :options="filteredDestinationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择终点机场"
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
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="searchData">查询</el-button>
              <el-button @click="resetQuery">重置</el-button>
            </el-form-item>

          </el-form>

          <!-- 查询结果 -->
          <div class="query-table" v-if="tableData.length">
            <div class="toolbar">
              <el-popover
                placement="bottom"
                trigger="click"
                width="250px"
              >
                <template #reference>
                  <el-button type="primary" size="small">选择显示列</el-button>
                </template>

                <el-checkbox-group v-model="selectedColumns" class="column-list">
                  <el-checkbox
                    v-for="col in allColumns"
                    :key="col"
                    :label="col"
                  >
                    {{ col }}
                  </el-checkbox>
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
                  class="pagination"
                />
                <el-button
                  type="success"
                  @click="exportData"
                  class="export-btn"
                >
                  导出查询结果
                </el-button>
              </div>
            </div>

            <el-table :data="tableData" border stripe style="width: 100%">
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
      <el-tab-pane label="数据上传" name="upload">
        <div class="data-manage-panel">
          <el-button
            type="primary"
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
            <div class="el-upload__text">拖拽或点击上传CSV数据文件</div>
            <div class="el-upload__tip">只能上传CSV格式文件，且不超过5MB</div>
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
import apiConfig from '@/config/api.js'
import { ref, reactive, computed, onMounted, watch } from 'vue'

const activeTab = ref('query')
const fileList = ref([])
const previewData = ref([])
const previewColumns = ref([])

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

// 动态列控制
const allColumns = ref([])
const selectedColumns = ref([])

watch(tableData, (val) => {
  if (val.length > 0) {
    allColumns.value = Object.keys(val[0])
    if (selectedColumns.value.length === 0) {
      selectedColumns.value = [...allColumns.value]
    }
  }
})

function selectAllColumns() {
  selectedColumns.value = [...allColumns.value]
}

function clearAllColumns() {
  selectedColumns.value = []
}

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
  if (!queryForm.originCity?.length || queryForm.originCity.length !== 3)
    return locationOptions.value
  const [originProvince, originCity, originIATA] = queryForm.originCity
  return locationOptions.value.map(province => ({
    ...province,
    children: province.children.map(city => ({
      ...city,
      children: city.children.filter(airport => airport.value !== originIATA)
    }))
  }))
})

// 加载机场数据
async function loadAirportData() {
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
    alert('加载机场数据失败，请刷新页面重试')
  }
}

// 查询
async function searchData() {
  try {
    const params = new URLSearchParams()

    if (queryForm.originCity?.length === 3)
      params.append('origin', queryForm.originCity[2])
    if (queryForm.destinationCity?.length === 3)
      params.append('destination', queryForm.destinationCity[2])

    if (queryForm.dateRange?.length === 2) {
      params.append('start_date', queryForm.dateRange[0])
      params.append('end_date', queryForm.dateRange[1])
    }

    const url = apiConfig.getUrl(apiConfig.endpoints.PREDICT.FLIGHTDATA) + `?${params.toString()}`
    console.log('请求 URL:', url)
    const res = await fetch(url)
    const result = await res.json()

    if (!result.success) {
      alert('数据请求失败，请重试')
      return
    }

    const rawData = result.data || []

    pagination.total = rawData.length
    const start = (pagination.currentPage - 1) * pagination.pageSize
    const end = pagination.currentPage * pagination.pageSize

    tableData.value = rawData.slice(start, end).map(item => ({
      origin: item.origin.code,
      destination: item.destination.code,
      date: item.year_month,
      capacity: item.route_total_seats,
      passengers: item.route_total_flights,
      flights: item.route_total_flights
    }))
  } catch (error) {
    console.error('查询失败:', error)
    alert('查询失败，请检查网络或后端服务')
  }
}

// 重置
function resetQuery() {
  queryForm.originCity = []
  queryForm.destinationCity = []
  queryForm.dateRange = []
  tableData.value = []
  pagination.currentPage = 1
  selectedColumns.value = []
}

// 分页事件
function handleSizeChange(size) {
  pagination.pageSize = size
  searchData()
}
function handleCurrentChange(page) {
  pagination.currentPage = page
  searchData()
}

// 导出 CSV（仅导出选中列）
function exportData() {
  if (!tableData.value.length) return
  if (!selectedColumns.value.length) {
    alert('请先选择要导出的列')
    return
  }

  const headers = selectedColumns.value.join(',')
  const csvContent = [
    headers,
    ...tableData.value.map(row =>
      selectedColumns.value.map(col => row[col]).join(',')
    )
  ].join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '查询结果.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

// 下载模板
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

// 上传文件校验与预览
function beforeUpload(file) {
  const isCSV = file.type === 'text/csv' || file.name.endsWith('.csv')
  const isLt5M = file.size / 1024 / 1024 < 5
  if (!isCSV) { alert('只能上传CSV文件'); return false }
  if (!isLt5M) { alert('文件大小不能超过5MB'); return false }
  return true
}

function handleFileChange(file, fileListNew) {
  fileList.value = fileListNew
  if (!file.raw) return
  const reader = new FileReader()
  reader.onload = e => { parseCSVPreview(e.target.result) }
  reader.readAsText(file.raw)
}

function parseCSVPreview(csvText) {
  const lines = csvText.split(/\r?\n/)
  const previewLines = lines.slice(0, 11)
  if (previewLines.length < 2) { previewData.value = []; previewColumns.value = []; return }
  const headers = previewLines[0].split(',')
  previewColumns.value = headers
  const rows = previewLines.slice(1).map(line => {
    const vals = line.split(',')
    const obj = {}
    headers.forEach((h, idx) => { obj[h] = vals[idx] })
    return obj
  })
  previewData.value = rows.filter(r => Object.values(r).some(v => v))
}

onMounted(() => { loadAirportData() })
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

/* 查询区域 */
.query-panel {
  padding: 24px 20px 32px 20px;
  background-color: #fafafa;
  border-radius: 8px;
  margin-bottom: 24px;
}

/* 表单行间距 */
.el-form-item {
  margin-bottom: 16px;
}

/* 输入组件统一宽度 */
.el-cascader,
.el-date-picker {
  width: 240px;
}

/* 查询与重置按钮放在一行右对齐 */
.el-form-item:last-child {
  margin-left: auto;
}

/* 表格容器 */
.query-table {
  margin-top: 24px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.05);
}

/* 工具栏布局 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

/* 分页与导出按钮 */
.pagination {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}

.export-btn {
  height: 32px;
}

/* 表格美化 */
.el-table {
  border-radius: 8px;
  overflow: hidden;
}

.el-table th,
.el-table td {
  text-align: center;
  font-size: 14px;
  height: 42px;
}

/* 空数据 */
.empty-data {
  margin-top: 60px;
  text-align: center;
}

/* 上传部分 */
.data-manage-panel {
  padding: 30px 20px;
  background-color: #fafafa;
  border-radius: 8px;
}

.download-btn {
  margin-bottom: 20px;
}

/* 上传区提示样式 */
.upload-demo {
  margin-bottom: 20px;
}

/* 预览表格 */
.preview-table {
  margin-top: 20px;
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.05);
}

.preview-table h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 12px;
}

</style>