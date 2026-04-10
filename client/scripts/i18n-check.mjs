/**
 * i18n key 覆盖率检查脚本
 *
 * 确保所有 t() / $t() 引用的 key 在三语 locale 文件中存在且完整，
 * 防止新增功能时遗漏国际化。
 *
 * 检查项：
 *   1. 缺失 key  — 源码引用了但 locale 文件中不存在的 key（运行时显示 raw key）
 *   2. 翻译不全  — zh-CN 有但 en-US / ja-JP 缺失的 key
 *   3. 孤立 key  — locale 中定义了但源码从未静态引用的 key
 *   4. 动态引用  — 使用模板字符串的 t() 调用（无法静态校验，仅计数提示）
 *
 * 用法：
 *   node scripts/i18n-check.mjs            # 仅报告
 *   node scripts/i18n-check.mjs --strict   # 缺失 key 时退出码 1（CI 用）
 *   node scripts/i18n-check.mjs --verbose  # 显示全部孤立 key
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ─── 配置 ───

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const srcRoot = path.join(projectRoot, 'src');

const LOCALE_FILES = [
  { name: 'zh-CN', path: path.join(srcRoot, 'i18n', 'locales', 'zh-CN.ts') },
  { name: 'en-US', path: path.join(srcRoot, 'i18n', 'locales', 'en-US.ts') },
  { name: 'ja-JP', path: path.join(srcRoot, 'i18n', 'locales', 'ja-JP.ts') },
];

const REFERENCE_LOCALE = 'zh-CN';
const SCAN_EXTENSIONS = new Set(['.vue', '.ts', '.tsx']);
const SKIP_DIR_NAMES = new Set(['node_modules', 'dist', '.vscode']);
const SKIP_FILE_SUFFIXES = ['.d.ts'];

const args = new Set(process.argv.slice(2));
const strict = args.has('--strict');
const verbose = args.has('--verbose');

// ─── Locale 文件解析 ───

/**
 * 从 .ts locale 文件中解析出扁平化的 key 集合
 * 使用 new Function 求值对象字面量部分（文件为受控的仓库内资源）
 */
function parseLocaleKeys(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const firstBrace = content.indexOf('{');
  const lastBrace = content.lastIndexOf('}');
  if (firstBrace < 0 || lastBrace <= firstBrace) {
    throw new Error(`无法定位对象字面量: ${filePath}`);
  }
  const objectStr = content.substring(firstBrace, lastBrace + 1);
  try {
    const obj = new Function(`return (${objectStr})`)();
    return flattenKeys(obj);
  } catch (err) {
    throw new Error(`解析 locale 文件失败 ${path.basename(filePath)}: ${err.message}`);
  }
}

/**
 * 递归展开嵌套对象为点路径 key 集合
 * { a: { b: { c: 'x' } } } → Set(['a.b.c'])
 */
function flattenKeys(obj, prefix = '') {
  const result = new Set();
  for (const [key, value] of Object.entries(obj)) {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      for (const k of flattenKeys(value, fullKey)) result.add(k);
    } else {
      result.add(fullKey);
    }
  }
  return result;
}

// ─── 源码扫描 ───

function walkSrcFiles(dir) {
  const results = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (SKIP_DIR_NAMES.has(entry.name)) continue;
      results.push(...walkSrcFiles(full));
    } else {
      const ext = path.extname(entry.name);
      if (!SCAN_EXTENSIONS.has(ext)) continue;
      if (SKIP_FILE_SUFFIXES.some(s => entry.name.endsWith(s))) continue;
      // 跳过 locale 文件自身
      if (full.includes(`${path.sep}i18n${path.sep}locales${path.sep}`)) continue;
      results.push(full);
    }
  }
  return results;
}

/**
 * 从单个源文件中提取 t() / $t() / i18n.global.t() / i18n.t() 引用的 key 及位置
 */
