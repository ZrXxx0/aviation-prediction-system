<template>
  <div id="app">
    <div class="dashboard">
      <!-- 左侧面板 - 地图和筛选 -->
      <div class="left-panel">
        <div class="panel-title">
          <Decoration1 :color="['#46bee9', '#46bee9']" style="width:200px;height:50px;" />
          <h2>全国航线实时分布</h2>
        </div>

        <div class="filters">
          <div class="filter-group">
            <label for="yearMonth"><i class="fas fa-calendar-alt"></i> 查看时间</label>
            <el-date-picker
                id="MapYearMonth"
                v-model="selectedDate"
                type="month"
                placeholder="选择年月"
                format="YYYY 年 MM 月"
                value-format="YYYY-MM"
                @change="updateChart"
                @input="(val) => console.log('时间选择器输入:', val)"
                style="width: 40%"
            ></el-date-picker>
          </div>

          <div class="filter-group">
            <label for="city"><i class="fas fa-map-marker-alt"></i> 查看城市</label>
            <el-cascader
              id="MapCity"
              v-model="selectedMapCity"
              :options="locationOptions"
              :props="cascaderProps"
              @change="handleMapCityChange"
              clearable
              style="width: 40%"
            ></el-cascader>
          </div>
        </div>

        <div class="chart-container" id="map-chart"></div>
      </div>

      <!-- 右侧面板 - 统计信息 -->
      <div class="right-panel">
        <div class="panel-title">
          <Decoration7 style="width:250px;height:30px;">&emsp;航班统计分析&emsp;</Decoration7>
        </div>

        <div class="filters">
          <div class="filter-group">
            <label for="startCity">起始城市</label>
            <el-cascader
                id="startCity"
                v-model="selectedStartCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                style="width: 40%"
            ></el-cascader>
          </div>

          <div class="filter-group">
            <label for="endCity"><i class="fas fa-plane-arrival"></i> 终点城市</label>
            <el-cascader
                id="endCity"
                v-model="selectedEndCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                style="width: 40%; margin-right: 20px"
            ></el-cascader>
            <el-button type="primary" :icon="Search" circle @click="handleSearch" />
          </div>
        </div>

        <div class="stats-cards">
          <div class="stat-card">
            <h3>🛫 总运力</h3>
            <div class="value">{{ filteredStats.capacity.toLocaleString() }}</div>
            <div class="unit">人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛩️ 总运量</h3>
            <div class="value">{{ filteredStats.volume.toLocaleString() }}</div>
            <div class="unit">人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛫 航班数量</h3>
            <div class="value">{{ filteredStats.flights.toLocaleString() }}</div>
            <div class="unit">班次/月</div>
          </div>
        </div>

        <div class="bar-chart-container">
          <div class="bar-chart-header">
            <div class="chart-title">航班统计指标趋势(过去12个月)</div>
            <el-select v-model="selectedStatType" placeholder="选择统计类型" style="width: 180px;margin-top: 15px">
              <el-option
                  v-for="item in statTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
              />
            </el-select>
          </div>
          <div ref="cubeChartRef" id="cube-bar-chart" style="width:100%;height:320px;min-height:200px;"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed, reactive } from 'vue';
import type { ElSelect, ElOption, CascaderOption, CascaderProps } from 'element-plus';
import {Search} from '@element-plus/icons-vue'
import { Decoration1 , Decoration7 } from 'datav-vue3';
import * as echarts from 'echarts';
import chinaMap from '@/assets/china.json';
import * as XLSX from 'xlsx';
import apiConfig from '@/config/api.js';

echarts.registerMap('china', chinaMap as any);

const selectedDate = ref('2024-05'); // 默认2024年5月
const selectedMapCity = ref([''] as string[]); // 地图查看城市
const selectedStartCity = ref([''] as string[]); // 起始城市
const selectedEndCity = ref([''] as string[]); // 终点城市
const selectedStatType = ref('capacity');
const provinces = ref(['北京', '上海', '广东', '江苏', '浙江', '四川', '山东', '河南', '湖北', '湖南']);
const cityMap = ref<Record<string, string[]>>({});
const geoCoordMap = ref<Record<string, [number, number]>>({});

