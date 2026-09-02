<template>
  <div class="node-presentation-section" v-if="canUsePresentationTools && isDialogueSelected">
    <n-collapse default-expanded-names="presentation-main">
      <n-collapse-item name="presentation-main">
        <template #header>
          <span class="presentation-section-title">
            <n-icon :component="Images" size="16" />
            <span>{{ t('nodeEditor.presentation.visualNovel') || '演出画面' }}</span>
          </span>
        </template>
        <template #header-extra>
          <n-space :size="4" align="center">
            <SparkTag v-if="currentBackgroundId" type="primary" size="small">
              {{ t('nodeEditor.presentation.backgroundShort', { value: currentBackgroundId }) }}
            </SparkTag>
            <SparkTag v-if="currentIllustrationId" type="success" size="small">
              {{ t('nodeEditor.presentation.illustrationShort', { value: currentIllustrationId }) }}
            </SparkTag>
          </n-space>
        </template>

        <div class="presentation-content-stack">
          <!-- 生图模型选择 -->
          <div class="presentation-field-group">
            <div class="field-label-row">
              <span class="field-label">{{ t('nodeEditor.presentation.imageModelLabel') }}</span>
            </div>
            <n-select
              v-model:value="selectedImageModelKey"
              class="presentation-select"
              size="small"
              clearable
              :loading="imageModelsLoading"
              :disabled="presentationGenerationBusy"
              :options="imageModelSelectOptions"
              :placeholder="t('nodeEditor.presentation.imageModelPlaceholder')"
            />
            <n-text v-if="!imageModelsLoading && availableImageModels.length === 0" depth="3" class="field-hint-text">
              {{ t('nodeEditor.presentation.imageModelMissing') }}
            </n-text>
          </div>

          <!-- 唯一演出构思编辑框 -->
          <div class="presentation-field-group">
            <div class="field-label-row">
              <span class="field-label">{{ t('nodeEditor.presentation.conceptionLabel') }}</span>
              <n-button
                v-if="currentIllustrationPending"
                size="tiny"
                type="primary"
                secondary
                :disabled="!canGenerateIllustrationConception"
                :loading="illustrationConceptionGenerating"
                @click="generateIllustrationConceptionByAI"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateIllustrationConception') }}
              </n-button>
            </div>
            <n-input
              v-model:value="illustrationPrompt"
              type="textarea"
              size="small"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :placeholder="t('nodeEditor.presentation.conceptionPlaceholder')"
              @blur="saveIllustrationPrompt"
            />
          </div>

          <!-- 背景配置与生成 -->
          <div class="presentation-field-group">
            <div class="field-label-row">
              <span class="field-label">{{ t('nodeEditor.presentation.background') }}</span>
            </div>
            <n-select
              :value="currentBackgroundId || null"
              size="small"
              clearable
              filterable
              :options="backgroundAssetOptions"
              :placeholder="t('nodeEditor.presentation.backgroundLibrarySelect')"
              @update:value="setDialoguePresentationValue('bg', $event || null)"
            />
            
            <div class="background-preview-box" :class="{ 'is-empty': !currentBackgroundPreviewUrl || backgroundPreviewFailed }">
              <img
                v-if="currentBackgroundPreviewUrl && !backgroundPreviewFailed"
                :src="currentBackgroundPreviewUrl"
                :alt="t('nodeEditor.presentation.background')"
                @error="backgroundPreviewFailed = true"
              />
              <div v-else class="background-preview-placeholder">
                <n-icon :component="ImagePlus" :size="20" />
                <span>{{ currentBackgroundId ? t('nodeEditor.presentation.backgroundPreviewUnavailable') : t('nodeEditor.presentation.noBackground') }}</span>
              </div>
            </div>

            <div class="action-button-row">
              <n-button
                size="tiny"
                secondary
                :disabled="backgroundUploading || presentationGenerationBusy"
                :loading="backgroundUploading"
                @click="triggerBackgroundUpload"
              >
                <template #icon><n-icon :component="Upload" /></template>
                {{ t('nodeEditor.presentation.uploadBackground') }}
              </n-button>
              <n-button
                v-if="currentBackgroundId"
                size="tiny"
                secondary
                type="warning"
                :disabled="backgroundUploading || presentationGenerationBusy"
                @click="clearDialogueBackground"
              >
                <template #icon><n-icon :component="Eraser" /></template>
                {{ t('nodeEditor.presentation.clearBackground') }}
              </n-button>
              <n-button
                size="tiny"
                type="primary"
                secondary
                :disabled="!canGenerateBackground"
                :loading="backgroundGenerating"
                @click="generateBackgroundByAI"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateBackground') }}
              </n-button>
            </div>
            <input
              ref="backgroundFileInputRef"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              style="display: none;"
              @change="onBackgroundFileChange"
            />
          </div>

          <!-- 显式立绘选择 -->
          <div class="presentation-field-group">
            <div class="field-label-row">
              <span class="field-label">{{ t('nodeEditor.presentation.explicitSprite') }}</span>
            </div>
            <n-select
              :value="currentSpriteId || null"
              size="small"
              clearable
              filterable
              :options="characterSpriteAssetOptions"
              :placeholder="t('nodeEditor.presentation.explicitSpritePlaceholder')"
              @update:value="setDialoguePresentationValue('sprite', $event || null)"
            />
          </div>

          <!-- 完整场景插图（整合区） -->
          <div v-if="visualIllustrationEnabled" class="presentation-field-group illustration-group">
            <div class="field-label-row">
              <span class="field-label">{{ t('nodeEditor.presentation.illustration') }}</span>
              <span v-if="currentIllustrationId" class="illustration-badge">{{ currentIllustrationId }}</span>
            </div>

            <div class="participants-box">
              <div class="field-sublabel">{{ t('nodeEditor.presentation.participatingCharacters') }}</div>
              <n-select
                v-model:value="presentationCharacterIds"
                multiple
                clearable
                filterable
                size="small"
                :options="characterSelectOptions"
                :placeholder="t('nodeEditor.presentation.participatingCharactersPlaceholder')"
                @update:value="savePresentationCharacters"
              />
            </div>

            <div class="action-button-row">
              <n-button
                size="tiny"
                secondary
                :disabled="illustrationUploading || presentationGenerationBusy"
                :loading="illustrationUploading"
                @click="triggerIllustrationUpload"
              >
                <template #icon><n-icon :component="Upload" /></template>
                {{ t('nodeEditor.presentation.uploadIllustration') }}
              </n-button>
              <n-button
                v-if="currentIllustrationId"
                size="tiny"
                secondary
                type="warning"
                :disabled="illustrationUploading || presentationGenerationBusy"
                @click="clearDialogueIllustration"
              >
                <template #icon><n-icon :component="Eraser" /></template>
                {{ t('nodeEditor.presentation.clearIllustration') }}
              </n-button>
              <n-button
                size="tiny"
                type="primary"
                secondary
                :disabled="!canGenerateIllustration"
                :loading="illustrationGenerating"
                @click="generateIllustrationByAI"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateIllustration') }}
              </n-button>
            </div>
            <input
              ref="illustrationFileInputRef"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              style="display: none;"
              @change="onIllustrationFileChange"
            />
          </div>
        </div>
      </n-collapse-item>
    </n-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCollapse, NCollapseItem, NSelect, NInput, NButton, NIcon, NSpace, NText } from 'naive-ui';
