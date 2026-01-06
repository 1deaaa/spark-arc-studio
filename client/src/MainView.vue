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
      <!-- New Activity Bar -->
      <ActivityBar @open-settings="openSettings" />

      <!-- Workspace Area -->
      <div class="workspace-area">
        
        <!-- Cached Views (Muse, World, Structure, Style, Engine, Blueprint, Settings) -->
        <keep-alive>
          <component :is="activeComponent" :projectId="projectStore.currentProject" />
        </keep-alive>

        <!-- View: Production (Original Editor) -->
        <div v-show="viewStore.currentView === 'production'" class="production-layout">
          <!-- 左侧边栏：资源管理 (文件 + 场景) -->
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

          <!-- 中间：主工作区 (对话树 / 设定) -->
          <div class="panel center-panel" style="position: relative;">
            <h2 v-if="!settingsVisible">对话树</h2>
            <h2 v-else>设定编辑</h2>
            <DialogueTree v-if="!settingsVisible" />
            <LorebookEditor v-else :visible="true" @close="settingsVisible = false" />
            <!-- 局部 Loading 遮罩 -->
            <GlobalLoading />
          </div>

          <div class="resizer" data-resize="center" @mousedown="handleMouseDown"></div>

          <!-- 右侧：属性/检查器 (节点编辑 / 设定面板) -->
          <div class="panel inspector-panel" :style="{ width: inspectorWidth + 'px' }">
            <template v-if="!settingsVisible">
              <NodeEditor />
            </template>
            <div v-else class="settings-right-panel">
              <AiSettingsPanel :visible="true" />
              <CharacterGeneratorPanel :visible="true" />
            </div>
          </div>

          <!-- 极右：AI 助手 (独立侧边栏) -->
          <template v-if="aiSidebarVisible">
            <div class="resizer" data-resize="inspector" @mousedown="handleMouseDown"></div>
            <div class="panel ai-sidebar" :style="{ width: aiSidebarWidth + 'px' }">
              <AiPanel />
            </div>
          </template>
        </div>
      </div>
  
      <!-- 右下角绿色提示（带过渡动画） -->
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
import { NModal } from 'naive-ui';
import VersionManager from './components/dlg-editor/VersionManager.vue';
import HeaderToolbar from './components/dlg-editor/HeaderToolbar.vue';
import FileTree from './components/file-explorer/FileTree.vue';
import SceneList from './components/dlg-editor/SceneList.vue';
import StoryBlueprint from './components/dlg-editor/StoryBlueprint.vue';
import DialogueTree from './components/dlg-editor/DialogueTree.vue';
import NodeEditor from './components/dlg-editor/NodeEditor.vue';
import AiPanel from './components/dlg-editor/AiPanel.vue';
import LorebookEditor from './components/lorebook/LorebookEditor.vue';
import AiSettingsPanel from './components/lorebook/AiSettingsPanel.vue';
import CharacterGeneratorPanel from './components/lorebook/CharacterGeneratorPanel.vue';
import LoginPage from './components/user/LoginPage.vue';
import GlobalLoading from './components/share/GlobalLoading.vue';
import GlobalChatFloat from './components/share/GlobalChatFloat.vue';

// New Components
import ActivityBar from './components/layout/ActivityBar.vue';
import WorldView from './views/WorldView.vue';
import SynopsisView from './views/SynopsisView.vue';
import StructureView from './views/StructureView.vue';
import StyleView from './views/StyleView.vue';
import EngineView from './views/EngineView.vue';
import SettingsView from './views/SettingsView.vue';
import AdminView from './views/AdminView.vue';
import { useViewStore } from './components/stores/viewStore';
import { useResizer } from './hooks/useResizer';

import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import bus from './eventBus';
import { useSceneStore } from './components/stores/sceneStore';
import { useProjectStore } from './components/stores/projectStore';
import { useFileStore } from './components/stores/fileStore';
import { getUserInfo } from './services/api';
import { useChatStore } from './components/stores/chatStore';
import { serializeToArc } from './services/arcParser';

const route = useRoute();
const router = useRouter();
const viewStore = useViewStore();
const { sidebarWidth, inspectorWidth, aiSidebarWidth, handleMouseDown } = useResizer();

// URL scheme (no legacy compatibility):
// - Non-production: /project/:projectId?view=world|synopsis|...
// - Production only: /project/:projectId/file/:filePath?scene=:sceneId
const urlHydrated = ref(false);
const isRestoringUrl = ref(false);
const isSyncingUrl = ref(false);

function safeDecodeURIComponent(s) {
  try { return decodeURIComponent(s); } catch { return s; }
}

function parseStateFromRoute(r) {
  const m = (r.path || '').match(/^\/project\/([^/]+)(?:\/file\/(.+))?$/);
  const projectId = m?.[1] ? safeDecodeURIComponent(m[1]) : '';
  const filePath = m?.[2]
    ? m[2].split('/').map(seg => safeDecodeURIComponent(seg)).join('/')
    : '';

  const viewFromQuery = (typeof r.query.view === 'string' && r.query.view) ? r.query.view : 'production';
  const sceneId = (typeof r.query.scene === 'string' && r.query.scene) ? r.query.scene : '';

  // Strict rule: file path in URL means production view.
  const view = filePath ? 'production' : viewFromQuery;

  return { projectId, filePath, sceneId, view };
}

function buildUrlFromState() {
  const project = projectStore.currentProject;
  const file = fileStore.selectedFile;
  const scene = sceneStore.currentScene;
  const view = viewStore.currentView || 'production';

  const query = {};
  if (view !== 'production') {
    query.view = view;
  }
  if (view === 'production' && scene?.scene) {
    query.scene = scene.scene;
  }

  if (!project) {
    return { path: '/', query };
  }

  const encodedProject = encodeURIComponent(project);
  if (view === 'production' && file) {
    const filePath = file.path || file.name;
    const encodedFilePath = filePath.split('/').map(encodeURIComponent).join('/');
    return { path: `/project/${encodedProject}/file/${encodedFilePath}`, query };
  }

  return { path: `/project/${encodedProject}`, query };
}

