<template>
  <div class="production-mobile">
    <GlobalLoading scope="production" />
    <div class="mobile-section">
      <h3 class="section-title">
        <n-icon :component="CreateOutline" />
        剧本创作
      </h3>
      <p class="section-desc">面向移动端的轻量剧本生成与场景管理</p>
    </div>

    <n-spin :show="loading">
      <!-- 文件与场景选择 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="DocumentTextOutline" size="18" />
          <span>文件与场景</span>
        </div>
        <n-select
          v-model:value="selectedFilePath"
          :options="storyOptions"
          placeholder="选择故事文件"
          size="small"
          clearable
          @update:value="handleFileChange"
        />
        <div class="scene-row">
          <n-select
            v-model:value="selectedSceneName"
            :options="sceneOptions"
            placeholder="选择场景"
            size="small"
            clearable
            :disabled="sceneOptions.length === 0"
            @update:value="handleSceneChange"
          />
          <n-button size="small" secondary @click="createScene" :disabled="!selectedFilePath">新建场景</n-button>
        </div>
        <div class="small-hint">先选择文件，再选择或新建场景</div>
      </div>

      <!-- 场景信息 -->
      <div class="flow-section" v-if="currentScene">
        <div class="section-header">
          <n-icon :component="ReaderOutline" size="18" />
          <span>场景信息</span>
        </div>
        <n-input v-model:value="sceneTitle" placeholder="场景名称" />
        <n-input
          v-model:value="sceneIntro"
          type="textarea"
          placeholder="场景简介 / 走向"
          :autosize="{ minRows: 2, maxRows: 5 }"
        />
        <n-input
          v-model:value="sceneGuide"
          type="textarea"
          placeholder="导演意图（可选）"
          :autosize="{ minRows: 2, maxRows: 5 }"
        />
        <n-button type="primary" secondary block size="small" @click="saveSceneMeta">保存场景信息</n-button>
      </div>

      <!-- 场景生成 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="SparklesOutline" size="18" />
          <span>场景生成</span>
        </div>
        <div class="small-hint">沿用桌面端场景构思与自动续写逻辑，适合手机端轻量操作。</div>
        <div class="small-hint" v-if="!currentScene">请选择或新建一个场景后再开始生成。</div>
        <AiPanel
          :allowed-modes="['multi-node', 'rewrite-scene']"
          default-mode="multi-node"
          :hide-mode-selector="true"
        />
      </div>

      <!-- 全自动生成 -->
      <div class="flow-section">
        <div class="section-header">
          <n-icon :component="CreateOutline" size="18" />
          <span>全自动生成</span>
        </div>
        <n-button type="primary" block size="large" :disabled="!outlineReady" @click="openAutoWrite">
          启动全自动剧本创作
        </n-button>
        <div class="small-hint" v-if="!outlineReady">需要先在「大纲编排」生成并保存大纲</div>
      </div>
    </n-spin>

    <ScriptGenerationModal
      v-model:show="showAutoWrite"
      :outline="outlineData"
      @refresh-files="handleRefreshFiles"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, inject, watch } from 'vue';
import { NIcon, NSpin, NButton, NInput, NSelect } from 'naive-ui';
import { 
  CreateOutline, 
  DocumentTextOutline, 
  SparklesOutline,
  ReaderOutline
} from '@vicons/ionicons5';
import { useSceneStore } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { getOutline } from '../../services/api';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import AiPanel from '../../components/dlg-editor/AiPanel.vue';
import ScriptGenerationModal from '../../components/dlg-editor/ScriptGenerationModal.vue';

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const projectId = inject('projectId', ref(null));

const loading = ref(false);
const outlineData = ref(null);
const showAutoWrite = ref(false);
const selectedFilePath = ref('');
const selectedSceneName = ref('');

const scenes = computed(() => sceneStore.scriptData || []);
const currentScene = computed(() => sceneStore.currentScene);

const sceneTitle = ref('');
const sceneIntro = ref('');
const sceneGuide = ref('');

const storyOptions = computed(() => {
  const flat = [];
  function walk(list = []) {
    list.forEach(item => {
      if (item.type === 'story') {
        flat.push({ label: item.name || item.path, value: item.path });
      } else if (item.children) {
        walk(item.children);
      }
    });
  }
  walk(fileStore.fileTree || []);
  return flat;
});

const sceneOptions = computed(() => {
  return scenes.value.map((s, idx) => ({
    label: s.scene || `场景 ${idx + 1}`,
    value: s.scene
  }));
});

const outlineReady = computed(() => !!outlineData.value?.nodes?.length);

async function loadOutline() {
  if (!projectId.value) return;
  try {
    outlineData.value = await getOutline(projectId.value);
  } catch {
    outlineData.value = null;
  }
}

async function loadFiles() {
  if (!projectId.value) return;
  loading.value = true;
  try {
    await fileStore.loadFileTree(projectId.value);
  } finally {
    loading.value = false;
  }
}

async function handleFileChange(val) {
  if (!val || !projectId.value) return;
  await fileStore.setCurrentFile(projectId.value, val);
  selectedFilePath.value = val;
  selectedSceneName.value = sceneStore.currentScene?.scene || '';
}

function handleSceneChange(val) {
  const found = scenes.value.find(s => s.scene === val);
  if (found) sceneStore.selectScene(found);
}

async function createScene() {
  if (!selectedFilePath.value) return;
  const scene = await sceneStore.createNewScene();
  if (scene?.scene) {
    selectedSceneName.value = scene.scene;
  }
}

function hydrateSceneForm() {
  if (!currentScene.value) {
    sceneTitle.value = '';
    sceneIntro.value = '';
    sceneGuide.value = '';
    return;
  }
  sceneTitle.value = currentScene.value.scene || '';
  sceneIntro.value = currentScene.value.intro || '';
  sceneGuide.value = currentScene.value.guide || '';
}

function saveSceneMeta() {
  if (!currentScene.value) return;
  sceneStore.updateCurrentScene({
    scene: sceneTitle.value.trim() || currentScene.value.scene,
    intro: sceneIntro.value,
    guide: sceneGuide.value
  });
}

function openAutoWrite() {
  showAutoWrite.value = true;
}

async function handleRefreshFiles() {
  await loadFiles();
}

onMounted(async () => {
  await loadFiles();
  await loadOutline();
  if (fileStore.selectedFile?.path) {
    selectedFilePath.value = fileStore.selectedFile.path;
  } else if (storyOptions.value[0]?.value) {
    selectedFilePath.value = storyOptions.value[0].value;
    await handleFileChange(selectedFilePath.value);
  }
});

watch(projectId, async () => {
  await loadFiles();
  await loadOutline();
});

watch(() => fileStore.selectedFile?.path, (val) => {
  if (val) selectedFilePath.value = val;
});

watch(currentScene, () => {
  selectedSceneName.value = currentScene.value?.scene || '';
  hydrateSceneForm();
});
</script>

<style scoped>
.production-mobile {
  padding: 0 4px;
  position: relative;
}

.mobile-section {
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--spark-primary);
  margin: 0 0 8px 0;
}

.section-desc {
  font-size: 13px;
  color: var(--spark-text-muted);
  margin: 0;
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  margin-bottom: 16px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
}

.scene-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}

.small-hint {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.right-panel-section {
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  overflow: hidden;
}
</style>
