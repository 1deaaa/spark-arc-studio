<template>
  <div
    id="settings-editor-container"
    class="settings-editor-container"
    :class="{ 'is-embedded': embedded, 'is-character-mode': isCharacterAtlas }"
  >
    <div class="lorebook-content">
      <!-- 世界观设定 -->
      <div v-if="showWorldview" class="lorebook-card-wrap worldview-wrap" :class="{ 'is-full-height': mode === 'worldview' }">
        <GlobalLoading scope="world" target="worldview" variant="card" />
        <WorldviewMarkdownEditor
          v-model="worldview"
          :save-status="worldviewSaveStatus"
          @input="onWorldviewInput"
        />
      </div>

      <!-- 角色设定 -->
      <CharacterAtlas
        v-if="isCharacterAtlas"
        ref="characterAtlasRef"
        :project-name="projectStore.currentProject || undefined"
        :characters="characters"
        :graph="characterGraph"
        :manual-relations="manualRelations"
        :graph-loading="characterGraphLoading"
        :is-script-mode="isScriptMode"
        @create="createAtlasCharacter"
        @save="saveAtlasCharacter"
        @delete="deleteCharacter"
        @sprite="openCharacterSpriteModal"
        @refresh-graph="refreshCharacterGraph"
        @create-relation="createAtlasRelation"
        @update-relation="updateAtlasRelation"
        @delete-relation="deleteAtlasRelation"
      />

      <div v-else-if="showCharacters" class="lorebook-card-wrap character-wrap">
        <GlobalLoading scope="world" target="characters" variant="card" />
        <n-card 
          :segmented="{ content: true }"
          :bordered="false"
          size="small"
          class="lorebook-card character-section-card"
        >

          <div class="character-section">
            <!-- 角色列表 -->
            <div class="character-grid">
              <n-card
                v-for="(ch, index) in characters"
                :key="ch.id"
                size="small"
                hoverable
                class="character-card"
              >
                <template #header>
                  <span class="character-name">{{ ch.id === -1 ? t('components.lorebookEditor.narrator') : (ch.name || t('components.lorebookEditor.characterN', { n: ch.id })) }}</span>
                </template>
                <template #header-extra>
                  <n-space :size="4">
                    <n-tooltip v-if="isScriptMode && ch.id !== -1" trigger="hover">
                      <template #trigger>
                        <n-button
                          size="tiny"
                          type="primary"
                          circle
                          :aria-label="t('components.lorebookEditor.spriteModalTitle', { name: ch.name || t('components.lorebookEditor.characterN', { n: ch.id }) })"
                          @click="openCharacterSpriteModal(ch)"
                        >
                          <template #icon>
                            <n-icon :component="ImagePlus" />
                          </template>
                        </n-button>
                      </template>
                      {{ t('components.lorebookEditor.spriteModalTitle', { name: ch.name || t('components.lorebookEditor.characterN', { n: ch.id }) }) }}
                    </n-tooltip>
                    <n-button size="tiny" @click="renameCharacter(ch)" :disabled="ch.id === -1">
                      <template #icon>
                        <n-icon :component="SquarePen" />
                      </template>
                    </n-button>
                    <n-popconfirm
                      v-if="ch.id !== -1"
                      @positive-click="deleteCharacter(ch)"
                      :positive-text="t('common.delete')"
                      :negative-text="t('common.cancel')"
                    >
                      <template #trigger>
                        <n-button size="tiny" type="error">
                          <template #icon>
                            <n-icon :component="Trash" />
                          </template>
                        </n-button>
                      </template>
                      <template #default>
                        {{ t('components.lorebookEditor.confirmDeleteCharacter', { name: ch.name || t('components.lorebookEditor.characterN', { n: ch.id }) }) }}
                      </template>
                    </n-popconfirm>
                    <n-button v-else size="tiny" type="error" disabled>
                      <template #icon>
                        <n-icon :component="Trash" />
                      </template>
                    </n-button>
                    <!-- 最后一个角色卡片显示加号按钮 -->
                    <n-button v-if="index === characters.length - 1" size="tiny" type="primary" @click="handleAddCharacter">
                      <template #icon>
                        <n-icon :component="Plus" />
                      </template>
                    </n-button>
                  </n-space>
                </template>

                <StudioSeamlessTextarea
                  v-model:value="ch.content"
                  @input="onCharacterInput(ch)"
                  :placeholder="ch.id === -1 ? t('components.lorebookEditor.narratorPlaceholder') : t('components.lorebookEditor.characterPlaceholder')"
                  :disabled="ch.id === -1"
                  class="character-editor"
                />
              </n-card>
            </div>
          </div>
        </n-card>
      </div>
    </div>

    <n-modal
      v-model:show="characterSpriteModalVisible"
      preset="card"
      :title="activeSpriteCharacter ? t('components.lorebookEditor.spriteModalTitle', { name: activeSpriteCharacter.name || t('components.lorebookEditor.characterN', { n: activeSpriteCharacter.id }) }) : t('components.lorebookEditor.spriteModalFallbackTitle')"
      class="character-sprite-modal"
      :bordered="false"
      style="max-width: 680px;"
    >
      <div v-if="activeSpriteCharacter" class="character-sprite-panel">
        <n-text depth="3" class="sprite-panel-tip">
          {{ t('components.lorebookEditor.spriteModalHint') }}
        </n-text>

        <div class="sprite-existing-list">
          <div
            v-for="asset in activeCharacterSpriteAssets"
            :key="asset.id"
            class="sprite-existing-item"
          >
            <img :src="presentationAssetUrl(asset)" :alt="asset.title || asset.id" />
            <n-tag size="small" :bordered="false" type="info">
              {{ asset.title || asset.id }}
            </n-tag>
            <n-tag v-if="isSpriteMatted(asset)" size="small" :bordered="false" type="success">
              {{ t('components.lorebookEditor.mattingComplete') }}
            </n-tag>
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  size="tiny"
                  quaternary
                  circle
                  :disabled="isSpriteMatted(asset)"
                  :loading="mattingAssetId === asset.id"
                  @click="matteExistingSprite(asset)"
                >
                  <template #icon><n-icon :component="Scissors" /></template>
                </n-button>
              </template>
              {{ t('components.lorebookEditor.matteSprite') }}
            </n-tooltip>
          </div>
          <n-text v-if="activeCharacterSpriteAssets.length === 0" depth="3">
            {{ t('components.lorebookEditor.noSpriteAssets') }}
          </n-text>
        </div>

        <n-select
          v-model:value="selectedImageModelKey"
          size="small"
          clearable
          :loading="imageModelsLoading"
          :options="imageModelOptions"
          :placeholder="t('nodeEditor.presentation.imageModelPlaceholder')"
        />
        <n-text v-if="selectedImageModel && !imageModelSupportsReference(selectedImageModel)" depth="3" class="sprite-panel-tip">
          {{ t('nodeEditor.presentation.imageModelTextOnlyHint') }}
        </n-text>

        <n-input
          v-model:value="characterSpritePrompt"
          type="textarea"
          :autosize="{ minRows: 4, maxRows: 7 }"
          :placeholder="t('components.lorebookEditor.spritePromptPlaceholder')"
        />

        <n-space justify="end" :size="8" wrap>
          <n-button secondary :loading="characterSpriteUploading" @click="triggerCharacterSpriteUpload">
            <template #icon>
              <n-icon :component="Upload" />
            </template>
            {{ t('components.lorebookEditor.uploadSprite') }}
          </n-button>
          <n-button
            type="primary"
            secondary
            :disabled="!canGenerateCharacterSprite"
            :loading="characterSpriteGenerating"
            @click="generateCharacterSpriteByAI"
          >
            <template #icon>
              <n-icon :component="Sparkles" />
            </template>
            {{ t('components.lorebookEditor.generateSprite') }}
          </n-button>
        </n-space>

        <input
          ref="characterSpriteFileInputRef"
          class="sprite-hidden-input"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          @change="onCharacterSpriteFileChange"
        />
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, nextTick, onActivated, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { NCard, NInput, NButton, NIcon, NSpace, NPopconfirm, NModal, NSelect, NText, NTag, NTooltip } from 'naive-ui';
import { ImagePlus, Plus, Scissors, Sparkles, SquarePen, Trash, Upload } from '@lucide/vue';
import StudioSeamlessTextarea from '../editors/StudioSeamlessTextarea.vue';
import CharacterAtlas from './CharacterAtlas.vue';
import WorldviewMarkdownEditor from './WorldviewMarkdownEditor.vue';
import bus from '../../eventBus';
import GlobalLoading from '../share/GlobalLoading.vue';
import { useProjectStore } from '../stores/projectStore';
import { useFileStore } from '../stores/fileStore';
import { useCharacterStore } from '../stores/characterStore';
import { useSceneStore } from '../stores/sceneStore';
import { fetchWithAuth, fetchCharacters, createCharacter, saveCharacter as saveCharacterApi, renameCharacter as renameCharacterApi, deleteCharacter as deleteCharacterApi, fetchCharacterRelations, createCharacterRelation, updateCharacterRelation, deleteCharacterRelation, type CharacterRelation } from '../../services/api';
import {
  fetchPresentationImageModels,
  fetchPresentationManifest,
  generatePresentationSprite,
  uploadPresentationSprite,
  type PresentationAsset,
  type PresentationImageModel,
  type PresentationManifest,
  type PresentationReferenceDescriptor,
  getPresentationErrorMessage,
} from '@/services/presentationService';
import { supportsImageInput } from '@/services/modelModalities';
import { matteSprite } from '@/utils/spriteMatting';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import { AUTO_SAVE_DEBOUNCE_TIME } from '../../config';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';
import {
  fetchGraphRAGCharacterGraph,
  enableCharacterGraph,
  refreshCharacterGraph as refreshCharacterGraphApi,
  type GraphRAGCharacterGraph,
} from '@/services/graphragService';

