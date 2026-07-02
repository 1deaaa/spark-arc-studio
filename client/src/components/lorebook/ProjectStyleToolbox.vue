<template>
  <div class="project-style-toolbox" :class="{ 'is-embedded': embedded }">
    <n-card
      :title="t('components.lorebookEditor.projectStyleTitle')"
      :segmented="{ content: true }"
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-button
          size="tiny"
          type="primary"
          :loading="styleReferenceGenerating"
          :disabled="!canGenerateStyleReference"
          @click="generateStyleReferenceByAI"
        >
          <template #icon>
            <n-icon :component="Sparkles" />
          </template>
          {{ t('nodeEditor.presentation.generateStyleReference') }}
        </n-button>
      </template>

      <div class="project-style-body">
        <n-text depth="3" class="project-style-tip">
          {{ t('components.lorebookEditor.projectStyleHint') }}
        </n-text>

        <div class="style-reference-list">
          <n-tag
            v-for="asset in projectStyleReferenceAssets"
            :key="asset.id"
            size="small"
            :bordered="false"
            type="success"
          >
            {{ asset.title || asset.id }}
          </n-tag>
          <n-text v-if="projectStyleReferenceAssets.length === 0" depth="3">
            {{ t('components.lorebookEditor.noStyleReferenceAssets') }}
          </n-text>
        </div>

        <n-select
          v-model:value="selectedProjectStyleReferenceId"
          size="small"
          clearable
          :options="styleReferenceOptions"
          :placeholder="t('components.lorebookEditor.styleReferencePlaceholder')"
        />

        <n-select
          v-model:value="selectedImageModelKey"
          size="small"
          clearable
          :loading="imageModelsLoading"
          :options="imageModelOptions"
          :placeholder="t('nodeEditor.presentation.imageModelPlaceholder')"
        />

        <StudioSeamlessTextarea
          v-model:value="styleReferencePrompt"
          :autosize="{ minRows: 5, maxRows: 9 }"
          :placeholder="t('components.lorebookEditor.projectStylePromptPlaceholder')"
          :show-count="true"
          :maxlength="900"
        />

        <n-space justify="end" :size="8" wrap>
          <n-button secondary @click="rollStyleReferencePrompt">
            <template #icon>
              <n-icon :component="Sparkles" />
            </template>
            {{ t('nodeEditor.presentation.rollStyleReference') }}
          </n-button>
          <n-button secondary :loading="styleReferenceUploading" @click="triggerStyleReferenceUpload">
            <template #icon>
              <n-icon :component="Upload" />
            </template>
            {{ t('nodeEditor.presentation.uploadStyleReference') }}
          </n-button>
        </n-space>

        <input
          ref="styleReferenceFileInputRef"
          class="style-hidden-input"
          type="file"
          accept="image/png,image/jpeg,image/webp"
          @change="onStyleReferenceFileChange"
        />
      </div>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NCard, NIcon, NSelect, NSpace, NTag, NText } from 'naive-ui';
import { Sparkles, Upload } from '@lucide/vue';
import StudioSeamlessTextarea from '@/components/editors/StudioSeamlessTextarea.vue';
import bus from '@/eventBus';
import { fetchCharacters, fetchWithAuth } from '@/services/api';
import {
  fetchPresentationImageModels,
  fetchPresentationManifest,
  generatePresentationReference,
  uploadPresentationReference,
  type PresentationAsset,
  type PresentationImageModel,
  type PresentationManifest,
} from '@/services/presentationService';
import { useProjectStore } from '@/components/stores/projectStore';
import type { StoryCharacterDetail } from '@/services/aiContracts';
import { buildCreativeCacheKey, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';

defineProps({
  embedded: { type: Boolean, default: false },
});

const projectStore = useProjectStore();
const { t } = useI18n();

const styleReferenceFileInputRef = ref<HTMLInputElement | null>(null);
const styleReferenceUploading = ref(false);
const styleReferenceGenerating = ref(false);
const styleReferencePrompt = ref('');
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const selectedProjectStyleReferenceId = ref<string | null>(null);

const manifestAssets = computed<Record<string, PresentationAsset>>(() => {
  const assets = presentationManifest.value?.assets;
  return assets && typeof assets === 'object' ? assets : {};
});

const projectStyleReferenceAssets = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'style_reference')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || ''))));

