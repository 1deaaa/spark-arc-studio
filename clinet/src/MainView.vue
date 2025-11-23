<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      :autoSaveEnabled="autoSaveEnabled"
      :aiSidebarVisible="aiSidebarVisible"
      @open-settings="openSettings"
      @auto-save-changed="(v) => autoSaveEnabled = v"
      @logout="onLogout"
      @toggle-ai-sidebar="aiSidebarVisible = !aiSidebarVisible"
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
          <div class="panel sidebar-panel">
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

          <div class="resizer" data-resize="sidebar"></div>

          <!-- 中间：主工作区 (对话树 / 设定) -->
          <div class="panel center-panel">
            <h2 v-if="!settingsVisible">对话树</h2>
            <h2 v-else>设定编辑</h2>
            <DialogueTree v-if="!settingsVisible" />
            <LorebookEditor v-else :visible="true" @close="settingsVisible = false" />
          </div>

          <div class="resizer" data-resize="center"></div>

          <!-- 右侧：属性/检查器 (节点编辑 / 设定面板) -->
          <div class="panel inspector-panel">
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
            <div class="resizer" data-resize="inspector"></div>
            <div class="panel ai-sidebar">
              <AiPanel />
            </div>
          </template>
        </div>
      </div>
  
      <!-- 右下角绿色提示（带过渡动画） -->
      <transition name="save-hint">
        <div v-show="saveHintVisible" class="save-hint">已自动保存</div>
      </transition>
    </main>
  </div>
</template>

<script setup>
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

// New Components
import ActivityBar from './components/layout/ActivityBar.vue';
import MuseView from './views/MuseView.vue';
import WorldView from './views/WorldView.vue';
import StructureView from './views/StructureView.vue';
import StyleView from './views/StyleView.vue';
import EngineView from './views/EngineView.vue';
import SettingsView from './views/SettingsView.vue';
import { useViewStore } from './components/stores/viewStore';

import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue';
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router';
import bus from './eventBus';
import { useSceneStore } from './components/stores/sceneStore';
import { useProjectStore } from './components/stores/projectStore';
import { useFileStore } from './components/stores/fileStore';
import { getUserInfo } from './services/api';

const route = useRoute();
const router = useRouter();
const viewStore = useViewStore();

const activeComponent = computed(() => {
  switch (viewStore.currentView) {
    case 'muse': return MuseView;
    case 'world': return WorldView;
    case 'structure': return StructureView;
    case 'style': return StyleView;
    case 'engine': return EngineView;
    case 'blueprint': return StoryBlueprint;
    case 'settings': return SettingsView;
    default: return null;
  }
});

const settingsVisible = ref(false);
const aiSidebarVisible = ref(true); // 默认显示 AI 侧边栏
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const username = ref('');
const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
const saveHintVisible = ref(false);

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

let isResizing = false;
let currentResizer = null;
let startX = 0;
let startWidth = 0;
let targetPanel = null;

function getPanelByType(type) {
  if (type === 'sidebar') return document.querySelector('.sidebar-panel');
  if (type === 'center') return document.querySelector('.center-panel'); // 注意：center 通常是 flex-grow，但如果我们要调整它的宽度，可能需要调整 inspector 的宽度？
  // 实际上，通常我们调整的是 sidebar, inspector, ai-sidebar 的宽度，center 自适应。
  // 但是这里有 3 个 resizer。
  // resizer 1 (sidebar): 调整 sidebar 宽度。
  // resizer 2 (center): 位于 center 和 inspector 之间。调整 inspector 宽度（反向）或者 center 宽度？
  // 如果 center 是 flex:1，我们应该调整 inspector 的宽度。
  // resizer 3 (inspector): 位于 inspector 和 ai 之间。调整 ai 宽度（反向）或者 inspector 宽度？
  
  // 让我们重新定义策略：
  // Sidebar: 固定宽度，可调。
  // AI Sidebar: 固定宽度，可调。
  // Inspector: 固定宽度，可调。
  // Center: Flex 1 (占据剩余空间)。
  
  // Resizer 1 (data-resize="sidebar"): 调整 sidebar 宽度。
  // Resizer 2 (data-resize="center"): 实际上是调整 Inspector 的左边界。拖动它会改变 Inspector 的宽度。
  // Resizer 3 (data-resize="inspector"): 实际上是调整 AI Sidebar 的左边界。拖动它会改变 AI Sidebar 的宽度。
  
  if (type === 'sidebar') return document.querySelector('.sidebar-panel');
  if (type === 'center') return document.querySelector('.inspector-panel'); // 拖动 center 右边的 resizer，实际上是在调整 inspector 的大小
  if (type === 'inspector') return document.querySelector('.ai-sidebar'); // 拖动 inspector 右边的 resizer，实际上是在调整 ai 的大小
  
  return null;
}

function initResizers() {
  const resizers = document.querySelectorAll('.resizer');
  resizers.forEach(r => r.addEventListener('mousedown', handleMouseDown));
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
  window.addEventListener('beforeunload', savePanelSizes);
}

function teardownResizers() {
  const resizers = document.querySelectorAll('.resizer');
  resizers.forEach(r => r.removeEventListener('mousedown', handleMouseDown));
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  window.removeEventListener('beforeunload', savePanelSizes);
}

