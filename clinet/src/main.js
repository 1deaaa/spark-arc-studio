import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import './styles/base.css'
import './styles/layout.css'
import './styles/theme.css'
import './styles/components.css'
import './styles/studio.css'
import App from './App.vue'
import router from './router'
import { useThemeStore } from './components/stores/themeStore'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)

// Initialize theme store
const themeStore = useThemeStore()

app.use(router) // Use the router
app.mount('#app')
