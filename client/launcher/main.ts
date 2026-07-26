import { createApp } from 'vue';
import { createPinia } from 'pinia';
import './lxgw-wenkai-launcher.css';
import '@/styles/theme.css';
import './launcher.css';
import LauncherApp from './LauncherApp.vue';
import { i18n } from './i18n';
import { setupExternalLinkHandling } from '@/utils/externalLinks';

const pinia = createPinia();
const app = createApp(LauncherApp);

app.use(pinia);
app.use(i18n);

setupExternalLinkHandling();
app.mount('#app');
