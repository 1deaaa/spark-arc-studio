<template>
  <div v-if="isScriptMode" class="project-style-toolbox" :class="{ 'is-embedded': embedded }">
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
        <div class="visual-illustration-setting">
          <div class="visual-illustration-setting__copy">
            <n-text strong>{{ t('components.lorebookEditor.visualIllustrationTitle') }}</n-text>
            <n-text depth="3" class="project-style-tip">
              {{ t('components.lorebookEditor.visualIllustrationHint') }}
            </n-text>
            <n-text v-if="missingCharacterSprites.length" type="warning" class="project-style-tip">
              {{ t('components.lorebookEditor.missingCharacterSprites', { count: missingCharacterSprites.length }) }}
            </n-text>
          </div>
          <n-switch
            v-model:value="visualIllustrationEnabled"
            :loading="presentationSettingsSaving"
            @update:value="saveVisualIllustrationEnabled"
          />
        </div>

        <n-text depth="3" class="project-style-tip">
          {{ t('components.lorebookEditor.projectStyleHint') }}
        </n-text>

        <div class="style-reference-list">
          <button
            v-for="asset in projectStyleReferenceAssets"
            :key="asset.id"
            type="button"
            class="style-reference-candidate"
            :class="{ 'is-selected': selectedProjectStyleReferenceIds.includes(asset.id) }"
            :aria-pressed="selectedProjectStyleReferenceIds.includes(asset.id)"
            :title="asset.title || asset.id"
            @click="toggleProjectStyleReference(asset.id)"
          >
            <img :src="presentationAssetUrl(asset)" :alt="asset.title || asset.id" />
            <span>{{ asset.title || asset.id }}</span>
            <n-icon v-if="selectedProjectStyleReferenceIds.includes(asset.id)" :component="Check" />
          </button>
          <n-text v-if="projectStyleReferenceAssets.length === 0" depth="3">
            {{ t('components.lorebookEditor.noStyleReferenceAssets') }}
          </n-text>
        </div>

        <n-select
          v-model:value="selectedProjectStyleReferenceIds"
          size="small"
          clearable
          multiple
          :max-tag-count="5"
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
          <n-button secondary :loading="styleReferenceUploading" @click="triggerStyleReferenceUpload">
            <template #icon>
              <n-icon :component="Upload" />
            </template>
            {{ t('nodeEditor.presentation.uploadStyleReference') }}
          </n-button>
          <n-button
            type="primary"
            :loading="presentationSettingsSaving"
            :disabled="!styleReferencePrompt.trim() && selectedProjectStyleReferenceIds.length === 0"
            @click="saveProjectVisualStyle"
          >
            <template #icon>
              <n-icon :component="Save" />
            </template>
            {{ t('components.lorebookEditor.saveProjectStyle') }}
          </n-button>
        </n-space>

        <section class="background-library-section">
          <div class="background-library-heading">
            <n-text strong>{{ t('nodeEditor.presentation.backgroundLibraryTitle') }}</n-text>
            <n-text depth="3" class="project-style-tip">
              {{ t('nodeEditor.presentation.backgroundLibraryHint') }}
            </n-text>
          </div>

          <div class="background-library-list">
            <button
              v-for="asset in projectBackgroundAssets"
              :key="asset.id"
              type="button"
              class="style-reference-candidate"
              :class="{ 'is-selected': selectedBackgroundReferenceId === asset.id }"
              :aria-pressed="selectedBackgroundReferenceId === asset.id"
              :title="asset.title || asset.id"
              @click="selectedBackgroundReferenceId = selectedBackgroundReferenceId === asset.id ? null : asset.id"
            >
              <img :src="presentationAssetUrl(asset)" :alt="asset.title || asset.id" />
              <span>{{ asset.title || asset.id }}</span>
              <n-icon v-if="selectedBackgroundReferenceId === asset.id" :component="Check" />
            </button>
            <n-text v-if="projectBackgroundAssets.length === 0" depth="3">
              {{ t('nodeEditor.presentation.backgroundLibraryEmpty') }}
            </n-text>
          </div>

          <StudioSeamlessTextarea
            v-model:value="backgroundLibraryPrompt"
            :autosize="{ minRows: 3, maxRows: 6 }"
            :placeholder="t('nodeEditor.presentation.backgroundLibraryPromptPlaceholder')"
            :show-count="true"
            :maxlength="900"
          />

          <n-space justify="end" :size="8" wrap>
            <n-button secondary :loading="backgroundLibraryUploading" @click="triggerBackgroundLibraryUpload">
              <template #icon><n-icon :component="Upload" /></template>
              {{ t('nodeEditor.presentation.uploadLibraryBackground') }}
            </n-button>
            <n-button
              type="primary"
              secondary
              :loading="backgroundLibraryGenerating"
              :disabled="!canGenerateProjectBackground"
              @click="generateProjectBackground"
            >
              <template #icon><n-icon :component="Sparkles" /></template>
              {{ t('nodeEditor.presentation.generateLibraryBackground') }}
            </n-button>
          </n-space>
          <input
            ref="backgroundLibraryFileInputRef"
            class="style-hidden-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="onBackgroundLibraryFileChange"
          />
        </section>

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
import { NButton, NCard, NIcon, NSelect, NSpace, NSwitch, NText } from 'naive-ui';
import { Check, Save, Sparkles, Upload } from '@lucide/vue';
import StudioSeamlessTextarea from '@/components/editors/StudioSeamlessTextarea.vue';
import bus from '@/eventBus';
import {
  fetchPresentationImageModels,
  fetchPresentationManifest,
  generatePresentationBackground,
  generatePresentationReference,
  updatePresentationSettings,
  uploadPresentationReference,
  uploadPresentationBackground,
  type PresentationAsset,
  type PresentationImageModel,
  type PresentationManifest,
  type PresentationReferenceDescriptor,
} from '@/services/presentationService';
import { supportsImageInput } from '@/services/modelModalities';
import { useProjectStore } from '@/components/stores/projectStore';
import { useSceneStore } from '@/components/stores/sceneStore';

