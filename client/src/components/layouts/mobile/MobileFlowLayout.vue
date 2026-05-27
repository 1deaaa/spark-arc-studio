<template>
  <div class="mobile-flow-shell">
    <!-- 顶部固定导航栏 -->
    <header class="flow-header">
      <div class="header-left">
        <a :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener" class="app-logo-link"><AppBrand class="app-logo" :size="28" :show-text="false" /></a>
      </div>
      
      <div class="header-center">
        <span class="current-step-label">{{ currentStepLabel }}</span>
      </div>
      
      <div class="header-right">
        <n-dropdown trigger="click" :options="projectSwitchOptions" @select="handleProjectSwitch">
          <span class="tooltip-dropdown-trigger">
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button quaternary circle size="small">
                  <template #icon><n-icon :component="FolderOpen" /></template>
                </n-button>
              </template>
              {{ t('mobileFlow.header.switchProject') }}
            </n-tooltip>
          </span>
        </n-dropdown>
        <StoryTagsPanel />
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button quaternary circle size="small" @click="openPublishDrawer">
              <template #icon><n-icon :component="Share2" /></template>
            </n-button>
          </template>
          {{ t('components.headerToolbar.publishTitle') }}
        </n-tooltip>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button quaternary circle size="small" @click="quickPreview" :loading="previewing">
              <template #icon><n-icon :component="Play" /></template>
            </n-button>
          </template>
          {{ t('components.headerToolbar.quickPreviewTitle') }}
        </n-tooltip>
        <n-button quaternary circle size="small" @click="openSettings">
          <template #icon><n-icon :component="Settings" /></template>
        </n-button>
      </div>
    </header>
    
    <!-- 滚动容器 -->
    <main class="flow-container" ref="containerRef">
      <!-- Step 1: 灵感 -->
      <FlowCard 
        :step="1" 
        :title="t('mobileFlow.cards.inspireTitle')" 
        :subtitle="t('mobileFlow.cards.inspireSubtitle')"
        :is-active="currentStep === 0"
      >
        <WorldMobile />
      </FlowCard>
      
      <!-- Step 2: 世界观 -->
      <FlowCard 
        :step="2" 
        :title="t('mobileFlow.cards.worldTitle')" 
        :subtitle="t('mobileFlow.cards.worldSubtitle')"
        :is-active="currentStep === 1"
      >
        <LorebookMobile />
      </FlowCard>
      
      <!-- Step 3: 故事梗概 -->
      <FlowCard 
        :step="3" 
        :title="t('mobileFlow.cards.synopsisTitle')" 
        :subtitle="t('mobileFlow.cards.synopsisSubtitle')"
        :is-active="currentStep === 2"
      >
        <SynopsisMobile />
      </FlowCard>
      
      <!-- Step 4: 大纲编排 -->
      <FlowCard 
        :step="4" 
        :title="t('mobileFlow.cards.structureTitle')" 
        :subtitle="t('mobileFlow.cards.structureSubtitle')"
        :is-active="currentStep === 3"
      >
        <StructureMobile />
      </FlowCard>
      
      <!-- Step 5: 剧本创作 -->
      <FlowCard 
        :step="5" 
        :title="t('mobileFlow.cards.productionTitle')" 
        :subtitle="t('mobileFlow.cards.productionSubtitle')"
        :is-active="currentStep === 4"
      >
        <ProductionMobile />
      </FlowCard>

      <!-- Step 6: 故事蓝图 -->
      <FlowCard 
        :step="6" 
        :title="t('mobileFlow.cards.blueprintTitle')" 
        :subtitle="t('mobileFlow.cards.blueprintSubtitleNew')"
        :is-active="currentStep === 5"
        :show-next-button="false"
      >
        <BlueprintIndex />
        <template #footer>
          <div class="completion-message">
            <n-icon :component="CircleCheckBig" size="24" color="var(--spark-success)" />
            <span>{{ t('mobileFlow.cards.completion') }}</span>
          </div>
        </template>
      </FlowCard>
    </main>
    
    <!-- 步骤指示器 -->
    <StepIndicator :steps="flowSteps" :container-ref="containerRef" />
    
    <!-- AI 悬浮聊天（仅灵感/世界观步骤） -->
    <GlobalChatFloat v-if="showChatFloat" />
    
    <!-- 发布管理抽屉 -->
    <n-drawer v-model:show="publishDrawerVisible" placement="bottom" height="90%">
      <n-drawer-content closable>
        <template #header>
          <div class="drawer-header">
            <span>{{ t('components.versionManager.title') }}</span>
          </div>
        </template>
        <VersionManager :projectId="projectStore.currentProject || undefined" :content-format="workspaceMode" />
      </n-drawer-content>
    </n-drawer>

    <!-- 项目导入文件选择 -->
    <input type="file" ref="importSparkInput" @change="onSparkFileChange" accept=".spark" style="display:none;">

    <!-- 设置抽屉 (包含 AI配置、风格、引擎等辅助功能) -->
    <n-drawer v-model:show="settingsDrawerVisible" placement="bottom" height="90%">
      <n-drawer-content closable>
        <template #header>
          <div class="drawer-header">
            <span>{{ t('mobileFlow.drawer.title') }}</span>
          </div>
        </template>
        
        <n-tabs type="line" animated>
          <n-tab-pane name="settings" :tab="t('mobileFlow.drawer.tabs.settings')">
            <SettingsMobile />
          </n-tab-pane>
          <n-tab-pane name="style" :tab="t('mobileFlow.drawer.tabs.style')">
            <StyleMobile />
          </n-tab-pane>
          <n-tab-pane name="engine" :tab="t('mobileFlow.drawer.tabs.engine')">
            <EngineMobile />
          </n-tab-pane>
          <n-tab-pane name="dashboard" :tab="t('mobileFlow.drawer.tabs.dashboard')">
            <DashboardMobile />
          </n-tab-pane>
        </n-tabs>
      </n-drawer-content>
    </n-drawer>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, provide, watch, h, nextTick } from 'vue';