import SparkTag from '../share/SparkTag.vue';
import { Eraser, ImagePlus, Images, Sparkles, Upload } from '@lucide/vue';
import bus from '@/eventBus';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useCharacterStore } from '@/components/stores/characterStore';
import {
  fetchPresentationImageModels,
  fetchPresentationManifest,
  generatePresentationBackground,
  generatePresentationIllustrationConception,
  generatePresentationIllustration,
  uploadPresentationBackground,
  uploadPresentationIllustration,
  type PresentationAsset,
  type PresentationImageModel,
  type PresentationManifest,
  getPresentationErrorMessage,
} from '@/services/presentationService';
import { createStreamingTask, isAbortLikeError } from '@/utils/streamingRuntime';
import { type ArcDialogueNode, type ArcScene, type PresentationCue } from '@/services/arcParser';

const { t } = useI18n();
const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const characterStore = useCharacterStore();

const backgroundFileInputRef = ref<HTMLInputElement | null>(null);
const illustrationFileInputRef = ref<HTMLInputElement | null>(null);
const backgroundUploading = ref(false);
const backgroundGenerating = ref(false);
const illustrationUploading = ref(false);
const illustrationGenerating = ref(false);
const illustrationConceptionGenerating = ref(false);
const backgroundPreviewFailed = ref(false);
const illustrationPrompt = ref('');
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const visualIllustrationEnabled = ref(false);
const presentationCharacterIds = ref<string[]>([]);
let presentationManifestRequestId = 0;
let localManifestRevision = 0;