function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const keyLocations = new Map();
  let dynamicCount = 0;

  // 静态 key: i18n.global.t('...') / i18n.t('...') / $t('...') / t('...')
  // 注意：长模式放前面避免 \bt 先匹配到 i18n.global.t 末尾的 t
  const staticRe = /(?:i18n\.global\.t|i18n\.t|\$t|\bt)\s*\(\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = staticRe.exec(content)) !== null) {
    const key = m[1];
    // 过滤明显不是 i18n key 的匹配（纯数字、URL、文件路径）
    if (/^\d+$/.test(key)) continue;
    if (key.startsWith('http://') || key.startsWith('https://') || key.startsWith('/')) continue;
    const line = content.substring(0, m.index).split('\n').length;
    const relPath = path.relative(projectRoot, filePath).replaceAll('\\', '/');
    if (!keyLocations.has(key)) keyLocations.set(key, []);
    keyLocations.get(key).push(`${relPath}:${line}`);
  }

  // 动态引用: i18n.global.t(`...`) / i18n.t(`...`) / $t(`...`) / t(`...`) 模板字符串
  const dynamicRe = /(?:i18n\.global\.t|i18n\.t|\$t|\bt)\s*\(\s*`/g;
  while ((m = dynamicRe.exec(content)) !== null) {
    dynamicCount++;
  }

  return { keyLocations, dynamicCount };
}

// ─── 报告 ───

function formatKeyList(keys, indent = '    ', maxItems) {
  const sorted = [...keys].sort();
  const display = maxItems ? sorted.slice(0, maxItems) : sorted;
  const lines = display.map(k => `${indent}- ${k}`);
  if (maxItems && sorted.length > maxItems) {
    lines.push(`${indent}... 还有 ${sorted.length - maxItems} 个`);
  }
  return lines.join('\n');
}

function report(localeData, allKeyLocations, totalDynamic) {
  const refEntry = localeData.find(d => d.name === REFERENCE_LOCALE);
  const refKeys = refEntry.keys;

  // 收集所有源码引用的 key
  const referencedKeys = new Set(allKeyLocations.keys());

  // 1. 缺失 key：源码引用了但基准 locale 中不存在
  const missingKeys = new Set();
  for (const key of referencedKeys) {
    if (!refKeys.has(key)) missingKeys.add(key);
  }

  // 2. 翻译不全：基准 locale 有但其他 locale 缺失
  const incomplete = [];
  for (const locale of localeData) {
    if (locale.name === REFERENCE_LOCALE) continue;
    const missing = new Set();
    for (const key of refKeys) {
      if (!locale.keys.has(key)) missing.add(key);
    }
    if (missing.size > 0) incomplete.push({ name: locale.name, missing });
  }

  // 3. 孤立 key：基准 locale 中定义但源码未静态引用
  const orphanKeys = new Set();
  for (const key of refKeys) {
    if (!referencedKeys.has(key)) orphanKeys.add(key);
  }

  // ─── 输出 ───
  console.log('');
  console.log('═══════════════════════════════════════════');
  console.log('  i18n Key 覆盖率检查报告');
  console.log('═══════════════════════════════════════════');
  console.log('');

  // 统计概览
  console.log('📊 Locale 词条统计:');
  for (const locale of localeData) {
    const marker = locale.name === REFERENCE_LOCALE ? ' ← 基准' : '';
    console.log(`  ${locale.name}: ${locale.keys.size} keys${marker}`);
  }
  console.log(`  源码静态引用: ${referencedKeys.size} unique keys`);
  console.log(`  源码动态引用: ${totalDynamic} 处（模板字符串，无法静态校验）`);
  console.log('');

  // 缺失 key
  if (missingKeys.size > 0) {
    console.log(`❌ 缺失 Key（${missingKeys.size} 个）:`);
    console.log('  以下 key 在源码中被 t() 引用，但在基准 locale 文件中不存在。');
    console.log('  运行时会显示 raw key 名而非翻译文本，必须修复。');
    console.log('');
    for (const key of [...missingKeys].sort()) {
      const locations = allKeyLocations.get(key) || [];
      const loc = locations[0] || '?';
      console.log(`    ${key}  ← ${loc}`);
    }
    console.log('');
  } else {
    console.log('✅ 缺失 Key: 无（所有源码引用的 key 均存在于基准 locale）');
    console.log('');
  }

  // 翻译不全
  if (incomplete.length > 0) {
    console.log('⚠️  翻译不全:');
    for (const { name, missing } of incomplete) {
      console.log(`  ${name} 缺少 ${missing.size} 个 key（基准 ${REFERENCE_LOCALE} 中存在）:`);
      console.log(formatKeyList(missing, '      ', verbose ? undefined : 20));
    }
    console.log('');
  } else {
    console.log('✅ 翻译完整性: 三语词条数量一致');
    console.log('');
  }

  // 孤立 key
  if (orphanKeys.size > 0) {
    console.log(`📦 潜在孤立 Key（${orphanKeys.size} 个）:`);
    console.log('  以下 key 在基准 locale 中定义但源码中未发现静态 t() 引用。');
    console.log('  部分可能被动态引用（如 t(`prefix.${var}.suffix`)），不一定是死代码。');
    console.log('');
    console.log(formatKeyList(orphanKeys, '    ', verbose ? undefined : 30));
    console.log('');
  } else {
    console.log('✅ 孤立 Key: 无');
    console.log('');
  }

  // 总结
  console.log('───────────────────────────────────────────');
  if (missingKeys.size > 0) {
    console.log(`❌ 发现 ${missingKeys.size} 个缺失 key，必须修复！`);
  } else if (incomplete.length > 0) {
    const total = incomplete.reduce((s, i) => s + i.missing.size, 0);
    console.log(`⚠️  无缺失 key，但有 ${total} 个翻译未补齐。`);
  } else {
    console.log('✅ i18n 覆盖率检查通过！');
  }
  console.log('───────────────────────────────────────────');
  console.log('');

  return missingKeys.size;
}

// ─── 主流程 ───

// 1. 解析 locale 文件
const localeData = [];
for (const { name, path: filePath } of LOCALE_FILES) {
  try {
    const keys = parseLocaleKeys(filePath);
    localeData.push({ name, keys });
    console.log(`✓ 已解析 ${name}: ${keys.size} keys`);
  } catch (err) {
    console.error(`❌ 解析 ${name} 失败: ${err.message}`);
    process.exit(1);
  }
}

// 2. 扫描源码
const sourceFiles = walkSrcFiles(srcRoot);
console.log(`✓ 已发现 ${sourceFiles.length} 个源文件待扫描`);

const mergedKeyLocations = new Map();
let totalDynamic = 0;

for (const filePath of sourceFiles) {
  const { keyLocations, dynamicCount } = scanFile(filePath);
  totalDynamic += dynamicCount;
  for (const [key, locations] of keyLocations) {
    if (!mergedKeyLocations.has(key)) mergedKeyLocations.set(key, []);
    mergedKeyLocations.get(key).push(...locations);
  }
}

console.log(`✓ 扫描完成: ${mergedKeyLocations.size} unique keys, ${totalDynamic} 动态引用`);

// 3. 生成报告
const missingCount = report(localeData, mergedKeyLocations, totalDynamic);

// 4. 退出码
if (strict && missingCount > 0) {
  console.log(`⚠️  --strict 模式：发现 ${missingCount} 个缺失 key，退出码设为 1`);
  process.exit(1);
}
