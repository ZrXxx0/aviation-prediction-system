import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

import * as echarts from 'echarts'
import DataVVue3 from 'datav-vue3'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'

const app = createApp(App)

// 全局挂载 echarts
app.config.globalProperties.$echarts = echarts

// 全局注册 dataV
app.use(DataVVue3)
app.use(ElementPlus, {
  locale: zhCn,
})

app.use(router).mount('#app')