const styleReferenceOptions = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'style_reference' || asset.type === 'scene_reference')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
  .map(asset => ({
    label: `${asset.type === 'style_reference' ? t('nodeEditor.presentation.styleReference') : t('nodeEditor.presentation.sceneReference')} · ${asset.title || asset.id}`,
    value: asset.id,
  })));

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

const canGenerateStyleReference = computed(() =>
  !!projectStore.currentProject
  && !!styleReferencePrompt.value.trim()
  && !!selectedImageModel.value
);

function buildPromptCacheKey(projectName = projectStore.currentProject) {
  return buildCreativeCacheKey('project-style-reference-prompt', projectName);
}

watch(styleReferencePrompt, (value) => {
  if (!projectStore.currentProject) return;
  saveCreativeCache(buildPromptCacheKey(), value);
});

watch(() => projectStore.currentProject, (projectName) => {
  styleReferencePrompt.value = loadCreativeCache<string>(buildPromptCacheKey(projectName)) || '';
  void loadPresentationManifest();
  void loadPresentationImageModels();
}, { immediate: true });

function imageModelKey(model: PresentationImageModel) {
  return `${model.platform_id}:${model.model_id}`;
}

function imageModelSupportsReference(model: PresentationImageModel | null) {
  const capabilities = Array.isArray(model?.capabilities) ? model.capabilities : [];
  return capabilities.includes('image_reference_input') || capabilities.includes('image_edit');
}

function presentationErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) return error.message;
  const raw = String(error || '').trim();
  return raw || fallback;
}

function compactPromptText(value: unknown, maxLength = 2400) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

async function loadPresentationImageModels() {
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
  if (!projectStore.currentProject) {
    presentationManifest.value = null;
    selectedProjectStyleReferenceId.value = null;
    return;
  }
  try {
    const result = await fetchPresentationManifest(projectStore.currentProject);
    presentationManifest.value = result.manifest || null;
    if (selectedProjectStyleReferenceId.value && !manifestAssets.value[selectedProjectStyleReferenceId.value]) {
      selectedProjectStyleReferenceId.value = null;
    }
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

const STYLE_REFERENCE_SEEDS = [
  '现代都市悬疑视觉小说风格，冷暖对比明显，雨夜霓虹，电影感镜头，细腻写实插画。',
  '青春校园奇幻风格，柔和日光，干净线条，轻微胶片颗粒，温暖但带一点神秘感。',
  '近未来低饱和科幻风格，玻璃与金属材质，蓝绿环境光，静谧、克制、精密。',
  '东方幻想志怪风格，雾气、纸灯、木质建筑、低对比水墨色彩，细节精致。',
  '治愈系日常视觉小说风格，明亮自然光，浅景深，空气感强，色彩清透。',
];

function rollStyleReferencePrompt() {
  const index = Math.floor(Math.random() * STYLE_REFERENCE_SEEDS.length);
  styleReferencePrompt.value = STYLE_REFERENCE_SEEDS[index];
}

async function buildActiveContext() {
  const projectName = projectStore.currentProject;
  if (!projectName) return { worldview: '', characters: [] as StoryCharacterDetail[] };

  let worldview = '';
  let characters: StoryCharacterDetail[] = [];

  try {
    const res = await fetchWithAuth(`/api/worldview/${encodeURIComponent(projectName)}`);
    if (res.ok) {
      const data = await res.json();
      worldview = String(data?.content || '').trim();
    }
  } catch {}

  try {
    characters = await fetchCharacters(projectName, true) as StoryCharacterDetail[];
  } catch {
    characters = [];
  }

  return { worldview, characters };
}

async function buildProjectStyleReferencePrompt() {
  const styleAsset = selectedProjectStyleReferenceId.value ? manifestAssets.value[selectedProjectStyleReferenceId.value] : null;
  const { worldview, characters } = await buildActiveContext();
  const characterSummary = (characters || [])
    .filter(ch => ![-1, -2].includes(Number(ch.id)))
    .slice(0, 8)
    .map(ch => `- ${ch.name || t('components.lorebookEditor.characterN', { n: ch.id })}：${compactPromptText(ch.content, 220)}`)
    .join('\n');
  return [
    '你正在为整个 Web 视觉小说项目生成项目级风格参考图。它不是正式背景，也不是角色立绘，而是后续背景、场景参考、角色立绘图生图时用于固定画风的一张锚点图。',
    '请优先利用自然语言语义理解，把项目主题、世界观气质、角色群像倾向转化为稳定的视觉语言。',
    '画面重点：色彩体系、光照、材质、时代感、镜头语言、整体情绪和绘制/摄影质感；可以出现一处代表性空间或氛围场景，但不要出现 UI、字幕、水印、标题字或大段文字。',
    '画幅：1536x1024，横版；主体与关键视觉信息保持在中心安全区，方便后续 PC 与手机端演出复用。',
    styleAsset ? `已有风格参考：${styleAsset.title || styleAsset.id}` : '',
    worldview ? `世界观设定：${compactPromptText(worldview, 2600)}` : '',
    characterSummary ? `主要角色摘要：\n${characterSummary}` : '',
    `用户具体风格要求：${styleReferencePrompt.value.trim()}`,
  ].filter(Boolean).join('\n');
}

function projectStyleReferenceAssetIds() {
  const model = selectedImageModel.value;
  if (!imageModelSupportsReference(model)) return [];
  const ids = new Set<string>();
  if (selectedProjectStyleReferenceId.value) ids.add(selectedProjectStyleReferenceId.value);
  const latestStyle = projectStyleReferenceAssets.value[0];
  if (latestStyle?.id) ids.add(latestStyle.id);
  return Array.from(ids).slice(0, 4);
}

function triggerStyleReferenceUpload() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  styleReferenceFileInputRef.value?.click();
}

async function onStyleReferenceFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  if (!file || !projectStore.currentProject) return;
  styleReferenceUploading.value = true;
  try {
    const result = await uploadPresentationReference(projectStore.currentProject, file, {
      title: file.name,
      assetType: 'style_reference',
    });
    updatePresentationManifest(result.manifest);
    selectedProjectStyleReferenceId.value = result.asset.id;
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.styleReferenceUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.styleReferenceUploadFailed')) });
  } finally {
    styleReferenceUploading.value = false;
  }
}

