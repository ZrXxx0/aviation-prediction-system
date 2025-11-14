import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import DashboardView from '@/views/DashboardView.vue'
import ForecastView from '@/views/ForecastView.vue'
import ManagementView from '@/views/ManagementView.vue'
import AdministrationView from '@/views/AdministrationView.vue'
import LoginView from '@/views/LoginView.vue'
import { getToken, canViewForecast, canViewManagement, canViewAdministration } from '@/utils/auth'

const routes = [
    {
        path: '/',
        redirect: '/login'
    },
    {
        path: '/login',
        name: 'Login',
        component: LoginView,
        meta: { hideHeader: true, hideFooter: true, requiresAuth: false }
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: DashboardView,
        meta: { requiresAuth: false } // 数据看板所有用户都可以访问
    },
    {
        path: '/forecast',
        name: 'Forecast',
        component: ForecastView,
        meta: { requiresAuth: true, requiresPermission: 'view_forecast' }
    },
    {
        path: '/management',
        name: 'management',
        component: ManagementView,
        meta: { requiresAuth: true, requiresPermission: 'view_management' }
    },
    {
        path: '/administration',
        name: 'administration',
        component: AdministrationView,
        meta: { requiresAuth: true, requiresPermission: 'view_administration' }
    },
    { 
        path: '/:pathMatch(.*)*', 
        redirect: '/' }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
    const token = getToken()
    
    // 如果访问登录页且已登录，重定向到看板
    if (to.path === '/login' && token) {
        next('/dashboard')
        return
    }
    
    // 检查是否需要认证
    if (to.meta.requiresAuth) {
        if (!token) {
            ElMessage.warning('请先登录')
            next('/login')
            return
        }
        
        // 检查权限
        const permission = to.meta.requiresPermission
        if (permission === 'view_forecast' && !canViewForecast()) {
            ElMessage.error('您没有权限访问此页面')
            next('/dashboard')
            return
        }
        if (permission === 'view_management' && !canViewManagement()) {
            ElMessage.error('您没有权限访问此页面')
            next('/dashboard')
            return
        }
        if (permission === 'view_administration' && !canViewAdministration()) {
            ElMessage.error('您没有权限访问此页面')
            next('/dashboard')
            return
        }
    }
    
    next()
})

export default router