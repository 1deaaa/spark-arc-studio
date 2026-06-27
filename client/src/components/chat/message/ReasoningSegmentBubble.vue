<template>
  <div
    class="chat-bubble reasoning-bubble"
    :class="{ 'has-agent-avatar': !!sourceAgent }"
  >
    <n-tooltip v-if="sourceAgent" trigger="hover">
      <template #trigger>
        <AgentAvatar
          class="agent-avatar-anchor"
          :agent-id="sourceAgent"
          :size="28"
          :active="active"
          :aria-label="avatarAriaLabel"
        />
      </template>
      {{ avatarAriaLabel }}
    </n-tooltip>

    <div
      class="reasoning-block"
      :class="{
        'is-finished': !streaming,
        'is-revealing': expanded || animating,
      }"
    >
      <div class="reasoning-toggle" :class="{ 'is-thinking': streaming }" @click="toggleReasoning">
        <svg v-if="streaming" class="reasoning-thinking-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="15 30" stroke-linecap="round" class="spinner-ring" />
          <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="5 45" stroke-dashoffset="20" stroke-linecap="round" class="spinner-ring-fast" />
          <circle cx="12" cy="12" r="3.5" fill="currentColor" class="pulse-dot" />
        </svg>
        <svg v-else class="reasoning-icon" :class="{ open: expanded }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
        <span class="reasoning-label">{{ streaming ? t('components.chatMessageList.thinkingDeep') : t('components.chatMessageList.thoughtDeep') }}</span>
        <span class="reasoning-len">{{ t('components.chatMessageList.charCount', { count: text.length }) }}</span>
      </div>

      <div
        class="reasoning-content-wrapper"
        :class="{
          'is-expanded': expanded,
          'is-closing': phase === 'closing',
          'is-auto-streaming': autoExpandedOnce && streaming,
        }"
        :style="panelStyle"
      >
        <div ref="contentRef" class="reasoning-content">
          <div class="reasoning-inner">
            <MarkdownRenderer
              class="reasoning-markdown"
              :content="text"
              :streaming="streaming"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NTooltip } from 'naive-ui';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';

type RevealPhase = '' | 'opening' | 'closing';

const STREAMING_REASONING_MAX_LINES = 5;
const STREAMING_REASONING_FALLBACK_MAX_HEIGHT = 108;
const REASONING_REVEAL_TIMER_MS = 360;
const REASONING_HEIGHT_STABLE_FRAMES = 2;
const REASONING_HEIGHT_MAX_SAMPLES = 5;

const { t } = useI18n();

const props = withDefaults(defineProps<{
  text: string;
  sourceAgent?: string;
  agentName?: string;
  streaming?: boolean;
  active?: boolean;
}>(), {
  sourceAgent: '',
  agentName: '',
  streaming: false,
  active: false,
});

const contentRef = ref<HTMLElement | null>(null);
const expanded = ref(false);
const autoExpandedOnce = ref(false);
const animating = ref(false);
const phase = ref<RevealPhase>('');
const desiredExpanded = ref(false);
const panelHeight = ref(0);
const measuredHeight = ref(0);
const layoutVersion = ref(0);
let animationTimer = 0;

const avatarAriaLabel = computed(() => `${props.agentName} (${t('components.chatMessageList.thinking')})`);
const panelStyle = computed(() => ({
  '--reasoning-panel-height': `${Math.max(0, panelHeight.value)}px`,
}));

function clearAnimationTimer() {
  if (!animationTimer) return;
  window.clearTimeout(animationTimer);
  animationTimer = 0;
}

function bumpLayoutVersion() {
  layoutVersion.value += 1;
  return layoutVersion.value;
}

function isLayoutVersionCurrent(version: number) {
  return layoutVersion.value === version;
}

function getWrapperElement() {
  return contentRef.value?.closest('.reasoning-content-wrapper') as HTMLElement | null;
}

function getVisibleHeight() {
  const wrapper = getWrapperElement();
  if (!wrapper) return panelHeight.value;
  return Math.max(0, Math.round(wrapper.getBoundingClientRect().height));
}

