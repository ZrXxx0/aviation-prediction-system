<template>
  <div class="dashboard-container">
    <div class="header">
      <div class="title">航线运量趋势统计</div>
      <div class="decoration"></div>
    </div>

    <div class="controls">
      <el-date-picker
          v-model="selectedDate"
          type="month"
          placeholder="选择年月"
          value-format="yyyy-MM"
          @change="updateChart"
      >
      </el-date-picker>
      <el-select
          v-model="selectedCity"
          placeholder="选择城市"
          style="margin-left: 10px; width: 200px;"
          @change="updateChart"
      >
        <el-option
            v-for="city in cities"
            :key="city"
            :label="city"
            :value="city"
        >
        </el-option>
      </el-select>
    </div>

    <!-- 指标卡片 -->
    <div class="metrics-container">
      <div class="metric-card">
        <div class="metric-card-left">
          <div class="metric-icon metric-icon-volume">
            <!-- 运量图标：飞机货运箱 -->
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M4 24l24-8-24-8v6l16 2-16 2v6z" fill="#fccb05"/><rect x="2" y="22" width="4" height="8" rx="1" fill="#f5804d"/></svg>
          </div>
          <div class="metric-title">运量</div>
        </div>
        <div class="metric-card-right">
          <div class="metric-value">{{ metrics.volume }}<span class="unit">人次</span></div>
          <div class="metric-change">
            <span :class="metrics.volumeChange >= 0 ? 'positive' : 'negative'">
              {{ metrics.volumeChange >= 0 ? '↑' : '↓' }} {{ Math.abs(metrics.volumeChange) }}%
            </span>
            较上月
          </div>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-card-left">
          <div class="metric-icon metric-icon-capacity">
            <!-- 运力图标：飞机 -->
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none"><path d="M2 28l28-12-28-12v6l20 6-20 6v6z" fill="#8bd46e"/><rect x="26" y="22" width="4" height="8" rx="1" fill="#09bcb7"/></svg>
          </div>
          <div class="metric-title">运力</div>
        </div>
        <div class="metric-card-right">
          <div class="metric-value">{{ metrics.capacity }}<span class="unit">人次</span></div>
          <div class="metric-change">
            <span :class="metrics.capacityChange >= 0 ? 'positive' : 'negative'">
              {{ metrics.capacityChange >= 0 ? '↑' : '↓' }} {{ Math.abs(metrics.capacityChange) }}%
            </span>
            较上月
          </div>
        </div>
      </div>
    </div>

    <!-- 图表容器 -->
    <div class="chart-container">
      <div ref="chart" style="width: 100%; height: 320px;"></div>
    </div>
  </div>
</template>

<script>
import * as echarts from 'echarts';

