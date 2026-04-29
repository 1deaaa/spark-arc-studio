import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const version = process.env.RELEASE_VERSION?.trim();

if (!version) {
  console.error('RELEASE_VERSION is required');
  process.exit(1);
}

if (!/^[0-9A-Za-z][0-9A-Za-z.+-]*$/.test(version)) {
  console.error(`Invalid RELEASE_VERSION: ${version}`);
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
  const next = source.replace(
    /(^\[package\][\s\S]*?^version = ")([^"]+)(")/m,
    `$1${version}$3`,
  );

  if (next === source) {
    throw new Error('Failed to update version in src-tauri/Cargo.toml');
  }

  await writeFile(cargoPath, next, 'utf8');
}

await updateJson('package.json', (data) => {
  data.version = version;
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