import { NButton, NIcon, NDrawer, NDrawerContent, NTabs, NTabPane, NDropdown, NModal, NCard, NTooltip, type DropdownOption, useDialog } from 'naive-ui';
import { Archive, CircleCheckBig, CirclePlus, FolderOpen, PaintBucket, Play, Settings, Share2, SquarePen, Trash } from 'lucide-vue-next';
import { useI18n } from 'vue-i18n';

import FlowCard from './FlowCard.vue';
import StepIndicator from './StepIndicator.vue';
import GlobalChatFloat from '../../share/GlobalChatFloat.vue';

// 核心工作流视图
import WorldMobile from '../../../views/World/WorldIndex.vue';
import LorebookMobile from '../../../views/Lorebook/LorebookIndex.vue';
import SynopsisMobile from '../../../views/Synopsis/SynopsisIndex.vue';
import StructureMobile from '../../../views/Structure/StructureIndex.vue';
import BlueprintIndex from '../../../views/Blueprint/BlueprintIndex.vue';
import ProductionMobile from '../../../views/Production/ProductionIndex.vue';

// 辅助功能（放入设置抽屉）
import SettingsMobile from '../../../views/Settings/SettingsIndex.vue';
import StyleMobile from '../../../views/Style/StyleIndex.vue';
import EngineMobile from '../../../views/Engine/EngineIndex.vue';
import DashboardMobile from '../../../views/Dashboard/DashboardIndex.vue';

import { useProjectStore } from '../../stores/projectStore';
import { useViewStore, type AppViewKey } from '../../stores/viewStore';
import { useSceneStore } from '../../stores/sceneStore';
import { useFileStore } from '../../stores/fileStore';
import { useFullscreen } from '../../../composables/useFullscreen';
import { useOnboarding } from '../../../onboarding';
import AppBrand from '../../share/AppBrand.vue';
import { SPARKARC_GITHUB_URL } from '@/config';
import VersionManager from '../../dlg-editor/VersionManager.vue';
import bus from '../../../eventBus';
import { saveStory, fetchWithAuth } from '../../../services/api';
import { exportProjectAsSpark, importProjectFromSpark } from '../../../services/projectService';
import StoryTagsPanel from '../../share/StoryTagsPanel.vue';

const projectStore = useProjectStore();
const viewStore = useViewStore();
const sceneStore = useSceneStore();
const fileStore = useFileStore();
const { preferred, requestFullscreen, setPreferred } = useFullscreen();
const { t } = useI18n();
const dialog = useDialog();
const containerRef = ref(null);
const currentStep = ref(0);
const settingsDrawerVisible = ref(false);
const publishDrawerVisible = ref(false);
const previewing = ref(false);

const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');


// 提供 projectId 给子组件
provide('projectId', computed(() => projectStore.currentProject));