function measureRenderedContentHeight(root: HTMLElement | null) {
  if (!root) return 0;

  const inner = (root.querySelector('.reasoning-inner') as HTMLElement | null) || root;
  const markdown = (inner.querySelector('.reasoning-markdown') as HTMLElement | null) || inner;
  const innerRect = inner.getBoundingClientRect();
  const innerStyle = window.getComputedStyle(inner);
  const paddingBottom = Number.parseFloat(innerStyle.paddingBottom || '0') || 0;
  const children = Array.from(markdown.children || []) as HTMLElement[];
  let bottom = 0;

  for (const child of children) {
    const rect = child.getBoundingClientRect();
    if (rect.width <= 0 && rect.height <= 0) continue;
    bottom = Math.max(bottom, rect.bottom - innerRect.top);
  }

  if (bottom > 0) {
    return Math.ceil(bottom + paddingBottom);
  }

  const innerRectHeight = innerRect.height || 0;
  if (innerRectHeight > 0) return Math.ceil(innerRectHeight);
  return Math.ceil(root.getBoundingClientRect().height || 0);
}

function parseCssPx(value: string | null | undefined) {
  const parsed = Number.parseFloat(value || '');
  return Number.isFinite(parsed) ? parsed : 0;
}

function resolveLineHeightPx(style: CSSStyleDeclaration) {
  const rawLineHeight = (style.lineHeight || '').trim();
  const fontSize = parseCssPx(style.fontSize);
  const parsedLineHeight = Number.parseFloat(rawLineHeight);

  if (Number.isFinite(parsedLineHeight) && parsedLineHeight > 0) {
    if (rawLineHeight.endsWith('px')) return parsedLineHeight;
    if (rawLineHeight.endsWith('%') && fontSize > 0) return fontSize * (parsedLineHeight / 100);
    if (parsedLineHeight <= 4 && fontSize > 0) return fontSize * parsedLineHeight;
    return parsedLineHeight;
  }

  return fontSize > 0 ? fontSize * 1.32 : 0;
}

function measureStreamingContentMaxHeight(root: HTMLElement | null) {
  if (!root || typeof window === 'undefined' || typeof window.getComputedStyle !== 'function') {
    return STREAMING_REASONING_FALLBACK_MAX_HEIGHT;
  }

  const inner = (root.querySelector('.reasoning-inner') as HTMLElement | null) || root;
  const markdown = (inner.querySelector('.reasoning-markdown') as HTMLElement | null) || inner;
  const innerStyle = window.getComputedStyle(inner);
  const markdownStyle = window.getComputedStyle(markdown);
  const lineHeight = resolveLineHeightPx(markdownStyle) || resolveLineHeightPx(innerStyle);

  if (lineHeight <= 0) return STREAMING_REASONING_FALLBACK_MAX_HEIGHT;

  const verticalExtra = (
    parseCssPx(innerStyle.paddingTop)
    + parseCssPx(innerStyle.paddingBottom)
    + parseCssPx(innerStyle.borderTopWidth)
    + parseCssPx(innerStyle.borderBottomWidth)
  );

  return Math.ceil((lineHeight * STREAMING_REASONING_MAX_LINES) + verticalExtra);
}

function measurePanelHeight(streaming = props.streaming) {
  const fullHeight = measureRenderedContentHeight(contentRef.value);
  if (!streaming) return fullHeight;
  if (fullHeight <= 0) return 0;
  return Math.min(fullHeight, measureStreamingContentMaxHeight(contentRef.value));
}

function getTargetHeight(streaming = props.streaming) {
  const measured = measurePanelHeight(streaming);
  if (measured > 0) return measured;
  if (measuredHeight.value > 0) {
    return streaming ? Math.min(measuredHeight.value, measureStreamingContentMaxHeight(contentRef.value)) : measuredHeight.value;
  }
  return streaming ? measureStreamingContentMaxHeight(contentRef.value) : 0;
}

