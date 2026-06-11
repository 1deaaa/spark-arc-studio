import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/theme.css'
import './styles/components.css'
import './styles/mobile.css'
import './styles/studio.css'
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
import { warmupAppFontInBackground } from './utils/fontWarmup'
import { ensureFullAppFontCss, hasAppFontWarmCacheHint, markAppFontWarmCacheHint } from './utils/fontAssets'

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

async function bootstrap() {
  // 仅在上次已完成后台预热后，才在挂载前抢先接回字体 CSS。
  // 这样首次登录不阻塞，后续刷新则能直接吃到本地缓存。
  if (hasAppFontWarmCacheHint()) {
    const loaded = await ensureFullAppFontCss({ timeoutMs: 600 })
    if (!loaded) {
      markAppFontWarmCacheHint(false)
    }
  }

  warmupAppFontInBackground('', { timeoutMs: 1800, maxChars: 180 })
  app.mount('#app')
}

void bootstrap()
