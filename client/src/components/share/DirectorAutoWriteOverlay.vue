<template>
  <Transition name="daw-slide">
    <div
      v-if="visible"
      class="daw-overlay"
      role="dialog"
      aria-modal="true"
      :aria-label="t('components.directorAutoWrite.ariaLabel')"
    >
      <!-- 全局遮罩模糊层 -->
      <div class="daw-backdrop" aria-hidden="true" />

      <!-- 中央卡片 -->
      <div class="daw-card" :class="{ 'daw-card--setup': showSetup }">
        <!-- 动画装饰: 全局灵感星河动画 -->
        <SparkLoaderAnimation class="daw-loader-anim" />

        <!-- 标题行 -->
        <div class="daw-header">
          <div class="daw-header-left">
            <span class="daw-icon-wrap" aria-hidden="true">
              <n-icon :component="CreateOutline" :size="16" class="daw-pen-icon" />
            </span>
            <span class="daw-title">
              {{ showSetup ? t('components.directorAutoWrite.setupTitle') : t('components.directorAutoWrite.writingTitle') }}
            </span>
            <span
              v-if="!showSetup && snapshot?.status === 'chapter_paused'"
              class="daw-badge daw-badge--paused"
              style="margin-left: 10px;"
            >{{ t('components.directorAutoWrite.chapterComplete', { chapter: (snapshot?.lastCompletedChapterIndex ?? 0) + 1 }) }}</span>
            <span class="daw-dot-pulse" aria-hidden="true" v-if="!showSetup && snapshot?.status === 'running'">
              <span /><span /><span />
            </span>
          </div>
          <!-- 关闭按钮（setup 阶段和暂停/完成/错误阶段） -->
          <button
            v-if="showSetup || snapshot?.status !== 'running'"
            class="daw-close-btn"
            @click="handleDismiss"
            aria-label="Close"
          >
            <n-icon :component="CloseOutline" :size="16" />
          </button>
        </div>

        <!-- ===== Setup 阶段 ===== -->
        <div v-if="showSetup" class="daw-setup">
          <!-- 项目名 -->
          <div class="daw-project-row">
            <n-icon :component="FolderOpenOutline" :size="13" class="daw-project-icon" />
            <span class="daw-project-name">{{ projectStore.currentProject || '—' }}</span>
          </div>

          <!-- 恢复提示 -->
          <div v-if="resumeSummary" class="daw-resume-row">
            <n-icon :component="AlertCircleOutline" :size="13" class="daw-row-icon daw-icon--warning" />
            <div class="daw-resume-content">
              <span class="daw-resume-text">{{ resumeSummary }}</span>
              <div v-if="resumeActions.length" class="daw-resume-actions">
                <button
                  v-for="action in resumeActions"
                  :key="action.key"
                  class="daw-action-btn daw-action-btn--small daw-action-btn--primary"
                  @click="startFromAction(action)"
                >{{ action.label }}</button>
                <button class="daw-action-btn daw-action-btn--small" @click="restartFromBeginning">
                  {{ t('components.directorAutoWrite.restartFromBeginning') }}
                </button>
              </div>
            </div>
          </div>

          <!-- 配置表单 -->
          <div class="daw-form">
            <div class="daw-form-item">
              <span class="daw-form-label">{{ t('components.directorAutoWrite.genMode') }}</span>
              <SparkSegment
                v-model="config.mode"
                :options="[
                  { value: 'chapter_by_chapter', label: t('components.directorAutoWrite.chapterByChapter') },
                  { value: 'continuous_write', label: t('components.directorAutoWrite.continuousWrite') },
                ]"
              />
            </div>
            <div class="daw-form-item">
              <span class="daw-form-label">{{ t('components.directorAutoWrite.exportFormat') }}</span>
              <SparkSegment
                v-model="config.exportFormat"
                :options="[
                  { value: 'arc', label: t('components.directorAutoWrite.formatArc') },
                  { value: 'novel', label: t('components.directorAutoWrite.formatNovel') },
                ]"
              />
            </div>
            <div v-if="chapterOptions.length > 1" class="daw-form-item">
              <span class="daw-form-label">{{ t('components.directorAutoWrite.startChapter') }}</span>
              <select v-model="config.startChapterIndex" class="daw-select">
                <option v-for="opt in chapterOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </div>
          </div>

          <!-- 覆盖警告 -->
          <div v-if="overwriteCount > 0" class="daw-overwrite-row">
            <n-icon :component="WarningOutline" :size="13" class="daw-row-icon daw-icon--warning" />
            <span class="daw-overwrite-text">{{ t('components.directorAutoWrite.overwriteWarning', { count: overwriteCount }) }}</span>
          </div>

          <!-- 启动按钮 -->
          <div class="daw-start-row">
            <button
              class="daw-action-btn daw-action-btn--primary daw-action-btn--large"
              :disabled="starting"
              @click="handleStart"
            >
              <n-icon v-if="starting" :component="ReloadOutline" :size="16" class="daw-spin" />
              <n-icon v-else :component="PlayOutline" :size="16" />
              <span>{{ starting ? t('components.directorAutoWrite.starting') : t('components.directorAutoWrite.startAutoWrite') }}</span>
            </button>
          </div>
        </div>

        <!-- ===== 运行阶段 ===== -->
        <div v-else>
          <!-- 项目名 -->
          <div class="daw-project-row">
            <n-icon :component="FolderOpenOutline" :size="13" class="daw-project-icon" />
            <span class="daw-project-name">{{ store.currentTask?.projectName ?? '—' }}</span>
          </div>

          <!-- 进度条 -->
          <div class="daw-progress-wrap">
            <div class="daw-progress-meta">
              <span class="daw-progress-label">{{ chapterProgressText }}</span>
              <span class="daw-progress-pct">{{ progressPercent }}%</span>
            </div>
            <div class="daw-progress-track">
              <div
                class="daw-progress-fill"
                :class="{ 'is-paused': snapshot?.status === 'chapter_paused' }"
                :style="{ width: progressPercent + '%' }"
              />
            </div>
          </div>

          <!-- 当前场景 -->
          <Transition name="daw-row-fade" mode="out-in">
            <div v-if="snapshot?.currentSceneTitle && snapshot?.status === 'running'" class="daw-scene-row">
              <n-icon :component="DocumentTextOutline" :size="13" class="daw-row-icon" />
              <span class="daw-scene-text">{{ snapshot.currentSceneTitle }}</span>
            </div>
          </Transition>

          <!-- 实时流式预览（手动触发时显示） -->
          <Transition name="daw-row-fade" mode="out-in">
            <div
              v-if="showStreamingPreview"
              class="daw-streaming-row"
            >
              <span class="daw-streaming-stats">
                {{ snapshot?.streamingChars ?? 0 }} {{ t('components.directorAutoWrite.charsUnit') }} · {{ snapshot?.streamingSpeed ?? 0 }} {{ t('components.directorAutoWrite.speedUnit') }} · {{ snapshot?.streamingElapsed ?? 0 }}s
              </span>
              <span class="daw-streaming-preview">{{ snapshot?.streamingPreview }}</span>
            </div>
          </Transition>

          <!-- 最近写入文件 -->
          <Transition name="daw-row-fade" mode="out-in">
            <div v-if="snapshot?.lastSavedFilename && snapshot?.status !== 'error'" class="daw-saved-row">
              <n-icon :component="CheckmarkCircleOutline" :size="13" class="daw-row-icon daw-icon--success" />
              <span class="daw-saved-text">{{ snapshot.lastSavedFilename }}</span>
            </div>
          </Transition>

          <!-- 错误提示 -->
          <Transition name="daw-row-fade" mode="out-in">
            <div v-if="snapshot?.lastError" class="daw-error-row">
              <n-icon :component="AlertCircleOutline" :size="13" class="daw-row-icon daw-icon--danger" />
              <span class="daw-error-text">{{ snapshot.lastError }}</span>
            </div>
          </Transition>

          <!-- 分割线 -->
          <div class="daw-divider" />

          <!-- 底部操作区 -->
          <div class="daw-footer">
            <span class="daw-hint">
              <n-icon :component="InformationCircleOutline" :size="12" class="daw-hint-icon" />
              {{ t('components.directorAutoWrite.switchProjectHint') }}
            </span>
            
            <button
              v-if="snapshot?.status === 'running'"
              class="daw-action-btn daw-action-btn--danger"
              :class="{ 'is-loading': pausing }"
              :disabled="pausing"
              @click="handlePause"
            >
              <n-icon v-if="pausing" :component="ReloadOutline" :size="14" class="daw-spin" />
              <n-icon v-else :component="SquareOutline" :size="14" />
              <span>{{ pausing ? t('components.directorAutoWrite.stopping') : t('components.directorAutoWrite.stopWriting') }}</span>
            </button>

            <template v-else-if="snapshot?.status === 'chapter_paused'">
              <button
                class="daw-action-btn daw-action-btn--primary"
                :class="{ 'is-loading': continuing }"
                :disabled="continuing"
                @click="handleContinue"
              >
                <n-icon v-if="continuing" :component="ReloadOutline" :size="14" class="daw-spin" />
                <n-icon v-else :component="PlayOutline" :size="14" />
                <span>{{ continuing ? t('components.directorAutoWrite.continuing') : t('components.directorAutoWrite.continueNextChapter') }}</span>
              </button>
              <button
                class="daw-action-btn"
                @click="handleDismiss"
              >
                <n-icon :component="CloseCircleOutline" :size="14" />
                <span>{{ t('components.directorAutoWrite.closePanel') }}</span>
              </button>
            </template>
            
            <button
              v-else
              class="daw-action-btn daw-action-btn--primary"
              @click="handleDismiss"
            >
              <n-icon :component="CloseCircleOutline" :size="14" />
              <span>{{ t('components.directorAutoWrite.closePanel') }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed, ref, reactive, watch, onMounted, onUnmounted } from 'vue';
