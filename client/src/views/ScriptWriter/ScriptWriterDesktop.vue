
<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      @open-settings="openSettings"
      @auto-save-changed="onAutoSaveChanged"
      @logout="onLogout"
      @open-version-manager="openVersionManager"
    />

    <main>
      <ActivityBar @open-settings="openSettings" />

      <div class="workspace-area">
        <transition name="spark-view" mode="out-in">
          <keep-alive>
            <component :is="activeComponent" :key="viewStore.currentView" :projectId="projectStore.currentProject" />
          </keep-alive>
        </transition>

        <div v-show="viewStore.currentView === 'production'" class="production-shell">
          <div class="production-layout">
            <div class="panel sidebar-panel" :style="{ width: sidebarWidth + 'px' }">
              <div class="sidebar-section file-section">
                <div class="file-section-header">
                  <span class="file-section-title">{{ t('views.scriptWriter.desktop.workspaceManager') }}</span>
                  <n-dropdown
                    v-if="isNovelWorkspace"
                    trigger="click"
                    :options="submissionExportOptions"
                    :disabled="!projectStore.currentProject || exportingSubmission"
                    @select="handleSubmissionExport"
                  >
                    <n-button
                      class="submission-platform-button"
                      secondary
                      size="small"
                      :loading="exportingSubmission"
                      :disabled="!projectStore.currentProject"
                    >
                      <template #icon>
                        <n-icon>
                          <Send />
                        </n-icon>
                      </template>
                      {{ t('components.novelEditor.submissionExport.button') }}
                    </n-button>
                  </n-dropdown>
                </div>
                <FileTree :key="workspaceMode" />
              </div>
            </div>

            <div class="resizer" data-resize="sidebar" @mousedown="handleMouseDown"></div>

            <div class="panel center-panel" style="position: relative;">
              <div class="center-panel-header">
                <h2 v-if="settingsVisible">{{ t('views.scriptWriter.desktop.settingEditor') }}</h2>
                <h2 v-else-if="!isNovelWorkspace">{{ t('views.scriptWriter.desktop.dialogueTree') }}</h2>
                <h2 v-else>{{ t('views.scriptWriter.desktop.modeNovel') }}</h2>
              </div>

              <Transition name="workspace-mode" mode="out-in">
                <LorebookEditor v-if="settingsVisible" key="settings" :visible="true" @close="settingsVisible = false" />
                <NovelReader v-else-if="isNovelWorkspace" key="novel-editor" :content="typeof sceneStore.scriptData === 'string' ? sceneStore.scriptData : ''" />
                <DialogueTree v-else key="dialogue-tree" />
              </Transition>

              <GlobalLoading scope="production" />
            </div>

            <Transition name="inspector-slide">
              <div v-if="showInspectorPanel" class="resizer" data-resize="center" @mousedown="handleMouseDown"></div>
            </Transition>

            <Transition name="inspector-slide">
              <div v-show="showInspectorPanel" class="panel inspector-panel" :style="{ width: inspectorWidth + 'px' }">
                <template v-if="!settingsVisible">
                  <NodeEditor key="node-editor" />
                </template>
                <div v-else class="settings-right-panel">
                  <AiSettingsPanel :visible="true" />
                  <CharacterGeneratorPanel :visible="true" />
                </div>
              </div>
            </Transition>

            <template v-if="aiSidebarVisible">
              <div class="resizer" data-resize="inspector" @mousedown="handleMouseDown"></div>
              <div class="panel ai-sidebar" :style="{ width: aiSidebarWidth + 'px' }">
                <AiPanel />
              </div>
            </template>
          </div>
        </div>
      </div>
  

        <n-modal v-model:show="versionManagerVisible" preset="card" :title="t('views.scriptWriter.desktop.versionManager')" style="width: 800px; max-height: 90vh;">
          <VersionManager :projectId="projectStore.currentProject || undefined" :content-format="workspaceMode" hide-title />
        </n-modal>

      <GlobalChatFloat />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, h, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { NButton, NDropdown, NIcon, NModal, type DropdownOption } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { useOnboarding } from '../../onboarding';
