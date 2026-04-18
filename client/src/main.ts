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
app.mount('#app')