const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const sceneStore = useSceneStore();
const route = useRoute();

const props = defineProps({
  embedded: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'both',
    validator: (value: string) => ['both', 'worldview', 'characters'].includes(value)
  }
});

const worldview = ref('');
const worldviewSaveStatus = ref<'idle' | 'dirty' | 'saving' | 'saved' | 'error'>('idle');
const { t } = useI18n();

const mode = computed(() => props.mode);
const showWorldview = computed(() => mode.value !== 'characters');
const showCharacters = computed(() => mode.value !== 'worldview');
const isCharacterAtlas = computed(() => mode.value === 'characters');
const characters = ref<any[]>([]); // [{id, name, content}]
const manualRelations = ref<CharacterRelation[]>([]);
const characterGraph = ref<GraphRAGCharacterGraph | null>(null);
const characterAtlasRef = ref<{ revealCharacter: (id: number | string, openProfile?: boolean) => void } | null>(null);
const characterGraphLoading = ref(false);
let characterGraphPollTimer: ReturnType<typeof setTimeout> | null = null;
const characterSpriteModalVisible = ref(false);
const activeSpriteCharacter = ref<any | null>(null);
const characterSpritePrompt = ref('');
const characterSpriteFileInputRef = ref<HTMLInputElement | null>(null);
const characterSpriteUploading = ref(false);
const characterSpriteGenerating = ref(false);
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const spriteChromaKey = ref('#00FF00');
const spriteMattingMode = ref('chroma_key');
const mattingAssetId = ref('');
const SYSTEM_CHARACTER_IDS = new Set([-1, -2]);
const isSystemCharacter = (ch: any) => SYSTEM_CHARACTER_IDS.has(Number(ch?.id));
const userCharactersOnly = (items: any[]) => (Array.isArray(items) ? items.filter(ch => !isSystemCharacter(ch)) : []);
const isScriptMode = computed(() => sceneStore.workspaceMode === 'script');

