import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import DashboardView from '@/views/DashboardView.vue'
import DataShowView from '@/views/DataShowView.vue'
import AircraftView from '@/views/AircraftView.vue'
import ForecastRunView from '@/views/ForecastRunView.vue'
import ModelTrainView from '@/views/ModelTrainView.vue'
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
        meta: { requiresAuth: false }
    },
    // Forecast 模块拆成独立页面
    {
        path: '/forecast',
        name: 'Forecast',
        redirect: '/forecast/show',
        meta: { requiresAuth: true, requiresPermission: 'view_forecast' }
    },
    {
        path: '/forecast/aircraft',
        name: 'Aircraft',
        component: AircraftView,
        meta: { requiresAuth: true, requiresPermission: 'view_forecast' }
    },
    {
        path: '/forecast/show',
        name: 'ForecastShow',
        component: DataShowView,
        meta: { requiresAuth: true, requiresPermission: 'view_forecast' }
    },
    {
        path: '/forecast/run',
        name: 'ForecastRun',
        component: ForecastRunView,
        meta: { requiresAuth: true, requiresPermission: 'view_forecast' }
    },
    {
        path: '/forecast/train',
        name: 'ForecastTrain',
        component: ModelTrainView,
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
        redirect: '/' 
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

// 路由守卫（保持和你现有逻辑一致）
router.beforeEach((to, from, next) => {
    const token = getToken()

    const normalize = (p) => (p !== '/' && p.endsWith('/') ? p.slice(0, -1) : p)
    const path = normalize(to.path)

    if (path === '/login' && token) {
        next('/dashboard')
        return
    }

    if (to.meta.requiresAuth) {
        if (!token) {
            ElMessage.warning('请先登录')
            next('/login')
            return
        }

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