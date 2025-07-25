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
                value-format="yyyy-MM"
                @change="updateChart"
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
                @change="handleStartCityChange"
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
                @change="handleEndCityChange"
                clearable
                style="width: 40%"
            ></el-cascader>
          </div>
        </div>

        <div class="stats-cards">
          <div class="stat-card">
            <h3>🛫 总运力</h3>
            <div class="value">1,258,000</div>
            <div class="unit">人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛩️ 总运量</h3>
            <div class="value">982,000</div>
            <div class="unit">人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛫 航班数量</h3>
            <div class="value">1,280</div>
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
import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed } from 'vue';
import type { ElSelect, ElOption, CascaderOption, CascaderProps } from 'element-plus';
import { Decoration1 , Decoration7 } from 'datav-vue3';
import * as echarts from 'echarts';
import chinaMap from '@/assets/china.json';
import * as XLSX from 'xlsx';

echarts.registerMap('china', chinaMap);


const selectedDate = ref('2023-07');
const selectedMapCity = ref([''] as string[]); // 地图查看城市
const selectedStartCity = ref([''] as string[]); // 起始城市
const selectedEndCity = ref([''] as string[]); // 终点城市
const selectedStatType = ref('capacity');
const provinces = ref(['北京', '上海', '广东', '江苏', '浙江', '四川', '山东', '河南', '湖北', '湖南']);
const cityMap = ref<Record<string, string[]>>({});
const geoCoordMap = ref<Record<string, [number, number]>>({});

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
const barChart = ref(null);
// 地理坐标数据
// 航线数据
const datas = [[{name: '上海'}, {name: '北京', value: 322}],
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
  mapChart.value = echarts.init(document.getElementById('map-chart'));
  renderMap();
  barChart.value = echarts.init(document.getElementById('bar-chart'));
  renderBarChart();
};
// 渲染地图
const renderMap = () => {
  // 获取当前选择的城市
  let city = selectedMapCity.value && selectedMapCity.value.length > 1
    ? selectedMapCity.value[1]
    : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');

  // 过滤航线数据
  let filteredDatas = datas;
  if (city && city !== '') {
    filteredDatas = datas.filter(d => d[0].name === city);
  }

  // 有航线的城市
  const flightCities = new Set(filteredDatas.flatMap(d => [d[0].name, d[1].name]));
  // 所有城市
  const allCities = Object.keys(geoCoordMap.value);

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
      itemStyle: {normal: {areaColor: '#323c48', borderColor: '#404a59'}, emphasis: {areaColor: '#2a333d'}}
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
  mapChart.value.setOption(option);
};
// 渲染柱状图
const renderBarChart = () => {
  // 模拟不同统计类型的数据
  const data = {
    capacity: [1258, 1120, 980, 865, 790, 720, 680],
    volume: [982, 860, 745, 680, 610, 580, 520],
    flights: [128, 112, 98, 85, 76, 70, 65]
  };
  const option = {
    backgroundColor: 'rgba(10, 20, 40, 0.3)',
    tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}},
    grid: {left: '3%', right: '4%', bottom: '3%', top: '10%', containLabel: true},
    xAxis: {
      type: 'category',
      data: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
      axisLine: {lineStyle: {color: '#7cb9e8'}},
      axisLabel: {color: '#fff'}
    },
    yAxis: {
      type: 'value',
      name: selectedStatType.value === 'capacity' ? '运力(吨)' : selectedStatType.value === 'volume' ? '运量(吨)' : '航班数量',
      nameTextStyle: {color: '#7cb9e8'},
      axisLine: {lineStyle: {color: '#7cb9e8'}},
      axisLabel: {color: '#fff'},
      splitLine: {lineStyle: {color: 'rgba(124, 185, 232, 0.2)'}}
    },
    series: [{
      name: selectedStatType.value === 'capacity' ? '运力' : selectedStatType.value === 'volume' ? '运量' : '航班数',
      type: 'bar',
      barWidth: '60%',
      data: data[selectedStatType.value],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{offset: 0, color: '#83bff6'}, {
          offset: 0.5,
          color: '#188df0'
        }, {offset: 1, color: '#188df0'}])
      },
      emphasis: {
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{
            offset: 0,
            color: '#2378f7'
          }, {offset: 0.7, color: '#2378f7'}, {offset: 1, color: '#83bff6'}])
        }
      }
    }]
  };
  barChart.value.setOption(option);
};
// 处理窗口大小变化
const handleResize = () => {
  if (mapChart.value) {
    mapChart.value.resize();
  }
  if (barChart.value) {
    barChart.value.resize();
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

function updateChart(val: string) {
  // 这里可以调用 renderMap() 或其他刷新逻辑
  renderMap();
}

function handleMapCityChange(val: string[]) {
  renderMap();
}
function handleStartCityChange(val: string[]) {
  // 处理起始城市的变化
}
function handleEndCityChange(val: string[]) {
  // 处理终点城市的变化
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
      ctx.moveTo(c0[0], c0[1]).lineTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).closePath();
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
      ctx.moveTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).lineTo(c4[0], c4[1]).closePath();
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
      ctx.moveTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).lineTo(c4[0], c4[1]).closePath();
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

const renderCubeBarChart = () => {
  if (!cubeChartRef.value) return;
  if (cubeChartInstance) cubeChartInstance.dispose();

  registerCustomShapes();

  cubeChartInstance = echarts.init(cubeChartRef.value);

  const months = getLast12Months();
  const max = statMaxMap[selectedStatType.value];
  const MAX = Array(12).fill(max);
  const VALUE = generateRandomData(max);

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

onMounted(() => {
  loadCityData().then(() => {
    nextTick(() => {
      initCharts();
      window.addEventListener('resize', handleResize);
      window.addEventListener('resize', handleCubeResize);
    });
  });
});
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  window.removeEventListener('resize', handleCubeResize);
  if (cubeChartInstance) cubeChartInstance.dispose();
});
watch(() => selectedStatType.value, () => {
  nextTick(() => renderCubeBarChart());
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
  gap: 20px;
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