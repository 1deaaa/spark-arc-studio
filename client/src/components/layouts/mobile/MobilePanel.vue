<template>
  <div class="mobile-panel">
    <!-- 顶部 Tab 切换 -->
    <div class="panel-tabs">
      <n-tabs 
        v-model:value="activeTab" 
        type="line" 
        justify-content="space-evenly"
        :animated="true"
        class="mobile-tabs"
      >
        <n-tab-pane 
          v-for="tab in tabs" 
          :key="tab.name" 
          :name="tab.name" 
          :tab="tab.label"
        />
      </n-tabs>
    </div>

    <!-- 内容区域 -->
    <div class="panel-content">
       <transition name="fade-slide" mode="out-in">
          <div :key="activeTab" class="tab-content-wrapper">
             <slot :name="activeTab"></slot>
          </div>
       </transition>
    </div>

    <!-- 浮动操作按钮插槽 -->
    <div v-if="$slots.fab" class="panel-fab">
       <slot name="fab"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, type PropType } from 'vue';
import { NTabs, NTabPane } from 'naive-ui';

type MobileTab = {
  name: string;
  label: string;
};

const props = defineProps({
  tabs: {
    type: Array as PropType<MobileTab[]>,
    required: true,
    // [{ name: 'muse', label: '灵感' }, { name: 'lore', label: '设定' }]
  },
  defaultTab: {
    type: String,
    default: ''
  }
});

const activeTab = ref(props.defaultTab || (props.tabs[0]?.name));

defineExpose({ activeTab });
</script>

<style scoped>
.mobile-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--spark-bg);
}

.panel-tabs {
  background: var(--spark-panel-bg);
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid var(--spark-border);
}

.mobile-tabs :deep(.n-tabs-nav) {
  padding: 0 16px; 
}

/* 调整 Tab 高度更适合手指点击 */
.mobile-tabs :deep(.n-tabs-tab) {
  padding: 12px 0; 
}

.panel-content {
  flex: 1;
  overflow-y: auto; /* 内容区域独立混动 */
  padding: 16px;
  position: relative;
  /* padding-bottom 由外部 Shell 控制或这里控制 */
}

.tab-content-wrapper {
  min-height: 100%;
}

.panel-fab {
  position: fixed; /* 相对于视口 */
  bottom: 80px; /* WorkflowNavigation 上方 */
  right: 20px;
  z-index: 100;
}

/* 简单的过渡动画 */
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateX(10px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}
</style>
