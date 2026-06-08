/**
 * i18n coverage validation script
 *
 * Ensures that keys referenced through t() / $t() exist in the locale files and
 * that the locale sets stay aligned as the frontend grows.
 *
 * Checks:
 *   1. Missing keys      — referenced in source, absent from the reference locale
 *   2. Incomplete locales — present in zh-CN, missing from other locale files
 *   3. Orphan keys       — defined in locale files but not statically referenced
 *   4. Dynamic references — template-string t() calls that cannot be verified statically
 *
 * Usage:
 *   node scripts/i18n-check.mjs            # report only
 *   node scripts/i18n-check.mjs --strict   # exit 1 when missing keys are found
 *   node scripts/i18n-check.mjs --verbose  # print the full orphan-key list
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ─── Configuration ───

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '..');
const srcRoot = path.join(projectRoot, 'src');

const LOCALE_FILES = [
  { name: 'zh-CN', path: path.join(srcRoot, 'i18n', 'locales', 'zh-CN.ts') },
  { name: 'en-US', path: path.join(srcRoot, 'i18n', 'locales', 'en-US.ts') },
  { name: 'ja-JP', path: path.join(srcRoot, 'i18n', 'locales', 'ja-JP.ts') },
  { name: 'ko-KR', path: path.join(srcRoot, 'i18n', 'locales', 'ko-KR.ts') },
];

const REFERENCE_LOCALE = 'zh-CN';
const SCAN_EXTENSIONS = new Set(['.vue', '.ts', '.tsx']);
const SKIP_DIR_NAMES = new Set(['node_modules', 'dist', '.vscode']);
const SKIP_FILE_SUFFIXES = ['.d.ts'];

const args = new Set(process.argv.slice(2));
const strict = args.has('--strict');
const verbose = args.has('--verbose');

// ─── Locale file parsing ───

/**
 * Parse a flattened key set from a locale .ts file.
 * The repository controls these files, so evaluating the object literal is acceptable here.
 */
function parseLocaleKeys(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const firstBrace = content.indexOf('{');
  const lastBrace = content.lastIndexOf('}');
  if (firstBrace < 0 || lastBrace <= firstBrace) {
    throw new Error(`Unable to locate object literal in ${filePath}`);
  }
  const objectStr = content.substring(firstBrace, lastBrace + 1);
  try {
    const obj = new Function(`return (${objectStr})`)();
    return flattenKeys(obj);
  } catch (err) {
    throw new Error(`Failed to parse locale file ${path.basename(filePath)}: ${err.message}`);
  }
}

/**
 * Recursively flatten nested objects into dot-path keys.
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

// ─── Source scanning ───

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
      // Skip locale files themselves.
      if (full.includes(`${path.sep}i18n${path.sep}locales${path.sep}`)) continue;
      results.push(full);
    }
  }
  return results;
}

/**
 * Extract i18n key references and locations from a single source file.
 */
function scanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const keyLocations = new Map();
  let dynamicCount = 0;

  // Static key calls: i18n.global.t('...') / i18n.t('...') / $t('...') / t('...')
  // Keep the longer patterns first so \bt does not pre-match the tail of i18n.global.t.
  const staticRe = /(?:i18n\.global\.t|i18n\.t|\$t|\bt)\s*\(\s*['"]([^'"]+)['"]/g;
  let m;
  while ((m = staticRe.exec(content)) !== null) {
    const key = m[1];
    // Filter obvious non-i18n matches such as pure numbers, URLs, and file paths.
    if (/^\d+$/.test(key)) continue;
    if (key.startsWith('http://') || key.startsWith('https://') || key.startsWith('/')) continue;
    const line = content.substring(0, m.index).split('\n').length;
    const relPath = path.relative(projectRoot, filePath).replaceAll('\\', '/');
    if (!keyLocations.has(key)) keyLocations.set(key, []);
    keyLocations.get(key).push(`${relPath}:${line}`);
  }

  // Dynamic references via template strings cannot be verified statically.
  const dynamicRe = /(?:i18n\.global\.t|i18n\.t|\$t|\bt)\s*\(\s*`/g;
  while ((m = dynamicRe.exec(content)) !== null) {
    dynamicCount++;
  }

  return { keyLocations, dynamicCount };
}

// ─── Reporting ───

function formatKeyList(keys, indent = '    ', maxItems) {
  const sorted = [...keys].sort();
  const display = maxItems ? sorted.slice(0, maxItems) : sorted;
  const lines = display.map(k => `${indent}- ${k}`);
  if (maxItems && sorted.length > maxItems) {
    lines.push(`${indent}... and ${sorted.length - maxItems} more`);
  }
  return lines.join('\n');
}

function report(localeData, allKeyLocations, totalDynamic) {
  const refEntry = localeData.find(d => d.name === REFERENCE_LOCALE);
  const refKeys = refEntry.keys;

  // Collect all keys referenced in source.
  const referencedKeys = new Set(allKeyLocations.keys());

  // 1. Missing keys: referenced in source but absent from the reference locale.
  const missingKeys = new Set();
  for (const key of referencedKeys) {
    if (!refKeys.has(key)) missingKeys.add(key);
  }

  // 2. Incomplete locales: keys exist in the reference locale but are missing elsewhere.
  const incomplete = [];
  for (const locale of localeData) {
    if (locale.name === REFERENCE_LOCALE) continue;
    const missing = new Set();
    for (const key of refKeys) {
      if (!locale.keys.has(key)) missing.add(key);
    }
    if (missing.size > 0) incomplete.push({ name: locale.name, missing });
  }

  // 3. Orphan keys: defined in the reference locale but not statically referenced.
  const orphanKeys = new Set();
  for (const key of refKeys) {
    if (!referencedKeys.has(key)) orphanKeys.add(key);
  }

  // ─── Output ───
  console.log('');
  console.log('═══════════════════════════════════════════');
  console.log('  i18n Coverage Report');
  console.log('═══════════════════════════════════════════');
  console.log('');

  // Overview
  console.log('📊 Locale key counts:');
  for (const locale of localeData) {
    const marker = locale.name === REFERENCE_LOCALE ? ' ← reference' : '';
    console.log(`  ${locale.name}: ${locale.keys.size} keys${marker}`);
  }
  console.log(`  Static source references: ${referencedKeys.size} unique keys`);
  console.log(`  Dynamic source references: ${totalDynamic} occurrences (template strings, not statically verifiable)`);
  console.log('');

  // Missing keys
  if (missingKeys.size > 0) {
    console.log(`❌ Missing keys (${missingKeys.size}):`);
    console.log('  These keys are referenced in source through t() but do not exist in the reference locale.');
    console.log('  At runtime they will render as raw keys instead of translated strings.');
    console.log('');
    for (const key of [...missingKeys].sort()) {
      const locations = allKeyLocations.get(key) || [];
      const loc = locations[0] || '?';
      console.log(`    ${key}  ← ${loc}`);
    }
    console.log('');
  } else {
    console.log('✅ Missing keys: none');
    console.log('');
  }

  // Incomplete locale coverage
  if (incomplete.length > 0) {
    console.log('⚠️  Incomplete locale coverage:');
    for (const { name, missing } of incomplete) {
      console.log(`  ${name} is missing ${missing.size} key(s) that exist in ${REFERENCE_LOCALE}:`);
      console.log(formatKeyList(missing, '      ', verbose ? undefined : 20));
    }
    console.log('');
  } else {
    console.log('✅ Locale completeness: all locale files are aligned');
    console.log('');
  }

  // Orphan keys
  if (orphanKeys.size > 0) {
    console.log(`📦 Potential orphan keys (${orphanKeys.size}):`);
    console.log('  These keys exist in the reference locale but were not found through static t() scanning.');
    console.log('  Some may still be referenced dynamically (for example t(`prefix.${var}.suffix`)).');
    console.log('');
    console.log(formatKeyList(orphanKeys, '    ', verbose ? undefined : 30));
    console.log('');
  } else {
    console.log('✅ Orphan keys: none');
    console.log('');
  }

  // Summary
  console.log('───────────────────────────────────────────');
  if (missingKeys.size > 0) {
    console.log(`❌ Found ${missingKeys.size} missing key(s). These must be fixed.`);
  } else if (incomplete.length > 0) {
    const total = incomplete.reduce((s, i) => s + i.missing.size, 0);
    console.log(`⚠️  No missing reference keys, but ${total} locale entry/entries are still incomplete.`);
  } else {
    console.log('✅ i18n coverage check passed.');
  }
  console.log('───────────────────────────────────────────');
  console.log('');

  return missingKeys.size;
}

// ─── Main flow ───

// 1. Parse locale files.
const localeData = [];
for (const { name, path: filePath } of LOCALE_FILES) {
  try {
    const keys = parseLocaleKeys(filePath);
    localeData.push({ name, keys });
    console.log(`✓ Parsed ${name}: ${keys.size} keys`);
  } catch (err) {
    console.error(`❌ Failed to parse ${name}: ${err.message}`);
    process.exit(1);
  }
}

// 2. Scan source files.
const sourceFiles = walkSrcFiles(srcRoot);
console.log(`✓ Found ${sourceFiles.length} source files to scan`);

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

console.log(`✓ Scan complete: ${mergedKeyLocations.size} unique keys, ${totalDynamic} dynamic reference(s)`);

// 3. Generate report.
const missingCount = report(localeData, mergedKeyLocations, totalDynamic);

// 4. Exit code.
if (strict && missingCount > 0) {
  console.log(`⚠️  --strict enabled: exiting with code 1 because ${missingCount} missing key(s) were found`);
  process.exit(1);
}