defineProps({
  embedded: { type: Boolean, default: false },
});

const projectStore = useProjectStore();
const sceneStore = useSceneStore();
const { t } = useI18n();

const styleReferenceFileInputRef = ref<HTMLInputElement | null>(null);
const styleReferenceUploading = ref(false);
const styleReferenceGenerating = ref(false);
const styleReferencePrompt = ref('');
const backgroundLibraryPrompt = ref('');
const backgroundLibraryGenerating = ref(false);
const backgroundLibraryUploading = ref(false);
const backgroundLibraryFileInputRef = ref<HTMLInputElement | null>(null);
const selectedBackgroundReferenceId = ref<string | null>(null);
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const selectedProjectStyleReferenceIds = ref<string[]>([]);
const visualIllustrationEnabled = ref(false);
const presentationSettingsSaving = ref(false);
const missingCharacterSprites = ref<Array<{ id: string; name: string }>>([]);
const isScriptMode = computed(() => sceneStore.workspaceMode === 'script');

const manifestAssets = computed<Record<string, PresentationAsset>>(() => {
  const assets = presentationManifest.value?.assets;
  return assets && typeof assets === 'object' ? assets : {};
});

const projectStyleReferenceAssets = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'style_reference')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || ''))));

const projectBackgroundAssets = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'background' && asset.library === true)
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || ''))));