const flowSteps = computed(() => [
  { id: 'muse', label: t('mobileFlow.steps.muse') },
  { id: 'lorebook', label: t('mobileFlow.steps.world') },
  { id: 'synopsis', label: t('mobileFlow.steps.synopsis') },
  { id: 'structure', label: t('mobileFlow.steps.structure') },
  { id: 'production', label: t('mobileFlow.steps.production') },
  { id: 'blueprint', label: t('mobileFlow.steps.blueprint') }
]);

const currentStepLabel = computed(() => {
  return flowSteps.value[currentStep.value]?.label || t('mobileFlow.sparkArc');
});

const showChatFloat = ref(true);

const stepViewMap: AppViewKey[] = ['world', 'lorebook', 'synopsis', 'structure', 'production', 'blueprint'];
watch(currentStep, (idx) => {
  const view = stepViewMap[idx] || 'world';
  if (viewStore.currentView !== view) {
    viewStore.setView(view);
  }
}, { immediate: true });

function openSettings() {
  settingsDrawerVisible.value = true;
}

function openPublishDrawer() {
  publishDrawerVisible.value = true;
}

// ── 项目菜单（含切换、新建、重命名、删除、导入导出） ──
const projectSwitchOptions = computed<DropdownOption[]>(() => {
  const items: DropdownOption[] = projectStore.projects.map(p => ({
    label: p === projectStore.currentProject ? `✓ ${p}` : p,
    key: `switch:${p}`,
  }));
  items.push({ type: 'divider', key: 'd1' });
  items.push({ label: t('components.projectSelector.newProject'), key: 'create', icon: () => h(NIcon, null, { default: () => h(CirclePlus) }) });
  if (projectStore.currentProject) {
    items.push({ label: t('components.projectSelector.renameCurrentProject'), key: 'rename', icon: () => h(NIcon, null, { default: () => h(SquarePen) }) });
    items.push({ label: t('components.projectSelector.deleteCurrentProject'), key: 'delete', icon: () => h(NIcon, null, { default: () => h(Trash) }) });
  }
  items.push({ type: 'divider', key: 'd2' });
  items.push({ label: t('components.headerToolbar.exportProject'), key: 'export_project', icon: () => h(NIcon, null, { default: () => h(Archive) }) });
  items.push({ label: t('components.headerToolbar.importProject'), key: 'import_project', icon: () => h(NIcon, null, { default: () => h(PaintBucket) }) });
  return items;
});

async function handleProjectSwitch(key: string) {
  if (key === 'create') {
    await projectStore.createProject();
  } else if (key === 'rename') {
    handleRenameProject();
  } else if (key === 'delete') {
    handleDeleteProject();
  } else if (key === 'export_project') {
    exportProjectSpark();
  } else if (key === 'import_project') {
    importSparkInput.value?.click();
  } else if (key.startsWith('switch:')) {
    const name = key.slice(7);
    if (name !== projectStore.currentProject) {
      await projectStore.setCurrentProject(name);
    }
  }
}

async function handleRenameProject() {
  if (!projectStore.currentProject) return;
  const newName = await new Promise<unknown>((resolve) => bus.emit('prompt', {
    title: t('components.projectSelector.renameProject'),
    message: t('components.projectSelector.renamePrompt', { project: projectStore.currentProject }),
    defaultValue: projectStore.currentProject,
    resolve,
  }));
  if (typeof newName === 'string' && newName.trim()) {
    await projectStore.renameCurrentProject(newName);
  }
}

function handleDeleteProject() {
  if (!projectStore.currentProject) return;
  // 第一次确认
  dialog.warning({
    title: t('components.projectSelector.confirmDeleteTitle'),
    content: t('components.projectSelector.confirmDelete', { project: projectStore.currentProject }),
    positiveText: t('common.confirm'),
    negativeText: t('common.cancel'),
    onPositiveClick: () => {
      // 第二次确认
      dialog.error({
        title: t('components.projectSelector.confirmDeleteTitle'),
        content: t('components.projectSelector.confirmDeleteFinal', { project: projectStore.currentProject }),
        positiveText: t('common.delete'),
        negativeText: t('common.cancel'),
        onPositiveClick: () => {
          projectStore.deleteCurrentProject();
        },
      });
    },
  });
}

const importSparkInput = ref<HTMLInputElement | null>(null);

function onSparkFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  handleSparkImport(file);
  (e.target as HTMLInputElement).value = '';
}

