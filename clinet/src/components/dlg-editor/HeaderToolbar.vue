<template>
  <header class="app-header no-select">
    <div class="header-left">
      <div class="logo" title="返回首页">CatGPTale</div>
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
        <n-button @click="triggerFileImport" title="从本地导入 .story 文件">
          <template #icon>
            <n-icon :component="CloudDownloadOutline" />
          </template>
          导入
        </n-button>
        <input type="file" ref="importFileInput" @change="onFileChange" accept=".story" style="display:none;">
        <n-button @click="exportScript" title="导出当前脚本">
          <template #icon>
            <n-icon :component="CloudUploadOutline" />
          </template>
          导出
        </n-button>
        <n-button @click="saveCurrentFile" type="primary" title="保存 (Ctrl+S)" strong>
          <template #icon>
            <n-icon :component="SaveOutline" />
          </template>
          保存
        </n-button>
        <n-button @click="$emit('open-settings')" title="编辑世界观 / 角色设定">
          <template #icon>
            <n-icon :component="CreateOutline" />
          </template>
          设定
        </n-button>
        <n-button @click="openBlueprint" title="打开剧情蓝图">
          <template #icon>
            <n-icon :component="StatsChartOutline" />
          </template>
          蓝图
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
import { onBeforeUnmount, onMounted, ref, computed } from 'vue';
import { NButton, NIcon, NSpace, NSwitch, NText } from 'naive-ui';
import { GridOutline, CloudDownloadOutline, CloudUploadOutline, SaveOutline, CreateOutline, StatsChartOutline, CheckmarkCircleOutline, CloseCircleOutline, LogOutOutline } from '@vicons/ionicons5';
import bus from '@/eventBus';
import ProjectSelector from '../user/ProjectSelector.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory, uploadStory, logout as apiLogout } from '@/services/api';

const props = defineProps({
  username: { type: String, default: '' },
  autoSaveEnabled: { type: Boolean, default: true },
});

const emit = defineEmits(['open-settings', 'auto-save-changed', 'logout']);

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

function exportScript() {
  const data = sceneStore.scriptData;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  // 优先使用选中文件的 name，退回到 path 的最后一段，再退回默认名
  let base = fileStore.selectedFile?.name
    || (currentFilePath.value ? String(currentFilePath.value).split(/[\\/]/).pop() : '')
    || 'dialogue_script';
  // 清洗 Windows 非法字符 \ / : * ? " < > | 以及首尾空格和点
  base = base.replace(/[\\/:*?"<>|]/g, '_').replace(/^\s+|\s+$/g, '').replace(/^\.+|\.+$/g, '');
  // 确保只有一个 .story 后缀
  if (!base.toLowerCase().endsWith('.story')) base += '.story';
  a.download = base;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function saveCurrentFile() {
  if (!currentFilePath.value) {
    bus.emit('toast', { type: 'error', message: '请先在左侧选择一个 .story 文件' });
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
</script>

<style scoped>
.no-select, .no-select * {
  -webkit-user-select: none;
  -ms-user-select: none;
  user-select: none;
}
</style>
