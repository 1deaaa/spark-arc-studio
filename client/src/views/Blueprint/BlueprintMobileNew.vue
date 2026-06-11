<template>
  <div class="blueprint-mobile-new">
    <!-- 文件选择 -->
    <div class="file-selector-bar">
      <n-select
        v-model:value="selectedFilePath"
        :options="groupedStoryOptions"
        :placeholder="t('views.blueprint.mobileNew.selectFile')"
        size="small"
        clearable
        @update:value="handleFileChange"
      />
    </div>

    <!-- 场景关系列表 -->
    <div v-if="scenes.length > 0" class="scene-relation-list">
      <div
        v-for="(scene, idx) in scenes"
        :key="scene.scene || idx"
        class="scene-relation-card"
        :class="{ 'is-selected': selectedSceneName === scene.scene }"
        @click="selectScene(scene)"
      >
        <div class="scene-card-main">
          <div class="scene-index">{{ idx + 1 }}</div>
          <div class="scene-card-info">
            <div class="scene-name">{{ scene.scene || t('views.blueprint.mobileNew.untitledScene', { index: idx + 1 }) }}</div>
            <div class="scene-guide" v-if="scene.guide">{{ scene.guide }}</div>
            <div class="scene-meta">
              <SparkTag v-if="scene.dia?.length" type="info" size="small">{{ scene.dia.length }} {{ t('views.blueprint.mobileNew.dialogues') }}</SparkTag>
            </div>
          </div>
        </div>

        <!-- 连线指示器：显示跳转关系 -->
        <div v-if="getSceneJumps(scene).length > 0" class="jump-indicators">
          <div
            v-for="jump in getSceneJumps(scene)"
            :key="jump.target"
            class="jump-indicator"
            @click.stop="editJump(scene, jump)"
          >
            <n-icon :component="ArrowRight" size="14" />
            <span class="jump-target">{{ jump.target }}</span>
            <n-tag size="tiny" :type="jump.type === 'option' ? 'success' : 'info'" :bordered="false">
              {{ jump.type === 'option' ? t('views.blueprint.mobileNew.optionJump') : t('views.blueprint.mobileNew.directJump') }}
            </n-tag>
          </div>
        </div>

        <!-- 连接线 -->
        <div v-if="idx < scenes.length - 1" class="connector-line"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <n-empty :description="selectedFilePath ? t('views.blueprint.mobileNew.noScenes') : t('views.blueprint.mobileNew.selectFileFirst')">
        <template #icon>
          <n-icon :component="GitBranch" size="48" />
        </template>
      </n-empty>
    </div>

    <!-- 新建场景 FAB -->
    <button class="fab-add" @click="createScene" :disabled="!selectedFilePath">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
      </svg>
    </button>

    <!-- 跳转编辑抽屉 -->
    <n-drawer v-model:show="showJumpEditor" placement="bottom" height="40%">
      <n-drawer-content closable>
        <template #header>{{ t('views.blueprint.mobileNew.editJump') }}</template>
        <div v-if="editingJumpScene" class="jump-editor-form">
          <div class="form-item">
            <label>{{ t('views.blueprint.mobileNew.sourceScene') }}</label>
            <n-input :value="editingJumpScene.scene" disabled />
          </div>
          <div class="form-item">
            <label>{{ t('views.blueprint.mobileNew.jumpTarget') }}</label>
            <n-select
              v-model:value="editingJumpTarget"
              :options="sceneNameOptions"
              :placeholder="t('views.blueprint.mobileNew.selectJumpTarget')"
              clearable
            />
          </div>
          <n-button type="primary" block @click="saveJumpEdit">
            {{ t('views.blueprint.mobileNew.saveJump') }}
          </n-button>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, onMounted, type Ref } from 'vue';
import { NSelect, NDrawer, NDrawerContent, NInput, NButton, NIcon, NEmpty, NTag } from 'naive-ui';
import { ArrowRight, GitBranch } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { useProjectStore } from '../../components/stores/projectStore';
import SparkTag from '../../components/share/SparkTag.vue';
import { useStoryFileOptions } from '../../composables/useStoryFileOptions';

const { t } = useI18n();
const sceneStore = useSceneStore();
const fileStore = useFileStore();
const projectStore = useProjectStore();
const projectId = inject<Ref<string | null>>('projectId', ref<string | null>(null));

const selectedFilePath = ref('');
const selectedSceneName = ref<string | null>(null);
const showJumpEditor = ref(false);
const editingJumpScene = ref<SceneWithClientId | null>(null);
const editingJumpTarget = ref('');
const editingJumpSourceNodeId = ref('');