import { NIcon } from 'naive-ui';
import {
  CreateOutline,
  FolderOpenOutline,
  DocumentTextOutline,
  CheckmarkCircleOutline,
  AlertCircleOutline,
  WarningOutline,
  InformationCircleOutline,
  SquareOutline,
  ReloadOutline,
  CloseCircleOutline,
  CloseOutline,
  PlayOutline,
} from '@vicons/ionicons5';
import { useI18n } from 'vue-i18n';
import { useDirectorAutoWriteStore } from '@/components/stores/directorAutoWriteStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { fetchWithAuth } from '@/services/apiClient';
import SparkLoaderAnimation from '@/components/share/SparkLoaderAnimation.vue';
import SparkSegment from '@/components/share/SparkSegment.vue';
import bus from '@/eventBus';

const { t } = useI18n();

const store = useDirectorAutoWriteStore();
const projectStore = useProjectStore();
const pausing = ref(false);
const continuing = ref(false);

// ── Setup 阶段状态 ──

/** 是否显示 setup 面板（手动触发入口） */
const setupVisible = ref(false);

/** 启动中 */
const starting = ref(false);

/** 配置表单 */
const config = reactive({
  mode: 'chapter_by_chapter',
  exportFormat: 'arc',
  startChapterIndex: 0,
});

