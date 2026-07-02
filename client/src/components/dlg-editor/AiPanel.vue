<template>
  <div id="ai-screenwriter" class="right-panel-section" v-show="visible">
    <n-card 
      title="AI 编剧" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="SquarePen" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <!-- 模式选择 -->
        <n-form-item label="模式" v-if="!hideModeSelector && modeOptions.length > 1">
          <n-select 
            v-model:value="mode" 
            id="ai-mode-select" 
            placeholder="选择生成模式"
            :options="modeOptions"
          />
        </n-form-item>

        <div v-if="canEditPresentation" class="presentation-tools">
          <div class="presentation-section-heading">
            <n-icon :component="ImagePlus" />
            <span>{{ t('nodeEditor.presentation.webCue') }}</span>
          </div>

          <div class="presentation-tool-stack">
            <div class="presentation-style-card presentation-reference-card">
              <div class="presentation-tool-heading">
                <n-icon :component="Palette" />
                <span>{{ t('nodeEditor.presentation.styleReference') }}</span>
              </div>
              <n-select
                v-model:value="selectedStyleReferenceId"
                class="presentation-wide-select"
                size="small"
                clearable
                :options="styleReferenceOptions"
                :placeholder="t('nodeEditor.presentation.styleReferenceSelect')"
              />
              <n-text depth="3" class="presentation-tool-tip">
                {{ selectedStyleReferenceLabel || t('nodeEditor.presentation.nodeStyleReferenceHint') }}
              </n-text>
            </div>

            <div class="presentation-control-grid">
              <div class="presentation-control-card">
                <div class="presentation-tool-heading">
                  <n-icon :component="ImagePlus" />
                  <span>{{ t('nodeEditor.presentation.background') }}</span>
                </div>
                <div class="presentation-current-line" :class="{ 'is-empty': !currentBackgroundId }">
                  {{ currentBackgroundId || t('nodeEditor.presentation.noBackground') }}
                </div>
                <n-input
                  v-model:value="backgroundPrompt"
                  type="textarea"
                  size="small"
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  :placeholder="t('nodeEditor.presentation.generatePromptPlaceholder')"
                />
                <n-space :size="8" wrap align="center">
                  <n-button size="small" secondary :loading="backgroundUploading" @click="triggerBackgroundUpload">
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

              <div class="presentation-control-card">
                <div class="presentation-tool-heading">
                  <n-icon :component="UserRound" />
                  <span>{{ t('nodeEditor.presentation.sprite') }}</span>
                </div>
                <div class="presentation-current-line" :class="{ 'is-empty': !currentSpriteId }">
                  {{ currentSpriteId || t('nodeEditor.presentation.noSprite') }}
                </div>
                <n-input
                  v-model:value="spritePrompt"
                  type="textarea"
                  size="small"
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  :placeholder="t('nodeEditor.presentation.generateSpritePromptPlaceholder')"
                />
                <n-space :size="8" wrap align="center">
                  <n-button size="small" secondary :loading="spriteUploading" @click="triggerSpriteUpload">
                    <template #icon>
                      <n-icon :component="Upload" />
                    </template>
                    {{ t('nodeEditor.presentation.uploadSprite') }}
                  </n-button>
                  <n-button
                    v-if="currentSpriteId"
                    size="small"
                    secondary
                    type="warning"
                    @click="clearDialogueSprite"
                  >
                    <template #icon>
                      <n-icon :component="Eraser" />
                    </template>
                    {{ t('nodeEditor.presentation.clearSprite') }}
                  </n-button>
                  <n-button
                    size="small"
                    type="primary"
                    secondary
                    :disabled="!canGenerateSprite"
                    :loading="spriteGenerating"
                    @click="generateSpriteByAI"
                  >
                    <template #icon>
                      <n-icon :component="Sparkles" />
                    </template>
                    {{ t('nodeEditor.presentation.generateSprite') }}
                  </n-button>
                </n-space>
                <input
                  ref="spriteFileInputRef"
                  class="presentation-hidden-input"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  @change="onSpriteFileChange"
                />
              </div>
            </div>

            <n-select
              v-model:value="selectedImageModelKey"
              class="presentation-wide-select"
              size="small"
              clearable
              :loading="imageModelsLoading"
              :options="imageModelSelectOptions"
              :placeholder="t('nodeEditor.presentation.imageModelPlaceholder')"
            />
            <n-text v-if="!imageModelsLoading && availableImageModels.length === 0" depth="3" class="presentation-tool-tip">
              {{ t('nodeEditor.presentation.imageModelMissing') }}
            </n-text>
          </div>
        </div>

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

        <!-- Critic 手动评审 -->
        <div v-show="mode === 'critic'" class="mode-content critic-mode">
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
      </n-form>
    </n-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NForm, NFormItem, NSelect, NInputNumber, NButton, NInput, NIcon, NSpace, NTag, NDivider, NText, useDialog } from 'naive-ui';
