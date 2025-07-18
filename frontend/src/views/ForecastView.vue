<template>
  <div class="forecast-container">
    <h1>数据预测分析</h1>
    <div class="forecast-content">
      <div class="control-panel">
        <h2>预测参数设置</h2>
        <div class="form-group">
          <label>时间范围</label>
          <select v-model="timeRange">
            <option>7天</option>
            <option>30天</option>
            <option>90天</option>
          </select>
        </div>
        <button class="run-btn">运行预测</button>
      </div>
      <div class="result-area">
        <div class="chart-placeholder">预测图表将显示在这里</div>
        <div class="stats">
          <div class="stat-card">
            <h3>预期增长</h3>
            <p>+18.2%</p>
          </div>
          <div class="stat-card">
            <h3>置信区间</h3>
            <p>95%</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const timeRange = ref('30天')
</script>

<style scoped>
.forecast-container {
  padding: 1rem 2rem;
  width: 100%;
  max-width: 100%;
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

.chart-placeholder {
  height: 400px;
  background: #f8f9fa;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #95a5a6;
  font-size: 1.2rem;
}

.stats {
  display: flex;
  gap: 1rem;
}

.stat-card {
  flex: 1;
  background: white;
  border-radius: 8px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  text-align: center;
}

.stat-card h3 {
  margin-top: 0;
  color: #7f8c8d;
}

.stat-card p {
  font-size: 2rem;
  font-weight: bold;
  color: #2ecc71;
  margin: 0.5rem 0;
}

.form-group {
  margin-bottom: 1.5rem;
}

label {
  display: block;
  margin-bottom: 0.5rem;
  color: #34495e;
}

select {
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
}

.run-btn:hover {
  background: #2980b9;
}
</style>