/** 大纲数据（setup 阶段加载） */
const outlineData = ref<Record<string, unknown> | null>(null);
const autoWriteState = ref<Record<string, unknown> | null>(null);

/** 章节选项列表 */
const chapterOptions = computed(() => {
  const nodes = (outlineData.value?.nodes as Array<Record<string, unknown>> | undefined) ?? [];
  const chapters = nodes.filter(n => n.type === 'chapter');
  if (chapters.length <= 1) return [];
  return chapters.map((ch, i) => ({
    value: i,
    label: `#${i + 1} ${ch.title || ''}`,
  }));
});

/** 覆盖文件数 */
const overwriteCount = computed(() => {
  const sceneFiles = (autoWriteState.value?.sceneFiles as Array<Record<string, unknown>> | undefined) ?? [];
  const startIdx = config.startChapterIndex;
  return sceneFiles.filter(s => (s.chapterIndex as number) >= startIdx && s.exists).length;
});

/** 恢复摘要 */
const resumeSummary = computed(() => {
  const s = autoWriteState.value;
  if (!s || s.status === 'idle') return '';
  if (s.status === 'running' || s.status === 'chapter_paused') {
    return t('components.directorAutoWrite.resumeRunning', { chapter: ((s.nextChapterIndex as number) ?? 0) + 1 });
  }
  if (s.status === 'interrupted') {
    return t('components.directorAutoWrite.resumeInterrupted', { chapter: ((s.availableResumeChapterIndex as number) ?? 0) + 1 });
  }
  if (s.status === 'error') {
    return t('components.directorAutoWrite.resumeError', { error: s.lastError || '' });
  }
  return '';
});