import SparkAlert from '@/components/share/SparkAlert.vue';
import { ChartColumn, CircleCheck, Eraser, FileText, Files, GitBranch, ImagePlus, Palette, RefreshCw, Sparkles, SquarePen, Upload, UserRound, Zap } from '@lucide/vue';
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
  generatePresentationSprite,
  uploadPresentationBackground,
  uploadPresentationSprite,
  type PresentationAsset,
  type PresentationImageModel,
  type PresentationManifest,
} from '@/services/presentationService';
import { createStreamingTask, consumeSSEReader, isAbortLikeError, parseSSEEventPayload } from '@/utils/streamingRuntime';
import type { CancelLoadingPayload } from '@/eventBus';
import type { StoryCharacterDetail } from '@/services/aiContracts';
import { formatSpeakerMarker, type ArcDialogueNode, type PresentationCue } from '@/services/arcParser';

type PanelMode = 'single-node' | 'multi-node' | 'critic' | 'rewrite-scene' | 'bridge';

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

const isNovelMode = computed(() => sceneStore.fileFormat === 'novel');
const visible = computed(() => sceneStore.selectionType === 'dialogue' || sceneStore.selectionType === 'scene' || sceneStore.selectionType === 'novel' || mode.value === 'bridge');

// 模式选项
const baseModeOptions = [
  { label: '单段续写', value: 'single-node', icon: FileText },
  { label: '多段续写', value: 'multi-node', icon: Files },
  { label: 'Critic 评审', value: 'critic', icon: CircleCheck },
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
let abortController: AbortController | null = null;

const backgroundFileInputRef = ref<HTMLInputElement | null>(null);
const spriteFileInputRef = ref<HTMLInputElement | null>(null);
const backgroundUploading = ref(false);
const backgroundGenerating = ref(false);
const spriteUploading = ref(false);
const spriteGenerating = ref(false);
const backgroundPrompt = ref('');
const spritePrompt = ref('');
const imageModels = ref<PresentationImageModel[]>([]);
const imageModelsLoading = ref(false);
const selectedImageModelKey = ref<string | null>(null);
const presentationManifest = ref<PresentationManifest | null>(null);
const selectedStyleReferenceId = ref<string | null>(null);

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
const currentSpriteId = computed(() => normalizePresentationValue(currentPresentation.value.sprite));

const currentSpriteCharacterId = computed(() => {
  const node = currentDialogueNode.value;
  const value = node?.speaker || node?.chr;
  if (value === undefined || value === null || value === '旁白' || value === -1 || value === '-1') return '';
  return String(value).trim();
});

const manifestAssets = computed<Record<string, PresentationAsset>>(() => {
  const assets = presentationManifest.value?.assets;
  return assets && typeof assets === 'object' ? assets : {};
});

const styleReferenceOptions = computed(() => Object.values(manifestAssets.value)
  .filter(asset => asset.type === 'style_reference' || asset.type === 'scene_reference')
  .sort((a, b) => String(b.createdAt || '').localeCompare(String(a.createdAt || '')))
  .map(asset => ({
    label: `${asset.type === 'style_reference' ? t('nodeEditor.presentation.styleReference') : t('nodeEditor.presentation.sceneReference')} · ${asset.title || asset.id}`,
    value: asset.id,
  })));

const selectedStyleReferenceLabel = computed(() => {
  const id = selectedStyleReferenceId.value;
  if (!id) return '';
  const asset = manifestAssets.value[id];
  return asset ? t('nodeEditor.presentation.activeStyleReference', { value: asset.title || asset.id }) : '';
});

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

const canGenerateBackground = computed(() =>
  !!projectStore.currentProject
  && !!backgroundPrompt.value.trim()
  && !!selectedImageModel.value
);

const canGenerateSprite = computed(() =>
  !!projectStore.currentProject
  && !!spritePrompt.value.trim()
  && !!selectedImageModel.value
  && !!currentSpriteCharacterId.value
);

function normalizePresentationValue(value: unknown): string {
  const raw = Array.isArray(value) ? value[0] : value;
  return typeof raw === 'string' ? raw.trim() : '';
}

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

function updateManifest(manifest: PresentationManifest | undefined | null) {
  if (manifest) presentationManifest.value = manifest;
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
    selectedStyleReferenceId.value = null;
    return;
  }
  try {
    const result = await fetchPresentationManifest(projectStore.currentProject);
    presentationManifest.value = result.manifest || null;
    if (selectedStyleReferenceId.value && !manifestAssets.value[selectedStyleReferenceId.value]) {
      selectedStyleReferenceId.value = null;
    }
  } catch (_error: unknown) {
    presentationManifest.value = null;
  }
}

