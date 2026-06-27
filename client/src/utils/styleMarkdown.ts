/**
 * 极简 Markdown 渲染器——专为风格档案设计
 *
 * 风格档案是 LLM 按受控模板产出的 markdown,内容形态固定:
 * - `##` / `###` 标题
 * - `-` 列表
 * - `**bold**` 强调
 * - 普通段落
 *
 * 因此我们不引入完整的 markdown 库(marked/markdown-it),
 * 只手写一个轻量的子集渲染器,同时确保转义所有 HTML 字符以防 XSS。
 *
 * 不支持(也不需要):表格、图片、代码块、链接、HTML 内联、复杂列表嵌套。
 */

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderInline(text: string): string {
  let result = escapeHtml(text);
  // **bold** -> <strong>
  result = result.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  return result;
}

export function renderStyleMarkdown(source: string): string {
  if (!source) return '';

  const lines = source.split('\n');
  const html: string[] = [];
  let inList = false;
  let paragraphBuffer: string[] = [];

  const flushParagraph = () => {
    if (paragraphBuffer.length === 0) return;
    const content = paragraphBuffer.join(' ').trim();
    if (content) {
      html.push(`<p class="style-md-p">${renderInline(content)}</p>`);
    }
    paragraphBuffer = [];
  };

  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    if (line === '') {
      flushParagraph();
      closeList();
      continue;
    }

    // ## / ### 标题
    const headingMatch = line.match(/^(#{2,3})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = headingMatch[1].length;
      const tag = level === 2 ? 'h3' : 'h4';
      html.push(`<${tag} class="style-md-h${level}">${renderInline(headingMatch[2])}</${tag}>`);
      continue;
    }

    // 横线分隔
    if (/^---+$/.test(line.trim())) {
      flushParagraph();
      closeList();
      html.push('<hr class="style-md-hr" />');
      continue;
    }

    // 列表项 (- 开头或缩进的 -)
    const listMatch = line.match(/^\s*-\s+(.+)$/);
    if (listMatch) {
      flushParagraph();
      if (!inList) {
        html.push('<ul class="style-md-ul">');
        inList = true;
      }
      html.push(`<li class="style-md-li">${renderInline(listMatch[1])}</li>`);
      continue;
    }

    // 普通段落行
    closeList();
    paragraphBuffer.push(line.trim());
  }

  flushParagraph();
  closeList();

  return html.join('\n');
}
