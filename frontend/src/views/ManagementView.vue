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
            <el-table :data="tableData" border stripe style="width: 100%">
              <el-table-column prop="origin" label="起点机场" min-width="100"/>
              <el-table-column prop="destination" label="终点机场" min-width="100"/>
              <el-table-column prop="date" label="时间" min-width="120"/>
              <el-table-column prop="capacity" label="运力" min-width="100"/>
              <el-table-column prop="passengers" label="运量" min-width="100"/>
              <el-table-column prop="flights" label="航班数" min-width="100"/>
            </el-table>

            <div class="toolbar">
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
import { ref, reactive, computed, onMounted } from 'vue'

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

// 过滤终点机场，避免选择和起点相同
const filteredDestinationOptions = computed(() => {
  if (!queryForm.originCity?.length || queryForm.originCity.length !== 3) return locationOptions.value
  const [originProvince, originCity, originIATA] = queryForm.originCity
  return locationOptions.value.map(province => ({
    ...province,
    children: province.children.map(city => ({
      ...city,
      children: city.children.filter(airport => airport.value !== originIATA)
    }))
  }))
})

// 查询
async function searchData() {
  try {
    const params = new URLSearchParams();

    if (queryForm.originCity?.length === 3)
      params.append('origin', queryForm.originCity[2]);
    if (queryForm.destinationCity?.length === 3)
      params.append('destination', queryForm.destinationCity[2]);

    if (queryForm.dateRange?.length === 2) {
      // 直接使用 picker 返回的字符串
      params.append('start_date', queryForm.dateRange[0]);
      params.append('end_date', queryForm.dateRange[1]);
    }

    const url = `http://localhost:8000/predict/data/get_flightdata/?${params.toString()}`
    const res = await fetch(url)
    const result = await res.json()

    if (!result.success) {
      alert('数据请求失败，请重试')
      return
    }

    const rawData = result.data || []

    // 前端分页
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

//重置
function resetQuery() {
  queryForm.originCity = []
  queryForm.destinationCity = []
  queryForm.dateRange = []
  tableData.value = []
  pagination.currentPage = 1
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

// 导出 CSV
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

// 上传文件校验
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

// 加载机场数据
async function loadAirportData() {
  try {
    const response = await fetch('/src/assets/iata_city_airport_mapping.json')
    const data = await response.json()

    const provinceMap = {}

    // 遍历 JSON 构造层级结构
    Object.entries(data).forEach(([iata, info]) => {
      const { province, city, airport } = info

      if (!provinceMap[province]) provinceMap[province] = {}
      if (!provinceMap[province][city]) provinceMap[province][city] = []

      provinceMap[province][city].push({
        label: airport,   // 前端显示机场名称
        value: iata       // 最终传给后端的三字码
      })
    })

    // 转换成 Cascader 所需格式
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

onMounted(() => { loadAirportData() })
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

.el-form-item {
  margin-bottom: 20px;
}

.el-cascader, .el-date-picker {
  width: 220px;
}

/* 按钮统一样式，文字居中 */
.el-button {
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-size: 14px;
  height: 32px;
  padding: 0 16px;
  line-height: normal;
}

/* 表格间距 */
.query-table, .preview-table {
  margin-top: 20px;
}

/* 空数据样式 */
.empty-data {
  margin-top: 50px;
  text-align: center;
}

/* 预览表格标题 */
.preview-table h4 {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 15px;
}

/* 表格字体大小 */
.el-table th, .el-table td {
  text-align: center;
  font-size: 14px;
  height: 40px;
}

/* 查询结果容器间距 */
.query-table {
  margin-top: 30px; /* 表格与上方表单间距增大 */
}

/* 分页栏间距 */
.query-table .el-pagination {
  margin-top: 20px; /* 分页栏与表格间距增大 */
  text-align: right;
}

/* 导出按钮间距 */
.query-table .export-btn {
  margin-top: 20px; /* 按钮与分页栏间距增大 */
}

.toolbar {
  display: flex;
  justify-content: space-between; /* 两端对齐 */
  align-items: center;            /* 垂直居中 */
  margin-top: 16px;               /* 上边距，可按需调整 */
}

.pagination {
  flex-shrink: 0; /* 避免被压缩 */
}

.export-btn {
  flex-shrink: 0;
}

</style>