/** 恢复操作列表 */
const resumeActions = computed(() => {
  const s = autoWriteState.value;
  if (!s) return [];
  const actions: Array<{ key: string; label: string; chapterIndex: number }> = [];
  if (s.availableResumeChapterIndex != null && (s.availableResumeChapterIndex as number) >= 0) {
    actions.push({
      key: 'resume',
      label: t('components.directorAutoWrite.resumeFromChapter', { chapter: ((s.availableResumeChapterIndex as number) + 1) }),
      chapterIndex: s.availableResumeChapterIndex as number,
    });
  }
  return actions;
});

// ── 可见性与阶段 ──

/** 遮罩可见：有当前任务（导演或手动触发），或 setup 阶段 */
const visible = computed(() => {
  if (setupVisible.value) return true;
  return store.currentTask !== null;
});

/** 是否显示 setup 阶段 */
const showSetup = computed(() => setupVisible.value);

/** 是否显示实时流式预览（手动触发且 running 时显示） */
const showStreamingPreview = computed(() => {
  const task = store.currentTask;
  if (!task) return false;
  // 手动触发且正在运行时显示流式区域
  return !task.fromDirector && (task.snapshot.status === 'running');
});

const snapshot = computed(() => store.currentTask?.snapshot ?? null);

/** 章节进度文本 */
const chapterProgressText = computed(() => {
  const s = snapshot.value;
  if (!s) return t('components.directorAutoWrite.preparing');
  const total = s.totalChapters ?? '?';
  const cur = s.currentChapterIndex !== null ? s.currentChapterIndex + 1 : '—';
  const title = s.currentChapterTitle ? ` · ${s.currentChapterTitle}` : '';
  return t('components.directorAutoWrite.chapterProgress', { current: cur, total, title });
});

/** 进度百分比（基于场景精细计算，保留1位小数） */
const progressPercent = computed(() => {
  const s = snapshot.value;
  if (!s || !s.totalScenes) return 0;
  const completed = s.completedScenes ?? 0;
  return Math.min(100, Math.round((completed / s.totalScenes) * 1000) / 10);
});

// ── 操作方法 ──

/** 打开 setup 面板（由 OutlineEditor 调用） */
async function openSetup(): Promise<void> {
  setupVisible.value = true;
  // 加载大纲和状态
  const proj = projectStore.currentProject;
  if (!proj) return;
  try {
    const [outlineRes, stateRes] = await Promise.all([
      fetchWithAuth(`/api/outline/${encodeURIComponent(proj)}`),
      fetchWithAuth(`/api/outline/${encodeURIComponent(proj)}/auto-write-state?export_format=${config.exportFormat}`),
    ]);
    if (outlineRes.ok) outlineData.value = await outlineRes.json();
    if (stateRes.ok) autoWriteState.value = await stateRes.json();
  } catch {
    // 静默
  }
}

async function handleStart(): Promise<void> {
  const proj = projectStore.currentProject;
  if (!proj) return;
  starting.value = true;
  try {
    const result = await store.startManualWrite(proj, {
      mode: config.mode,
      startChapterIndex: config.startChapterIndex,
      exportFormat: config.exportFormat,
    });
    if (result.success) {
      setupVisible.value = false;
    }
  } finally {
    starting.value = false;
  }
}

function startFromAction(action: { chapterIndex: number }): void {
  config.startChapterIndex = action.chapterIndex;
  handleStart();
}

function restartFromBeginning(): void {
  config.startChapterIndex = 0;
  handleStart();
}

async function handleContinue(): Promise<void> {
  const proj = store.currentTask?.projectName;
  if (!proj) return;
  // 使用 nextChapterIndex（后端在 paused 事件中提供）
  const nextIdx = snapshot.value?.nextChapterIndex ?? 0;
  continuing.value = true;
  try {
    await store.startManualWrite(proj, {
      mode: config.mode,
      startChapterIndex: nextIdx,
      exportFormat: config.exportFormat,
    });
  } finally {
    continuing.value = false;
  }
}

