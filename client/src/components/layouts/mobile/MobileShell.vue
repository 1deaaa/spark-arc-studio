<template>
  <div class="mobile-shell">
    <!-- 顶部导航栏 -->
    <header class="mobile-header">
      <div class="header-left">
        <slot name="header-left">
           <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="app-logo-link"><AppBrand class="app-logo" :size="24" :show-text="false" /></a>
        </slot>
      </div>
      
      <div class="header-center">
        <span class="view-title">{{ currentTitle }}</span>
      </div>
      
      <div class="header-right">
        <slot name="header-right">
           <!-- 预留：AI 聊天入口或设置入口 -->
           <n-button quaternary circle size="small" @click="$emit('open-settings')">
             <template #icon><n-icon :component="Settings" /></template>
           </n-button>
        </slot>
      </div>
    </header>

    <!-- 主内容区域 (支持滚动) -->
    <main class="mobile-content">
      <slot></slot>
    </main>

    <!-- 底部导航栏 -->
    <WorkflowNavigation />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NButton, NIcon } from 'naive-ui';
import { Settings } from 'lucide-vue-next';
import AppBrand from '../../share/AppBrand.vue';
import { SPARKARC_GITHUB_URL } from '@/config';
import WorkflowNavigation from './WorkflowNavigation.vue';
import { useViewStore } from '../../stores/viewStore';

const viewStore = useViewStore();

const viewTitles = {
  'world': '灵感与世界',
  'synopsis': '故事梗概',
  'structure': '大纲编排',
  'style': '风格管理',
  'blueprint': '故事蓝图',
  'production': '剧本创作',
  'settings': '系统设置',
  'dashboard': '管理中心'
};

const currentTitle = computed(() => {
  return viewTitles[viewStore.currentView] || 'SparkArc';
});

defineEmits(['open-settings']);
</script>

<style scoped>
.mobile-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh; /* 适配动态视口高度 */
  background-color: var(--spark-bg);
  overflow: hidden;
}

.mobile-header {
  height: calc(var(--mobile-header-height, 48px) + var(--sat, 0px));
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  padding-top: var(--sat, 0px);
  background-color: var(--spark-panel-bg);
  border-bottom: 1px solid var(--spark-border);
  z-index: 100;
  flex-shrink: 0;
}

.header-left, .header-right {
  width: 40px; /* 保持平衡 */
  display: flex;
  justify-content: center;
}

.header-left {
  justify-content: flex-start;
}

.header-right {
  justify-content: flex-end;
}

.app-logo-link {
  display: inline-flex;
  align-items: center;
  text-decoration: none;
  color: inherit;
  line-height: 0;
}
.app-logo {
  display: inline-flex;
  align-items: center;
  line-height: 0;
}

.view-title {
  font-weight: 600;
  font-size: var(--spark-fs-lg);
  color: var(--spark-text);
}

.mobile-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding-bottom: calc(var(--mobile-bottom-nav-height, 60px) + var(--sab, 0px)); /* 为底部导航栏留出空间 */
  -webkit-overflow-scrolling: touch; /* iOS 惯性滚动 */
}
</style>