function finishRevealAnimation(nextHeight: number) {
  clearAnimationTimer();
  animating.value = false;
  phase.value = '';
  panelHeight.value = nextHeight;
}

function animateReveal(nextPhase: Exclude<RevealPhase, ''>, nextHeight: number, onDone?: () => void) {
  clearAnimationTimer();
  animating.value = true;
  phase.value = nextPhase;
  panelHeight.value = nextHeight;
  animationTimer = window.setTimeout(() => {
    if (onDone) {
      onDone();
    } else {
      finishRevealAnimation(nextHeight);
    }
    animationTimer = 0;
  }, REASONING_REVEAL_TIMER_MS);
}

function flushLayout() {
  void getWrapperElement()?.offsetHeight;
}

function waitAnimationFrame() {
  return new Promise<void>((resolve) => {
    if (typeof window === 'undefined' || typeof window.requestAnimationFrame !== 'function') {
      resolve();
      return;
    }
    window.requestAnimationFrame(() => resolve());
  });
}

async function measureStableTargetHeight(streaming = props.streaming, version: number) {
  let lastHeight = getTargetHeight(streaming);
  let stableFrames = 0;

  for (let index = 0; index < REASONING_HEIGHT_MAX_SAMPLES; index += 1) {
    await waitAnimationFrame();
    if (!isLayoutVersionCurrent(version)) return 0;

    const nextHeight = getTargetHeight(streaming);
    if (nextHeight > 0 && Math.abs(nextHeight - lastHeight) <= 1) {
      stableFrames += 1;
    } else {
      stableFrames = 0;
    }
    lastHeight = nextHeight;

    if (stableFrames >= REASONING_HEIGHT_STABLE_FRAMES - 1) {
      break;
    }
  }

  return lastHeight;
}

function scrollToBottom() {
  const content = contentRef.value;
  if (!content) return;
  content.scrollTop = content.scrollHeight;
}

function syncStreamingHeight() {
  const nextHeight = measurePanelHeight(true);
  if (nextHeight <= 0) return;
  panelHeight.value = nextHeight;
  measuredHeight.value = nextHeight;
  scrollToBottom();
}

function openPanel(streaming = props.streaming) {
  clearAnimationTimer();
  const version = bumpLayoutVersion();
  const wrapper = getWrapperElement();
  if (wrapper) {
    wrapper.style.height = '';
    wrapper.style.overflow = '';
    wrapper.style.transition = '';
  }

  expanded.value = true;
  desiredExpanded.value = true;
  panelHeight.value = 0;

  nextTick(async () => {
    // 先让展开态真正落到 DOM，再测目标高度，避免折叠态窄宽度把首展高度量虚高。
    if (!isLayoutVersionCurrent(version) || !expanded.value || !desiredExpanded.value) return;

    const targetHeight = await measureStableTargetHeight(streaming, version);
    if (!isLayoutVersionCurrent(version) || !expanded.value || !desiredExpanded.value) return;

    flushLayout();
    animateReveal('opening', targetHeight, () => {
      // 动画结束后再按最终布局落一次实高，防止流式 Markdown 首次成型时高度仍有轻微漂移。
      const nextMeasuredHeight = measurePanelHeight(streaming) || targetHeight;
      measuredHeight.value = nextMeasuredHeight;
      finishRevealAnimation(nextMeasuredHeight);
    });
    scrollToBottom();
  });
}

function closePanel() {
  clearAnimationTimer();
  bumpLayoutVersion();

  desiredExpanded.value = false;
  expanded.value = true;
  panelHeight.value = getVisibleHeight();

  flushLayout();
  animateReveal('closing', 0, () => {
    expanded.value = false;
    finishRevealAnimation(0);
  });
}

function toggleReasoning() {
  if (desiredExpanded.value) {
    closePanel();
    return;
  }
  openPanel();
}