import VersionManager from '../../components/dlg-editor/VersionManager.vue';
import HeaderToolbar from '../../components/layouts/desktop/HeaderToolbar.vue';
import FileTree from '../../components/file-explorer/FileTree.vue';
import BlueprintView from '../Blueprint/BlueprintIndex.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
import NovelReader from '../../components/dlg-editor/NovelReader.vue';
import NodeEditor from '../../components/dlg-editor/NodeEditor.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import GlobalChatFloat from '../../components/chat/GlobalChatFloat.vue';
import ActivityBar from '../../components/layouts/desktop/ActivityBar.vue';

// 这里的 View 引用改为新的分发器路径
import WorldView from '../World/WorldIndex.vue';
import SynopsisView from '../Synopsis/SynopsisIndex.vue';
import StructureView from '../Structure/StructureIndex.vue';
import StyleView from '../Style/StyleIndex.vue';
import EngineView from '../Engine/EngineIndex.vue';
import SettingsView from '../Settings/SettingsIndex.vue';
import DashboardView from '../Dashboard/DashboardIndex.vue';
import ChatDesktopView from '../ChatDesktop/ChatDesktopIndex.vue';

import bus from '../../eventBus';
import { useResizer } from '../../hooks/useResizer';
import { useScriptWriterLogic } from '../../composables/useScriptWriterLogic';
import { useSceneStore } from '../../components/stores/sceneStore';
import { Send } from '@lucide/vue';
import { shouldShowProductionInspector } from './productionInspector';
import {
  NOVEL_SUBMISSION_PLATFORMS,
  downloadNovelSubmissionExport,
  type NovelSubmissionPlatform,
} from '../../services/storyService';

const { t } = useI18n();
const sceneStore = useSceneStore();
const { sidebarWidth, inspectorWidth, aiSidebarWidth, handleMouseDown } = useResizer();
const {
  viewStore,
  projectStore,
  username,
  settingsVisible,
  versionManagerVisible,
  aiSidebarVisible,
  openSettings,
  onLogout
} = useScriptWriterLogic();

// 首次进入桌面工作台时触发引导（等待登录后检查完成）
const { triggerIfFirst } = useOnboarding();
const onPostLoginReady = () => {
  nextTick(() => triggerIfFirst('desktop-workspace'));
};
onMounted(() => {
  bus.on('post-login-ready', onPostLoginReady);
  // 如果 App.vue 已经发过 post-login-ready（竞态：子组件晚于 App mount），直接触发
  if ((bus as any).postLoginReadySent) onPostLoginReady();
});
onUnmounted(() => {
  bus.off('post-login-ready', onPostLoginReady);
});

function onAutoSaveChanged(_v: boolean) {
  // autoSaveEnabled 已改为 computed 读 localStorage，无需手动赋值
}

function openVersionManager() {
  versionManagerVisible.value = true;
}

const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');

const isNovelWorkspace = computed(() => workspaceMode.value === 'novel');
const showInspectorPanel = computed(() => shouldShowProductionInspector({
  isNovelWorkspace: isNovelWorkspace.value,
  settingsVisible: settingsVisible.value,
  hasOpenScriptFile: !!sceneStore.currentFilePath,
  hasCurrentScene: !!sceneStore.currentScene,
  selectionType: sceneStore.selectionType,
}));
const exportingSubmission = ref(false);
const submissionExportOptions = computed<DropdownOption[]>(() => (
  NOVEL_SUBMISSION_PLATFORMS.map(platform => ({
    key: platform,
    label: t(`components.novelEditor.submissionExport.platforms.${platform}`),
    icon: () => h(NIcon, null, { default: () => h(Send) }),
  }))
));

