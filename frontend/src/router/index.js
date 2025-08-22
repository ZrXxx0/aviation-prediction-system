import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import ForecastView from '@/views/ForecastView.vue'
import ManagementView from '@/views/ManagementView.vue'
import ForecastManager from '@/views/ForecastManager.vue'

const routes = [
    {
        path: '/',
        redirect: '/dashboard'
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: DashboardView
    },
    {
        path: '/forecast',
        name: 'Forecast',
        component: ForecastManager
    },
    {
        path: '/management',
        name: 'management',
        component: ManagementView
    }
    
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router