const manifestAssets = computed<Record<string, PresentationAsset>>(() => {
  const assets = presentationManifest.value?.assets;
  return assets && typeof assets === 'object' ? assets : {};
});

const activeCharacterSpriteAssets = computed(() => {
  const characterKeys = new Set(
    [activeSpriteCharacter.value?.name, activeSpriteCharacter.value?.id]
      .filter(value => value !== undefined && value !== null && String(value).trim())
      .map(value => String(value).trim()),
  );
  if (characterKeys.size === 0) return [];
  return Object.values(manifestAssets.value)
    .filter(asset => asset.type === 'character_sprite' && characterKeys.has(String(asset.characterId || '').trim()))
    .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')));
});

const availableImageModels = computed(() => imageModels.value.filter(model => model.api_key_set !== false));

const imageModelOptions = computed(() => availableImageModels.value.map(model => ({
  label: `${model.platform_name} · ${model.display_name || model.model_name}`,
  value: imageModelKey(model),
})));

const selectedImageModel = computed(() => {
  const key = selectedImageModelKey.value;
  if (key) {
    const matched = availableImageModels.value.find(model => imageModelKey(model) === key);
    if (matched) return matched;
  }
  return availableImageModels.value[0] || null;
});

const canGenerateCharacterSprite = computed(() =>
  isScriptMode.value
  && !!projectStore.currentProject
  && !!activeSpriteCharacter.value
  && !!characterSpritePrompt.value.trim()
  && !!selectedImageModel.value
);

type LorebookCacheSnapshot = {
  worldview: string;
  characters: Array<{ id: number | string; name?: string; content?: string }>;
};

function buildLorebookCacheKey() {
  return buildCreativeCacheKey('lorebook-content', projectStore.currentProject);
}

function getLorebookSnapshot(): LorebookCacheSnapshot {
  return {
    worldview: worldview.value,
    characters: Array.isArray(characters.value)
      ? characters.value.map((ch: any) => ({
          id: ch.id,
          name: ch.name || '',
          content: ch.content || '',
        }))
      : [],
  };
}

function saveLorebookSnapshot() {
  if (!projectStore.currentProject) return;
  saveCreativeCache(buildLorebookCacheKey(), getLorebookSnapshot());
}

function hydrateLorebookFromCache() {
  const cached = loadCreativeCache<LorebookCacheSnapshot>(buildLorebookCacheKey());
  if (!cached) return;
  worldview.value = cached.worldview || '';
  if (Array.isArray(cached.characters)) {
    characters.value = userCharactersOnly(cached.characters).map((ch) => ({ ...ch }));
  }
}

// 加载世界观
async function loadWorldview() {
  const projectId = projectStore.currentProject;
  const fileId = '世界观.txt';
  if (!projectId || !fileId) return;
  try {
    const res = await fetchWithAuth(`/api/lorebooks/${projectId}/${fileId}`);
    if (res.ok) {
      const data = await res.json();
      const remoteWorldview = data?.content || '';
      if (!isCreativeCacheEqual(worldview.value, remoteWorldview)) {
        worldview.value = remoteWorldview;
      }
      worldviewSaveStatus.value = 'saved';
    } else if (res.status === 404) {
      worldview.value = '';
      worldviewSaveStatus.value = 'idle';
    }
    saveLorebookSnapshot();
  } catch {
    worldviewSaveStatus.value = 'error';
  }
}

