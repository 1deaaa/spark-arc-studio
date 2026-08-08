#!/usr/bin/env node

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const githubRepository = env('GITHUB_REPOSITORY', '1deaaa/spark-arc-studio');
const giteeRepository = env('GITEE_REPOSITORY', 'aideaaa/spark-arc-studio');
const giteeApiBase = `${env('GITEE_API_BASE', 'https://gitee.com/api/v5')}/repos/${giteeRepository}`;
const stagingRoot = resolve(root, '.tmp', 'release-sync');
const maxAttempts = 3;

function env(name, fallback = '') {
  return String(process.env[name] || fallback).trim();
}

function sleep(ms) {
  return new Promise((resolvePromise) => setTimeout(resolvePromise, ms));
}

async function requestJson(url, options = {}, label = url) {
  let lastError;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, {
        ...options,
        signal: AbortSignal.timeout(options.timeoutMs || 120_000),
      });
      const text = await response.text();
      let data = null;
      try {
        data = text ? JSON.parse(text) : null;
      } catch {
        data = null;
      }
      if (response.ok) return data;
      const detail = data?.message || data?.error || text || response.statusText;
      lastError = new Error(`${label}: HTTP ${response.status} ${detail}`);
      if (response.status >= 400 && response.status < 500 && response.status !== 429) break;
    } catch (error) {
      lastError = error;
    }
    if (attempt < maxAttempts) await sleep(attempt * 5_000);
  }
  throw lastError || new Error(`${label}: request failed`);
}

function authHeaders(token, extra = {}) {
  return {
    Authorization: `token ${token}`,
    Accept: 'application/json',
    ...extra,
  };
}

async function downloadAsset(asset, destination, token) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const response = await fetch(asset.browser_download_url, {
        headers: {
          Accept: 'application/octet-stream',
          'User-Agent': 'SparkArc-Release-Sync',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: AbortSignal.timeout(10 * 60_000),
        redirect: 'follow',
      });
      if (!response.ok) throw new Error(`HTTP ${response.status} ${response.statusText}`);
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (asset.size && bytes.byteLength !== asset.size) {
        throw new Error(`size mismatch: expected ${asset.size}, got ${bytes.byteLength}`);
      }
      await writeFile(destination, bytes);
      return bytes.byteLength;
    } catch (error) {
      if (attempt === maxAttempts) throw new Error(`download ${asset.name} failed: ${error.message}`);
      console.warn(`Download retry ${attempt}/${maxAttempts}: ${asset.name}`);
      await sleep(attempt * 5_000);
    }
  }
  return 0;
}

async function getGiteeRelease(token, tag) {
  const url = `${giteeApiBase}/releases/tags/${encodeURIComponent(tag)}`;
  try {
    return await requestJson(url, { headers: authHeaders(token) }, `get Gitee release ${tag}`);
  } catch (error) {
    if (error.message.includes('HTTP 404')) return null;
    throw error;
  }
}

