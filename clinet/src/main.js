import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import './style.css'
import App from './App.vue'
import router from './router' // Import the router

const pinia = createPinia()
const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(ElementPlus, {
  // 配置所有弹出层（下拉框、日期选择器等）附加到 body
  // 这样可以避免在滚动容器内被裁剪
  appendTo: 'body'
})
app.use(router) // Use the router
app.mount('#app')