async function handleSubmissionExport(key: string | number) {
  if (exportingSubmission.value) return;
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('components.novelEditor.submissionExport.noProject') });
    return;
  }

  exportingSubmission.value = true;
  try {
    if (sceneStore.workspaceMode === 'novel') {
      await sceneStore._saveStory();
    }
    await downloadNovelSubmissionExport(projectStore.currentProject, key as NovelSubmissionPlatform);
    bus.emit('toast', { type: 'success', message: t('components.novelEditor.submissionExport.success') });
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    bus.emit('toast', {
      type: 'error',
      message: `${t('components.novelEditor.submissionExport.failed')}: ${errorMessage}`,
    });
  } finally {
    exportingSubmission.value = false;
  }
}

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return BlueprintView;
    case 'settings': return SettingsView;
    case 'dashboard': return DashboardView;
    case 'chat': return ChatDesktopView;
    default: return null;
  }
});
</script>

<style scoped>
.container {
  height: 100vh;
  width: 100%;
  max-width: none;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.workspace-area {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  overflow: hidden;
  position: relative;
}

.production-shell {
  display: flex;
  flex-direction: column;
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: var(--spark-bg);
}

.production-layout {
  display: flex;
  flex: 1;
  width: 100%;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.sidebar-panel {
  width: 250px;
  min-width: 0;
  max-width: 400px;
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-right: 1px solid var(--n-border-color);
}

.sidebar-section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 8px 8px 16px;
  background: var(--spark-panel-header-bg);
  border-bottom: 1px solid var(--spark-border);
  flex-shrink: 0;
}

.file-section-title {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--spark-fs-base);
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.submission-platform-button {
  flex: 0 1 auto;
  max-width: 100%;
}

.submission-platform-button :deep(.n-button__content) {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sidebar-divider {
  height: 1px;
  background-color: var(--n-border-color);
  margin: 4px 0;
}

.center-panel {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color);
}

.center-panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--spark-panel-header-bg);
  border-bottom: 1px solid var(--spark-border);
  flex-shrink: 0;
  position: relative;
}

.inspector-panel {
  width: 300px;
  min-width: 0;
  max-width: 600px;
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
}

.ai-sidebar {
  width: 350px;
  min-width: 0;
  max-width: 800px;
  flex: 0 0 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
}

.settings-right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 12px;
}

.resizer {
  width: 4px;
  flex-shrink: 0;
  background: transparent;
  cursor: col-resize;
  z-index: 10;
  transition: background 0.2s;
}

.resizer:hover {
  background: var(--spark-primary);
}

h2 {
  font-size: var(--spark-fs-base);
  padding: 0;
  margin: 0;
}

.workspace-mode-enter-from,
.workspace-mode-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.995);
}
.workspace-mode-enter-active,
.workspace-mode-leave-active {
  transition: opacity 0.22s ease, transform 0.22s cubic-bezier(.4,0,.2,1);
}
.workspace-mode-enter-to,
.workspace-mode-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
}

.inspector-slide-enter-from {
  opacity: 0;
  transform: translateX(18px);
}
.inspector-slide-leave-to {
  opacity: 0;
  transform: translateX(18px);
}
.inspector-slide-enter-active,
.inspector-slide-leave-active {
  transition: opacity 0.24s ease, transform 0.24s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}
.inspector-slide-enter-to,
.inspector-slide-leave-from {
  opacity: 1;
  transform: translateX(0);
}

@media (max-width: 1520px) {
  .resizer {
    width: 3px;
  }
}

@media (max-width: 1280px) {
  h2 {
    font-size: var(--spark-fs-sm);
    padding: 8px 12px;
  }

  .sidebar-panel {
    max-width: 260px;
  }

  .inspector-panel {
    max-width: 320px;
  }

  .ai-sidebar {
    max-width: 340px;
  }

  .settings-right-panel {
    padding: 10px;
    gap: 12px;
  }
}
</style>
