<template>
  <div id="ai-screenwriter" class="right-panel-section" v-show="visible">
    <n-card 
      :title="t('nodeEditor.presentation.toolboxTitle')"
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="SquarePen" size="20" />
      </template>

      <n-form class="toolbox-form" label-placement="top" size="medium">
        <section v-if="canUsePresentationTools" class="toolbox-module image-generation-module">
          <div class="toolbox-module-heading">
            <n-icon :component="Images" />
            <span>{{ t('nodeEditor.presentation.imageGenerationModule') }}</span>
          </div>

          <div class="presentation-model-control">
            <div class="toolbox-field-label">{{ t('nodeEditor.presentation.imageModelLabel') }}</div>
            <n-select
              v-model:value="selectedImageModelKey"
              class="presentation-wide-select"
              size="small"
              clearable
              :loading="imageModelsLoading"
              :disabled="presentationGenerationBusy"
              :options="imageModelSelectOptions"
              :placeholder="t('nodeEditor.presentation.imageModelPlaceholder')"
            />
            <n-text v-if="!imageModelsLoading && availableImageModels.length === 0" depth="3" class="presentation-tool-tip">
              {{ t('nodeEditor.presentation.imageModelMissing') }}
            </n-text>
            <n-text v-if="selectedImageModel && !imageModelSupportsReference(selectedImageModel)" depth="3" class="presentation-tool-tip">
              {{ t('nodeEditor.presentation.imageModelTextOnlyHint') }}
            </n-text>
          </div>

          <div v-if="canEditPresentation" class="presentation-tool-stack">
            <div class="presentation-tool-heading">
              <n-icon :component="ImagePlus" />
              <span>{{ t('nodeEditor.presentation.background') }}</span>
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
            <div class="background-preview" :class="{ 'is-empty': !currentBackgroundPreviewUrl || backgroundPreviewFailed }">
              <img
                v-if="currentBackgroundPreviewUrl && !backgroundPreviewFailed"
                :src="currentBackgroundPreviewUrl"
                :alt="t('nodeEditor.presentation.background')"
                @error="backgroundPreviewFailed = true"
              />
              <div v-else class="background-preview-empty">
                <n-icon :component="ImagePlus" />
                <span>
                  {{ currentBackgroundId
                    ? t('nodeEditor.presentation.backgroundPreviewUnavailable')
                    : t('nodeEditor.presentation.noBackground') }}
                </span>
                </div>
            </div>
            <div class="toolbox-field-label">{{ t('nodeEditor.presentation.explicitSprite') }}</div>
            <n-select
              :value="currentSpriteId || null"
              size="small"
              clearable
              filterable
              :options="characterSpriteAssetOptions"
              :placeholder="t('nodeEditor.presentation.explicitSpritePlaceholder')"
              @update:value="setDialoguePresentationValue('sprite', $event || null)"
            />
            <div class="toolbox-field-label">{{ t('nodeEditor.presentation.conceptionLabel') }}</div>
            <n-input
              v-model:value="illustrationPrompt"
              type="textarea"
              size="small"
              :autosize="{ minRows: 2, maxRows: 4 }"
              :placeholder="t('nodeEditor.presentation.conceptionPlaceholder')"
              @blur="saveIllustrationPrompt"
            />
            <n-space v-if="currentIllustrationPending" :size="8" wrap align="center">
              <n-tag type="warning" size="small" :bordered="false">
                {{ t('nodeEditor.presentation.illustrationPending') }}
              </n-tag>
              <n-button
                size="small"
                type="primary"
                secondary
                :disabled="!canGenerateIllustrationConception"
                :loading="illustrationConceptionGenerating"
                @click="generateIllustrationConceptionByAI"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateIllustrationConception') }}
              </n-button>
            </n-space>
            <div v-if="visualIllustrationEnabled" class="presentation-participants">
              <div class="toolbox-field-label">{{ t('nodeEditor.presentation.participatingCharacters') }}</div>
              <n-select
                v-model:value="presentationCharacterIds"
                multiple
                clearable
                filterable
                size="small"
                :options="characterOptions"
                :placeholder="t('nodeEditor.presentation.participatingCharactersPlaceholder')"
                @update:value="savePresentationCharacters"
              />
              <n-text depth="3" class="presentation-tool-tip">
                {{ t('nodeEditor.presentation.participatingCharactersHint') }}
              </n-text>
            </div>
            <n-space :size="8" wrap align="center">
              <n-button
                size="small"
                secondary
                :disabled="backgroundUploading || presentationGenerationBusy"
                :loading="backgroundUploading"
                @click="triggerBackgroundUpload"
              >
                <template #icon>
                  <n-icon :component="Upload" />
                </template>
                {{ t('nodeEditor.presentation.uploadBackground') }}
              </n-button>
              <n-button
                v-if="currentBackgroundId"
                size="small"
                secondary
                type="warning"
                :disabled="backgroundUploading || presentationGenerationBusy"
                @click="clearDialogueBackground"
              >
                <template #icon>
                  <n-icon :component="Eraser" />
                </template>
                {{ t('nodeEditor.presentation.clearBackground') }}
              </n-button>
              <n-button
                size="small"
                type="primary"
                secondary
                :disabled="!canGenerateBackground"
                :loading="backgroundGenerating"
                @click="generateBackgroundByAI"
              >
                <template #icon>
                  <n-icon :component="Sparkles" />
                </template>
                {{ t('nodeEditor.presentation.generateBackground') }}
              </n-button>
            </n-space>
            <input
              ref="backgroundFileInputRef"
              class="presentation-hidden-input"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              @change="onBackgroundFileChange"
            />

          </div>
        </section>

        <section v-if="canUsePresentationTools && visualIllustrationEnabled" class="toolbox-module presentation-style-card presentation-illustration-card">
          <div class="toolbox-module-heading">
            <n-icon :component="Images" />
            <span>{{ t('nodeEditor.presentation.illustration') }}</span>
          </div>
          <template v-if="canEditPresentation">
            <div class="presentation-current-line" :class="{ 'is-empty': !currentIllustrationId }">
              {{ currentIllustrationId || t('nodeEditor.presentation.noIllustration') }}
            </div>
            <n-space :size="8" wrap align="center">
              <n-button
                size="small"
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
                size="small"
                secondary
                type="warning"
                :disabled="illustrationUploading || presentationGenerationBusy"
                @click="clearDialogueIllustration"
              >
                <template #icon><n-icon :component="Eraser" /></template>
                {{ t('nodeEditor.presentation.clearIllustration') }}
              </n-button>
              <n-button
                size="small"
                type="primary"
                secondary
                :disabled="!canGenerateIllustration"
                :loading="illustrationGenerating"
                @click="generateIllustrationByAI"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateIllustration') }}
              </n-button>
            </n-space>
          </template>

          <div class="illustration-batch-controls">
            <n-radio-group v-model:value="illustrationBatchScope" size="small">
              <n-radio-button value="scene">{{ t('nodeEditor.presentation.batchScopeScene') }}</n-radio-button>
              <n-radio-button value="file">{{ t('nodeEditor.presentation.batchScopeFile') }}</n-radio-button>
            </n-radio-group>
            <n-text depth="3" class="presentation-tool-tip" role="status">
              {{ illustrationBatchStatusText }}
            </n-text>
            <n-text v-if="illustrationBatchCurrent" depth="3" class="presentation-tool-tip">
              {{ illustrationBatchCurrentText }}
            </n-text>
            <n-text v-if="illustrationBatchError" type="error" class="presentation-tool-tip">
              {{ illustrationBatchError }}
            </n-text>
            <n-text v-if="illustrationBatchFailureText" type="warning" class="presentation-tool-tip">
              {{ illustrationBatchFailureText }}
            </n-text>
            <n-space :size="8" wrap align="center">
              <n-button
                size="small"
                secondary
                :disabled="!canBatchGenerateIllustrations"
                :loading="illustrationBatchGenerating"
                @click="generateSceneIllustrations"
              >
                <template #icon><n-icon :component="Images" /></template>
                {{ t('nodeEditor.presentation.generateSceneIllustrations') }}
              </n-button>
              <n-button
                size="small"
                secondary
                :disabled="!canGenerateIllustrationConceptions"
                :loading="illustrationConceptionBatchGenerating"
                @click="generateIllustrationConceptions"
              >
                <template #icon><n-icon :component="Sparkles" /></template>
                {{ t('nodeEditor.presentation.generateIllustrationConceptions') }}
              </n-button>
            </n-space>
            <n-text depth="3" class="presentation-tool-tip" role="status">
              {{ illustrationConceptionBatchStatusText }}
            </n-text>
            <n-text v-if="illustrationConceptionBatchCurrent" depth="3" class="presentation-tool-tip">
              {{ illustrationConceptionBatchCurrentText }}
            </n-text>
            <n-text v-if="illustrationConceptionBatchError" type="error" class="presentation-tool-tip">
              {{ illustrationConceptionBatchError }}
            </n-text>
            <n-text v-if="illustrationConceptionBatchFailureText" type="warning" class="presentation-tool-tip">
              {{ illustrationConceptionBatchFailureText }}
            </n-text>
          </div>
          <input
            v-if="canEditPresentation"
            ref="illustrationFileInputRef"
            class="presentation-hidden-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            @change="onIllustrationFileChange"
          />
        </section>

        <section class="toolbox-module continuation-module">
          <div class="toolbox-module-heading">
            <n-icon :component="Zap" />
            <span>{{ t('nodeEditor.presentation.continuationModule') }}</span>
          </div>

          <!-- 模式选择 -->
          <n-form-item class="continuation-mode-selector" :label="t('nodeEditor.presentation.modeLabel')" v-if="!hideModeSelector && modeOptions.length > 1">
            <n-select
              v-model:value="mode"
              id="ai-mode-select"
              :placeholder="t('nodeEditor.presentation.modePlaceholder')"
              :options="modeOptions"
            />
          </n-form-item>

        <!-- 单段续写控件 -->
        <div v-show="mode === 'single-node'" class="mode-content">
          <n-form-item label="长度">
            <n-input-number 
              id="ai-single-length" 
              v-model:value="singleLength" 
              :min="1" 
              :max="1000"
              style="width: 100%"
            />
          </n-form-item>
          
          <n-button 
            id="ai-generate-single-btn"
            type="primary" 
            :disabled="disableGenerate" 
            :loading="generating"
            @click="handleSingleNode"
            block
            strong
          >
            <template #icon>
              <n-icon :component="Zap" />
            </template>
            {{ generating ? '生成中...' : '生成' }}
          </n-button>
        </div>

                <!-- 多段续写控件 -->
        <div v-show="mode === 'multi-node'" class="mode-content">
                  <SparkAlert v-if="isNovelMode" type="info" style="margin-bottom: 12px;">
                    当前将基于整篇小说正文继续续写，并直接写回当前 `.md` 文件。
                  </SparkAlert>
                  <n-form-item v-if="!isNovelMode" label="场景思路">
                    <n-input
                      v-model:value="currentThought"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 6 }"
                      placeholder="AI 将基于此构思生成剧情。留空则自动生成。"
                    />
                  </n-form-item>
          <n-form-item :label="isNovelMode ? '续写要求' : '引导提示'">
            <n-input 
              id="ai-multi-prompt"
              v-model:value="multiPrompt" 
              type="textarea"
              :autosize="{ minRows: 3, maxRows: 6 }"
              :placeholder="isNovelMode ? '例如：延续当前文风，强化心理描写，并推进到新的冲突节点。' : '给 AI 的额外指示...'"
            />
          </n-form-item>

          <n-form-item label="段数 (0为无限)">
            <n-input-number
              id="ai-multi-segments"
              v-model:value="multiSegments" 
              :min="0" 
              :max="10"
              style="width: 100%"
            />
          </n-form-item>

          <n-form-item v-if="!isNovelMode" label="参与角色（1-4）">
            <n-select 
              id="ai-multi-chars"
              v-model:value="selectedCharacterIds" 
              multiple
              placeholder="选择参与角色"
              :options="characterOptions"
              filterable
            />
          </n-form-item>

          <n-button 
            id="ai-generate-multi-btn"
            type="primary" 
            :disabled="disableGenerate || (!isNovelMode && (selectedCharacterIds.length === 0 || selectedCharacterIds.length > 4))" 
            :loading="generating"
            @click="handleMultiNode"
            block
            strong
          >
            <template #icon>
              <n-icon :component="Zap" />
            </template>
            {{ generating ? '生成中...' : '生成' }}
          </n-button>

          <!-- 思维链展示 (多段续写模式) -->
          <div v-if="lastThought && (mode === 'multi-node')" class="thought-process">
            <n-collapse :default-expanded-names="['thought']">
              <n-collapse-item name="thought">
                <template #header>
                  <n-space align="center">
                    <n-icon :component="ChartColumn" color="var(--primary-color)" />
                    <span>AI 思维链 (Thought Process)</span>
                  </n-space>
                </template>
                <div class="thought-content">
                  <MarkdownRenderer :content="lastThought" />
                </div>
              </n-collapse-item>
            </n-collapse>
          </div>
        </div>

        <!-- 重写整个场景控件 -->
        <div v-show="mode === 'rewrite-scene'" class="mode-content">
          <SparkAlert type="warning" title="覆盖警告" style="margin-bottom: 16px;">
            {{ isNovelMode ? '此操作将重写当前小说全文，并直接覆盖当前 `.md` 文件。' : '此操作将清空当前场景的所有对话内容，并用 AI 生成的新内容替换。' }}
          </SparkAlert>

          <n-form-item :label="isNovelMode ? '改写目标 (可选)' : '场景构思 (可选)'">
            <n-input
              v-model:value="rewriteThought"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              :placeholder="isNovelMode ? '描述你希望这一版小说强化什么，例如文风、节奏、心理刻画。' : '描述你希望这个场景如何发展...'"
            />
          </n-form-item>

          <n-form-item :label="isNovelMode ? '重写要求 (可选)' : '引导提示 (可选)'">
            <n-input 
              v-model:value="rewriteGuidance" 
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              :placeholder="isNovelMode ? '例如：保持剧情不变，但改写得更像悬疑小说。' : '给 AI 的额外指示...'"
            />
          </n-form-item>

          <n-form-item v-if="!isNovelMode" label="参与角色（1-4）">
            <n-select 
              v-model:value="selectedCharacterIds" 
              multiple
              placeholder="选择参与角色"
              :options="characterOptions"
              filterable
            />
          </n-form-item>

          <n-button 
            type="warning" 
            :disabled="isNovelMode ? (!fileStore.selectedFile?.path || generating) : (!sceneStore.currentScene || generating || selectedCharacterIds.length === 0 || selectedCharacterIds.length > 4)" 
            :loading="generating"
            @click="handleRewriteScene"
            block
            strong
          >
            <template #icon>
              <n-icon :component="RefreshCw" />
            </template>
            {{ generating ? '重写中...' : '重写整个场景' }}
          </n-button>
        </div>

        <!-- 场景衔接控件 (Bridge) -->

        <div v-show="mode === 'bridge'" class="mode-content">
          <n-form-item label="前一场景">
            <n-select 
              v-model:value="bridgePrevScene"
              placeholder="选择前一场景"
              :options="sceneOptions"
              filterable
            />
          </n-form-item>

          <n-form-item label="后一场景">
            <n-select 
              v-model:value="bridgeNextScene"
              placeholder="选择后一场景"
              :options="sceneOptions"
              filterable
            />
          </n-form-item>

          <n-form-item label="节奏">
            <n-select 
              v-model:value="bridgePacing"
              :options="pacingOptions"
            />
          </n-form-item>

          <n-form-item label="用户指导（可选）">
            <n-input 
              v-model:value="bridgeGuidance" 
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              placeholder="例如：增加悬念、使用特定角色对话..."
            />
          </n-form-item>

          <n-button 
            type="primary" 
            :disabled="!canGenerateBridge" 
            :loading="generating"
            @click="handleBridge"
            block
            strong
          >
            <template #icon>
              <n-icon :component="GitBranch" />
            </template>
            {{ generating ? '生成中...' : '生成过渡对话' }}
          </n-button>

          <!-- 生成结果预览 -->
          <div v-if="bridgeResult.length > 0" class="bridge-result">
            <n-divider title-placement="left">生成结果</n-divider>
            <div class="bridge-dialogues">
              <div v-for="(d, idx) in bridgeResult" :key="idx" class="bridge-dialogue-item">
                <n-tag :type="d.chr === 0 ? 'default' : 'info'" size="small">
                  {{ chrName(d.chr) }}
                </n-tag>
                <span class="dialogue-text">{{ d.txt }}</span>
              </div>
            </div>
            <n-space justify="end" style="margin-top: 12px;">
              <n-button @click="bridgeResult = []" secondary size="small">清除</n-button>
              <n-button type="primary" @click="insertBridgeResult" size="small">插入到场景</n-button>
            </n-space>
          </div>
        </div>
        </section>

        <!-- Critic 手动评审 -->
        <section class="toolbox-module critic-module">
          <div class="toolbox-module-heading">
            <n-icon :component="CircleCheck" />
            <span>{{ t('nodeEditor.presentation.criticModule') }}</span>
          </div>

          <div class="mode-content critic-mode">
            <SparkAlert type="info" style="margin-bottom: 12px;">
              {{ criticTargetLabel }}。Critic 会结合当前项目上下文，输出结构化审查意见，但不会自动改稿。
            </SparkAlert>

            <n-form-item label="审查重点（可选）">
              <n-input
                v-model:value="criticGuidance"
                type="textarea"
                :autosize="{ minRows: 3, maxRows: 6 }"
                :placeholder="isNovelMode ? '例如：重点看是否有解释腔、段尾升华、心理描写假大空。' : '例如：重点看当前场景对白是否像真人说话，是否有 AI 味。'"
              />
            </n-form-item>

            <n-button
              type="error"
              :disabled="!canRunCritic"
              :loading="generating"
              @click="handleCriticReview"
              block
              strong
            >
              <template #icon>
                <n-icon :component="CircleCheck" />
              </template>
              {{ generating ? '评审中...' : '开始评审' }}
            </n-button>

            <div v-if="criticResult" class="critic-result">
              <n-space justify="space-between" align="center">
                <n-space align="center">
                  <n-tag :type="criticDecisionTagType" size="small">{{ criticResult.decision || 'PASS' }}</n-tag>
                  <span class="critic-risk-score">总评 {{ criticResult.overall_grade || 'A' }}</span>
                </n-space>
                <n-tag size="small" :bordered="false">{{ criticResult.status || 'APPROVE' }}</n-tag>
              </n-space>

              <div v-if="criticResult.overall_summary" class="critic-summary">
                {{ criticResult.overall_summary }}
              </div>

              <div v-if="criticResult.rewrite_brief" class="critic-brief">
                <strong>修改摘要：</strong>{{ criticResult.rewrite_brief }}
              </div>

              <n-divider title-placement="left">维度等级</n-divider>
              <div class="critic-score-grid">
                <div v-for="item in criticDimensionItems" :key="item.key" class="critic-score-item">
                  <span class="critic-score-label">{{ item.label }}</span>
                  <n-tag size="small" :bordered="false">{{ item.value }}</n-tag>
                </div>
              </div>

              <n-divider title-placement="left">命中问题</n-divider>
              <div v-if="criticHits.length === 0" class="critic-empty-hits">
                未命中明显问题，当前稿件整体可用。
              </div>
              <div v-else class="critic-hit-list">
                <div v-for="(hit, idx) in criticHits" :key="`${hit.feature}-${idx}`" class="critic-hit-item">
                  <n-space align="center" style="margin-bottom: 6px;">
                    <n-tag size="small" :type="criticSeverityTagType(hit.severity)">{{ formatCriticFeature(hit.feature) }}</n-tag>
                    <n-tag size="small" :bordered="false">{{ formatCriticSeverity(hit.severity) }}</n-tag>
                  </n-space>

                  <div v-if="hit.reason" class="critic-hit-reason">{{ hit.reason }}</div>
                  <div v-if="hit.suggestion" class="critic-hit-suggestion">建议：{{ hit.suggestion }}</div>

                  <div v-if="Array.isArray(hit.evidence) && hit.evidence.length" class="critic-evidence-list">
                    <div v-for="(ev, evIdx) in hit.evidence" :key="evIdx" class="critic-evidence-item">
                      <div v-if="ev.quote" class="critic-evidence-quote">“{{ ev.quote }}”</div>
                      <div v-if="ev.reason" class="critic-evidence-reason">{{ ev.reason }}</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NForm, NFormItem, NSelect, NInputNumber, NButton, NInput, NIcon, NSpace, NTag, NDivider, NText, NRadioButton, NRadioGroup, NCollapse, NCollapseItem, useDialog } from 'naive-ui';
