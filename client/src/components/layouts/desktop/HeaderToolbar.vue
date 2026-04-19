<template>
  <header class="app-header no-select" @mousedown="onHeaderMousedown">
    <div class="header-left">
      <div class="logo" :title="t('components.headerToolbar.backHome')">
        SparkArc
      </div>
      <ProjectSelector />
    </div>
    <div class="header-center header-buttons">
      <div class="dock-bar" ref="dockBarRef"
        @mouseenter="onDockEnter" @mousemove="onDockMove" @mouseleave="onDockLeave">
        <n-dropdown trigger="click" :options="projectOptions" @select="handleProjectAction">
          <n-button class="header-action-btn" :title="t('components.headerToolbar.projectActionTitle')" type="primary" strong>
            <template #icon>
              <n-icon :component="FolderOpenOutline" />
            </template>
            {{ t('components.headerToolbar.project') }}
          </n-button>
        </n-dropdown>

        <n-button class="header-action-btn" @click="$emit('open-version-manager')" :title="t('components.headerToolbar.publishTitle')" type="primary" strong>
          <template #icon>
            <n-icon :component="ShareSocialOutline" />
          </template>
          {{ t('components.headerToolbar.publish') }}
        </n-button>

        <n-button class="header-action-btn" @click="quickPreview" :loading="previewing" :title="t('components.headerToolbar.quickPreviewTitle')" type="primary" strong>
          <template #icon>
            <n-icon :component="PlayOutline" />
          </template>
          {{ t('components.headerToolbar.quickPreview') }}
        </n-button>

        <n-dropdown trigger="click" :options="fileOptions" @select="handleFileAction">
          <n-button class="header-action-btn" :title="t('components.headerToolbar.fileActionTitle')" type="primary" strong>
            <template #icon>
              <n-icon :component="FolderOpenOutline" />
            </template>
            {{ t('components.headerToolbar.file') }}
          </n-button>
        </n-dropdown>

        <n-button class="header-action-btn" @click="saveCurrentFile" type="primary" :title="t('components.headerToolbar.saveShortcut')" strong>
          <template #icon>
            <n-icon :component="saveSucceeded ? CheckmarkCircleOutline : SaveOutline" />
          </template>
          {{ saveButtonText }}
        </n-button>
      </div>
      <input type="file" ref="importFileInput" @change="onFileChange" accept=".arc" style="display:none;">
      <input type="file" ref="importSparkInput" @change="onSparkFileChange" accept=".spark" style="display:none;">
    </div>
    <div class="header-right">
      <n-button 
        text 
        style="font-size: var(--spark-fs-h1); margin-right: 8px;" 
        :title="autoSaveEnabled ? t('components.headerToolbar.autoSaveDisable') : t('components.headerToolbar.autoSaveEnable')" 
        @click="toggleAutoSave(!autoSaveEnabled)"
      >
        <template #icon>
          <n-icon 
            :component="SyncOutline" 
            :color="autoSaveEnabled ? 'var(--n-primary-color)' : '#e88080'" 
            :style="{ 
              opacity: autoSaveEnabled ? 1 : 1, 
              transition: 'all 0.3s ease',
              transform: autoSaveEnabled ? 'rotate(0deg)' : 'rotate(-45deg)'
            }"
          />
        </template>
      </n-button>
      <n-button text style="font-size: var(--spark-fs-h2); margin-left: 8px;" :title="isFullscreen ? t('components.headerToolbar.exitFullscreen') : t('components.headerToolbar.fullscreen')" @click="handleToggleFullscreen">
        <n-icon :component="isFullscreen ? ContractOutline : ExpandOutline" />
      </n-button>
      <n-dropdown trigger="hover" :options="themeOptions" @select="handleThemeChange">
        <n-button text style="font-size: var(--spark-fs-h1); margin-left: 8px;" :title="t('components.headerToolbar.themeSwitch')">
          <n-icon :component="currentThemeIcon" />
        </n-button>
      </n-dropdown>
      <div class="user-info">
        <n-text>{{ username || t('components.headerToolbar.loading') }}</n-text>
        <n-button @click="handleLogout" text :title="t('components.headerToolbar.logoutTitle')">
          <template #icon>
            <n-icon :component="LogOutOutline" />
          </template>
          {{ t('components.headerToolbar.logout') }}
        </n-button>
      </div>
      <!-- Tauri 桌面端窗口控制按钮 -->
      <WindowControls variant="header" />
    </div>
  </header>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed, h } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NText, NDropdown } from 'naive-ui';
