<template>
  <div class="model-container">
    <el-tabs v-model="activeTab" type="card" stretch>
      <el-tab-pane label="数据预测" name="forecast">
        <ForecastTab />
      </el-tab-pane>
      <el-tab-pane label="模型训练" name="model">
        <TrainTab />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref } from 'vue'

// 引入拆分好的 Tab 文件
import ForecastTab from './ForecastTab.vue'
import TrainTab from './TrainTab.vue'

const activeTab = ref('forecast')
</script>

<style scoped>
.model-container {
  width: 100%;
  padding: 20px;
  box-sizing: border-box;
  background-color: #f5f5f5;
}

.main-card {
  padding: 20px;
}

.el-tabs--card .el-tabs__header {
  background-color: #fff;
  border-bottom: 1px solid #ebeef5;
}

.el-tab-pane {
  padding: 20px 0;
}

/* 可根据需要调整 ForecastTab 和 TrainTab 的布局 */
</style>
