import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '@/views/DashboardView.vue'
import ForecastView from '@/views/ForecastView.vue'
import ManagementView from '@/views/ManagementView.vue'
import AdministrationView from '@/views/AdministrationView.vue'
import LoginView from '@/views/LoginView.vue'

const routes = [
    {
        path: '/',
        redirect: '/login'
    },
    {
        path: '/login',
        name: 'Login',
        component: LoginView,
        meta: { hideHeader: true, hideFooter: true }
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
    },
    {
        path: '/management',
        name: 'management',
        component: ManagementView
    }
    ,
    {
        path: '/administration',
        name: 'administration',
        component: AdministrationView
    },
    { 
        path: '/:pathMatch(.*)*', 
        redirect: '/' }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router