// 保存世界观
async function saveWorldview() {
  const projectId = projectStore.currentProject;
  const fileId = '世界观.txt';
  if (!projectId || !fileId) return;
  const contentToSave = worldview.value;
  worldviewSaveStatus.value = 'saving';
  try {
    const res = await fetchWithAuth('/api/lorebooks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectId, fileName: fileId, content: contentToSave })
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await res.json();
    saveLorebookSnapshot();
    worldviewSaveStatus.value = worldview.value === contentToSave ? 'saved' : 'dirty';
  } catch {
    worldviewSaveStatus.value = 'error';
  }
}

let worldviewTimer: ReturnType<typeof setTimeout> | null = null;
function onWorldviewInput() {
  worldviewSaveStatus.value = 'dirty';
  saveLorebookSnapshot();
  if (worldviewTimer) {
    clearTimeout(worldviewTimer);
  }
  worldviewTimer = setTimeout(() => {
    saveWorldview();
  }, AUTO_SAVE_DEBOUNCE_TIME);
}

// 加载角色设定
async function loadCharacters() {
  if (!projectStore.currentProject) return;
  try {
    const remoteCharacters = await fetchCharacters(projectStore.currentProject, true);
    if (!isCreativeCacheEqual(characters.value, remoteCharacters)) {
      characters.value = userCharactersOnly(remoteCharacters);
    }
    try {
      manualRelations.value = await fetchCharacterRelations(projectStore.currentProject);
    } catch {}
  } catch {}
  saveLorebookSnapshot();
}

function stopCharacterGraphPolling() {
  if (characterGraphPollTimer) {
    clearTimeout(characterGraphPollTimer);
    characterGraphPollTimer = null;
  }
}

async function loadCharacterGraph(options: { poll?: boolean } = {}) {
  stopCharacterGraphPolling();
  const projectName = projectStore.currentProject;
  if (!projectName || !showCharacters.value) {
    characterGraph.value = null;
    return;
  }
  characterGraphLoading.value = true;
  try {
    const result = await fetchGraphRAGCharacterGraph(projectName);
    if (projectStore.currentProject !== projectName) return;
    characterGraph.value = result;
    const status = result.buildState.status.toLowerCase();
    if (options.poll !== false && ['queued', 'building', 'cancelling'].includes(status)) {
      characterGraphPollTimer = setTimeout(() => loadCharacterGraph({ poll: true }), 2200);
    }
  } catch {
    characterGraph.value = null;
  } finally {
    characterGraphLoading.value = false;
  }
}

async function refreshCharacterGraph() {
  const projectName = projectStore.currentProject;
  if (!projectName) return;
  try {
    if (characterGraph.value?.enabled) {
      await refreshCharacterGraphApi(projectName);
    } else {
      await enableCharacterGraph(projectName);
    }
  } catch {
    bus.emit('toast', { type: 'error', message: t('views.characters.graphSyncFailed') });
  }
  await loadCharacterGraph();
}

function markCharacterGraphStale() {
  const graph = characterGraph.value;
  if (!graph?.enabled) return;
  const activeStatuses = new Set(['queued', 'building', 'cancelling']);
  const status = graph.buildState.status.toLowerCase();
  characterGraph.value = {
    ...graph,
    needsRebuild: true,
    buildState: activeStatuses.has(status)
      ? graph.buildState
      : {
          ...graph.buildState,
          status: graph.graphReady ? 'stale' : 'not_built',
          stage: 'idle',
        },
  };
}

function imageModelKey(model: PresentationImageModel) {
  return `${model.platform_id}:${model.model_id}`;
}

function imageModelSupportsReference(model: PresentationImageModel | null) {
  return supportsImageInput(model);
}

function presentationErrorMessage(error: unknown, fallback: string) {
  return getPresentationErrorMessage(error, fallback);
}

async function loadPresentationImageModels() {
  if (!isScriptMode.value) {
    imageModels.value = [];
    selectedImageModelKey.value = null;
    return;
  }
  imageModelsLoading.value = true;
  try {
    const result = await fetchPresentationImageModels();
    imageModels.value = Array.isArray(result.models) ? result.models : [];
    if (!selectedImageModelKey.value && availableImageModels.value.length > 0) {
      selectedImageModelKey.value = imageModelKey(availableImageModels.value[0]);
    }
  } catch (error: unknown) {
    imageModels.value = [];
    bus.emit('toast', { type: 'warning', message: presentationErrorMessage(error, t('nodeEditor.presentation.imageModelLoadFailed')) });
  } finally {
    imageModelsLoading.value = false;
  }
}

async function loadPresentationManifest() {
  if (!projectStore.currentProject || !isScriptMode.value) {
    presentationManifest.value = null;
    return;
  }
  try {
    const result = await fetchPresentationManifest(projectStore.currentProject);
    presentationManifest.value = result.manifest || null;
    spriteChromaKey.value = result.settings?.visualIllustration?.sprite_chroma_key || '#00FF00';
    spriteMattingMode.value = result.settings?.visualIllustration?.sprite_matting || 'chroma_key';
  } catch {
    presentationManifest.value = null;
  }
}

function updatePresentationManifest(manifest: PresentationManifest | undefined | null) {
  if (manifest) {
    presentationManifest.value = manifest;
    bus.emit('presentation-manifest-updated', { projectName: projectStore.currentProject });
  }
}

function characterAssetKey(ch: any) {
  return String(ch?.id ?? '').trim();
}

function openCharacterSpriteModal(ch) {
  if (!isScriptMode.value || isSystemCharacter(ch)) return;
  activeSpriteCharacter.value = ch;
  characterSpritePrompt.value = '';
  characterSpriteModalVisible.value = true;
  void loadPresentationManifest();
  void loadPresentationImageModels();
}

function characterSpriteReferences() {
  const model = selectedImageModel.value;
  if (!imageModelSupportsReference(model)) return [];
  const result: PresentationReferenceDescriptor[] = [];
  const latestSprite = activeCharacterSpriteAssets.value[0];
  if (latestSprite?.id) {
    result.push({ assetId: latestSprite.id, role: 'character' });
  }
  return result;
}

function presentationAssetUrl(asset: PresentationAsset) {
  if (asset.url) return asset.url;
  const projectName = encodeURIComponent(projectStore.currentProject || '');
  const path = String(asset.path || '').replace(/\\/g, '/').split('/').filter(Boolean).map(encodeURIComponent).join('/');
  return projectName && path ? `/api/presentation/${projectName}/assets/${path}` : '';
}

function isSpriteMatted(asset: PresentationAsset): boolean {
  const status = String(asset.matting?.status || '').trim().toLowerCase();
  if (status === 'complete' || status === 'completed') return true;

  // 兼容本功能上线前已经生成的透明立绘记录，后续新记录以 matting 元数据为准。
  const title = String(asset.title || '').trim().toLowerCase();
  const path = String(asset.path || '').trim().toLowerCase();
  return asset.source === 'upload'
    && path.endsWith('.png')
    && /透明立绘|透過立ち絵|transparent\s+sprite|투명\s*(?:스프라이트|立ち絵)/i.test(title);
}

async function matteAndUploadSprite(asset: PresentationAsset) {
  const projectName = projectStore.currentProject;
  const character = activeSpriteCharacter.value;
  const url = presentationAssetUrl(asset);
  if (!projectName || !character || !url) throw new Error(t('components.lorebookEditor.matteSourceMissing'));
  const response = await fetchWithAuth(url);
  if (!response.ok) throw new Error(t('components.lorebookEditor.matteSourceMissing'));
  const transparent = await matteSprite(await response.blob(), {
    mode: spriteMattingMode.value,
    chromaKey: spriteChromaKey.value,
  });
  const file = new File([transparent], `${asset.id}-transparent.png`, { type: 'image/png' });
  return await uploadPresentationSprite(projectName, file, {
    title: `${character.name || character.id}-${t('components.lorebookEditor.transparentSpriteTitle')}`,
    characterId: characterAssetKey(character),
    expression: asset.expression || 'default',
    matting: {
      mode: spriteMattingMode.value,
      sourceAssetId: asset.id,
    },
  });
}

async function matteExistingSprite(asset: PresentationAsset) {
  if (isSpriteMatted(asset)) {
    bus.emit('toast', { type: 'info', message: t('components.lorebookEditor.mattingAlreadyComplete') });
    return;
  }
  mattingAssetId.value = asset.id;
  try {
    const result = await matteAndUploadSprite(asset);
    updatePresentationManifest(result.manifest);
    bus.emit('toast', { type: 'success', message: t('components.lorebookEditor.matteSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('components.lorebookEditor.matteFailed')) });
  } finally {
    mattingAssetId.value = '';
  }
}

function triggerCharacterSpriteUpload() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  characterSpriteFileInputRef.value?.click();
}

async function onCharacterSpriteFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  if (!file || !projectStore.currentProject || !activeSpriteCharacter.value) return;
  characterSpriteUploading.value = true;
  try {
    const result = await uploadPresentationSprite(projectStore.currentProject, file, {
      title: `${activeSpriteCharacter.value.name || activeSpriteCharacter.value.id}-${file.name}`,
      characterId: characterAssetKey(activeSpriteCharacter.value),
      expression: 'default',
    });
    updatePresentationManifest(result.manifest);
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.spriteUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.spriteUploadFailed')) });
  } finally {
    characterSpriteUploading.value = false;
  }
}

async function generateCharacterSpriteByAI() {
  if (!projectStore.currentProject || !activeSpriteCharacter.value) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  const model = selectedImageModel.value;
  if (!model) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.imageModelMissing') });
    return;
  }
  if (!characterSpritePrompt.value.trim()) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.promptRequired') });
    return;
  }
  characterSpriteGenerating.value = true;
  const task = createStreamingTask('world', {
    target: 'visual-character-sprite',
    text: t('components.lorebookEditor.generateSprite'),
    progress: t('components.lorebookEditor.generateSprite'),
    canCancel: true,
    statsMode: 'elapsed',
  });
  try {
    task.throwIfAborted();
    const result = await generatePresentationSprite(projectStore.currentProject, {
      prompt: characterSpritePrompt.value.trim(),
      title: activeSpriteCharacter.value.name || t('components.lorebookEditor.characterN', { n: activeSpriteCharacter.value.id }),
      characterId: characterAssetKey(activeSpriteCharacter.value),
      expression: 'default',
      size: '1024x1536',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssets: characterSpriteReferences(),
      context: {
        characterIds: [String(activeSpriteCharacter.value.id)],
      },
    }, task.signal);
    task.throwIfAborted();
    updatePresentationManifest(result.manifest);
    if (result.asset?.id) {
      try {
        mattingAssetId.value = result.asset.id;
        const transparentResult = await matteAndUploadSprite(result.asset);
        updatePresentationManifest(transparentResult.manifest);
      } catch (error: unknown) {
        bus.emit('toast', { type: 'warning', message: presentationErrorMessage(error, t('components.lorebookEditor.autoMatteFailed')) });
      } finally {
        mattingAssetId.value = '';
      }
    }
    characterSpritePrompt.value = '';
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.spriteGenerateSuccess') });
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.spriteGenerateFailed')) });
  } finally {
    task.dispose();
    characterSpriteGenerating.value = false;
  }
}

