<template>
  <div class="dashboard-container">
    <div class="header">
      <div class="title">航线运量城市统计</div>
      <div class="decoration"></div>
    </div>

    <div>
      <el-date-picker
          v-model="selectedDate"
          type="month"
          placeholder="选择年月"
          value-format="yyyy-MM"
          @change="updateChart"
      >
      </el-date-picker>
      <el-select v-model="selectedCity" placeholder="选择城市" style="margin-left: 10px; width: 120px;">
        <el-option
            v-for="city in cities"
            :key="city"
            :label="city"
            :value="city">
        </el-option>
      </el-select>
    </div>

    <div class="chart-container">
      <div class="chart-header">
        <div class="chart-title">
          <i class="fas fa-plane-departure"></i>
          {{ selectedCity }} {{ selectedYear }}年{{ months[selectedMonth-1] }} 航线运量Top10
        </div>
        <div class="chart-stats">
          <div class="stat-card">
            <span class="stat-value">{{ formatNumber(totalPassengers) }}</span>
            <span class="stat-label">&emsp;总运量</span>
          </div>
        </div>
      </div>
      <div id="chart" ref="chartDom"></div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'FlightAnalysis',
  data() {
    return {
      years: [2023, 2024, 2025],
      months: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
      cities: ['北京', '上海', '广州', '深圳', '成都', '重庆', '杭州', '南京', '武汉', '西安', '香港', '台北'],
      selectedYear: 2025,
      selectedMonth: 7,
      selectedCity: '上海',
      chart: null,
      chartData: {
        '北京': [12360, 12140, 11290, 9250, 8550, 7690, 6750, 5850, 5345, 4245],
        '上海': [14320, 13210, 12180, 11230, 10250, 9540, 8750, 7650, 6540, 5430],
        '广州': [11250, 10240, 9540, 8750, 7650, 6540, 5430, 4320, 3210, 2100],
        '深圳': [13210, 12180, 11230, 10250, 9540, 8750, 7650, 6540, 5430, 4320],
        '成都': [9540, 8750, 7650, 6540, 5430, 4320, 3210, 2100, 1980, 1760],
        '重庆': [8750, 7650, 6540, 5430, 4320, 3210, 2100, 1980, 1760, 1540],
        '杭州': [7650, 6540, 5430, 4320, 3210, 2100, 1980, 1760, 1540, 1320],
        '南京': [6540, 5430, 4320, 3210, 2100, 1980, 1760, 1540, 1320, 1100],
        '武汉': [5430, 4320, 3210, 2100, 1980, 1760, 1540, 1320, 1100, 980],
        '西安': [4320, 3210, 2100, 1980, 1760, 1540, 1320, 1100, 980, 860],
        '香港': [15230, 14210, 13250, 12280, 11250, 10240, 9540, 8750, 7650, 6540],
        '台北': [14210, 13250, 12280, 11250, 10240, 9540, 8750, 7650, 6540, 5430]
      },
      chartNames: {
        '北京': ["上海", "广州", "深圳", "成都", "重庆", "杭州", "西安", "香港", "台北", "昆明"],
        '上海': ["北京", "广州", "深圳", "成都", "重庆", "杭州", "南京", "西安", "香港", "台北"],
        '广州': ["上海", "北京", "深圳", "成都", "重庆", "杭州", "南京", "西安", "昆明", "海口"],
        '深圳': ["上海", "北京", "广州", "成都", "重庆", "杭州", "南京", "西安", "昆明", "台北"],
        '成都': ["北京", "上海", "广州", "深圳", "重庆", "昆明", "西安", "杭州", "拉萨", "乌鲁木齐"],
        '重庆': ["北京", "上海", "广州", "深圳", "成都", "昆明", "西安", "杭州", "南京", "武汉"],
        '杭州': ["北京", "上海", "广州", "深圳", "成都", "重庆", "西安", "昆明", "厦门", "青岛"],
        '南京': ["北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "西安", "武汉", "厦门"],
        '武汉': ["北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "南京", "西安", "昆明"],
        '西安': ["北京", "上海", "广州", "深圳", "成都", "重庆", "杭州", "南京", "武汉", "乌鲁木齐"],
        '香港': ["上海", "北京", "台北", "东京", "首尔", "曼谷", "新加坡", "马尼拉", "吉隆坡", "大阪"],
        '台北': ["上海", "香港", "东京", "首尔", "曼谷", "新加坡", "大阪", "北京", "福冈", "冲绳"]
      }
    }
  },
  computed: {
    currentChartData() {
      return this.chartData[this.selectedCity] || [];
    },
    currentChartNames() {
      return this.chartNames[this.selectedCity] || [];
    },
    totalPassengers() {
      return this.currentChartData.reduce((sum, val) => sum + val, 0);
    },
    topCity() {
      return this.currentChartNames.length > 0 ?
          `${this.selectedCity} → ${this.currentChartNames[0]}` : '';
    }
  },
  watch: {
    selectedYear() {
      this.updateChart();
    },
    selectedMonth() {
      this.updateChart();
    },
    selectedCity() {
      this.updateChart();
    }
  },
  mounted() {
    this.initChart();
    this.updateChart();
    window.addEventListener('resize', this.handleResize);
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.handleResize);
    if (this.chart) {
      this.chart.dispose();
    }
  },
  methods: {
    initChart() {
      this.chart = echarts.init(this.$refs.chartDom);
    },
    formatNumber(num) {
      return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    },
    handleResize() {
      if (this.chart) {
        this.chart.resize();
      }
    },
    updateChart() {
      if (!this.chart) return;

      const colorList = ['#FFCC00', '#999999', '#CC9933', 'rgba(23, 165, 213, 1)'];
      const chartData = this.currentChartData;
      const chartName = this.currentChartNames;

      const maxValue = Math.max(...chartData);
      const emptyData = chartData.map((v, i) => {
        return {
          value: maxValue * 1.2,
          label: {
            formatter: '{a|' + this.formatNumber(v) + '}',
            position: 'right',
            rich: {
              a: {
                color: '#fff',
                fontSize: 13,
                padding: [5, 10]
              }
            }
          }
        }
      });

      const option = {
        backgroundColor: 'transparent',
        tooltip: {
          show: true,
          trigger: 'item',
          formatter: (params) => {
            const index = params.dataIndex;
            return `<b>${this.selectedCity} → ${chartName[index]}</b><br />运量: ${this.formatNumber(chartData[index])} 人次`;
          },
          backgroundColor: 'rgba(6, 19, 48, 0.9)',
          borderColor: '#3498db',
          textStyle: {
            color: '#fff'
          }
        },
        grid: {
          top: '10%',
          right: '10%',
          left: '10%',
          bottom: '10%',
          containLabel: true
        },
        xAxis: [
          { show: false },
          {
            type: 'value',
            axisLabel: { show: false },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { show: false },
            max: maxValue * 1.2
          }
        ],
        yAxis: [{
          type: 'category',
          show: true,
          inverse: true,
          data: chartName,
          axisTick: { show: false },
          axisLabel: {
            formatter: (value, index) => {
              const leftIndex = index + 1;
              if (leftIndex < 4) {
                return ["{a" + leftIndex + "|" + leftIndex + "}" + "  " + value].join("/n");
              } else {
                return ["{b|" + leftIndex + "}" + "  " + value].join("/n");
              }
            },
            color: '#fff',
            fontSize: 13,
            rich: {
              a1: {
                color: '#fff',
                backgroundColor: colorList[0],
                width: 20,
                height: 20,
                align: 'center',
                borderRadius: 10,
              },
              a2: {
                color: '#fff',
                backgroundColor: colorList[1],
                width: 20,
                height: 20,
                align: 'center',
                borderRadius: 10,
              },
              a3: {
                color: '#fff',
                backgroundColor: colorList[2],
                width: 20,
                height: 20,
                align: 'center',
                borderRadius: 10,
              },
              b: {
                color: '#fff',
                backgroundColor: colorList[3],
                width: 20,
                height: 20,
                align: 'center',
                borderRadius: 10,
              },
            }
          },
          axisLine: { show: false },
          splitLine: { show: false },
        },
          {
            type: "category",
            name: "",
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            axisLine: { show: false },
            inverse: true,
            data: chartName
          }],
        series: [
          {
            type: 'bar',
            barWidth: '30%',
            yAxisIndex: 1,
            silent: true,
            itemStyle: {
              color: 'rgba(255, 255, 255, 0.1)',
              barBorderRadius: [20, 20],
            },
            label: { show: true },
            data: emptyData
          },
          {
            show: true,
            type: 'bar',
            barWidth: '35%',
            z: 2,
            label: { show: false },
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 1, 1, [
                { offset: 0, color: '#347ce9' },
                { offset: 1, color: '#28c3db' }
              ], false),
              barBorderRadius: [20, 20],
            },
            data: chartData,
          }
        ]
      };

      this.chart.setOption(option);
    }
  }
}
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

.chart-container {
  height: 320px;
  background: rgba(16, 42, 88, 0.5);
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  border: 1px solid rgba(52, 152, 219, 0.3);
  margin-top: 5px;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 5px;
  background: rgba(10, 30, 60, 0.7);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.chart-title {
  font-size: 15px;
  color: #fdfdfd;
  display: flex;
  align-items: center;
  gap: 10px;
}

.chart-stats {
  display: flex;
  gap: 20px;
}

.stat-card {
  background: rgba(26, 188, 156, 0.2);
  padding: 2px 5px;
  border-radius: 10px;
  display: flex;
  flex-direction: row;
  align-items: center;
}

.stat-value {
  font-size: 1.2rem;
  font-weight: bold;
  color: #1abc9c;
}

.stat-label {
  font-size: 0.8rem;
  color: #bdc3c7;
}

#chart {
  width: 100%;
  height: 300px;
}

@media (max-width: 768px) {

  .chart-container {
    height: 500px;
  }

  #chart {
    height: 420px;
  }

  .chart-header {
    flex-direction: column;
    gap: 15px;
  }
}
</style>