import SparkAlert from '@/components/share/SparkAlert.vue';
import { ChartColumn, CircleCheck, Eraser, FileText, Files, GitBranch, ImagePlus, Images, RefreshCw, Sparkles, SquarePen, Upload, Zap } from '@lucide/vue';
import bus from '@/eventBus';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useCharacterStore } from '@/components/stores/characterStore';
import { fetchWithAuth, fetchCharacters } from '@/services/api';
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
  type PresentationSettings,
  type PresentationReferenceDescriptor,
  isPresentationEndpointNotFoundError,
  isPresentationUpstreamBlockingError,
  getPresentationErrorMessage,
} from '@/services/presentationService';
import { supportsImageInput } from '@/services/modelModalities';
import { createStreamingTask, consumeSSEReader, isAbortLikeError, parseSSEEventPayload } from '@/utils/streamingRuntime';
import {
  selectPresentationIllustrationCandidates,
  selectPresentationIllustrationConceptionCandidates,
} from '@/utils/presentationIllustrationPolicy';
import type { CancelLoadingPayload } from '@/eventBus';
import type { StoryCharacterDetail } from '@/services/aiContracts';
import { formatSpeakerMarker, type ArcDialogueNode, type ArcScene, type PresentationCue } from '@/services/arcParser';

type PanelMode = 'single-node' | 'multi-node' | 'rewrite-scene' | 'bridge';

