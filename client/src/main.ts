import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/theme.css'
import './styles/components.css'
import './styles/studio.css'
import 'katex/dist/katex.min.css'
import 'cn-fontsource-lxgw-wen-kai-screen/font.css'
import App from './App.vue'
import router from './router'
import { useThemeStore } from './components/stores/themeStore'
import { useLocaleStore } from './components/stores/localeStore'
import { i18n } from './i18n'
import { setupTauriOfflineFallback } from './utils/tauriOfflineFallback'
import { warmupAppFontInBackground } from './utils/fontWarmup'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(i18n)

// Initialize theme store
const themeStore = useThemeStore()
const localeStore = useLocaleStore()
void themeStore
void localeStore

app.use(router) // Use the router
setupTauriOfflineFallback()
warmupAppFontInBackground('打开关闭返回设置列表章节场景继续跳过播放小说阅读目录选项重试')
app.mount('#app')