async function restoreStateFromRoute(r) {
  const { projectId, filePath, sceneId, view } = parseStateFromRoute(r);

  if (view && viewStore.currentView !== view) {
    viewStore.setView(view);
  }

  if (!projectId) return;
  if (!projectStore.projects.includes(projectId)) return;

  if (projectStore.currentProject !== projectId) {
    await projectStore.setCurrentProject(projectId);
  }

  if (view !== 'production') return;
  if (!filePath) return;

  try {
    if (fileStore.selectedFile?.path !== filePath) {
      await fileStore.setCurrentFile(projectId, filePath);
    }

    if (sceneId) {
      const scene = (sceneStore.scriptData || []).find(s => s.scene === sceneId);
      if (scene && sceneStore.currentScene !== scene) {
        sceneStore.selectScene(scene);
      }
    }
  } catch (e) {
    console.warn('URL 恢复失败:', e);
  }
}

async function syncUrlToState({ replace = true } = {}) {
  if (!urlHydrated.value || isRestoringUrl.value || isSyncingUrl.value) return;

  const location = buildUrlFromState();
  const currentFullPath = router.currentRoute.value.fullPath;
  const nextFullPath = router.resolve(location).fullPath;
  if (currentFullPath === nextFullPath) return;

  isSyncingUrl.value = true;
  try {
    if (replace) {
      await router.replace(location);
    } else {
      await router.push(location);
    }
  } finally {
    isSyncingUrl.value = false;
  }
}

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'world': return WorldView;
    case 'synopsis': return SynopsisView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return StoryBlueprint;
    case 'settings': return SettingsView;
    case 'admin': return AdminView;
    default: return null;
  }
});

const settingsVisible = ref(false);
const versionManagerVisible = ref(false);
const aiSidebarVisible = ref(true); // 默认显示 AI 侧边栏
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const username = ref('');
const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
const saveHintVisible = ref(false);
const chatStore = useChatStore();

// Prevent refresh "flash": set initial view from URL synchronously before first render.
// (We will still restore project/file/scene asynchronously in onMounted.)
{
  const { view } = parseStateFromRoute(route);
  if (view && viewStore.currentView !== view) {
    viewStore.setView(view);
  }
}

onMounted(() => {
  chatStore.registerContextProvider(() => {
    // 1. WorldView (Muse / Lorebook) - 返回灵感工坊内容
    if (viewStore.currentView === 'world') {
      const inspiration = projectStore.currentInspiration || '';
      if (inspiration) {
        return `【当前灵感工坊内容】\n${inspiration}`;
      }
    }
    // 2. Production View (Scriptwriter) - 返回场景文本
    if (viewStore.currentView === 'production') {
      if (sceneStore.currentScene) {
        try {
          // 序列化当前场景为 ARC 文本
          const lines = serializeToArc([sceneStore.currentScene]);
          return lines.join('\n');
        } catch (e) {
          console.warn('序列化场景失败', e);
        }
      }
    }
    // 默认返回空
    return '';
  });
});

function showSaveHint() {
  saveHintVisible.value = true;
  clearTimeout(showSaveHint._t);
  showSaveHint._t = setTimeout(() => saveHintVisible.value = false, 1200);
}

function openSettings() { settingsVisible.value = true; }

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    bus.emit('save-request');
  }
}

function sceneSelectedHandler() {
  settingsVisible.value = false;
  // Switch to production view if a scene is selected from blueprint
  if (viewStore.currentView === 'blueprint') {
      viewStore.setView('production');
  }
}

watch(() => sceneStore.currentScene, () => {
  settingsVisible.value = false;
});

onMounted(async () => {
  try {
    const user = await getUserInfo();
    username.value = user?.username || '';
    await projectStore.loadProjects();
    isRestoringUrl.value = true;
    await restoreStateFromRoute(route);
    urlHydrated.value = true;
    isRestoringUrl.value = false;
    // Always keep URL in canonical form.
    await syncUrlToState({ replace: true });
  } catch (e) {
    router.push('/login');
  }
  
  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  bus.off('saved', showSaveHint);
  bus.off('scene-selected', sceneSelectedHandler);
});

async function onLoggedIn(user) {
  username.value = user?.username || '';
  await projectStore.loadProjects();
  
  const postLoginUrl = localStorage.getItem('postLoginUrl');
  localStorage.removeItem('postLoginUrl');
  
  if (postLoginUrl) {
    router.push(postLoginUrl);
  } else {
    router.push('/');
  }
}

function onLogout() {
  // Backend uses httpOnly cookie, so just redirect to login
  router.push('/login');
}

watch([
  () => projectStore.currentProject,
  () => fileStore.selectedFile, 
  () => sceneStore.currentScene, 
  () => viewStore.currentView
], () => {
  syncUrlToState({ replace: true });
});

// Handle back/forward or manual URL edits: restore state from route after navigation is confirmed.
watch(
  () => router.currentRoute.value.fullPath,
  async () => {
    if (!urlHydrated.value || isSyncingUrl.value) return;
    isRestoringUrl.value = true;
    try {
      await restoreStateFromRoute(router.currentRoute.value);
    } finally {
      isRestoringUrl.value = false;
    }
  },
  { flush: 'post' }
);

</script>

<style>
/* New Layout Styles */
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

.inspector-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Styles from before */
.settings-right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}
.settings-right-panel > * {
  flex-shrink: 0;
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
</style>