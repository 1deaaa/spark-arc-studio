<template>
  <LoginPage v-if="showLogin" @logged-in="onLoggedIn" />
  <div v-else class="container">
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
        <AiSettingsPanel v-else :visible="true" />
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
</template>

<script setup>
import HeaderToolbar from './components/dlg-editor/HeaderToolbar.vue';
import Toast from './components/share/Toast.vue';
import ModalHost from './components/share/ModalHost.vue';
import ContextPrompt from './components/share/ContextPrompt.vue';
import FileTree from './components/file-explorer/FileTree.vue';
import SceneList from './components/dlg-editor/SceneList.vue';
import DialogueTree from './components/dlg-editor/DialogueTree.vue';
import NodeEditor from './components/dlg-editor/NodeEditor.vue';
import AiPanel from './components/dlg-editor/AiPanel.vue';
import LorebookEditor from './components/lorebook/LorebookEditor.vue';
import AiSettingsPanel from './components/lorebook/AiSettingsPanel.vue';
import LoginPage from './components/user/LoginPage.vue';
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import bus from './eventBus';
import { useSceneStore } from './components/stores/sceneStore';
import { useProjectStore } from './components/stores/projectStore';
import { useFileStore } from './components/stores/fileStore';
import { getUserInfo } from './services/api';

const settingsVisible = ref(false);
const sceneStore = useSceneStore();
const showLogin = ref(false);
const username = ref('');
const autoSaveEnabled = ref(localStorage.getItem('autoSaveEnabled') === 'true');
const saveHintVisible = ref(false);
const toastRef = ref(null);
const modalRef = ref(null);
const ctxPromptRef = ref(null);

function showSaveHint() {
  saveHintVisible.value = true;
  clearTimeout(showSaveHint._t);
  showSaveHint._t = setTimeout(() => saveHintVisible.value = false, 1200);
}

function openSettings() { settingsVisible.value = true; }

function onKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
  // 转发到 HeaderToolbar 统一处理保存
  bus.emit('save-request');
  }
}

// 当选中场景时，确保关闭设定面板，回到对话树视图
function sceneSelectedHandler() { settingsVisible.value = false; }

// 兜底：只要当前场景发生切换，就自动关闭设定面板
watch(() => sceneStore.currentScene, () => {
  settingsVisible.value = false;
});

// 分隔条拖拽与持久化逻辑（合并到单一 <script setup> 中）
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

onMounted(async () => {
  try {
    const user = await getUserInfo();
    username.value = user?.username || '';
  } catch (e) {
    // 未认证 -> 显示登录页
    showLogin.value = true;
    return;
  }
  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
  // 统一 Toast
  const onToast = (p) => {
    const { message, type = 'info', duration } = p || {};
    toastRef.value?.show?.(message || '', type, duration);
  };
  // 存引用以便 off
  onMounted.onToast = onToast;
  bus.on('toast', onToast);
  // 统一 confirm/prompt
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
  // 恢复面板宽度并初始化分隔条拖拽
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
  teardownResizers();
});

function onLoggedIn(user) {
  username.value = user?.username || '';
  showLogin.value = false;
  // 初始化布局与监听
  loadPanelSizes();
  initResizers();
  // 补注册事件监听（首次进入为登录页时，onMounted提前return，需在此处添加）
  window.addEventListener('keydown', onKeydown);
  bus.on('saved', showSaveHint);
  bus.on('scene-selected', sceneSelectedHandler);
}

function onLogout() {
  // 切换到登录界面，并移除当前应用相关监听
  showLogin.value = true;
  username.value = '';
  window.removeEventListener('keydown', onKeydown);
  bus.off('saved', showSaveHint);
  bus.off('scene-selected', sceneSelectedHandler);
  if (onMounted.onToast) bus.off('toast', onMounted.onToast);
  if (onMounted.onConfirm) bus.off('confirm', onMounted.onConfirm);
  if (onMounted.onPrompt) bus.off('prompt', onMounted.onPrompt);
}
</script>

<style>
/* 我们将继续使用全局的 style.css，所以这里不需要 scoped 样式 */
</style>
<style>
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

/* 进入/离开过渡动画：淡入 + 轻微上移 + 缩放 */
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