type PanelProps = {
  defaultMode?: string;
  allowedModes?: string[] | null;
  hideModeSelector?: boolean;
};

type ComposeRequestPayload = {
  operation: string;
  mode: string;
  projectName: string;
  filePath?: string;
  sceneName?: string;
  nodeId?: number;
  selectedCharacterIds?: number[];
  guidance?: string;
  segmentCount?: number;
  lastNodeText?: string;
  context?: string;
  confirmContinue?: boolean;
  rewrite?: boolean;
  length?: number;
  prevScene?: Record<string, unknown> | null;
  nextScene?: Record<string, unknown> | null;
  pacing?: string;
  mood?: string;
};

type CriticHitItem = {
  feature?: string;
  severity?: string;
  evidence?: unknown;
  suggestion?: string;
  [key: string]: unknown;
};

type CriticEvidenceItem = {
  quote?: string;
  reason?: string;
};

type CriticHitViewItem = CriticHitItem & {
  evidence: CriticEvidenceItem[];
};

type CriticResultPayload = Record<string, unknown> & {
  decision?: string;
  hits?: CriticHitItem[];
  dimension_grades?: Record<string, string>;
};

type BridgeTriggerPayload = {
  prevScene?: string | null;
  nextScene?: string | null;
};

type SceneDialogueCarrier = {
  scene?: string;
  dia?: ArcDialogueNode[];
};

function getErrorMessage(error: unknown, fallback = '发生未知错误'): string {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return fallback;
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  if (error instanceof Error && error.name === 'AbortError') return true;
  return isAbortLikeError(error);
}

function normalizeCriticEvidenceItem(value: unknown): CriticEvidenceItem | null {
  if (!value || typeof value !== 'object') return null;
  const quote = 'quote' in value ? String((value as { quote?: unknown }).quote || '').trim() : '';
  const reason = 'reason' in value ? String((value as { reason?: unknown }).reason || '').trim() : '';
  if (!quote && !reason) return null;
  return { quote, reason };
}

type ComposeStreamPayload = Record<string, unknown> & {
  text?: string;
  thought?: string;
  error?: string;
  message?: string;
  dialogues?: ArcDialogueNode[];
  onProgress?: { message?: string };
  onStart?: { message?: string };
  onDone?: { message?: string };
  onCancelled?: { message?: string };
  onError?: { message?: string };
  onStats?: Record<string, unknown>;
};

type ConflictPayload = {
  error?: string;
  message?: string;
  missing?: string[];
};

type StreamComposeResult = {
  done?: ComposeStreamPayload | null;
  conflict?: ConflictPayload | null;
};

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();
const dialog = useDialog();
const { t } = useI18n();

const props = withDefaults(defineProps<PanelProps>(), {
  defaultMode: '',
  allowedModes: null,
  hideModeSelector: false,
});

const isNovelMode = computed(() => sceneStore.workspaceMode === 'novel' || sceneStore.fileFormat === 'novel');
const isScriptMode = computed(() => sceneStore.workspaceMode === 'script' && !isNovelMode.value);
const visible = computed(() => sceneStore.selectionType === 'dialogue'
  || sceneStore.selectionType === 'scene'
  || sceneStore.selectionType === 'novel'
  || (isScriptMode.value && !!sceneStore.currentScene)
  || mode.value === 'bridge');

// 模式选项
const baseModeOptions = [
  { label: '单段续写', value: 'single-node', icon: FileText },
  { label: '多段续写', value: 'multi-node', icon: Files },
  { label: '重写整个场景', value: 'rewrite-scene', icon: RefreshCw },
  { label: '场景过渡', value: 'bridge', icon: GitBranch }
];

const modeOptions = computed(() => {
  let options = baseModeOptions;
  if (isNovelMode.value) {
    options = baseModeOptions.filter(opt => ['multi-node', 'rewrite-scene'].includes(opt.value));
  }
  const allowedModes = props.allowedModes || [];
  if (allowedModes.length === 0) return options;
  return options.filter(opt => allowedModes.includes(opt.value));
});

const mode = ref<PanelMode | string>(props.defaultMode || modeOptions.value[0]?.value || 'single-node');
const singleLength = ref(50);
const generating = ref(false);
const disableGenerate = computed(() => {
  if (isNovelMode.value) return generating.value || !fileStore.selectedFile?.path;
  return generating.value || (!sceneStore.currentNode && sceneStore.selectionType !== 'scene');
});

watch(modeOptions, (opts) => {
  if (!opts.find(o => o.value === mode.value)) {
    mode.value = opts[0]?.value || 'single-node';
  }
});

// 多段续写
const multiPrompt = ref('');
const multiSegments = ref(0);
const characters = ref<StoryCharacterDetail[]>([]);
const selectedCharacterIds = ref<string[]>([]);
const presentationCharacterIds = ref<string[]>([]);
let abortController: AbortController | null = null;

const backgroundFileInputRef = ref<HTMLInputElement | null>(null);
const illustrationFileInputRef = ref<HTMLInputElement | null>(null);
const backgroundUploading = ref(false);
const backgroundGenerating = ref(false);
const illustrationUploading = ref(false);
const illustrationGenerating = ref(false);
const illustrationBatchGenerating = ref(false);
const illustrationBatchScope = ref<'scene' | 'file'>('scene');
const illustrationBatchTotal = ref(0);
const illustrationBatchCompleted = ref(0);
const illustrationBatchFailed = ref(0);
const illustrationBatchCurrent = ref<{
  index: number;
  total: number;
  sceneName: string;
  nodeLabel: string;
} | null>(null);
const illustrationBatchFailureItems = ref<string[]>([]);
const illustrationBatchError = ref('');
const illustrationBatchLastState = ref<'idle' | 'done' | 'cancelled' | 'failed'>('idle');
const illustrationConceptionGenerating = ref(false);
const illustrationConceptionBatchGenerating = ref(false);
const illustrationConceptionBatchTotal = ref(0);
const illustrationConceptionBatchCompleted = ref(0);
const illustrationConceptionBatchFailed = ref(0);
const illustrationConceptionBatchCurrent = ref<{
  index: number;
  total: number;
  sceneName: string;
  nodeLabel: string;
} | null>(null);
const illustrationConceptionBatchFailureItems = ref<string[]>([]);
const illustrationConceptionBatchError = ref('');
const illustrationConceptionBatchLastState = ref<'idle' | 'done' | 'cancelled' | 'failed'>('idle');
const backgroundPreviewFailed = ref(false);
const illustrationPrompt = ref('');
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const visualIllustrationEnabled = ref(false);
const visualIllustrationMaxPerScene = ref(2);
const visualIllustrationMinNodeGap = ref(1);
let presentationManifestRequestId = 0;
let localManifestRevision = 0;

// 重写场景
const rewriteThought = ref('');
const rewriteGuidance = ref('');
const criticGuidance = ref('');
const criticResult = ref<CriticResultPayload | null>(null);


// Thought 编辑
const currentThought = computed({
  get: () => sceneStore.currentScene?.thought || '',
  set: (val) => {
    if (sceneStore.currentScene) {
      sceneStore.currentScene.thought = val;
    }
  }
});

// Bridge 场景过渡
const bridgePrevScene = ref<string | null>(null);
const bridgeNextScene = ref<string | null>(null);
const bridgePacing = ref('Normal');
const bridgeGuidance = ref('');
const bridgeResult = ref<ArcDialogueNode[]>([]);
const lastThought = ref('');

const pacingOptions = [
  { label: '慢节奏 (Slow)', value: 'Slow' },
  { label: '正常节奏 (Normal)', value: 'Normal' },
  { label: '快节奏 (Fast)', value: 'Fast' }
];

// 场景选项
const sceneOptions = computed(() => {
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  return scenes.map((s, idx) => ({
    label: s.scene || `场景 ${idx + 1}`,
    value: s.scene
  }));
});

// 是否可以生成过渡
const canGenerateBridge = computed(() => {
  return !generating.value && 
         bridgePrevScene.value && 
         bridgeNextScene.value && 
         bridgePrevScene.value !== bridgeNextScene.value;
});

const canRunCritic = computed(() => {
  if (generating.value) return false;
  if (isNovelMode.value) {
    return !!fileStore.selectedFile?.path && typeof sceneStore.scriptData === 'string';
  }
  return !!sceneStore.currentScene;
});

const criticTargetLabel = computed(() => {
  if (isNovelMode.value) {
    return fileStore.selectedFile?.path ? `将审查当前小说文件：${fileStore.selectedFile.path}` : '将审查当前小说正文';
  }
  return sceneStore.currentScene?.scene ? `将审查当前场景：${sceneStore.currentScene.scene}` : '将审查当前场景';
});

const canUsePresentationTools = computed(() => isScriptMode.value && !!projectStore.currentProject && !!sceneStore.currentScene);
const canEditPresentation = computed(() => sceneStore.selectionType === 'dialogue' && !!currentDialogueNode.value && !isNovelMode.value);

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
  !normalizePresentationValue(currentPresentation.value.illustration_prompt)
  && !currentIllustrationId.value
  && normalizePresentationValue(currentPresentation.value.illustration_pending).toLowerCase() === 'true'
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
  || illustrationBatchGenerating.value
  || illustrationConceptionGenerating.value
  || illustrationConceptionBatchGenerating.value
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
  canEditPresentation.value
  && visualIllustrationEnabled.value
  && currentIllustrationPending.value
  && !presentationGenerationBusy.value
);

const illustrationCandidates = computed(() => {
  const scenes = illustrationBatchScope.value === 'file'
    ? (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData as ArcScene[] : [])
    : (sceneStore.currentScene ? [sceneStore.currentScene as ArcScene] : []);
  return scenes.flatMap(scene => selectPresentationIllustrationCandidates(
    collectDialogueNodes(scene),
    node => node.presentation,
    {
      maxPerScene: visualIllustrationMaxPerScene.value,
      minNodeGap: visualIllustrationMinNodeGap.value,
    },
  ).map(node => ({ scene, node })));
});

const illustrationConceptionCandidates = computed(() => {
  const scenes = illustrationBatchScope.value === 'file'
    ? (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData as ArcScene[] : [])
    : (sceneStore.currentScene ? [sceneStore.currentScene as ArcScene] : []);
  return scenes.flatMap(scene => selectPresentationIllustrationConceptionCandidates(
    collectDialogueNodes(scene),
    node => node.presentation,
    {
      maxPerScene: visualIllustrationMaxPerScene.value,
      minNodeGap: visualIllustrationMinNodeGap.value,
    },
  ).map(node => ({ scene, node })));
});