// 航线数据
const routeData = ref<any[]>([]);

// 查询结果统计数据（默认全国）
const filteredStats = reactive({
  capacity: 0,
  volume: 0,
  flights: 0
});
// 查询结果趋势数据（默认全国）
const filteredTrendData = reactive({
  months: [],
  capacity: [],
  volume: [],
  flights: []
});

// 获取航线分布数据
const fetchRouteDistribution = async (yearMonth: string, city?: string) => {
  try {
    console.log('🔍 发送请求参数:', { yearMonth, city });
    const params = new URLSearchParams({ year_month: yearMonth });
    if (city) params.append('city', city);
    
    const url = apiConfig.getUrl(apiConfig.endpoints.SHOW.ROUTES) + `?${params}`;
    console.log('🔍 请求URL:', url);
    
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 转换数据格式为前端需要的格式
    const convertedData = data.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    routeData.value = convertedData;
    console.log('✅ 成功获取航线数据:', routeData.value.length, '条记录');
  } catch (error) {
    console.error('❌ 获取航线数据失败:', error);
    // 如果API失败，使用默认数据
    routeData.value = defaultRouteData;
    console.log('📊 使用默认航线数据:', routeData.value.length, '条记录');
  }
};

// API调用函数
const fetchStatisticsSummary = async (yearMonth: string, startCity?: string, endCity?: string) => {
  try {
    const params = new URLSearchParams({ year_month: yearMonth });
    if (startCity) params.append('start_city', startCity);
    if (endCity) params.append('end_city', endCity);
    
    const response = await fetch(apiConfig.getUrl(apiConfig.endpoints.SHOW.STATISTICS_SUMMARY) + `?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    filteredStats.capacity = data.capacity || 0;
    filteredStats.volume = data.volume || 0;
    filteredStats.flights = data.flights || 0;
    console.log('✅ 成功获取统计数据:', filteredStats);
  } catch (error) {
    console.error('❌ 获取统计数据失败:', error);
    // 设置默认统计数据
    filteredStats.capacity = 1500000;
    filteredStats.volume = 1200000;
    filteredStats.flights = 15000;
    console.log('📊 使用默认统计数据:', filteredStats);
  }
};

const fetchStatisticsTrend = async (yearMonth: string, startCity?: string, endCity?: string) => {
  try {
    const params = new URLSearchParams({ year_month: yearMonth });
    if (startCity) params.append('start_city', startCity);
    if (endCity) params.append('end_city', endCity);
    
    const response = await fetch(apiConfig.getUrl(apiConfig.endpoints.SHOW.STATISTICS_TREND) + `?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    filteredTrendData.months = data.months || [];
    filteredTrendData.capacity = data.capacity || [];
    filteredTrendData.volume = data.volume || [];
    filteredTrendData.flights = data.flights || [];
    console.log('✅ 成功获取趋势数据:', filteredTrendData);
  } catch (error) {
    console.error('❌ 获取趋势数据失败:', error);
    // 设置默认趋势数据
    const months = getLast12Months();
    filteredTrendData.months = months;
    filteredTrendData.capacity = generateRandomData(1500);
    filteredTrendData.volume = generateRandomData(1200);
    filteredTrendData.flights = generateRandomData(200);
    console.log('📊 使用默认趋势数据:', filteredTrendData);
  }
};

async function loadCityData() {
  const response = await fetch('/src/assets/城市经纬度.xlsx');
  const arrayBuffer = await response.arrayBuffer();
  const workbook = XLSX.read(arrayBuffer, { type: 'array' });
  const sheet = workbook.Sheets[workbook.SheetNames[0]];
  const data = XLSX.utils.sheet_to_json(sheet);

  const cityMapTemp: Record<string, string[]> = {};
  const geoCoordMapTemp: Record<string, [number, number]> = {};

  data.forEach((row: any) => {
    const province = row['省份'];
    const city = row['城市'];
    const lng = Number(row['经度']);
    const lat = Number(row['纬度']);
    if (!cityMapTemp[province]) cityMapTemp[province] = [];
    cityMapTemp[province].push(city);
    geoCoordMapTemp[city] = [lng, lat];
  });

  cityMap.value = cityMapTemp;
  geoCoordMap.value = geoCoordMapTemp;
}

const currentDate = ref(new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric'
}));
// ECharts实例
const mapChart = ref(null);
// 地理坐标数据
// 默认航线数据（当API失败时使用）
const defaultRouteData = [[{name: '上海'}, {name: '北京', value: 322}],
  [{name: '上海'}, {name: '广州', value: 350}],
  [{name: '北京'}, {name: '上海', value: 210}],
  [{name: '北京'}, {name: '广州', value: 188}],
  [{name: '北京'}, {name: '成都', value: 196}],
  [{name: '广州'}, {name: '上海', value: 104}],
  [{name: '广州'}, {name: '北京', value: 238}],
  [{name: '广州'}, {name: '成都', value: 282}],
  [{name: '成都'}, {name: '北京', value: 196}],
  [{name: '成都'}, {name: '广州', value: 48}],
  [{name: '深圳'}, {name: '北京', value: 156}],
  [{name: '深圳'}, {name: '上海', value: 210}],
  [{name: '杭州'}, {name: '广州', value: 126}],
  [{name: '重庆'}, {name: '北京', value: 42}],
  [{name: '武汉'}, {name: '广州', value: 98}],
  [{name: '西安'}, {name: '北京', value: 162}],
  [{name: '天津'}, {name: '广州', value: 130}],
  [{name: '郑州'}, {name: '北京', value: 143}],
  [{name: '长沙'}, {name: '广州', value: 145}],
  [{name: '昆明'}, {name: '北京', value: 84}],
  [{name: '乌鲁木齐'}, {name: '北京', value: 140}],
  [{name: '哈尔滨'}, {name: '北京', value: 570}],
  [{name: '青岛'}, {name: '上海', value: 134}],
  [{name: '厦门'}, {name: '北京', value: 56}],
  [{name: '三亚'}, {name: '北京', value: 56}],
  [{name: '南京'}, {name: '深圳', value: 120}],
  [{name: '南京'}, {name: '成都', value: 90}],
  [{name: '合肥'}, {name: '上海', value: 80}],
  [{name: '合肥'}, {name: '广州', value: 70}],
  [{name: '厦门'}, {name: '成都', value: 60}],
  [{name: '青岛'}, {name: '深圳', value: 110}],
  [{name: '西安'}, {name: '杭州', value: 95}],
  [{name: '重庆'}, {name: '南京', value: 85}],
  [{name: '长沙'}, {name: '合肥', value: 75}],
  [{name: '哈尔滨'}, {name: '成都', value: 65}],
];
// 转换航线数据
const convertData = (data) => {
  const res = [];
  for (let i = 0; i < data.length; i++) {
    const dataItem = data[i];
    const fromCoord = geoCoordMap.value[dataItem[0].name];
    const toCoord = geoCoordMap.value[dataItem[1].name];
    if (fromCoord && toCoord) {
      res.push({
        fromName: dataItem[0].name,
        toName: dataItem[1].name,
        coords: [fromCoord, toCoord],
        value: dataItem[1].value
      });
    }
  }
  return res;
};
// 初始化图表
const initCharts = () => {
  console.log('📊 开始初始化图表...');
  
  // 检查DOM元素是否存在
  const mapElement = document.getElementById('map-chart');
  
  if (!mapElement) {
    console.error('❌ 地图容器元素不存在');
    return false;
  }
  
  try {
    // 初始化地图图表
    mapChart.value = echarts.init(mapElement);
    console.log('✅ 地图图表初始化成功');
    
    return true;
  } catch (error) {
    console.error('❌ 图表初始化失败:', error);
    return false;
  }
};
// 渲染地图
const renderMap = () => {
  console.log('🗺️ 开始渲染地图...');
  
  // 获取当前选择的城市
  let city = selectedMapCity.value && selectedMapCity.value.length > 1
    ? selectedMapCity.value[1]
    : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');

  // 使用从API获取的航线数据
  let filteredDatas = routeData.value || [];
  if (city && city !== '') {
    filteredDatas = (routeData.value || []).filter(d => d[0].name === city);
  }

  console.log('📊 地图数据:', {
    totalRoutes: filteredDatas.length,
    selectedCity: city,
    hasData: filteredDatas.length > 0
  });

  // 有航线的城市
  const flightCities = new Set(filteredDatas.flatMap(d => [d[0].name, d[1].name]));
  // 所有城市
  const allCities = Object.keys(geoCoordMap.value || {});

  const allCityData = allCities.map(city => ({
    name: city,
    value: geoCoordMap.value[city],
    itemStyle: { color: '#fff' }, // 小白点
    label: { show: false }
  }));

  const flightCityData = Array.from(flightCities).map(city => ({
    name: city,
    value: geoCoordMap.value[city],
    itemStyle: { color: '#e6c652' }, // 高亮色
    label: { show: true, position: 'right', formatter: '{b}' }
  }));

  // 新增：高亮选中城市（无论是否有航线）
  const selectedCityData = city && city !== '' && geoCoordMap.value[city]
    ? [{
        name: city,
        value: geoCoordMap.value[city],
        itemStyle: { color: 'red' },
        symbolSize: 16,
        label: { show: true, position: 'right', formatter: '{b}', color: 'red', fontWeight: 'bold' }
      }]
    : [];

  const option = {
    backgroundColor: '#c0dcef',
    tooltip: {
      trigger: 'item', formatter: (params) => {
        if (params.data && params.data.fromName) {
          return `${params.data.fromName} → ${params.data.toName}<br/>航班量: ${params.data.value}`;
        }
        return params.name;
      }
    },
    geo: {
      map: 'china',
      zoom: 1.2,
      label: {emphasis: {show: false}},
      roam: true,
      itemStyle: {normal: {areaColor: '#323c48', borderColor: '#4e5667'}, emphasis: {areaColor: '#2a333d'}}
    },
    series: [
      {
        name: '所有城市',
        type: 'scatter',
        coordinateSystem: 'geo',
        zlevel: 1,
        symbolSize: 3,
        data: allCityData,
        tooltip: { show: true, formatter: '{b}' }
      },
      {
        name: '航线城市',
        type: 'scatter',
        coordinateSystem: 'geo',
        zlevel: 2,
        symbolSize: 6,
        data: flightCityData,
        tooltip: { show: true, formatter: '{b}' }
      },
      // 新增：高亮选中城市
      {
        name: '选中城市',
        type: 'scatter',
        coordinateSystem: 'geo',
        zlevel: 3,
        symbolSize: 16,
        data: selectedCityData,
        tooltip: { show: true, formatter: '{b}' }
      },
      {
        name: '航线',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: 1,
        effect: {show: true, period: 4, trailLength: 0.02, symbol: 'arrow', symbolSize: 5},
        lineStyle: {normal: {color: '#ffffff', width: 1, opacity: 0.6, curveness: 0.2}},
        data: convertData(filteredDatas)
      }]
  };
  if (mapChart.value) {
    try {
      mapChart.value.setOption(option);
      console.log('✅ 地图渲染完成');
    } catch (error) {
      console.error('❌ 地图渲染失败:', error);
    }
  } else {
    console.error('❌ 地图图表实例不存在');
  }
};

