import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/theme.css'
import './styles/components.css'
import './styles/studio.css'
import 'katex/dist/katex.min.css'
// 字体已改为 CDN 加载 LXGW WenKai Lite，见 index.html <link>
import App from './App.vue'
import router from './router'
import { useThemeStore } from './components/stores/themeStore'
import { useLocaleStore } from './components/stores/localeStore'
import { i18n } from './i18n'
import { setupTauriOfflineFallback } from './utils/tauriOfflineFallback'
import { setupExternalLinkHandling } from './utils/externalLinks'
import './composables/useMobile' // 早期触发 safe-area 兜底检测
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
setupExternalLinkHandling()
setupTauriOfflineFallback()
warmupAppFontInBackground('')
app.mount('#app')
