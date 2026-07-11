#!/usr/bin/env node

/**
 * SparkArc 跨平台前端构建入口。
 *
 * 此脚本由 start.bat、start.sh 和 Launcher 受管 Node 共同调用。它不写入全局
 * npm 配置，也不依赖 PowerShell、cmd 或任何系统包管理器。
 */
import { createHash } from 'node:crypto';
import { access, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const clientDir = dirname(fileURLToPath(import.meta.url));
const packageJson = join(clientDir, 'package.json');
const packageLock = join(clientDir, 'package-lock.json');
const markerPath = join(clientDir, '.frontend_build_complete');
const distIndex = join(clientDir, 'dist', 'index.html');
const minimumNodeMajor = 20;

function fail(message) {
  console.error(`[frontend] ${message}`);
  process.exitCode = 1;
}

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

function run(command, args, env) {
  const result = spawnSync(command, args, {
    cwd: clientDir,
    stdio: 'inherit',
    env,
    // Windows 的 npm.cmd 只能由命令解释器启动；参数均为本脚本的固定值。
    shell: process.platform === 'win32',
  });
  if (result.error) {
    throw new Error(`${command} 无法启动：${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(' ')} 失败，退出码 ${result.status ?? 'unknown'}。`);
  }
}

function nodeMajorVersion() {
  const [major] = process.versions.node.split('.');
  return Number.parseInt(major, 10);
}

async function hashFile(path) {
  return createHash('sha256').update(await readFile(path)).digest('hex');
}

async function newestMtime(path) {
  const entry = await stat(path);
  let newest = entry.mtimeMs;
  if (!entry.isDirectory()) return newest;

  for (const child of await readdir(path, { withFileTypes: true })) {
    if (child.name === 'node_modules' || child.name === 'dist' || child.name.startsWith('.tmp')) continue;
    newest = Math.max(newest, await newestMtime(join(path, child.name)));
  }
  return newest;
}

async function readMarker() {
  try {
    return JSON.parse(await readFile(markerPath, 'utf8'));
  } catch {
    return null;
  }
}

async function buildInputsChanged(lockHash) {
  if (!(await exists(distIndex))) return true;
  const marker = await readMarker();
  if (!marker || marker.lockHash !== lockHash || typeof marker.builtAt !== 'number') return true;

  const watched = [
    packageJson,
    packageLock,
    join(clientDir, 'vite.config.ts'),
    join(clientDir, 'tsconfig.json'),
    join(clientDir, 'src'),
    join(clientDir, 'public'),
  ];
  for (const path of watched) {
    if ((await exists(path)) && (await newestMtime(path)) > marker.builtAt) return true;
  }
  return false;
}

async function probeRegistry(registry) {
  const normalized = registry.replace(/\/+$/, '');
  try {
    const response = await fetch(`${normalized}/-/ping`, {
      signal: AbortSignal.timeout(3_500),
      headers: { Accept: 'application/json' },
    });
    return response.ok ? `${normalized}/` : null;
  } catch {
    return null;
  }
}

async function selectRegistry() {
  const override = (process.env.SPARKARC_NPM_REGISTRY || process.env.NPM_CONFIG_REGISTRY || '').trim();
  if (override) return override.replace(/\/+$/, '/');

  const candidates = [
    'https://registry.npmjs.org/',
    'https://registry.npmmirror.com/',
  ];
  for (const candidate of candidates) {
    const reachable = await probeRegistry(candidate);
    if (reachable) return reachable;
  }
  return candidates[0];
}

async function main() {
  if (nodeMajorVersion() < minimumNodeMajor) {
    throw new Error(`需要 Node.js ${minimumNodeMajor} 或更高版本，当前为 v${process.versions.node}。`);
  }
  if (!(await exists(packageJson))) {
    throw new Error(`未找到 ${packageJson}。`);
  }
  if (!(await exists(packageLock))) {
    throw new Error('未找到 package-lock.json，受管构建拒绝使用不确定的依赖图。');
  }

  const lockHash = await hashFile(packageLock);
  if (!(await buildInputsChanged(lockHash))) {
    console.log('[frontend] 前端产物与依赖锁一致，无需重新构建。');
    return;
  }

  const registry = await selectRegistry();
  const env = { ...process.env, NPM_CONFIG_REGISTRY: registry };
  console.log(`[frontend] 使用 npm registry: ${registry}`);
  console.log('[frontend] 安装锁定的前端依赖...');
  run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['ci', '--no-audit', '--no-fund'], env);
  console.log('[frontend] 构建前端...');
  run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], env);

  await mkdir(dirname(markerPath), { recursive: true });
  await writeFile(
    markerPath,
    `${JSON.stringify({ lockHash, builtAt: Date.now(), nodeVersion: process.versions.node, registry }, null, 2)}\n`,
    'utf8',
  );
  console.log('[frontend] 前端构建完成。');
}

main().catch((error) => fail(error instanceof Error ? error.message : String(error)));
