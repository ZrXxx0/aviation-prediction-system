<template>
  <div class="manage-container">
    <el-tabs v-model="activeTab" type="card" stretch>
      <!-- 数据查询 Tab -->
      <el-tab-pane label="数据查询" name="query">
        <div class="query-panel">
          <el-form :model="queryForm" ref="queryFormRef" label-width="100px" inline>
            <el-form-item label="起点城市">
              <el-cascader
                v-model="queryForm.originCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择起点城市"
              />
            </el-form-item>

            <el-form-item label="终点城市">
              <el-cascader
                v-model="queryForm.destinationCity"
                :options="filteredDestinationOptions"
                :props="cascaderProps"
                clearable
                placeholder="选择终点城市"
              />
            </el-form-item>

            <el-form-item label="时间范围">
              <el-date-picker
                v-model="queryForm.dateRange"
                type="daterange"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="yyyy-MM-dd"
                clearable
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" icon="el-icon-search" @click="searchData">查询</el-button>
              <el-button icon="el-icon-refresh" @click="resetQuery">重置</el-button>
            </el-form-item>
          </el-form>

          <div class="query-table" v-if="tableData.length">
            <el-table :data="tableData" border stripe style="width: 100%">
              <el-table-column prop="origin" label="起点城市" min-width="100"/>
              <el-table-column prop="destination" label="终点城市" min-width="100"/>
              <el-table-column prop="date" label="时间" min-width="120"/>
              <el-table-column prop="capacity" label="运力" min-width="100"/>
              <el-table-column prop="passengers" label="运量" min-width="100"/>
              <el-table-column prop="flights" label="航班数" min-width="100"/>
            </el-table>

            <el-pagination
              background
              layout="prev, pager, next, sizes, total"
              :page-sizes="[10, 20, 50, 100]"
              :page-size="pagination.pageSize"
              :current-page="pagination.currentPage"
              :total="pagination.total"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
              style="margin-top: 10px; text-align: right;"
            >
            </el-pagination>

            <el-button
              type="success"
              icon="el-icon-download"
              @click="exportData"
              style="margin-top: 10px;"
            >
              导出查询结果
            </el-button>
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
import { ref, reactive, computed, onMounted } from 'vue'
import * as XLSX from 'xlsx'

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
  if (!queryForm.originCity?.length || queryForm.originCity.length !== 2) {
    return locationOptions.value
  }
  const [originProvince, originCity] = queryForm.originCity
  return locationOptions.value
    .map(province => {
      const filteredChildren = province.children.filter(city =>
        !(province.value === originProvince && city.value === originCity)
      )
      return filteredChildren.length ? { ...province, children: filteredChildren } : null
    })
    .filter(Boolean)
})

function searchData() {
  // 模拟数据查询
  const data = [
    {origin:'北京', destination:'上海', date:'2024-01-01', capacity:1000, passengers:900, flights:30},
    {origin:'上海', destination:'广州', date:'2024-01-01', capacity:1200, passengers:1100, flights:28},
    {origin:'北京', destination:'广州', date:'2024-01-02', capacity:1100, passengers:1000, flights:29}
  ]
  tableData.value = data.slice(
    (pagination.currentPage - 1) * pagination.pageSize,
    pagination.currentPage * pagination.pageSize
  )
  pagination.total = data.length
}

function resetQuery() {
  queryForm.originCity = []
  queryForm.destinationCity = []
  queryForm.dateRange = []
  tableData.value = []
  pagination.currentPage = 1
}

function handleSizeChange(size) {
  pagination.pageSize = size
  searchData()
}

function handleCurrentChange(page) {
  pagination.currentPage = page
  searchData()
}

function exportData() {
  if (!tableData.value.length) return
  const headers = Object.keys(tableData.value[0]).join(',')
  const csvContent = [headers, ...tableData.value.map(r => Object.values(r).join(','))].join('\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = '查询结果.csv'
  link.click()
  URL.revokeObjectURL(link.href)
}

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

async function loadCityData() {
  try {
    const response = await fetch('/src/assets/城市经纬度.xlsx')
    const arrayBuffer = await response.arrayBuffer()
    const workbook = XLSX.read(arrayBuffer, { type: 'array' })
    const sheet = workbook.Sheets[workbook.SheetNames[0]]
    const data = XLSX.utils.sheet_to_json(sheet)
    const cityMapTemp = {}
    data.forEach(row => {
      const province = row['省份']
      const city = row['城市']
      if (!cityMapTemp[province]) cityMapTemp[province] = []
      cityMapTemp[province].push(city)
    })
    locationOptions.value = Object.keys(cityMapTemp).map(province => ({
      label: province,
      value: province,
      children: cityMapTemp[province].map(city => ({ label: city, value: city }))
    }))
  } catch (error) {
    console.error('加载城市数据失败:', error)
    alert('加载城市数据失败，请刷新页面重试')
  }
}

onMounted(() => {
  loadCityData()
})
</script>

<style scoped>
.manage-container {
  padding: 1rem 2rem;
  max-width: 1600px;
  margin: 0 auto;
}

.query-panel, .data-manage-panel {
  padding: 20px 10px;
}

.download-btn {
  margin-bottom: 20px;
  height: 32px;
  font-size: 14px;
  padding: 0 20px;
}

.query-panel .el-form-item,
.data-manage-panel .el-upload {
  margin-bottom: 20px;
}

.query-panel .el-cascader,
.query-panel .el-date-picker {
  width: 220px;
}

.query-table {
  margin-top: 20px;
}

.empty-data {
  margin-top: 50px;
  text-align: center;
}

.preview-table h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 15px;
}

.preview-table .el-table {
  font-size: 14px;
}

.preview-table .el-table th,
.preview-table .el-table td {
  text-align: center;
  font-size: 14px;
  height: 40px;
}

.el-button {
  display: flex !important; 
  align-items: center !important;
  justify-content: center !important;
  line-height: normal !important;
  padding: 0 20px; 
  font-size: 14px;
  height: 32px;
}
</style>