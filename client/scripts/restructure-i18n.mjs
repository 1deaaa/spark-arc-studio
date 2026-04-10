/**
 * i18n locale 文件结构重构脚本
 * 
 * 将古老的单页架构挂载重构为 components / views / stores 语义分层：
 * 1. productHomeDesktop 下的共享组件词条 → components
 * 2. 页面级顶层 key（login/settings 等）→ views
 * 3. chatStore → stores
 */

import fs from 'fs';

// ─── 解析工具 ───

/**
 * 在指定行范围和缩进级别内，解析所有 key: { ... } 段
 */
function parseSections(lines, searchFrom, searchTo, targetIndent) {
  const sections = [];
  let i = searchFrom;

  while (i <= searchTo) {
    const line = lines[i];
    if (!line) { i++; continue; }
    const indent = line.match(/^(\s*)/)[1].length;
    const trimmed = line.trimStart();

    if (indent === targetIndent && /^[a-zA-Z]/.test(trimmed) && trimmed.includes(':') && !trimmed.startsWith('//')) {
      const key = trimmed.replace(/:.*$/, '').trim();
      const sectionStart = i;

      if (!trimmed.includes('{')) {
        // 简单值行（不太可能出现在这个项目中，但做防御）
        sections.push({ key, startLine: sectionStart, endLine: i });
        i++;
      } else {
        // 对象值 — 用大括号深度追踪找闭合
        let depth = 0;
        let inString = false;
        let stringChar = '';

        for (let j = i; j <= searchTo; j++) {
          for (let k = 0; k < lines[j].length; k++) {
            const ch = lines[j][k];
            if (inString) {
              if (ch === stringChar && (k === 0 || lines[j][k - 1] !== '\\')) {
                inString = false;
              }
            } else {
              if (ch === "'" || ch === '"') {
                inString = true;
                stringChar = ch;
              } else if (ch === '{') {
                depth++;
              } else if (ch === '}') {
                depth--;
                if (depth === 0) {
                  sections.push({ key, startLine: sectionStart, endLine: j });
                  i = j + 1;
                  j = searchTo + 1;
                  break;
                }
              }
            }
          }
        }
        if (depth !== 0) {
          console.warn(`  ⚠ 未找到 '${key}' 的闭合括号，fallback 到 searchTo`);
          sections.push({ key, startLine: sectionStart, endLine: searchTo });
          i = searchTo + 1;
        }
      }
    } else {
      i++;
    }
  }
  return sections;
}

function getSectionLines(lines, section) {
  return lines.slice(section.startLine, section.endLine + 1);
}

/**
 * 调整缩进：delta > 0 加空格，delta < 0 减空格
 */
function reindent(lineArr, delta) {
  if (delta === 0) return lineArr;
  return lineArr.map(line => {
    if (line.trim() === '') return line;
    const curIndent = line.match(/^(\s*)/)[1].length;
    const newIndent = Math.max(0, curIndent + delta);
    return ' '.repeat(newIndent) + line.trimStart();
  });
}

// ─── 重构主函数 ───

const SHARED_COMPONENT_KEYS = [
  'chatPanel', 'chatMessageList', 'directorAutoWrite', 'termsModal',
  'projectSelector', 'outlineNode', 'agentModelCard', 'mcpConnectCard',
  'lorebookEditor', 'scriptGenModal',
];

const PAGE_SPECIFIC_KEYS = [
  'nav', 'hero', 'features', 'workflow', 'showcase', 'philosophy', 'footer',
];

// 需要从顶层移入 views 的 key
const VIEW_MIGRATE_KEYS = [
  'settings', 'mobileFlow', 'activityBar', 'login', 'productHomeMobile',
];