// 处理窗口大小变化
const handleResize = () => {
  if (mapChart.value) {
    mapChart.value.resize();
  }
};
// Cascader options for province/city
const locationOptions = computed(() => [
  { label: '全国', value: '' },
  ...Object.keys(cityMap.value).map(province => ({
    label: province,
    value: province,
    children: (cityMap.value[province] || []).map(city => ({
      label: city,
      value: city
    }))
  }))
]);
const cascaderProps: CascaderProps = {
  expandTrigger: 'hover',
  checkStrictly: false, // allow selecting parent (province) or child (city)
  emitPath: true, // value is array
  value: 'value',
  label: 'label',
  children: 'children',
};

function handleLocationChange(val: string[]) {
  // You can update chart or filter logic here
  // val: [] for 全国, [province], or [province, city]
  // Example: console.log('Location changed:', val)
}

async function updateChart(val: string) {
  console.log('🔍 updateChart 被调用，时间值:', val);
  
  // 获取当前选中的城市
  const city = selectedMapCity.value && selectedMapCity.value.length > 1
    ? selectedMapCity.value[1]
    : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');
  
  // 使用传递的时间值，如果没有则使用selectedDate.value
  const timeValue = val || selectedDate.value;
  console.log('🔍 使用的时间值:', timeValue);
  
  // 获取航线数据
  await fetchRouteDistribution(timeValue, city);
  
  // 更新地图
  renderMap();
  
  // 获取当前选中的城市
  const start = selectedStartCity.value && selectedStartCity.value.length > 1
    ? selectedStartCity.value[1]
    : (selectedStartCity.value && selectedStartCity.value.length === 1 ? selectedStartCity.value[0] : '');
  const end = selectedEndCity.value && selectedEndCity.value.length > 1
    ? selectedEndCity.value[1]
    : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');
  
  // 更新统计数据
  await fetchStatisticsSummary(timeValue, start, end);
  await fetchStatisticsTrend(timeValue, start, end);
  renderCubeBarChart();
}

