<template>
  <!-- 鉴权未完成前不渲染任何主要内容，避免登录页闪烁 -->
  <LoginPage v-if="isAuthReady && showLogin" @logged-in="onLoggedIn" />
  <div v-else-if="isAuthReady" class="container">
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
  <Toast ref="toastRef" />
  <ModalHost ref="modalRef" />
  <ContextPrompt ref="ctxPromptRef" />
  
  <div v-if="blueprintVisible" class="blueprint-modal">
    <div class="blueprint-modal-content">
      <StoryBlueprint />
      <button @click="closeBlueprint" class="close-blueprint-btn">关闭</button>
    </div>
  </div>
</template>

<script setup>
import HeaderToolbar from './components/dlg-editor/HeaderToolbar.vue';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import ContextPrompt from './components/share/ContextPrompt.vue';
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
import bus from './eventBus';
import { useSceneStore } from './components/stores/sceneStore';
import { useProjectStore } from './components/stores/projectStore';
import { useFileStore } from './components/stores/fileStore';
import { getUserInfo } from './services/api';

const settingsVisible = ref(false);
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const isAuthReady = ref(false);
const showLogin = ref(true);
const username = ref('');
const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
const saveHintVisible = ref(false);
const toastRef = ref(null);
const modalRef = ref(null);
const ctxPromptRef = ref(null);
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

async function restoreStateFromUrl() {
  const hash = window.location.hash.slice(1); // like: /project/<project>/file/<file>[?scene=xxx]
  if (!hash.startsWith('/project/')) return;

  // split path and query
  const [rawPath, rawQuery] = hash.split('?');
  const query = rawQuery ? new URLSearchParams(rawQuery) : null;

  // path segments: ["", "project", projectId, "file", ...fileSegs]
  const segs = rawPath.split('/').filter(Boolean);
  if (segs.length < 4 || segs[0] !== 'project' || segs[2] !== 'file') return;

  const projectId = decodeURIComponent(segs[1] || '');
  const fileRaw = segs.slice(3).join('/');
  if (!projectId || !fileRaw) return;
  let fileId = decodeURIComponent(fileRaw);
  // tolerate URL without .story suffix
  if (!/\.story$/i.test(fileId)) fileId = `${fileId}.story`;
  const sceneId = query ? decodeURIComponent(query.get('scene') || '') : '';

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
    showLogin.value = false;
    await projectStore.loadProjects();
    await restoreStateFromUrl();
  } catch (e) {
    // 即使认证失败，也要尝试恢复URL状态，以便在登录后能导航到正确的位置
    showLogin.value = true;
    // 保存当前URL，以便登录后能导航到正确的位置
    const hash = window.location.hash.slice(1);
    if (hash.startsWith('/project/')) {
      localStorage.setItem('postLoginUrl', hash);
    }
  } finally {
    // 鉴权流程结束后再渲染，避免闪烁
    isAuthReady.value = true;
  }
  
  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
  bus.on('open-blueprint', openBlueprint);
  
  const onToast = (p) => {
    const { message, type = 'info', duration } = p || {};
    toastRef.value?.show?.(message || '', type, duration);
  };
  onMounted.onToast = onToast;
  bus.on('toast', onToast);
  
  const onConfirm = async (p) => {
    const { x, y } = p || {};
    let res;
    if (typeof x === 'number' && typeof y === 'number' && ctxPromptRef.value) {
      res = await ctxPromptRef.value.open({ mode: 'confirm', ...p });
    } else {
      res = await modalRef.value?.open?.({ mode: 'confirm', ...p });
    }
    p?.resolve?.(res === true);
  };
  const onPrompt = async (p) => {
    const { x, y } = p || {};
    let res;
    if (typeof x === 'number' && typeof y === 'number' && ctxPromptRef.value) {
      res = await ctxPromptRef.value.open({ mode: 'prompt', ...p });
    } else {
      res = await modalRef.value?.open?.({ mode: 'prompt', ...p });
    }
    p?.resolve?.(res ?? null);
  };
  onMounted.onConfirm = onConfirm; onMounted.onPrompt = onPrompt;
  bus.on('confirm', onConfirm);
  bus.on('prompt', onPrompt);
  
  loadPanelSizes();
  initResizers();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
  bus.off('saved', showSaveHint);
  bus.off('scene-selected', sceneSelectedHandler);
  if (onMounted.onToast) bus.off('toast', onMounted.onToast);
  if (onMounted.onConfirm) bus.off('confirm', onMounted.onConfirm);
  if (onMounted.onPrompt) bus.off('prompt', onMounted.onPrompt);
  bus.off('open-blueprint', openBlueprint);
  teardownResizers();
});

async function onLoggedIn(user) {
  username.value = user?.username || '';
  showLogin.value = false;
  isAuthReady.value = true;
  
  await projectStore.loadProjects();
  // 首先尝试使用登录后导航的URL
  const postLoginUrl = localStorage.getItem('postLoginUrl');
  if (postLoginUrl) {
    localStorage.removeItem('postLoginUrl');
    window.location.hash = '#' + postLoginUrl;
  } else {
    // 如果没有登录后导航的URL，则使用最后访问的URL
    const lastUrl = localStorage.getItem('lastUrl');
    if (lastUrl) {
      window.location.hash = lastUrl;
    }
  }
  
  await restoreStateFromUrl();

  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
  bus.on('open-blueprint', openBlueprint);
  loadPanelSizes();
  initResizers();
}

function onLogout() {
  showLogin.value = true;
  username.value = '';
  // 不需要移除 token，因为后端使用 Cookie 进行认证
  window.location.hash = '';
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
    // 使用完整路径，保持目录层级；确保编码
    const filePath = file.path || file.name;
    const encodedProject = encodeURIComponent(project);
    const encodedFilePath = filePath.split('/').map(encodeURIComponent).join('/');
    let hash = `#/project/${encodedProject}/file/${encodedFilePath}`;
    if (scene) {
      hash += `?scene=${encodeURIComponent(scene.scene)}`;
    }
    if (window.location.hash !== hash) {
      window.location.hash = hash;
    }
    localStorage.setItem('lastUrl', hash);
  }
}, { deep: true });

</script>

<style>
/* Styles from before */
.settings-right-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.settings-right-panel > * {
  border-bottom: 1px solid #eee;
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
.close-blueprint-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 8px 12px;
  background-color: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
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