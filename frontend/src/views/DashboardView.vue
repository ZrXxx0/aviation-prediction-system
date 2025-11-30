<template>
  <div id="app">
    <div class="dashboard">
      <!-- 左侧面板 - 地图和筛选 -->
      <div class="left-panel">
        <div class="panel-title" style="margin-top: -15px">
          <Decoration1 :color="['#46bee9', '#46bee9']" style="width:200px;height:50px;" />
          <h2>全国航线数据统计</h2>
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
                style="width: 60%"
            ></el-date-picker>
          </div>

          <div class="filter-group">
            <label for="selectedCity"><i class="fas fa-map-marker-alt"></i> 城市筛选</label>
            <el-cascader
              id="MapSelectedCity"
              v-model="selectedMapSelectedCity"
              :options="locationOptions"
              :props="props"
              clearable
              collapse-tags
              collapse-tags-tooltip
              :show-all-levels="false"
              @change="handleMapSelectedCityChange"
              style="width: 60%"
              :max-collapse-tags="1"
              :max-collapse-tags-length="8"
            ></el-cascader>
          </div>

          <div class="filter-group">
            <label for="city"><i class="fas fa-map-marker-alt"></i> 起点城市</label>
            <el-cascader
              id="MapCity"
              v-model="selectedMapCity"
              :options="locationOptions"
              :props="cascaderProps"
              clearable
              style="width: 60%"
            ></el-cascader>
          </div>

          <div class="filter-group">
            <label for="toCity"><i class="fas fa-map-marker-alt"></i> 终点城市</label>
            <el-cascader
                id="MapToCity"
                v-model="selectedMapToCity"
                :options="locationOptions"
                :props="cascaderProps"
                clearable
                style="width: 60%"
            ></el-cascader>
          </div>

          <el-button type="primary" :icon="Search" circle @click="handleMapSearch" />
        </div>

        <div class="chart-container" id="map-chart"></div>
      </div>

      <!-- 右侧面板 - 统计信息 -->
      <div class="right-panel">
        <div class="panel-title">
          <Decoration7 style="width:250px;height:30px;">&emsp;航线统计分析&emsp;</Decoration7>
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
                style="width: 50%"
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
                style="width: 50%; margin-right: 20px"
            ></el-cascader>
            <el-button type="primary" :icon="Search" circle @click="handleSearch" />
          </div>
        </div>

        <div class="stats-cards">
          <div class="stat-card">
            <h3>🛫 总座次</h3>
            <div class="value">{{ filteredStats.capacity.toLocaleString() }}</div>
            <div class="unit">万 人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛩️ 总运量</h3>
            <div class="value">{{ filteredStats.volume.toLocaleString() }}</div>
            <div class="unit">万 人次/月</div>
          </div>
          <div class="stat-card">
            <h3>🛫 航班数量</h3>
            <div class="value">{{ filteredStats.flights.toLocaleString() }}</div>
            <div class="unit">班次/月</div>
          </div>
        </div>

        <div class="rose-chart-container">
          <!-- 玫瑰图并排两个，展示机型和机队数据 -->
          <div class="rose-charts-wrapper">
            <div class="rose-chart-item">
<!--              <div class="rose-chart-title">机型分布</div>-->
              <div ref="aircraftTypeChartRef" id="aircraft-type-chart" style="width:100%;height:280px;"></div>
            </div>
            <div class="rose-chart-item">
<!--              <div class="rose-chart-title">机队分布</div>-->
              <div ref="fleetChartRef" id="fleet-chart" style="width:100%;height:280px;"></div>
            </div>
          </div>
        </div>

        <div class="bar-chart-container">
          <div class="bar-chart-header">
            <div class="chart-title">航线数据趋势分析</div>
            <div style=" text-align: center;">
              <label style="margin-left: 5px; color: #7cb9e8;">时间周期：</label>
              <el-input-number v-model="month_number" :min="3" :max="24" @change="handleTimePeriodChange" >
                <template #suffix>
                  <span>月</span>
                </template>
              </el-input-number>
            </div>
          </div>
          <div ref="cubeChartRef" id="cube-bar-chart" style="width:100%;height:320px;min-height:200px"></div>
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
const month_number = ref(12) // 默认12个月，与timePeriod保持一致
const selectedDate = ref('2024-05'); // 默认2024年5月
const selectedMapSelectedCity = ref([['']] as any[]); // 城市筛选，默认全国
const selectedMapCity = ref([''] as string[]); // 地图查看起点城市
const selectedMapToCity = ref([''] as string[]); // 地图查看终点城市
const selectedStartCity = ref([''] as string[]); // 起始城市
const selectedEndCity = ref([''] as string[]); // 终点城市
const timePeriod = ref(12); // 时间周期，默认12个月
const cityMap = ref<Record<string, string[]>>({});
const geoCoordMap = ref<Record<string, [number, number]>>({});

// 航线数据 - 保存完整的后端返回数据
const routeData = ref<any[]>([]);
// 转换后的航线数据 - 用于地图显示
const convertedRouteData = ref<any[]>([]);

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

// 机型和机队数据
const aircraftData = reactive({
  aircraftTypes: [],
  fleetData: []
});