const isNovelMode = computed(() => sceneStore.workspaceMode === 'novel');
const canUsePresentationTools = computed(() => !isNovelMode.value && !!projectStore.currentProject && !!sceneStore.currentScene);
const isDialogueSelected = computed(() => sceneStore.selectionType === 'dialogue' && !!currentDialogueNode.value);

const currentDialogueNode = computed<ArcDialogueNode | null>(() => {
  if (sceneStore.selectionType !== 'dialogue') return null;
  const node = sceneStore.currentNode;
  if (!node || typeof node !== 'object' || !('id' in node)) return null;
  return node as ArcDialogueNode;
});

const currentPresentation = computed<Record<string, unknown>>(() => {
  const cue = currentDialogueNode.value?.presentation;
  return cue && typeof cue === 'object' ? cue as Record<string, unknown> : {};
});

const currentBackgroundId = computed(() => normalizePresentationValue(currentPresentation.value.bg));
const currentIllustrationId = computed(() => normalizePresentationValue(currentPresentation.value.illustration));
const currentSpriteId = computed(() => normalizePresentationValue(currentPresentation.value.sprite));
const currentIllustrationPending = computed(() => (
  !normalizePresentationValue(currentPresentation.value.img ?? currentPresentation.value.illustration_prompt)
  && !currentIllustrationId.value
  && normalizePresentationValue(currentPresentation.value.pending ?? currentPresentation.value.illustration_pending).toLowerCase() === 'true'
));

const manifestAssets = computed<Record<string, PresentationAsset>>(() => {
  const assets = presentationManifest.value?.assets;
  return assets && typeof assets === 'object' ? assets : {};
});

const currentBackgroundAsset = computed(() => manifestAssets.value[currentBackgroundId.value] || null);
const currentBackgroundPreviewUrl = computed(() => (
  currentBackgroundAsset.value ? presentationAssetUrl(currentBackgroundAsset.value) : ''
));

const characterSpriteAssetOptions = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'character_sprite')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
  .map(asset => ({
    label: asset.title || asset.id,
    value: asset.id,
  })));

const backgroundAssetOptions = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'background' && asset.library === true)
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
  .map(asset => ({
    label: asset.title || asset.id,
    value: asset.id,
  })));

const characterSelectOptions = computed(() =>
  characterStore.list.map(c => ({
    label: c.name || String(c.id),
    value: String(c.id),
  }))
);

const availableImageModels = computed(() => imageModels.value.filter(model => model.api_key_set !== false));