function handleMapCityChange(val: string[]) {
  // 获取选中的城市
  const city = val && val.length > 1 ? val[1] : (val && val.length === 1 ? val[0] : '');
  
  // 重新获取航线数据并更新地图
  fetchRouteDistribution(selectedDate.value, city).then(() => {
    renderMap();
  });
}
async function handleStartCityChange(val: string[]) {
  // 处理起始城市的变化
  const start = val && val.length > 1 ? val[1] : (val && val.length === 1 ? val[0] : '');
  const end = selectedEndCity.value && selectedEndCity.value.length > 1
    ? selectedEndCity.value[1]
    : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');
  
  await fetchStatisticsSummary(selectedDate.value, start, end);
  await fetchStatisticsTrend(selectedDate.value, start, end);
  renderCubeBarChart();
}

async function handleEndCityChange(val: string[]) {
  // 处理终点城市的变化
  const end = val && val.length > 1 ? val[1] : (val && val.length === 1 ? val[0] : '');
  const start = selectedStartCity.value && selectedStartCity.value.length > 1
    ? selectedStartCity.value[1]
    : (selectedStartCity.value && selectedStartCity.value.length === 1 ? selectedStartCity.value[0] : '');
  
  await fetchStatisticsSummary(selectedDate.value, start, end);
  await fetchStatisticsTrend(selectedDate.value, start, end);
  renderCubeBarChart();
}