// 省份运量数据
const provinceVolumeData = ref([]);

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
    
    // 保存完整的后端数据
    routeData.value = data;
    
    // 转换数据格式为前端地图需要的格式
    // 后端返回格式: [{from: "上海", to: "北京", flights: 322, detail: [...]}]
    // 前端需要格式: [[{name: "上海"}, {name: "北京", value: 322}]]
    const convertedData = data.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('✅ 成功获取航线数据:', routeData.value.length, '条记录');
  } catch (error) {
    console.error('❌ 获取航线数据失败:', error);
    // 如果API失败，使用默认数据
    routeData.value = defaultRouteData;
    
    // 转换默认数据格式为前端地图需要的格式
    const convertedData = defaultRouteData.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('📊 使用默认航线数据:', convertedRouteData.value.length, '条记录');
  }
};

// 获取航线分布数据（支持起点和终点城市）
const fetchRouteDistributionWithCities = async (yearMonth: string, originCity: string, destCity: string) => {
  try {
    console.log('🔍 发送航线分布请求参数:', { yearMonth, originCity, destCity });
    const params = new URLSearchParams({ 
      year_month: yearMonth,
      city: originCity,
      to_city: destCity
    });
    
    const url = apiConfig.getUrl(apiConfig.endpoints.SHOW.ROUTE_DISTRIBUTION) + `?${params}`;
    console.log('🔍 请求URL:', url);
    
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 保存完整的后端数据
    routeData.value = data;
    
    // 转换数据格式为前端地图需要的格式
    // 后端返回格式: [{from: "上海", to: "北京", flights: 322, detail: [...]}]
    // 前端需要格式: [[{name: "上海"}, {name: "北京", value: 322}]]
    const convertedData = data.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('✅ 成功获取航线分布数据:', routeData.value.length, '条记录');
  } catch (error) {
    console.error('❌ 获取航线分布数据失败:', error);
    // 如果API失败，使用默认数据
    routeData.value = defaultRouteData;
    
    // 转换默认数据格式为前端地图需要的格式
    const convertedData = defaultRouteData.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('📊 使用默认航线数据:', convertedRouteData.value.length, '条记录');
  }
};

// 使用新的后端API获取航线分布数据（支持复杂的城市筛选逻辑）
const fetchRouteDistributionAdvanced = async (yearMonth: string, selectedCities: string[], originCity: string, destCity: string) => {
  try {
    console.log('🔍 使用高级API获取航线分布数据:', { yearMonth, selectedCities, originCity, destCity });
    
    const params = new URLSearchParams({ 
      year_month: yearMonth
    });
    
    // 添加城市筛选参数
    if (selectedCities && selectedCities.length > 0) {
      // 过滤掉空字符串（全国）
      const validCities = selectedCities.filter(city => city !== '' && city !== '全国');
      if (validCities.length > 0) {
        params.append('selected_cities', validCities.join(','));
      }
    }
    
    // 添加起点城市参数
    if (originCity && originCity !== '全国') {
      params.append('origin_city', originCity);
    }
    
    // 添加终点城市参数
    if (destCity && destCity !== '全国') {
      params.append('dest_city', destCity);
    }
    
    const url = apiConfig.getUrl(apiConfig.endpoints.SHOW.ROUTE_DISTRIBUTION_ADVANCED) + `?${params}`;
    console.log('🔍 请求URL:', url);
    
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 保存完整的后端数据
    routeData.value = data;
    
    // 转换数据格式为前端地图需要的格式
    const convertedData = data.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('✅ 成功获取高级航线分布数据:', routeData.value.length, '条记录');
  } catch (error) {
    console.error('❌ 获取高级航线分布数据失败:', error);
    // 如果API失败，使用默认数据
    routeData.value = defaultRouteData;
    
    const convertedData = defaultRouteData.map((item: any) => [
      { name: item.from },
      { name: item.to, value: item.flights }
    ]);
    
    convertedRouteData.value = convertedData;
    console.log('📊 使用默认航线数据:', convertedRouteData.value.length, '条记录');
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
    // 设置默认统计数据（万人次）
    filteredStats.capacity = 150;  // 150万人次
    filteredStats.volume = 120;    // 120万人次
    filteredStats.flights = 15000; // 航班数量保持原单位
    console.log('📊 使用默认统计数据:', filteredStats);
  }
};