const imageModelSelectOptions = computed(() => availableImageModels.value.map(model => ({
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

const presentationGenerationBusy = computed(() => (
  backgroundGenerating.value
  || illustrationGenerating.value
  || illustrationConceptionGenerating.value
));

const canGenerateBackground = computed(() =>
  !presentationGenerationBusy.value
  && !!projectStore.currentProject
  && !!illustrationPrompt.value.trim()
  && !!selectedImageModel.value
);

const canGenerateIllustration = computed(() =>
  !presentationGenerationBusy.value
  && visualIllustrationEnabled.value
  && !!projectStore.currentProject
  && !!illustrationPrompt.value.trim()
  && !!selectedImageModel.value
);

const canGenerateIllustrationConception = computed(() =>
  isDialogueSelected.value
  && visualIllustrationEnabled.value
  && currentIllustrationPending.value
  && !presentationGenerationBusy.value
);

watch(
  () => [
    currentDialogueNode.value?.id,
    normalizePresentationValue(currentPresentation.value.img ?? currentPresentation.value.illustration_prompt),
    normalizePresentationList(currentPresentation.value.characters).join('|'),
  ],
  () => {
    illustrationPrompt.value = normalizePresentationValue(currentPresentation.value.img ?? currentPresentation.value.illustration_prompt);
    presentationCharacterIds.value = normalizePresentationList(currentPresentation.value.characters);
  },
  { immediate: true },
);

watch(currentBackgroundPreviewUrl, () => {
  backgroundPreviewFailed.value = false;
});

function normalizePresentationValue(value: unknown): string {
  const raw = Array.isArray(value) ? value[0] : value;
  return typeof raw === 'string' ? raw.trim() : '';
}

function normalizePresentationList(value: unknown): string[] {
  const values = Array.isArray(value) ? value : (value ? [value] : []);
  return Array.from(new Set(values.map(item => String(item || '').trim()).filter(Boolean)));
}

function imageModelKey(model: PresentationImageModel) {
  return `${model.platform_id}:${model.model_id}`;
}

function presentationErrorMessage(error: unknown, fallback: string) {
  return getPresentationErrorMessage(error, fallback);
}

function presentationAssetUrl(asset: PresentationAsset) {
  if (asset.url) return asset.url;
  const projectName = encodeURIComponent(projectStore.currentProject || '');
  const path = String(asset.path || '')
    .replace(/\\/g, '/')
    .split('/')
    .filter(Boolean)
    .map(encodeURIComponent)
    .join('/');
  return projectName && path ? `/api/presentation/${projectName}/assets/${path}` : '';
}

function updateManifest(manifest: PresentationManifest | undefined | null) {
  if (manifest) {
    localManifestRevision += 1;
    presentationManifest.value = manifest;
    bus.emit('presentation-manifest-updated', {
      projectName: projectStore.currentProject,
      manifest,
    });
  }
}

async function loadPresentationImageModels() {
  if (isNovelMode.value) {
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
  if (!projectStore.currentProject || isNovelMode.value) {
    presentationManifest.value = null;
    visualIllustrationEnabled.value = false;
    return;
  }
  const requestId = ++presentationManifestRequestId;
  const revisionAtRequest = localManifestRevision;
  const projectName = projectStore.currentProject;
  try {
    const result = await fetchPresentationManifest(projectName);
    if (
      requestId !== presentationManifestRequestId
      || revisionAtRequest !== localManifestRevision
      || projectName !== projectStore.currentProject
      || isNovelMode.value
    ) return;
    presentationManifest.value = result.manifest || null;
    visualIllustrationEnabled.value = !!result.settings?.visualIllustration?.effectiveEnabled;
  } catch (_error: unknown) {
    if (requestId === presentationManifestRequestId && revisionAtRequest === localManifestRevision) {
      presentationManifest.value = null;
    }
  }
}

async function savePresentationBinding() {
  try {
    await sceneStore._saveStory?.();
  } catch (error: unknown) {
    bus.emit('toast', { type: 'warning', message: presentationErrorMessage(error, t('nodeEditor.presentation.bindingSaveFailed')) });
  }
}

type EditablePresentationKey = 'bg' | 'sprite' | 'img' | 'pending' | 'illustration_prompt' | 'illustration' | 'illustration_pending' | 'characters';
type EditablePresentationValue = string | string[] | null;

function setNodePresentationValue(
  node: ArcDialogueNode | null,
  key: EditablePresentationKey,
  value: EditablePresentationValue,
) {
  if (!node) return;
  const nextPresentation: PresentationCue = { ...(node.presentation || {}) };
  const isEmpty = value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0);
  if (isEmpty) delete nextPresentation[key];
  else nextPresentation[key] = value as any;
  const presentation = Object.keys(nextPresentation).length > 0 ? nextPresentation : undefined;
  if (node === currentDialogueNode.value) sceneStore.updateCurrentDialogue({ presentation });
  else node.presentation = presentation;
}

function setDialoguePresentationValue(key: EditablePresentationKey, value: EditablePresentationValue) {
  setNodePresentationValue(currentDialogueNode.value, key, value);
  void savePresentationBinding();
}

function triggerBackgroundUpload() {
  if (presentationGenerationBusy.value || backgroundUploading.value) return;
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  backgroundFileInputRef.value?.click();
}

async function onBackgroundFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  if (!file || !projectName || !targetNode || presentationGenerationBusy.value || backgroundUploading.value) return;
  backgroundUploading.value = true;
  try {
    const result = await uploadPresentationBackground(projectName, file, file.name);
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setNodePresentationValue(targetNode, 'bg', result.asset.id);
    await savePresentationBinding();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.uploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.uploadFailed')) });
  } finally {
    backgroundUploading.value = false;
  }
}

function clearDialogueBackground() {
  setDialoguePresentationValue('bg', null);
  bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.clearSuccess') });
}

async function generateBackgroundByAI() {
  if (presentationGenerationBusy.value) return;
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (!projectName || !targetNode || !targetScene) return;
  const prompt = illustrationPrompt.value.trim();
  const model = selectedImageModel.value;
  if (!prompt || !model) return;

  backgroundGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-background',
    text: t('nodeEditor.presentation.generateBackground'),
    progress: t('nodeEditor.presentation.generateBackground'),
    canCancel: true,
    statsMode: 'elapsed',
  });
  try {
    task.throwIfAborted();
    saveIllustrationPrompt();
    const result = await generatePresentationBackground(projectName, {
      prompt,
      title: targetNode.txt?.trim().slice(0, 18) || t('nodeEditor.presentation.generatedBackgroundTitle'),
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      context: {
        sceneName: targetScene.scene || '',
        sceneIntro: targetScene.intro || '',
        sceneConception: targetScene.thought || '',
        nodeText: String(targetNode.txt || '').trim(),
      },
    }, task.signal);
    task.throwIfAborted();
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setNodePresentationValue(targetNode, 'bg', result.asset.id);
    await savePresentationBinding();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.generateSuccess') });
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.generateFailed')) });
  } finally {
    task.dispose();
    backgroundGenerating.value = false;
  }
}

function saveIllustrationPrompt() {
  const prompt = illustrationPrompt.value.trim();
  const node = currentDialogueNode.value;
  if (!node) return;
  const nextPresentation: PresentationCue = { ...(node.show || node.presentation || {}) };
  if (prompt) {
    nextPresentation.img = prompt;
    delete nextPresentation.pending;
    delete nextPresentation.illustration_prompt;
    delete nextPresentation.illustration_pending;
  } else {
    delete nextPresentation.img;
    delete nextPresentation.illustration_prompt;
  }
  node.presentation = Object.keys(nextPresentation).length > 0 ? nextPresentation : undefined;
  node.show = node.presentation;
  sceneStore.updateCurrentDialogue({ presentation: node.presentation });
  void savePresentationBinding();
}

function savePresentationCharacters() {
  setDialoguePresentationValue('characters', presentationCharacterIds.value.length > 0 ? presentationCharacterIds.value : null);
}

function triggerIllustrationUpload() {
  if (presentationGenerationBusy.value || illustrationUploading.value || !projectStore.currentProject || !visualIllustrationEnabled.value) return;
  illustrationFileInputRef.value?.click();
}

async function onIllustrationFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (!file || !projectName || !targetNode || !targetScene || presentationGenerationBusy.value || illustrationUploading.value) return;
  illustrationUploading.value = true;
  try {
    saveIllustrationPrompt();
    const result = await uploadPresentationIllustration(projectName, file, {
      title: file.name,
      sceneName: targetScene.scene || '',
      nodeId: String(targetNode.id),
    });
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setNodePresentationValue(targetNode, 'illustration', result.asset.id);
    await savePresentationBinding();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.uploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.uploadFailed')) });
  } finally {
    illustrationUploading.value = false;
  }
}

