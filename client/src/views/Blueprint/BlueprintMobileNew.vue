<template>
  <div class="blueprint-mobile-new">
    <section class="blueprint-check-panel">
      <div class="blueprint-heading">
        <div class="blueprint-copy">
          <span class="blueprint-kicker">{{ t('views.blueprint.mobileNew.checkerKicker') }}</span>
          <h3>{{ t('views.blueprint.mobileNew.checkerTitle') }}</h3>
          <p>{{ t('views.blueprint.mobileNew.checkerSubtitle') }}</p>
        </div>
        <SparkTag type="info" size="small">{{ t('views.blueprint.mobileNew.readOnlyBadge') }}</SparkTag>
      </div>

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

      <div class="blueprint-stats">
        <div class="blueprint-stat">
          <span>{{ t('views.blueprint.mobileNew.sceneCount') }}</span>
          <strong>{{ relationStats.sceneCount }}</strong>
        </div>
        <div class="blueprint-stat">
          <span>{{ t('views.blueprint.mobileNew.jumpCount') }}</span>
          <strong>{{ relationStats.jumpCount }}</strong>
        </div>
        <div class="blueprint-stat">
          <span>{{ t('views.blueprint.mobileNew.isolatedCount') }}</span>
          <strong>{{ relationStats.isolatedCount }}</strong>
        </div>
      </div>
    </section>

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
          <n-button text size="tiny" class="open-writing-btn" @click.stop="openSceneInProduction(scene)">
            {{ t('views.blueprint.mobileNew.openInWriting') }}
          </n-button>
        </div>

        <!-- 连线指示器：显示跳转关系 -->
        <div v-if="getSceneJumps(scene).length > 0" class="jump-indicators">
          <div
            v-for="jump in getSceneJumps(scene)"
            :key="jump.target"
            class="jump-indicator"
          >
            <n-icon :component="ArrowRight" size="14" />
            <span class="jump-target">{{ jump.target }}</span>
            <n-tag size="tiny" :type="jump.type === 'option' ? 'success' : 'info'" :bordered="false">
              {{ jump.type === 'option' ? t('views.blueprint.mobileNew.optionJump') : t('views.blueprint.mobileNew.directJump') }}
            </n-tag>
          </div>
        </div>
        <div v-else class="no-jump-hint">
          {{ t('views.blueprint.mobileNew.noJump') }}
        </div>

        <div v-if="selectedSceneName === scene.scene" class="relation-focus">
          <div class="relation-focus-metric">
            <n-icon :component="CornerUpLeft" size="15" />
            <span>{{ t('views.blueprint.mobileNew.incoming') }}</span>
            <strong>{{ getIncomingSources(scene).length }}</strong>
          </div>
          <div class="relation-focus-metric">
            <n-icon :component="CornerDownRight" size="15" />
            <span>{{ t('views.blueprint.mobileNew.outgoing') }}</span>
            <strong>{{ getSceneJumps(scene).length }}</strong>
          </div>
          <div v-if="getIncomingSources(scene).length" class="incoming-sources">
            <span>{{ t('views.blueprint.mobileNew.incomingFrom') }}</span>
            <n-tag v-for="source in getIncomingSources(scene)" :key="source" size="tiny" :bordered="false">
              {{ source }}
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
        <template #extra>
          <n-button type="primary" secondary size="small" @click="openSceneInProduction()">
            {{ t('views.blueprint.mobileNew.goProduction') }}
          </n-button>
        </template>
      </n-empty>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, inject, watch, onMounted, nextTick, type Ref } from 'vue';
import { NButton, NIcon, NEmpty, NSelect, NTag } from 'naive-ui';
import { ArrowRight, CornerDownRight, CornerUpLeft, GitBranch } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import { useSceneStore, type SceneWithClientId } from '../../components/stores/sceneStore';
import { useFileStore } from '../../components/stores/fileStore';
import { useViewStore } from '../../components/stores/viewStore';
import SparkTag from '../../components/share/SparkTag.vue';
import { useStoryFileOptions } from '../../composables/useStoryFileOptions';

const { t } = useI18n();
const sceneStore = useSceneStore();
const fileStore = useFileStore();
const viewStore = useViewStore();
const projectId = inject<Ref<string | null>>('projectId', ref<string | null>(null));