async function handlePause(): Promise<void> {
  const proj = store.currentTask?.projectName;
  if (!proj) return;
  pausing.value = true;
  try {
    await store.requestPause(proj);
  } finally {
    pausing.value = false;
  }
}

function handleDismiss(): void {
  if (setupVisible.value) {
    setupVisible.value = false;
    return;
  }
  const proj = store.currentTask?.projectName;
  if (proj) {
    store.dismissTask(proj);
  }
}

// ── 完成时自动关闭面板 ──
let autoCloseTimer: ReturnType<typeof setTimeout> | null = null;

watch(
  () => snapshot.value?.status,
  (status) => {
    if (autoCloseTimer) {
      clearTimeout(autoCloseTimer);
      autoCloseTimer = null;
    }
    if (status === 'complete') {
      // 延迟 2 秒后自动关闭，给用户看到完成状态的时间
      autoCloseTimer = setTimeout(() => {
        const proj = store.currentTask?.projectName;
        if (proj) store.dismissTask(proj);
        autoCloseTimer = null;
      }, 2000);
    }
  },
);

// 暴露 openSetup 供外部组件调用
defineExpose({ openSetup });

// ── 事件监听 ──
onMounted(() => {
  bus.on('open-auto-write-setup', () => {
    openSetup();
  });
});
onUnmounted(() => {
  bus.off('open-auto-write-setup');
  if (autoCloseTimer) {
    clearTimeout(autoCloseTimer);
    autoCloseTimer = null;
  }
});
</script>

<style scoped>
/* ── 顶层容器：固定定位占满全屏，但 z-index=800 让它位于层级之下 ── */
.daw-overlay {
  position: fixed;
  inset: 0;
  top: 60px; /* 桌面端：为顶部 TitleBar 保留完全清晰的空间 */
  z-index: 800; /* TitleBar(9999), ChatFloat(1000) 位于其上 */
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

/* ── 全局遮罩背景 ── */
.daw-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(10, 10, 18, 0.72);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 1;
}

/* ── 中央卡片 ── */
.daw-card {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 440px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-lg);
  padding: 24px 28px 24px;
  box-shadow:
    var(--spark-shadow-lg),
    0 0 0 1px color-mix(in srgb, var(--spark-primary), transparent 86%),
    inset 0 1px 0 color-mix(in srgb, white, transparent 92%);
  overflow: hidden;
}

/* ── 角落动画装饰 ── */
.daw-loader-anim {
  position: absolute;
  top: 10px;
  right: 10px;
  transform: scale(0.55);
  transform-origin: top right;
  pointer-events: none;
  opacity: 0.85;
  z-index: 1; /* 在卡片底色之上，文字之下 */
}


/* ── 标题行 ── */
.daw-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 8px;
}

.daw-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.daw-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--spark-primary-container);
  color: var(--spark-primary);
  flex-shrink: 0;
}

.daw-pen-icon {
  animation: dawPenRock 2.4s ease-in-out infinite;
}

@keyframes dawPenRock {
  0%, 100% { transform: rotate(-8deg); }
  50%       { transform: rotate(8deg); }
}

.daw-title {
  font-size: var(--spark-fs-lg);
  font-weight: 600;
  color: var(--spark-text);
  white-space: nowrap;
}

/* ── 脉动点 ── */
.daw-dot-pulse {
  display: flex;
  align-items: center;
  gap: 3px;
  flex-shrink: 0;
  margin-top: 4px;
}

.daw-dot-pulse span {
  display: block;
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--spark-primary);
  animation: dawDot 1.4s ease-in-out infinite;
}

.daw-dot-pulse span:nth-child(2) { animation-delay: 0.2s; }
.daw-dot-pulse span:nth-child(3) { animation-delay: 0.4s; }

@keyframes dawDot {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
  40%            { opacity: 1;    transform: scale(1); }
}

/* ── 状态徽章 ── */
.daw-badge {
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 20px;
  flex-shrink: 0;
  letter-spacing: 0.02em;
}