function clearDialogueIllustration() {
  setDialoguePresentationValue('illustration', null);
  bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.clearSuccess') });
}

async function generateIllustrationByAI() {
  if (presentationGenerationBusy.value) return;
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (!projectName || !targetNode || !targetScene) return;
  const prompt = illustrationPrompt.value.trim();
  const model = selectedImageModel.value;
  if (!prompt || !model) return;

  illustrationGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-illustration',
    text: t('nodeEditor.presentation.generateIllustration'),
    progress: t('nodeEditor.presentation.generateIllustration'),
    canCancel: true,
    statsMode: 'elapsed',
  });
  try {
    task.throwIfAborted();
    saveIllustrationPrompt();
    const result = await generatePresentationIllustration(projectName, {
      prompt,
      title: targetNode.txt?.trim().slice(0, 18) || t('nodeEditor.presentation.generatedIllustrationTitle'),
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      sceneName: targetScene.scene || '',
      nodeId: String(targetNode.id),
      context: {
        sceneName: targetScene.scene || '',
        sceneIntro: targetScene.intro || '',
        sceneConception: targetScene.thought || '',
        nodeText: String(targetNode.txt || '').trim(),
      },
    }, task.signal);
    task.throwIfAborted();
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setNodePresentationValue(targetNode, 'illustration', result.asset.id);
    await savePresentationBinding();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.generateSuccess') });
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.generateFailed')) });
  } finally {
    task.dispose();
    illustrationGenerating.value = false;
  }
}