// 添加角色（通过弹窗输入名称）
async function handleAddCharacter() {
  const name = await new Promise<string | null>(resolve => {
    bus.emit('prompt', {
      title: t('components.lorebookEditor.addCharacter'),
      message: t('components.lorebookEditor.enterCharacterName'),
      defaultValue: '',
      resolve
    });
  });
  if (!name || !name.trim()) return;
  try {
    await createCharacter(projectStore.currentProject, name.trim());
    await loadCharacters();
    await characterStore.reload(projectStore.currentProject);
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

async function createAtlasCharacter(
  payload: { name: string; content: string },
  complete: (success: boolean) => void,
) {
  const name = payload.name.trim();
  if (!name || !projectStore.currentProject) {
    complete(false);
    return;
  }
  const projectName = projectStore.currentProject;
  let result: Awaited<ReturnType<typeof createCharacter>>;
  try {
    result = await createCharacter(projectName, name, payload.content);
  } catch (error: unknown) {
    complete(false);
    bus.emit('toast', {
      type: 'error',
      message: presentationErrorMessage(error, t('views.characters.createFailed')),
    });
    return;
  }

  const createdId = result.id;
  if (createdId === undefined) {
    complete(false);
    bus.emit('toast', { type: 'error', message: t('views.characters.createFailed') });
    return;
  }
  const createdCharacter = { id: createdId, name, desc: '', content: payload.content };
  const existingIndex = characters.value.findIndex(character => String(character.id) === String(createdId));
  characters.value = existingIndex >= 0
    ? characters.value.map((character, index) => index === existingIndex ? createdCharacter : character)
    : [...characters.value, createdCharacter];
  markCharacterGraphStale();
  saveLorebookSnapshot();
  await nextTick();
  characterAtlasRef.value?.revealCharacter(createdId, false);
  complete(true);
  window.dispatchEvent(new CustomEvent('saved'));
  bus.emit('toast', { type: 'success', message: t('views.characters.created') });
  void characterStore.reload(projectName).catch(() => undefined);
}

async function saveAtlasCharacter(payload: { character: any; name: string; content: string }) {
  const projectName = projectStore.currentProject;
  if (!projectName) return;
  const oldName = String(payload.character.name || '').trim();
  try {
    if (payload.name !== oldName) {
      await renameCharacterApi(projectName, payload.character.id, payload.name);
      sceneStore.renameSpeaker(oldName, payload.name);
    }
    await saveCharacterApi(projectName, payload.character.id, payload.content || '');
    await loadCharacters();
    markCharacterGraphStale();
    await characterStore.reload(projectName);
    window.dispatchEvent(new CustomEvent('saved'));
    bus.emit('toast', { type: 'success', message: t('views.characters.saved') });
  } catch {
    bus.emit('toast', { type: 'error', message: t('views.characters.saveFailed') });
  }
}

type AtlasRelationPayload = Omit<CharacterRelation, 'id' | 'created_at' | 'updated_at'>;

async function createAtlasRelation(payload: AtlasRelationPayload, complete: (success: boolean) => void) {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    complete(false);
    return;
  }
  try {
    const relation = await createCharacterRelation(projectName, payload);
    manualRelations.value = [...manualRelations.value, relation];
    complete(true);
    bus.emit('toast', { type: 'success', message: t('views.characters.relationCreated') });
  } catch (error: unknown) {
    complete(false);
    bus.emit('toast', { type: 'error', message: error instanceof Error ? error.message : t('views.characters.relationSaveFailed') });
  }
}

async function updateAtlasRelation(relationId: string, payload: AtlasRelationPayload, complete: (success: boolean) => void) {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    complete(false);
    return;
  }
  try {
    const relation = await updateCharacterRelation(projectName, relationId, payload);
    manualRelations.value = manualRelations.value.map(item => item.id === relationId ? relation : item);
    complete(true);
    bus.emit('toast', { type: 'success', message: t('views.characters.relationSaved') });
  } catch (error: unknown) {
    complete(false);
    bus.emit('toast', { type: 'error', message: error instanceof Error ? error.message : t('views.characters.relationSaveFailed') });
  }
}

