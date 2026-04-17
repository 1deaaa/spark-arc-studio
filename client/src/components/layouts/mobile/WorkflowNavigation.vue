<template>
  <div class="mobile-bottom-nav">
    <div 
      v-for="tab in tabs" 
      :key="tab.id"
      class="nav-item"
      :class="{ active: currentView === tab.view || (tab.children && tab.children.includes(currentView)) }"
      @click="handleTabClick(tab)"
    >
      <div class="icon-container">
        <n-icon size="24" :component="tab.icon" />
        <div v-if="tab.badge" class="badge"></div>
      </div>
      <span class="label">{{ tab.label }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue';
import { NIcon } from 'naive-ui';
import {
  BulbOutline,          // 灵感 - 与桌面端统一
  ListOutline,          // 大纲结构 - 与桌面端统一
  CreateOutline         // 剧本创作 - 与桌面端统一
} from '@vicons/ionicons5';
import { useViewStore } from '../../stores/viewStore';

const viewStore = useViewStore();
const currentView = computed(() => viewStore.currentView);

// 工作流阶段定义 - 与桌面端使用完全相同的图标
const tabs = [
  {
    id: 'ideation',
    label: '构思',
    icon: markRaw(BulbOutline),  // 灵感 - 与桌面端 world 页面统一
    view: 'world',
    children: ['world', 'synopsis'], // 包含灵感、世界观、梗概
    badge: false,
  },
  {
    id: 'planning',
    label: '策划',
    icon: markRaw(ListOutline),  // 大纲结构 - 与桌面端 structure 页面统一
    view: 'structure',
    children: ['structure', 'style', 'blueprint'], // 包含大纲、风格、蓝图
    badge: false,
  },
  {
    id: 'production',
    label: '创作',
    icon: markRaw(CreateOutline),  // 剧本创作 - 与桌面端 production 页面统一
    view: 'production',
    children: ['production', 'player'], // 包含剧本、预览
    badge: false,
  }
];

function handleTabClick(tab) {
  // 如果点击当前 tab，且有多个子视图，可以在这里处理子视图循环切换逻辑
  // 目前简单处理：点击即跳转到该阶段的主视图
  viewStore.setView(tab.view);
}
</script>

<style scoped>
.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 60px; /* 安全高度，适配 iOS home indicator 需额外 padding */
  padding-bottom: var(--sab, env(safe-area-inset-bottom, 0px));
  background: var(--spark-panel-bg);
  border-top: 1px solid var(--spark-border);
  display: flex;
  justify-content: space-around;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(20px);
}

.nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  color: var(--n-text-color-3);
  transition: all 0.2s;
  padding: 8px 16px;
  border-radius: 8px;
}

.nav-item.active {
  color: var(--n-primary-color);
}

.icon-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.label {
  font-size: var(--spark-fs-3xs);
  font-weight: 500;
}

.badge {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 8px;
  height: 8px;
  background-color: var(--n-error-color);
  border-radius: 50%;
}
</style>