const canBatchGenerateIllustrations = computed(() =>
  canUsePresentationTools.value
  && visualIllustrationEnabled.value
  && !presentationGenerationBusy.value
  && illustrationCandidates.value.length > 0
  && !!selectedImageModel.value
);

const canGenerateIllustrationConceptions = computed(() =>
  canUsePresentationTools.value
  && visualIllustrationEnabled.value
  && !presentationGenerationBusy.value
  && illustrationConceptionCandidates.value.length > 0
);

const illustrationBatchStatusText = computed(() => {
  if (illustrationBatchGenerating.value) {
    return t('nodeEditor.presentation.batchProgress', {
      current: illustrationBatchCompleted.value + illustrationBatchFailed.value + 1,
      total: illustrationBatchTotal.value,
    });
  }
  if (illustrationBatchLastState.value === 'done') {
    return t('nodeEditor.presentation.batchDone', {
      completed: illustrationBatchCompleted.value,
      failed: illustrationBatchFailed.value,
    });
  }
  if (illustrationBatchLastState.value === 'cancelled') {
    return t('nodeEditor.presentation.batchCancelled', {
      completed: illustrationBatchCompleted.value,
    });
  }
  if (illustrationBatchLastState.value === 'failed') {
    return t('nodeEditor.presentation.batchFailed');
  }
  return t('nodeEditor.presentation.batchPendingCount', { count: illustrationCandidates.value.length });
});

const illustrationBatchCurrentText = computed(() => {
  const current = illustrationBatchCurrent.value;
  if (!current) return '';
  return t('nodeEditor.presentation.batchCurrentItem', {
    scene: current.sceneName,
    node: current.nodeLabel,
  });
});

const illustrationBatchFailureText = computed(() => {
  if (!illustrationBatchFailureItems.value.length) return '';
  return t('nodeEditor.presentation.batchFailedItems', {
    items: illustrationBatchFailureItems.value.join('、'),
  });
});

const illustrationConceptionBatchStatusText = computed(() => {
  if (illustrationConceptionBatchGenerating.value) {
    return t('nodeEditor.presentation.conceptionBatchProgress', {
      current: illustrationConceptionBatchCompleted.value + illustrationConceptionBatchFailed.value + 1,
      total: illustrationConceptionBatchTotal.value,
    });
  }
  if (illustrationConceptionBatchLastState.value === 'done') {
    return t('nodeEditor.presentation.conceptionBatchDone', {
      completed: illustrationConceptionBatchCompleted.value,
      failed: illustrationConceptionBatchFailed.value,
    });
  }
  if (illustrationConceptionBatchLastState.value === 'cancelled') {
    return t('nodeEditor.presentation.conceptionBatchCancelled', {
      completed: illustrationConceptionBatchCompleted.value,
    });
  }
  if (illustrationConceptionBatchLastState.value === 'failed') {
    return t('nodeEditor.presentation.conceptionBatchFailed');
  }
  return t('nodeEditor.presentation.conceptionBatchPendingCount', {
    count: illustrationConceptionCandidates.value.length,
  });
});

const illustrationConceptionBatchCurrentText = computed(() => {
  const current = illustrationConceptionBatchCurrent.value;
  if (!current) return '';
  return t('nodeEditor.presentation.batchCurrentItem', {
    scene: current.sceneName,
    node: current.nodeLabel,
  });
});

const illustrationConceptionBatchFailureText = computed(() => {
  if (!illustrationConceptionBatchFailureItems.value.length) return '';
  return t('nodeEditor.presentation.batchFailedItems', {
    items: illustrationConceptionBatchFailureItems.value.join('、'),
  });
});

watch(
  () => [
    currentDialogueNode.value?.id,
    normalizePresentationValue(currentPresentation.value.illustration_prompt),
    normalizePresentationList(currentPresentation.value.characters).join('|'),
  ],
  () => {
    illustrationPrompt.value = normalizePresentationValue(currentPresentation.value.illustration_prompt);
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

function normalizeVisualIllustrationPolicyValue(value: unknown, fallback: number, minimum: number, maximum: number) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, Math.trunc(parsed)));
}

function applyVisualIllustrationSettings(settings: PresentationSettings['visualIllustration'] | undefined) {
  visualIllustrationMaxPerScene.value = normalizeVisualIllustrationPolicyValue(
    settings?.max_per_scene,
    2,
    1,
    4,
  );
  visualIllustrationMinNodeGap.value = normalizeVisualIllustrationPolicyValue(
    settings?.min_node_gap,
    1,
    0,
    4,
  );
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
    applyVisualIllustrationSettings(undefined);
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
    applyVisualIllustrationSettings(result.settings?.visualIllustration);
    visualIllustrationEnabled.value = !!result.settings?.visualIllustration?.effectiveEnabled;
  } catch (_error: unknown) {
    if (requestId === presentationManifestRequestId && revisionAtRequest === localManifestRevision) {
      presentationManifest.value = null;
      applyVisualIllustrationSettings(undefined);
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

type EditablePresentationKey = 'bg' | 'sprite' | 'illustration_prompt' | 'illustration' | 'illustration_pending' | 'characters';
type EditablePresentationValue = string | string[] | null;

function setNodePresentationValues(
  node: ArcDialogueNode | null,
  values: Partial<Record<EditablePresentationKey, EditablePresentationValue>>,
) {
  if (!node) return;
  const nextPresentation: PresentationCue = { ...(node.presentation || {}) };
  for (const [key, value] of Object.entries(values)) {
    const isEmpty = value === null
      || value === undefined
      || value === ''
      || (Array.isArray(value) && value.length === 0);
    if (isEmpty) delete nextPresentation[key];
    else nextPresentation[key] = value;
  }
  const presentation = Object.keys(nextPresentation).length > 0 ? nextPresentation : undefined;
  if (node === currentDialogueNode.value) sceneStore.updateCurrentDialogue({ presentation });
  else node.presentation = presentation;
}

function setNodePresentationValue(
  node: ArcDialogueNode | null,
  key: EditablePresentationKey,
  value: EditablePresentationValue,
) {
  setNodePresentationValues(node, { [key]: value });
}

function setDialoguePresentationValues(values: Partial<Record<EditablePresentationKey, EditablePresentationValue>>) {
  setNodePresentationValues(currentDialogueNode.value, values);
  void savePresentationBinding();
}

function setDialoguePresentationValue(key: EditablePresentationKey, value: EditablePresentationValue) {
  setDialoguePresentationValues({ [key]: value });
}

function collectDialogueNodes(scene: ArcScene | null | undefined): ArcDialogueNode[] {
  const result: ArcDialogueNode[] = [];
  const walk = (nodes: ArcDialogueNode[] | undefined) => {
    for (const node of nodes || []) {
      result.push(node);
      for (const option of node.opt || []) walk(option.dia || []);
    }
  };
  walk(scene?.dia || []);
  return result;
}

function collectDialogueContextNodes(): ArcDialogueNode[] {
  return collectDialogueNodes(sceneStore.currentScene as ArcScene | null);
}

function getCurrentDialogueWindow(
  target = currentDialogueNode.value,
  scene: ArcScene | null = sceneStore.currentScene as ArcScene | null,
) {
  const nodes = collectDialogueNodes(scene);
  const index = target ? nodes.indexOf(target) : -1;
  if (index < 0) return [];
  return nodes.slice(Math.max(0, index - 2), Math.min(nodes.length, index + 3));
}

function nearestIllustrationAssetId(
  target = currentDialogueNode.value,
  scene: ArcScene | null = sceneStore.currentScene as ArcScene | null,
) {
  const nodes = collectDialogueNodes(scene);
  const index = target ? nodes.indexOf(target) : -1;
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    const assetId = normalizePresentationValue(nodes[cursor]?.presentation?.illustration);
    if (assetId) return assetId;
  }
  return '';
}

function characterIdForNode(node: ArcDialogueNode): string {
  const raw = String(node.speaker ?? node.chr ?? '').trim();
  if (!raw || raw === '-1' || raw === '旁白') return '';
  const byId = characters.value.find(character => String(character.id) === raw);
  if (byId) return String(byId.id);
  const byName = characters.value.find(character => character.name === raw || character.name === chrName(raw));
  return byName ? String(byName.id) : '';
}

function buildPresentationGenerationContext(
  node = currentDialogueNode.value,
  scene: ArcScene | null = sceneStore.currentScene as ArcScene | null,
  includeCharacters = true,
) {
  const contextNodes = getCurrentDialogueWindow(node, scene);
  const plannedCharacterIds = normalizePresentationList(node?.presentation?.characters);
  const characterIds = includeCharacters
    ? (plannedCharacterIds.length > 0
      ? plannedCharacterIds
      : Array.from(new Set(contextNodes.map(characterIdForNode).filter(Boolean))))
    : [];
  if (includeCharacters && plannedCharacterIds.length === 0 && node) {
    const currentId = characterIdForNode(node);
    if (currentId && !characterIds.includes(currentId)) characterIds.unshift(currentId);
  }
  return {
    sceneName: scene?.scene || '',
    sceneIntro: scene?.intro || '',
    sceneConception: scene?.thought || '',
    nodeText: node ? `${chrName(node.speaker || node.chr)}：${String(node.txt || '').trim()}` : '',
    nearbyDialogue: contextNodes
      .map(item => `${chrName(item.speaker || item.chr)}：${String(item.txt || '').trim()}`)
      .filter(line => !line.endsWith('：')),
    characterIds,
  };
}

function referenceAssetsFor(
  kind: 'background' | 'illustration',
  node = currentDialogueNode.value,
  scene: ArcScene | null = sceneStore.currentScene as ArcScene | null,
) {
  const model = selectedImageModel.value;
  if (!imageModelSupportsReference(model)) return [];
  const result: PresentationReferenceDescriptor[] = [];
  const seen = new Set<string>();
  const add = (assetId: string, role: PresentationReferenceDescriptor['role']) => {
    if (!assetId || seen.has(assetId) || result.length >= 4) return;
    seen.add(assetId);
    result.push({ assetId, role });
  };

  const cue = node?.presentation || {};
  add(normalizePresentationValue(cue.bg), 'scene');

  if (kind === 'illustration') {
    const characterIds = new Set(buildPresentationGenerationContext(node, scene).characterIds);
    Object.values(manifestAssets.value)
      .filter(asset => asset.type === 'character_sprite' && characterIds.has(String(asset.characterId || '')))
      .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
      .forEach(asset => add(asset.id, 'character'));
    add(normalizePresentationValue(cue.illustration) || nearestIllustrationAssetId(node, scene), 'continuity');
  }
  return result;
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
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (
    !file
    || !projectName
    || !targetNode
    || !targetScene
    || presentationGenerationBusy.value
    || backgroundUploading.value
  ) return;
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
  if (!projectName) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  if (!targetNode || !targetScene) return;
  const prompt = illustrationPrompt.value.trim();
  const model = selectedImageModel.value;
  if (!prompt) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.promptRequired') });
    return;
  }
  if (!model) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.imageModelMissing') });
    return;
  }
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
    saveIllustrationPromptForNode(targetNode);
    const result = await generatePresentationBackground(projectName, {
      prompt,
      title: targetNode.txt?.trim().slice(0, 18) || t('nodeEditor.presentation.generatedBackgroundTitle'),
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssets: referenceAssetsFor('background', targetNode, targetScene),
      context: buildPresentationGenerationContext(targetNode, targetScene, false),
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

function saveIllustrationPromptForNode(node: ArcDialogueNode | null) {
  const prompt = illustrationPrompt.value.trim();
  if (prompt) {
    setNodePresentationValues(node, {
      illustration_prompt: prompt,
      illustration_pending: null,
    });
  } else {
    setNodePresentationValue(node, 'illustration_prompt', null);
  }
  void savePresentationBinding();
}

function saveIllustrationPrompt() {
  saveIllustrationPromptForNode(currentDialogueNode.value);
}

function savePresentationCharacters() {
  setDialoguePresentationValue('characters', presentationCharacterIds.value.length > 0 ? presentationCharacterIds.value : null);
}

function triggerIllustrationUpload() {
  if (
    presentationGenerationBusy.value
    || illustrationUploading.value
    || !projectStore.currentProject
    || !visualIllustrationEnabled.value
  ) return;
  illustrationFileInputRef.value?.click();
}

async function onIllustrationFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  const projectName = projectStore.currentProject;
  const targetNode = currentDialogueNode.value;
  const targetScene = sceneStore.currentScene as ArcScene | null;
  if (
    !file
    || !projectName
    || !targetNode
    || !targetScene
    || presentationGenerationBusy.value
    || illustrationUploading.value
  ) return;
  illustrationUploading.value = true;
  try {
    saveIllustrationPromptForNode(targetNode);
    const result = await uploadPresentationIllustration(projectName, file, {
      title: file.name,
      sceneName: targetScene.scene || '',
      nodeId: String(targetNode.id),
    });
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setNodePresentationValue(targetNode, 'illustration', result.asset.id);
    await savePresentationBinding();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.illustrationUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.illustrationUploadFailed')) });
  } finally {
    illustrationUploading.value = false;
  }
}

function clearDialogueIllustration() {
  setDialoguePresentationValue('illustration', null);
  bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.illustrationClearSuccess') });
}

async function generateIllustrationForNode(
  node: ArcDialogueNode,
  scene: ArcScene,
  signal?: AbortSignal,
) {
  const projectName = projectStore.currentProject;
  const model = selectedImageModel.value;
  const prompt = normalizePresentationValue(node.presentation?.illustration_prompt);
  if (!projectName || !model || !prompt) throw new Error(t('nodeEditor.presentation.illustrationPromptRequired'));
  const result = await generatePresentationIllustration(projectName, {
    prompt,
    title: String(node.txt || '').trim().slice(0, 18) || t('nodeEditor.presentation.generatedIllustrationTitle'),
    sceneName: scene.scene || '',
    nodeId: String(node.id),
    size: '1536x1024',
    platformId: Number(model.platform_id),
    modelId: Number(model.model_id),
    referenceAssets: referenceAssetsFor('illustration', node, scene),
    context: buildPresentationGenerationContext(node, scene),
  }, signal);
  if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
  updateManifest(result.manifest);
  setNodePresentationValue(node, 'illustration', result.asset.id);
  await sceneStore._saveStory?.();
  return result.asset;
}

async function generateIllustrationConceptionForNode(
  node: ArcDialogueNode,
  scene: ArcScene,
  signal?: AbortSignal,
) {
  const projectName = projectStore.currentProject;
  if (
    !projectName
    || normalizePresentationValue(node.presentation?.illustration_pending).toLowerCase() !== 'true'
  ) {
    throw new Error(t('nodeEditor.presentation.illustrationConceptionRequired'));
  }
  const result = await generatePresentationIllustrationConception(projectName, {
    sceneName: scene.scene || '',
    nodeId: String(node.id),
    context: buildPresentationGenerationContext(node, scene),
  }, signal);
  const prompt = String(result.prompt || '').trim();
  if (!prompt) throw new Error(t('nodeEditor.presentation.illustrationConceptionEmpty'));
  setNodePresentationValues(node, {
    illustration_prompt: prompt,
    illustration_pending: null,
  });
  await sceneStore._saveStory?.();
  return prompt;
}

async function generateIllustrationConceptionByAI() {
  if (presentationGenerationBusy.value) return;
  const node = currentDialogueNode.value;
  const scene = sceneStore.currentScene as ArcScene | null;
  if (!node || !scene || !currentIllustrationPending.value) return;
  illustrationConceptionGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-illustration-conception',
    text: t('nodeEditor.presentation.generateIllustrationConception'),
    progress: t('nodeEditor.presentation.generateIllustrationConception'),
    canCancel: true,
    statsMode: 'elapsed',
  });
  try {
    task.throwIfAborted();
    await generateIllustrationConceptionForNode(node, scene, task.signal);
    task.throwIfAborted();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.illustrationConceptionSuccess') });
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.illustrationConceptionFailed')) });
  } finally {
    task.dispose();
    illustrationConceptionGenerating.value = false;
  }
}