type SelectOption = { label: string; value: string };

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);

const { groupedOptions } = useStoryFileOptions(() => t('views.production.mobile.rootFiles'));
const groupedStoryOptions = computed(() => groupedOptions.value);

const sceneNameOptions = computed<SelectOption[]>(() =>
  scenes.value.map(s => ({ label: s.scene || '', value: s.scene || '' }))
);

// ── 跳转关系提取 ──
type JumpInfo = { target: string; type: 'direct' | 'option'; sourceNodeId?: string };

function getSceneJumps(scene: SceneWithClientId): JumpInfo[] {
  const jumps: JumpInfo[] = [];
  if (!scene.dia) return jumps;
  scene.dia.forEach(d => {
    if (d.next) {
      jumps.push({ target: d.next, type: 'direct' });
    }
    d.opt?.forEach(o => {
      if (o.dia?.length) {
        o.dia.forEach(sd => {
          if (sd.next) {
            jumps.push({ target: sd.next, type: 'option' });
          }
        });
      }
    });
  });
  // 去重
  const seen = new Set<string>();
  return jumps.filter(j => {
    const key = `${j.target}:${j.type}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

// ── 文件选择 ──
async function handleFileChange(val: string | null) {
  if (!val || !projectId.value) return;
  await fileStore.setCurrentFile(projectId.value, val);
  selectedFilePath.value = val;
}

// ── 场景选择 ──
function selectScene(scene: SceneWithClientId) {
  selectedSceneName.value = scene.scene || null;
  sceneStore.selectScene(scene);
}

// ── 创建场景 ──
async function createScene() {
  if (!selectedFilePath.value) return;
  const scene = await sceneStore.createNewScene();
  if (scene) {
    selectedSceneName.value = scene.scene || null;
  }
}

// ── 跳转编辑 ──
function editJump(scene: SceneWithClientId, jump: JumpInfo) {
  editingJumpScene.value = scene;
  editingJumpTarget.value = jump.target;
  showJumpEditor.value = true;
}

function saveJumpEdit() {
  // 跳转编辑目前是只读展示，后续可扩展修改 next 字段
  showJumpEditor.value = false;
}

// ── 初始化 ──
onMounted(async () => {
  if (projectId.value) {
    await fileStore.loadFileTree(projectId.value);
    if (fileStore.selectedFile?.path) {
      selectedFilePath.value = fileStore.selectedFile.path;
    }
  }
});

// 项目切换时重置本地状态并重新加载
watch(projectId, async (newId) => {
  selectedFilePath.value = '';
  selectedSceneName.value = null;
  if (newId) {
    await fileStore.loadFileTree(newId);
  }
});

watch(() => fileStore.selectedFile?.path, (p) => {
  if (p) selectedFilePath.value = p;
});
</script>

<style scoped>
.blueprint-mobile-new {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.file-selector-bar {
  padding: 8px 12px;
  border-bottom: 1px solid var(--spark-border);
  flex-shrink: 0;
}

.scene-relation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  padding-bottom: calc(var(--mobile-bottom-nav-height, 60px) + var(--sab, 0px));
}

.scene-relation-card {
  position: relative;
  background: var(--spark-card-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 4px;
  transition: border-color 0.2s;
}

.scene-relation-card.is-selected {
  border-color: var(--spark-primary);
  box-shadow: 0 0 0 1px var(--spark-primary);
}

.scene-card-main {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.scene-index {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--spark-primary-dim);
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--spark-fs-xs);
  font-weight: 700;
}

.scene-card-info {
  flex: 1;
  min-width: 0;
}

.scene-name {
  font-weight: 600;
  font-size: var(--spark-fs-base);
  color: var(--spark-text);
  margin-bottom: 2px;
}

.scene-guide {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scene-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.jump-indicators {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--spark-border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.jump-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: rgba(var(--spark-primary-rgb), 0.06);
  border-radius: 6px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text);
  cursor: pointer;
  transition: background 0.2s;
}

.jump-indicator:active {
  background: rgba(var(--spark-primary-rgb), 0.15);
}

.jump-target {
  font-weight: 500;
}

.connector-line {
  width: 2px;
  height: 8px;
  background: var(--spark-border);
  margin: 0 auto;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
}

.fab-add {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--spark-primary);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
}

.fab-add:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.jump-editor-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-item label {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--spark-text-muted);
}
</style>