import { CloudDownloadOutline, CloudUploadOutline, SaveOutline, CheckmarkCircleOutline, LogOutOutline, SunnyOutline, MoonOutline, LaptopOutline, FolderOpenOutline, ShareSocialOutline, ExpandOutline, ContractOutline, SyncOutline, PlayOutline, ArchiveOutline, ColorFillOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import ProjectSelector from '../../user/ProjectSelector.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useThemeStore } from '@/components/stores/themeStore';
import { saveStory, uploadStory, logout as apiLogout, fetchWithAuth } from '@/services/api';
import { exportProjectToSQLite, exportProjectAsSpark, importProjectFromSpark } from '@/services/projectService';
import { useFullscreen } from '@/composables/useFullscreen';
import { useWindowControls } from '@/composables/useWindowControls';
import { useDockMagnify } from '@/composables/useDockMagnify';
import WindowControls from './WindowControls.vue';

const { startDragging, isTauriDesktop: showWinControls } = useWindowControls();

/** 仅在空白区域触发窗口拖拽，按钮/输入等交互元素不触发 */
function onHeaderMousedown(e) {
  if (!showWinControls.value) return;
  const tag = e.target.tagName.toLowerCase();
  const interactive = ['button', 'input', 'select', 'textarea', 'a', 'svg', 'path'];
  if (interactive.includes(tag) || e.target.closest('button, a, input, .n-button, .n-switch, .n-dropdown, .window-controls, .header-buttons')) return;
  startDragging();
}

/** ── macOS Dock 放大推开效果（composable） ── */
const { dockRef: dockBarRef, onDockEnter, onDockMove, onDockLeave } = useDockMagnify();

const props = defineProps({
  username: { type: String, default: '' },
  autoSaveEnabled: { type: Boolean, default: true },
});

const { t } = useI18n();

const emit = defineEmits(['open-settings', 'auto-save-changed', 'logout', 'open-version-manager']);

const saveSucceeded = ref(false);
const saveButtonText = computed(() => saveSucceeded.value ? t('components.headerToolbar.saveSuccess') : t('views.common.save'));
const previewing = ref(false);

// 本地响应式状态用于 switch
const autoSaveEnabled = ref(props.autoSaveEnabled);

const importFileInput = ref(null);
function triggerFileImport() { importFileInput.value?.click(); }
function onFileChange(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  handleFileSelected(file);
  e.target.value = '';
}

const importSparkInput = ref(null);
function triggerSparkImport() { importSparkInput.value?.click(); }
function onSparkFileChange(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  handleSparkImport(file);
  e.target.value = '';
}

// stores
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const themeStore = useThemeStore();
const { isFullscreen, preferred, requestFullscreen, toggleFullscreen } = useFullscreen();

const fileOptions = computed(() => [
  { label: t('components.headerToolbar.importArc'), key: 'import', icon: () => h(NIcon, null, { default: () => h(CloudDownloadOutline) }) },
  { label: t('components.headerToolbar.exportArc'), key: 'export_arc', icon: () => h(NIcon, null, { default: () => h(CloudUploadOutline) }) },
]);

function handleFileAction(key) {
  if (key === 'import') triggerFileImport();
  else if (key === 'export_arc') exportArc();
}

const projectOptions = computed(() => [
  { label: t('components.headerToolbar.exportProject'), key: 'export_project', icon: () => h(NIcon, null, { default: () => h(ArchiveOutline) }) },
  { label: t('components.headerToolbar.importProject'), key: 'import_project', icon: () => h(NIcon, null, { default: () => h(ColorFillOutline) }) },
]);

const exportingSpark = ref(false);

function handleProjectAction(key) {
  if (key === 'export_project') exportProjectSpark();
  else if (key === 'import_project') triggerSparkImport();
}

async function exportProjectSpark() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'error', message: t('components.headerToolbar.selectProjectFirst') });
    return;
  }
  exportingSpark.value = true;
  try {
    await exportProjectAsSpark(projectStore.currentProject);
    bus.emit('toast', { type: 'success', message: t('components.headerToolbar.exportProjectSuccess') });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { type: 'error', message: `${t('components.headerToolbar.exportProjectFailed')}: ${errorMessage}` });
  } finally {
    exportingSpark.value = false;
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

const themeOptions = computed(() => [
  { label: t('components.headerToolbar.themeLight'), key: 'light', icon: () => h(NIcon, null, { default: () => h(SunnyOutline) }) },
  { label: t('components.headerToolbar.themeDark'), key: 'dark', icon: () => h(NIcon, null, { default: () => h(MoonOutline) }) },
  { label: t('components.headerToolbar.themeSystem'), key: 'system', icon: () => h(NIcon, null, { default: () => h(LaptopOutline) }) },
]);

const handleThemeChange = (key) => {
  themeStore.setThemeMode(key);
};

const currentThemeIcon = computed(() => {
  switch (themeStore.themeMode) {
    case 'light': return SunnyOutline;
    case 'dark': return MoonOutline;
    default: return LaptopOutline;
  }
});

const currentFilePath = computed(() => fileStore.selectedFile?.type === 'story' ? fileStore.selectedFile.path : null);

function showSavedHint() {
  bus.emit('saved');
}

function createNewScene() { sceneStore.createNewScene(); }

async function handleFileSelected(file) {
  try {
    const res = await uploadStory(projectStore.currentProject, file);
    // 刷新文件树并尝试加载上传的文件
    await fileStore.loadFileTree(projectStore.currentProject);
    const uploaded = res.filename;
    const path = typeof uploaded === 'string' ? uploaded : uploaded?.[0] || null;
    if (path) {
      const match = findFileByPath(fileStore.fileTree, path);
      if (match) {
        fileStore.selectedFile = match;
        await sceneStore.loadStory(match.path);
      }
    }
  showSavedHint();
  bus.emit('toast', { type: 'success', message: t('components.headerToolbar.uploadSuccess') });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { type: 'error', message: `${t('components.headerToolbar.uploadFailed')}: ${errorMessage}` });
  }
}