function restructureLocaleFile(filePath) {
  console.log(`\n处理: ${filePath}`);
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');

  // 找 const 声明行
  const constLineIdx = lines.findIndex(l => /^const\s+\w+\s*=\s*\{/.test(l.trimStart()));
  if (constLineIdx < 0) { console.error('  ✗ 找不到 const 声明'); return null; }
  const varName = lines[constLineIdx].match(/const\s+(\w+)/)[1];
  console.log(`  变量名: ${varName}, 声明行: L${constLineIdx + 1}`);

  // 找文件末尾 }; 和 export default
  let closeBraceIdx = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (lines[i].trim() === '};') { closeBraceIdx = i; break; }
  }
  if (closeBraceIdx < 0) { console.error('  ✗ 找不到 };'); return null; }

  // 解析顶层段
  const topSections = parseSections(lines, constLineIdx + 1, closeBraceIdx - 1, 2);
  console.log(`  顶层段: ${topSections.map(s => s.key).join(', ')}`);

  const findSec = (key) => topSections.find(s => s.key === key);

  // 解析 components 子段
  const compSec = findSec('components');
  const compSubs = compSec
    ? parseSections(lines, compSec.startLine + 1, compSec.endLine - 1, 4)
    : [];
  console.log(`  components 子段: ${compSubs.map(s => s.key).join(', ')}`);

  // 解析 productHomeDesktop 子段
  const phdSec = findSec('productHomeDesktop');
  const phdSubs = phdSec
    ? parseSections(lines, phdSec.startLine + 1, phdSec.endLine - 1, 4)
    : [];
  console.log(`  productHomeDesktop 子段: ${phdSubs.map(s => s.key).join(', ')}`);

  const sharedCompSubs = phdSubs.filter(s => SHARED_COMPONENT_KEYS.includes(s.key));
  const pageSpecSubs = phdSubs.filter(s => PAGE_SPECIFIC_KEYS.includes(s.key));
  console.log(`  共享组件移入 components: ${sharedCompSubs.map(s => s.key).join(', ')}`);
  console.log(`  页面专属保留: ${pageSpecSubs.map(s => s.key).join(', ')}`);

  // 解析 views 子段
  const viewsSec = findSec('views');
  const viewsSubs = viewsSec
    ? parseSections(lines, viewsSec.startLine + 1, viewsSec.endLine - 1, 4)
    : [];
  console.log(`  原 views 子段: ${viewsSubs.map(s => s.key).join(', ')}`);

  // ─── 组装新文件 ───

  const out = [];

  // 1. const 声明
  out.push(`const ${varName} = {`);

  // 2. locale / common / app（不变）
  for (const key of ['locale', 'common', 'app']) {
    const sec = findSec(key);
    if (sec) out.push(...getSectionLines(lines, sec));
  }

  // 3. components（扩充：原 components + 从 productHomeDesktop 移入的共享组件）
  out.push('  components: {');
  for (const sub of compSubs) {
    out.push(...getSectionLines(lines, sub));
  }
  for (const sub of sharedCompSubs) {
    // 缩进不变：原来在 productHomeDesktop 下是 indent 4，移到 components 下也是 indent 4
    out.push(...getSectionLines(lines, sub));
  }
  out.push('  },');

  // 4. views（新结构）
  out.push('  views: {');
  // 4a. 从顶层移入的页面级 key（+2 缩进）
  for (const key of VIEW_MIGRATE_KEYS) {
    const sec = findSec(key);
    if (sec) out.push(...reindent(getSectionLines(lines, sec), 2));
  }
  // 4b. productHomeDesktop 页面专属部分（+2 缩进）
  out.push('    productHomeDesktop: {');
  for (const sub of pageSpecSubs) {
    out.push(...reindent(getSectionLines(lines, sub), 2));
  }
  out.push('    },');
  // 4c. 原 views 子段（缩进不变，已经是 indent 4）
  for (const sub of viewsSubs) {
    out.push(...getSectionLines(lines, sub));
  }
  out.push('  },');

  // 5. stores
  const chatStoreSec = findSec('chatStore');
  out.push('  stores: {');
  if (chatStoreSec) out.push(...reindent(getSectionLines(lines, chatStoreSec), 2));
  out.push('  },');

  // 6. utils（不变）
  const utilsSec = findSec('utils');
  if (utilsSec) out.push(...getSectionLines(lines, utilsSec));

  // 7. 闭合
  out.push('};');
  out.push('');
  out.push(`export default ${varName};`);
  out.push('');

  return out.join('\n');
}

// ─── 执行 ───

const localeFiles = [
  'src/i18n/locales/zh-CN.ts',
  'src/i18n/locales/en-US.ts',
  'src/i18n/locales/ja-JP.ts',
];

let allOk = true;
for (const file of localeFiles) {
  const fullPath = file; // 相对于 client 目录
  const result = restructureLocaleFile(fullPath);
  if (result) {
    // 先写临时文件验证
    fs.writeFileSync(fullPath + '.restructured', result);
    console.log(`  ✓ 已写入 ${fullPath}.restructured (${result.length} bytes)`);
  } else {
    console.error(`  ✗ ${fullPath} 重构失败`);
    allOk = false;
  }
}

if (allOk) {
  console.log('\n所有文件重构成功，请检查 .restructured 文件后运行:');
  console.log('  node scripts/restructure-i18n-apply.mjs');
} else {
  console.error('\n部分文件重构失败，请检查日志');
}
