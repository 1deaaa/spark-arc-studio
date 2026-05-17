<template>
  <header class="app-header no-select" @mousedown="onHeaderMousedown">
    <div class="header-left">
      <n-tooltip trigger="hover">
        <template #trigger>
          <a class="logo" :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener">
            <AppBrand :size="28" :alt="t('components.headerToolbar.backHome')" />
          </a>
        </template>
        {{ t('components.headerToolbar.backHome') }}
      </n-tooltip>
      <ProjectSelector />
    </div>
    <div class="header-center header-buttons">
      <div class="dock-bar" ref="dockBarRef"
        @mouseenter="onDockEnter" @mousemove="onDockMove" @mouseleave="onDockLeave">
        <n-dropdown trigger="click" :options="projectOptions" @select="handleProjectAction">
          <span class="tooltip-dropdown-trigger">
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button class="header-action-btn" type="primary" strong>
                  <template #icon>
                    <n-icon :component="FolderOpen" />
                  </template>
                  {{ t('components.headerToolbar.project') }}
                </n-button>
              </template>
              {{ t('components.headerToolbar.projectActionTitle') }}
            </n-tooltip>
          </span>
        </n-dropdown>

        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button class="header-action-btn" @click="$emit('open-version-manager')" type="primary" strong>
              <template #icon>
                <n-icon :component="Share2" />
              </template>
              {{ t('components.headerToolbar.publish') }}
            </n-button>
          </template>
          {{ t('components.headerToolbar.publishTitle') }}
        </n-tooltip>

        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button class="header-action-btn" @click="quickPreview" :loading="previewing" type="primary" strong>
              <template #icon>
                <n-icon :component="Play" />
              </template>
              {{ t('components.headerToolbar.quickPreview') }}
            </n-button>
          </template>
          {{ t('components.headerToolbar.quickPreviewTitle') }}
        </n-tooltip>

        <n-dropdown trigger="click" :options="fileOptions" @select="handleFileAction">
          <span class="tooltip-dropdown-trigger">
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button class="header-action-btn" type="primary" strong>
                  <template #icon>
                    <n-icon :component="FolderOpen" />
                  </template>
                  {{ t('components.headerToolbar.file') }}
                </n-button>
              </template>
              {{ t('components.headerToolbar.fileActionTitle') }}
            </n-tooltip>
          </span>
        </n-dropdown>

        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button class="header-action-btn" @click="saveCurrentFile" type="primary" strong>
              <template #icon>
                <n-icon :component="saveSucceeded ? CircleCheck : Save" />
              </template>
              {{ saveButtonText }}
            </n-button>
          </template>
          {{ t('components.headerToolbar.saveShortcut') }}
        </n-tooltip>
      </div>
      <input type="file" ref="importFileInput" @change="onFileChange" accept=".arc" style="display:none;">
      <input type="file" ref="importSparkInput" @change="onSparkFileChange" accept=".spark" style="display:none;">
    </div>
    <div class="header-right">
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button
            text
            style="font-size: var(--spark-fs-h1); margin-right: 8px;"
            @click="toggleAutoSave(!autoSaveEnabled)"
          >
            <template #icon>
              <n-icon
                :component="autoSaveEnabled ? SaveAll : SaveOff"
                :color="autoSaveEnabled ? 'var(--n-primary-color)' : '#e88080'"
                :style="{
                  transition: 'all 0.3s ease'
                }"
              />
            </template>
          </n-button>
        </template>
        {{ autoSaveEnabled ? t('components.headerToolbar.autoSaveDisable') : t('components.headerToolbar.autoSaveEnable') }}
      </n-tooltip>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button text style="font-size: var(--spark-fs-h2); margin-left: 8px;" @click="handleToggleFullscreen">
            <n-icon :component="isFullscreen ? Minimize2 : Maximize2" />
          </n-button>
        </template>
        {{ isFullscreen ? t('components.headerToolbar.exitFullscreen') : t('components.headerToolbar.fullscreen') }}
      </n-tooltip>
      <n-dropdown trigger="hover" :options="themeOptions" @select="handleThemeChange">
        <span class="tooltip-dropdown-trigger">
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button text style="font-size: var(--spark-fs-h1); margin-left: 8px;">
                <n-icon :component="currentThemeIcon" />
              </n-button>
            </template>
            {{ t('components.headerToolbar.themeSwitch') }}
          </n-tooltip>
        </span>
      </n-dropdown>
      <div class="user-info">
        <n-text>{{ username || t('components.headerToolbar.loading') }}</n-text>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button @click="handleLogout" text>
              <template #icon>
                <n-icon :component="LogOut" />
              </template>
              {{ t('components.headerToolbar.logout') }}
            </n-button>
          </template>
          {{ t('components.headerToolbar.logoutTitle') }}
        </n-tooltip>
      </div>
      <!-- Tauri 桌面端窗口控制按钮 -->
      <WindowControls variant="header" />
    </div>
  </header>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed, h } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NText, NDropdown, NTooltip } from 'naive-ui';