async function handleSearch() {
  // 获取选中的起始城市和终点城市
  const start = selectedStartCity.value && selectedStartCity.value.length > 1
    ? selectedStartCity.value[1]
    : (selectedStartCity.value && selectedStartCity.value.length === 1 ? selectedStartCity.value[0] : '');
  const end = selectedEndCity.value && selectedEndCity.value.length > 1
    ? selectedEndCity.value[1]
    : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');

  // 调用API获取统计数据
  await fetchStatisticsSummary(selectedDate.value, start, end);
  await fetchStatisticsTrend(selectedDate.value, start, end);

  // 刷新柱状图
  renderCubeBarChart();
}
// 生命周期钩子
const statTypeLabelMap: Record<string, string> = {
  capacity: '运力',
  volume: '运量',
  flights: '航班数量'
};

const statTypeOptions = [
  { value: 'capacity', label: '运力统计' },
  { value: 'volume', label: '运量统计' },
  { value: 'flights', label: '航班数量' }
];

const cubeChartRef = ref<HTMLElement | null>(null);
let cubeChartInstance: echarts.ECharts | null = null;

const registerCustomShapes = () => {
  const offsetX = 12;
  const offsetY = 7;

  // 左侧面
  const CubeLeft = echarts.graphic.extendShape({
    shape: { x: 0, y: 0 },
    buildPath(ctx, shape) {
      const xAxisPoint = shape.xAxisPoint;
      const c0 = [shape.x, shape.y];
      const c1 = [shape.x - offsetX, shape.y - offsetY];
      const c2 = [xAxisPoint[0] - offsetX, xAxisPoint[1] - offsetY];
      const c3 = [xAxisPoint[0], xAxisPoint[1]];
      ctx.moveTo(c0[0], c0[1]);
      ctx.lineTo(c1[0], c1[1]);
      ctx.lineTo(c2[0], c2[1]);
      ctx.lineTo(c3[0], c3[1]);
      ctx.closePath();
    }
  });
  // 右侧面
  const CubeRight = echarts.graphic.extendShape({
    shape: { x: 0, y: 0 },
    buildPath(ctx, shape) {
      const xAxisPoint = shape.xAxisPoint;
      const c1 = [shape.x, shape.y];
      const c2 = [xAxisPoint[0], xAxisPoint[1]];
      const c3 = [xAxisPoint[0] + offsetX, xAxisPoint[1] - offsetY];
      const c4 = [shape.x + offsetX, shape.y - offsetY];
      ctx.moveTo(c1[0], c1[1]);
      ctx.lineTo(c2[0], c2[1]);
      ctx.lineTo(c3[0], c3[1]);
      ctx.lineTo(c4[0], c4[1]);
      ctx.closePath();
    }
  });
  // 顶面
  const CubeTop = echarts.graphic.extendShape({
    shape: { x: 0, y: 0 },
    buildPath(ctx, shape) {
      const c1 = [shape.x, shape.y];
      const c2 = [shape.x + offsetX, shape.y - offsetY];
      const c3 = [shape.x, shape.y - offsetX];
      const c4 = [shape.x - offsetX, shape.y - offsetY];
      ctx.moveTo(c1[0], c1[1]);
      ctx.lineTo(c2[0], c2[1]);
      ctx.lineTo(c3[0], c3[1]);
      ctx.lineTo(c4[0], c4[1]);
      ctx.closePath();
    }
  });

  echarts.graphic.registerShape('CubeLeft', CubeLeft);
  echarts.graphic.registerShape('CubeRight', CubeRight);
  echarts.graphic.registerShape('CubeTop', CubeTop);
};

