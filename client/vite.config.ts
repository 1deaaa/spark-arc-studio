import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

function manualChunks(id: string): string | undefined {
  if (!id.includes('node_modules')) {
    return undefined;
  }
  if (id.includes('node_modules/naive-ui')) return 'ui-naive';
  if (id.includes('node_modules/@css-render')) return 'ui-naive';
  if (id.includes('node_modules/@lucide/vue')) return 'icons-lucide';
  if (id.includes('node_modules/highlight.js')) return 'highlight-core';
  if (id.includes('node_modules/gsap')) return 'motion-gsap';
  if (id.includes('node_modules/three')) return 'three-vendor';
  if (id.includes('node_modules/@fingerprintjs')) return 'fingerprint';
  if (id.includes('node_modules/@tauri-apps')) return 'tauri-api';
  if (id.includes('node_modules/cn-fontsource-lxgw-wen-kai-screen')) return 'font-lxgw-wenkai';
  return undefined;
}

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 12346,
    allowedHosts: true,
    proxy: {
      '/api': {
        target: 'http://localhost:6688',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        manualChunks,
      },
    },
  },
});