import { Archive, CircleCheck, CloudDownload, CloudUpload, FolderOpen, Laptop, LogOut, Maximize2, Minimize2, Moon, PaintBucket, Play, Save, SaveAll, SaveOff, Share2, Sun } from 'lucide-vue-next';
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
import AppBrand from '@/components/share/AppBrand.vue';
import { SPARKARC_GITHUB_URL } from '@/config';
import { autoSaveEnabled, setAutoSaveEnabled } from '@/utils/autoSaveState';
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
});

const { t } = useI18n();

const emit = defineEmits(['open-settings', 'auto-save-changed', 'logout', 'open-version-manager']);

const saveSucceeded = ref(false);
const saveButtonText = computed(() => saveSucceeded.value ? t('components.headerToolbar.saveSuccess') : t('views.common.save'));
const previewing = ref(false);

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
  { label: t('components.headerToolbar.importArc'), key: 'import', icon: () => h(NIcon, null, { default: () => h(CloudDownload) }) },
  { label: t('components.headerToolbar.exportArc'), key: 'export_arc', icon: () => h(NIcon, null, { default: () => h(CloudUpload) }) },
]);

function handleFileAction(key) {
  if (key === 'import') triggerFileImport();
  else if (key === 'export_arc') exportArc();
}

const projectOptions = computed(() => [
  { label: t('components.headerToolbar.exportProject'), key: 'export_project', icon: () => h(NIcon, null, { default: () => h(Archive) }) },
  { label: t('components.headerToolbar.importProject'), key: 'import_project', icon: () => h(NIcon, null, { default: () => h(PaintBucket) }) },
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
  { label: t('components.headerToolbar.themeLight'), key: 'light', icon: () => h(NIcon, null, { default: () => h(Sun) }) },
  { label: t('components.headerToolbar.themeDark'), key: 'dark', icon: () => h(NIcon, null, { default: () => h(Moon) }) },
  { label: t('components.headerToolbar.themeSystem'), key: 'system', icon: () => h(NIcon, null, { default: () => h(Laptop) }) },
]);

const handleThemeChange = (key) => {
  themeStore.setThemeMode(key);
};

const currentThemeIcon = computed(() => {
  switch (themeStore.themeMode) {
    case 'light': return Sun;
    case 'dark': return Moon;
    default: return Laptop;
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
    if (autoSaveEnabled.value) localStorage.setItem('lastSavedState', JSON.stringify(sceneStore.scriptData));
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
  setAutoSaveEnabled(newVal);
  // 仅关闭时提示（开启是默认行为，无需提示）
  if (!newVal) {
    bus.emit('toast', { type: 'warning', message: t('components.headerToolbar.autoSaveOff') });
  }
  emit('auto-save-changed', newVal);
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

.tooltip-dropdown-trigger {
  display: inline-flex;
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

.logo {
  display: flex;
  align-items: center;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}
</style>