export default {
  name: 'AirlineDashboard',
  data() {
    return {
      selectedDate: '2023-12',
      selectedCity: '全国',
      cities: ['全国', '北京', '上海', '广州', '深圳', '成都', '重庆', '杭州', '西安', '武汉'],
      chartInstance: null,
      metrics: {
        volume: 0,
        capacity: 0,
        flights: 0,
        utilization: 0,
        volumeChange: 0,
        capacityChange: 0,
        flightsChange: 0,
        utilizationChange: 0
      }
    };
  },
  mounted() {
    this.initChart();
    this.updateMetrics();
    window.addEventListener('resize', this.resizeChart);
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeChart);
    if (this.chartInstance) {
      this.chartInstance.dispose();
    }
  },
  methods: {
    initChart() {
      this.chartInstance = echarts.init(this.$refs.chart);
      this.updateChart();
    },
    resizeChart() {
      if (this.chartInstance) {
        this.chartInstance.resize();
      }
    },
    updateChart() {
      if (!this.chartInstance) return;

      const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];

      // 模拟数据生成
      const volumeData = months.map(() => Math.floor(Math.random() * 10000) + 5000);
      const capacityData = months.map(() => Math.floor(Math.random() * 12000) + 6000);
      const flightsData = months.map(() => Math.floor(Math.random() * 800) + 200);

      const option = {
        backgroundColor: 'transparent',
        title: {
          text: `${this.selectedCity} - 航线运量趋势`,
          textStyle: {
            align: 'center',
            color: '#000',
            fontSize: 20,
          },
          top: '5%',
          left: 'center',
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: {
            type: 'cross',
            crossStyle: {
              color: '#999'
            }
          },
          formatter: function(params) {
            let result = `<div style="margin-bottom:5px;font-weight:bold;color:#000">${params[0].name}</div>`;
            params.forEach(item => {
              let value = item.value;
              let unit = item.seriesName === '航班数' ? '班次' : '吨';

              if (item.seriesName === '利用率') {
                value = value.toFixed(1) + '%';
              } else {
                value = value.toLocaleString() + ` ${unit}`;
              }

              result += `
                <div style="display:flex;align-items:center;margin:3px 0; color:#000;">
                  <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${item.color};margin-right:5px"></span>
                  ${item.seriesName}: ${value}
                </div>
              `;
            });
            return result;
          }
        },
        legend: {
          data: ['运量', '运力', '航班数', '利用率'],
          right: 10,
          top: 12,
          textStyle: {
            color: "#000"
          },
          itemWidth: 12,
          itemHeight: 10,
        },
        grid: {
          left: '2%',
          right: '4%',
          bottom: '14%',
          top: '16%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: months,
          axisLine: {
            lineStyle: {
              color: '#000'
            }
          },
          axisLabel: {
            textStyle: {
              fontFamily: 'Microsoft YaHei',
              color: '#000'
            }
          },
        },
        yAxis: [
          {
            type: 'value',
            name: '吨',
            nameTextStyle: {
              color: '#000'
            },
            axisLine: {
              show: true,
              lineStyle: {
                color: '#000'
              }
            },
            splitLine: {
              show: true,
              lineStyle: {
                color: 'rgba(0,0,0,0.1)'
              }
            },
            axisLabel: {
              color: '#000'
            }
          },
          {
            type: 'value',
            name: '航班数',
            nameTextStyle: {
              color: '#000'
            },
            position: 'right',
            axisLine: {
              show: true,
              lineStyle: {
                color: '#000'
              }
            },
            splitLine: {
              show: false
            },
            axisLabel: {
              color: '#000',
              formatter: '{value} 班次'
            }
          }
        ],
        dataZoom: [{
          show: true,
          height: 12,
          xAxisIndex: [0],
          bottom: '8%',
          start: 0,
          end: 100,
          handleIcon: 'path://M306.1,413c0,2.2-1.8,4-4,4h-59.8c-2.2,0-4-1.8-4-4V200.8c0-2.2,1.8-4,4-4h59.8c2.2,0,4,1.8,4,4V413z',
          handleSize: '110%',
          handleStyle: {
            color: "#d3dee5",
          },
          textStyle: {
            color: "#000"
          },
          borderColor: "#90979c"
        }],
        series: [
          {
            name: '运量',
            type: 'bar',
            barWidth: '15%',
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#fccb05' },
                { offset: 1, color: '#f5804d' }
              ]),
              borderRadius: [5, 5, 0, 0]
            },
            data: volumeData
          },
          {
            name: '运力',
            type: 'bar',
            barWidth: '15%',
            itemStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#8bd46e' },
                { offset: 1, color: '#09bcb7' }
              ]),
              borderRadius: [5, 5, 0, 0]
            },
            data: capacityData
          },
          {
            name: '航班数',
            type: 'line',
            yAxisIndex: 1,
            symbol: 'circle',
            symbolSize: 8,
            lineStyle: {
              width: 3,
              color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
                { offset: 0, color: '#248ff7' },
                { offset: 1, color: '#6851f1' }
              ])
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(36, 143, 247, 0.5)' },
                { offset: 1, color: 'rgba(104, 81, 241, 0.2)' }
              ])
            },
            data: flightsData
          },
          {
            name: '利用率',
            type: 'line',
            symbol: 'none',
            lineStyle: {
              width: 2,
              type: 'dashed',
              color: '#ff7c7c'
            },
            data: volumeData.map((v, i) => {
              return (v / capacityData[i] * 100).toFixed(1);
            })
          }
        ]
      };

      this.chartInstance.setOption(option);
      this.updateMetrics();
    },
    updateMetrics() {
      // 模拟数据更新
      const randomBase = this.selectedCity === '全国' ? 10000 : 5000;

      this.metrics.volume = Math.floor(Math.random() * randomBase) + randomBase;
      this.metrics.capacity = Math.floor(this.metrics.volume * (1.2 + Math.random() * 0.3));
      this.metrics.flights = Math.floor(Math.random() * 800) + 200;
      this.metrics.utilization = (this.metrics.volume / this.metrics.capacity * 100).toFixed(1);

      // 生成随机环比变化值（-10%到10%之间）
      this.metrics.volumeChange = (Math.random() * 20 - 10).toFixed(1);
      this.metrics.capacityChange = (Math.random() * 20 - 10).toFixed(1);
      this.metrics.flightsChange = (Math.random() * 20 - 10).toFixed(1);
      this.metrics.utilizationChange = (Math.random() * 10 - 5).toFixed(1);
    }
  }
};
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

.controls {
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.metrics-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 10px;
}

/* 新增指标卡片布局样式 */
.metric-card {
  display: flex;
  flex-direction: row;
  align-items: center;
  background: rgba(16, 42, 88, 0.5);
  border-radius: 5px;
  padding: 2px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(66, 150, 255, 0.2);
  transition: all 0.3s ease;
}

.metric-card-left {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 60px;
  min-width: 60px;
  margin-right: 10px;
}

.metric-icon {
  margin-bottom: 5px;
}

.metric-title {
  font-size: 16px;
  color: #a0b9d3;
  margin-bottom: 0;
  text-align: center;
}

.metric-card-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
}

.metric-value {
  font-size: 25px;
  font-weight: bold;
  margin-bottom: 5px;
  color: #fff;
}

.metric-value .unit {
  font-size: 16px;
  margin-left: 5px;
  color: #a0b9d3;
}

.metric-change {
  font-size: 14px;
  color: #a0b9d3;
}

.positive {
  color: #52c41a;
  font-weight: bold;
}

.negative {
  color: #f5222d;
  font-weight: bold;
}

.chart-container {
  background: rgb(255, 255, 255);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(66, 150, 255, 0.2);
}

@media (max-width: 768px) {
  .metrics-container {
    grid-template-columns: 1fr;
  }

  .controls {
    flex-direction: column;
    align-items: center;
  }

  .el-select {
    margin-left: 0;
    margin-top: 10px;
    width: 100% !important;
    max-width: 300px;
  }
}
</style>