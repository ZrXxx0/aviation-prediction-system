<template>
  <div class="dashboard-container">
    <div class="dashboard-grid">
      <!-- 左侧列 -->
      <BorderBox1 class="container panel-1">
        <Panel1 />
      </BorderBox1>

      <!-- 中间列 -->
      <div class="panel-3">
        <Panel3 />
      </div>

      <!-- 右侧列 (嵌套网格) -->
      <div class="right-column">
        <BorderBox1 class="container panel-2">
          <Panel2 />
        </BorderBox1>
        <BorderBox1 class="container panel-5">
          <Panel5 />
        </BorderBox1>
      </div>

      <!-- 左下角面板 -->
      <BorderBox1 class="container panel-4">
        <Panel4 />
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
  padding: 0.5rem;
  width: 100%;
  background: white;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1.2fr 1fr;
  grid-template-rows: 400px 400px; /* 保持左侧行高不变 */
  gap: 20px;
}

/* 右侧列容器 (嵌套网格) */
.right-column {
  grid-column: 3 / 4;
  grid-row: 1 / 3; /* 跨两行 */
  display: grid;
  grid-template-rows: 500px 300px; /* 自定义右侧高度 */
  gap: 20px; /* 保持间隔一致 */
}

/* 面板定位 */
.panel-1 {
  grid-column: 1 / 2;
  grid-row: 1 / 2;
}

.panel-4 {
  grid-column: 1 / 2;
  grid-row: 2 / 3;
}

.panel-3 {
  grid-column: 2 / 3;
  grid-row: 1 / 3;
}

/* 通用容器样式 */
.container {
  width: 100%;
  height: 100%;
  padding: 0.1rem;
  background: white;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.panel-3 {
  background: transparent;
  box-shadow: none;
  padding: 0;
  border-radius: 0;
  display: flex;
}

/* 调整datav边框组件 */
.dv-border-box-1 {
  width: 100%;
  height: 100%;
}
</style>