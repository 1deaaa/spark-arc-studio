<template>
  <div class="markdown-content" v-html="renderedContent"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import katex from 'katex';

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
});

/**
 * 简单的 Markdown 渲染器
 * 支持：标题、粗体、斜体、删除线、链接、列表、引用、分隔线、换行、LaTeX 公式
 */

/**
 * 提取 LaTeX 公式并用占位符替换，避免后续正则破坏公式内容
 * 返回 { text: 替换后的文本, formulas: 占位符到渲染结果的映射 }
 */
function extractLatex(text) {
  const formulas = new Map();
  let counter = 0;
  const placeholder = (idx) => `\x00KATEX_${idx}\x00`;

  // 先提取块级公式 $$...$$（贪婪匹配，支持多行）
  let result = text.replace(/\$\$([\s\S]+?)\$\$/g, (_match, formula) => {
    const idx = counter++;
    try {
      const html = katex.renderToString(formula.trim(), {
        displayMode: true,
        throwOnError: false,
        trust: true,
      });
      // 渲染结果包含错误标记时降级为原始文本
      if (html.includes('katex-error')) {
        return _match;
      }
      formulas.set(placeholder(idx), html);
    } catch {
      return _match;
    }
    return placeholder(idx);
  });

  // 再提取行内公式 $...$（非贪婪，不跨行）
  // 排除 $$ 和转义的 \$
  // 不做前置过滤，直接尝试 KaTeX 渲染：成功则用，失败则降级为原始文本
  result = result.replace(/(?<!\$)\$(?!\$)([^\$\n]+?)\$(?!\$)/g, (_match, formula) => {
    const idx = counter++;
    try {
      const html = katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
        trust: true,
      });
      // KaTeX throwOnError=false 时仍可能产出包含错误标记的 HTML，
      // 检测到 katex-error 类则降级为原始文本
      if (html.includes('katex-error')) {
        return _match;
      }
      formulas.set(placeholder(idx), html);
    } catch {
      return _match;
    }
    return placeholder(idx);
  });

  return { text: result, formulas };
}

