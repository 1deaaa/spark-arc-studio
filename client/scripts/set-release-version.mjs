import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const versionSources = [
  process.env.RELEASE_VERSION,
  process.env.RELEASE_TAG,
  process.env.GITHUB_REF_NAME,
  process.env.GITEA_REF_NAME,
  process.env.GITHUB_REF,
  process.env.GITEA_REF,
  process.env.CI_COMMIT_TAG,
];

function normalizeVersion(input) {
  if (!input) {
    return null;
  }

  const value = input.trim();
  if (!value) {
    return null;
  }

  const directMatch = value.match(/^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/);
  if (directMatch) {
    return directMatch[0];
  }

  const tagMatch = value.match(/(?:^|[^0-9A-Za-z])v?(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)(?:$|[^0-9A-Za-z.+-])/);
  return tagMatch?.[1] ?? null;
}

const version = versionSources.map(normalizeVersion).find(Boolean);

if (!version) {
  console.error('未能从 RELEASE_VERSION、tag 或 CI 环境中解析版本号');
  process.exit(1);
}

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

async function updateJson(relativePath, mutate, indent = 2) {
  const absolutePath = path.join(rootDir, relativePath);
  const source = await readFile(absolutePath, 'utf8');
  const parsed = JSON.parse(source);
  mutate(parsed);
  await writeFile(absolutePath, `${JSON.stringify(parsed, null, indent)}\n`, 'utf8');
}

async function updateCargoVersion() {
  const cargoPath = path.join(rootDir, 'src-tauri', 'Cargo.toml');
  const source = await readFile(cargoPath, 'utf8');
  const eol = source.includes('\r\n') ? '\r\n' : '\n';
  const lines = source.split(/\r?\n/);

  let inPackageSection = false;
  let updated = false;

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const trimmed = rawLine.trim();

    if (trimmed === '[package]') {
      inPackageSection = true;
      continue;
    }

    if (inPackageSection && trimmed.startsWith('[') && trimmed.endsWith(']')) {
      break;
    }

    if (inPackageSection && /^version\s*=/.test(trimmed)) {
      lines[index] = rawLine.replace(
        /^(\s*version\s*=\s*")[^"]+(".*)$/,
        `$1${version}$2`,
      );
      updated = lines[index] !== rawLine;
      break;
    }
  }

  if (!updated) {
    throw new Error('未能更新 src-tauri/Cargo.toml 中的版本号');
  }

  await writeFile(cargoPath, lines.join(eol), 'utf8');
}

await updateJson('package.json', (data) => {
  data.version = version;
});

await updateJson('package-lock.json', (data) => {
  data.version = version;
  if (data.packages?.['']) {
    data.packages[''].version = version;
  }
});

await updateJson(
  path.join('src-tauri', 'tauri.conf.json'),
  (data) => {
    data.version = version;
  },
  '\t',
);

await updateCargoVersion();

console.log(`Version set to ${version}`);
