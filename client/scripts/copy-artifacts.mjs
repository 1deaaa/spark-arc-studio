import { cp, mkdir, readdir, stat } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..", "..");
const clientRoot = resolve(__dirname, "..");

const platformArg = (process.argv[2] || "desktop").toLowerCase();

function desktopTarget() {
  switch (process.platform) {
    case "win32":
      return "windows";
    case "darwin":
      return "macos";
    default:
      return "linux";
  }
}

function resolveSource(target) {
  if (target === "android") {
    return resolve(clientRoot, "src-tauri", "gen", "android", "app", "build", "outputs");
  }
  if (target === "ios") {
    return resolve(clientRoot, "src-tauri", "gen", "ios");
  }
  return resolve(clientRoot, "src-tauri", "target", "release", "bundle");
}

function resolveDest(target) {
  return resolve(repoRoot, "app-build", target);
}

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

async function copyDir(source, dest) {
  await mkdir(dest, { recursive: true });
  await cp(source, dest, { recursive: true, force: true });
}

async function ensureSourceNotEmpty(source) {
  if (!(await exists(source))) {
    throw new Error(`Source not found: ${source}`);
  }
  const entries = await readdir(source);
  if (entries.length === 0) {
    throw new Error(`Source is empty: ${source}`);
  }
}

const target = platformArg === "desktop" ? desktopTarget() : platformArg;
const source = resolveSource(target);
const dest = resolveDest(target);

await ensureSourceNotEmpty(source);
await copyDir(source, dest);
console.log(`Copied build artifacts from ${source} to ${dest}`);
