<template>
  <div class="mobile-flow-shell">
    <!-- 顶部固定导航栏 -->
    <header class="flow-header">
      <div class="header-left">
        <div class="app-logo">
          <svg class="logo-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path class="spark-draw" d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span>SparkArc</span>
        </div>
      </div>
      
      <div class="header-center">
        <span class="current-step-label">{{ currentStepLabel }}</span>
      </div>
      
      <div class="header-right">
        <n-button quaternary circle size="small" @click="openSettings">
          <template #icon><n-icon :component="SettingsOutline" /></template>
        </n-button>
      </div>
    </header>
    
    <!-- 滚动容器 -->
    <main class="flow-container" ref="containerRef">
      <!-- Step 1: 灵感 -->
      <FlowCard 
        :step="1" 
        title="点燃灵感" 
        subtitle="从一个梦境、歌词或瞬间感觉开始"
        :is-active="currentStep === 0"
      >
        <WorldMobile />
      </FlowCard>
      
      <!-- Step 2: 世界观 -->
      <FlowCard 
        :step="2" 
        title="构建世界" 
        subtitle="管理角色、地点、物品等设定"
        :is-active="currentStep === 1"
      >
        <LorebookMobile />
      </FlowCard>
      
      <!-- Step 3: 故事梗概 -->
      <FlowCard 
        :step="3" 
        title="故事梗概" 
        subtitle="从 Logline 到完整梗概和节拍表"
        :is-active="currentStep === 2"
      >
        <SynopsisMobile />
      </FlowCard>
      
      <!-- Step 4: 大纲编排 -->
      <FlowCard 
        :step="4" 
        title="大纲编排" 
        subtitle="规划章节结构与情节走向"
        :is-active="currentStep === 3"
      >
        <StructureMobile />
      </FlowCard>
      
      <!-- Step 5: 剧本创作 -->
      <FlowCard 
        :step="5" 
        title="剧本创作" 
        subtitle="基于场景构思与自动生成"
        :is-active="currentStep === 4"
      >
        <ProductionMobile />
      </FlowCard>

      <!-- Step 6: 故事蓝图 -->
      <FlowCard 
        :step="6" 
        title="故事蓝图" 
        subtitle="可视化场景连接与跳转逻辑"
        :is-active="currentStep === 5"
        :show-next-button="false"
      >
        <BlueprintMobile />
        <template #footer>
          <div class="completion-message">
            <n-icon :component="CheckmarkCircle" size="24" color="var(--spark-success)" />
            <span>完成所有流程，开始正式创作！</span>
          </div>
        </template>
      </FlowCard>
    </main>
    
    <!-- 步骤指示器 -->
    <StepIndicator :steps="flowSteps" :container-ref="containerRef" />
    
    <!-- AI 悬浮聊天（仅灵感/世界观步骤） -->
    <GlobalChatFloat v-if="showChatFloat" />
    
    <!-- 设置抽屉 (包含 AI配置、风格、引擎等辅助功能) -->
    <n-drawer v-model:show="settingsDrawerVisible" placement="bottom" height="90%">
      <n-drawer-content closable>
        <template #header>
          <div class="drawer-header">
            <span>设置与工具</span>
          </div>
        </template>
        
        <n-tabs type="line" animated>
          <n-tab-pane name="settings" tab="基础设置">
            <SettingsMobile />
          </n-tab-pane>
          <n-tab-pane name="style" tab="风格管理">
            <StyleMobile />
          </n-tab-pane>
          <n-tab-pane name="engine" tab="引擎绑定">
            <EngineMobile />
          </n-tab-pane>
          <n-tab-pane name="admin" tab="管理中心" v-if="isAdmin">
            <AdminMobile />
          </n-tab-pane>
        </n-tabs>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide, watch } from 'vue';
import { NButton, NIcon, NDrawer, NDrawerContent, NTabs, NTabPane } from 'naive-ui';
import { SettingsOutline, CheckmarkCircle } from '@vicons/ionicons5';

import FlowCard from './FlowCard.vue';
import StepIndicator from './StepIndicator.vue';
import GlobalChatFloat from '../../share/GlobalChatFloat.vue';

// 核心工作流视图
import WorldMobile from '../../../views/World/WorldIndex.vue';
import LorebookMobile from '../../../views/Lorebook/LorebookIndex.vue';
import SynopsisMobile from '../../../views/Synopsis/SynopsisIndex.vue';
import StructureMobile from '../../../views/Structure/StructureIndex.vue';
import BlueprintMobile from '../../../views/Blueprint/BlueprintIndex.vue';
import ProductionMobile from '../../../views/Production/ProductionIndex.vue';

// 辅助功能（放入设置抽屉）
import SettingsMobile from '../../../views/Settings/SettingsIndex.vue';
import StyleMobile from '../../../views/Style/StyleIndex.vue';
import EngineMobile from '../../../views/Engine/EngineIndex.vue';
import AdminMobile from '../../../views/Admin/AdminIndex.vue';

