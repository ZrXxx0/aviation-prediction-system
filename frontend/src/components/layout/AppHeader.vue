<template>
  <header class="app-header">
    <div class="logo">航空市场需求分析预测</div>

    <nav class="nav-links">
      <router-link
          to="/dashboard"
          :class="{ active: currentRoute === '/dashboard' }"
      >
        数据看板
      </router-link>
      <router-link
          to="/forecast"
          :class="{ active: currentRoute === '/forecast' }"
      >
        预测分析
      </router-link>
    </nav>

    <div class="user-section">
      <span>{{ userName }}</span>
      <button class="logout-btn">退出</button>
    </div>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'

const userName = ref('管理员')
const route = useRoute()

// 计算当前路由路径
const currentRoute = computed(() => route.path)
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: #2c3e50;
  color: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  width: 100%;
}

.logo {
  font-size: 1.5rem;
  font-weight: bold;
}

.nav-links {
  display: flex;
  gap: 2rem;
}

.nav-links a {
  color: #ecf0f1;
  text-decoration: none;
  padding: 0.5rem;
  border-radius: 4px;
  transition: background 0.3s;
}

.nav-links a.active {
  background-color: #3498db;
}

.nav-links a:hover:not(.active) {
  background-color: #34495e;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.logout-btn {
  background: #e74c3c;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.3s;
}

.logout-btn:hover {
  background: #c0392b;
}
</style>