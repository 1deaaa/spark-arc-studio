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
import { collectFontWarmupText, ensureAppFontReadyForText } from './utils/fontWarmup'
import { ensureFullAppFontCss, hasAppFontWarmCacheHint, markAppFontWarmCacheHint } from './utils/fontAssets'
import { SUPPORTED_LOCALES } from './i18n/types'

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
  const hadWarmCacheHint = hasAppFontWarmCacheHint()
  const loginFontText = collectFontWarmupText(
    '2024-2026 1deaaa AIdeaStudio SparkArc',
    ...SUPPORTED_LOCALES.flatMap((locale) => {
      const messages = i18n.global.getLocaleMessage(locale) as Record<string, unknown>
      return [messages.locale, messages.login]
    }),
  )

  // 登录页允许四语即时切换，挂载前只加载这些少量字形；全量常用字仍在登录后后台预热。
  const fontCssReady = await ensureFullAppFontCss({ timeoutMs: hadWarmCacheHint ? 1500 : 3500 })
  const loginFontReady = fontCssReady
    ? await ensureAppFontReadyForText(loginFontText, {
        fontFamily: 'LXGW WenKai Screen',
        timeoutMs: hadWarmCacheHint ? 1500 : 3500,
        maxChars: 2400,
      })
    : false

  if (hadWarmCacheHint && !loginFontReady) {
    markAppFontWarmCacheHint(false)
  }

  app.mount('#app')
}

void bootstrap()