async function generateIllustrationByAI() {
  if (presentationGenerationBusy.value) return;
  const node = currentDialogueNode.value;
  const scene = sceneStore.currentScene as ArcScene | null;
  if (!node || !scene) return;
  saveIllustrationPrompt();
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
    await generateIllustrationForNode(node, scene, task.signal);
    task.throwIfAborted();
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.illustrationGenerateSuccess') });
  } catch (error: unknown) {
    if (isAbortLikeError(error) || task.aborted) return;
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.illustrationGenerateFailed')) });
  } finally {
    task.dispose();
    illustrationGenerating.value = false;
  }
}

function illustrationBatchItemMeta(candidate: { node: ArcDialogueNode; scene: ArcScene }, index: number, total: number) {
  return {
    index,
    total,
    sceneName: String(candidate.scene.scene || '').trim() || t('nodeEditor.presentation.batchUnnamedScene'),
    nodeLabel: String(candidate.node.txt || '').trim().slice(0, 72) || t('nodeEditor.presentation.batchUnnamedNode'),
  };
}

async function generateSceneIllustrations() {
  if (presentationGenerationBusy.value) return;
  const candidates = [...illustrationCandidates.value];
  if (!candidates.length) return;
  illustrationBatchTotal.value = candidates.length;
  illustrationBatchCompleted.value = 0;
  illustrationBatchFailed.value = 0;
  illustrationBatchCurrent.value = null;
  illustrationBatchFailureItems.value = [];
  illustrationBatchError.value = '';
  illustrationBatchLastState.value = 'idle';
  illustrationBatchGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-illustrations',
    text: t('nodeEditor.presentation.batchGenerating'),
    progress: t('nodeEditor.presentation.batchProgress', { current: 0, total: candidates.length }),
    canCancel: true,
    statsMode: 'elapsed',
  });
  let completed = 0;
  let failed = 0;
  try {
    for (const [index, candidate] of candidates.entries()) {
      task.throwIfAborted();
      const current = illustrationBatchItemMeta(candidate, index + 1, candidates.length);
      illustrationBatchCurrent.value = current;
      task.setProgress(`${t('nodeEditor.presentation.batchProgress', {
        current: current.index,
        total: current.total,
      })} · ${t('nodeEditor.presentation.batchCurrentItem', {
        scene: current.sceneName,
        node: current.nodeLabel,
      })}`);
      try {
        await generateIllustrationForNode(candidate.node, candidate.scene, task.signal);
        completed += 1;
        illustrationBatchCompleted.value = completed;
      } catch (error: unknown) {
        if (isAbortError(error) || task.aborted) throw error;
        if (isPresentationUpstreamBlockingError(error) || isPresentationEndpointNotFoundError(error)) throw error;
        failed += 1;
        illustrationBatchFailed.value = failed;
        illustrationBatchFailureItems.value = [
          ...illustrationBatchFailureItems.value,
          `${current.sceneName} · ${current.nodeLabel}`,
        ];
      }
    }
    illustrationBatchLastState.value = 'done';
    bus.emit('toast', {
      type: failed ? 'warning' : 'success',
      message: t('nodeEditor.presentation.batchDone', { completed, failed }),
    });
  } catch (error: unknown) {
    if (isAbortError(error) || task.aborted) {
      illustrationBatchLastState.value = 'cancelled';
      bus.emit('toast', { type: 'info', message: t('nodeEditor.presentation.batchCancelled', { completed }) });
    } else {
      illustrationBatchLastState.value = 'failed';
      illustrationBatchError.value = presentationErrorMessage(error, t('nodeEditor.presentation.batchFailed'));
      bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.batchFailed')) });
    }
  } finally {
    illustrationBatchCurrent.value = null;
    task.dispose();
    illustrationBatchGenerating.value = false;
  }
}

async function generateIllustrationConceptions() {
  if (presentationGenerationBusy.value) return;
  const candidates = [...illustrationConceptionCandidates.value];
  if (!candidates.length) return;
  illustrationConceptionBatchTotal.value = candidates.length;
  illustrationConceptionBatchCompleted.value = 0;
  illustrationConceptionBatchFailed.value = 0;
  illustrationConceptionBatchCurrent.value = null;
  illustrationConceptionBatchFailureItems.value = [];
  illustrationConceptionBatchError.value = '';
  illustrationConceptionBatchLastState.value = 'idle';
  illustrationConceptionBatchGenerating.value = true;
  const task = createStreamingTask('production', {
    target: 'visual-illustration-conceptions',
    text: t('nodeEditor.presentation.conceptionBatchGenerating'),
    progress: t('nodeEditor.presentation.conceptionBatchProgress', { current: 0, total: candidates.length }),
    canCancel: true,
    statsMode: 'elapsed',
  });
  let completed = 0;
  let failed = 0;
  try {
    for (const [index, candidate] of candidates.entries()) {
      task.throwIfAborted();
      const current = illustrationBatchItemMeta(candidate, index + 1, candidates.length);
      illustrationConceptionBatchCurrent.value = current;
      task.setProgress(`${t('nodeEditor.presentation.conceptionBatchProgress', {
        current: current.index,
        total: current.total,
      })} · ${t('nodeEditor.presentation.batchCurrentItem', {
        scene: current.sceneName,
        node: current.nodeLabel,
      })}`);
      try {
        await generateIllustrationConceptionForNode(candidate.node, candidate.scene, task.signal);
        completed += 1;
        illustrationConceptionBatchCompleted.value = completed;
      } catch (error: unknown) {
        if (isAbortError(error) || task.aborted) throw error;
        if (isPresentationUpstreamBlockingError(error) || isPresentationEndpointNotFoundError(error)) throw error;
        failed += 1;
        illustrationConceptionBatchFailed.value = failed;
        illustrationConceptionBatchFailureItems.value = [
          ...illustrationConceptionBatchFailureItems.value,
          `${current.sceneName} · ${current.nodeLabel}`,
        ];
      }
    }
    illustrationConceptionBatchLastState.value = 'done';
    bus.emit('toast', {
      type: failed ? 'warning' : 'success',
      message: t('nodeEditor.presentation.conceptionBatchDone', { completed, failed }),
    });
  } catch (error: unknown) {
    if (isAbortError(error) || task.aborted) {
      illustrationConceptionBatchLastState.value = 'cancelled';
      bus.emit('toast', { type: 'info', message: t('nodeEditor.presentation.conceptionBatchCancelled', { completed }) });
    } else {
      illustrationConceptionBatchLastState.value = 'failed';
      illustrationConceptionBatchError.value = presentationErrorMessage(error, t('nodeEditor.presentation.conceptionBatchFailed'));
      bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.conceptionBatchFailed')) });
    }
  } finally {
    illustrationConceptionBatchCurrent.value = null;
    task.dispose();
    illustrationConceptionBatchGenerating.value = false;
  }
}

