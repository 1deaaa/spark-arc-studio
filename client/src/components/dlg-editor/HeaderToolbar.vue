<template>
  <header class="app-header no-select">
    <div class="header-left">
      <div class="logo" title="返回首页">
        <svg class="logo-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path class="spark-draw" d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        SparkArc
      </div>
      <ProjectSelector />
    </div>
    <div class="header-center header-buttons">
      <n-space :size="12">
        <n-button @click="createNewScene" type="primary" title="创建一个新的场景" strong>
          <template #icon>
            <n-icon :component="GridOutline" />
          </template>
          场景
        </n-button>
        
        <n-button @click="saveCurrentFile" type="primary" title="保存 (Ctrl+S)" strong>
          <template #icon>
            <n-icon :component="SaveOutline" />
          </template>
          保存
        </n-button>

        <n-dropdown trigger="click" :options="fileOptions" @select="handleFileAction">
          <n-button title="导入/导出" type="primary" strong>
            <template #icon>
              <n-icon :component="FolderOpenOutline" />
            </template>
            文件
          </n-button>
        </n-dropdown>
        <input type="file" ref="importFileInput" @change="onFileChange" accept=".arc" style="display:none;">

        <n-button @click="exportToSQLite" title="导出 SQLite 数据库" type="primary" strong>
          <template #icon>
            <n-icon :component="ServerOutline" />
          </template>
          导出DB
        </n-button>

        <n-button @click="$emit('open-version-manager')" title="版本管理与分享" type="primary" strong>
          <template #icon>
            <n-icon :component="ShareSocialOutline" />
          </template>
          分享/版本
        </n-button>

        <n-button @click="$emit('open-settings')" title="编辑世界观 / 角色设定" type="primary" strong>
          <template #icon>
            <n-icon :component="CreateOutline" />
          </template>
          设定
        </n-button>
      </n-space>
    </div>
    <div class="header-right">
      <n-switch
        v-model:value="autoSaveEnabled"
        @update:value="toggleAutoSave"
        size="medium"
      >
        <template #checked>
          自动保存
        </template>
        <template #unchecked>
          手动保存
        </template>
        <template #checked-icon>
          <n-icon :component="CheckmarkCircleOutline" />
        </template>
        <template #unchecked-icon>
          <n-icon :component="CloseCircleOutline" />
        </template>
      </n-switch>
      <n-dropdown trigger="hover" :options="themeOptions" @select="handleThemeChange">
        <n-button text style="font-size: 24px; margin-left: 12px;" title="切换主题">
          <n-icon :component="currentThemeIcon" />
        </n-button>
      </n-dropdown>
      <div class="user-info">
        <n-text>{{ username || '加载中...' }}</n-text>
        <n-button @click="handleLogout" text title="登出当前账号">
          <template #icon>
            <n-icon :component="LogOutOutline" />
          </template>
          登出
        </n-button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, computed, h } from 'vue';
import { NButton, NIcon, NSpace, NSwitch, NText, NDropdown } from 'naive-ui';
import { GridOutline, CloudDownloadOutline, CloudUploadOutline, SaveOutline, CreateOutline, StatsChartOutline, CheckmarkCircleOutline, CloseCircleOutline, LogOutOutline, SunnyOutline, MoonOutline, LaptopOutline, ServerOutline, FolderOpenOutline, ShareSocialOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import ProjectSelector from '../user/ProjectSelector.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useThemeStore } from '@/components/stores/themeStore';
import { saveStory, uploadStory, logout as apiLogout, exportProjectToSQLite } from '@/services/api';

const props = defineProps({
  username: { type: String, default: '' },
  autoSaveEnabled: { type: Boolean, default: true },
});

const emit = defineEmits(['open-settings', 'auto-save-changed', 'logout', 'open-version-manager']);

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

// stores
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const themeStore = useThemeStore();

const fileOptions = [
  { label: '导入 (.arc)', key: 'import', icon: () => h(NIcon, null, { default: () => h(CloudDownloadOutline) }) },
  { label: '导出脚本 (.arc)', key: 'export_arc', icon: () => h(NIcon, null, { default: () => h(CloudUploadOutline) }) },
  { label: '导出数据库 (SQLite)', key: 'export_db', icon: () => h(NIcon, null, { default: () => h(ServerOutline) }) },
];

function handleFileAction(key) {
  if (key === 'import') triggerFileImport();
  else if (key === 'export_arc') exportArc();
  else if (key === 'export_db') exportToSQLite();
}

const themeOptions = [
  { label: '亮色模式', key: 'light', icon: () => h(NIcon, null, { default: () => h(SunnyOutline) }) },
  { label: '暗色模式', key: 'dark', icon: () => h(NIcon, null, { default: () => h(MoonOutline) }) },
  { label: '跟随系统', key: 'system', icon: () => h(NIcon, null, { default: () => h(LaptopOutline) }) },
];

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
  bus.emit('toast', { type: 'success', message: '上传成功' });
  } catch (e) {
  bus.emit('toast', { type: 'error', message: `上传失败: ${e.message}` });
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
    const arcText = serializeToArc(data);
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

async function saveCurrentFile() {
  if (!currentFilePath.value) {
    bus.emit('toast', { type: 'error', message: '请先在左侧选择一个 .arc 文件' });
    return;
  }
  try {
    await saveStory(projectStore.currentProject, currentFilePath.value, sceneStore.scriptData);
    if (props.autoSaveEnabled) localStorage.setItem('lastSavedState', JSON.stringify(sceneStore.scriptData));
    showSavedHint();
  bus.emit('toast', { type: 'success', message: '保存成功' });
  } catch (e) {
  bus.emit('toast', { type: 'error', message: `保存失败: ${e.message}` });
  }
}

function toggleAutoSave(newVal) {
  localStorage.setItem('autoSaveEnabled', String(newVal));
  emit('auto-save-changed', newVal);
  if (newVal) saveCurrentFile();
}

async function handleLogout() {
  try { await apiLogout(); } catch {}
  // 切换到应用内登录视图（SPA），由父组件处理
  emit('logout');
}

function onSaveRequest() { saveCurrentFile(); }
onMounted(() => { bus.on('save-request', onSaveRequest); });
onBeforeUnmount(() => { bus.off('save-request', onSaveRequest); });

function openBlueprint() {
  bus.emit('open-blueprint');
}

const exporting = ref(false);

async function exportToSQLite() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'error', message: '请先选择一个项目' });
    return;
  }
  
  exporting.value = true;
  try {
    const result = await exportProjectToSQLite(projectStore.currentProject, true);
    bus.emit('toast', { 
      type: 'success', 
      message: `导出成功！章节: ${result.chapters}，场景: ${result.scenes}`,
      duration: 5000
    });
    console.log('SQLite 数据库路径:', result.db_path);
  } catch (e) {
    bus.emit('toast', { 
      type: 'error', 
      message: `导出失败: ${e.message}` 
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
</style>
