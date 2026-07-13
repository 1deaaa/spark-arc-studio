<template>
  <MarkdownRender
    v-if="!workerParsing || parsedNodes || workerFallback"
    class="markdown-content"
    :content="parsedNodes ? undefined : content"
    :nodes="parsedNodes || undefined"
    custom-id="sparkarc-markdown"
    :mode="renderMode"
    :final="!streaming"
    :parse-options="parseOptions"
    :parse-coalesce-ms="streaming || deferred ? 16 : 0"
    :is-dark="isDark"
    :fade="false"
    :smooth-streaming="streaming ? 'auto' : false"
    :typewriter="streaming"
    :batch-rendering="streaming || deferred"
    :initial-render-batch-size="deferred && !streaming ? 8 : 16"
    :max-live-nodes="streaming ? 0 : maxLiveNodes"
    :render-batch-size="streaming ? 16 : (deferred ? 24 : 48)"
    :render-batch-delay="streaming || deferred ? 8 : 0"
    :render-batch-budget-ms="streaming || deferred ? 4 : 8"
    :render-code-blocks-as-pre="true"
    :code-block-props="codeBlockProps"
    :mermaid-props="mermaidProps"
  />
  <div v-else class="markdown-content markdown-content-preparing" aria-busy="true">
    <span class="markdown-preparing-line"></span>
    <span class="markdown-preparing-line is-short"></span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue';
import 'markstream-vue/index.css';
import 'katex/dist/katex.min.css';
import {
  MarkdownRender,
  enableKatex,
  enableMermaid,
  MathBlockNode,
  MathInlineNode,
  MermaidBlockNode,
  setCustomComponents,
  type BaseNode,
} from 'markstream-vue';
import { useThemeStore } from '@/components/stores/themeStore';
import { parseMarkdownOffThread } from '@/components/share/markdownParseWorker';

enableKatex(() => import('katex'));
enableMermaid(() => import('mermaid'));
setCustomComponents('sparkarc-markdown', {
  math_inline: MathInlineNode,
  math_block: MathBlockNode,
  mermaid: MermaidBlockNode,
});

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
  /**
   * 流式模式：交给 markstream-vue 的 chat 模式做增量解析与批量渲染，
   * 避免旧实现每次 token 都重新正则解析整段 Markdown。
   */
  streaming: {
    type: Boolean,
    default: false,
  },
  /** 完成态长文分批提交节点；最终样式与交互不变，仅避免首次挂载长期占用主线程。 */
  deferred: {
    type: Boolean,
    default: false,
  },
  /** 完成态保留的活动块节点数；聊天历史使用更小窗口，完整内容仍可正常滚动查看。 */
  maxLiveNodes: {
    type: Number,
    default: 320,
  },
});

// 主题监听统一由 themeStore 在应用根部维护，避免每个 Markdown 实例各建一套全局监听器。
const themeStore = useThemeStore();
const isDark = computed(() => themeStore.isDark);
const parsedNodes = shallowRef<BaseNode[] | null>(null);
const workerFallback = ref(false);
const workerParsing = computed(() => props.deferred && !props.streaming && !!props.content);
let parseSequence = 0;

watch(
  () => [workerParsing.value, props.content] as const,
  async ([shouldParse, content]) => {
    const sequence = ++parseSequence;
    parsedNodes.value = null;
    workerFallback.value = false;
    if (!shouldParse) return;
    const nodes = await parseMarkdownOffThread(content);
    if (sequence !== parseSequence) return;
    if (nodes) parsedNodes.value = nodes;
    else workerFallback.value = true;
  },
  { immediate: true },
);

const renderMode = computed(() => (props.streaming ? 'chat' : 'minimal'));

const parseOptions = computed(() => ({
  final: !props.streaming,
  streamParse: props.streaming ? 'auto' : false,
} as const));

const codeBlockProps = computed(() => ({
  theme: {
    light: 'vitesse-light',
    dark: 'vitesse-dark',
  },
  monacoOptions: {
    fontFamily: 'var(--spark-mono)',
    fontSize: 13,
    lineHeight: 18,
    wordWrap: 'on',
  },
  showHeader: true,
  showCopyButton: true,
  showExpandButton: false,
  showPreviewButton: false,
  showCollapseButton: false,
  showFontSizeButtons: false,
  showTooltips: false,
}));

const mermaidProps = computed(() => ({
  showHeader: true,
  showModeToggle: false,
  showCopyButton: true,
  showExportButton: false,
  showFullscreenButton: true,
  showCollapseButton: false,
  showZoomControls: false,
  enableMermaidInteractions: false,
}));
</script>