.daw-badge--running {
  background: color-mix(in srgb, var(--spark-success), transparent 82%);
  color: var(--spark-success);
}
.daw-badge--paused {
  background: color-mix(in srgb, var(--spark-warning), transparent 82%);
  color: var(--spark-warning);
}
.daw-badge--success {
  background: color-mix(in srgb, var(--spark-primary), transparent 82%);
  color: var(--spark-primary);
}
.daw-badge--error {
  background: var(--spark-danger-bg);
  color: var(--spark-danger);
}

/* ── 项目名 ── */
.daw-project-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 20px;
}

.daw-project-icon {
  color: var(--spark-text-muted);
  flex-shrink: 0;
}

.daw-project-name {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ── 进度区 ── */
.daw-progress-wrap {
  margin-bottom: 16px;
}

.daw-progress-meta {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}

.daw-progress-label {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
  margin-right: 8px;
}

.daw-progress-pct {
  font-size: var(--spark-fs-md);
  font-weight: 700;
  color: var(--spark-primary);
  flex-shrink: 0;
}

.daw-progress-track {
  height: 6px;
  border-radius: 99px;
  background: color-mix(in srgb, var(--spark-primary), transparent 85%);
  overflow: hidden;
}

.daw-progress-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(
    90deg,
    var(--spark-primary-dim),
    var(--spark-primary)
  );
  transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
  position: relative;
}

.daw-progress-fill.is-paused {
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--spark-warning), black 20%),
    var(--spark-warning)
  );
}

.daw-progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 40px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25));
  animation: dawShimmer 2s ease-in-out infinite;
}

@keyframes dawShimmer {
  0%   { opacity: 0; transform: translateX(-40px); }
  50%  { opacity: 1; }
  100% { opacity: 0; transform: translateX(80px); }
}

/* ── 数据行通用 ── */
.daw-scene-row,
.daw-saved-row,
.daw-error-row {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: var(--spark-fs-sm);
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  line-height: 1.5;
}

.daw-row-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--spark-text-muted);
}

.daw-icon--success { color: var(--spark-success); }
.daw-icon--danger  { color: var(--spark-danger); }

/* 当前场景行 */
.daw-scene-row {
  background: var(--spark-primary-container);
  border-left: 3px solid var(--spark-primary);
}

.daw-scene-text {
  color: var(--spark-text);
  flex: 1;
  min-width: 0;
  word-break: break-all;
}

/* 保存行 */
.daw-saved-row {
  background: color-mix(in srgb, var(--spark-success), transparent 90%);
}

.daw-saved-text {
  color: color-mix(in srgb, var(--spark-success), var(--spark-text) 20%);
  flex: 1;
  min-width: 0;
  word-break: break-all;
}

/* 错误行 */
.daw-error-row {
  background: var(--spark-danger-bg);
  border-left: 3px solid var(--spark-danger);
}

.daw-error-text {
  color: var(--spark-danger);
  flex: 1;
  min-width: 0;
  word-break: break-all;
}

/* ── 分割线 ── */
.daw-divider {
  height: 1px;
  background: var(--spark-border);
  margin: 16px 0;
}

/* ── 底部 ── */
.daw-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.daw-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  min-width: 0;
  flex: 1;
}

.daw-hint-icon {
  flex-shrink: 0;
  opacity: 0.7;
}

/* 底部操作按钮 */
.daw-action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  font-size: var(--spark-fs-sm);
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.15s ease;
  font-family: var(--spark-font);
}

.daw-action-btn--danger {
  background: transparent;
  color: var(--spark-text-muted);
}
.daw-action-btn--danger:hover:not(:disabled) {
  border-color: var(--spark-danger);
  color: var(--spark-danger);
  background: var(--spark-danger-bg);
  box-shadow: 0 0 12px color-mix(in srgb, var(--spark-danger), transparent 75%);
  transform: translateY(-1px);
}

.daw-action-btn--primary {
  background: var(--spark-primary-container);
  color: var(--spark-primary);
  border-color: var(--spark-primary);
}
.daw-action-btn--primary:hover:not(:disabled) {
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--spark-primary), transparent 60%);
  transform: translateY(-1px);
}