const criticHits = computed<CriticHitViewItem[]>(() => {
  if (!Array.isArray(criticResult.value?.hits)) return [];
  return criticResult.value.hits.map((hit) => {
    const evidenceList = Array.isArray(hit?.evidence)
      ? hit.evidence.map((item) => normalizeCriticEvidenceItem(item)).filter(Boolean) as CriticEvidenceItem[]
      : [];
    return {
      ...hit,
      evidence: evidenceList,
    };
  });
});

const criticDecisionTagType = computed(() => {
  const decision = String(criticResult.value?.decision || '').toUpperCase();
  if (decision === 'REJECT') return 'error';
  if (decision === 'REVISE') return 'warning';
  return 'success';
});

const criticDimensionItems = computed(() => {
  const grades = criticResult.value?.dimension_grades || {};
  return [
    { key: 'structure_ai_flavor', label: '结构 AI 味', value: grades.structure_ai_flavor ?? 'B' },
    { key: 'language_ai_flavor', label: '语言 AI 味', value: grades.language_ai_flavor ?? 'B' },
    { key: 'dialogue_ai_flavor', label: '对白 AI 味', value: grades.dialogue_ai_flavor ?? 'B' },
    { key: 'literary_flatness', label: '文学承载不足', value: grades.literary_flatness ?? 'B' },
    { key: 'logic_and_character', label: '逻辑 / 人设', value: grades.logic_and_character ?? 'B' },
  ];
});

// 将说话人标记映射为显示名
function chrName(id: number | string | null | undefined) {
  if (id === -1 || id === '旁白') return '旁白';
  if (typeof id === 'string' && Number.isNaN(Number(id))) return id;
  const name = characterStore.map?.[Number(id)];
  return name ?? `角色 ${id}`;
}

function formatCriticFeature(feature: unknown) {
  const map: Record<string, string> = {
    dialogue_over_efficiency: '对白过度高效',
    structure_ai_flavor: '结构 AI 味',
    language_ai_flavor: '语言 AI 味',
    literary_flatness: '文学承载不足',
    logic_and_character: '逻辑 / 人设问题',
    unknown_issue: '待关注问题'
  };
  const normalizedFeature = String(feature || '').trim();
  return map[normalizedFeature] || normalizedFeature || '待关注问题';
}

function formatCriticSeverity(severity) {
  const normalized = String(severity || '').toLowerCase();
  if (normalized === 'critical') return '严重';
  if (normalized === 'major') return '明显';
  return '轻微';
}

function criticSeverityTagType(severity: unknown) {
  const normalized = String(severity || '').toLowerCase();
  if (normalized === 'critical') return 'error';
  if (normalized === 'major') return 'warning';
  return 'default';
}

// 角色选项
const characterOptions = computed(() => 
  characters.value.map(c => ({
    label: c.name || `角色 ${c.id}`,
    value: String(c.id)
  }))
);

async function loadCharacters() {
  if (!projectStore.currentProject) return;
  try {
    characters.value = await fetchCharacters(projectStore.currentProject, true);
  } catch (_e: unknown) {
    characters.value = [];
  }
}

function onPresentationSettingsUpdated(payload?: unknown) {
  const projectName = payload && typeof payload === 'object' && 'projectName' in payload
    ? String((payload as { projectName?: unknown }).projectName || '')
    : '';
  if (projectName && projectName !== projectStore.currentProject) return;
  void loadPresentationManifest();
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
    localManifestRevision += 1;
    presentationManifest.value = manifest as PresentationManifest;
    return;
  }
  void loadPresentationManifest();
}

onMounted(() => {
  loadCharacters();
  void loadPresentationImageModels();
  void loadPresentationManifest();
  bus.on('presentation-settings-updated', onPresentationSettingsUpdated);
  bus.on('presentation-manifest-updated', onPresentationManifestUpdated);
});
onBeforeUnmount(() => {
  bus.off('presentation-settings-updated', onPresentationSettingsUpdated);
  bus.off('presentation-manifest-updated', onPresentationManifestUpdated);
});
watch(() => projectStore.currentProject, () => {
  presentationManifestRequestId += 1;
  localManifestRevision += 1;
  loadCharacters();
  void loadPresentationManifest();
});

// 监听外部触发的 Bridge 请求（从蓝图连线）
bus.on('trigger-bridge', (payload: unknown) => {
  const data = payload && typeof payload === 'object' ? payload as BridgeTriggerPayload : null;
  const prevScene = data?.prevScene ?? null;
  const nextScene = data?.nextScene ?? null;
  mode.value = 'bridge';
  bridgePrevScene.value = prevScene;
  bridgeNextScene.value = nextScene;
});

// 监听取消生成事件
bus.on('cancel-loading', (payload: CancelLoadingPayload | undefined) => {
  if (payload?.scope && payload.scope !== 'production') return;
  if (abortController) {
    abortController.abort();
    abortController = null;
    generating.value = false;
    bus.emit('toast', { type: 'info', message: '已取消生成' });
  }
});

async function handleSingleNode() {
  if (!sceneStore.currentNode || sceneStore.selectionType !== 'dialogue') return;
  generating.value = true;
  abortController = new AbortController();
  try {
    const context = sceneStore.currentNode.txt || '';
    await streamComposeRequest({
      operation: 'continue',
      mode: 'single-node',
      projectName: projectStore.currentProject,
      context,
      length: Number(singleLength.value) || 50,
      selectedCharacterIds: [Number(sceneStore.currentNode.chr) || 0],
    }, {
      loadingText: 'AI 正在继续写作...',
      onChunk: (data) => {
        bus.emit('ai-append-text', { chunk: data.text || '' });
      }
    });
  } catch (e: unknown) {
    if (isAbortError(e)) return;
    bus.emit('toast', { type: 'error', message: 'AI 单段续写失败' });
  } finally {
    generating.value = false;
    abortController = null;
  }
}

// 将节点树转换为 .arc 文本
function nodesToArc(nodes: ArcDialogueNode[]) {
  if (!nodes || !Array.isArray(nodes)) return '';
  let text = '';
  nodes.forEach(node => {
    // 忽略空节点或纯行为节点（不传给 AI）
    if (!node || !node.txt) return;

    // 节点级 thought（如有）也一并提供给 AI 作为上下文
    if (node.thought) {
      text += `<conception>${String(node.thought)}</conception>\n`;
    }
    
    text += `${formatSpeakerMarker(node.chr, node.speaker, characterStore.map)}\n${node.txt}\n\n`;
    
    if (node.opt) {
      text += `<choice>\n`;
      node.opt.forEach(opt => {
        text += `  <opt text="${opt.optn}">\n`;
        const optContent = nodesToArc(opt.dia || []);
        text += optContent.split('\n').map(l => `    ${l}`).join('\n');
        text += `\n  </opt>\n`;
      });
      text += `</choice>\n\n`;
    }
  });
  return text;
}

type StreamComposeOptions = {
  onChunk?: (data: ComposeStreamPayload) => void;
  onDone?: (data: ComposeStreamPayload) => void;
  loadingText?: string;
};

async function streamComposeRequest(payload: ComposeRequestPayload, { onChunk, onDone, loadingText = 'AI 正在创作中...' }: StreamComposeOptions = {}): Promise<StreamComposeResult> {
  const response = await fetchWithAuth('/api/scriptwriter/compose/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal: abortController?.signal,
  });

  if (response.status === 409) {
    return { conflict: await response.json() };
  }

  if (!response.ok) {
    const err = await response.json().catch(() => null);
    throw new Error(err?.error || `HTTP ${response.status}`);
  }

  const reader = response.body?.getReader?.();
  if (!reader) throw new Error('流式响应不可用');

  const task = createStreamingTask('production', {
    text: loadingText,
    canCancel: true,
    autoStart: true,
    onCancel: () => {
      try {
        abortController?.abort?.('user_cancelled');
      } catch {}
    },
  });

  let donePayload: ComposeStreamPayload | null = null;
  try {
    await consumeSSEReader(reader, {
      signal: abortController?.signal,
      onEvent: async (evt) => {
        const data = parseSSEEventPayload(evt?.data || '') as ComposeStreamPayload;
        const progressText = data.onProgress?.message || data.onStart?.message || data.message || loadingText;
        const statsPayload = (data.onStats || null) as Record<string, unknown> | null;

        if (evt?.event === 'chunk') {
          if (statsPayload) task.applyStats(statsPayload, loadingText, { progress: progressText });
          else if (data.text) task.push(data.text, loadingText, { progress: progressText });
          onChunk?.(data);
          return;
        }

        if (evt?.event === 'progress') {
          task.setProgress(progressText);
          if (statsPayload) task.applyStats(statsPayload, loadingText, { progress: progressText });
          return;
        }

        if (evt?.event === 'cancelled') {
          task.setProgress(data.onCancelled?.message || '任务已取消');
          throw new DOMException(data.onCancelled?.message || 'user_cancelled', 'AbortError');
        }

        if (evt?.event === 'done') {
          if (statsPayload) task.applyStats(statsPayload, loadingText, { progress: data.onDone?.message || '已完成' });
          task.setProgress(data.onDone?.message || '已完成');
          onDone?.(data);
          donePayload = data;
          return;
        }

        if (evt?.event === 'error') {
          task.setProgress(data.onError?.message || data.error || '生成失败');
          throw new Error(data.error || data.message || data.onError?.message || '生成失败');
        }
      },
    });
  } finally {
    task.dispose();
  }

  return { done: donePayload };
}