async function deleteAtlasRelation(relation: CharacterRelation, complete: (success: boolean) => void) {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    complete(false);
    return;
  }
  try {
    await deleteCharacterRelation(projectName, relation.id);
    manualRelations.value = manualRelations.value.filter(item => item.id !== relation.id);
    complete(true);
    bus.emit('toast', { type: 'success', message: t('views.characters.relationDeleted') });
  } catch (error: unknown) {
    complete(false);
    bus.emit('toast', { type: 'error', message: error instanceof Error ? error.message : t('views.characters.relationDeleteFailed') });
  }
}

// 保存角色
async function saveCharacter(ch) {
  try {
    await saveCharacterApi(projectStore.currentProject, ch.id, ch.content || '');
    markCharacterGraphStale();
    saveLorebookSnapshot();
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

// 重命名角色
async function renameCharacter(ch) {
  const newName = await new Promise(resolve => {
    bus.emit('prompt', {
      title: t('components.lorebookEditor.renameCharacter'),
      message: t('components.lorebookEditor.enterNewCharacterName'),
      defaultValue: ch.name || '',
      resolve
    });
  });
  const oldName = String(ch.name || '').trim();
  const normalizedNewName = typeof newName === 'string' ? newName.trim() : '';
  if (!normalizedNewName || normalizedNewName === oldName) return;
  try {
    await renameCharacterApi(projectStore.currentProject, ch.id, normalizedNewName);
    sceneStore.renameSpeaker(oldName, normalizedNewName);
    await loadCharacters();
    markCharacterGraphStale();
    await characterStore.reload(projectStore.currentProject);
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

// 删除角色
async function deleteCharacter(ch) {
  // n-popconfirm 已经提供确认功能，无需额外确认
  try {
    await deleteCharacterApi(projectStore.currentProject, ch.id);
    await loadCharacters();
    markCharacterGraphStale();
    await characterStore.reload(projectStore.currentProject);
    window.dispatchEvent(new CustomEvent('saved'));
    bus.emit('toast', { type: 'success', message: t('components.lorebookEditor.characterDeleted') });
  } catch {
    bus.emit('toast', { type: 'error', message: t('components.lorebookEditor.deleteFailed') });
  }
}

// 输入防抖自动保存角色
const timers = new Map();
function onCharacterInput(ch) {
  const key = ch.id;
  saveLorebookSnapshot();
  clearTimeout(timers.get(key));
  const timer = setTimeout(() => {
    saveCharacter(ch);
  }, AUTO_SAVE_DEBOUNCE_TIME);
  timers.set(key, timer);
}

// 当显示或项目变化时加载数据
// 当显示或项目变化时加载数据
onMounted(() => {
  hydrateLorebookFromCache();
  if (showWorldview.value) loadWorldview();
  if (showCharacters.value) loadCharacters();
  if (showCharacters.value) loadCharacterGraph();
  if (showCharacters.value) loadPresentationManifest();
  if (showCharacters.value) loadPresentationImageModels();
  bus.on('lorebook-refresh', onLorebookRefresh);
  bus.on('character-streamed', onStreamedCharacter);
  bus.on('characters-cleared', onCharactersCleared);
  bus.on('worldview-stream-start', onWorldviewStreamStart);
  bus.on('worldview-stream-chunk', onWorldviewStreamChunk);
  bus.on('worldview-stream-end', onWorldviewStreamEnd);
  bus.on('lorebook-refresh-worldview', onLorebookRefreshWorldview);
  bus.on('lorebook-refresh-characters', onLorebookRefreshCharacters);
  bus.on('presentation-manifest-updated', onPresentationManifestUpdated);
});

watch(() => projectStore.currentProject, (nextProject, prevProject) => {
  if (nextProject === prevProject) return;
  hydrateLorebookFromCache();
  if (showWorldview.value) loadWorldview();
  if (showCharacters.value) loadCharacters();
  if (showCharacters.value) loadCharacterGraph();
  if (showCharacters.value) loadPresentationManifest();
  if (showCharacters.value) loadPresentationImageModels();
});

onBeforeUnmount(() => {
  stopCharacterGraphPolling();
  if (worldviewTimer) clearTimeout(worldviewTimer);
  timers.forEach(timer => clearTimeout(timer));
  timers.clear();
  bus.off('lorebook-refresh', onLorebookRefresh);
  bus.off('character-streamed', onStreamedCharacter);
  bus.off('characters-cleared', onCharactersCleared);
  bus.off('worldview-stream-start', onWorldviewStreamStart);
  bus.off('worldview-stream-chunk', onWorldviewStreamChunk);
  bus.off('worldview-stream-end', onWorldviewStreamEnd);
  bus.off('lorebook-refresh-worldview', onLorebookRefreshWorldview);
  bus.off('lorebook-refresh-characters', onLorebookRefreshCharacters);
  bus.off('presentation-manifest-updated', onPresentationManifestUpdated);
});

onActivated(() => {
  // Silently refresh data when view is reactivated
  if (showWorldview.value) loadWorldview();
  if (showCharacters.value) loadCharacters();
  if (showCharacters.value) loadCharacterGraph();
  if (showCharacters.value) loadPresentationManifest();
  if (showCharacters.value) loadPresentationImageModels();
});

function onLorebookRefresh() {
  loadWorldview();
  loadCharacters();
  markCharacterGraphStale();
  loadPresentationManifest();
}

function onLorebookRefreshWorldview() {
  if (worldviewTimer) clearTimeout(worldviewTimer);
  loadWorldview();
  markCharacterGraphStale();
}

function onLorebookRefreshCharacters() {
  loadCharacters();
  markCharacterGraphStale();
}

function onPresentationManifestUpdated(payload?: unknown) {
  const projectName = payload && typeof payload === 'object' && 'projectName' in payload
    ? String((payload as { projectName?: unknown }).projectName || '')
    : '';
  if (projectName && projectName !== projectStore.currentProject) return;
  const manifest = payload && typeof payload === 'object' && 'manifest' in payload
    ? (payload as { manifest?: unknown }).manifest
    : null;
  if (manifest && typeof manifest === 'object') {
    presentationManifest.value = manifest as PresentationManifest;
    return;
  }
  loadPresentationManifest();
}

function onWorldviewStreamStart() {
  if (worldviewTimer) clearTimeout(worldviewTimer);
  worldviewSaveStatus.value = 'saving';
  worldview.value = '';
}

function onWorldviewStreamChunk(payload) {
  const text = payload?.text ?? '';
  if (!text) return;
  worldview.value += text;
}

function onWorldviewStreamEnd() {
  loadWorldview();
}

function onCharactersCleared(payload) {
  try {
    if (!payload || payload.projectName !== projectStore.currentProject) return;
    characters.value = [];
    streamBuffers.clear();
  } catch {}
}

// 流式数据缓冲区：用于减少 Vue 更新频率
const streamBuffers = new Map(); // id -> {buffer, timer}
const UPDATE_INTERVAL = 100; // 每100ms最多更新一次

function extractXmlTagValue(text, tag) {
  const raw = String(text || '');
  const startTag = `<${tag}>`;
  const endTag = `</${tag}>`;
  const start = raw.indexOf(startTag);
  if (start === -1) return null;
  const valueStart = start + startTag.length;
  const end = raw.indexOf(endTag, valueStart);
  if (end === -1) return null;
  return raw.slice(valueStart, end).trim();
}

function extractXmlTagFragment(text, tag) {
  const raw = String(text || '');
  const startTag = `<${tag}>`;
  const endTag = `</${tag}>`;
  const start = raw.indexOf(startTag);
  if (start === -1) return null;
  const valueStart = start + startTag.length;
  const end = raw.indexOf(endTag, valueStart);
  if (end === -1) return raw.slice(valueStart).replace(/^[\r\n]+/, '');
  return raw.slice(valueStart, end).replace(/^[\r\n]+/, '');
}

function parseCharacterStreamPayload(text, fallbackName) {
  const raw = String(text || '');
  const xmlName = extractXmlTagValue(raw, 'name');
  const xmlContent = extractXmlTagFragment(raw, 'content');

  if (xmlName || xmlContent !== null) {
    return {
      name: xmlName || fallbackName,
      content: xmlContent || '',
    };
  }

  const separatorPos = raw.indexOf('\n\n');
  if (separatorPos !== -1) {
    const legacyName = raw.substring(0, separatorPos).trim() || fallbackName;
    const legacyContent = raw.substring(separatorPos + 2);
    return {
      name: legacyName,
      content: legacyContent,
    };
  }

  return {
    name: fallbackName,
    content: raw,
  };
}

// 应用缓冲区的流式内容到 Vue 数据
function applyStreamBuffer(charId) {
  const bufferData = streamBuffers.get(charId);
  if (!bufferData || !bufferData.buffer) return;
  
  const idx = characters.value.findIndex(x => String(x.id) === String(charId));
  
  if (idx >= 0) {
    const prev = characters.value[idx];
    const streamBuffer = (prev.streamBuffer || '') + bufferData.buffer;
    const parsed = parseCharacterStreamPayload(streamBuffer, prev.name || t('components.lorebookEditor.characterN', { n: charId }));
    
    // 直接修改对象属性，触发响应式更新
    prev.name = parsed.name;
    prev.content = parsed.content;
    prev.streamBuffer = streamBuffer;
  } else {
    // 新角色，初始化
    const streamBuffer = bufferData.buffer;
    const parsed = parseCharacterStreamPayload(streamBuffer, t('components.lorebookEditor.characterN', { n: charId }));
    
    characters.value.push({ 
      id: charId, 
      name: parsed.name,
      content: parsed.content,
      streamBuffer: streamBuffer
    });
  }
  
  // 清空缓冲区
  bufferData.buffer = '';
  markCharacterGraphStale();
  saveLorebookSnapshot();
}

// 流式新增：接收 CharacterGeneratorPanel 发出的事件
function onStreamedCharacter(payload) {
  try {
    if (!payload || payload.projectName !== projectStore.currentProject) return;
    const ch = payload.character;
    if (!ch || typeof ch.id === 'undefined') return;
    
    // 处理增量内容（来自 character-delta 事件）
    if (typeof ch.appendContent === 'string') {
      // 获取或创建缓冲区
      let bufferData = streamBuffers.get(ch.id);
      if (!bufferData) {
        bufferData = { buffer: '', timer: null };
        streamBuffers.set(ch.id, bufferData);
      }
      
      // 累加到缓冲区
      bufferData.buffer += ch.appendContent;
      
      // 节流更新：防抖，最后一次更新后才真正应用
      if (bufferData.timer) {
        clearTimeout(bufferData.timer);
      }
      
      bufferData.timer = setTimeout(() => {
        applyStreamBuffer(ch.id);
        bufferData.timer = null;
      }, UPDATE_INTERVAL);
      
      return;
    }
    
    // 非增量更新（来自 character-start/character-streamed/character-end 事件）
    
    // 清空该角色的缓冲区和定时器
    const bufferData = streamBuffers.get(ch.id);
    if (bufferData) {
      if (bufferData.timer) {
        clearTimeout(bufferData.timer);
        bufferData.timer = null;
      }
      // 先应用缓冲区中的内容
      if (bufferData.buffer) {
        applyStreamBuffer(ch.id);
      }
    }
    
    const idx = characters.value.findIndex(x => String(x.id) === String(ch.id));
    
    if (idx >= 0) {
      const prev = characters.value[idx];
      
      // 如果提供了 name，更新 name
      if (ch.name !== undefined && ch.name !== null) {
        prev.name = ch.name || `角色 ${ch.id}`;
      }
      
      // 如果提供了 content，更新 content
      if (ch.content !== undefined && ch.content !== null) {
        prev.content = ch.content;
      }
      
      // 清除流式缓冲（仅在收到 character-end 且有完整 content 时）
      if (ch.content !== undefined) {
        delete prev.streamBuffer;
      }
    } else {
      // 新角色
      const newChar = { 
        id: ch.id, 
        name: ch.name || `角色 ${ch.id}`, 
        content: ch.content || '',
        streamBuffer: ''
      };
      characters.value.push(newChar);
    }
    markCharacterGraphStale();
    saveLorebookSnapshot();
  } catch (err) {
    // 静默处理错误
  }
}

</script>

<style scoped>
.lorebook-card-wrap {
  position: relative;
  border-radius: 14px;
  overflow: hidden;
}

.settings-editor-container {
  width: 100%;
  height: 100%;
}

.lorebook-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  height: 100%;
}

.lorebook-content > :deep(.character-atlas) {
  flex: 1;
  min-height: 0;
}

.lorebook-card {
  width: 100%;
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.settings-editor-container :deep(.lorebook-card.n-card) {
  border-radius: 0 !important;
  box-shadow: none !important;
  background: transparent !important;
}

.settings-editor-container :deep(.lorebook-card .n-card__header),
.settings-editor-container :deep(.lorebook-card .n-card-content),
.settings-editor-container :deep(.lorebook-card .n-card__action) {
  border-radius: 0 !important;
  background: transparent !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card__header) {
  padding: 0 0 8px !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card-content) {
  padding: 0 !important;
}

.settings-editor-container.is-embedded :deep(.lorebook-card .n-card__action) {
  padding: 10px 0 0 !important;
}

.worldview-wrap {
  height: 45%;
  flex-shrink: 0;
  border-radius: 6px;
}

.worldview-wrap.is-full-height {
  height: 100%;
  flex: 1 1 auto;
}

.worldview-wrap :deep(.worldview-workbench) {
  height: 100%;
}

.character-wrap {
  height: 55%;
  flex-shrink: 0;
  overflow: auto;
}

.character-section-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.character-section-card :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  overflow: auto;
}

.character-section {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-width-space {
  width: 100%;
}

.character-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: calc(50% - 6px);
  gap: 12px;
  width: 100%;
  flex: 1;
  min-height: 0;
  align-content: start;
}

.character-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.character-card :deep(.n-card-header) {
  padding: 6px 10px !important;
  min-height: 32px;
  flex-shrink: 0;
}

.character-card :deep(.n-card-header__main) {
  font-size: var(--spark-fs-sm);
  line-height: 1.2;
}

.character-name {
  font-weight: 600;
}

.character-card :deep(.n-card-content) {
  padding: 0 !important;
  overflow: auto;
  flex: 1;
  min-height: 0;
}

.character-editor {
  width: 100%;
  height: 100%;
}

.character-editor :deep(.n-input),
.character-editor :deep(.n-input-wrapper),
.character-editor :deep(.n-input__textarea),
.character-editor :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.character-editor :deep(.n-input__textarea-mirror) {
  min-height: 100% !important;
  max-height: 100% !important;
}

/* 窄屏：保持 2 列 */
@media (max-width: 1920px) {
  .character-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.settings-editor-container.is-embedded {
  height: auto;
  overflow: visible;
  padding: 0;
}

.settings-editor-container.is-embedded.is-character-mode {
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.settings-editor-container.is-embedded .lorebook-content {
  padding: 0;
}

/* Force Naive UI components to fill width */
.settings-editor-container :deep(.n-input),
.settings-editor-container :deep(.n-input-wrapper),
.settings-editor-container :deep(.n-input__textarea) {
  width: 100% !important;
}

.settings-editor-container :deep(.n-card) {
  width: 100%;
}

.settings-editor-container :deep(.n-space) {
  width: 100% !important;
  display: flex !important;
}

.character-sprite-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sprite-panel-tip {
  font-size: var(--spark-fs-xs);
  line-height: 1.55;
}

.sprite-existing-list {
  min-height: 30px;
  max-height: 240px;
  overflow: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 42%, transparent);
}

.sprite-existing-item {
  min-width: 0;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 28px;
  align-items: center;
  gap: 8px;
}

.sprite-existing-item img {
  width: 48px;
  height: 64px;
  object-fit: contain;
  background: var(--spark-bg);
  border-radius: 4px;
}

.sprite-existing-item :deep(.n-tag) {
  min-width: 0;
  overflow: hidden;
}

.sprite-hidden-input {
  display: none;
}

:global(.character-sprite-modal.n-card) {
  border-radius: 8px;
}
</style>