function findFileByPath(tree, path) {
  for (const item of tree) {
    if (item.type === 'story' && item.path === path) return item;
    if (item.children) {
      const r = findFileByPath(item.children, path);
      if (r) return r;
    }
  }
  return null;
}

function exportArc() {
  // Import the serializer
  import('@/services/arcParser').then(({ serializeToArc }) => {
    const data = sceneStore.scriptData;
    const arcText = Array.isArray(data) ? serializeToArc(data) : String(data || '');
    const blob = new Blob([arcText], { type: 'text/plain; charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    // 优先使用选中文件的 name，退回到 path 的最后一段，再退回默认名
    let base = fileStore.selectedFile?.name
      || (currentFilePath.value ? String(currentFilePath.value).split(/[\\/]/).pop() : '')
      || 'dialogue_script';
    // 清洗 Windows 非法字符
    base = base.replace(/[\\/:*?"<>|]/g, '_').replace(/^\s+|\s+$/g, '').replace(/^\.+|\.+$/g, '');
    // 移除原有扩展名并添加 .arc
    base = base.replace(/\.arc$/i, '');
    base += '.arc';
    a.download = base;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
}

function handleToggleFullscreen() {
  toggleFullscreen();
}

async function saveCurrentFile() {
  if (!currentFilePath.value) {
    bus.emit('toast', { type: 'info', message: autoSaveEnabled.value ? t('components.headerToolbar.autoSaveOn') : t('components.headerToolbar.autoSaveOff') });
    return;
  }
  try {
    await saveStory(projectStore.currentProject, currentFilePath.value, sceneStore.scriptData);
    if (props.autoSaveEnabled) localStorage.setItem('lastSavedState', JSON.stringify(sceneStore.scriptData));
    showSavedHint();
    
    // 成功反馈
    saveSucceeded.value = true;
    setTimeout(() => {
      saveSucceeded.value = false;
    }, 2000);

    bus.emit('toast', { type: 'success', message: t('views.common.saveSuccess') });
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { type: 'error', message: `${t('views.common.saveFailed')}: ${errorMessage}` });
    throw e;
  }
}

async function quickPreview() {
  if (!projectStore.currentProject || previewing.value) {
    if (!projectStore.currentProject) {
      bus.emit('toast', { type: 'error', message: t('components.headerToolbar.selectProjectFirst') });
    }
    return;
  }

  try {
    await saveCurrentFile();
  } catch {
    return;
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

function toggleAutoSave(newVal) {
  autoSaveEnabled.value = newVal;
  localStorage.setItem('autoSaveEnabled', String(newVal));
  emit('auto-save-changed', newVal);
  bus.emit('toast', { type: 'info', message: newVal ? t('components.headerToolbar.autoSaveOn') : t('components.headerToolbar.autoSaveOff') });
  if (newVal) saveCurrentFile();
}

async function handleLogout() {
  // 先重置 Pinia 状态，防止旧项目名残留导致新用户登录后被 watch immediate 捕获
  projectStore.resetForLogout();
  try { await apiLogout(); } catch {}
  // 切换到应用内登录视图（SPA），由父组件处理
  emit('logout');
}

function onSaveRequest() { saveCurrentFile(); }
onMounted(() => { bus.on('save-request', onSaveRequest); });
onBeforeUnmount(() => { bus.off('save-request', onSaveRequest); });

onMounted(() => {
  if (preferred.value && !document.fullscreenElement) {
    requestFullscreen();
  }
});

function openBlueprint() {
  bus.emit('open-blueprint');
}

const exporting = ref(false);

async function exportToSQLite() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'error', message: t('components.headerToolbar.selectProjectFirst') });
    return;
  }
  
  exporting.value = true;
  try {
    const result = await exportProjectToSQLite(projectStore.currentProject, true);
    bus.emit('toast', { 
      type: 'success', 
      message: `${t('components.headerToolbar.exportSuccess')}: ${result.chapters}/${result.scenes}`,
      duration: 5000
    });
    console.log('SQLite 数据库路径:', result.db_path);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || 'Unknown error');
    bus.emit('toast', { 
      type: 'error', 
      message: `${t('components.headerToolbar.exportFailed')}: ${errorMessage}`
    });
  } finally {
    exporting.value = false;
  }
}
</script>

<style scoped>
.no-select, .no-select * {
  -webkit-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

/* ── Dock 栏容器：flex 布局，子元素居中 ── */
.dock-bar {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* ── Dock 子元素：默认无 transition（即时跟手），离开时 JS 添加 .dock-leaving 触发回弹 ── */
.dock-bar > :deep(*) {
  transform-origin: center center;
  will-change: transform;
}
.dock-bar > :deep(.dock-leaving) {
  transition: transform 0.22s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}

/* ── 按钮基础 ── */
.header-action-btn {
  height: 32px;
  padding: 0 12px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* ── 点击动画：按下缩放 + 弹性回弹 ── */
.header-action-btn:active {
  transform: scale(0.9) !important;
  transition-duration: 0.08s;
}

/* ── 点击涟漪光晕 ── */
@keyframes dock-click-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(107, 144, 128, 0.45); }
  100% { box-shadow: 0 0 0 10px rgba(107, 144, 128, 0); }
}
.header-action-btn:active {
  animation: dock-click-pulse 0.4s ease-out;
}

.save-icon-stack {
  position: relative;
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #9aa0a6;
}

.save-icon-stack .n-icon {
  position: absolute;
  top: 0;
  left: 0;
}

.save-icon-stack .n-icon:last-child {
  transform: translate(3px, 3px);
  opacity: 0.6;
}

.save-icon-stack.is-active {
  color: var(--n-primary-color);
}
</style>