const fetchStatisticsTrend = async (yearMonth: string, startCity?: string, endCity?: string) => {
  try {
    const params = new URLSearchParams({ year_month: yearMonth });
    if (startCity) params.append('start_city', startCity);
    if (endCity) params.append('end_city', endCity);
    // 添加时间周期参数，如果API支持的话
    params.append('months', timePeriod.value.toString());
    
    const response = await fetch(apiConfig.getUrl(apiConfig.endpoints.SHOW.STATISTICS_TREND) + `?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 如果后端返回的数据长度与当前时间周期不匹配，则截取或补充
    const months = data.months || [];
    const capacity = data.capacity || [];
    const volume = data.volume || [];
    const flights = data.flights || [];
    
    // 确保数据长度与时间周期一致
    const targetLength = timePeriod.value;
    filteredTrendData.months = months.length >= targetLength ? months.slice(-targetLength) : getLastNMonths(targetLength);
    filteredTrendData.capacity = capacity.length >= targetLength ? capacity.slice(-targetLength) : generateRandomData(150, targetLength);  // 150万人次
    filteredTrendData.volume = volume.length >= targetLength ? volume.slice(-targetLength) : generateRandomData(120, targetLength);      // 120万人次
    filteredTrendData.flights = flights.length >= targetLength ? flights.slice(-targetLength) : generateRandomData(200, targetLength);   // 航班数量
    
    console.log('✅ 成功获取趋势数据:', filteredTrendData);
  } catch (error) {
    console.error('❌ 获取趋势数据失败:', error);
    // 设置默认趋势数据（万人次）
    const months = getLastNMonths(timePeriod.value);
    filteredTrendData.months = months;
    filteredTrendData.capacity = generateRandomData(150, timePeriod.value);  // 150万人次
    filteredTrendData.volume = generateRandomData(120, timePeriod.value);    // 120万人次
    filteredTrendData.flights = generateRandomData(200, timePeriod.value);   // 航班数量
    console.log('📊 使用默认趋势数据:', filteredTrendData);
  }
};

// 获取机型和机队数据
const fetchAircraftData = async (yearMonth: string, startCity?: string, endCity?: string) => {
  try {
    const params = new URLSearchParams({ year_month: yearMonth });
    if (startCity) params.append('origin_province', startCity);
    if (endCity) params.append('dest_province', endCity);
    
    const response = await fetch(apiConfig.getUrl(apiConfig.endpoints.SHOW.AIRCRAFT_DATA) + `?${params}`);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    
    // 转换后端数据格式为前端需要的格式，只显示前5种，其他合并为"其他"
    const allEquipment = (data.equipment_distribution || []).map(item => ({
      value: item.flights,
      name: item.equipment,
      percentage: parseFloat(item.percentage.toFixed(2)) // 确保百分比为两位小数
    }));
    
    // 只有当机型数量大于5时才进行拆分
    if (allEquipment.length > 7) {
      // 只取前5种机型
      const top5Equipment = allEquipment.slice(0, 7);
      const otherEquipment = allEquipment.slice(7);
      
      // 计算"其他"的总数据
      const otherTotal = otherEquipment.reduce((sum, item) => sum + item.value, 0);
      const otherPercentage = parseFloat(otherEquipment.reduce((sum, item) => sum + item.percentage, 0).toFixed(2));
      
      aircraftData.aircraftTypes = [
        ...top5Equipment,
        {
          value: otherTotal,
          name: '其他',
          percentage: otherPercentage,
          children: otherEquipment // 保存其他机型的详细信息
        }
      ];
    } else {
      // 机型数量小于等于5，直接显示所有机型
      aircraftData.aircraftTypes = allEquipment;
    }
    
    // 处理机队数据，直接显示所有机队类型（不进行拆分）
    aircraftData.fleetData = (data.fleet_distribution || []).map(item => ({
      value: item.flights,
      name: item.fleet_type,
      percentage: parseFloat(item.percentage.toFixed(2)) // 确保百分比为两位小数
    }));
    console.log('✅ 成功获取机型和机队数据:', aircraftData);
  } catch (error) {
    console.error('❌ 获取机型和机队数据失败:', error);
    // 设置默认机型和机队数据（只显示前5种，其他合并为"其他"）
    const defaultEquipment = [
      { value: 35, name: 'B737', percentage: 35.00 },
      { value: 28, name: 'A320', percentage: 28.00 },
      { value: 22, name: 'B787', percentage: 22.00 },
      { value: 18, name: 'A330', percentage: 18.00 },
      { value: 15, name: 'B777', percentage: 15.00 },
      { value: 12, name: 'A350', percentage: 12.00 },
      { value: 10, name: 'B747', percentage: 10.00 },
      { value: 8, name: 'A380', percentage: 8.00 }
    ];
    
    // 只有当机型数量大于5时才进行拆分
    if (defaultEquipment.length > 7) {
      const top5Default = defaultEquipment.slice(0, 7);
      const otherDefault = defaultEquipment.slice(7);
      const otherTotal = otherDefault.reduce((sum, item) => sum + item.value, 0);
      const otherPercentage = parseFloat(otherDefault.reduce((sum, item) => sum + item.percentage, 0).toFixed(2));
      
      aircraftData.aircraftTypes = [
        ...top5Default,
        {
          value: otherTotal,
          name: '其他',
          percentage: otherPercentage,
          children: otherDefault
        }
      ];
    } else {
      aircraftData.aircraftTypes = defaultEquipment;
    }
    // 设置默认机队数据（直接显示所有机队类型）
    aircraftData.fleetData = [
      { value: 42, name: '中型窄体客机', percentage: 42.00 },
      { value: 38, name: '小型窄体客机', percentage: 38.00 },
      { value: 35, name: '大型窄体客机', percentage: 35.00 },
      { value: 28, name: '小型宽体客机', percentage: 28.00 },
      { value: 25, name: '中型宽体客机', percentage: 25.00 },
      { value: 22, name: '大型宽体客机', percentage: 22.00 },
      { value: 18, name: '大型涡扇支线客机', percentage: 18.00 }
    ];
    console.log('📊 使用默认机型和机队数据:', aircraftData);
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
// 默认航线数据（当API失败时使用）- 符合后端返回格式
const defaultRouteData = [
  {
    from: "上海",
    to: "北京",
    flights: 322,
    detail: [
      {
        from_airport: "上海虹桥国际机场",
        to_airport: "北京首都国际机场",
        flights: 322
      }
    ]
  },
  {
    from: "上海",
    to: "广州",
    flights: 350,
    detail: [
      {
        from_airport: "上海虹桥国际机场",
        to_airport: "广州白云国际机场",
        flights: 350
      }
    ]
  },
  {
    from: "北京",
    to: "上海",
    flights: 210,
    detail: [
      {
        from_airport: "北京首都国际机场",
        to_airport: "上海虹桥国际机场",
        flights: 210
      }
    ]
  },
  {
    from: "北京",
    to: "广州",
    flights: 188,
    detail: [
      {
        from_airport: "北京首都国际机场",
        to_airport: "广州白云国际机场",
        flights: 188
      }
    ]
  },
  {
    from: "北京",
    to: "成都",
    flights: 196,
    detail: [
      {
        from_airport: "北京首都国际机场",
        to_airport: "成都双流国际机场",
        flights: 196
      }
    ]
  },
  {
    from: "广州",
    to: "上海",
    flights: 104,
    detail: [
      {
        from_airport: "广州白云国际机场",
        to_airport: "上海虹桥国际机场",
        flights: 104
      }
    ]
  },
  {
    from: "广州",
    to: "北京",
    flights: 238,
    detail: [
      {
        from_airport: "广州白云国际机场",
        to_airport: "北京首都国际机场",
        flights: 238
      }
    ]
  },
  {
    from: "广州",
    to: "成都",
    flights: 282,
    detail: [
      {
        from_airport: "广州白云国际机场",
        to_airport: "成都双流国际机场",
        flights: 282
      }
    ]
  },
  {
    from: "深圳",
    to: "北京",
    flights: 156,
    detail: [
      {
        from_airport: "深圳宝安国际机场",
        to_airport: "北京首都国际机场",
        flights: 156
      }
    ]
  },
  {
    from: "杭州",
    to: "广州",
    flights: 126,
    detail: [
      {
        from_airport: "杭州萧山国际机场",
        to_airport: "广州白云国际机场",
        flights: 126
      }
    ]
  },
];
// 转换航线数据
const convertData = (data) => {
  const res = [];
  for (let i = 0; i < data.length; i++) {
    const dataItem = data[i];
    const fromCoord = geoCoordMap.value[dataItem[0].name];
    const toCoord = geoCoordMap.value[dataItem[1].name];
    if (fromCoord && toCoord) {
      // 查找对应的完整数据
      const fullData = routeData.value.find(item => 
        item.from === dataItem[0].name && item.to === dataItem[1].name
      );
      
      res.push({
        fromName: dataItem[0].name,
        toName: dataItem[1].name,
        coords: [fromCoord, toCoord],
        value: dataItem[1].value,
        detail: fullData ? fullData.detail : []
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

  // 使用从API获取的航线数据（已经通过API过滤）
  let filteredDatas = convertedRouteData.value || [];

  console.log('📊 地图数据:', {
    totalRoutes: filteredDatas.length,
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
    itemStyle: { color: '#ffb701' }, // 高亮色
    label: { show: true, position: 'right', formatter: '{b}' }
  }));

  const option = {
    backgroundColor: '#fff',
    tooltip: {
      trigger: 'item', 
      formatter: (params) => {
        if (params.data && params.data.fromName) {
          // 航线数据
          let tooltipContent = `
            <div style="padding: 8px;">
              <div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                <span style="color: #1890ff;">起始城市：</span>${params.data.fromName}
              </div>
              <div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                <span style="color: #1890ff;">终点城市：</span>${params.data.toName}
              </div>
              <div style="font-weight: bold; margin-bottom: 8px; color: #333;">
                <span style="color: #1890ff;">总航班数：</span>${params.data.value}
              </div>
          `;
          
          // 如果有详细信息，添加详情信息
          if (params.data.detail && params.data.detail.length > 0) {
            tooltipContent += `
              <div style="font-weight: bold; margin-bottom: 4px; color: #333;">
                <span style="color: #1890ff;">详情信息：</span>
              </div>
            `;
            params.data.detail.forEach((detailItem, index) => {
              tooltipContent += `
                <div style="margin-left: 8px; margin-bottom: 2px; color: #666;">
                  &#8226; ${detailItem.from_airport || '未知机场'} - ${detailItem.to_airport || '未知机场'} ${detailItem.flights || 0}
                </div>
              `;
            });
          }
          
          tooltipContent += '</div>';
          return tooltipContent;
        }
        return params.name;
      }
    },
    geo: {
      map: 'china',
      zoom: 1.2,
      label: {emphasis: {show: false}},
      roam: true,
      // itemStyle: {normal: {areaColor: '#1067b3', borderColor: '#ece8e8'}, emphasis: {areaColor: '#2a333d'}}
      //地图颜色
      itemStyle: {normal: {areaColor: '#2a333d', borderColor: '#ece8e8'}, emphasis: {areaColor: '#1067b3'}}
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
      {
        name: '航线',
        type: 'lines',
        coordinateSystem: 'geo',
        zlevel: 1,
        effect: {show: true, period: 4, trailLength: 0.02, symbol: 'arrow', symbolSize: 5},
        lineStyle: {normal: {color: '#ffeea9', width: 1, opacity: 0.6, curveness: 0.2}},
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

const props = { multiple: true }

// 处理城市筛选的变化
function handleMapSelectedCityChange(val: any[]) {
  console.log('原始选择值:', val);
  
  if (!val || val.length === 0) {
    // 如果没有选择任何城市，默认设置为全国
    selectedMapSelectedCity.value = [['']];
    return;
  }
  
  // 提取所有选中的城市名称（取每个路径的最后一个元素）
  const selectedCities = val.map(path => {
    if (Array.isArray(path)) {
      return path[path.length - 1]; // 取路径的最后一个元素
    }
    return path;
  });
  
  console.log('提取的城市名称:', selectedCities);
  
  // 检查是否包含"全国"（空字符串）
  const hasNational = selectedCities.includes('');
  // 检查是否包含其他城市
  const hasOtherCities = selectedCities.some(city => city !== '');
  
  if (hasOtherCities && hasNational) {
    // 如果选择了其他城市，自动去掉"全国"
    const filteredPaths = val.filter(path => {
      const city = Array.isArray(path) ? path[path.length - 1] : path;
      return city !== '';
    });
    selectedMapSelectedCity.value = filteredPaths;
    console.log('去掉全国后的选择:', filteredPaths);
  } else if (!hasOtherCities && !hasNational) {
    // 如果没有选择任何城市，默认设置为全国
    selectedMapSelectedCity.value = [['']];
    console.log('设置为全国');
  } else {
    // 其他情况保持原样
    selectedMapSelectedCity.value = val;
    console.log('保持原样');
  }
  
  console.log('最终城市筛选变化:', selectedMapSelectedCity.value);
  
  // 当城市筛选发生变化时，自动触发地图搜索
  handleMapSearch();
}

function handleLocationChange(val: string[]) {
  // You can update chart or filter logic here
  // val: [] for 全国, [province], or [province, city]
  // Example: console.log('Location changed:', val)
}

async function handleStartCityChange(val: string[]) {
  // 处理起始城市的变化
  const start = val && val.length > 1 ? val[1] : (val && val.length === 1 ? val[0] : '');
  const end = selectedEndCity.value && selectedEndCity.value.length > 1
    ? selectedEndCity.value[1]
    : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');
  
  await fetchStatisticsSummary(selectedDate.value, start, end);
  await fetchStatisticsTrend(selectedDate.value, start, end);
  await fetchAircraftData(selectedDate.value, start, end);
  renderCubeBarChart();
  renderAircraftTypeChart();
  renderFleetChart();
}

async function handleEndCityChange(val: string[]) {
  // 处理终点城市的变化
  const end = val && val.length > 1 ? val[1] : (val && val.length === 1 ? val[0] : '');
  const start = selectedStartCity.value && selectedStartCity.value.length > 1
    ? selectedStartCity.value[1]
    : (selectedStartCity.value && selectedStartCity.value.length === 1 ? selectedStartCity.value[0] : '');
  
  await fetchStatisticsSummary(selectedDate.value, start, end);
  await fetchStatisticsTrend(selectedDate.value, start, end);
  await fetchAircraftData(selectedDate.value, start, end);
  renderCubeBarChart();
  renderAircraftTypeChart();
  renderFleetChart();
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
  await fetchAircraftData(selectedDate.value, start, end);

  // 刷新图表
  renderCubeBarChart();
  renderAircraftTypeChart();
  renderFleetChart();
}

// 获取城市筛选中选中的城市列表
function getSelectedCities(): string[] {
  if (!selectedMapSelectedCity.value || selectedMapSelectedCity.value.length === 0) {
    return ['全国'];
  }
  
  return selectedMapSelectedCity.value.map(path => {
    if (Array.isArray(path)) {
      return path[path.length - 1]; // 取路径的最后一个元素
    }
    return path;
  });
}

// 检查是否选择了全国
function isNationalSelected(): boolean {
  const selectedCities = getSelectedCities();
  return selectedCities.includes('') || selectedCities.includes('全国');
}

async function handleMapSearch() {
  // 获取选中的起点城市和终点城市
  const fromCity = selectedMapCity.value && selectedMapCity.value.length > 1
    ? selectedMapCity.value[1]
    : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');
  const toCity = selectedMapToCity.value && selectedMapToCity.value.length > 1
    ? selectedMapToCity.value[1]
    : (selectedMapToCity.value && selectedMapToCity.value.length === 1 ? selectedMapToCity.value[0] : '');

  // 获取城市筛选中选中的城市
  const selectedCities = getSelectedCities();
  const isNational = isNationalSelected();
  
  console.log('🔍 地图搜索参数:', { 
    yearMonth: selectedDate.value, 
    selectedCities,
    isNational,
    fromCity, 
    toCity 
  });

  // 使用新的后端API，让后端处理所有逻辑
  await fetchRouteDistributionAdvanced(selectedDate.value, selectedCities, fromCity, toCity);
  
  // 更新地图显示
  renderMap();
}
// 图表相关
const cubeChartRef = ref<HTMLElement | null>(null);
let cubeChartInstance: echarts.ECharts | null = null;

// 玫瑰图相关
const aircraftTypeChartRef = ref<HTMLElement | null>(null);
const fleetChartRef = ref<HTMLElement | null>(null);
let aircraftTypeChartInstance: echarts.ECharts | null = null;
let fleetChartInstance: echarts.ECharts | null = null;

const getLastNMonths = (n: number) => {
  const months = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    months.push(`${d.getFullYear()}-${(d.getMonth() + 1).toString().padStart(2, '0')}`);
  }
  return months;
};

const getLast12Months = () => {
  return getLastNMonths(12);
};

// 处理时间周期变化
const handleTimePeriodChange = () => {
  // 更新timePeriod变量
  timePeriod.value = month_number.value;
  console.log('🔄 时间周期已更改为:', timePeriod.value, '个月');
  
  // 重新获取趋势数据
  fetchStatisticsTrend(
    selectedDate.value, 
    selectedStartCity.value[selectedStartCity.value.length - 1], 
    selectedEndCity.value[selectedEndCity.value.length - 1]
  ).then(() => {
    // 数据获取完成后重新渲染图表
    renderCubeBarChart();
  });
};

const generateRandomData = (max: number, length: number = 12) => {
  return Array.from({ length }, () => Math.floor(Math.random() * (max * 0.8)) + Math.floor(max * 0.2));
};

const renderCubeBarChart = () => {
  if (!cubeChartRef.value) return;
  if (cubeChartInstance) cubeChartInstance.dispose();

  cubeChartInstance = echarts.init(cubeChartRef.value);

  // 使用后端返回的月份数据，如果没有则使用默认的时间周期
  const months = filteredTrendData.months && filteredTrendData.months.length > 0 
    ? filteredTrendData.months 
    : getLastNMonths(timePeriod.value);
  
  // 获取数据，如果没有则生成默认数据
  const capacityData = filteredTrendData.capacity && filteredTrendData.capacity.length > 0 
    ? filteredTrendData.capacity 
    : generateRandomData(1500, timePeriod.value);
  const volumeData = filteredTrendData.volume && filteredTrendData.volume.length > 0 
    ? filteredTrendData.volume 
    : generateRandomData(1200, timePeriod.value);
  const flightsData = filteredTrendData.flights && filteredTrendData.flights.length > 0 
    ? filteredTrendData.flights 
    : generateRandomData(200, timePeriod.value);

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter(params: any) {
        let result = params[0].name + '<br/>';
        params.forEach((param: any) => {
          const marker = param.marker || '';
          const value = param.value;
          let unit = '';
          if (param.seriesName === '运力' || param.seriesName === '运量') {
            unit = ' 万 人次';
          } else if (param.seriesName === '航班数量') {
            unit = ' 班次';
          }
          result += marker + param.seriesName + ': ' + value + unit + '<br/>';
        });
        return result;
      }
    },
    legend: {
      data: ['座次', '运量', '航班数量'],
      textStyle: { color: '#052233' },
      top: 10
    },
    grid: { 
      left: '10%', 
      right: '10%', 
      top: '15%', 
      bottom: '10%', 
      containLabel: true 
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { show: true, lineStyle: { width: 2, color: '#2B7BD6' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 12, color: '#000305', rotate: 20 }
    },
    yAxis: [
      {
        type: 'value',
        name: '万 人次',
        nameTextStyle: { color: '#052233' },
        axisLine: { show: true, lineStyle: { width: 2, color: '#8c68fc' } },
        splitLine: { show: true, lineStyle: { color: 'rgba(43, 123, 214, 0.2)' } },
        axisTick: { show: false },
        axisLabel: { fontSize: 12, color: '#000305' },
        position: 'left'
      },
      {
        type: 'value',
        name: '班次',
        nameTextStyle: { color: '#052233' },
        axisLine: { show: true, lineStyle: { width: 2, color: '#44befc' } },
        splitLine: { show: false },
        axisTick: { show: false },
        axisLabel: { fontSize: 12, color: '#000305' },
        position: 'right'
      }
    ],
    series: [
      {
        name: '座次',
        type: 'line',
        yAxisIndex: 0,
        data: capacityData,
        smooth: true,
        lineStyle: {
          width: 2,
          color: '#8c68fc'
        },
        itemStyle: {
          color: '#8c68fc',
          borderWidth: 1,
          borderColor: '#fff'
        },
        // areaStyle: {
        //   color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        //     { offset: 0, color: 'rgba(78, 205, 196, 0.3)' },
        //     { offset: 1, color: 'rgba(78, 205, 196, 0.1)' }
        //   ])
        // },
        symbol: 'circle',
        symbolSize: 8
      },
      {
        name: '运量',
        type: 'line',
        yAxisIndex: 0,
        data: volumeData,
        smooth: true,
        lineStyle: {
          width: 2,
          color: '#246eff'
        },
        itemStyle: {
          color: '#246eff',
          borderWidth: 1,
          borderColor: '#fff'
        },
        // areaStyle: {
        //   color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
        //     { offset: 0, color: 'rgba(69, 183, 209, 0.3)' },
        //     { offset: 1, color: 'rgba(69, 183, 209, 0.1)' }
        //   ])
        // },
        symbol: 'diamond',
        symbolSize: 8
      },
      {
        name: '航班数量',
        type: 'bar',
        yAxisIndex: 1,
        data: flightsData,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#44befc' },
            { offset: 1, color: '#e4f0ff' }
          ]),
          borderRadius: [4, 4, 0, 0]
        },
        barWidth: '60%',
        label: {
          show: false,
          position: 'top',
          formatter: (e: any) => e.value,
          fontSize: 10,
          color: '#000305'
        }
      }
    ]
  };

  cubeChartInstance.setOption(option);
};

// 渲染机型玫瑰图
const renderAircraftTypeChart = () => {
  if (!aircraftTypeChartRef.value) return;
  if (aircraftTypeChartInstance) aircraftTypeChartInstance.dispose();

  aircraftTypeChartInstance = echarts.init(aircraftTypeChartRef.value);

  const option = {
    title: {
      text: '  机型分布',
      left: 'left',
      textStyle: {
        color: '#2B7BD6',
        fontSize: 16,
        fontWeight: 'bold',
      }
    },
    tooltip: {
      trigger: 'item',
      position: function (point: any, params: any, dom: any, rect: any, size: any) {
        // 获取图表容器的位置和大小
        const chartContainer = document.querySelector('#aircraft-type-chart') as HTMLElement;
        if (chartContainer) {
          const containerRect = chartContainer.getBoundingClientRect();
          const containerWidth = containerRect.width;
          const containerHeight = containerRect.height;
          
          // 计算tooltip的宽度和高度
          const tooltipWidth = size.contentSize[0];
          const tooltipHeight = size.contentSize[1];
          
          // 如果鼠标在图表左半部分，tooltip显示在右侧
          if (point[0] < containerWidth / 2) {
            // 确保tooltip不会超出容器右边界
            const rightPosition = point[0] + 60;
            const topPosition = Math.max(10, Math.min(point[1] - tooltipHeight / 2, containerHeight - tooltipHeight - 10));
            return [rightPosition, topPosition];
          } else {
            // 鼠标在右半部分，tooltip显示在左侧
            const leftPosition = Math.max(10, point[0] - tooltipWidth - 60);
            const topPosition = Math.max(10, Math.min(point[1] - tooltipHeight / 2, containerHeight - tooltipHeight - 10));
            return [leftPosition, topPosition];
          }
        }
        return [point[0] + 10, point[1] - 10]; // 默认位置
      },
      formatter: (params: any) => {
        const data = aircraftData.aircraftTypes.find(item => item.name === params.name);
        const percentage = data?.percentage || params.percent;
        
        // 如果是"其他"类型，显示详细的机型列表（自动分为两列）
        if (params.name === '其他' && data?.children) {
          const children = data.children;
          const midPoint = Math.ceil(children.length / 2);
          const leftColumn = children.slice(0, midPoint);
          const rightColumn = children.slice(midPoint);
          
          const leftList = leftColumn.map((child: any) => 
            `${child.name}: ${child.value} 航班 (${child.percentage.toFixed(2)}%)`
          ).join('<br/>');
          
          const rightList = rightColumn.map((child: any) => 
            `${child.name}: ${child.value} 航班 (${child.percentage.toFixed(2)}%)`
          ).join('<br/>');
          
          // 创建两列布局
          const twoColumnLayout = `
            <div style="display: flex; gap: 20px;">
              <div>${leftList}</div>
              <div>${rightList}</div>
            </div>
          `;
          
          return `${params.seriesName}<br/>${params.name}: ${params.value} 航班 (${percentage.toFixed(2)}%)<br/><br/>包含机型：<br/>${twoColumnLayout}`;
        }
        
        return `${params.seriesName}<br/>${params.name}: ${params.value} 航班 (${percentage.toFixed(2)}%)`;
      }
    },
    legend: {
      left: 'center',
      top: 'bottom',
      textStyle: {
        color: '#052233',
        fontSize: 10
      },
      data: aircraftData.aircraftTypes.map(item => item.name)
    },
    toolbox: {
      show: true,
      feature: {
        mark: { show: true },
        dataView: { show: true, readOnly: false },
        restore: { show: true },
        saveAsImage: { show: true }
      }
    },
    series: [
      {
        name: '  机型分布',
        type: 'pie',
        radius: [20, 110],
        center: ['50%', '50%'],
        roseType: 'radius',
        itemStyle: {
          borderRadius: 5
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: false,
            formatter: '{b}: {c} ({d}%)'
          }
        },
        data: aircraftData.aircraftTypes
      }
    ]
  };

  aircraftTypeChartInstance.setOption(option);
};

// 渲染机队玫瑰图
const renderFleetChart = () => {
  if (!fleetChartRef.value) return;
  if (fleetChartInstance) fleetChartInstance.dispose();

  fleetChartInstance = echarts.init(fleetChartRef.value);

  const option = {
    title: {
      text: '座级分布',
      left: 'left',
      textStyle: {
        color: '#2B7BD6',
        fontSize: 16,
        fontWeight: 'bold'
      }
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const data = aircraftData.fleetData.find(item => item.name === params.name);
        const percentage = data?.percentage || params.percent;
        return `${params.seriesName}<br/>${params.name}: ${params.value} 航班 (${percentage.toFixed(2)}%)`;
      }
    },
    legend: {
      left: 'center',
      top: 'bottom',
      textStyle: {
        color: '#052233',
        fontSize: 10
      },
      data: aircraftData.fleetData.map(item => item.name)
    },
    toolbox: {
      show: true,
      feature: {
        mark: { show: true },
        dataView: { show: true, readOnly: false },
        restore: { show: true },
        saveAsImage: { show: true }
      }
    },
    series: [
      {
        name: '座级分布',
        type: 'pie',
        radius: [20, 110],
        center: ['50%', '50%'],
        roseType: 'area',
        itemStyle: {
          borderRadius: 5
        },
        label: {
          show: false
        },
        emphasis: {
          label: {
            show: false,
            formatter: '{b}: {c} ({d}%)'
          }
        },
        data: aircraftData.fleetData
      }
    ]
  };

  fleetChartInstance.setOption(option);
};

const handleCubeResize = () => {
  cubeChartInstance?.resize();
};

const handleRoseChartsResize = () => {
  aircraftTypeChartInstance?.resize();
  fleetChartInstance?.resize();
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

watch(
  () => aircraftTypeChartRef.value,
  (el) => {
    if (el) {
      renderAircraftTypeChart();
    }
  },
  { immediate: true }
);

watch(
  () => fleetChartRef.value,
  (el) => {
    if (el) {
      renderFleetChart();
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
    window.addEventListener('resize', handleRoseChartsResize);
    
    // 5. 加载默认数据（全国数据）
    console.log('📊 开始加载默认数据...');
    
    // 并行加载所有数据
    await Promise.all([
      fetchRouteDistributionWithCities(selectedDate.value, '全国', '全国'),
      fetchStatisticsSummary(selectedDate.value),
      fetchStatisticsTrend(selectedDate.value, undefined, undefined),  // 传递undefined表示全国数据
      fetchAircraftData(selectedDate.value, undefined, undefined)
    ]);
    
    console.log('✅ 所有数据加载完成');
    
    // 6. 渲染图表
    renderMap();
    renderCubeBarChart();
    renderAircraftTypeChart();
    renderFleetChart();
    
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
  window.removeEventListener('resize', handleRoseChartsResize);
  if (cubeChartInstance) cubeChartInstance.dispose();
  if (aircraftTypeChartInstance) aircraftTypeChartInstance.dispose();
  if (fleetChartInstance) fleetChartInstance.dispose();
});


// 移除时间变化的自动更新监听器，现在只有点击查找按钮才会更新
// watch(() => selectedDate.value, async (newVal, oldVal) => {
//   console.log('🔍 selectedDate 发生变化:', { oldVal, newVal });
//   
//   // 获取当前选中的城市
//   const city = selectedMapCity.value && selectedMapCity.value.length > 1
//     ? selectedMapCity.value[1]
//     : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');
//   
//   // 重新获取航线数据
//   await fetchRouteDistribution(newVal, city);
//   renderMap();
//   
//   const start = selectedStartCity.value && selectedStartCity.value.length > 1
//     ? selectedStartCity.value[1]
//     : (selectedMapCity.value && selectedMapCity.value.length === 1 ? selectedMapCity.value[0] : '');
//   const end = selectedEndCity.value && selectedEndCity.value.length > 1
//     ? selectedEndCity.value[1]
//     : (selectedEndCity.value && selectedEndCity.value.length === 1 ? selectedEndCity.value[0] : '');
//   
//   await fetchStatisticsSummary(newVal, start, end);
//   await fetchStatisticsTrend(newVal, start, end);
//   renderCubeBarChart();
// });
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
  width: 100%;
}

.panel-title {
  display: flex;
  align-items: center;
  color: #000;
  gap: 12px;
  margin-bottom: 5px;
  font-size: 1.2rem;
  padding-bottom: 5px;
  border-bottom: 2px solid rgba(70, 130, 180, 0.5);
}

.filters {
  display: flex;
  gap: 1px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  flex-direction: row; 
  align-items: flex-end; 
}

.filter-group {
  flex: 1;
  min-width: 10px;
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

/* 控制城市筛选器的显示样式 */
:deep(.el-cascader) {
  max-width: 100%;
}

:deep(.el-cascader .el-input__inner) {
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.el-cascader .el-tag) {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

:deep(.el-cascader .el-tag .el-tag__content) {
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  min-height: 270px;
  margin-top: -30px;
  border-radius: 10px;
  overflow: hidden;
  width: 100%;
}

.rose-chart-container {
  flex: 1;
  min-height: 80px;
  border-radius: 5px;
  overflow: hidden;
}

.rose-charts-wrapper {
  display: flex;
  gap: 5px;
  height: 90%;
}

.rose-chart-item {
  flex: 1;
  border-radius: 5px;
  transition: transform 0.3s ease;
}

.bar-chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.bar-chart-header .chart-title {
  margin: 0;
}

.bar-chart-container .chart-title {
  text-align: center;
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