function buildCurrentSceneContextForCritic() {
  if (!sceneStore.currentScene) return '';
  let context = '';
  if (sceneStore.currentScene.scene) {
    context += `# ${sceneStore.currentScene.scene}\n`;
  }
  if (sceneStore.currentScene.intro) {
    context += `@intro\n${sceneStore.currentScene.intro}\n\n`;
  }
  if (sceneStore.currentScene.thought) {
    context += `<conception>\n${sceneStore.currentScene.thought}\n</conception>\n\n`;
  }
  context += nodesToArc(sceneStore.currentScene.dia || []);
  return context.trim();
}

function buildCriticActiveContext() {
  const parts: string[] = [];
  if (fileStore.selectedFile?.path) {
    parts.push(`当前文件：${fileStore.selectedFile.path}`);
  }
  if (isNovelMode.value) {
    parts.push('当前审查目标：整篇小说正文');
  } else {
    if (sceneStore.currentScene?.scene) {
      parts.push(`当前场景：${sceneStore.currentScene.scene}`);
    }
    if (sceneStore.currentNode?.id) {
      parts.push(`当前焦点节点ID：${sceneStore.currentNode.id}`);
    }
    if (sceneStore.currentNode?.txt) {
      parts.push(`当前焦点节点文本：${sceneStore.currentNode.txt}`);
    }
  }
  return parts.join('\n');
}

async function handleCriticReview() {
  if (!canRunCritic.value) {
    bus.emit('toast', { type: 'warning', message: isNovelMode.value ? '请先打开一个小说文件' : '请先选择一个场景再进行评审' });
    return;
  }

  generating.value = true;
  abortController = new AbortController();
  criticResult.value = null;

  try {
    await sceneStore._saveStory?.();

    const currentFilePath = fileStore.selectedFile?.path || sceneStore.currentFilePath || '';
    const payload = {
      projectName: projectStore.currentProject,
      guidance: criticGuidance.value || '',
      activeContext: buildCriticActiveContext(),
      sceneName: isNovelMode.value ? '' : (sceneStore.currentScene?.scene || ''),
      filePath: currentFilePath,
      script_text: isNovelMode.value
        ? String(sceneStore.scriptData || '')
        : buildCurrentSceneContextForCritic(),
    };

    const response = await fetchWithAuth('/api/ai/critic', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: abortController?.signal,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => null);
      throw new Error(err?.error || `HTTP ${response.status}`);
    }

    criticResult.value = await response.json();
    bus.emit('toast', { type: 'success', message: isNovelMode.value ? '小说评审完成' : '场景评审完成' });
  } catch (e: unknown) {
    if (isAbortError(e)) return;
    bus.emit('toast', { type: 'error', message: getErrorMessage(e, 'Critic 评审失败') });
  } finally {
    generating.value = false;
    abortController = null;
  }
}

async function reloadCurrentStorySelection(currentSceneName: string | null | undefined, currentNodeId: number | null | undefined, preferNextNode = true) {
  if (!fileStore.selectedFile?.path) return;
  await sceneStore.loadStory(fileStore.selectedFile.path);
  if (!currentSceneName) return;
  const scene = (Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : []).find(s => s.scene === currentSceneName);
  if (!scene) return;
  sceneStore.selectScene(scene);
  if (!currentNodeId) return;

  let targetNode: ArcDialogueNode | null = null;
  const flatNodes: ArcDialogueNode[] = [];
  const flatten = (nodes: ArcDialogueNode[]) => {
    nodes.forEach(n => {
      flatNodes.push(n);
      if (n.opt) n.opt.forEach(o => flatten(o.dia || []));
    });
  };
  flatten(scene.dia || []);

  const currentIndex = flatNodes.findIndex(n => n.id === currentNodeId);
  if (preferNextNode && currentIndex !== -1 && currentIndex + 1 < flatNodes.length) {
    targetNode = flatNodes[currentIndex + 1];
  } else {
    targetNode = flatNodes.find(n => n.id === currentNodeId) || null;
  }

  if (targetNode) {
    sceneStore.selectDialogue(targetNode);
    setTimeout(() => {
      const el = document.getElementById(`node-${targetNode.id}`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 100);
  }
}

async function handleMultiNode() {
  if (isNovelMode.value) {
    generating.value = true;
    abortController = new AbortController();

    try {
      await sceneStore._saveStory();
      lastThought.value = '';
      sceneStore.setLastScriptwriterThought('');

      const currentFilePath = fileStore.selectedFile?.path || sceneStore.currentFilePath || '';
      const resultWrapper = await streamComposeRequest({
        operation: 'continue',
        mode: 'multi-node',
        projectName: projectStore.currentProject,
        context: String(sceneStore.scriptData || ''),
        guidance: multiPrompt.value || '请紧接当前正文继续写作，保持小说格式一致。',
        selectedCharacterIds: [],
        segmentCount: Number(multiSegments.value),
        filePath: currentFilePath,
        sceneName: '',
        nodeId: 0,
        lastNodeText: '',
      }, {
        loadingText: 'AI 正在续写小说...',
        onDone: (result) => {
          if (result.thought) {
            lastThought.value = result.thought;
            sceneStore.setLastScriptwriterThought(result.thought);
          }
        }
      });

      if (resultWrapper?.done?.thought) {
        lastThought.value = resultWrapper.done.thought;
        sceneStore.setLastScriptwriterThought(resultWrapper.done.thought);
      }
      await sceneStore.loadStory(currentFilePath);
      bus.emit('toast', { type: 'success', message: 'AI 小说续写完成' });
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      bus.emit('toast', { type: 'error', message: getErrorMessage(e, 'AI 小说续写失败') });
    } finally {
      generating.value = false;
      abortController = null;
    }
    return;
  }

  if (!sceneStore.currentScene) return;
  if (selectedCharacterIds.value.length === 0 || selectedCharacterIds.value.length > 4) {
    bus.emit('toast', { type: 'error', message: '请选择 1 到 4 个参与角色' });
    return;
  }
  generating.value = true;
  abortController = new AbortController();
  
  // 确保在请求 AI 之前保存当前剧本
  try {
    await sceneStore._saveStory();
  } catch (e: unknown) {
    console.warn('AI 请求前自动保存失败:', e);
  }

  try {
    // 构建完整的场景文本上下文
    let context = '';
    if (sceneStore.currentScene) {
      // 场景标题与场景级 thought 也纳入上下文，提升续写一致性
      if (sceneStore.currentScene.scene) {
        context += `# ${sceneStore.currentScene.scene}\n`;
      }
      if (sceneStore.currentScene.intro) {
        context += `@intro\n${sceneStore.currentScene.intro}\n\n`;
      }
      if (sceneStore.currentScene.thought) {
        context += `<conception>\n${sceneStore.currentScene.thought}\n</conception>\n\n`;
      }
      context += nodesToArc(sceneStore.currentScene.dia || []);
    }
    
    // 获取当前节点的文本作为锚点（如果是从场景开始写，则为空）
    const lastNodeText = sceneStore.currentNode?.txt || '';
    const currentSceneName = sceneStore.currentScene?.scene;
    const currentNodeId = sceneStore.currentNode?.id;

    lastThought.value = ''; 
    sceneStore.setLastScriptwriterThought('');
    
    const payload: ComposeRequestPayload = {
      operation: 'continue',
      mode: 'multi-node',
      projectName: projectStore.currentProject,
      context,
      guidance: multiPrompt.value,
      selectedCharacterIds: selectedCharacterIds.value.map((v) => Number(v)).filter((n) => !Number.isNaN(n)),
      segmentCount: Number(multiSegments.value),
      filePath: fileStore.selectedFile?.path || '',
      sceneName: sceneStore.currentScene?.scene || '',
      nodeId: sceneStore.currentNode?.id || 0,
      lastNodeText,
    };

    let firstPass = await streamComposeRequest(payload, {
      loadingText: 'AI 正在构思剧情...',
    }).catch(async (e) => {
      throw e;
    });

    if (firstPass?.conflict) {
      const errorData = firstPass.conflict;

      // 使用 Naive UI 的 Dialog
      return new Promise<void>((resolve) => {
        dialog.warning({
          title: '信息缺失',
          content: errorData.message || '检测到缺失信息，是否继续？',
          positiveText: '继续生成',
          negativeText: '取消',
          onPositiveClick: async () => {
            try {
              // 用户确认继续，重新发送请求
              payload.confirmContinue = true;
              abortController = new AbortController();
              
              const currentSceneName = sceneStore.currentScene?.scene;
              const currentNodeId = sceneStore.currentNode?.id;

              const resultWrapper = await streamComposeRequest(payload, {
                loadingText: 'AI 正在强制生成...',
                onDone: (result) => {
                  if (result.thought) {
                    lastThought.value = result.thought;
                    sceneStore.setLastScriptwriterThought(result.thought);
                  }
                }
              });

              const result = resultWrapper?.done || {};
              bus.emit('toast', { type: 'success', message: 'AI 续写完成' });
              await reloadCurrentStorySelection(currentSceneName, currentNodeId, true);
            } catch (e: unknown) {
              if (isAbortError(e)) return;
              bus.emit('toast', { type: 'error', message: getErrorMessage(e, 'AI 多段续写失败') });
            } finally {
              generating.value = false;
              abortController = null;
              resolve();
            }
          },
          onNegativeClick: () => {
            generating.value = false;
            resolve();
          }
        });
      });
    }

    const result = firstPass?.done || {};
    if (result.thought) {
      lastThought.value = result.thought;
      sceneStore.setLastScriptwriterThought(result.thought);
    }
    // 成功提示
    bus.emit('toast', { type: 'success', message: 'AI 续写完成' });
    await reloadCurrentStorySelection(currentSceneName, currentNodeId, true);
  } catch (e: unknown) {
    if (isAbortError(e)) return;
    bus.emit('toast', { type: 'error', message: getErrorMessage(e, 'AI 多段续写失败') });
  } finally {
    generating.value = false;
    abortController = null;
  }
}

async function handleRewriteScene() {
  if (isNovelMode.value) {
    generating.value = true;
    abortController = new AbortController();

    try {
      await sceneStore._saveStory();
      const currentFilePath = fileStore.selectedFile?.path || sceneStore.currentFilePath || '';
      const combinedGuidance = [rewriteThought.value, rewriteGuidance.value]
        .map(v => String(v || '').trim())
        .filter(Boolean)
        .join('\n\n');

      const resultWrapper = await streamComposeRequest({
        operation: 'rewrite_scene',
        mode: 'rewrite-scene',
        projectName: projectStore.currentProject,
        context: String(sceneStore.scriptData || ''),
        guidance: combinedGuidance || '请重写当前全文，使其成为更流畅、更一致的纯文本小说。',
        selectedCharacterIds: [],
        segmentCount: 0,
        filePath: currentFilePath,
        sceneName: '',
        nodeId: 0,
        rewrite: true,
      }, {
        loadingText: 'AI 正在重写小说...',
        onDone: (result) => {
          if (result.thought) {
            lastThought.value = result.thought;
            sceneStore.setLastScriptwriterThought(result.thought);
          }
        }
      });

      if (resultWrapper?.done?.thought) {
        lastThought.value = resultWrapper.done.thought;
        sceneStore.setLastScriptwriterThought(resultWrapper.done.thought);
      }
      await sceneStore.loadStory(currentFilePath);
      bus.emit('toast', { type: 'success', message: '小说重写完成' });
    } catch (e: unknown) {
      if (isAbortError(e)) return;
      bus.emit('toast', { type: 'error', message: getErrorMessage(e, '小说重写失败') });
    } finally {
      generating.value = false;
      abortController = null;
    }
    return;
  }

  if (!sceneStore.currentScene) {
    bus.emit('toast', { type: 'error', message: '请先选择一个场景' });
    return;
  }
  if (selectedCharacterIds.value.length === 0 || selectedCharacterIds.value.length > 4) {
    bus.emit('toast', { type: 'error', message: '请选择 1 到 4 个参与角色' });
    return;
  }

  generating.value = true;
  abortController = new AbortController();

  try {
    // 保存当前文件
    await sceneStore._saveStory();
    const currentSceneName = sceneStore.currentScene?.scene;

    // 构建上下文 (场景标题 + intro，但不包含对话)
    let context = '';
    if (sceneStore.currentScene.scene) {
      context += `# ${sceneStore.currentScene.scene}\n`;
    }
    if (sceneStore.currentScene.intro) {
      context += `@intro\n${sceneStore.currentScene.intro}\n\n`;
    }
    if (rewriteThought.value) {
      context += `<conception>\n${rewriteThought.value}\n</conception>\n\n`;
    }
    // 注意：不包含现有对话，因为这是重写

    const payload = {
      operation: 'rewrite_scene',
      mode: 'rewrite-scene',
      projectName: projectStore.currentProject,
      context,
      guidance: rewriteGuidance.value || '请重写整个场景，生成完整的对话内容。',
      selectedCharacterIds: selectedCharacterIds.value.map((v) => Number(v)).filter((n) => !Number.isNaN(n)),
      segmentCount: 0,
      filePath: fileStore.selectedFile?.path || '',
      sceneName: sceneStore.currentScene?.scene || '',
      nodeId: 0,
      rewrite: true
    };

    const resultWrapper = await streamComposeRequest(payload, {
      loadingText: 'AI 正在重写场景...',
      onDone: (result) => {
        if (result.thought) {
          lastThought.value = result.thought;
          sceneStore.setLastScriptwriterThought(result.thought);
        }
      }
    });

    bus.emit('toast', { type: 'success', message: '场景重写完成' });
    await reloadCurrentStorySelection(currentSceneName, 0, false);
  } catch (e: unknown) {
    if (isAbortError(e)) return;
    bus.emit('toast', { type: 'error', message: getErrorMessage(e, '场景重写失败') });
  } finally {
    generating.value = false;
    abortController = null;
  }
}

async function handleBridge() {

  if (!canGenerateBridge.value) return;
  generating.value = true;
  abortController = new AbortController();
  bridgeResult.value = [];
  
  try {
    const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
    const prevSceneData = scenes.find(s => s.scene === bridgePrevScene.value);
    const nextSceneData = scenes.find(s => s.scene === bridgeNextScene.value);
    
    if (!prevSceneData || !nextSceneData) {
      throw new Error('找不到指定场景');
    }
    
    const resultWrapper = await streamComposeRequest({
      operation: 'bridge',
      mode: 'bridge',
      projectName: projectStore.currentProject,
      prevScene: prevSceneData,
      nextScene: nextSceneData,
      pacing: bridgePacing.value,
      guidance: bridgeGuidance.value,
      filePath: fileStore.selectedFile?.path || '',
      sceneName: sceneStore.currentScene?.scene || '',
    }, {
      loadingText: 'AI 正在生成过渡场景...',
      onDone: (result) => {
        bridgeResult.value = result.dialogues || [];
      }
    });

    bridgeResult.value = resultWrapper?.done?.dialogues || bridgeResult.value || [];
    
    if (bridgeResult.value.length > 0) {
      bus.emit('toast', { type: 'success', message: `生成了 ${bridgeResult.value.length} 条过渡对话` });
    } else {
      bus.emit('toast', { type: 'warning', message: '未生成任何对话' });
    }
  } catch (e: unknown) {
    if (isAbortError(e)) return;
    console.error('Bridge generation failed:', e);
    bus.emit('toast', { type: 'error', message: getErrorMessage(e, '生成过渡对话失败') });
  } finally {
    generating.value = false;
    abortController = null;
  }
}

// 从场景数据中提取摘要
function extractSummary(sceneData: SceneDialogueCarrier | null | undefined) {
  if (!sceneData?.dia?.length) return '(空场景)';
  const firstFew = sceneData.dia.slice(0, 3);
  return firstFew.map(d => `${chrName(d.chr)}: ${(d.txt || '').slice(0, 50)}...`).join(' | ');
}

// 将生成结果插入到场景
function insertBridgeResult() {
  if (!bridgeResult.value.length) return;
  
  // 查找目标场景（插入到 nextScene 的开头）
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  const targetScene = scenes.find(s => s.scene === bridgeNextScene.value);
  
  if (!targetScene) {
    bus.emit('toast', { type: 'error', message: '找不到目标场景' });
    return;
  }
  
  // 生成新的对话节点 ID
  let maxId = 0;
  scenes.forEach(s => {
    (s.dia || []).forEach(d => {
      if (d.id > maxId) maxId = d.id;
    });
  });
  
  // 构建新对话节点
  const newNodes = bridgeResult.value.map((d, idx) => ({
    id: maxId + idx + 1,
    chr: d.chr,
    txt: d.txt
  }));
  
  // 插入到场景开头
  if (!targetScene.dia) targetScene.dia = [];
  targetScene.dia.unshift(...newNodes);
  
  // 保存
  sceneStore._saveStory?.();
  
  bus.emit('toast', { type: 'success', message: `已插入 ${newNodes.length} 条对话到「${targetScene.scene}」` });
  bridgeResult.value = [];
}
</script>

<style scoped>
.right-panel-section {
  padding: 0;
  flex: 1;
  min-height: 0;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 与节点编辑器一致：卡片占满面板，标题固定，内容区域独立滚动。 */
#ai-screenwriter :deep(.n-card) {
  flex: 1;
  min-height: 0;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

#ai-screenwriter :deep(.n-card__content),
#ai-screenwriter :deep(.n-card-content) {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
}

.mode-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  order: 1;
}

.toolbox-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  padding-bottom: 20px;
}