async function exportProjectSpark() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'error', message: t('components.headerToolbar.selectProjectFirst') });
    return;
  }
  try {
    await exportProjectAsSpark(projectStore.currentProject);
    bus.emit('toast', { type: 'success', message: t('components.headerToolbar.exportProjectSuccess') });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { type: 'error', message: `${t('components.headerToolbar.exportProjectFailed')}: ${errorMessage}` });
  }
}

async function handleSparkImport(file: File) {
  try {
    const result = await importProjectFromSpark(file);
    const newProjectName = result.projectName || '';
    if (newProjectName) {
      await projectStore.loadProjects();
      projectStore.setCurrentProject(newProjectName);
    }
    bus.emit('toast', { type: 'success', message: t('components.headerToolbar.importProjectSuccess', { name: newProjectName }) });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { type: 'error', message: `${t('components.headerToolbar.importProjectFailed')}: ${errorMessage}` });
  }
}

async function quickPreview() {
  if (!projectStore.currentProject || previewing.value) {
    if (!projectStore.currentProject) {
      bus.emit('toast', { type: 'error', message: t('components.headerToolbar.selectProjectFirst') });
    }
    return;
  }

  // 先保存当前文件
  const currentFilePath = fileStore.selectedFile?.type === 'story' ? fileStore.selectedFile.path : null;
  if (currentFilePath) {
    try {
      await saveStory(projectStore.currentProject, currentFilePath, sceneStore.scriptData);
    } catch {
      return;
    }
  }

  previewing.value = true;
  try {
    const contentFormat = sceneStore.workspaceMode === 'novel' ? 'novel' : 'script';
    const res = await fetchWithAuth(`/api/versions/${projectStore.currentProject}/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ contentFormat }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({} as Record<string, unknown>));
      const errorMessage = typeof body.error === 'string'
        ? body.error
        : typeof body.message === 'string'
          ? body.message
          : t('components.headerToolbar.quickPreviewFailed');
      throw new Error(errorMessage);
    }

    const data = await res.json() as { version_id?: string };
    if (!data.version_id) {
      throw new Error(t('components.headerToolbar.quickPreviewFailed'));
    }

    window.open(`#/play/v/${data.version_id}`, '_blank');
    bus.emit('toast', { type: 'success', message: t('components.headerToolbar.quickPreviewStarted') });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || t('components.headerToolbar.quickPreviewFailed'));
    bus.emit('toast', { type: 'error', message: `${t('components.headerToolbar.quickPreviewFailed')}: ${errorMessage}` });
  } finally {
    previewing.value = false;
  }
}

// IntersectionObserver 检测当前可见卡片
let observer: IntersectionObserver | null = null;

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
  flowSteps.value.forEach((_, index) => {
    const element = document.getElementById(`step-${index + 1}`);
    if (element) {
      observer?.observe(element);
    }
  });
}

// 首次进入移动端时触发统一引导（等待登录后检查完成）
const { triggerIfFirst } = useOnboarding();
const onPostLoginReady = () => {
  nextTick(() => triggerIfFirst('mobile-workspace'));
};

onMounted(() => {
  setTimeout(setupObserver, 200);

  // 确保移动端独立初始化项目列表并恢复上次选中的项目
  if (projectStore.projects.length === 0) {
    projectStore.loadProjects();
  }

  bus.on('post-login-ready', onPostLoginReady);
  // 如果 App.vue 已经发过 post-login-ready（竞态：子组件晚于 App mount），直接触发
  if ((bus as any).postLoginReadySent) onPostLoginReady();

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
  bus.off('post-login-ready', onPostLoginReady);
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
  height: calc(var(--mobile-header-height, 48px) + var(--sat, 0px));
  z-index: 200;
  
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  padding-top: var(--sat, 0px);
  
  background: color-mix(in srgb, var(--spark-panel-bg) 85%, transparent);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid color-mix(in srgb, var(--spark-border) 50%, transparent);
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
  gap: 4px;
  width: auto;
}

.app-logo-link {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: inherit;
  line-height: 0;
}
.app-logo {
  display: flex;
  align-items: center;
  line-height: 0;
}

.tooltip-dropdown-trigger {
  display: inline-flex;
}


.current-step-label {
  font-weight: 600;
  font-size: var(--spark-fs-md);
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
  font-size: var(--spark-fs-lg);
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

/* 移动端移除选项卡滑动指示条阴影特效 */
:deep(.n-tabs-bar) {
  box-shadow: none !important;
}

:deep(.n-tab-pane) {
  padding: 16px 0;
  padding-bottom: 100px;
}
</style>