const styleReferenceOptions = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'style_reference')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
  .map(asset => ({
    label: `${t('nodeEditor.presentation.styleReference')} · ${asset.title || asset.id}`,
    value: asset.id,
    disabled: selectedProjectStyleReferenceIds.value.length >= 5
      && !selectedProjectStyleReferenceIds.value.includes(asset.id),
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
  isScriptMode.value
  && !!projectStore.currentProject
  && !!styleReferencePrompt.value.trim()
  && !!selectedImageModel.value
);

const canGenerateProjectBackground = computed(() =>
  isScriptMode.value
  && !!projectStore.currentProject
  && !!backgroundLibraryPrompt.value.trim()
  && !!selectedImageModel.value
);

watch([() => projectStore.currentProject, () => sceneStore.workspaceMode], () => {
  styleReferencePrompt.value = '';
  selectedProjectStyleReferenceIds.value = [];
  visualIllustrationEnabled.value = false;
  missingCharacterSprites.value = [];
  if (!isScriptMode.value) {
    presentationManifest.value = null;
    imageModels.value = [];
    selectedImageModelKey.value = null;
    return;
  }
  void loadPresentationManifest();
  void loadPresentationImageModels();
}, { immediate: true });

function imageModelKey(model: PresentationImageModel) {
  return `${model.platform_id}:${model.model_id}`;
}

function imageModelSupportsReference(model: PresentationImageModel | null) {
  return supportsImageInput(model);
}

function presentationErrorMessage(error: unknown, fallback: string) {
  if (error instanceof Error && error.message.trim()) return error.message;
  const raw = String(error || '').trim();
  return raw || fallback;
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

async function loadPresentationImageModels() {
  if (!isScriptMode.value) return;
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
    selectedProjectStyleReferenceIds.value = [];
    return;
  }
  try {
    const result = await fetchPresentationManifest(projectStore.currentProject);
    presentationManifest.value = result.manifest || null;
    styleReferencePrompt.value = result.settings?.visualStyle?.seed_prompt || '';
    selectedProjectStyleReferenceIds.value = (result.settings?.visualStyle?.reference_asset_ids || [])
      .filter(assetId => manifestAssets.value[assetId]?.type === 'style_reference')
      .slice(0, 5);
    visualIllustrationEnabled.value = !!result.settings?.visualIllustration?.enabled;
    missingCharacterSprites.value = result.settings?.readiness?.missingCharacterSprites || [];
  } catch {
    presentationManifest.value = null;
  }
}

async function saveVisualIllustrationEnabled(enabled: boolean) {
  if (!projectStore.currentProject || !isScriptMode.value) return;
  presentationSettingsSaving.value = true;
  try {
    const result = await updatePresentationSettings(projectStore.currentProject, {
      visualIllustrationEnabled: enabled,
    });
    visualIllustrationEnabled.value = !!result.settings?.visualIllustration?.enabled;
    bus.emit('presentation-settings-updated', { projectName: projectStore.currentProject });
    bus.emit('toast', { type: 'success', message: t('components.lorebookEditor.visualIllustrationSaved') });
  } catch (error: unknown) {
    visualIllustrationEnabled.value = !enabled;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('components.lorebookEditor.visualIllustrationSaveFailed')) });
  } finally {
    presentationSettingsSaving.value = false;
  }
}

async function saveProjectVisualStyle() {
  if (!projectStore.currentProject || !isScriptMode.value) return;
  presentationSettingsSaving.value = true;
  try {
    await updatePresentationSettings(projectStore.currentProject, {
      styleSeedPrompt: styleReferencePrompt.value.trim(),
      styleReferenceAssetIds: selectedProjectStyleReferenceIds.value.slice(0, 5),
    });
    bus.emit('presentation-settings-updated', { projectName: projectStore.currentProject });
    bus.emit('toast', { type: 'success', message: t('components.lorebookEditor.projectStyleSaved') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('components.lorebookEditor.projectStyleSaveFailed')) });
  } finally {
    presentationSettingsSaving.value = false;
  }
}

function updatePresentationManifest(manifest: PresentationManifest | undefined | null) {
  if (manifest) {
    presentationManifest.value = manifest;
    bus.emit('presentation-manifest-updated', { projectName: projectStore.currentProject });
  }
}

function projectStyleReferenceAssetIds() {
  const model = selectedImageModel.value;
  if (!imageModelSupportsReference(model)) return [];
  return selectedProjectStyleReferenceIds.value.slice(0, 5);
}

function toggleProjectStyleReference(assetId: string) {
  if (selectedProjectStyleReferenceIds.value.includes(assetId)) {
    selectedProjectStyleReferenceIds.value = selectedProjectStyleReferenceIds.value.filter(id => id !== assetId);
    return;
  }
  if (selectedProjectStyleReferenceIds.value.length < 5) {
    selectedProjectStyleReferenceIds.value = [...selectedProjectStyleReferenceIds.value, assetId];
  }
}

function includeNewProjectStyleReference(assetId: string) {
  if (!assetId || selectedProjectStyleReferenceIds.value.includes(assetId)) return;
  if (selectedProjectStyleReferenceIds.value.length < 5) {
    selectedProjectStyleReferenceIds.value = [...selectedProjectStyleReferenceIds.value, assetId];
  }
}

