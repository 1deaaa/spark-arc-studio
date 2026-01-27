
<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      :autoSaveEnabled="autoSaveEnabled"
      @open-settings="openSettings"
      @auto-save-changed="(v) => autoSaveEnabled = v"
      @logout="onLogout"
      @open-version-manager="versionManagerVisible = true"
    />

    <main>
      <ActivityBar @open-settings="openSettings" />

      <div class="workspace-area">
        <keep-alive>
          <component :is="activeComponent" :projectId="projectStore.currentProject" />
        </keep-alive>

        <div v-show="viewStore.currentView === 'production'" class="production-layout">
          <div class="panel sidebar-panel" :style="{ width: sidebarWidth + 'px' }">
            <div class="sidebar-section file-section">
              <h2>文件管理器</h2>
              <FileTree />
            </div>
            <div class="sidebar-divider"></div>
            <div class="sidebar-section scene-section">
              <h2>场景列表</h2>
              <SceneList />
            </div>
          </div>

          <div class="resizer" data-resize="sidebar" @mousedown="handleMouseDown"></div>

          <div class="panel center-panel" style="position: relative;">
            <h2 v-if="!settingsVisible">对话树</h2>
            <h2 v-else>设定编辑</h2>
            <DialogueTree v-if="!settingsVisible" />
            <LorebookEditor v-else :visible="true" @close="settingsVisible = false" />
            <GlobalLoading />
          </div>

          <div class="resizer" data-resize="center" @mousedown="handleMouseDown"></div>

          <div class="panel inspector-panel" :style="{ width: inspectorWidth + 'px' }">
            <template v-if="!settingsVisible">
              <NodeEditor />
            </template>
            <div v-else class="settings-right-panel">
              <AiSettingsPanel :visible="true" />
              <CharacterGeneratorPanel :visible="true" />
            </div>
          </div>

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
        <VersionManager :projectId="projectStore.currentProject" />
      </n-modal>

      <GlobalChatFloat />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { NModal } from 'naive-ui';
import VersionManager from '../../components/dlg-editor/VersionManager.vue';
import HeaderToolbar from '../../components/layouts/desktop/HeaderToolbar.vue';
import FileTree from '../../components/file-explorer/FileTree.vue';
import SceneList from '../../components/dlg-editor/SceneList.vue';
import BlueprintView from '../Blueprint/BlueprintIndex.vue';
import DialogueTree from '../../components/dlg-editor/DialogueTree.vue';
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

import { useResizer } from '../../hooks/useResizer';
import { useScriptWriterLogic } from '../../composables/useScriptWriterLogic';

const { sidebarWidth, inspectorWidth, aiSidebarWidth, handleMouseDown } = useResizer();
const {
  viewStore,
  projectStore,
  username,
  autoSaveEnabled,
  saveHintVisible,
  settingsVisible,
  versionManagerVisible,
  aiSidebarVisible,
  openSettings,
  onLogout
} = useScriptWriterLogic();

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return BlueprintView;
    case 'settings': return SettingsView;
    case 'admin': return AdminView;
    default: return null;
  }
});
</script>

<style scoped>
.container {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.workspace-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.production-layout {
  display: flex;
  flex: 1;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.sidebar-panel {
  width: 250px;
  min-width: 150px;
  max-width: 400px;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-right: 1px solid var(--n-border-color);
}

.sidebar-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-divider {
  height: 1px;
  background-color: var(--n-border-color);
  margin: 4px 0;
}

.center-panel {
  flex: 1;
  min-width: 300px;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color);
}

.inspector-panel {
  width: 300px;
  min-width: 200px;
  max-width: 600px;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color-modal);
  border-left: 1px solid var(--n-border-color);
}

.ai-sidebar {
  width: 350px;
  min-width: 250px;
  max-width: 800px;
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
</style>