/** HTML 特殊字符转义 */
function escapeHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function renderMarkdown(text) {
  if (!text) return '';

  // 先提取 LaTeX 公式，用占位符保护
  const { text: protectedText, formulas } = extractLatex(text);

  // 工具名称映射
  const toolNameMap = {
    'rewrite_worldview': '重写世界观',
    'rewriteworldview': '重写世界观',
    'rewrite_all_characters': '重写角色',
    'rewriteallcharacters': '重写角色',
    'update_character': '修改角色',
    'updatecharacter': '修改角色',
    'rewrite_synopsis': '重写梗概',
    'rewrite_beat_sheet': '重写节拍',
    'rewrite_outline': '重写大纲',
    'create_or_rewrite_script': '重写剧本',
  };
  
  let html = protectedText;
  
  // 先处理工具调用标记（在转义之前），替换为 SVG 徽章
  html = html.replace(/<!-- TOOL_CALL_START:(\w+) -->/g, (match, toolName) => {
    const displayName = toolNameMap[toolName] || toolName || '工具调用中';
    return `<span class="tool-call-badge"><svg class="tool-spinner" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" class="orbit"/><circle cx="12" cy="2" r="2.5" class="satellite"/></svg><span class="tool-name">${displayName}</span></span>`;
  });
  html = html.replace(/<!-- TOOL_CALL_END -->/g, '');
  
  // 转义 HTML 特殊字符（安全处理）
  // 注意：保留已转换的 SVG 徽章
  html = html
    .replace(/&(?!amp;|lt;|gt;)/g, '&amp;')
    .replace(/<(?!span|svg|circle|\/span|\/svg)/g, '&lt;')
    .replace(/(?<!span|svg|circle|")>/g, '&gt;');
  
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

  // GitHub 风格表格
  html = renderTables(html);
  
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

  // 清理块级标签周围被正则误加的 <br>，由 CSS 统一控制间距
  html = html.replace(/<(h[2-6]|ul|ol|li|blockquote|p|hr)><br>/g, '<$1>');
  html = html.replace(/<br><\/(h[2-6]|ul|ol|li|blockquote|p|hr)>/g, '</$1>');
  html = html.replace(/<\/(h[2-6]|ul|ol|li|blockquote|p|hr)><br>/g, '</$1>');
  html = html.replace(/<br><(h[2-6]|ul|ol|li|blockquote|p|hr)>/g, '<$1>');
  html = html.replace(/<p><table/g, '<table');
  html = html.replace(/<\/table><\/p>/g, '</table>');
  html = html.replace(/<br><table/g, '<table');
  html = html.replace(/<\/table><br>/g, '</table>');
  
  // 包装在 p 标签中（如果有内容）
  if (html && !html.startsWith('<')) {
    html = '<p>' + html + '</p>';
  }
  
  // 清理空段落及多余空行
  html = html.replace(/<p><\/p>/g, '');
  html = html.replace(/<p><br><\/p>/g, '');
  html = html.replace(/<p><br><\/p>/g, '');

  // 回填 KaTeX 渲染结果（占位符 -> 实际 HTML）
  for (const [ph, rendered] of formulas) {
    html = html.replaceAll(ph, rendered);
    // 清理占位符被段落标签包裹的情况
    html = html.replaceAll(`<p>${rendered}</p>`, rendered);
    html = html.replaceAll(`<p>${rendered}<br>`, `<p>${rendered}`);
    html = html.replaceAll(`<br>${rendered}</p>`, `${rendered}</p>`);
  }

  return html;
}

function isTableSeparatorLine(line) {
  const normalized = String(line || '').trim().replace(/^\||\|$/g, '');
  if (!normalized.includes('|')) return false;
  const cells = normalized.split('|').map(cell => cell.trim());
  return cells.length > 0 && cells.every(cell => /^:?-{3,}:?$/.test(cell));
}

function parseTableRow(line) {
  return String(line || '')
    .trim()
    .replace(/^\||\|$/g, '')
    .split('|')
    .map(cell => cell.trim());
}

function getTableAlignments(separatorLine) {
  return parseTableRow(separatorLine).map((cell) => {
    if (/^:-{3,}:$/.test(cell)) return 'center';
    if (/^:-{3,}$/.test(cell)) return 'left';
    if (/^-{3,}:$/.test(cell)) return 'right';
    return '';
  });
}

function renderTables(text) {
  const lines = String(text || '').split('\n');
  const output: string[] = [];

  for (let index = 0; index < lines.length; index += 1) {
    const headerLine = lines[index];
    const separatorLine = lines[index + 1];

    if (!headerLine || !separatorLine || !headerLine.includes('|') || !isTableSeparatorLine(separatorLine)) {
      output.push(headerLine);
      continue;
    }

    const headers = parseTableRow(headerLine);
    const alignments = getTableAlignments(separatorLine);
    const bodyRows: string[][] = [];
    let cursor = index + 2;

    while (cursor < lines.length) {
      const currentLine = lines[cursor];
      if (!currentLine?.trim() || !currentLine.includes('|')) break;
      bodyRows.push(parseTableRow(currentLine));
      cursor += 1;
    }

    const headerHtml = headers
      .map((cell, cellIndex) => {
        const align = alignments[cellIndex] ? ` style="text-align:${alignments[cellIndex]}"` : '';
        return `<th${align}>${cell}</th>`;
      })
      .join('');

    const bodyHtml = bodyRows
      .map((row) => {
        const rowHtml = row
          .map((cell, cellIndex) => {
            const align = alignments[cellIndex] ? ` style="text-align:${alignments[cellIndex]}"` : '';
            return `<td${align}>${cell}</td>`;
          })
          .join('');
        return `<tr>${rowHtml}</tr>`;
      })
      .join('');

    output.push(`<table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>`);
    index = cursor - 1;
  }

  return output.join('\n');
}

const renderedContent = computed(() => renderMarkdown(props.content));
</script>

<style scoped>
/* Markdown 渲染容器：整体字体、行高、颜色与断行行为 */
.markdown-content {
  font-size: var(--spark-fs-sm);
  line-height: 1.32;
  color: var(--spark-text);
  word-break: break-word;
}
/* Markdown 渲染容器：覆盖默认字号与行高（用于桌面视图） */
.markdown-content {
  line-height: 1.32;
  font-size: var(--spark-fs-base);
}
/* 二级标题：字号、粗细、上下间距、分割线 */
.markdown-content :deep(h2) {
  font-size: var(--spark-fs-md-h2);
  font-weight: 700;
  margin: 0.6em 0 0.25em 0;
  line-height: 1.2;
  color: var(--spark-text);
  border-bottom: 1px solid var(--spark-border);
  padding-bottom: 0.08em;
}

/* 三级标题：字号、粗细、上下间距 */
.markdown-content :deep(h3) {
  font-size: var(--spark-fs-md-h3);
  font-weight: 600;
  margin: 0.5em 0 0.25em 0;
  line-height: 1.2;
  color: var(--spark-text);
}

/* 四级标题：字号、粗细、上下间距 */
.markdown-content :deep(h4) {
  font-size: var(--spark-fs-md-h4);
  font-weight: 600;
  margin: 0.4em 0 0.25em 0;
  line-height: 1.2;
  color: var(--spark-text);
}

/* 五级标题：字号、粗细、上下间距（强调色） */
.markdown-content :deep(h5) {
  font-size: var(--spark-fs-md-h5);
  font-weight: 600;
  margin: 0.4em 0 0.25em 0;
  line-height: 1.2;
  color: var(--spark-primary);
}

/* 六级标题：字号、粗细、上下间距（弱化色） */
.markdown-content :deep(h6) {
  font-size: var(--spark-fs-md-h6);
  font-weight: 600;
  margin: 0.35em 0 0.25em 0;
  line-height: 1.2;
  color: var(--spark-text-muted);
}

/* 段落：上下外边距控制段落间距 */
.markdown-content :deep(p) {
  margin: 0.25em 0;
}

/* 移除以前的标题后紧贴逻辑，现在由统一的 margin 控制 */
.markdown-content :deep(h2 + p),
.markdown-content :deep(h3 + p),
.markdown-content :deep(h4 + p),
.markdown-content :deep(h5 + p),
.markdown-content :deep(h6 + p),
.markdown-content :deep(h2 + ul),
.markdown-content :deep(h3 + ul),
.markdown-content :deep(h4 + ul),
.markdown-content :deep(h5 + ul),
.markdown-content :deep(h6 + ul),
.markdown-content :deep(h2 + ol),
.markdown-content :deep(h3 + ol),
.markdown-content :deep(h4 + ol),
.markdown-content :deep(h5 + ol),
.markdown-content :deep(h6 + ol),
.markdown-content :deep(h2 + blockquote),
.markdown-content :deep(h3 + blockquote),
.markdown-content :deep(h4 + blockquote),
.markdown-content :deep(h5 + blockquote),
.markdown-content :deep(h6 + blockquote) {
  margin-top: 0;
}

/* 加粗：强调文本颜色和粗细 */
.markdown-content :deep(strong) {
  font-weight: 700;
  color: var(--spark-text);
}

/* 斜体：优化可读性 */
.markdown-content :deep(em) {
  font-style: italic;
  color: var(--spark-text-soft);
  padding-right: 0.1em;
}

/* 删除线：透明度弱化 */
.markdown-content :deep(del) {
  text-decoration: line-through;
  opacity: 0.7;
}

/* 行内代码：背景、内边距、圆角、等宽字体 */
.markdown-content :deep(code) {
  background: var(--spark-hover);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-family: var(--spark-mono);
  font-size: var(--spark-fs-mono);
}

/* 链接：颜色与无下划线 */
.markdown-content :deep(a) {
  color: var(--spark-primary);
  text-decoration: none;
}

/* 链接 hover：显示下划线 */
.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

/* 引用块：外边距、内边距、左侧强调线与背景 */
.markdown-content :deep(blockquote) {
  margin: 0.25em 0;
  padding: 0.4em 0.8em;
  border-left: 3px solid var(--spark-primary);
  background: var(--spark-hover);
  color: var(--spark-text-muted);
}

/* 列表容器（无序/有序）：外边距、缩进、整体行高 */
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.3em 0;
  padding-left: 1.3em;
  line-height: 1.1;
}

/* 列表项：上下边距（控制点状行间距） */
.markdown-content :deep(li) {
  margin: 0.25em 0;
  line-height: 1.1;
}

/* 分隔线：细线样式与上下间距 */
.markdown-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--spark-border);
  margin: 0.6em 0;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 0.45em 0;
  font-size: 0.95em;
  overflow: hidden;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--spark-border);
  padding: 0.38em 0.55em;
  vertical-align: top;
}

.markdown-content :deep(th) {
  background: var(--spark-hover);
  font-weight: 700;
  color: var(--spark-text);
}

.markdown-content :deep(td) {
  color: var(--spark-text);
}

/* 工具调用徽章样式 */
.markdown-content :deep(.tool-call-badge) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: linear-gradient(135deg, 
    color-mix(in srgb, var(--spark-primary), transparent 85%),
    color-mix(in srgb, var(--spark-harmonious-a, var(--spark-primary)), transparent 85%)
  );
  border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 60%);
  border-radius: 16px;
  font-size: 0.8rem;
  color: var(--spark-primary);
  font-weight: 500;
  margin: 4px 0;
}

.markdown-content :deep(.tool-spinner) {
  width: 16px;
  height: 16px;
  animation: tool-spin 1.5s linear infinite;
}

.markdown-content :deep(.tool-spinner .orbit) {
  fill: none;
  stroke: currentColor;
  stroke-width: 1;
  opacity: 0.3;
}

.markdown-content :deep(.tool-spinner .satellite) {
  fill: currentColor;
  transform-origin: 12px 12px;
}

.markdown-content :deep(.tool-name) {
  letter-spacing: 0.5px;
}

@keyframes tool-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
