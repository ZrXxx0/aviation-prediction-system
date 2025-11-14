<template>
  <el-header height="64px" class="app-header">
    <div class="logo">航空市场需求分析预测</div>
    <el-menu
      mode="horizontal"
      :default-active="currentRoute"
      background-color="#2c3e50"
      text-color="#ecf0f1"
      active-text-color="#3498db"
      class="nav-menu"
      router
    >
      <el-menu-item index="/dashboard">数据看板</el-menu-item>
      <el-menu-item index="/forecast">预测模块</el-menu-item>
      <el-menu-item index="/management">数据管理</el-menu-item>
      <!-- <el-menu-item index="/administration">系统管理</el-menu-item> -->
    </el-menu>

    <!-- 系统管理齿轮图标（靠右） -->
    <el-button class="sys-btn" type="text" @click="goSystem" title="系统管理">
      <el-icon><setting /></el-icon>
    </el-button>

    <el-dropdown class="user-section" trigger="click">
      <span class="el-dropdown-link">
        <span style="margin-right: 25px; font-size: 0.8rem; color: #ecf0f1; letter-spacing: 1px;">
          {{ currentTime }}
        </span>
        <el-avatar size="small" style="margin-right: 8px; background: #3498db;">{{ userName[0] }}</el-avatar>
        {{ userName }}
        <el-icon style="margin-left: 4px;"><arrow-down /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item @click="handleLogout">退出</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </el-header>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown, Setting } from '@element-plus/icons-vue'

const userName = ref('管理员')
const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => route.path)

// 实时时间逻辑
const currentTime = ref('')
let timer = null
function updateTime() {
  const now = new Date()
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  const ss = String(now.getSeconds()).padStart(2, '0')
  currentTime.value = `${yyyy}-${mm}-${dd} ${hh}:${min}:${ss}`
}
onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

function handleLogout() {
  ElMessage.success('已退出登录')
  // 这里可以添加实际的登出逻辑，如清除 token、跳转登录页等
  // router.push('/login')
}

function goSystem() {
  // 跳转到系统管理页面（请确保路由已配置）
  router.push('/administration')
}
</script>

<style scoped>
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 2rem;
  background-color: #2c3e50;
  color: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  width: 100%;
  height: 64px;
}
.logo {
  font-size: 1.5rem;
  font-weight: bold;
  color: #fff;
}
.nav-menu {
  flex: 1;
  margin-left: 3rem;
  background: transparent;
  border-bottom: none;
}

/* 齿轮按钮样式 */
.sys-btn {
  color: #ecf0f1;
  margin-right: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.sys-btn:hover {
  color: #ffffff;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
}

.user-section {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
</style>