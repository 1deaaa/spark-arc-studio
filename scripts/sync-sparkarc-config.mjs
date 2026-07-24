/**
 * 从 sparkarc.json 派生静态前端、Tauri 权限及仓库文档中的公开地址。
 * 默认写入；--check 仅检查，不修改文件，供 CI 与 Cargo 构建期调用。
 */
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import {
  allNetworkCandidates,
  projectRoot,
  readSparkArcConfig,
  repositoryUrls,
} from './sparkarc-config.mjs';

const checkOnly = process.argv.includes('--check');
const config = readSparkArcConfig();
const repository = repositoryUrls(config);

function launcherAllowList({ includeProxies }) {
  const urls = [repository.web];
  if (includeProxies) {
    for (const prefix of allNetworkCandidates('gh_proxy', config)) {
      urls.push(`${prefix.replace(/\/+$/, '')}/${repository.web}`);
    }
  }
  return [...new Set(urls.map((url) => ({ url: `${url}*` })))];
}

function capability(identifier, description, options) {
  const permissions = options.permissions ?? [];
  permissions.push({
    identifier: 'opener:allow-open-url',
    allow: launcherAllowList({ includeProxies: options.includeProxies }),
  });
  const result = { identifier, description, windows: options.windows, ...options.extra, permissions };
  return `${JSON.stringify(result, null, 2)}\n`;
}

const generated = new Map([
  [
    join(projectRoot, 'client', 'src', 'generated', 'sparkarcConfig.ts'),
    `// 此文件由 scripts/sync-sparkarc-config.mjs 从 sparkarc.json 生成，请勿手动编辑。\nexport const SPARKARC_GITHUB_URL = ${JSON.stringify(repository.web)};\nexport const SPARKARC_GIT_CLONE_URL = ${JSON.stringify(repository.clone)};\n`,
  ],
  [
    join(projectRoot, 'client', 'src-tauri', 'capabilities', 'main.json'),
    capability('main-capability', 'Main window permissions', {
      windows: ['*'],
      includeProxies: true,
      permissions: [
        'core:default',
        'core:window:default',
        'core:window:allow-start-dragging',
        'core:window:allow-minimize',
        'core:window:allow-toggle-maximize',
        'core:window:allow-is-maximized',
        'core:window:allow-close',
        'core:window:allow-set-focus',
        'core:window:allow-start-resize-dragging',
        'core:webview:allow-create-webview-window',
        'os:default',
      ],
    }),
  ],
  [
    join(projectRoot, 'client', 'src-tauri', 'capabilities', 'remote-desktop.json'),
    capability('remote-desktop-shell', 'Minimal desktop permissions for self-hosted SparkArc frontends loaded over HTTP(S). Kept intentionally small so developers can deploy to arbitrary domains without editing capability files.', {
      windows: ['*'],
      includeProxies: true,
      extra: {
        $schema: '../gen/schemas/desktop-schema.json',
        platforms: ['windows', 'macOS', 'linux'],
        local: false,
        remote: { urls: ['http://*:*/*', 'https://*:*/*'] },
      },
      permissions: [
        'core:event:allow-listen',
        'core:event:allow-unlisten',
        'core:window:allow-close',
        'core:window:allow-is-maximized',
        'core:window:allow-minimize',
        'core:window:allow-start-dragging',
        'core:window:allow-start-resize-dragging',
        'core:window:allow-toggle-maximize',
        'core:webview:allow-create-webview-window',
        'os:default',
      ],
    }),
  ],
  [
    join(projectRoot, 'client', 'src-tauri', 'capabilities', 'remote-mobile.json'),
    capability('remote-mobile-shell', 'Minimal mobile permissions for self-hosted SparkArc frontends loaded over HTTP(S). Only OS information is exposed so runtime can keep mobile-specific branches and performance grading.', {
      windows: ['main'],
      includeProxies: false,
      extra: {
        $schema: '../gen/schemas/mobile-schema.json',
        platforms: ['android', 'iOS'],
        local: false,
        remote: { urls: ['http://*:*/*', 'https://*:*/*'] },
      },
      permissions: ['os:default'],
    }),
  ],
]);

const documentationTransforms = [
  {
    paths: ['README.md', 'README.en.md', 'README.ja.md', 'README.ko.md'],
    pattern: /git clone https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\.git)?/g,
    replacement: `git clone ${repository.web}`,
    expectedMatches: 2,
  },
  {
    paths: ['docs/local-deployment-manager.zh-CN.md'],
    pattern: /固定仓库为 `[^`]+`。/g,
    replacement: `固定仓库为 \`${repository.slug}\`。`,
    expectedMatches: 1,
  },
  {
    paths: ['.github/FUNDING.yml'],
    pattern: /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/blob\/main\/\.github\/SUPPORT\.md/g,
    replacement: `${repository.web}/blob/main/.github/SUPPORT.md`,
    expectedMatches: 1,
  },
  {
    paths: ['.github/ISSUE_TEMPLATE/config.yml'],
    pattern: /https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/blob\/main\/\.github\/(CONTRIBUTING|SECURITY)\.md/g,
    replacement: `${repository.web}/blob/main/.github/$1.md`,
    expectedMatches: 2,
  },
];

async function update(path, expected) {
  let actual = '';
  try {
    actual = await readFile(path, 'utf8');
  } catch {
    if (checkOnly) throw new Error(`缺少派生产物 ${path}`);
  }
  if (actual === expected) return;
  if (checkOnly) throw new Error(`派生产物已漂移：${path}。请运行 node scripts/sync-sparkarc-config.mjs。`);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, expected, 'utf8');
}

async function syncDocumentation(transform) {
  for (const relativePath of transform.paths) {
    const path = join(projectRoot, relativePath);
    const content = await readFile(path, 'utf8');
    const matches = content.match(transform.pattern) ?? [];
    if (matches.length !== transform.expectedMatches) {
      throw new Error(`${relativePath} 的项目地址位置数量异常：预期 ${transform.expectedMatches}，实际 ${matches.length}。`);
    }
    const expected = content.replace(transform.pattern, transform.replacement);
    await update(path, expected);
  }
}

try {
  for (const [path, content] of generated) await update(path, content);
  for (const transform of documentationTransforms) await syncDocumentation(transform);
  if (!checkOnly) console.log('已从 sparkarc.json 同步公开仓库地址与 Tauri 权限清单。');
} catch (error) {
  console.error(`[sparkarc-config] ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