<style scoped>
/* Markdown 外观变量统一映射到 SparkArc 全局主题，避免 markstream 默认色系漂移。 */
.markdown-content {
  color: var(--spark-text);
  font-family: var(--spark-font, inherit);
  font-size: var(--spark-fs-base);
  line-height: 1.32;
  word-break: break-word;
  overflow-wrap: anywhere;

  --ms-font-sans: var(--spark-font, inherit);
  --ms-font-mono: var(--spark-mono);
  --ms-radius: 0.375rem;

  --ms-text-body: var(--spark-fs-base);
  --ms-leading-body: 1.32;
  --ms-text-h1: var(--spark-fs-md-h2);
  --ms-text-h2: var(--spark-fs-md-h2);
  --ms-text-h3: var(--spark-fs-md-h3);
  --ms-text-h4: var(--spark-fs-md-h4);
  --ms-text-h5: var(--spark-fs-md-h5);
  --ms-text-h6: var(--spark-fs-md-h6);
  --ms-leading-h1: 1.2;
  --ms-leading-h2: 1.2;
  --ms-leading-h3: 1.2;

  --ms-flow-paragraph-y: 0.25em;
  --ms-flow-list-y: 0.3em;
  --ms-flow-list-item-y: 0.25em;
  --ms-flow-list-indent: 1.3em;
  --ms-flow-table-y: 0.45em;
  --ms-flow-table-cell: 0.38em 0.55em;
  --ms-flow-blockquote-y: 0.25em;
  --ms-flow-blockquote-indent: 0.8em;
  --ms-flow-hr-y: 0.6em;
  --ms-flow-diagram-y: 0.6em;
  --ms-flow-codeblock-y: 0.5em;
  --ms-flow-heading-1-mt: 0.6em;
  --ms-flow-heading-1-mb: 0.25em;
  --ms-flow-heading-2-mt: 0.6em;
  --ms-flow-heading-2-mb: 0.25em;
  --ms-flow-heading-3-mt: 0.5em;
  --ms-flow-heading-3-mb: 0.25em;
  --ms-flow-heading-4-mt: 0.4em;
  --ms-flow-heading-4-mb: 0.25em;
  --ms-flow-heading-5-mt: 0.4em;
  --ms-flow-heading-5-mb: 0.25em;
  --ms-flow-heading-6-mt: 0.35em;
  --ms-flow-heading-6-mb: 0.25em;

  --inline-code-bg: var(--spark-hover);
  --inline-code-fg: var(--spark-text);
  --inline-code-border: var(--spark-border);
  --code-bg: var(--spark-hover);
  --code-fg: var(--spark-text);
  --code-border: var(--spark-border);
  --code-header-bg: var(--spark-bg-alt);
  --code-action-fg: var(--spark-text-muted);
  --code-action-hover-bg: var(--spark-hover);
  --code-action-hover-fg: var(--spark-primary);
  --code-action-active-bg: var(--spark-primary);
  --code-action-active-fg: var(--spark-text-inverse);
  --blockquote-border: var(--spark-primary);
  --table-border: var(--spark-border);
  --table-header-bg: var(--spark-hover);
  --link-color: var(--spark-primary);
  --hr-border: var(--spark-border);
  --diagram-bg: var(--spark-hover);
  --diagram-border: var(--spark-border);
  --diagram-header-bg: var(--spark-bg-alt);
  --loading-spinner: var(--spark-primary);
  --loading-shimmer: color-mix(in srgb, var(--spark-primary), transparent 88%);
  --markstream-code-font-family: var(--spark-mono);
}

.markdown-content :deep(.markstream-vue) {
  color: var(--spark-text);
  font-family: var(--spark-font, inherit);
  font-size: inherit;
  line-height: inherit;
}

.markdown-content-preparing {
  display: grid;
  gap: 8px;
  min-height: 44px;
  align-content: center;
}

.markdown-preparing-line {
  display: block;
  width: 88%;
  height: 8px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--spark-text-muted), transparent 86%);
  animation: markdownPreparingPulse 1.1s ease-in-out infinite;
}

.markdown-preparing-line.is-short {
  width: 56%;
  animation-delay: 120ms;
}

@keyframes markdownPreparingPulse {
  0%, 100% { opacity: 0.45; }
  50% { opacity: 0.85; }
}

.markdown-content :deep(h1),
.markdown-content :deep(h2) {
  color: var(--spark-text);
  border-bottom: 1px solid var(--spark-border);
  padding-bottom: 0.08em;
}

.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  color: var(--spark-text);
}

.markdown-content :deep(h5) {
  color: var(--spark-primary);
}

.markdown-content :deep(h6) {
  color: var(--spark-text-muted);
}

.markdown-content :deep(strong) {
  color: var(--spark-text);
  font-weight: 700;
}

.markdown-content :deep(em) {
  color: var(--spark-text-soft);
}

.markdown-content :deep(a) {
  color: var(--spark-primary);
  text-decoration: none;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(blockquote) {
  background: var(--spark-hover);
  color: var(--spark-text-muted);
  border-left: 3px solid var(--spark-primary);
  padding: 0.4em 0.8em;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  overflow: hidden;
  font-size: 0.95em;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--spark-border);
  color: var(--spark-text);
  vertical-align: top;
}

.markdown-content :deep(th) {
  background: var(--spark-hover);
  font-weight: 700;
}

.markdown-content :deep(.inline-code) {
  border-radius: 4px;
}

.markdown-content :deep(.katex) {
  color: var(--spark-text);
}

.markdown-content :deep(.checkbox-checked) {
  color: var(--spark-primary);
}

.markdown-content :deep(.checkbox-unchecked) {
  color: var(--spark-text-muted);
}

.markdown-content :deep(.mermaid-block-container),
.markdown-content :deep(.code-block-shell),
.markdown-content :deep(.code-block-content) {
  border-radius: 6px;
}
</style>