.daw-action-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.daw-action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.daw-action-btn.is-loading {
  opacity: 0.8;
  cursor: wait;
}

/* 旋转 loader */
.daw-spin {
  animation: dawSpin 0.8s linear infinite;
}

@keyframes dawSpin {
  to { transform: rotate(360deg); }
}

/* ── 进出场动画 ── */
.daw-slide-enter-active {
  transition: opacity 0.35s ease;
}
.daw-slide-leave-active {
  transition: opacity 0.25s ease;
}
.daw-slide-enter-from,
.daw-slide-leave-to {
  opacity: 0;
}

.daw-slide-enter-active .daw-card {
  transition: transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.daw-slide-leave-active .daw-card {
  transition: transform 0.25s cubic-bezier(0.55, 0, 1, 0.45);
}
.daw-slide-enter-from .daw-card {
  transform: translateY(20px) scale(0.95);
}
.daw-slide-leave-to .daw-card {
  transform: translateY(14px) scale(0.97);
}

/* ── 数据行淡入动画 ── */
.daw-row-fade-enter-active,
.daw-row-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.daw-row-fade-enter-from,
.daw-row-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ── Setup 卡片加宽 ── */
.daw-card--setup {
  max-width: 480px;
}

/* ── 关闭按钮 ── */
.daw-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  background: transparent;
  color: var(--spark-text-muted);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease;
}
.daw-close-btn:hover {
  background: var(--spark-danger-bg);
  border-color: var(--spark-danger);
  color: var(--spark-danger);
}

/* ── Setup 阶段 ── */
.daw-setup {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── 恢复提示行 ── */
.daw-resume-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-warning), transparent 88%);
  border-left: 3px solid var(--spark-warning);
}
.daw-icon--warning { color: var(--spark-warning); }
.daw-resume-content {
  flex: 1;
  min-width: 0;
}
.daw-resume-text {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text);
  line-height: 1.5;
}
.daw-resume-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

/* ── 配置表单 ── */
.daw-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.daw-form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.daw-form-label {
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-text-muted);
  letter-spacing: 0.02em;
}
.daw-select {
  width: 100%;
  height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
  color: var(--spark-text);
  font-size: var(--spark-fs-sm);
  font-family: var(--spark-font);
  cursor: pointer;
  outline: none;
  transition: border-color 0.2s ease;
}
.daw-select:focus {
  border-color: var(--spark-primary);
}

/* ── 覆盖警告 ── */
.daw-overwrite-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-warning), transparent 90%);
  font-size: var(--spark-fs-sm);
  color: var(--spark-warning);
}

/* ── 启动按钮行 ── */
.daw-start-row {
  display: flex;
  justify-content: center;
  padding-top: 4px;
}

/* ── 小按钮 ── */
.daw-action-btn--small {
  padding: 4px 10px;
  font-size: var(--spark-fs-xs);
  border-radius: 6px;
}
.daw-action-btn--large {
  padding: 10px 24px;
  font-size: var(--spark-fs-md);
  border-radius: 10px;
}

/* ── 实时流式预览 ── */
.daw-streaming-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--spark-primary), transparent 90%);
  border-left: 3px solid var(--spark-primary);
  margin-bottom: 8px;
  min-height: 78px; /* 固定三行高度：stats(18px) + gap(4px) + preview(3行×18px) + padding */
}
.daw-streaming-stats {
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-primary);
  letter-spacing: 0.02em;
  flex-shrink: 0;
}
.daw-streaming-preview {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text);
  line-height: 1.4;
  word-break: break-all;
  white-space: pre-wrap;
  height: calc(1.4em * 3); /* 固定三行 */
  overflow: hidden;
  text-overflow: ellipsis;
  opacity: 0.85;
}

/* ── 移动端适配 ── */
@media (max-width: 768px) {
  .daw-overlay {
    top: calc(56px + var(--sat, 0px)); /* 移动端：为 flow-header 保留空间，刚好不遮住标题栏 */
  }
}

@media (max-width: 600px) {
  .daw-overlay {
    padding: 16px;
    align-items: flex-end; /* 移动端靠下 */
  }

  .daw-card {
    max-width: 100%;
    border-radius: 20px;
    padding: 24px 20px;
  }
}
</style>
