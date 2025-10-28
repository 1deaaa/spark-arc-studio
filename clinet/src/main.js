import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router' // Import the router
import { useThemeStore } from './components/stores/themeStore'

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)

// Initialize theme store
const themeStore = useThemeStore()

app.use(router) // Use the router
app.mount('#app')
