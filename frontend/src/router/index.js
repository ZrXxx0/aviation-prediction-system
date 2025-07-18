import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import ForecastView from '@/views/ForecastView.vue'

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
        component: ForecastView
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router