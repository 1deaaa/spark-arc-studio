<template>
  <div class="container">
    <HeaderToolbar
      :username="username"
      :autoSaveEnabled="autoSaveEnabled"
      @open-settings="openSettings"
      @auto-save-changed="(v) => autoSaveEnabled = v"
      @logout="onLogout"
    />

    <main>
      <div class="panel file-panel">
        <h2>文件管理器</h2>
        <FileTree />
      </div>

      <div class="resizer" data-resize="file"></div>

      <div class="panel left-panel">
        <h2>场景列表</h2>
        <SceneList />
      </div>

      <div class="resizer" data-resize="left"></div>

      <div class="panel middle-panel">
        <h2 v-if="!settingsVisible">对话树</h2>
        <h2 v-else>设定编辑</h2>
        <DialogueTree v-if="!settingsVisible" />
        <LorebookEditor v-else :visible="true" @close="settingsVisible = false" />
      </div>

      <div class="resizer" data-resize="middle"></div>

      <div class="panel right-panel">
        <AiPanel v-if="!settingsVisible" />
        <div v-else class="settings-right-panel">
          <AiSettingsPanel :visible="true" />
          <CharacterGeneratorPanel :visible="true" />
        </div>
        <NodeEditor v-if="!settingsVisible" />
      </div>
  
      <!-- 右下角绿色提示（带过渡动画） -->
      <transition name="save-hint">
        <div v-show="saveHintVisible" class="save-hint">已自动保存</div>
      </transition>
    </main>
  </div>
  
  <div v-if="blueprintVisible" class="blueprint-modal">
    <div class="blueprint-modal-content">
      <StoryBlueprint :projectId="projectStore.currentProject" @close="closeBlueprint" />
    </div>
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
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router';
import bus from './eventBus';
import { useSceneStore } from './components/stores/sceneStore';
import { useProjectStore } from './components/stores/projectStore';
import { useFileStore } from './components/stores/fileStore';
import { getUserInfo } from './services/api';

const route = useRoute();
const router = useRouter();

const settingsVisible = ref(false);
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const username = ref('');
const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
const saveHintVisible = ref(false);
const blueprintVisible = ref(false);

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
  blueprintVisible.value = false;
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
  if (type === 'file') return document.querySelector('.file-panel');
  if (type === 'left') return document.querySelector('.left-panel');
  if (type === 'middle') return document.querySelector('.right-panel');
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
  if (resizeType === 'file' || resizeType === 'left') {
    newWidth = startWidth + deltaX;
  } else if (resizeType === 'middle') {
    newWidth = startWidth - deltaX;
  }
  const cs = getComputedStyle(targetPanel);
  const minWidth = parseInt(cs.minWidth) || 100;
  const maxWidth = parseInt(cs.maxWidth) || 1000;
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
    const filePanel = document.querySelector('.file-panel');
    const leftPanel = document.querySelector('.left-panel');
    const rightPanel = document.querySelector('.right-panel');
    const cfg = {
      fileWidth: filePanel?.offsetWidth || undefined,
      leftWidth: leftPanel?.offsetWidth || undefined,
      rightWidth: rightPanel?.offsetWidth || undefined,
    };
    localStorage.setItem('panelSizes', JSON.stringify(cfg));
  } catch {}
}

function loadPanelSizes() {
  try {
    const txt = localStorage.getItem('panelSizes');
    if (!txt) return;
    const cfg = JSON.parse(txt);
    const filePanel = document.querySelector('.file-panel');
    const leftPanel = document.querySelector('.left-panel');
    const rightPanel = document.querySelector('.right-panel');
    if (cfg?.fileWidth && filePanel) filePanel.style.width = `${cfg.fileWidth}px`;
    if (cfg?.leftWidth && leftPanel) leftPanel.style.width = `${cfg.leftWidth}px`;
    if (cfg?.rightWidth && rightPanel) rightPanel.style.width = `${cfg.rightWidth}px`;
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
  bus.on('open-blueprint', openBlueprint);
  
  
  loadPanelSizes();
  initResizers();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  bus.off('saved', showSaveHint);
  bus.off('scene-selected', sceneSelectedHandler);
  bus.off('open-blueprint', openBlueprint);
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

function openBlueprint() {
  blueprintVisible.value = true;
}

function closeBlueprint() {
  blueprintVisible.value = false;
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
.blueprint-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  opacity: 0;
  animation: fadeIn 0.3s forwards;
}
@keyframes fadeIn {
  to {
    opacity: 1;
  }
}
.blueprint-modal-content {
  width: 100vw;
  height: 100vh;
  background-color: white;
  border-radius: 0;
  padding: 0;
  box-shadow: none;
  position: relative;
  transform: scale(0.7);
  animation: scaleUp 0.3s forwards;
}
@keyframes scaleUp {
  to {
    transform: scale(1);
  }
}
.save-hint {
  position: fixed;
  right: 16px;
  bottom: 16px;
  background: #27ae60;
  color: #fff;
  padding: 8px 12px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
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
</style>