async function savePresentationBinding() {
  try {
    await sceneStore._saveStory?.();
  } catch (error: unknown) {
    bus.emit('toast', { type: 'warning', message: presentationErrorMessage(error, t('nodeEditor.presentation.bindingSaveFailed')) });
  }
}

function setDialoguePresentationValue(key: 'bg' | 'sprite', value: string | null) {
  const node = currentDialogueNode.value;
  if (!node) return;
  const nextPresentation: PresentationCue = { ...(node.presentation || {}) };
  if (!value) delete nextPresentation[key];
  else nextPresentation[key] = value;
  sceneStore.updateCurrentDialogue({
    presentation: Object.keys(nextPresentation).length > 0 ? nextPresentation : undefined,
  });
  void savePresentationBinding();
}

function collectDialogueContextNodes(): ArcDialogueNode[] {
  const scene = sceneStore.currentScene;
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

function getCurrentDialogueWindow() {
  const nodes = collectDialogueContextNodes();
  const current = currentDialogueNode.value;
  const index = current ? nodes.indexOf(current) : -1;
  if (index < 0) return [];
  return nodes.slice(Math.max(0, index - 2), Math.min(nodes.length, index + 3));
}

function currentCharacterDetail() {
  const id = currentSpriteCharacterId.value;
  if (!id) return null;
  const byId = characters.value.find(ch => String(ch.id) === id);
  if (byId) return byId;
  const name = chrName(id);
  return characters.value.find(ch => ch.name === name) || null;
}

function buildPresentationImagePrompt(kind: 'background' | 'sprite', userPrompt: string) {
  const scene = sceneStore.currentScene;
  const node = currentDialogueNode.value;
  const contextNodes = getCurrentDialogueWindow()
    .map(item => `${chrName(item.speaker || item.chr)}：${String(item.txt || '').trim()}`)
    .filter(line => !line.endsWith('：'))
    .join('\n');
  const character = currentCharacterDetail();
  const styleReference = selectedStyleReferenceId.value ? manifestAssets.value[selectedStyleReferenceId.value] : null;
  const lines = [
    '你正在为一部 Web 视觉小说生成演出素材。请优先使用自然语言语义理解，不要把以下内容画成界面、字幕或水印。',
    '统一画风要求：画面需要能与同一项目内的其他素材保持一致；若提供了参考图，请优先继承其构图语言、色彩倾向、笔触/摄影质感与角色一致性。',
    '跨端构图要求：默认生成横版素材，适合 PC 舞台；移动端会居中显示，并使用同图的模糊扩展填充上下区域，所以主体和关键视觉信息必须放在安全中心区域，不要贴边。',
    styleReference ? `已选风格参考：${styleReference.title || styleReference.id}` : '',
    scene?.scene ? `当前场景：${scene.scene}` : '',
    scene?.intro ? `场景引言：${scene.intro}` : '',
    scene?.thought ? `场景构思：${scene.thought}` : '',
    node?.txt ? `当前节点文本：${chrName(node.speaker || node.chr)}：${node.txt}` : '',
    contextNodes ? `邻近剧情片段：\n${contextNodes}` : '',
  ];

  if (kind === 'background') {
    lines.push(
      '任务：生成背景图。不要出现角色立绘、对话框、UI、标题字、漫画分镜格或大段文字；画面应像可用于视觉小说舞台的场景背景。',
      '画幅：1536x1024，横版，电影感构图，中心安全区清晰。',
    );
  } else if (kind === 'sprite') {
    lines.push(
      `任务：生成角色立绘。目标角色：${character?.name || chrName(currentSpriteCharacterId.value)}。`,
      character?.content ? `角色设定：${character.content}` : '',
      '立绘要求：角色主体清晰，适合叠加在视觉小说背景上；避免复杂背景、UI、文字、水印；尽量保持透明或纯净背景感。',
      '画幅：1024x1536，竖版，角色位于中心安全区。',
    );
  }
  lines.push(`用户具体要求：${userPrompt.trim()}`);
  return lines.filter(Boolean).join('\n');
}

function referenceAssetIdsFor(kind: 'background' | 'sprite') {
  const model = selectedImageModel.value;
  if (!imageModelSupportsReference(model)) return [];
  const ids = new Set<string>();
  if (selectedStyleReferenceId.value) ids.add(selectedStyleReferenceId.value);
  if (kind === 'background' && currentBackgroundId.value.startsWith('bg_')) ids.add(currentBackgroundId.value);
  if (kind === 'sprite' && currentSpriteId.value.startsWith('sprite_')) ids.add(currentSpriteId.value);
  return Array.from(ids).slice(0, 4);
}

function triggerBackgroundUpload() {
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
  if (!file || !projectStore.currentProject) return;
  backgroundUploading.value = true;
  try {
    const result = await uploadPresentationBackground(projectStore.currentProject, file, file.name);
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setDialoguePresentationValue('bg', result.asset.id);
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
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  const prompt = backgroundPrompt.value.trim();
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
  try {
    const result = await generatePresentationBackground(projectStore.currentProject, {
      prompt: buildPresentationImagePrompt('background', prompt),
      title: currentDialogueNode.value?.txt?.trim().slice(0, 18) || t('nodeEditor.presentation.generatedBackgroundTitle'),
      size: '1536x1024',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssetIds: referenceAssetIdsFor('background'),
    });
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setDialoguePresentationValue('bg', result.asset.id);
    backgroundPrompt.value = '';
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.generateSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.generateFailed')) });
  } finally {
    backgroundGenerating.value = false;
  }
}

function triggerSpriteUpload() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  if (!currentSpriteCharacterId.value) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.characterRequired') });
    return;
  }
  spriteFileInputRef.value?.click();
}

