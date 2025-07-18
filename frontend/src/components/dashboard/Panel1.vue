<template>
  <div class="dashboard-container">
    <div class="header">
      <div class="title">宏观经济指标数据</div>
      <div class="decoration"></div>
    </div>

    <div ><el-date-picker
        v-model="value1"
        type="date"
        placeholder="选择日期">
    </el-date-picker></div>

    <div class="indicators">
      <div class="indicator-card">
        <div class="indicator-icon">💰</div>
        <div class="indicator-info">
          <div class="indicator-name">GDP</div>
          <div class="indicator-value">{{ formatNumber(indicators.gdp) }}<span class="indicator-unit">亿元</span></div>
        </div>
      </div>

      <div class="indicator-card">
        <div class="indicator-icon">👥</div>
        <div class="indicator-info">
          <div class="indicator-name">人口总数</div>
          <div class="indicator-value">{{ formatNumber(indicators.population) }}<span class="indicator-unit">万人</span></div>
        </div>
      </div>

      <div class="indicator-card">
        <div class="indicator-icon">📈</div>
        <div class="indicator-info">
          <div class="indicator-name">人均可支配收入</div>
          <div class="indicator-value">{{ formatNumber(indicators.income) }}<span class="indicator-unit">元</span></div>
        </div>
      </div>
    </div>

    <div class="chart-container">
      <div ref="chartRef" id="chart"></div>
      <div class="chart-title">国民航空客运量 (近10年)</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import * as echarts from 'echarts';
import type { ElSelect, ElOption } from 'element-plus'

// 定义指标类型
interface EconomicIndicators {
  gdp: number;
  population: number;
  income: number;
}

// 响应式数据
const selectedYear = ref('2023');
const selectedProvince = ref('全国总体');
const indicators = ref<EconomicIndicators>({
  gdp: 1210207,
  population: 141178,
  income: 39218
});

const years = ref(['2020', '2021', '2022', '2023', '2024']);
const provinces = ref(['全国总体', '北京市', '上海市', '广东省', '江苏省', '浙江省', '山东省', '四川省']);
const chartRef = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;

// 格式化数字显示
const formatNumber = (num: number): string => {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

// 注册自定义立方体形状
const registerCustomShapes = () => {
  const offsetX = 12;
  const offsetY = 7;

  // 绘制左侧面
  const CubeLeft = echarts.graphic.extendShape({
    shape: {
      x: 0,
      y: 0,
    },
    buildPath: function(ctx, shape) {
      const xAxisPoint = shape.xAxisPoint;
      const c0 = [shape.x, shape.y];
      const c1 = [shape.x - offsetX, shape.y - offsetY];
      const c2 = [xAxisPoint[0] - offsetX, xAxisPoint[1] - offsetY];
      const c3 = [xAxisPoint[0], xAxisPoint[1]];
      ctx.moveTo(c0[0], c0[1]).lineTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).closePath();
    },
  });

  // 绘制右侧面
  const CubeRight = echarts.graphic.extendShape({
    shape: {
      x: 0,
      y: 0,
    },
    buildPath: function(ctx, shape) {
      const xAxisPoint = shape.xAxisPoint;
      const c1 = [shape.x, shape.y];
      const c2 = [xAxisPoint[0], xAxisPoint[1]];
      const c3 = [xAxisPoint[0] + offsetX, xAxisPoint[1] - offsetY];
      const c4 = [shape.x + offsetX, shape.y - offsetY];
      ctx.moveTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).lineTo(c4[0], c4[1]).closePath();
    },
  });

  // 绘制顶面
  const CubeTop = echarts.graphic.extendShape({
    shape: {
      x: 0,
      y: 0,
    },
    buildPath: function(ctx, shape) {
      const c1 = [shape.x, shape.y];
      const c2 = [shape.x + offsetX, shape.y - offsetY];
      const c3 = [shape.x, shape.y - offsetX];
      const c4 = [shape.x - offsetX, shape.y - offsetY];
      ctx.moveTo(c1[0], c1[1]).lineTo(c2[0], c2[1]).lineTo(c3[0], c3[1]).lineTo(c4[0], c4[1]).closePath();
    },
  });

  // 注册三个面图形
  echarts.graphic.registerShape('CubeLeft', CubeLeft);
  echarts.graphic.registerShape('CubeRight', CubeRight);
  echarts.graphic.registerShape('CubeTop', CubeTop);
};

