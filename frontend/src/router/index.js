import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import ForecastView from '@/views/ForecastView.vue'
import DataManageView from '@/views/DataManageView.vue'

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
    ,
    {
        path : '/datamanage',
        name : 'DataManage',
        component : DataManageView
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router