async function onSpriteFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (input) input.value = '';
  if (!file || !projectStore.currentProject) return;
  spriteUploading.value = true;
  try {
    const result = await uploadPresentationSprite(projectStore.currentProject, file, {
      title: `${currentSpriteCharacterId.value}-${file.name}`,
      characterId: currentSpriteCharacterId.value,
      expression: 'default',
    });
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setDialoguePresentationValue('sprite', result.asset.id);
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.spriteUploadSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.spriteUploadFailed')) });
  } finally {
    spriteUploading.value = false;
  }
}

function clearDialogueSprite() {
  setDialoguePresentationValue('sprite', null);
  bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.spriteClearSuccess') });
}

async function generateSpriteByAI() {
  if (!projectStore.currentProject) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.projectRequired') });
    return;
  }
  if (!currentSpriteCharacterId.value) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.characterRequired') });
    return;
  }
  const prompt = spritePrompt.value.trim();
  const model = selectedImageModel.value;
  if (!prompt) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.promptRequired') });
    return;
  }
  if (!model) {
    bus.emit('toast', { type: 'warning', message: t('nodeEditor.presentation.imageModelMissing') });
    return;
  }
  spriteGenerating.value = true;
  try {
    const result = await generatePresentationSprite(projectStore.currentProject, {
      prompt: buildPresentationImagePrompt('sprite', prompt),
      title: currentCharacterDetail()?.name || currentSpriteCharacterId.value || t('nodeEditor.presentation.generatedSpriteTitle'),
      characterId: currentSpriteCharacterId.value,
      expression: 'default',
      size: '1024x1536',
      platformId: Number(model.platform_id),
      modelId: Number(model.model_id),
      referenceAssetIds: referenceAssetIdsFor('sprite'),
    });
    if (!result.asset?.id) throw new Error(t('nodeEditor.presentation.uploadInvalidResult'));
    updateManifest(result.manifest);
    setDialoguePresentationValue('sprite', result.asset.id);
    spritePrompt.value = '';
    bus.emit('toast', { type: 'success', message: t('nodeEditor.presentation.spriteGenerateSuccess') });
  } catch (error: unknown) {
    bus.emit('toast', { type: 'error', message: presentationErrorMessage(error, t('nodeEditor.presentation.spriteGenerateFailed')) });
  } finally {
    spriteGenerating.value = false;
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

onMounted(() => {
  loadCharacters();
  void loadPresentationImageModels();
  void loadPresentationManifest();
});
watch(() => projectStore.currentProject, () => {
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
}

/* 让 AI 面板占更少空间，给节点编辑器更多空间 */
#ai-screenwriter.right-panel-section {
  flex: 0.6;  /* AI 面板占更少空间 */
  min-height: 0;
  overflow-y: auto;
}

.mode-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.presentation-tools {
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 8%);
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-bg) 38%, transparent);
}

.presentation-section-heading {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 10px;
  font-size: var(--spark-fs-xs);
  font-weight: 700;
  color: var(--spark-text);
}

.presentation-tool-stack {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}

.presentation-style-card,
.presentation-control-card {
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

.presentation-control-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
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

@media (max-width: 1280px) {
  .presentation-control-grid {
    grid-template-columns: 1fr;
  }
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
