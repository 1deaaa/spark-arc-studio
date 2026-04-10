import fs from 'node:fs';
import path from 'node:path';

const projectRoot = process.cwd();
const srcRoot = path.join(projectRoot, 'src');
const args = new Set(process.argv.slice(2));
const fullScan = args.has('--full');
const includeExt = fullScan
  ? new Set(['.vue', '.ts', '.tsx', '.js', '.jsx'])
  : new Set(['.vue']);
const ignoreSegments = [
  `${path.sep}i18n${path.sep}locales${path.sep}`,
  `${path.sep}__tests__${path.sep}`,
  `${path.sep}test${path.sep}`,
  `${path.sep}types${path.sep}`,
];
const cjkRegex = /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}]/u;

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...walk(full));
      continue;
    }
    if (!includeExt.has(path.extname(entry.name))) {
      continue;
    }
    if (ignoreSegments.some(seg => full.includes(seg))) {
      continue;
    }
    files.push(full);
  }
  return files;
}

function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split(/\r?\n/);
  const ext = path.extname(filePath);
  const templateLineSet = !fullScan && ext === '.vue' ? collectVueTemplateLineSet(lines) : null;
  const matches = [];

  lines.forEach((line, index) => {
    const lineNo = index + 1;
    if (templateLineSet && !templateLineSet.has(lineNo)) {
      return;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    if (
      trimmed.startsWith('//') ||
      trimmed.startsWith('/*') ||
      trimmed.startsWith('*') ||
      trimmed.startsWith('*/') ||
      trimmed.startsWith('<!--')
    ) {
      return;
    }
    if (!cjkRegex.test(line)) {
      return;
    }

    matches.push({
      line: lineNo,
      text: trimmed,
    });
  });

  return matches;
}

function collectVueTemplateLineSet(lines) {
  const set = new Set();
  let inTemplate = false;
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!inTemplate && line.includes('<template')) {
      inTemplate = true;
    }
    if (inTemplate) {
      set.add(i + 1);
    }
    if (inTemplate && line.includes('</template>')) {
      inTemplate = false;
    }
  }
  return set;
}

const files = walk(srcRoot);
let total = 0;
for (const file of files) {
  const matches = scanFile(file);
  if (matches.length === 0) {
    continue;
  }
  const rel = path.relative(projectRoot, file).replaceAll('\\\\', '/');
  for (const item of matches) {
    total += 1;
    console.log(`${rel}:${item.line}: ${item.text}`);
  }
}

const modeLabel = fullScan ? 'full' : 'ui-template';
console.log(`\nFound ${total} line(s) containing CJK characters in ${modeLabel} scan.`);
console.log('Tip: migrate user-visible text to Vue I18n keys in src/i18n/locales/*.ts');