watch(() => props.streaming, (streaming, wasStreaming) => {
  if (streaming) {
    if (!autoExpandedOnce.value) {
      autoExpandedOnce.value = true;
      if (!expanded.value) {
        openPanel(true);
        return;
      }
    }
    nextTick(() => syncStreamingHeight());
    return;
  }

  if (wasStreaming && autoExpandedOnce.value && expanded.value && desiredExpanded.value) {
    closePanel();
  }
}, { immediate: true });

watch(() => props.text, () => {
  if (!props.streaming) return;
  nextTick(() => syncStreamingHeight());
});

onBeforeUnmount(() => {
  clearAnimationTimer();
});
</script>

<style scoped>
.has-agent-avatar {
  margin-top: 18px;
  position: relative;
}

.agent-avatar-anchor {
  position: absolute;
  top: -16px;
  left: -10px;
  z-index: 10;
}

.chat-bubble {
  max-width: 100%;
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  padding: 9px 12px;
  background-color: var(--spark-panel-bg);
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  user-select: text;
  border-top-left-radius: 4px;
}

.reasoning-bubble {
  width: fit-content;
  min-width: min(1100px, 100%);
  max-width: 100%;
  box-sizing: border-box;
  align-self: flex-start;
}

.reasoning-block {
  margin-bottom: 8px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  overflow: hidden;
  background: linear-gradient(135deg, color-mix(in srgb, var(--spark-primary), transparent 94%) 0%, transparent 100%);
}

.reasoning-block.is-revealing {
  overflow-anchor: none;
}

.reasoning-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.reasoning-toggle:hover {
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
}

.reasoning-icon {
  width: 14px;
  height: 14px;
  color: var(--spark-text-muted);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.reasoning-icon.open {
  transform: rotate(90deg);
}

.reasoning-thinking-icon {
  width: 14px;
  height: 14px;
  color: var(--spark-primary);
  flex-shrink: 0;
}

.reasoning-thinking-icon .spinner-ring {
  animation: spin 3s linear infinite;
  transform-origin: center;
}

.reasoning-thinking-icon .spinner-ring-fast {
  animation: spin 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  transform-origin: center;
  opacity: 0.6;
}

.reasoning-thinking-icon .pulse-dot {
  animation: toolCorePulse 1.5s ease-in-out infinite;
  transform-origin: center;
  opacity: 0.8;
}

.reasoning-toggle.is-thinking {
  background: color-mix(in srgb, var(--spark-primary), transparent 95%);
}

.reasoning-toggle.is-thinking .reasoning-label {
  color: var(--spark-primary);
  font-weight: 600;
}

.reasoning-label {
  font-size: var(--spark-fs-xs);
  font-weight: 500;
  color: var(--spark-text-secondary);
}

.reasoning-len {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  margin-left: auto;
}

.reasoning-content-wrapper {
  position: relative;
  height: 0;
  overflow: hidden;
  contain: layout paint style;
  transition: height 320ms cubic-bezier(0.22, 0.72, 0.16, 1);
  will-change: height;
}

.reasoning-content-wrapper.is-expanded {
  height: var(--reasoning-panel-height, auto);
}

.reasoning-content-wrapper.is-closing {
  height: 0;
}

.reasoning-content {
  overflow: hidden;
  min-height: auto;
}

.reasoning-content-wrapper.is-auto-streaming .reasoning-content {
  height: 100%;
  overflow-y: auto;
  overscroll-behavior: contain;
}

.reasoning-inner {
  padding: 4px 10px 8px;
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
  color: var(--spark-text-secondary);
  border-top: 1px solid var(--spark-border);
  overflow: visible;
}

.reasoning-markdown {
  font-size: var(--spark-fs-base);
  line-height: 1.32;
}

.reasoning-block.is-finished {
  content-visibility: auto;
  contain-intrinsic-size: auto 80px;
}

.reasoning-block.is-finished.is-revealing {
  content-visibility: visible;
  contain-intrinsic-size: none;
}

@keyframes toolCorePulse {
  0%, 100% { opacity: 0.7; transform: scale(0.9); transform-origin: center; }
  50% { opacity: 1; transform: scale(1.08); transform-origin: center; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
