<template>
  <div class="dashboard-container">
    <div class="dashboard-grid">
      <!-- 左侧列 -->
      <BorderBox1 class="container">
        <Panel1 />
      </BorderBox1>

      <!-- 右侧列 -->
      <BorderBox1 class="container">
        <Panel2 />
      </BorderBox1>

      <!-- 中间列 - 无边框 -->
      <div class="panel-3">
        <Panel3 />
      </div>

      <!-- 左侧列 -->
      <BorderBox1 class="container">
        <Panel4 />
      </BorderBox1>

      <!-- 右侧列 -->
      <BorderBox1 class="container">
        <Panel5 />
      </BorderBox1>
    </div>
  </div>
</template>

<script setup>
import Panel1 from '@/components/dashboard/Panel1.vue'
import Panel2 from '@/components/dashboard/Panel2.vue'
import Panel3 from '@/components/dashboard/Panel3.vue'
import Panel4 from '@/components/dashboard/Panel4.vue'
import Panel5 from '@/components/dashboard/Panel5.vue'
import { BorderBox1 } from 'datav-vue3';
</script>

<style scoped>
.dashboard-container {
  padding: 0.5rem 0.5rem;
  width: 100%;
  max-width: 100%;
  background: #efefef;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  grid-template-rows: 400px 400px;
  gap: 20px;
}

.container {
  width: 600px;
  height: 200px;
  padding: 0.1rem;
  background: white;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

/* 通用面板样式 */
.panel {
  border-radius: 8px;
  padding: 0.1rem;
  background: white;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

/* 特殊处理无边框的panel-3 */
.panel-3 {
  /* 移除所有面板样式 */
  background: transparent !important;
  box-shadow: none !important;
  padding: 0 !important;
  border-radius: 0 !important;

  /* 确保内容填满区域 */
  display: flex;
  height: 100%;
  width: 100%;
}

/* 左侧列 */
.panel-1 {
  grid-column: 1 / 2;
  grid-row: 1 / 2; /* 左上 */
}

.panel-4 {
  grid-column: 1 / 2;
  grid-row: 2 / 3; /* 左下 */
}

/* 中间列 */
.panel-3 {
  grid-column: 2 / 3;
  grid-row: 1 / 3; /* 跨两行 */
}

/* 右侧列 */
.panel-2 {
  grid-column: 3 / 4;
  grid-row: 1 / 2; /* 右上 */
}

.panel-5 {
  grid-column: 3 / 4;
  grid-row: 2 / 3; /* 右下 */
  height: 250px;   /* 保持原有高度设置 */
}

/* 调整datav边框组件的内部样式 */
.dv-border-box-1 {
  width: 100%;
  height: 100%;
}
</style>