const getLast12Months = () => {
  const months = [];
  const now = new Date();
  for (let i = 11; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(`${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}`);
  }
  return months;
};

const generateRandomData = (max: number) => {
  return Array.from({ length: 12 }, () => Math.floor(Math.random() * (max * 0.8)) + Math.floor(max * 0.2));
};



const statMaxMap = {
  capacity: 1500,
  volume: 1200,
  flights: 200
};

// 获取当前统计类型的最大值
const getCurrentMax = () => {
  const data = filteredTrendData[selectedStatType.value];
  if (!data || data.length === 0) return 100; // 默认最大值
  return Math.max(...data);
};

const renderCubeBarChart = () => {
  if (!cubeChartRef.value) return;
  if (cubeChartInstance) cubeChartInstance.dispose();

  registerCustomShapes();

  cubeChartInstance = echarts.init(cubeChartRef.value);

  // 使用后端返回的月份数据，如果没有则使用默认的12个月
  const months = filteredTrendData.months && filteredTrendData.months.length > 0 
    ? filteredTrendData.months 
    : getLast12Months();
  const currentMax = getCurrentMax();
  const MAX = Array(months.length).fill(currentMax);
  const VALUE = filteredTrendData[selectedStatType.value] || Array(months.length).fill(0);

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params: any) {
        const item = params[1];
        return item.name + ' : ' + item.value + (selectedStatType.value === 'flights' ? ' 班次' : ' 人次');
      }
    },
    grid: { left: '10%', right: '10%', top: '15%', bottom: '10%', containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { show: true, lineStyle: { width: 2, color: '#2B7BD6' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 12, color: '#000305', rotate: 30 }
    },
    yAxis: {
      type: 'value',
      name: selectedStatType.value === 'capacity' ? '人次' : selectedStatType.value === 'volume' ? '人次' : '班次',
      nameTextStyle: { color: '#052233' },
      axisLine: { show: true, lineStyle: { width: 2, color: '#2B7BD6' } },
      splitLine: { show: true, lineStyle: { color: 'rgba(43, 123, 214, 0.2)' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 12, color: '#000305' }
    },
    series: [
      {
        type: 'custom',
        renderItem: function(params: any, api: any) {
          const location = api.coord([api.value(0), api.value(1)]);
          return {
            type: 'group',
            children: [
              {
                type: 'CubeLeft',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: { fill: `rgba(25,155,172,.1)` }
              },
              {
                type: 'CubeRight',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: { fill: `rgba(25,155,172,.3)` }
              },
              {
                type: 'CubeTop',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: { fill: `rgba(25,155,172,.4)` }
              }
            ]
          };
        },
        data: MAX
      },
      {
        type: 'custom',
        renderItem: function(params: any, api: any) {
          const location = api.coord([api.value(0), api.value(1)]);
          const index = params.dataIndex;
          const colors = [
            "25,155,172", "45,183,202", "65,211,232",
            "85,239,255", "105,200,255", "125,180,255", "145,160,255", "25,155,172", "45,183,202", "65,211,232",
            "85,239,255", "105,200,255"
          ];
          const color = colors[index % colors.length];
          return {
            type: 'group',
            children: [
              {
                type: 'CubeLeft',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: { fill: `rgba(${color}, .5)` }
              },
              {
                type: 'CubeRight',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: {
                  fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${color},1)` },
                    { offset: 1, color: `rgba(${color},.5)` }
                  ])
                }
              },
              {
                type: 'CubeTop',
                shape: { api, x: location[0], y: location[1], xAxisPoint: api.coord([api.value(0), 0]) },
                style: {
                  fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${color},1)` },
                    { offset: 1, color: `rgba(${color},1)` }
                  ])
                }
              }
            ]
          };
        },
        data: VALUE
      },
      {
        type: 'bar',
        label: {
          show: true,
          position: 'top',
          formatter: (e: any) => e.value,
          fontSize: 10,
          color: '#000000',
          offset: [0, -25]
        },
        itemStyle: { color: 'transparent' },
        data: VALUE
      }
    ]
  };

  cubeChartInstance.setOption(option);
};

