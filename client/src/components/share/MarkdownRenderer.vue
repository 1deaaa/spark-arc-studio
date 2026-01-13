<template>
  <div class="markdown-content" v-html="renderedContent"></div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

/**
 * 简单的 Markdown 渲染器
 * 支持：标题、粗体、斜体、删除线、链接、列表、引用、分隔线、换行
 */
function renderMarkdown(text) {
  if (!text) return '';
  
  let html = text;
  
  // 转义 HTML 特殊字符（安全处理）
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  
  // 标题 (按照 # 数量从多到少解析，避免误匹配)
  html = html.replace(/^##### (.+)$/gm, '<h6>$1</h6>');
  html = html.replace(/^#### (.+)$/gm, '<h5>$1</h5>');
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
  
  // 粗体 **text** 或 __text__
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
  
  // 斜体 *text* 或 _text_（避免和粗体冲突）
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>');
  html = html.replace(/(?<!_)_([^_]+)_(?!_)/g, '<em>$1</em>');
  
  // 删除线 ~~text~~
  html = html.replace(/~~(.+?)~~/g, '<del>$1</del>');
  
  // 行内代码 `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  
  // 链接 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  
  // 分隔线 ---
  html = html.replace(/^---+$/gm, '<hr>');
  
  // 引用 > text
  html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
  // 合并连续引用
  html = html.replace(/<\/blockquote>\n<blockquote>/g, '\n');
  
  // 无序列表 - item 或 * item
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
  // 包装连续的 li
  html = html.replace(/(<li>.*<\/li>\n?)+/g, (match) => `<ul>${match}</ul>`);
  
  // 有序列表 1. item
  html = html.replace(/^\d+\. (.+)$/gm, '<oli>$1</oli>');
  html = html.replace(/(<oli>.*<\/oli>\n?)+/g, (match) => {
    return '<ol>' + match.replace(/<\/?oli>/g, (tag) => tag.replace('oli', 'li')) + '</ol>';
  });
  
  // 段落和换行
  // 双换行 -> 段落
  html = html.replace(/\n\n+/g, '</p><p>');
  // 单换行 -> <br>
  html = html.replace(/\n/g, '<br>');
  
  // 包装在 p 标签中（如果有内容）
  if (html && !html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }
  
  // 清理空段落
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p><br><\/p>/g, '');
  
  return html;
}

const renderedContent = computed(() => renderMarkdown(props.content));
</script>

<style scoped>
.markdown-content {
  font-size: 13px;
  line-height: 1.4;
  color: var(--spark-text);
  word-break: break-word;
}

.markdown-content :deep(h2) {
  font-size: 1.3em;
  font-weight: 700;
  margin: 0.6em 0 0.3em;
  color: var(--spark-text);
  border-bottom: 1px solid var(--spark-border);
  padding-bottom: 0.2em;
}

.markdown-content :deep(h3) {
  font-size: 1.15em;
  font-weight: 600;
  margin: 0.5em 0 0.2em;
  color: var(--spark-text);
}

.markdown-content :deep(h4) {
  font-size: 1em;
  font-weight: 600;
  margin: 0.4em 0 0.2em;
  color: var(--spark-text);
}

.markdown-content :deep(h5) {
  font-size: 0.95em;
  font-weight: 600;
  margin: 0.4em 0 0.2em;
  color: var(--spark-primary);
}

.markdown-content :deep(h6) {
  font-size: 0.9em;
  font-weight: 600;
  margin: 0.3em 0 0.1em;
  color: var(--spark-text-muted);
}

.markdown-content :deep(p) {
  margin: 0.3em 0;
}

.markdown-content :deep(strong) {
  font-weight: 700;
  color: var(--spark-text);
}

.markdown-content :deep(em) {
  font-style: italic;
  color: var(--spark-text-muted);
}

.markdown-content :deep(del) {
  text-decoration: line-through;
  opacity: 0.7;
}

.markdown-content :deep(code) {
  background: var(--spark-hover);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: var(--spark-mono);
  font-size: 0.9em;
}

.markdown-content :deep(a) {
  color: var(--spark-primary);
  text-decoration: none;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(blockquote) {
  margin: 0.5em 0;
  padding: 0.5em 1em;
  border-left: 3px solid var(--spark-primary);
  background: var(--spark-hover);
  color: var(--spark-text-muted);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.markdown-content :deep(li) {
  margin: 0.2em 0;
}

.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--spark-border);
  margin: 1em 0;
}
</style>