const selectedFilePath = ref('');
const selectedSceneName = ref<string | null>(null);

const scenes = computed<SceneWithClientId[]>(() => Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []);

const { flatOptions, groupedOptions } = useStoryFileOptions(() => t('views.production.mobile.rootFiles'));
const groupedStoryOptions = computed(() => groupedOptions.value);

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

function getIncomingSources(targetScene: SceneWithClientId): string[] {
  const targetName = String(targetScene.scene || '').trim();
  if (!targetName) return [];
  return scenes.value
    .filter(scene => getSceneJumps(scene).some(jump => jump.target === targetName))
    .map(scene => String(scene.scene || '').trim())
    .filter(Boolean);
}

const relationStats = computed(() => {
  const names = scenes.value
    .map(scene => scene.scene || '')
    .filter(Boolean);
  const linked = new Set<string>();
  let jumpCount = 0;

  scenes.value.forEach(scene => {
    const jumps = getSceneJumps(scene);
    jumpCount += jumps.length;
    if (jumps.length > 0 && scene.scene) {
      linked.add(scene.scene);
    }
    jumps.forEach(jump => {
      if (jump.target) linked.add(jump.target);
    });
  });

  return {
    sceneCount: scenes.value.length,
    jumpCount,
    isolatedCount: names.filter(name => !linked.has(name)).length,
  };
});

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

async function openSceneInProduction(scene?: SceneWithClientId) {
  if (scene) {
    selectScene(scene);
  }
  viewStore.setView('production');
  await nextTick();
  document.getElementById('step-5')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ── 初始化 ──
onMounted(async () => {
  if (projectId.value) {
    await fileStore.loadFileTree(projectId.value);
    if (fileStore.selectedFile?.path) {
      selectedFilePath.value = fileStore.selectedFile.path;
    } else if (flatOptions.value[0]?.value) {
      await handleFileChange(flatOptions.value[0].value);
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

watch(scenes, (nextScenes) => {
  const selectedStillExists = nextScenes.some(scene => scene.scene === selectedSceneName.value);
  if (!selectedStillExists) selectedSceneName.value = nextScenes[0]?.scene || null;
}, { immediate: true });
</script>

<style scoped>
.blueprint-mobile-new {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.blueprint-check-panel {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-bottom: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg) 94%, var(--spark-primary) 6%);
}

.blueprint-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.blueprint-copy {
  min-width: 0;
}

.blueprint-kicker {
  display: block;
  margin-bottom: 2px;
  font-size: var(--spark-fs-3xs);
  font-weight: 700;
  color: var(--spark-primary);
}

.blueprint-copy h3 {
  margin: 0;
  font-size: var(--spark-fs-md);
  font-weight: 650;
  color: var(--spark-text);
}

.blueprint-copy p {
  margin: 3px 0 0;
  font-size: var(--spark-fs-xs);
  line-height: 1.45;
  color: var(--spark-text-muted);
}

.file-selector-bar {
  min-width: 0;
}

.blueprint-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.blueprint-stat {
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border) 80%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 38%, transparent);
}

.blueprint-stat span,
.blueprint-stat strong {
  display: block;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.blueprint-stat span {
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
}

.blueprint-stat strong {
  margin-top: 2px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text);
}

.scene-relation-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 8px 12px;
  padding-bottom: 12px;
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

.open-writing-btn {
  flex: 0 0 auto;
  margin-top: -2px;
  white-space: nowrap;
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
  transition: background 0.2s;
}

.jump-target {
  font-weight: 500;
}

.no-jump-hint {
  margin-top: 8px;
  padding: 7px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--spark-warning) 10%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
}

.relation-focus {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--spark-border);
}

.relation-focus-metric {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 5px;
  min-width: 0;
  padding: 7px 8px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--spark-primary) 8%, transparent);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
}

.relation-focus-metric span {
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.relation-focus-metric strong {
  color: var(--spark-primary);
}

.incoming-sources {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
  min-width: 0;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-3xs);
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

@media (max-width: 380px) {
  .blueprint-stats {
    gap: 6px;
  }

  .blueprint-stat {
    padding: 7px 8px;
  }
}
</style>
