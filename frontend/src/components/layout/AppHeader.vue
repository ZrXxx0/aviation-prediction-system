<template>
  <el-header height="64px" class="app-header">
    <div class="logo">航空市场需求分析工具</div>
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
      <el-menu-item v-if="canViewForecast" index="/forecast">预测模块</el-menu-item>
      <el-menu-item v-if="canViewManagement" index="/management">数据管理</el-menu-item>
    </el-menu>

    <!-- 系统管理齿轮图标（靠右）- 只有超级管理员可见 -->
    <el-button v-if="canViewAdministration" class="sys-btn" type="text" @click="goSystem" title="系统管理">
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
import { getUserInfo, clearAuth, canViewAdministration as checkAdmin, canViewForecast as checkForecast, canViewManagement as checkManagement } from '@/utils/auth'

const userName = ref('游客')
const route = useRoute()
const router = useRouter()

const currentRoute = computed(() => route.path)

// 权限检查
const canViewAdministration = computed(() => checkAdmin())
const canViewForecast = computed(() => checkForecast())
const canViewManagement = computed(() => checkManagement())

// 加载用户信息
function loadUserInfo() {
  const userInfo = getUserInfo()
  if (userInfo) {
    userName.value = userInfo.username || userInfo.email || '用户'
  } else {
    userName.value = '游客'
  }
}

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
  loadUserInfo()
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function handleLogout() {
  try {
    // 调用后端登出接口（可选）
    const token = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token')
    if (token) {
      const apiConfig = await import('@/config/api.js')
      const url = apiConfig.default.getUrl('/auth/logout/')
      await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }).catch(() => {}) // 忽略登出接口错误
    }
  } catch (e) {
    console.error('登出请求失败:', e)
  } finally {
    // 清除本地认证信息
    clearAuth()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
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

/* 隐藏 Element Plus 菜单的"更多"下拉菜单（当菜单项较少时自动显示的） */
.nav-menu :deep(.el-sub-menu) {
  display: none !important;
}

.nav-menu :deep(.el-menu--popup) {
  display: none !important;
}

/* 确保菜单项正确显示 */
.nav-menu :deep(.el-menu-item) {
  display: inline-flex !important;
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