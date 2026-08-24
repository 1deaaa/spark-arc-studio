export interface WorldviewField {
  lineIndex: number;
  label: string;
  value: string;
}

export interface WorldviewSection {
  index: number;
  title: string;
  body: string;
  startOffset: number;
  endOffset: number;
  bodyStartOffset: number;
  legacy: boolean;
}

export interface WorldviewDocument {
  title: string;
  sections: WorldviewSection[];
}

const H1_PATTERN = /^#\s+(.+)$/m;
const H2_PATTERN = /^##\s+(.+)$/gm;
const FIELD_PATTERN = /^(\s*[-*]\s+)([^：:\n]+?)([：:])(.*)$/;

function trimSectionBody(value: string): string {
  return value.replace(/^\r?\n/, '').replace(/\s+$/, '');
}

export function parseWorldviewMarkdown(markdown: string): WorldviewDocument {
  const source = String(markdown || '').replace(/\r\n/g, '\n');
  const title = source.match(H1_PATTERN)?.[1]?.trim() || '';
  const headings = Array.from(source.matchAll(H2_PATTERN));

  if (headings.length === 0) {
    return {
      title,
      sections: [{
        index: 0,
        title: '',
        body: source,
        startOffset: 0,
        endOffset: source.length,
        bodyStartOffset: 0,
        legacy: true,
      }],
    };
  }

  const sections: WorldviewSection[] = [];
  const preambleEnd = headings[0]?.index ?? 0;
  const preamble = source.slice(0, preambleEnd).trimEnd();
  const preambleWithoutTitle = preamble.replace(H1_PATTERN, '').trim();
  if (preambleWithoutTitle) {
    sections.push({
      index: 0,
      title: '',
      body: preamble,
      startOffset: 0,
      endOffset: preambleEnd,
      bodyStartOffset: 0,
      legacy: true,
    });
  }

  headings.forEach((match, headingIndex) => {
    const startOffset = match.index ?? 0;
    const headingText = match[0];
    const bodyStartOffset = startOffset + headingText.length;
    const endOffset = headings[headingIndex + 1]?.index ?? source.length;
    sections.push({
      index: sections.length,
      title: String(match[1] || '').trim(),
      body: trimSectionBody(source.slice(bodyStartOffset, endOffset)),
      startOffset,
      endOffset,
      bodyStartOffset,
      legacy: false,
    });
  });

  return { title, sections };
}

export function parseWorldviewFields(body: string): WorldviewField[] {
  return String(body || '')
    .split('\n')
    .map((line, lineIndex) => {
      const match = line.match(FIELD_PATTERN);
      if (!match) return null;
      return {
        lineIndex,
        label: match[2].trim(),
        value: match[4].trim(),
      } satisfies WorldviewField;
    })
    .filter((field): field is WorldviewField => field !== null);
}

export function updateWorldviewField(
  body: string,
  lineIndex: number,
  patch: Partial<Pick<WorldviewField, 'label' | 'value'>>,
): string {
  const lines = String(body || '').split('\n');
  const line = lines[lineIndex];
  const match = line?.match(FIELD_PATTERN);
  if (!match) return body;
  const label = patch.label === undefined ? match[2].trim() : patch.label.trim();
  const value = patch.value === undefined ? match[4].trim() : patch.value;
  lines[lineIndex] = `${match[1]}${label}${match[3]}${value ? ` ${value}` : ''}`;
  return lines.join('\n');
}

export function removeWorldviewField(body: string, lineIndex: number): string {
  const lines = String(body || '').split('\n');
  if (lineIndex < 0 || lineIndex >= lines.length) return body;
  lines.splice(lineIndex, 1);
  return lines.join('\n');
}

export function updateWorldviewSection(
  markdown: string,
  sectionIndex: number,
  patch: Partial<Pick<WorldviewSection, 'title' | 'body'>>,
): string {
  const source = String(markdown || '').replace(/\r\n/g, '\n');
  const section = parseWorldviewMarkdown(source).sections[sectionIndex];
  if (!section) return source;

  if (section.legacy) {
    if (patch.body === undefined) return source;
    const suffix = source.slice(section.endOffset).trimStart();
    return `${patch.body.trimEnd()}${suffix ? `\n\n${suffix}` : ''}`;
  }

  const title = patch.title === undefined ? section.title : patch.title.trim();
  const body = patch.body === undefined ? section.body : patch.body.replace(/^\s+|\s+$/g, '');
  const replacement = `## ${title || section.title}\n${body ? `\n${body}\n` : '\n'}`;
  return `${source.slice(0, section.startOffset)}${replacement}${source.slice(section.endOffset).replace(/^\n+/, '\n')}`;
}

export function appendWorldviewSection(markdown: string, title: string, body = ''): string {
  const source = String(markdown || '').replace(/\r\n/g, '\n').trimEnd();
  const section = `## ${title.trim()}\n${body.trim() ? `\n${body.trim()}\n` : ''}`;
  return source ? `${source}\n\n${section}` : section;
}

export function removeWorldviewSection(markdown: string, sectionIndex: number): string {
  const source = String(markdown || '').replace(/\r\n/g, '\n');
  const section = parseWorldviewMarkdown(source).sections[sectionIndex];
  if (!section || section.legacy) return source;
  return `${source.slice(0, section.startOffset).trimEnd()}\n\n${source.slice(section.endOffset).trimStart()}`.trim();
}

export function moveWorldviewSection(markdown: string, sectionIndex: number, direction: -1 | 1): string {
  const source = String(markdown || '').replace(/\r\n/g, '\n');
  const document = parseWorldviewMarkdown(source);
  const movableSections = document.sections.filter(section => !section.legacy);
  const currentPosition = movableSections.findIndex(section => section.index === sectionIndex);
  const targetPosition = currentPosition + direction;
  if (currentPosition < 0 || targetPosition < 0 || targetPosition >= movableSections.length) return source;

  const prefix = source.slice(0, movableSections[0].startOffset).trimEnd();
  const blocks = movableSections.map(section => source.slice(section.startOffset, section.endOffset).trim());
  [blocks[currentPosition], blocks[targetPosition]] = [blocks[targetPosition], blocks[currentPosition]];
  return `${prefix}${prefix ? '\n\n' : ''}${blocks.join('\n\n')}\n`;
}