function projectBackgroundReferences(): PresentationReferenceDescriptor[] {
  const model = selectedImageModel.value;
  if (!model || !imageModelSupportsReference(model) || !selectedBackgroundReferenceId.value) return [];
  return [{ assetId: selectedBackgroundReferenceId.value, role: 'scene' }];
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
    includeNewProjectStyleReference(result.asset.id);
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.styleReferenceUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.styleReferenceUploadFailed')) });
  } finally {
    styleReferenceUploading.value = false;
  }
}

async function generateStyleReferenceByAI() {
  if (!projectStore.currentProject || !isScriptMode.value) {
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
      prompt: styleReferencePrompt.value.trim(),
      title: t('nodeEditor.presentation.generatedStyleReferenceTitle'),
      assetType: 'style_reference',
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssetIds: projectStyleReferenceAssetIds(),
    });
    updatePresentationManifest(result.manifest);
    includeNewProjectStyleReference(result.asset.id);
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.styleReferenceGenerateSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.styleReferenceGenerateFailed')) });
  } finally {
    styleReferenceGenerating.value = false;
  }
}

async function generateProjectBackground() {
  const projectName = projectStore.currentProject;
  const model = selectedImageModel.value;
  const prompt = backgroundLibraryPrompt.value.trim();
  if (!projectName || !model || !prompt) return;
  backgroundLibraryGenerating.value = true;
  try {
    const result = await generatePresentationBackground(projectName, {
      prompt,
      title: prompt.slice(0, 24),
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssets: projectBackgroundReferences(),
      context: { characterIds: [] },
      library: true,
    });
    updatePresentationManifest(result.manifest);
    selectedBackgroundReferenceId.value = result.asset?.id || null;
    backgroundLibraryPrompt.value = '';
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.backgroundLibraryGenerateSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.backgroundLibraryGenerateFailed')) });
  } finally {
    backgroundLibraryGenerating.value = false;
  }
}

function triggerBackgroundLibraryUpload() {
  if (!projectStore.currentProject) return;
  backgroundLibraryFileInputRef.value?.click();
}

async function onBackgroundLibraryFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  if (!file || !projectStore.currentProject) return;
  backgroundLibraryUploading.value = true;
  try {
    const result = await uploadPresentationBackground(projectStore.currentProject, file, file.name, true);
    updatePresentationManifest(result.manifest);
    selectedBackgroundReferenceId.value = result.asset?.id || null;
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.backgroundLibraryUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.backgroundLibraryUploadFailed')) });
  } finally {
    backgroundLibraryUploading.value = false;
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

.visual-illustration-setting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--spark-border-soft);
}

.visual-illustration-setting__copy {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.project-style-tip {
  font-size: var(--spark-fs-xs);
  line-height: 1.55;
}

.style-reference-list {
  min-height: 82px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
  gap: 6px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 42%, transparent);
}

.style-reference-candidate {
  position: relative;
  min-width: 0;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  background: var(--spark-panel-bg);
  color: var(--spark-text);
  cursor: pointer;
  text-align: left;
}

.style-reference-candidate img {
  display: block;
  width: 100%;
  aspect-ratio: 3 / 2;
  object-fit: cover;
  background: var(--spark-bg);
}

.style-reference-candidate span {
  display: block;
  padding: 5px 7px;
  overflow: hidden;
  font-size: var(--spark-fs-2xs);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.style-reference-candidate > :deep(.n-icon) {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--spark-primary);
  color: white;
}

.style-reference-candidate.is-selected {
  border-color: var(--spark-primary);
  box-shadow: 0 0 0 1px var(--spark-primary);
}

.style-reference-candidate:focus-visible {
  outline: 2px solid var(--spark-primary);
  outline-offset: 2px;
}

.style-hidden-input {
  display: none;
}

.background-library-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--spark-border-soft);
}

.background-library-heading {
  display: grid;
  gap: 4px;
}

.background-library-list {
  min-height: 82px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(104px, 1fr));
  gap: 6px;
  padding: 8px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 42%, transparent);
}
</style>