async function generateIllustrationConceptionByAI() {
  if (presentationGenerationBusy.value) return;
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (!projectName || !targetNode || !targetScene) return;

  illustrationConceptionGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-conception',
    text: t('nodeEditor.presentation.generateIllustrationConception'),
    progress: t('nodeEditor.presentation.generateIllustrationConception'),
    canCancel: true,
    statsMode: 'elapsed',
  });
  try {
    task.throwIfAborted();
    const result = await generatePresentationIllustrationConception(projectName, {
      sceneName: targetScene.scene || '',
      nodeId: String(targetNode.id),
      context: {
        sceneName: targetScene.scene || '',
        sceneIntro: targetScene.intro || '',
        sceneConception: targetScene.thought || '',
        nodeText: String(targetNode.txt || '').trim(),
      },
    }, task.signal);
    task.throwIfAborted();
    if (result.prompt) {
      illustrationPrompt.value = result.prompt;
      saveIllustrationPrompt();
      bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.generateSuccess') });
    }
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.generateFailed')) });
  } finally {
    task.dispose();
    illustrationConceptionGenerating.value = false;
  }
}

onMounted(() => {
  void loadPresentationImageModels();
  void loadPresentationManifest();
});
</script>

<style scoped>
.node-presentation-section {
  margin-top: 10px;
  width: 100%;
}

.presentation-section-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: var(--spark-fs-sm, 13px);
  color: var(--spark-text);
}

.presentation-content-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

.presentation-field-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 500;
  color: var(--spark-text);
}

.field-sublabel {
  font-size: var(--spark-fs-2xs, 11px);
  color: var(--spark-text-muted);
  margin-bottom: 4px;
}

.field-hint-text {
  font-size: var(--spark-fs-2xs, 11px);
}

.background-preview-box {
  width: 100%;
  height: 100px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.04);
  border: 1px dashed var(--spark-border);
  display: flex;
  align-items: center;
  justify-content: center;
}

.background-preview-box img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.background-preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs, 11px);
}

.action-button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.illustration-badge {
  font-size: var(--spark-fs-2xs, 11px);
  padding: 1px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--spark-primary) 15%, transparent);
  color: var(--spark-primary);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.participants-box {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
