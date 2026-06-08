import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/theme.css'
import './styles/components.css'
import './styles/mobile.css'
import './styles/studio.css'
import 'cn-fontsource-lxgw-wen-kai-screen/font.css'
import App from './App.vue'
import router from './router'
import { useThemeStore } from './components/stores/themeStore'
import { useLocaleStore } from './components/stores/localeStore'
import { i18n } from './i18n'
import { setupTauriOfflineFallback } from './utils/tauriOfflineFallback'
import { setupExternalLinkHandling } from './utils/externalLinks'
import { setupMobileTooltipGuard } from './utils/mobileTooltipGuard'
import './composables/useMobile' // 早期触发 safe-area 兜底检测
import './composables/usePlatform' // 早期同步平台壳类名，供响应式样式复用
import { warmupAppFontInBackground, warmupCommonChineseCharacters } from './utils/fontWarmup'

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
setupMobileTooltipGuard()
warmupAppFontInBackground('', { timeoutMs: 1800, maxChars: 180 })

// 页面完全加载 (onload) 且空闲后，在后台静默异步预加载 3500 常用中文字型分包 (可强缓存复用)
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    warmupCommonChineseCharacters();
  });
}
app.mount('#app')