function handleMouseDown(e) {
  e.preventDefault();
  isResizing = true;
  currentResizer = e.currentTarget;
  startX = e.clientX;
  const resizeType = currentResizer.getAttribute('data-resize');
  targetPanel = getPanelByType(resizeType);
  if (targetPanel) startWidth = targetPanel.offsetWidth;
  currentResizer.classList.add('active');
  document.body.style.cursor = 'col-resize';
  document.body.style.userSelect = 'none';
}

function handleMouseMove(e) {
  if (!isResizing || !targetPanel || !currentResizer) return;
  e.preventDefault();
  const deltaX = e.clientX - startX;
  const resizeType = currentResizer.getAttribute('data-resize');
  let newWidth = startWidth;
  
  if (resizeType === 'sidebar') {
    // 正向调整
    newWidth = startWidth + deltaX;
  } else if (resizeType === 'center') {
    // 调整 Inspector (在 Center 右边)，拖动向左(delta < 0)应增加 Inspector 宽度
    newWidth = startWidth - deltaX;
  } else if (resizeType === 'inspector') {
    // 调整 AI Sidebar (在 Inspector 右边)，拖动向左(delta < 0)应增加 AI 宽度
    newWidth = startWidth - deltaX;
  }
  
  const cs = getComputedStyle(targetPanel);
  const minWidth = parseInt(cs.minWidth) || 200;
  const maxWidth = parseInt(cs.maxWidth) || 800;
  newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
  targetPanel.style.width = `${newWidth}px`;
}

function handleMouseUp() {
  if (!isResizing) return;
  isResizing = false;
  if (currentResizer) currentResizer.classList.remove('active');
  currentResizer = null;
  targetPanel = null;
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  savePanelSizes();
}

function savePanelSizes() {
  try {
    const sidebar = document.querySelector('.sidebar-panel');
    const inspector = document.querySelector('.inspector-panel');
    const ai = document.querySelector('.ai-sidebar');
    const cfg = {
      sidebarWidth: sidebar?.offsetWidth || undefined,
      inspectorWidth: inspector?.offsetWidth || undefined,
      aiWidth: ai?.offsetWidth || undefined,
    };
    localStorage.setItem('panelSizes_v2', JSON.stringify(cfg));
  } catch {}
}

function loadPanelSizes() {
  try {
    const txt = localStorage.getItem('panelSizes_v2');
    if (!txt) return;
    const cfg = JSON.parse(txt);
    const sidebar = document.querySelector('.sidebar-panel');
    const inspector = document.querySelector('.inspector-panel');
    const ai = document.querySelector('.ai-sidebar');
    
    if (cfg?.sidebarWidth && sidebar) sidebar.style.width = `${cfg.sidebarWidth}px`;
    if (cfg?.inspectorWidth && inspector) inspector.style.width = `${cfg.inspectorWidth}px`;
    if (cfg?.aiWidth && ai) ai.style.width = `${cfg.aiWidth}px`;
  } catch {}
}

async function loadStateFromRoute(currentRoute) {
  const { params, query } = currentRoute;
  const path = params.pathMatch?.join('/') || '';
  if (!path.startsWith('project/')) return;

  const segs = path.split('/');
  if (segs.length < 3 || segs !== 'project' || segs !== 'file') return;

  const projectId = decodeURIComponent(segs || '');
  const fileRaw = segs.slice(3).join('/');
  if (!projectId || !fileRaw) return;

  let fileId = decodeURIComponent(fileRaw);
  if (!/\.story$/i.test(fileId)) fileId = `${fileId}.story`;
  const sceneId = decodeURIComponent(query.scene || '');

  // ensure project exists then switch
  if (projectStore.projects.includes(projectId)) {
    await projectStore.setCurrentProject(projectId);
  } else {
    return; // unknown project; keep default behavior
  }

  // ensure file tree is ready then select file and load story
  try {
    await fileStore.setCurrentFile(projectId, fileId);
    if (sceneId) {
      // wait story loaded then select scene
      const scene = (sceneStore.scriptData || []).find(s => s.scene === sceneId);
      if (scene) sceneStore.selectScene(scene);
    }
  } catch (e) {
    console.warn('URL 恢复失败:', e);
  }
}

onMounted(async () => {
  try {
    const user = await getUserInfo();
    username.value = user?.username || '';
    await projectStore.loadProjects();
    await loadStateFromRoute(route);
  } catch (e) {
    router.push('/login');
  }
  
  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
  
  loadPanelSizes();
  initResizers();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  bus.off('saved', showSaveHint);
  bus.off('scene-selected', sceneSelectedHandler);
  teardownResizers();
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

watch([() => fileStore.selectedFile, () => sceneStore.currentScene], () => {
  const project = projectStore.currentProject;
  const file = fileStore.selectedFile;
  const scene = sceneStore.currentScene;

  if (project && file) {
    const filePath = file.path || file.name;
    const encodedProject = encodeURIComponent(project);
    const encodedFilePath = filePath.split('/').map(encodeURIComponent).join('/');
    
    let newPath = `/project/${encodedProject}/file/${encodedFilePath}`;
    const newQuery = {};
    if (scene) {
      newQuery.scene = scene.scene;
    }

    // Only push to router if the path or query is different
    if (route.path !== newPath || JSON.stringify(route.query) !== JSON.stringify(newQuery)) {
      router.push({ path: newPath, query: newQuery });
    }
  }
}, { deep: true });

onBeforeRouteUpdate(async (to, from) => {
  // React to route changes, e.g., user navigating with back/forward buttons
  if (to.path !== from.path || to.query !== from.query) {
    await loadStateFromRoute(to);
  }
});

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