async function generateStyleReferenceByAI() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  const model = selectedImageModel.value;
  if (!styleReferencePrompt.value.trim()) {
    bus.emit('toast', { type: 'warning', message: t('components.lorebookEditor.projectStylePromptRequired') });
    return;
  }
  if (!model) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.imageModelMissing') });
    return;
  }
  styleReferenceGenerating.value = true;
  try {
    const result = await generatePresentationReference(projectStore.currentProject, {
      prompt: await buildProjectStyleReferencePrompt(),
      title: t('nodeEditor.presentation.generatedStyleReferenceTitle'),
      assetType: 'style_reference',
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssetIds: projectStyleReferenceAssetIds(),
    });
    updatePresentationManifest(result.manifest);
    selectedProjectStyleReferenceId.value = result.asset.id;
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.styleReferenceGenerateSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.styleReferenceGenerateFailed')) });
  } finally {
    styleReferenceGenerating.value = false;
  }
}

function onPresentationManifestUpdated(payload?: unknown) {
  const projectName = payload && typeof payload === 'object' && 'projectName' in payload
    ? String((payload as { projectName?: unknown }).projectName || '')
    : '';
  if (projectName && projectName !== projectStore.currentProject) return;
  void loadPresentationManifest();
}

onMounted(() => {
  bus.on('presentation-manifest-updated', onPresentationManifestUpdated);
});

onBeforeUnmount(() => {
  bus.off('presentation-manifest-updated', onPresentationManifestUpdated);
});

onActivated(() => {
  void loadPresentationManifest();
  void loadPresentationImageModels();
});
</script>

<style scoped>
.project-style-toolbox {
  padding: 0;
}

.project-style-toolbox.is-embedded :deep(.n-card) {
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius) !important;
  box-shadow: none !important;
}

.project-style-toolbox.is-embedded :deep(.n-card__header) {
  padding: 8px 8px 6px !important;
}

.project-style-toolbox.is-embedded :deep(.n-card-header__main) {
  font-size: var(--spark-fs-base);
  line-height: 1.2;
}

.project-style-toolbox.is-embedded :deep(.n-card-content) {
  padding: 8px !important;
}

.project-style-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.project-style-tip {
  font-size: var(--spark-fs-xs);
  line-height: 1.55;
}

.style-reference-list {
  min-height: 34px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 42%, transparent);
}

.style-hidden-input {
  display: none;
}
</style>
