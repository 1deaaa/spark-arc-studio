import { readFile, readdir } from 'node:fs/promises';
import { basename, join, relative, resolve } from 'node:path';

const root = process.cwd();

function env(name, fallback = '') {
  return (process.env[name] || fallback || '').trim();
}

function boolEnv(name, fallback) {
  const raw = env(name, fallback ? 'true' : 'false').toLowerCase();
  return raw === '1' || raw === 'true' || raw === 'yes';
}

async function readVersion() {
  const configPath = resolve(root, 'client', 'src-tauri', 'tauri.conf.json');
  const raw = await readFile(configPath, 'utf8');
  return JSON.parse(raw).version;
}

async function collectFiles(paths) {
  const files = [];

  async function walk(path) {
    const entries = await readdir(path, { withFileTypes: true });
    for (const entry of entries) {
      const next = join(path, entry.name);
      if (entry.isDirectory()) {
        await walk(next);
      } else if (entry.isFile()) {
        files.push(next);
      }
    }
  }

  for (const path of paths) {
    const abs = resolve(root, path);
    const entries = await readdir(abs, { withFileTypes: true });
    if (entries.length === 0) {
      throw new Error(`Artifact directory is empty: ${path}`);
    }
    for (const entry of entries) {
      const next = join(abs, entry.name);
      if (entry.isDirectory()) {
        await walk(next);
      } else if (entry.isFile()) {
        files.push(next);
      }
    }
  }

  return files;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const message = data?.message || data?.errors?.[0]?.message || text || response.statusText;
    const error = new Error(`${options.method || 'GET'} ${url} failed: ${response.status} ${message}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

async function main() {
  const artifactArgs = process.argv.slice(2);

  const token = env('GITEA_RELEASE_TOKEN') || env('GITEA_TOKEN') || env('GITHUB_TOKEN');
  if (!token) {
    throw new Error('Missing GITEA_RELEASE_TOKEN, GITEA_TOKEN, or GITHUB_TOKEN.');
  }

  const serverUrl = (env('GITEA_SERVER_URL') || env('GITHUB_SERVER_URL')).replace(/\/+$/, '');
  const repository = env('GITEA_REPOSITORY') || env('GITHUB_REPOSITORY');
  if (!serverUrl || !repository || !repository.includes('/')) {
    throw new Error('Missing Gitea server/repository context. Expected GITEA_SERVER_URL/GITHUB_SERVER_URL and GITEA_REPOSITORY/GITHUB_REPOSITORY.');
  }

  const [owner, repo] = repository.split('/');
  const apiBase = `${serverUrl}/api/v1/repos/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`;
  const version = await readVersion();
  const tag = env('RELEASE_TAG', `sparkarc-v${version}`);
  const name = env('RELEASE_NAME', `SparkArc Studio v${version}`);
  const body = env('RELEASE_BODY', 'SparkArc Studio release.');
  const draft = boolEnv('RELEASE_DRAFT', true);
  const prerelease = boolEnv('RELEASE_PRERELEASE', false);
  const target = env('GITHUB_SHA') || env('GITEA_SHA') || env('RELEASE_TARGET');
  const headers = {
    Authorization: `token ${token}`,
    Accept: 'application/json',
  };

  let release;
  try {
    release = await requestJson(`${apiBase}/releases/tags/${encodeURIComponent(tag)}`, { headers });
    console.log(`Using existing Gitea release ${tag} (#${release.id}).`);
  } catch (error) {
    if (error.status !== 404) throw error;
    release = await requestJson(`${apiBase}/releases`, {
      method: 'POST',
      headers: {
        ...headers,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        tag_name: tag,
        target_commitish: target || undefined,
        name,
        body,
        draft,
        prerelease,
      }),
    });
    console.log(`Created Gitea release ${tag} (#${release.id}).`);
  }

  if (boolEnv('RELEASE_ENSURE_ONLY', false)) {
    console.log(`Ensured Gitea release ${tag} (#${release.id}).`);
    return;
  }

  if (artifactArgs.length === 0) {
    throw new Error('Usage: node scripts/gitea-release-upload.mjs <artifact-dir> [artifact-dir...]');
  }

  const assets = new Map((release.assets || []).map((asset) => [asset.name, asset.id]));
  const files = await collectFiles(artifactArgs);
  if (files.length === 0) {
    throw new Error(`No artifacts found in: ${artifactArgs.join(', ')}`);
  }

  for (const file of files) {
    const relativeName = relative(root, file).replaceAll('\\', '/');
    const assetName = basename(file);
    const existingId = assets.get(assetName);

    if (existingId) {
      await requestJson(`${apiBase}/releases/${release.id}/assets/${existingId}`, {
        method: 'DELETE',
        headers,
      });
      console.log(`Deleted existing asset ${assetName}.`);
    }

    const bytes = await readFile(file);
    const form = new FormData();
    form.append('attachment', new Blob([bytes]), assetName);

    await requestJson(`${apiBase}/releases/${release.id}/assets?name=${encodeURIComponent(assetName)}`, {
      method: 'POST',
      headers,
      body: form,
    });
    console.log(`Uploaded ${relativeName} as ${assetName}.`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
