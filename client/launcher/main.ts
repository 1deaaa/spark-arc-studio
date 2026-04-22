import { createApp } from 'vue';
import { createPinia } from 'pinia';
import '@/style.css';
import '@/styles/base.css';
import '@/styles/layout.css';
import '@/styles/theme.css';
import '@/styles/components.css';
import '@/styles/studio.css';
import 'katex/dist/katex.min.css';
import 'cn-fontsource-lxgw-wen-kai-screen/font.css';
import LauncherApp from './LauncherApp.vue';
import { i18n } from './i18n';
import { useThemeStore } from '@/components/stores/themeStore';

const pinia = createPinia();
const app = createApp(LauncherApp);

app.use(pinia);
app.use(i18n);

const themeStore = useThemeStore();
void themeStore;

app.mount('#app');
