<template>
  <div class="dashboard-container">
    <div class="header">
      <div class="title">历史预测结果</div>
      <div class="decoration"></div>
    </div>

    <div class="filters">
      <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          value-format="yyyy-MM-dd"
      />
      <el-select
          v-model="selectedCity"
          placeholder="选择城市"
          style="margin-left: 10px; width: 120px;"
      >
        <el-option
            v-for="city in cities"
            :key="city"
            :label="city"
            :value="city"
        />
      </el-select>
    </div>

    <el-table
        :data="filteredData"
        stripe
        style="width: 100%; margin-top: 15px;"
        class="prediction-table"
    >
      <el-table-column
          prop="routeName"
          label="航线名称"
          width="100"
      />
      <el-table-column
          prop="predictDate"
          label="预测时间"
          width="120"
      />
      <el-table-column
          prop="volume"
          label="预测运量"
          width="80"
      />
      <el-table-column
          prop="capacity"
          label="预测运力"
          width="100"
      />
      <el-table-column
          prop="accuracy"
          label="预测准确率"
          width="100"
          :formatter="formatAccuracy"
      />
    </el-table>
  </div>
</template>

<script>
export default {
  data() {
    return {
      selectedDate: '',
      selectedCity: '',
      cities: ['北京', '上海', '广州', '深圳', '成都', '武汉'],
      tableData: [
        { id: 1, routeName: '北京-上海', predictDate: '2023-07-10', volume: '1250吨', capacity: '1400吨', accuracy: 0.92, city: '北京' },
        { id: 2, routeName: '上海-广州', predictDate: '2023-07-11', volume: '980吨', capacity: '1100吨', accuracy: 0.87, city: '上海' },
        { id: 3, routeName: '广州-深圳', predictDate: '2023-07-12', volume: '650吨', capacity: '700吨', accuracy: 0.95, city: '广州' },
        { id: 4, routeName: '成都-武汉', predictDate: '2023-07-13', volume: '420吨', capacity: '500吨', accuracy: 0.84, city: '成都' }
      ]
    }
  },
  computed: {
    filteredData() {
      let result = this.tableData;
      if (this.selectedDate) {
        result = result.filter(item => item.predictDate === this.selectedDate);
      }
      if (this.selectedCity) {
        result = result.filter(item => item.city === this.selectedCity);
      }
      return result;
    }
  },
  methods: {
    formatAccuracy(row) {
      return `${(row.accuracy * 100).toFixed(1)}%`;
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

.filters {
  display: flex;
  margin-bottom: 5px;
}

.prediction-table {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

::v-deep .el-table th {
  background-color: #f8f9fa;
  font-weight: bold;
  color: #606266;
}

::v-deep .el-table--striped .el-table__body tr.el-table__row--striped td {
  background-color: #fafafa;
}
</style>