// 生成随机数据
const generateRandomData = (): number[] => {
  const data = [];
  for (let i = 0; i < 10; i++) {
    data.push(Math.floor(Math.random() * 700) + 100);
  }
  return data;
};

// 初始化图表
const initChart = () => {
  if (!chartRef.value) return;

  // 销毁之前的图表实例
  if (chartInstance) {
    chartInstance.dispose();
  }

  // 注册自定义形状
  registerCustomShapes();

  // 创建新的图表实例
  chartInstance = echarts.init(chartRef.value);

  const offsetX = 20;
  const offsetY = 10;
  const primaryColor = "25,155,172";
  const isMaxShow = true;

  const MAX = [800, 800, 800, 800, 800, 800, 800, 800, 800, 800];
  const VALUE = generateRandomData();

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow',
      },
      formatter: function(params: any) {
        const item = params[1];
        return item.name + ' : ' + item.value + ' 百万人次';
      },
    },
    grid: {
      left: '10%',
      right: '10%',
      top: '15%',
      bottom: '10%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: ['2012', '2013', '2014', '2015', '2016', '2017', '2018', '2019', '2020', '2021'],
      axisLine: {
        show: true,
        lineStyle: {
          width: 2,
          color: '#2B7BD6',
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        fontSize: 12,
        color: '#000305'
      },
    },
    yAxis: {
      type: 'value',
      name: '百万人次',
      nameTextStyle: {
        color: '#052233'
      },
      axisLine: {
        show: true,
        lineStyle: {
          width: 2,
          color: '#2B7BD6',
        },
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: 'rgba(43, 123, 214, 0.2)',
        },
      },
      axisTick: {
        show: false,
      },
      axisLabel: {
        fontSize: 12,
        color: '#000305'
      },
    },
    series: [
      isMaxShow ? {
        type: 'custom',
        renderItem: function(params: any, api: any) {
          const location = api.coord([api.value(0), api.value(1)])
          return {
            type: 'group',
            children: [{
              type: 'CubeLeft',
              shape: {
                api,
                x: location[0],
                y: location[1],
                xAxisPoint: api.coord([api.value(0), 0])
              },
              style: {
                fill: `rgba(${primaryColor}, .1)`
              }
            }, {
              type: 'CubeRight',
              shape: {
                api,
                x: location[0],
                y: location[1],
                xAxisPoint: api.coord([api.value(0), 0])
              },
              style: {
                fill: `rgba(${primaryColor}, .3)`
              }
            }, {
              type: 'CubeTop',
              shape: {
                api,
                x: location[0],
                y: location[1],
                xAxisPoint: api.coord([api.value(0), 0])
              },
              style: {
                fill: `rgba(${primaryColor}, .4)`
              }
            }]
          }
        },
        data: MAX
      } : null,
      {
        type: 'custom',
        renderItem: (params: any, api: any) => {
          const location = api.coord([api.value(0), api.value(1)]);
          const index = params.dataIndex;
          // 为每个柱子设置不同的颜色
          const colors = [
            "25,155,172", "45,183,202", "65,211,232",
            "85,239,255", "105,200,255", "125,180,255", "145,160,255", "25,155,172", "45,183,202", "65,211,232",
          ];
          const color = colors[index % colors.length];

          return {
            type: 'group',
            children: [
              {
                type: 'CubeLeft',
                shape: {
                  api,
                  xValue: api.value(0),
                  yValue: api.value(1),
                  x: location[0],
                  y: location[1],
                  xAxisPoint: api.coord([api.value(0), 0]),
                },
                style: {
                  fill: `rgba(${color}, .5)`
                },
              },
              {
                type: 'CubeRight',
                shape: {
                  api,
                  xValue: api.value(0),
                  yValue: api.value(1),
                  x: location[0],
                  y: location[1],
                  xAxisPoint: api.coord([api.value(0), 0]),
                },
                style: {
                  fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${color},1)` },
                    { offset: 1, color: `rgba(${color},.5)` },
                  ]),
                },
              },
              {
                type: 'CubeTop',
                shape: {
                  api,
                  xValue: api.value(0),
                  yValue: api.value(1),
                  x: location[0],
                  y: location[1],
                  xAxisPoint: api.coord([api.value(0), 0]),
                },
                style: {
                  fill: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: `rgba(${color},1)` },
                    { offset: 1, color: `rgba(${color},1)` },
                  ]),
                },
              },
            ],
          };
        },
        data: VALUE,
      },
      {
        type: 'bar',
        label: {
          show: true,
          position: 'top',
          formatter: (e: any) => {
            return e.value + '次';
          },
          fontSize: 10,
          color: '#000000',
          offset: [0, -25],
        },
        itemStyle: {
          color: 'transparent',
        },
        data: VALUE,
      },
    ].filter(Boolean) as any,
  };

  chartInstance.setOption(option);
};

// 响应窗口变化
const handleResize = () => {
  chartInstance?.resize();
};

// 生命周期钩子
onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize);
  if (chartInstance) {
    chartInstance.dispose();
  }
});

// 监听筛选条件变化
watch([selectedYear, selectedProvince], () => {
  // 模拟数据变化
  indicators.value = {
    gdp: 1210207 + Math.floor(Math.random() * 100000),
    population: 141178 + Math.floor(Math.random() * 1000),
    income: 39218 + Math.floor(Math.random() * 1000)
  };

  // 重新渲染图表
  initChart();
});
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Microsoft YaHei', Arial, sans-serif;
}

body {
  background-color: #0c1d35;
  color: #fff;
  padding: 5px;
  min-height: 100vh;
}

.dashboard-container {
  max-width: 1400px;
  margin: 0 auto;
  background: linear-gradient(135deg, #0a1a32 0%, #0c2342 100%);
  border-radius: 10px;
  padding: 5px;
  box-shadow: 0 0 30px rgba(0, 78, 152, 0.3);
  border: 1px solid rgba(42, 123, 214, 0.2);
}

.header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.title {
  font-size: 15px;
  font-weight: bold;
  background: linear-gradient(90deg, #1d9dd9, #4ce2ff);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  margin-right: 20px;
  text-shadow: 0 0 10px rgba(76, 226, 255, 0.3);
}

.decoration {
  flex-grow: 1;
  height: 2px;
  background: linear-gradient(90deg, transparent, #1d9dd9, #4ce2ff, transparent);
  border-radius: 3px;
  box-shadow: 0 0 10px rgba(76, 226, 255, 0.3);
}

.indicators {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 10px;
  margin-bottom: 10px;
}

.indicator-card {
  background: rgba(16, 42, 88, 0.5);
  border-radius: 10px;
  padding: 2px;
  display: flex;
  align-items: center;
  border: 1px solid rgba(42, 123, 214, 0.3);
  transition: all 0.3s ease;
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.indicator-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 25px rgba(0, 78, 152, 0.4);
  border-color: rgba(42, 123, 214, 0.6);
}

.indicator-icon {
  width: 18px;
  height: 18px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
  font-size: 16px;
  background: rgba(25, 155, 172, 0.2);
}

.indicator-info {
  flex: 1;
}

.indicator-name {
  font-size: 16px;
  color: #8db9e6;
  margin-bottom: 5px;
}

.indicator-value {
  font-size: 18px;
  font-weight: bold;
  background: linear-gradient(90deg, #4ce2ff, #1d9dd9);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.indicator-unit {
  font-size: 14px;
  color: #8db9e6;
  margin-left: 5px;
}

.chart-container {
  height: 240px;
  background: whitesmoke;
  border-radius: 10px;
  padding: 5px;
  border: 1px solid rgba(42, 123, 214, 0.2);
}

.chart-title {
  text-align: center;
  font-size: 13px;
  margin-bottom: 2px;
  color: #020f1c;
}

#chart {
  width: 100%;
  height: 210px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .dashboard-container {
    padding: 10px;
  }
  .indicators {
    grid-template-columns: 1fr;
  }
  .filters {
    flex-direction: column;
    padding: 8px 10px;
  }
}
</style>