import { useProjectStore } from '../../stores/projectStore';
import { useViewStore } from '../../stores/viewStore';
import { useAdminLogic } from '../../../composables/useAdminLogic';
import { useFullscreen } from '../../../composables/useFullscreen';

const projectStore = useProjectStore();
const viewStore = useViewStore();
const { isAdmin } = useAdminLogic();
const { preferred, requestFullscreen, setPreferred } = useFullscreen();
const containerRef = ref(null);
const currentStep = ref(0);
const settingsDrawerVisible = ref(false);

// 提供 projectId 给子组件
provide('projectId', computed(() => projectStore.currentProject));

const flowSteps = [
  { id: 'muse', label: '灵感' },
  { id: 'lorebook', label: '世界' },
  { id: 'synopsis', label: '梗概' },
  { id: 'structure', label: '大纲' },
  { id: 'production', label: '创作' },
  { id: 'blueprint', label: '蓝图' }
];

const currentStepLabel = computed(() => {
  return flowSteps[currentStep.value]?.label || 'SparkArc';
});

const showChatFloat = ref(true);

const stepViewMap = ['world', 'lorebook', 'synopsis', 'structure', 'production', 'blueprint'];
watch(currentStep, (idx) => {
  const view = stepViewMap[idx] || 'world';
  if (viewStore.currentView !== view) {
    viewStore.setView(view);
  }
}, { immediate: true });

function openSettings() {
  settingsDrawerVisible.value = true;
}

// IntersectionObserver 检测当前可见卡片
let observer = null;

function setupObserver() {
  const options = {
    root: containerRef.value,
    rootMargin: '-40% 0px -40% 0px',
    threshold: 0
  };
  
  observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        const match = id.match(/step-(\d+)/);
        if (match) {
          currentStep.value = parseInt(match[1]) - 1;
        }
      }
    });
  }, options);
  
  // 观察所有步骤卡片
  flowSteps.forEach((_, index) => {
    const element = document.getElementById(`step-${index + 1}`);
    if (element) {
      observer.observe(element);
    }
  });
}

onMounted(() => {
  setTimeout(setupObserver, 200);

  try {
    const stored = localStorage.getItem('spark_fullscreen');
    if (stored === null) {
      setPreferred(true);
    }
  } catch {}

  if (preferred.value && !document.fullscreenElement) {
    const tryOnce = () => {
      requestFullscreen();
    };
    window.addEventListener('touchstart', tryOnce, { once: true, passive: true });
    window.addEventListener('click', tryOnce, { once: true });
  }
});

onUnmounted(() => {
  if (observer) {
    observer.disconnect();
  }
});
</script>

<style scoped>
.mobile-flow-shell {
  height: 100vh;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
  overflow: hidden;
}

/* 顶部导航栏 */
.flow-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  z-index: 200;
  
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  padding-top: env(safe-area-inset-top);
  
  background: rgba(var(--spark-panel-bg-rgb), 0.85);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(var(--spark-border-rgb), 0.5);
}

.header-left, .header-right {
  width: 48px;
  display: flex;
  justify-content: center;
}

.header-left {
  justify-content: flex-start;
}

.header-right {
  justify-content: flex-end;
}

.app-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  font-size: 16px;
  color: var(--spark-text-bright);
}

.logo-icon {
  color: var(--spark-primary);
}

.current-step-label {
  font-weight: 600;
  font-size: 15px;
  color: var(--spark-text);
}

/* 滚动容器 */
.flow-container {
  flex: 1;
  /* 强制垂直布局 */
  display: flex;
  flex-direction: column;
  
  /* 确保宽度正确 */
  width: 100%;
  max-width: 100vw;
  
  overflow-y: auto;
  overflow-x: hidden;
  
  /* 垂直滚动吸附 */
  scroll-snap-type: y mandatory;
  -webkit-overflow-scrolling: touch;
  scroll-behavior: smooth;
  
  /* 防止橡皮筋效果影响整体 */
  overscroll-behavior-y: contain;
}

/* 完成消息 */
.completion-message {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: rgba(var(--spark-success-rgb), 0.1);
  border: 1px solid rgba(var(--spark-success-rgb), 0.3);
  border-radius: 12px;
  color: var(--spark-success);
  font-weight: 500;
}

/* 抽屉样式 */
.drawer-header {
  font-size: 16px;
  font-weight: 600;
}

:deep(.n-drawer) {
  border-radius: 16px 16px 0 0;
}

:deep(.n-drawer-header) {
  padding: 16px !important;
  border-bottom: 1px solid var(--spark-border);
}

:deep(.n-tabs-nav) {
  padding: 0 16px;
}

:deep(.n-tab-pane) {
  padding: 16px 0;
  padding-bottom: 100px;
}
</style>
