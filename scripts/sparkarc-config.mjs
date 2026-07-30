/**
 * SparkArc 跨语言项目常量的 Node 读取器。
 *
 * 业务代码不应在此处维护备用网址或仓库地址；所有值来自根目录 sparkarc.json。
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = dirname(fileURLToPath(import.meta.url));
export const projectRoot = join(scriptDir, '..');
export const configPath = join(projectRoot, 'sparkarc.json');

function requireString(value, name) {
  if (typeof value !== 'string' || !value.trim()) {
    throw new Error(`sparkarc.json 的 ${name} 必须是非空字符串。`);
  }
  return value.trim();
}

function requireUrlList(value, name) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || !item.trim())) {
    throw new Error(`sparkarc.json 的 ${name} 必须是 URL 字符串数组。`);
  }
  return value.map((item) => item.trim());
}

export function validateSparkArcConfig(config) {
  if (!config || typeof config !== 'object' || config.schemaVersion !== 1) {
    throw new Error('sparkarc.json 的 schemaVersion 必须为 1。');
  }
  if (config.repository?.provider !== 'github') {
    throw new Error('sparkarc.json 当前仅支持 repository.provider = "github"。');
  }
  const slug = requireString(config.repository?.slug, 'repository.slug');
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(slug)) {
    throw new Error('sparkarc.json 的 repository.slug 必须是 owner/repository 格式。');
  }
  if (config.repository?.mainlandRelease?.provider !== 'gitee') {
    throw new Error('sparkarc.json 当前仅支持 repository.mainlandRelease.provider = "gitee"。');
  }
  const mainlandReleaseSlug = requireString(config.repository.mainlandRelease.slug, 'repository.mainlandRelease.slug');
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(mainlandReleaseSlug)) {
    throw new Error('sparkarc.json 的 repository.mainlandRelease.slug 必须是 owner/repository 格式。');
  }
  requireUrlList(config.repository?.mainlandCloneUrls, 'repository.mainlandCloneUrls');
  if (!config.network || typeof config.network !== 'object') {
    throw new Error('sparkarc.json 缺少 network 配置。');
  }
  const geoIpProviders = requireUrlList(config.network.geoIpProviders, 'network.geoIpProviders');
  if (new Set(geoIpProviders).size < 2) {
    throw new Error('sparkarc.json 的 network.geoIpProviders 至少需要两个不同的服务。');
  }
  if (!config.network.resources || typeof config.network.resources !== 'object') {
    throw new Error('sparkarc.json 缺少 network.resources 配置。');
  }
  for (const [name, route] of Object.entries(config.network.resources)) {
    requireUrlList(route?.default, `network.resources.${name}.default`);
    requireUrlList(route?.mainland, `network.resources.${name}.mainland`);
  }
  for (const requiredResource of ['pypi', 'npm_registry', 'github_release', 'gh_proxy', 'huggingface', 'python_standalone', 'node_distribution']) {
    if (!Object.hasOwn(config.network.resources, requiredResource)) {
      throw new Error(`sparkarc.json 缺少 network.resources.${requiredResource}。`);
    }
  }
  return config;
}

export function readSparkArcConfig() {
  let config;
  try {
    config = JSON.parse(readFileSync(configPath, 'utf8'));
  } catch (error) {
    throw new Error(`无法读取 ${configPath}: ${error instanceof Error ? error.message : String(error)}`);
  }
  return validateSparkArcConfig(config);
}

export function repositoryUrls(config = readSparkArcConfig()) {
  const slug = config.repository.slug;
  const web = `https://github.com/${slug}`;
  const mainlandReleaseSlug = config.repository.mainlandRelease.slug;
  const mainlandReleaseWeb = `https://gitee.com/${mainlandReleaseSlug}`;
  return {
    slug,
    web,
    clone: `${web}.git`,
    mainlandClones: [...config.repository.mainlandCloneUrls],
    releaseApi: `https://api.github.com/repos/${slug}/releases/latest`,
    releasePage: `${web}/releases/latest`,
    mainlandRelease: {
      provider: config.repository.mainlandRelease.provider,
      slug: mainlandReleaseSlug,
      web: mainlandReleaseWeb,
      releaseApi: `https://gitee.com/api/v5/repos/${mainlandReleaseSlug}/releases/latest`,
      releasePage: `${mainlandReleaseWeb}/releases/latest`,
    },
  };
}

export function networkCandidates(resource, { mainland = false, includeFallback = true, config = readSparkArcConfig() } = {}) {
  const route = config.network.resources[resource];
  if (!route) {
    throw new Error(`sparkarc.json 未定义网络资源 ${resource}。`);
  }
  const preferred = mainland ? route.mainland : route.default;
  const fallback = mainland ? route.default : route.mainland;
  const candidates = includeFallback ? [...preferred, ...fallback] : [...preferred];
  return [...new Set(candidates.map((item) => item.trim()).filter(Boolean))];
}

export function allNetworkCandidates(resource, config = readSparkArcConfig()) {
  const route = config.network.resources[resource];
  if (!route) {
    throw new Error(`sparkarc.json 未定义网络资源 ${resource}。`);
  }
  return [...new Set([...route.default, ...route.mainland].map((item) => item.trim()).filter(Boolean))];
}