async function ensureGiteeRelease(token, githubRelease) {
  const tag = githubRelease.tag_name;
  const existing = await getGiteeRelease(token, tag);
  const payload = {
    tag_name: tag,
    name: githubRelease.name || `SparkArc Studio ${tag}`,
    body: githubRelease.body || '',
    prerelease: Boolean(githubRelease.prerelease),
  };
  if (existing?.id) {
    return requestJson(`${giteeApiBase}/releases/${existing.id}`, {
      method: 'PATCH',
      headers: authHeaders(token, { 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload),
    }, `update Gitee release ${tag}`);
  }
  return requestJson(`${giteeApiBase}/releases`, {
    method: 'POST',
    headers: authHeaders(token, { 'Content-Type': 'application/json' }),
    body: JSON.stringify({ ...payload, target_commitish: 'main' }),
  }, `create Gitee release ${tag}`);
}

async function listGiteeAssets(token, releaseId) {
  return requestJson(`${giteeApiBase}/releases/${releaseId}/attach_files?page=1&per_page=100`, {
    headers: authHeaders(token),
  }, `list Gitee assets for release ${releaseId}`);
}

async function deleteGiteeAsset(token, releaseId, assetId, name) {
  await requestJson(`${giteeApiBase}/releases/${releaseId}/attach_files/${assetId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  }, `delete Gitee asset ${name}`);
}

async function uploadGiteeAsset(token, releaseId, filePath, name, size) {
  const bytes = await readFile(filePath);
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      const form = new FormData();
      form.append('file', new Blob([bytes]), name);
      const url = `${giteeApiBase}/releases/${releaseId}/attach_files?name=${encodeURIComponent(name)}`;
      const uploaded = await requestJson(url, {
        method: 'POST',
        headers: authHeaders(token),
        body: form,
        timeoutMs: 10 * 60_000,
      }, `upload Gitee asset ${name}`);
      if (uploaded?.name !== name || Number(uploaded?.size) !== size) {
        throw new Error(`response mismatch for ${name}`);
      }
      return;
    } catch (error) {
      if (attempt === maxAttempts) throw error;
      console.warn(`Upload retry ${attempt}/${maxAttempts}: ${name}`);
      await sleep(attempt * 10_000);
    }
  }
}

async function main() {
  const giteeToken = env('GITEE_TOKEN');
  const githubToken = env('GITHUB_TOKEN');
  if (!giteeToken || giteeToken === 'PASTE_YOUR_GITEE_TOKEN_HERE') {
    throw new Error('GITEE_TOKEN is missing. Edit sync-github-release-to-gitee.bat first.');
  }

  const githubHeaders = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'SparkArc-Release-Sync',
    ...(githubToken ? { Authorization: `Bearer ${githubToken}` } : {}),
  };
  const releaseUrl = `${env('GITHUB_API_BASE', 'https://api.github.com')}/repos/${githubRepository}/releases/latest`;
  const githubRelease = await requestJson(releaseUrl, { headers: githubHeaders }, 'get GitHub latest release');
  if (!githubRelease?.tag_name || githubRelease.draft || githubRelease.prerelease) {
    throw new Error('GitHub latest release is missing or is not stable.');
  }
  const assets = Array.isArray(githubRelease.assets) ? githubRelease.assets : [];
  if (assets.length === 0) throw new Error(`GitHub release ${githubRelease.tag_name} has no assets.`);
  console.log(`GitHub release: ${githubRelease.tag_name} (${assets.length} assets)`);

  const giteeRelease = await ensureGiteeRelease(giteeToken, githubRelease);
  if (!giteeRelease?.id || giteeRelease.tag_name !== githubRelease.tag_name) {
    throw new Error('Gitee release response is invalid.');
  }
  const releaseDir = join(stagingRoot, githubRelease.tag_name);
  await mkdir(releaseDir, { recursive: true });
  let giteeAssets = await listGiteeAssets(giteeToken, giteeRelease.id);

  for (const asset of assets) {
    if (!asset.name || !asset.browser_download_url) continue;
    if (basename(asset.name) !== asset.name) throw new Error(`Unsafe asset name: ${asset.name}`);
    const size = Number(asset.size || 0);
    if (size > 100_000_000) throw new Error(`Asset exceeds Gitee 100 MB limit: ${asset.name}`);
    const destination = join(releaseDir, basename(asset.name));
    const localSize = await downloadAsset(asset, destination, githubToken);
    const existing = giteeAssets.find((item) => item.name === asset.name);
    if (existing && Number(existing.size) === localSize) {
      console.log(`Skip existing asset: ${asset.name}`);
      continue;
    }
    if (existing?.id) {
      await deleteGiteeAsset(giteeToken, giteeRelease.id, existing.id, asset.name);
    }
    await uploadGiteeAsset(giteeToken, giteeRelease.id, destination, asset.name, localSize);
    console.log(`Uploaded: ${asset.name}`);
    giteeAssets = await listGiteeAssets(giteeToken, giteeRelease.id);
  }

  const finalAssets = await listGiteeAssets(giteeToken, giteeRelease.id);
  const missing = assets.filter((asset) => !finalAssets.some(
    (uploaded) => uploaded.name === asset.name && Number(uploaded.size) === Number(asset.size),
  ));
  if (missing.length) throw new Error(`Gitee verification failed: ${missing.map((item) => item.name).join(', ')}`);
  console.log(`Sync complete: ${githubRelease.tag_name}`);
}

main().catch((error) => {
  console.error(error.message || error);
  process.exitCode = 1;
});
