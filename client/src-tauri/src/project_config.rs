//! 编译进 Launcher 的跨语言项目常量读取器。
//!
//! `sparkarc.json` 是唯一人工维护源；Cargo 会在该文件变化时重新构建，因此已发布
//! 的 Launcher 不依赖安装目录旁的源码文件。

use serde::Deserialize;
use std::{collections::BTreeMap, sync::OnceLock};

const PROJECT_CONFIG_JSON: &str =
    include_str!(concat!(env!("CARGO_MANIFEST_DIR"), "/../../sparkarc.json"));

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ProjectConfig {
    schema_version: u32,
    repository: RepositoryConfig,
    network: NetworkConfig,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RepositoryConfig {
    provider: String,
    slug: String,
    mainland_release: ReleaseRepositoryConfig,
    mainland_clone_urls: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReleaseRepositoryConfig {
    provider: String,
    slug: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct NetworkConfig {
    geo_ip_providers: Vec<String>,
    resources: BTreeMap<String, NetworkRoute>,
}

#[derive(Debug, Deserialize)]
struct NetworkRoute {
    #[serde(rename = "default")]
    default_urls: Vec<String>,
    mainland: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct RepositoryUrls {
    pub clone: String,
    pub mainland_clones: Vec<String>,
    pub release_api: String,
    pub release_page: String,
    pub mainland_release: ReleaseRepositoryUrls,
}

#[derive(Debug, Clone)]
pub struct ReleaseRepositoryUrls {
    pub web: String,
    pub release_api: String,
}

static PROJECT_CONFIG: OnceLock<ProjectConfig> = OnceLock::new();

fn config() -> &'static ProjectConfig {
    PROJECT_CONFIG.get_or_init(|| {
        let config: ProjectConfig =
            serde_json::from_str(PROJECT_CONFIG_JSON).expect("sparkarc.json 必须是有效 JSON");
        assert_eq!(
            config.schema_version, 1,
            "sparkarc.json schemaVersion 必须为 1"
        );
        assert_eq!(
            config.repository.provider, "github",
            "当前 Launcher 仅支持 GitHub 仓库"
        );
        assert!(
            config.network.geo_ip_providers.len() >= 2,
            "sparkarc.json network.geoIpProviders 至少需要两个服务"
        );
        assert!(
            config.repository.slug.split('/').count() == 2,
            "sparkarc.json repository.slug 必须是 owner/repository 格式"
        );
        assert_eq!(
            config.repository.mainland_release.provider, "gitee",
            "sparkarc.json repository.mainlandRelease.provider 必须为 gitee"
        );
        assert!(
            config.repository.mainland_release.slug.split('/').count() == 2,
            "sparkarc.json repository.mainlandRelease.slug 必须是 owner/repository 格式"
        );
        assert!(
            !config.repository.mainland_clone_urls.is_empty(),
            "sparkarc.json repository.mainlandCloneUrls 至少需要一个地址"
        );
        for resource in [
            "pypi",
            "npm_registry",
            "github_release",
            "gh_proxy",
            "huggingface",
            "python_standalone",
            "node_distribution",
        ] {
            let route = config
                .network
                .resources
                .get(resource)
                .unwrap_or_else(|| panic!("sparkarc.json 缺少网络资源 {resource}"));
            assert!(
                !route.default_urls.is_empty() || !route.mainland.is_empty(),
                "sparkarc.json 网络资源 {resource} 没有候选地址"
            );
        }
        config
    })
}

pub fn repository_urls() -> RepositoryUrls {
    let slug = config().repository.slug.clone();
    let web = format!("https://github.com/{slug}");
    let mainland_release_slug = config().repository.mainland_release.slug.clone();
    let mainland_release_web = format!("https://gitee.com/{mainland_release_slug}");
    RepositoryUrls {
        clone: format!("{web}.git"),
        mainland_clones: config().repository.mainland_clone_urls.clone(),
        release_api: format!("https://api.github.com/repos/{slug}/releases/latest"),
        release_page: format!("{web}/releases/latest"),
        mainland_release: ReleaseRepositoryUrls {
            web: mainland_release_web.clone(),
            release_api: format!(
                "https://gitee.com/api/v5/repos/{mainland_release_slug}/releases/latest"
            ),
        },
    }
}

pub fn geoip_providers() -> Vec<String> {
    config().network.geo_ip_providers.clone()
}

pub fn network_candidates(resource: &str, mainland: bool, include_fallback: bool) -> Vec<String> {
    let route = config()
        .network
        .resources
        .get(resource)
        .unwrap_or_else(|| panic!("sparkarc.json 未定义网络资源 {resource}"));
    let (preferred, fallback) = if mainland {
        (&route.mainland, &route.default_urls)
    } else {
        (&route.default_urls, &route.mainland)
    };
    let mut result = preferred.clone();
    if include_fallback {
        result.extend(fallback.iter().cloned());
    }
    result.retain(|value| !value.trim().is_empty());
    result.dedup();
    result
}

pub fn all_network_candidates(resource: &str) -> Vec<String> {
    let route = config()
        .network
        .resources
        .get(resource)
        .unwrap_or_else(|| panic!("sparkarc.json 未定义网络资源 {resource}"));
    let mut result = route.default_urls.clone();
    result.extend(route.mainland.iter().cloned());
    result.retain(|value| !value.trim().is_empty());
    result.dedup();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn repository_urls_are_derived_from_the_manifest() {
        let urls = repository_urls();
        let web = format!("https://github.com/{}", config().repository.slug);
        assert_eq!(urls.clone, format!("{web}.git"));
        assert_eq!(
            urls.mainland_clones.first().map(String::as_str),
            Some("https://gitee.com/aideaaa/spark-arc-studio.git")
        );
        assert_eq!(
            urls.release_api,
            format!(
                "https://api.github.com/repos/{}/releases/latest",
                config().repository.slug
            )
        );
        assert_eq!(config().repository.mainland_release.provider, "gitee");
        assert_eq!(
            urls.mainland_release.web,
            "https://gitee.com/aideaaa/spark-arc-studio"
        );
        assert_eq!(
            urls.mainland_release.release_api,
            "https://gitee.com/api/v5/repos/aideaaa/spark-arc-studio/releases/latest"
        );
    }

    #[test]
    fn mainland_routes_prefer_configured_mirrors() {
        let mainland = network_candidates("node_distribution", true, true);
        let default = network_candidates("node_distribution", false, true);
        assert_eq!(
            mainland.first().map(String::as_str),
            Some("https://npmmirror.com/mirrors/node")
        );
        assert_eq!(
            default.first().map(String::as_str),
            Some("https://nodejs.org/dist")
        );
    }
}