const handleCubeResize = () => {
  cubeChartInstance?.resize();
};

watch(
  () => cubeChartRef.value,
  (el) => {
    if (el) {
      renderCubeBarChart();
    }
  },
  { immediate: true }
);

onMounted(async () => {
  console.log('🚀 页面开始初始化...');
  
  try {
    // 1. 首先加载城市数据
    await loadCityData();
    console.log('✅ 城市数据加载完成');
    
    // 2. 等待DOM完全渲染
    await nextTick();
    // 额外等待一小段时间确保DOM完全准备好
    await new Promise(resolve => setTimeout(resolve, 100));
    console.log('✅ DOM更新完成');
    
    // 3. 初始化图表
    const chartsInitialized = initCharts();
    if (!chartsInitialized) {
      console.error('❌ 图表初始化失败，尝试延迟初始化...');
      // 如果初始化失败，延迟重试
      await new Promise(resolve => setTimeout(resolve, 500));
      const retryResult = initCharts();
      if (!retryResult) {
        console.error('❌ 图表初始化最终失败');
        return;
      }
    }
    console.log('✅ 图表初始化完成');
    
    // 4. 添加窗口大小监听
    window.addEventListener('resize', handleResize);
    window.addEventListener('resize', handleCubeResize);
    
    // 5. 加载默认数据（全国数据）
    console.log('📊 开始加载默认数据...');
    
    // 并行加载所有数据
    await Promise.all([
      fetchRouteDistribution(selectedDate.value),
      fetchStatisticsSummary(selectedDate.value),
      fetchStatisticsTrend(selectedDate.value)
    ]);
    
    console.log('✅ 所有数据加载完成');
    
    // 6. 渲染图表
    renderMap();
    renderCubeBarChart();
    
    console.log('✅ 图表渲染完成');
  } catch (error) {
    console.error('❌ 页面初始化过程中出现错误:', error);
    // 即使出错也要尝试渲染默认数据
    try {
      renderMap();
      renderCubeBarChart();
    } catch (renderError) {
      console.error('❌ 渲染默认数据也失败:', renderError);
    }
  }
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('resize', handleCubeResize);
  if (cubeChartInstance) cubeChartInstance.dispose();
});
watch(() => selectedStatType.value, () => {
  nextTick(() => renderCubeBarChart());
});