.toolbox-module {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.continuation-module {
  order: 0;
}

.critic-module {
  order: 1;
  padding-top: 18px;
  border-top: 1px solid color-mix(in srgb, var(--spark-border), transparent 12%);
}

.image-generation-module {
  order: 2;
  padding-top: 18px;
  border-top: 1px solid color-mix(in srgb, var(--spark-border), transparent 12%);
}

.toolbox-module-heading {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding-bottom: 10px;
  border-bottom: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  font-size: var(--spark-fs-base);
  font-weight: 700;
  color: var(--spark-primary);
}

.toolbox-field-label {
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-text-secondary);
}

.presentation-tool-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  margin-bottom: 12px;
}

.presentation-model-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.presentation-participants {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.presentation-style-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 9px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 12%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 2%);
}

.presentation-tool-heading {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--spark-fs-xs);
  font-weight: 650;
  color: var(--spark-text);
}

.presentation-current-line {
  min-width: 0;
  padding: 6px 8px;
  border-radius: 7px;
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 72%);
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
  color: var(--spark-text);
  font-size: var(--spark-fs-2xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.presentation-current-line.is-empty {
  border-color: color-mix(in srgb, var(--spark-border), transparent 8%);
  background: color-mix(in srgb, var(--spark-bg) 44%, transparent);
  color: var(--spark-text-muted);
}

.illustration-batch-controls {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding-top: 4px;
}

.background-preview {
  width: 100%;
  height: clamp(132px, 24vh, 280px);
  min-width: 0;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 4%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg), black 8%);
}

.background-preview img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.background-preview.is-empty {
  background: color-mix(in srgb, var(--spark-bg) 72%, transparent);
}

.background-preview-empty {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  text-align: center;
}

.background-preview-empty .n-icon {
  font-size: 24px;
}

.presentation-model-select {
  width: min(100%, 230px);
  flex: 1 1 180px;
}

.presentation-wide-select {
  width: 100%;
}

.presentation-tool-tip {
  font-size: var(--spark-fs-2xs);
  line-height: 1.45;
}

.presentation-hidden-input {
  display: none;
}

/* Bridge 结果样式 */
.bridge-result {
  margin-top: 16px;
}

.bridge-dialogues {
  max-height: 200px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bridge-dialogue-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px;
  background: var(--spark-bg);
  border-radius: 4px;
  border-left: 3px solid var(--node-dialogue);
}

.bridge-dialogue-item .dialogue-text {
  flex: 1;
  font-size: var(--spark-fs-sm);
  line-height: 1.4;
  color: var(--spark-text);
}

.thought-process {
  margin-top: 16px;
  border: 1px dashed var(--primary-color);
  border-radius: 8px;
  padding: 4px;
  background: rgba(var(--primary-color-rgb), 0.05);
  animation: thoughtPulse 1.6s ease-in-out infinite;
}

@keyframes thoughtPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(var(--primary-color-rgb), 0.0);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(var(--primary-color-rgb), 0.14);
  }
}

.thought-content {
  font-size: var(--spark-fs-xs);
  max-height: 300px;
  overflow-y: auto;
  padding: 8px;
  color: var(--spark-text-muted);
}

.critic-result {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--spark-bg);
  border: 1px solid rgba(208, 48, 80, 0.12);
}

.critic-risk-score {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

.critic-summary,
.critic-brief,
.critic-hit-reason,
.critic-hit-suggestion,
.critic-empty-hits {
  font-size: var(--spark-fs-sm);
  line-height: 1.6;
  color: var(--spark-text);
}

.critic-summary {
  margin-top: 10px;
}

.critic-brief {
  margin-top: 8px;
  color: var(--spark-text-muted);
}

.critic-score-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.critic-score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
}

.critic-score-label {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

.critic-hit-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.critic-hit-item {
  padding: 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.04);
}

.critic-hit-suggestion {
  margin-top: 6px;
  color: var(--spark-text-muted);
}

.critic-evidence-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}

.critic-evidence-item {
  padding: 8px;
  border-left: 3px solid rgba(208, 48, 80, 0.5);
  background: rgba(208, 48, 80, 0.05);
  border-radius: 4px;
}

.critic-evidence-quote {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text);
}

.critic-evidence-reason {
  margin-top: 4px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}
</style>
