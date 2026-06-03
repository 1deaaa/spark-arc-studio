import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

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
    rollupOptions: {
      output: {
        manualChunks: {
          'naive-ui': ['naive-ui'],
          lucide: ['@lucide/vue'],
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
        },
      },
    },
  },
});