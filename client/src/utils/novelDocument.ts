export type NovelDocument = {
  body: string;
  conception: string;
};

const CONCEPTION_BLOCK_RE = /<conception(?:\s[^>]*)?>([\s\S]*?)(?:<\/conception\s*>|$)/i;
const CONCEPTION_FIELD_RE = /^(\s*)(?:[-*]\s*)?["']?(?:conception|scene[_ -]?conception|sceneConception)["']?\s*[:：=]\s*(.*)$/i;

function normalizeNewlines(value: unknown): string {
  return String(value ?? '').replace(/\r\n/g, '\n').replace(/\r/g, '\n');
}

export function parseNovelDocument(value: unknown): NovelDocument {
  let raw = normalizeNewlines(value);
  const stripped = raw.trim();
  if (stripped.startsWith('{') && stripped.endsWith('}')) {
    try {
      const payload = JSON.parse(stripped) as Record<string, unknown>;
      const bodyCandidates = ['content', 'body', 'text', '正文', 'novel']
        .map(key => payload[key])
        .filter((item): item is string => typeof item === 'string');
      const body = bodyCandidates.find(item => item.trim()) ?? bodyCandidates[0];
      const conception = payload.conception ?? payload.scene_conception ?? payload.sceneConception;
      if (typeof body === 'string') {
        return {
          body: body.trim(),
          conception: typeof conception === 'string' ? conception.trim() : '',
        };
      }
    } catch {
      // 不是结构化 JSON 时按普通小说文本处理。
    }
  }

  let conception = '';
  let blockMatch = raw.match(CONCEPTION_BLOCK_RE);
  while (blockMatch) {
    conception = blockMatch[1].trim() || conception;
    raw = raw.replace(CONCEPTION_BLOCK_RE, '');
    blockMatch = raw.match(CONCEPTION_BLOCK_RE);
  }
  raw = raw.replace(/<conception\s*\/?>\s*/gi, '');
  raw = raw.replace(/<!--[\s\S]*?-->/g, '');

  const lines: string[] = [];
  const sourceLines = raw.split('\n');
  for (let index = 0; index < sourceLines.length; index += 1) {
    const line = sourceLines[index];
    const match = line.match(CONCEPTION_FIELD_RE);
    if (!match) {
      lines.push(line);
      continue;
    }
    const inlineValue = match[2].trim();
    if (inlineValue && !conception) conception = inlineValue;
    if (inlineValue) continue;
    const baseIndent = match[1].replace(/\t/g, '    ').length;
    const nested: string[] = [];
    while (index + 1 < sourceLines.length) {
      const candidate = sourceLines[index + 1];
      if (!candidate.trim()) {
        index += 1;
        continue;
      }
      const indent = candidate.length - candidate.replace(/^\s+/, '').length;
      if (indent <= baseIndent) break;
      nested.push(candidate.trim());
      index += 1;
    }
    if (!conception && nested.length) conception = nested.join('\n').trim();
  }

  return {
    body: lines.join('\n').replace(/^\s*[@#]?conception\s*$/gim, '').replace(/\n{3,}/g, '\n\n').trim(),
    conception,
  };
}

export function serializeNovelDocument(body: unknown, conception: unknown): string {
  const normalizedBody = normalizeNewlines(body).trim();
  const normalizedConception = normalizeNewlines(conception).trim();
  if (!normalizedConception) return normalizedBody;
  return `<conception>\n${normalizedConception}\n</conception>${normalizedBody ? `\n\n${normalizedBody}` : ''}`;
}
