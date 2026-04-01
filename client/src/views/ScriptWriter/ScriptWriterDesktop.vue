
<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      :autoSaveEnabled="autoSaveEnabled"
      @open-settings="openSettings"
      @auto-save-changed="(v) => autoSaveEnabled = v"
      @logout="onLogout"
      @open-version-manager="openVersionManager"
    />

    <main>
      <ActivityBar :is-admin="isAdmin" @open-settings="openSettings" />

      <div class="workspace-area">
        <transition name="spark-view" mode="out-in">
          <keep-alive>
            <component :is="activeComponent" :key="viewStore.currentView" :projectId="projectStore.currentProject" />
          </keep-alive>
        </transition>

        <div v-show="viewStore.currentView === 'production'" class="production-layout">
          <div class="panel sidebar-panel" :style="{ width: sidebarWidth + 'px' }">
            <div class="sidebar-section file-section">
              <div class="file-section-header">
                <span class="file-section-title">作品管理器</span>
                <SparkSegment
                  :model-value="workspaceMode"
                  :options="[{value:'script',label:'剧本'},{value:'novel',label:'小说'}]"
                  size="tiny"
                  @update:model-value="handleWorkspaceModeChange"
                />
              </div>
              <Transition name="workspace-mode" mode="out-in">
                <FileTree :key="workspaceMode" />
              </Transition>
            </div>
          </div>

          <div class="resizer" data-resize="sidebar" @mousedown="handleMouseDown"></div>

          <div class="panel center-panel" style="position: relative;">
            <h2 v-if="settingsVisible">设定编辑</h2>
            <h2 v-else-if="!isNovelWorkspace">对话树</h2>
            
            <Transition name="workspace-mode" mode="out-in">
              <LorebookEditor v-if="settingsVisible" key="settings" :visible="true" @close="settingsVisible = false" />
              <NovelReader v-else-if="isNovelWorkspace" key="novel-editor" :content="typeof sceneStore.scriptData === 'string' ? sceneStore.scriptData : ''" />
              <DialogueTree v-else key="dialogue-tree" />
            </Transition>
            
            <GlobalLoading scope="production" />
          </div>

          <Transition name="inspector-slide">
            <div v-if="!isNovelWorkspace || settingsVisible" class="resizer" data-resize="center" @mousedown="handleMouseDown"></div>
          </Transition>

          <Transition name="inspector-slide">
            <div v-if="!isNovelWorkspace || settingsVisible" class="panel inspector-panel" :style="{ width: inspectorWidth + 'px' }">
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
  
      <transition name="save-hint">
        <div v-show="saveHintVisible" class="save-hint">已自动保存</div>
      </transition>

        <n-modal v-model:show="versionManagerVisible" preset="card" title="版本管理" style="width: 800px; max-height: 90vh;">
          <VersionManager :projectId="projectStore.currentProject || undefined" :content-format="workspaceMode" />
        </n-modal>

      <GlobalChatFloat />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NModal } from 'naive-ui';
import SparkSegment from '../../components/share/SparkSegment.vue';
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
import GlobalChatFloat from '../../components/share/GlobalChatFloat.vue';
import ActivityBar from '../../components/layouts/desktop/ActivityBar.vue';

// 这里的 View 引用改为新的分发器路径
import WorldView from '../World/WorldIndex.vue';
import SynopsisView from '../Synopsis/SynopsisIndex.vue';
import StructureView from '../Structure/StructureIndex.vue';
import StyleView from '../Style/StyleIndex.vue';
import EngineView from '../Engine/EngineIndex.vue';
import SettingsView from '../Settings/SettingsIndex.vue';
import AdminView from '../Admin/AdminIndex.vue';
import ChatDesktopView from '../ChatDesktop/ChatDesktopIndex.vue';

import { useResizer } from '../../hooks/useResizer';
import { useScriptWriterLogic } from '../../composables/useScriptWriterLogic';
import { useFileStore } from '../../components/stores/fileStore';
import { useSceneStore } from '../../components/stores/sceneStore';

const fileStore = useFileStore();
const sceneStore = useSceneStore();
const { sidebarWidth, inspectorWidth, aiSidebarWidth, handleMouseDown } = useResizer();
const {
  viewStore,
  projectStore,
  username,
  isAdmin,
  autoSaveEnabled,
  saveHintVisible,
  settingsVisible,
  versionManagerVisible,
  aiSidebarVisible,
  openSettings,
  onLogout
} = useScriptWriterLogic();

function openVersionManager() {
  versionManagerVisible.value = true;
}

const workspaceMode = computed({
  get: () => sceneStore.workspaceMode || 'script',
  set: (mode) => {
    sceneStore.setWorkspaceMode(mode);
  }
});

const isNovelWorkspace = computed(() => workspaceMode.value === 'novel');

async function handleWorkspaceModeChange(mode) {
  const normalized = mode === 'novel' ? 'novel' : 'script';
  sceneStore.setWorkspaceMode(normalized);
  if (projectStore.currentProject) {
    await fileStore.loadFileTree(projectStore.currentProject, normalized);
  }

  const expectedFormat = normalized === 'novel' ? 'novel' : 'arc';
  if (!fileStore.selectedFile?.format || fileStore.selectedFile.format !== expectedFormat) {
    fileStore.selectedFile = null;
    sceneStore.resetForWorkspaceMode(normalized);
  }
}

const activeComponent = computed(() => {
  if (viewStore.currentView === 'admin' && !isAdmin.value) {
    return SettingsView;
  }
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return BlueprintView;
    case 'settings': return SettingsView;
    case 'admin': return AdminView;
    case 'chat': return ChatDesktopView;
    default: return null;
  }
});
</script>

<style scoped>
.container {
  height: 100vh;
  width: 100%;
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

.production-layout {
  display: flex;
  flex: 1;
  width: 100%;
  min-width: 0;
  height: 100%;
  overflow: hidden;
  background: var(--spark-bg);
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
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
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

.save-hint {
  position: fixed;
  right: 16px;
  bottom: 16px;
  background: var(--spark-success);
  color: var(--spark-text-inverse);
  padding: 8px 12px;
  border-radius: var(--spark-radius-sm);
  box-shadow: var(--spark-shadow-sm);
  z-index: 9999;
}

.save-hint-enter-from,
.save-hint-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
.save-hint-enter-active,
.save-hint-leave-active {
  transition: opacity .18s ease, transform .18s ease;
}
.save-hint-enter-to,
.save-hint-leave-from {
  opacity: 1;
  transform: translateY(0) scale(1);
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
  font-size: 14px;
  padding: 8px 16px;
  margin: 0;
  background: var(--spark-panel-header-bg);
  border-bottom: 1px solid var(--spark-border);
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
    font-size: 13px;
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
