<template>
  <div class="forecast-container">
    <div class="forecast-content">
      <!-- 左侧控制面板 -->
      <div class="control-panel">
        <h2>预测参数设置</h2>

        <div class="form-group">
          <label>预测时间粒度</label>
          <select v-model="timeRange">
            <option>年度</option>
            <option>季度</option>
            <option>月度</option>
          </select>
        </div>

        <div class="form-group">
          <label>预测时间长度</label>
          <input type="number" v-model="numFeatures" min="1" />
        </div>

        <div class="form-group">
          <label>选择模型</label>
          <select v-model="modelType">
            <option value="ARIMA">ARIMA</option>
            <option value="LSTM">LSTM</option>
            <option value="Prophet">Prophet</option>
          </select>
        </div>

        <div class="form-group">
          <label>选择起点</label>
          <select v-model="selectedFrom">
            <option disabled value="">请选择</option>
            <option v-for="city in cities" :key="'from-' + city">{{ city }}</option>
          </select>
        </div>

        <div class="form-group">
          <label>选择终点</label>
          <select v-model="selectedTo">
            <option disabled value="">请选择</option>
            <option v-for="city in cities" :key="'to-' + city">{{ city }}</option>
          </select>
        </div>

        <button class="run-btn" @click="addRoute">添加航线</button>

        <div class="route-list" v-if="routes.length">
          <h3>已选航线</h3>
          <ul>
            <li v-for="(route, index) in routes" :key="index">
              {{ route.from }} → {{ route.to }}
              <button class="delete-btn" @click="removeRoute(index)">删除</button>
            </li>
          </ul>
        </div>

        <button class="run-btn" @click="runForecast">运行预测</button>
      </div>

      <!-- 右侧图表和结果 -->
      <div class="result-area">
        <div class="chart-area" ref="chartRef"></div>

        <div class="stat-card" v-if="performanceTable.length">
          <h3>预测性能指标</h3>
          <table class="performance-table">
            <thead>
              <tr>
                <th>航线</th>
                <th>模型</th>
                <th>R²</th>
                <th>MAPE (%)</th>
                <th>RMSE</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in performanceTable" :key="index">
                <td>{{ row.route }}</td>
                <td>{{ row.model }}</td>
                <td>{{ row.r2 }}</td>
                <td>{{ row.mape }}</td>
                <td>{{ row.rmse }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

// 控制参数
const timeRange = ref('月度')
const modelType = ref('ARIMA')
const numFeatures = ref(3)

// 图表相关
const chartRef = ref(null)
let chartInstance = null

// 航线数据
const cities = ['北京', '上海', '广州', '深圳', '成都', '杭州']
const selectedFrom = ref('')
const selectedTo = ref('')
const routes = ref([])

// 表格数据
const performanceTable = ref([])

// 添加航线
function addRoute() {
  if (!selectedFrom.value || !selectedTo.value) return
  if (selectedFrom.value === selectedTo.value) return
  const exists = routes.value.some(r => r.from === selectedFrom.value && r.to === selectedTo.value)
  if (!exists) {
    routes.value.push({ from: selectedFrom.value, to: selectedTo.value })
  }
}

// 删除航线
function removeRoute(index) {
  routes.value.splice(index, 1)
}

// 生成模拟预测数据，航线数 = series 数
function getDefaultForecastData() {
  const timeLabels = Array.from({ length: numFeatures.value }, (_, i) => {
    return `${i + 1}${timeRange.value === '年度' ? '年' : timeRange.value === '季度' ? '季度' : '月'}`
  })

  const series = routes.value.map((route, idx) => {
    return {
      name: `${route.from}→${route.to}`,
      type: 'line',
      data: Array.from({ length: numFeatures.value }, () => Math.round(Math.random() * 1000 + 500))
    }
  })

  const performance = routes.value.map(route => ({
    route: `${route.from} → ${route.to}`,
    model: modelType.value,
    r2: (Math.random() * 0.3 + 0.7).toFixed(2),
    mape: (Math.random() * 10 + 5).toFixed(2),
    rmse: (Math.random() * 50 + 100).toFixed(2)
  }))

  return { timeLabels, series, performance }
}

// 渲染图表：多条线
function renderChart(timeLabels = [], seriesData = []) {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const options = {
    title: {
      text: '预测结果',
      textStyle: { color: 'black' }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' }
    },
    legend: {
      data: seriesData.map(s => s.name)
    },
    toolbox: {
      show: true,
      feature: {
        dataView: { readOnly: false },
        magicType: { type: ['line', 'bar', 'stack'] },
        restore: {},
        saveAsImage: {}
      }
    },
    xAxis: {
      type: 'category',
      data: timeLabels
    },
    yAxis: { type: 'value' },
    series: seriesData
  }

  chartInstance.setOption(options)
}

// 运行预测（使用模拟数据）
async function runForecast() {
  if (routes.value.length === 0) {
    alert('请先添加至少一条航线')
    return
  }

  const { timeLabels, series, performance } = getDefaultForecastData()
  renderChart(timeLabels, series)
  performanceTable.value = performance
}

// 初始化空图
onMounted(() => {
  renderChart([], [])
})
</script>

<style scoped>
.forecast-container {
  padding: 1rem 2rem;
  width: 100%;
}
.forecast-content {
  display: flex;
  gap: 2rem;
  margin-top: 1.5rem;
}
.control-panel {
  flex: 0 0 300px;
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}
.result-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.chart-area {
  height: 400px;
  background: #f8f9fa;
  border-radius: 8px;
}
.stat-card {
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.stat-card h3 {
  margin-top: 0;
  color: #7f8c8d;
}
.form-group {
  margin-bottom: 1.2rem;
}
label {
  display: block;
  margin-bottom: 0.5rem;
  color: #34495e;
}
select, input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}
.run-btn {
  width: 100%;
  padding: 0.75rem;
  background: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  transition: background 0.3s;
  margin-top: 0.5rem;
}
.run-btn:hover {
  background: #2980b9;
}
.route-list {
  margin-top: 1rem;
}
.route-list ul {
  list-style: none;
  padding: 0;
}
.route-list li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
  background: #f3f4f6;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
}
.delete-btn {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}
.delete-btn:hover {
  background: #c0392b;
}
.performance-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}
.performance-table th,
.performance-table td {
  border: 1px solid #ddd;
  padding: 0.75rem;
  text-align: center;
}
.performance-table th {
  background: #f0f2f5;
  color: #2c3e50;
  font-weight: 600;
}
</style>