// 监听时间变化，重新获取数据
watch(() => selectedDate.value, async (newVal, oldVal) => {
  console.log('🔍 selectedDate 发生变化:', { oldVal, newVal });
  
  // 获取当前选中的城市
  const city = selectedMapCity.value && selectedMapCity.value.length > 1
    ? selectedMapCity.value[1]
    : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');
  
  // 重新获取航线数据
  await fetchRouteDistribution(newVal, city);
  renderMap();
  
  const start = selectedStartCity.value && selectedStartCity.value.length > 1
    ? selectedStartCity.value[1]
    : (selectedStartCity.value && selectedStartCity.value.length === 1 ? selectedStartCity.value[0] : '');
  const end = selectedEndCity.value && selectedEndCity.value.length > 1
    ? selectedEndCity.value[1]
    : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');
  
  await fetchStatisticsSummary(newVal, start, end);
  await fetchStatisticsTrend(newVal, start, end);
  renderCubeBarChart();
});
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

body {
  background: linear-gradient(135deg, #1a2a6c, #2c3e50);
  color: #fff;
  min-height: 100vh;
}

.dashboard {
  display: flex;
  gap: 9px;
  max-width: 1800px;
  margin: 0 auto;
}

.left-panel {
  flex: 2;
  border-radius: 2px;
  padding: 10px;
  margin-left: 2px;
  display: flex;
  flex-direction: column;
}

.right-panel {
  flex: 1;
  border-radius: 2px;
  padding: 10px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  gap: 10px;
  backdrop-filter: blur(10px);
}

.panel-title {
  display: flex;
  align-items: center;
  color: #000;
  gap: 12px;
  margin-bottom: 10px;
  font-size: 1.2rem;
  padding-bottom: 10px;
  border-bottom: 2px solid rgba(70, 130, 180, 0.5);
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  flex-direction: row; 
  align-items: flex-end; 
}

.filter-group {
  flex: 1;
  min-width: 180px;
  flex-wrap: wrap;
  flex-direction: row;
  align-items: flex-end;
}

.filter-group label {
  white-space: nowrap;
  margin-bottom: 3px;
  margin-right: 8px;
  font-weight: 600;
  color: #7cb9e8;
}

.chart-container {
  flex: 1;
  min-height: 700px;
  border-radius: 10px;
  overflow: hidden;
  background: rgba(10, 20, 40, 0.4);
}

.stats-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.stat-card {
  background: rgba(20, 40, 80, 0.6);
  border-radius: 10px;
  padding: 5px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  transition: transform 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-5px);
  background: rgba(30, 60, 120, 0.7);
}

.stat-card h3 {
  font-size: 1.1rem;
  margin-bottom: 1px;
  color: #7cb9e8;
}

.stat-card .value {
  font-size: 1.8rem;
  font-weight: 700;
  color: #64feda;
}

.stat-card .unit {
  font-size: 0.9rem;
  color: #aaa;
}

.bar-chart-container {
  flex: 1;
  min-height: 300px;
  border-radius: 10px;
  overflow: hidden;
}

.bar-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between; /* 或 flex-start，看你想左对齐还是两端对齐 */
  margin-bottom: 10px; /* 适当调整间距 */
}

.bar-chart-header .chart-title {
  margin: 0;
}

.bar-chart-container .chart-title {
  text-align: center;
  margin-top: 5px;
  color: #2B7BD6;
  font-weight: bold;
  font-size: 1.1rem;
  letter-spacing: 1px;
}

.stat-selector label {
  font-weight: 600;
  color: #7cb9e8;
}

.footer {
  text-align: center;
  margin-top: 30px;
  padding: 20px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.9rem;
}

@media (max-width: 1200px) {
  .dashboard {
    flex-direction: column;
  }

  .filters {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .stats-cards {
    grid-template-columns: 1fr;
  }

  .header h1 {
    font-size: 2rem;
  }
} </style>