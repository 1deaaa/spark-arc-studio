//! Launcher 本地部署与更新的唯一收口层。
//!
//! 这里不承担界面职责，也不依赖 PowerShell、Bash 或系统 Git。Launcher 只对
//! 自己创建并带有 ownership 标记的 `main` 工作树执行 Git 操作；用户的开发
//! 工作树和任意手动部署目录只能被启动，绝不会被此模块改写。

use chrono::{DateTime, Utc};
use flate2::read::GzDecoder;
use git2::{
    build::{CheckoutBuilder, RepoBuilder},
    AutotagOption, FetchOptions, Oid, Repository, Status, StatusOptions,
};
use reqwest::{blocking::Client, header::LOCATION, redirect::Policy, Url};
use semver::Version;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    fs,
    fs::File,
    io::Write,
    net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr, TcpStream},
    path::{Path, PathBuf},
    thread,
    time::Duration,
};
use sysinfo::{Pid, System};
use tar::Archive;
use xz2::read::XzDecoder;
use zip::ZipArchive;

#[cfg(windows)]
use std::process::Command;

const REPOSITORY_URL: &str = "https://github.com/1deaaa/spark-arc-studio.git";
const REPOSITORY_IDENTITY: &str = "1deaaa/spark-arc-studio";
const RELEASES_API_URL: &str =
    "https://api.github.com/repos/1deaaa/spark-arc-studio/releases/latest";
const RELEASES_LATEST_PAGE_URL: &str = "https://github.com/1deaaa/spark-arc-studio/releases/latest";
const MANAGED_MARKER_FILE: &str = ".sparkarc-managed.json";
const DEPLOYMENT_STATE_FILE: &str = "deployment.json";
const DEPLOYMENT_LOG_FILE: &str = "deploy.log";
const LAUNCHER_RELEASE_CACHE_FILE: &str = "launcher-release.json";
const MANAGED_SERVICE_PROCESS_FILE: &str = "managed-service-process.json";
const STAGING_DIR_NAME: &str = ".staging";
const MANAGED_INSTALL_DIR_NAME: &str = "sparkarc-server";
const MANAGED_SCHEMA_VERSION: u32 = 1;
const MANAGED_NODE_VERSION: &str = "24.16.0";
const LAUNCHER_RELEASE_CACHE_TTL_SECONDS: i64 = 6 * 60 * 60;
const MANAGED_SERVICE_PORT: u16 = 6688;
const GITHUB_PROXY_PREFIXES: [&str; 2] = ["https://ghfast.top/", "https://ghproxy.net/"];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum DeploymentPhase {
    Idle,
    Checking,
    Downloading,
    Ready,
    UpdateAvailable,
    ApplyingUpdate,
    Failed,
}

impl Default for DeploymentPhase {
    fn default() -> Self {
        Self::Idle
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DeploymentStatus {
    pub schema_version: u32,
    pub managed: bool,
    pub phase: DeploymentPhase,
    pub channel: String,
    pub project_root: Option<String>,
    pub installed_commit: Option<String>,
    pub available_commit: Option<String>,
    pub previous_commit: Option<String>,
    pub update_available: bool,
    pub checked_at: Option<String>,
    pub updated_at: Option<String>,
    pub last_source: Option<String>,
    pub last_error: Option<String>,
}

impl Default for DeploymentStatus {
    fn default() -> Self {
        Self {
            schema_version: MANAGED_SCHEMA_VERSION,
            managed: false,
            phase: DeploymentPhase::Idle,
            channel: "main".to_string(),
            project_root: None,
            installed_commit: None,
            available_commit: None,
            previous_commit: None,
            update_available: false,
            checked_at: None,
            updated_at: None,
            last_source: None,
            last_error: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ManagedInstallMarker {
    schema_version: u32,
    channel: String,
    repository: String,
    installed_commit: String,
    created_at: String,
    updated_at: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LauncherReleaseStatus {
    pub checked_at: String,
    pub current_version: String,
    pub latest_version: Option<String>,
    pub update_available: bool,
    pub release_url: Option<String>,
    pub last_error: Option<String>,
    pub source: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LauncherReleaseCache {
    checked_at: String,
    current_version: String,
    latest_version: Option<String>,
    update_available: bool,
    release_url: Option<String>,
    source: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ManagedServiceProcess {
    schema_version: u32,
    project_root: String,
    pid: u32,
    #[serde(default)]
    process_started_at: Option<u64>,
    started_at: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum ManagedProcessState {
    Missing,
    MatchesRecord,
    Mismatched,
}

#[derive(Debug, Deserialize)]
struct GithubRelease {
    tag_name: String,
    html_url: String,
    draft: bool,
    prerelease: bool,
}

#[derive(Debug, Clone)]
struct PreservedFile {
    relative_path: PathBuf,
    content: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum NodeArchiveKind {
    Zip,
    TarGz,
    TarXz,
}

#[derive(Debug, Clone)]
struct NodeDistribution {
    platform: String,
    archive_name: String,
    archive_kind: NodeArchiveKind,
    archive_sha256: &'static str,
}

/// 所有平台共享的受管部署器。
#[derive(Debug, Clone)]
pub struct DeploymentManager {
    user_dir: PathBuf,
    target_dir: PathBuf,
    state_path: PathBuf,
    log_path: PathBuf,
    launcher_release_cache_path: PathBuf,
    managed_service_process_path: PathBuf,
}

impl DeploymentManager {
    pub fn new() -> Result<Self, String> {
        let home = dirs::home_dir().ok_or_else(|| "无法获取用户主目录".to_string())?;
        Ok(Self::from_user_dir(home.join(".sparkarc")))
    }

    fn from_user_dir(user_dir: PathBuf) -> Self {
        let target_dir = user_dir.join(MANAGED_INSTALL_DIR_NAME);
        Self {
            state_path: user_dir.join(DEPLOYMENT_STATE_FILE),
            log_path: user_dir.join(DEPLOYMENT_LOG_FILE),
            launcher_release_cache_path: user_dir.join(LAUNCHER_RELEASE_CACHE_FILE),
            managed_service_process_path: user_dir.join(MANAGED_SERVICE_PROCESS_FILE),
            user_dir,
            target_dir,
        }
    }

    pub fn append_log(&self, message: impl AsRef<str>) {
        if self.ensure_user_dir().is_err() {
            return;
        }
        let line = format!(
            "{} {}\n",
            Utc::now().format("%Y-%m-%d %H:%M:%S UTC"),
            message.as_ref()
        );
        let _ = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.log_path)
            .and_then(|mut file| file.write_all(line.as_bytes()));
    }

    pub fn read_status(&self) -> DeploymentStatus {
        let Ok(raw) = fs::read_to_string(&self.state_path) else {
            return DeploymentStatus::default();
        };
        serde_json::from_str(&raw).unwrap_or_default()
    }

    fn write_status(&self, status: &DeploymentStatus) -> Result<(), String> {
        self.ensure_user_dir()?;
        write_json_atomically(&self.state_path, status)
    }

    fn save_status<F>(&self, mutate: F) -> Result<DeploymentStatus, String>
    where
        F: FnOnce(&mut DeploymentStatus),
    {
        let mut status = self.read_status();
        mutate(&mut status);
        self.write_status(&status)?;
        Ok(status)
    }

    pub fn is_valid_project_root(path: &Path) -> bool {
        path.is_dir()
            && ((path.join("server").join("app.py")).is_file()
                || path.join("start.bat").is_file()
                || path.join("start.sh").is_file())
    }

    pub fn is_managed_project(&self, path: &Path) -> bool {
        if !Self::is_valid_project_root(path) {
            return false;
        }
        let marker_path = path.join(MANAGED_MARKER_FILE);
        let Ok(raw) = fs::read_to_string(marker_path) else {
            return false;
        };
        let Ok(marker) = serde_json::from_str::<ManagedInstallMarker>(&raw) else {
            return false;
        };
        marker.schema_version == MANAGED_SCHEMA_VERSION
            && marker.channel == "main"
            && is_project_repository(&marker.repository)
    }

    /// 兼容旧版 Launcher 已创建的固定目录，但只会认领指向官方仓库的工作树。
    pub fn adopt_legacy_managed_install(&self) -> Result<bool, String> {
        if self.is_managed_project(&self.target_dir) {
            return Ok(true);
        }
        if !Self::is_valid_project_root(&self.target_dir) {
            return Ok(false);
        }

        let repository = match Repository::open(&self.target_dir) {
            Ok(repository) => repository,
            Err(_) => return Ok(false),
        };
        let origin = repository
            .find_remote("origin")
            .ok()
            .and_then(|remote| remote.url().ok().map(str::to_owned))
            .unwrap_or_default();
        if !is_project_repository(&origin) {
            return Ok(false);
        }

        self.write_marker(&self.target_dir, &repository)?;
        self.append_log("已认领旧版 Launcher 创建的 main 工作树。");
        Ok(true)
    }

    pub fn managed_project_root(&self) -> Result<Option<PathBuf>, String> {
        if self.is_managed_project(&self.target_dir) {
            return Ok(Some(self.target_dir.clone()));
        }
        if self.adopt_legacy_managed_install()? {
            return Ok(Some(self.target_dir.clone()));
        }
        Ok(None)
    }

    /// 首次部署时克隆 main；已有受管工作树不会被隐式更新。
    pub fn ensure_managed_checkout(&self) -> Result<PathBuf, String> {
        if let Some(project_root) = self.managed_project_root()? {
            return Ok(project_root);
        }
        if self.target_dir.exists() {
            return Err(format!(
                "发现未受 Launcher 管理的目录 {:?}。为避免覆盖用户文件，已拒绝自动接管。",
                self.target_dir
            ));
        }

        self.ensure_user_dir()?;
        self.save_status(|status| {
            status.phase = DeploymentPhase::Downloading;
            status.last_error = None;
            status.project_root = Some(self.target_dir.to_string_lossy().to_string());
        })?;
        self.append_log("开始创建 Launcher 受管的 main 工作树...");

        let staging_root = self.user_dir.join(STAGING_DIR_NAME);
        fs::create_dir_all(&staging_root).map_err(|err| err.to_string())?;
        let staging_dir = staging_root.join(format!(
            "install-{}",
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));

        let repository = match self.clone_main(&staging_dir) {
            Ok(repository) => repository,
            Err(err) => {
                let _ = fs::remove_dir_all(&staging_dir);
                self.mark_failed(&err)?;
                return Err(err);
            }
        };

        if !Self::is_valid_project_root(&staging_dir) {
            let message = "下载的仓库不包含 SparkArc 启动入口，已终止部署。".to_string();
            let _ = fs::remove_dir_all(&staging_dir);
            self.mark_failed(&message)?;
            return Err(message);
        }

        let commit = repository_head_commit(&repository)?;
        self.write_marker(&staging_dir, &repository)?;
        fs::rename(&staging_dir, &self.target_dir)
            .map_err(|err| format!("无法将已校验的源码切换到受管目录: {err}"))?;

        self.save_status(|status| {
            status.managed = true;
            status.phase = DeploymentPhase::Ready;
            status.project_root = Some(self.target_dir.to_string_lossy().to_string());
            status.installed_commit = Some(commit.clone());
            status.available_commit = Some(commit);
            status.update_available = false;
            status.updated_at = Some(now_string());
            status.last_error = None;
        })?;
        self.append_log("main 工作树已就绪。");
        Ok(self.target_dir.clone())
    }

    /// 为 Launcher 受管工作树准备私有 Node。该运行时不写入系统 PATH，也不调用
    /// winget、brew、apt 等包管理器。
    pub fn ensure_node_runtime(&self) -> Result<PathBuf, String> {
        let distribution = NodeDistribution::for_current_platform()?;
        let install_dir = self
            .user_dir
            .join("tools")
            .join("node")
            .join(MANAGED_NODE_VERSION)
            .join(&distribution.platform);
        let executable = node_executable_path(&install_dir);
        if verify_node_runtime(&executable) {
            return Ok(node_bin_dir(&install_dir));
        }

        self.ensure_user_dir()?;
        self.append_log(format!(
            "正在准备受管 Node.js v{} ({})...",
            MANAGED_NODE_VERSION, distribution.platform
        ));
        let staging_root = self.user_dir.join(STAGING_DIR_NAME).join("node");
        fs::create_dir_all(&staging_root).map_err(|err| err.to_string())?;
        let staging_dir = staging_root.join(format!(
            "node-{}",
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        fs::create_dir_all(&staging_dir).map_err(|err| err.to_string())?;
        let archive_path = staging_dir.join(&distribution.archive_name);
        let extract_root = staging_dir.join("extract");

        let result = (|| -> Result<(), String> {
            download_verified_node_archive(&distribution, &archive_path, self)?;
            extract_node_archive(&distribution, &archive_path, &extract_root)?;
            let extracted_root =
                extract_root.join(node_archive_root_name(&distribution.archive_name));
            if !verify_node_runtime(&node_executable_path(&extracted_root)) {
                return Err("解压后的 Node 运行时不完整或版本不匹配。".to_string());
            }

            if install_dir.exists() {
                fs::remove_dir_all(&install_dir)
                    .map_err(|err| format!("无法清理损坏的受管 Node 运行时: {err}"))?;
            }
            let parent = install_dir
                .parent()
                .ok_or_else(|| "受管 Node 目录无父路径。".to_string())?;
            fs::create_dir_all(parent).map_err(|err| err.to_string())?;
            fs::rename(&extracted_root, &install_dir)
                .map_err(|err| format!("无法切换受管 Node 运行时: {err}"))?;
            Ok(())
        })();

        let _ = fs::remove_dir_all(&staging_dir);
        if let Err(err) = result {
            self.append_log(format!("受管 Node.js 准备失败: {err}"));
            return Err(err);
        }
        self.append_log(format!("受管 Node.js v{} 已就绪。", MANAGED_NODE_VERSION));
        Ok(node_bin_dir(&install_dir))
    }

    /// 静默 fetch main，仅更新状态，不改工作树。
    pub fn check_main_update(&self) -> Result<DeploymentStatus, String> {
        let project_root = self
            .managed_project_root()?
            .ok_or_else(|| "尚未发现 Launcher 受管的本地服务。".to_string())?;
        let repository =
            Repository::open(&project_root).map_err(|err| format!("无法打开受管仓库: {err}"))?;
        let current = repository_head_commit(&repository)?;

        self.save_status(|status| {
            status.managed = true;
            status.phase = DeploymentPhase::Checking;
            status.project_root = Some(project_root.to_string_lossy().to_string());
            status.installed_commit = Some(current.clone());
            status.checked_at = Some(now_string());
            status.last_error = None;
        })?;
        self.append_log("正在检查 main 更新...");

        match self.fetch_main_commit(&repository) {
            Ok((available, source)) => {
                let update_available = available != current;
                let status = self.save_status(|status| {
                    status.managed = true;
                    status.phase = if update_available {
                        DeploymentPhase::UpdateAvailable
                    } else {
                        DeploymentPhase::Ready
                    };
                    status.installed_commit = Some(current.clone());
                    status.available_commit = Some(available.clone());
                    status.update_available = update_available;
                    status.checked_at = Some(now_string());
                    status.last_source = Some(source.clone());
                    status.last_error = None;
                })?;
                if update_available {
                    self.append_log(format!("发现 main 更新: {current} -> {available}"));
                } else {
                    self.append_log("当前已是 main 最新版本。");
                }
                Ok(status)
            }
            Err(err) => {
                self.append_log(format!("检查 main 更新失败: {err}"));
                self.save_status(|status| {
                    status.phase = DeploymentPhase::Ready;
                    status.checked_at = Some(now_string());
                    status.last_error = Some(err);
                })
            }
        }
    }

    /// 显式应用已发现的更新。调用方必须确保后端未运行。
    pub fn apply_main_update(&self) -> Result<DeploymentStatus, String> {
        let project_root = self
            .managed_project_root()?
            .ok_or_else(|| "尚未发现 Launcher 受管的本地服务。".to_string())?;
        let repository =
            Repository::open(&project_root).map_err(|err| format!("无法打开受管仓库: {err}"))?;
        let current = repository_head_commit(&repository)?;

        self.save_status(|status| {
            status.phase = DeploymentPhase::ApplyingUpdate;
            status.last_error = None;
            status.project_root = Some(project_root.to_string_lossy().to_string());
            status.installed_commit = Some(current.clone());
        })?;
        self.append_log("正在准备应用 main 更新...");

        let (available, source) = match self.fetch_main_commit(&repository) {
            Ok(result) => result,
            Err(err) => {
                self.mark_failed(&err)?;
                return Err(err);
            }
        };
        if available == current {
            return self.save_status(|status| {
                status.phase = DeploymentPhase::Ready;
                status.installed_commit = Some(current.clone());
                status.available_commit = Some(current);
                status.update_available = false;
                status.last_source = Some(source);
                status.last_error = None;
            });
        }

        let preserved = match collect_preserved_changes(&repository, &project_root) {
            Ok(files) => files,
            Err(err) => {
                self.mark_failed(&err)?;
                return Err(err);
            }
        };

        if let Err(err) = checkout_main_commit(&repository, &available) {
            let rollback_result = checkout_main_commit(&repository, &current);
            let restore_result = restore_preserved_files(&project_root, &preserved);
            let message = match (rollback_result, restore_result) {
                (Ok(()), Ok(())) => format!("应用更新失败，已回退旧版本: {err}"),
                (rollback, restore) => format!(
                    "应用更新失败且回退不完整: {err}; 回退结果: {rollback:?}; 数据恢复结果: {restore:?}"
                ),
            };
            self.mark_failed(&message)?;
            return Err(message);
        }

        if let Err(err) = restore_preserved_files(&project_root, &preserved) {
            let _ = checkout_main_commit(&repository, &current);
            let _ = restore_preserved_files(&project_root, &preserved);
            let message = format!("恢复受保护运行时文件失败，已尝试回退: {err}");
            self.mark_failed(&message)?;
            return Err(message);
        }

        self.write_marker(&project_root, &repository)?;
        let status = self.save_status(|status| {
            status.managed = true;
            status.phase = DeploymentPhase::Ready;
            status.installed_commit = Some(available.clone());
            status.available_commit = Some(available.clone());
            status.previous_commit = Some(current.clone());
            status.update_available = false;
            status.updated_at = Some(now_string());
            status.last_source = Some(source);
            status.last_error = None;
        })?;
        self.append_log(format!("已切换 main: {current} -> {available}"));
        Ok(status)
    }

    /// 直接读取 GitHub Release。API 受限或网络不稳定时，回退到 GitHub 标准
    /// `/releases/latest` 重定向；两者均不依赖项目仓库内的自定义更新清单。
    pub fn check_launcher_release(&self, current_version: &str) -> LauncherReleaseStatus {
        let cached = self.read_launcher_release_cache(current_version);
        if let Some(status) = cached
            .as_ref()
            .filter(|status| Self::is_launcher_release_cache_fresh(status))
        {
            return status.clone();
        }

        let checked_at = now_string();
        let client = match Client::builder()
            .timeout(Duration::from_secs(8))
            .user_agent("SparkArc-Launcher/1.0")
            .build()
        {
            Ok(client) => client,
            Err(err) => {
                return self.release_check_failure_or_stale_cache(
                    current_version,
                    checked_at,
                    vec![format!("无法创建 Release 检查客户端: {err}")],
                    cached,
                )
            }
        };

        let mut errors = Vec::new();
        for endpoint in github_release_api_candidates() {
            let response = match client
                .get(&endpoint)
                .header("Accept", "application/vnd.github+json")
                .send()
            {
                Ok(response) => response,
                Err(err) => {
                    errors.push(format!("{endpoint}: {err}"));
                    continue;
                }
            };
            if !response.status().is_success() {
                errors.push(format!("{endpoint}: HTTP {}", response.status()));
                continue;
            }
            let release = match response.json::<GithubRelease>() {
                Ok(release) => release,
                Err(err) => {
                    errors.push(format!("{endpoint}: Release 响应解析失败: {err}"));
                    continue;
                }
            };
            if release.draft || release.prerelease {
                errors.push(format!("{endpoint}: 最新 Release 不是稳定版本"));
                continue;
            }

            let latest_version = normalize_release_version(&release.tag_name);
            let update_available = latest_version
                .as_deref()
                .map(|latest| is_newer_version(latest, current_version))
                .unwrap_or(false);
            let status = LauncherReleaseStatus {
                checked_at,
                current_version: current_version.to_string(),
                latest_version,
                update_available,
                release_url: Some(release_url_for_source(&endpoint, &release.html_url)),
                last_error: None,
                source: Some(endpoint),
            };
            self.write_launcher_release_cache(&status);
            return status;
        }

        let redirect_client = match Client::builder()
            .timeout(Duration::from_secs(8))
            .user_agent("SparkArc-Launcher/1.0")
            .redirect(Policy::none())
            .build()
        {
            Ok(client) => client,
            Err(err) => {
                errors.push(format!("无法创建 Release 页面检查客户端: {err}"));
                return self.release_check_failure_or_stale_cache(
                    current_version,
                    checked_at,
                    errors,
                    cached,
                );
            }
        };
        for page in github_release_page_candidates() {
            let response = match redirect_client.get(&page).send() {
                Ok(response) => response,
                Err(err) => {
                    errors.push(format!("{page}: {err}"));
                    continue;
                }
            };
            if !response.status().is_redirection() {
                errors.push(format!("{page}: HTTP {}", response.status()));
                continue;
            }
            let Some(location) = response.headers().get(LOCATION) else {
                errors.push(format!("{page}: 缺少 Release 重定向地址"));
                continue;
            };
            let Ok(location) = location.to_str() else {
                errors.push(format!("{page}: Release 重定向地址编码无效"));
                continue;
            };
            let release_url = match Url::parse(&page).and_then(|base| base.join(location)) {
                Ok(url) => release_url_for_source(&page, url.as_str()),
                Err(err) => {
                    errors.push(format!("{page}: 无法解析 Release 重定向地址: {err}"));
                    continue;
                }
            };
            let Some(tag_name) = release_tag_from_url(&release_url) else {
                errors.push(format!("{page}: 无法从 Release 地址识别版本标签"));
                continue;
            };
            let latest_version = normalize_release_version(&tag_name);
            let update_available = latest_version
                .as_deref()
                .map(|latest| is_newer_version(latest, current_version))
                .unwrap_or(false);
            let status = LauncherReleaseStatus {
                checked_at,
                current_version: current_version.to_string(),
                latest_version,
                update_available,
                release_url: Some(release_url),
                last_error: None,
                source: Some(page),
            };
            self.write_launcher_release_cache(&status);
            return status;
        }

        self.release_check_failure_or_stale_cache(current_version, checked_at, errors, cached)
    }

    /// 由 Launcher 启动受管 main 时写入进程记录。记录只属于受管目录，绝不登记
    /// 用户手动部署的工作树，避免更新功能误杀开发者自己的服务。
    pub fn record_managed_service_process(&self, pid: u32) -> Result<(), String> {
        let project_root = self
            .managed_project_root()?
            .ok_or_else(|| "无法为未受管工作树登记服务进程。".to_string())?;
        self.ensure_user_dir()?;
        let record = ManagedServiceProcess {
            schema_version: MANAGED_SCHEMA_VERSION,
            project_root: project_root.to_string_lossy().to_string(),
            pid,
            process_started_at: managed_process_started_at(pid),
            started_at: now_string(),
        };
        write_json_atomically(&self.managed_service_process_path, &record)?;
        self.append_log(format!("已登记受管后端进程: {pid}"));
        Ok(())
    }

    /// 只停止本 Launcher 曾为受管 main 工作树登记的进程。进程记录不存在而 6688
    /// 端口仍被占用时，保守拒绝操作，避免影响其他本地服务。
    pub fn stop_managed_service(&self) -> Result<(), String> {
        let project_root = self
            .managed_project_root()?
            .ok_or_else(|| "尚未发现 Launcher 受管的本地服务。".to_string())?;
        let Some(record) = self.read_managed_service_process()? else {
            if managed_service_port_is_open() {
                return Err(
                    "检测到 6688 端口仍有本地服务，但缺少 Launcher 进程记录。为避免误停止其他服务，请先手动停止该服务后再更新。"
                        .to_string(),
                );
            }
            return Ok(());
        };
        if record.schema_version != MANAGED_SCHEMA_VERSION
            || Path::new(&record.project_root) != project_root
        {
            return Err("受管服务进程记录与当前工作树不匹配，已拒绝停止。".to_string());
        }

        match managed_process_state(&record) {
            ManagedProcessState::Missing => {
                if !managed_service_port_is_open() {
                    let _ = fs::remove_file(&self.managed_service_process_path);
                    self.append_log("受管服务进程记录已过期，已清理。");
                    return Ok(());
                }
                return Err(
                    "受管服务进程记录中的 PID 已不存在，但 6688 端口仍被占用。为避免误停止其他服务，请先手动停止后再更新。"
                        .to_string(),
                );
            }
            ManagedProcessState::Mismatched => {
                return Err(
                    "受管服务进程记录与当前 PID 的启动时间或命令行不匹配，已拒绝停止。请先手动确认该进程。"
                        .to_string(),
                );
            }
            ManagedProcessState::MatchesRecord => {}
        }

        self.append_log(format!("正在停止受管后端进程: {}", record.pid));
        if let Err(err) = terminate_process(record.pid) {
            if !managed_service_port_is_open() {
                let _ = fs::remove_file(&self.managed_service_process_path);
                self.append_log("受管服务进程记录已过期，已清理。");
                return Ok(());
            }
            return Err(err);
        }
        for _ in 0..40 {
            if !managed_service_port_is_open() {
                let _ = fs::remove_file(&self.managed_service_process_path);
                self.append_log("受管后端已停止。");
                return Ok(());
            }
            thread::sleep(Duration::from_millis(250));
        }
        Err(
            "停止受管后端超时，6688 端口仍被占用。为避免更新中切换运行代码，已取消更新。"
                .to_string(),
        )
    }

    /// 用于更新前的最后一道保护。端口、受管进程记录或 PID 身份任一存在不确定性
    /// 时，均拒绝切换代码，避免 Launcher 重启后在运行中的服务上覆盖文件。
    pub fn ensure_managed_service_stopped(&self) -> Result<(), String> {
        let project_root = self
            .managed_project_root()?
            .ok_or_else(|| "尚未发现 Launcher 受管的本地服务。".to_string())?;
        if managed_service_port_is_open() {
            return Err("检测到 6688 端口仍有本地服务，请先通过 Launcher 停止服务。".to_string());
        }
        let Some(record) = self.read_managed_service_process()? else {
            return Ok(());
        };
        if record.schema_version != MANAGED_SCHEMA_VERSION
            || Path::new(&record.project_root) != project_root
        {
            return Err("受管服务进程记录与当前工作树不匹配，已拒绝应用更新。".to_string());
        }
        match managed_process_state(&record) {
            ManagedProcessState::Missing => {
                let _ = fs::remove_file(&self.managed_service_process_path);
                self.append_log("受管服务进程记录已过期，已清理。");
                Ok(())
            }
            ManagedProcessState::MatchesRecord => {
                Err("检测到 Launcher 受管后端进程仍在运行，请先停止服务后再应用更新。".to_string())
            }
            ManagedProcessState::Mismatched => Err(
                "受管服务进程记录与当前 PID 身份不匹配，已拒绝应用更新。请先手动确认该进程。"
                    .to_string(),
            ),
        }
    }

    fn read_launcher_release_cache(&self, current_version: &str) -> Option<LauncherReleaseStatus> {
        let raw = fs::read_to_string(&self.launcher_release_cache_path).ok()?;
        let cache = serde_json::from_str::<LauncherReleaseCache>(&raw).ok()?;
        if cache.current_version != current_version {
            return None;
        }
        Some(LauncherReleaseStatus {
            checked_at: cache.checked_at,
            current_version: cache.current_version,
            latest_version: cache.latest_version,
            update_available: cache.update_available,
            release_url: cache.release_url,
            last_error: None,
            source: cache.source,
        })
    }

    fn is_launcher_release_cache_fresh(status: &LauncherReleaseStatus) -> bool {
        let Ok(checked_at) = DateTime::parse_from_rfc3339(&status.checked_at) else {
            return false;
        };
        let age_seconds = Utc::now()
            .signed_duration_since(checked_at.with_timezone(&Utc))
            .num_seconds();
        (0..=LAUNCHER_RELEASE_CACHE_TTL_SECONDS).contains(&age_seconds)
    }

    fn write_launcher_release_cache(&self, status: &LauncherReleaseStatus) {
        let cache = LauncherReleaseCache {
            checked_at: status.checked_at.clone(),
            current_version: status.current_version.clone(),
            latest_version: status.latest_version.clone(),
            update_available: status.update_available,
            release_url: status.release_url.clone(),
            source: status.source.clone(),
        };
        if let Err(err) = self
            .ensure_user_dir()
            .and_then(|_| write_json_atomically(&self.launcher_release_cache_path, &cache))
        {
            self.append_log(format!("无法写入 Launcher Release 缓存: {err}"));
        }
    }

    fn release_check_failure_or_stale_cache(
        &self,
        current_version: &str,
        checked_at: String,
        errors: Vec<String>,
        stale_cache: Option<LauncherReleaseStatus>,
    ) -> LauncherReleaseStatus {
        let error = errors.join("；");
        if let Some(mut cached) = stale_cache {
            cached.last_error = Some(format!("本次检查失败，仍展示上次结果: {error}"));
            return cached;
        }
        LauncherReleaseStatus {
            checked_at,
            current_version: current_version.to_string(),
            latest_version: None,
            update_available: false,
            release_url: None,
            last_error: Some(error),
            source: None,
        }
    }

    fn read_managed_service_process(&self) -> Result<Option<ManagedServiceProcess>, String> {
        if !self.managed_service_process_path.is_file() {
            return Ok(None);
        }
        let raw = fs::read_to_string(&self.managed_service_process_path)
            .map_err(|err| format!("无法读取受管服务进程记录: {err}"))?;
        serde_json::from_str(&raw)
            .map(Some)
            .map_err(|err| format!("受管服务进程记录格式无效: {err}"))
    }

    fn ensure_user_dir(&self) -> Result<(), String> {
        fs::create_dir_all(&self.user_dir).map_err(|err| err.to_string())
    }

    fn clone_main(&self, destination: &Path) -> Result<Repository, String> {
        let mut errors = Vec::new();
        for source in git_remote_candidates() {
            self.append_log(format!("尝试从 {source} 获取 main..."));
            let mut fetch_options = FetchOptions::new();
            fetch_options.download_tags(AutotagOption::None);
            fetch_options.depth(1);
            let mut builder = RepoBuilder::new();
            builder.branch("main").fetch_options(fetch_options);
            match builder.clone(&source, destination) {
                Ok(repository) => {
                    self.append_log(format!("已从 {source} 获取 main。"));
                    return Ok(repository);
                }
                Err(err) => {
                    errors.push(format!("{source}: {err}"));
                    let _ = fs::remove_dir_all(destination);
                }
            }
        }
        Err(format!("无法从任何 Git 源获取 main：{}", errors.join("；")))
    }

    fn fetch_main_commit(&self, repository: &Repository) -> Result<(String, String), String> {
        let reference_name = "refs/remotes/sparkarc-launcher/main";
        let refspec = format!("+refs/heads/main:{reference_name}");
        let mut errors = Vec::new();

        for source in git_remote_candidates() {
            self.append_log(format!("检查 main 源: {source}"));
            let mut fetch_options = FetchOptions::new();
            fetch_options.download_tags(AutotagOption::None);
            fetch_options.depth(1);
            let mut remote = match repository.remote_anonymous(&source) {
                Ok(remote) => remote,
                Err(err) => {
                    errors.push(format!("{source}: 无法创建远端: {err}"));
                    continue;
                }
            };
            match remote.fetch(&[&refspec], Some(&mut fetch_options), None) {
                Ok(()) => match repository.refname_to_id(reference_name) {
                    Ok(oid) => return Ok((oid.to_string(), source)),
                    Err(err) => errors.push(format!("{source}: 未找到 main 提交: {err}")),
                },
                Err(err) => errors.push(format!("{source}: {err}")),
            }
        }
        Err(format!("无法检查 main 更新：{}", errors.join("；")))
    }

    fn write_marker(&self, project_root: &Path, repository: &Repository) -> Result<(), String> {
        let commit = repository_head_commit(repository)?;
        let marker_path = project_root.join(MANAGED_MARKER_FILE);
        let existing = fs::read_to_string(&marker_path)
            .ok()
            .and_then(|raw| serde_json::from_str::<ManagedInstallMarker>(&raw).ok());
        let marker = ManagedInstallMarker {
            schema_version: MANAGED_SCHEMA_VERSION,
            channel: "main".to_string(),
            repository: REPOSITORY_URL.to_string(),
            installed_commit: commit,
            created_at: existing
                .as_ref()
                .map(|value| value.created_at.clone())
                .unwrap_or_else(now_string),
            updated_at: now_string(),
        };
        write_json_atomically(&marker_path, &marker)
    }

    fn mark_failed(&self, message: &str) -> Result<(), String> {
        self.append_log(message);
        self.save_status(|status| {
            status.phase = DeploymentPhase::Failed;
            status.last_error = Some(message.to_string());
        })?;
        Ok(())
    }
}

impl NodeDistribution {
    fn for_current_platform() -> Result<Self, String> {
        let (platform, extension, archive_kind, archive_sha256) =
            match (std::env::consts::OS, std::env::consts::ARCH) {
                ("windows", "x86_64") => (
                    "win-x64",
                    "zip",
                    NodeArchiveKind::Zip,
                    "edaca9bd58ec8e92037dac4e877d52f6b8f430b81c18b57e264b4e2fb111cd56",
                ),
                ("windows", "aarch64") => (
                    "win-arm64",
                    "zip",
                    NodeArchiveKind::Zip,
                    "14834611d4c6b3c06054e7007732b90474c16e0b32f395e05b55a571ef71c6d2",
                ),
                ("macos", "x86_64") => (
                    "darwin-x64",
                    "tar.gz",
                    NodeArchiveKind::TarGz,
                    "298b4c7b3cb80765c8703e42b90324a4ece3b6634947b89e769c3c980ab55185",
                ),
                ("macos", "aarch64") => (
                    "darwin-arm64",
                    "tar.gz",
                    NodeArchiveKind::TarGz,
                    "39189dab4eeb15706c424af0ac08a3044c9e48f7db12a7d77f6b7aafc7dd5df6",
                ),
                ("linux", "x86_64") => (
                    "linux-x64",
                    "tar.xz",
                    NodeArchiveKind::TarXz,
                    "d804845d34eddc21dc1092b519d643ef40b1f58ec5dec5c22b1f4bd8fabde6c9",
                ),
                ("linux", "aarch64") => (
                    "linux-arm64",
                    "tar.xz",
                    NodeArchiveKind::TarXz,
                    "524659219d6a207a7400f2bde15d19ba060ffbe0d32a8643319ad67e3bb64c78",
                ),
                (os, arch) => {
                    return Err(format!("暂不支持为 {os}/{arch} 自动准备 Node.js。"));
                }
            };
        let archive_name = format!("node-v{MANAGED_NODE_VERSION}-{platform}.{extension}");
        Ok(Self {
            platform: platform.to_string(),
            archive_name,
            archive_kind,
            archive_sha256,
        })
    }
}

fn node_distribution_bases() -> Vec<String> {
    let mut candidates = Vec::new();
    if let Ok(override_url) = std::env::var("SPARKARC_NODE_DIST_MIRROR") {
        let override_url = override_url.trim().trim_end_matches('/');
        if !override_url.is_empty() {
            candidates.push(override_url.to_string());
        }
    }
    candidates.push("https://nodejs.org/dist".to_string());
    candidates.push("https://npmmirror.com/mirrors/node".to_string());
    deduplicate_urls(candidates)
}

fn node_archive_root_name(archive_name: &str) -> String {
    archive_name
        .strip_suffix(".tar.gz")
        .or_else(|| archive_name.strip_suffix(".tar.xz"))
        .or_else(|| archive_name.strip_suffix(".zip"))
        .unwrap_or(archive_name)
        .to_string()
}

fn node_bin_dir(install_dir: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        install_dir.to_path_buf()
    } else {
        install_dir.join("bin")
    }
}

fn node_executable_path(install_dir: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        install_dir.join("node.exe")
    } else {
        install_dir.join("bin").join("node")
    }
}

fn verify_node_runtime(executable: &Path) -> bool {
    let Ok(output) = std::process::Command::new(executable)
        .arg("--version")
        .output()
    else {
        return false;
    };
    output.status.success()
        && String::from_utf8_lossy(&output.stdout).trim() == format!("v{MANAGED_NODE_VERSION}")
}

fn download_verified_node_archive(
    distribution: &NodeDistribution,
    destination: &Path,
    manager: &DeploymentManager,
) -> Result<(), String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(90))
        .user_agent("SparkArc-Launcher/1.0")
        .build()
        .map_err(|err| format!("无法创建 Node 下载客户端: {err}"))?;
    let mut errors = Vec::new();

    for base in node_distribution_bases() {
        let version_root = format!("{base}/v{MANAGED_NODE_VERSION}");
        let archive_url = format!("{version_root}/{}", distribution.archive_name);
        manager.append_log(format!("尝试下载受管 Node: {archive_url}"));

        let bytes = match client
            .get(&archive_url)
            .send()
            .and_then(|response| response.error_for_status())
        {
            Ok(response) => match response.bytes() {
                Ok(bytes) => bytes,
                Err(err) => {
                    errors.push(format!("{archive_url}: 下载内容读取失败: {err}"));
                    continue;
                }
            },
            Err(err) => {
                errors.push(format!("{archive_url}: {err}"));
                continue;
            }
        };
        let actual_sha256 = format!("{:x}", Sha256::digest(&bytes));
        if actual_sha256 != distribution.archive_sha256 {
            errors.push(format!("{archive_url}: SHA-256 校验失败"));
            continue;
        }
        fs::write(destination, &bytes)
            .map_err(|err| format!("无法写入 Node 下载文件 {:?}: {err}", destination))?;
        manager.append_log(format!("受管 Node 下载和校验完成: {archive_url}"));
        return Ok(());
    }

    Err(format!("无法下载受管 Node.js：{}", errors.join("；")))
}

fn extract_node_archive(
    distribution: &NodeDistribution,
    archive_path: &Path,
    destination: &Path,
) -> Result<(), String> {
    fs::create_dir_all(destination).map_err(|err| err.to_string())?;
    match distribution.archive_kind {
        NodeArchiveKind::Zip => {
            let file = File::open(archive_path).map_err(|err| err.to_string())?;
            let mut archive =
                ZipArchive::new(file).map_err(|err| format!("无法读取 Node ZIP 归档: {err}"))?;
            for index in 0..archive.len() {
                let mut entry = archive
                    .by_index(index)
                    .map_err(|err| format!("无法读取 Node ZIP 条目: {err}"))?;
                let Some(relative_path) = entry.enclosed_name().map(PathBuf::from) else {
                    return Err("Node ZIP 包含不安全路径。".to_string());
                };
                let output_path = destination.join(relative_path);
                if entry.is_dir() {
                    fs::create_dir_all(&output_path).map_err(|err| err.to_string())?;
                    continue;
                }
                let parent = output_path
                    .parent()
                    .ok_or_else(|| "Node ZIP 条目无父目录。".to_string())?;
                fs::create_dir_all(parent).map_err(|err| err.to_string())?;
                let mut output = File::create(&output_path).map_err(|err| err.to_string())?;
                std::io::copy(&mut entry, &mut output)
                    .map_err(|err| format!("无法解压 Node ZIP 文件 {:?}: {err}", output_path))?;
            }
        }
        NodeArchiveKind::TarGz => {
            let file = File::open(archive_path).map_err(|err| err.to_string())?;
            let decoder = GzDecoder::new(file);
            let mut archive = Archive::new(decoder);
            archive
                .unpack(destination)
                .map_err(|err| format!("无法解压 Node tar.gz 归档: {err}"))?;
        }
        NodeArchiveKind::TarXz => {
            let file = File::open(archive_path).map_err(|err| err.to_string())?;
            let decoder = XzDecoder::new(file);
            let mut archive = Archive::new(decoder);
            archive
                .unpack(destination)
                .map_err(|err| format!("无法解压 Node tar.xz 归档: {err}"))?;
        }
    }
    Ok(())
}

fn managed_service_port_is_open() -> bool {
    let addresses = [
        SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), MANAGED_SERVICE_PORT),
        SocketAddr::new(IpAddr::V6(Ipv6Addr::LOCALHOST), MANAGED_SERVICE_PORT),
    ];
    addresses
        .iter()
        .any(|address| TcpStream::connect_timeout(address, Duration::from_millis(300)).is_ok())
}

fn managed_process_started_at(pid: u32) -> Option<u64> {
    let system = System::new_all();
    system
        .process(Pid::from_u32(pid))
        .map(|process| process.start_time())
}

fn managed_process_state(record: &ManagedServiceProcess) -> ManagedProcessState {
    let system = System::new_all();
    let Some(process) = system.process(Pid::from_u32(record.pid)) else {
        return ManagedProcessState::Missing;
    };
    if record
        .process_started_at
        .is_some_and(|started_at| process.start_time() != started_at)
    {
        return ManagedProcessState::Mismatched;
    }
    let command = process
        .cmd()
        .iter()
        .map(|argument| argument.to_string_lossy())
        .collect::<Vec<_>>()
        .join(" ");
    if command_mentions_project_root(&command, &record.project_root) {
        ManagedProcessState::MatchesRecord
    } else {
        ManagedProcessState::Mismatched
    }
}

fn command_mentions_project_root(command: &str, project_root: &str) -> bool {
    let normalized_root = normalize_process_path(project_root);
    !normalized_root.is_empty() && normalize_process_path(command).contains(&normalized_root)
}

fn normalize_process_path(value: &str) -> String {
    let normalized = value.replace('\\', "/");
    if cfg!(windows) {
        normalized.to_ascii_lowercase()
    } else {
        normalized
    }
}

#[cfg(windows)]
fn terminate_process(pid: u32) -> Result<(), String> {
    let output = Command::new("taskkill.exe")
        .args(["/PID", &pid.to_string(), "/T", "/F"])
        .output()
        .map_err(|err| format!("无法调用 Windows 进程终止工具: {err}"))?;
    if output.status.success() {
        return Ok(());
    }
    let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
    Err(format!("无法停止受管后端进程 {pid}: {detail}"))
}

#[cfg(unix)]
fn terminate_process(pid: u32) -> Result<(), String> {
    let result = unsafe { libc::kill(pid as i32, libc::SIGTERM) };
    if result == 0 {
        return Ok(());
    }
    Err(format!(
        "无法停止受管后端进程 {pid}: {}",
        std::io::Error::last_os_error()
    ))
}

#[cfg(all(not(windows), not(unix)))]
fn terminate_process(_pid: u32) -> Result<(), String> {
    Err("当前平台不支持停止受管后端进程。".to_string())
}

fn now_string() -> String {
    Utc::now().to_rfc3339()
}

fn repository_head_commit(repository: &Repository) -> Result<String, String> {
    repository
        .head()
        .and_then(|head| head.peel_to_commit())
        .map(|commit| commit.id().to_string())
        .map_err(|err| format!("无法读取当前 main 提交: {err}"))
}

fn is_project_repository(url: &str) -> bool {
    url.to_ascii_lowercase()
        .replace(".git", "")
        .contains(REPOSITORY_IDENTITY)
}

fn git_remote_candidates() -> Vec<String> {
    let mut candidates = Vec::new();
    if let Ok(override_url) = std::env::var("SPARKARC_GIT_REMOTE") {
        let override_url = override_url.trim();
        if !override_url.is_empty() {
            candidates.push(override_url.to_string());
        }
    }
    candidates.push(REPOSITORY_URL.to_string());
    candidates.extend(
        GITHUB_PROXY_PREFIXES
            .iter()
            .map(|prefix| format!("{prefix}{REPOSITORY_URL}")),
    );
    deduplicate_urls(candidates)
}

fn github_release_api_candidates() -> Vec<String> {
    let mut candidates = Vec::new();
    if let Ok(override_url) = std::env::var("SPARKARC_GITHUB_RELEASE_API") {
        let override_url = override_url.trim();
        if !override_url.is_empty() {
            candidates.push(override_url.to_string());
        }
    }
    candidates.push(RELEASES_API_URL.to_string());
    candidates.extend(
        GITHUB_PROXY_PREFIXES
            .iter()
            .map(|prefix| format!("{prefix}{RELEASES_API_URL}")),
    );
    deduplicate_urls(candidates)
}

fn github_release_page_candidates() -> Vec<String> {
    let mut candidates = vec![RELEASES_LATEST_PAGE_URL.to_string()];
    candidates.extend(
        GITHUB_PROXY_PREFIXES
            .iter()
            .map(|prefix| format!("{prefix}{RELEASES_LATEST_PAGE_URL}")),
    );
    deduplicate_urls(candidates)
}

fn deduplicate_urls(candidates: Vec<String>) -> Vec<String> {
    let mut unique = Vec::new();
    for candidate in candidates {
        if !unique.iter().any(|item: &String| item == &candidate) {
            unique.push(candidate);
        }
    }
    unique
}

fn normalize_release_version(value: &str) -> Option<String> {
    let normalized = value
        .trim()
        .trim_start_matches("sparkarc-")
        .trim_start_matches('v');
    Version::parse(normalized)
        .ok()
        .map(|version| version.to_string())
}

fn release_url_for_source(source: &str, release_url: &str) -> String {
    for prefix in GITHUB_PROXY_PREFIXES {
        if source.starts_with(prefix) && release_url.starts_with("https://github.com/") {
            return format!("{prefix}{release_url}");
        }
    }
    release_url.to_string()
}

fn release_tag_from_url(release_url: &str) -> Option<String> {
    let parsed = Url::parse(release_url).ok()?;
    parsed
        .path()
        .split_once("/releases/tag/")
        .map(|(_, tag)| tag.trim_matches('/').to_string())
        .filter(|tag| !tag.is_empty())
}

fn is_newer_version(latest: &str, current: &str) -> bool {
    let Ok(latest) = Version::parse(latest.trim_start_matches('v')) else {
        return false;
    };
    let current = normalize_release_version(current)
        .and_then(|value| Version::parse(&value).ok())
        .unwrap_or_else(|| Version::new(0, 0, 0));
    latest > current
}

fn is_preserved_relative_path(relative_path: &Path) -> bool {
    let normalized = relative_path.to_string_lossy().replace('\\', "/");
    normalized == MANAGED_MARKER_FILE
        || normalized.starts_with("server/data/")
        || normalized.starts_with("server/_userdata/")
        || normalized.starts_with("server/shares_data/")
        || normalized.starts_with("server/.runtime/")
        || normalized.starts_with("server/llm/agen_matchbox/.runtime/")
        || normalized.starts_with("client/dist/")
        || normalized.starts_with("client/node_modules/")
        || normalized == "client/.frontend_build_complete"
        || normalized == "client/.package-lock.sha256"
        || normalized == "client/.frontend_build.log"
}

fn collect_preserved_changes(
    repository: &Repository,
    project_root: &Path,
) -> Result<Vec<PreservedFile>, String> {
    let mut options = StatusOptions::new();
    options
        .include_untracked(true)
        .recurse_untracked_dirs(false)
        .include_ignored(false);
    let statuses = repository
        .statuses(Some(&mut options))
        .map_err(|err| format!("无法检查受管工作树状态: {err}"))?;
    let mut preserved = Vec::new();

    for entry in statuses.iter() {
        let Ok(path) = entry.path() else {
            continue;
        };
        let relative_path = PathBuf::from(path);
        if !is_preserved_relative_path(&relative_path) {
            return Err(format!(
                "受管目录包含未声明的本地修改: {path}。为避免覆盖用户改动，Launcher 拒绝更新。"
            ));
        }

        let status = entry.status();
        let should_backup = status.intersects(
            Status::WT_MODIFIED
                | Status::WT_DELETED
                | Status::INDEX_MODIFIED
                | Status::INDEX_DELETED
                | Status::INDEX_RENAMED
                | Status::INDEX_TYPECHANGE,
        );
        let source_path = project_root.join(&relative_path);
        if should_backup && source_path.is_file() {
            let content = fs::read(&source_path)
                .map_err(|err| format!("无法备份受保护文件 {:?}: {err}", source_path))?;
            preserved.push(PreservedFile {
                relative_path,
                content,
            });
        }
    }
    Ok(preserved)
}

fn restore_preserved_files(project_root: &Path, files: &[PreservedFile]) -> Result<(), String> {
    for file in files {
        let destination = project_root.join(&file.relative_path);
        let parent = destination
            .parent()
            .ok_or_else(|| format!("受保护文件路径无父目录: {:?}", destination))?;
        fs::create_dir_all(parent).map_err(|err| err.to_string())?;
        fs::write(&destination, &file.content)
            .map_err(|err| format!("无法恢复受保护文件 {:?}: {err}", destination))?;
    }
    Ok(())
}

fn checkout_main_commit(repository: &Repository, commit_id: &str) -> Result<(), String> {
    let oid = Oid::from_str(commit_id).map_err(|err| err.to_string())?;
    let commit = repository
        .find_commit(oid)
        .map_err(|err| format!("无法读取目标 main 提交: {err}"))?;
    let branch_ref = "refs/heads/main";
    match repository.find_reference(branch_ref) {
        Ok(mut reference) => {
            reference
                .set_target(oid, "SparkArc Launcher apply main update")
                .map_err(|err| format!("无法更新本地 main 引用: {err}"))?;
        }
        Err(_) => {
            repository
                .branch("main", &commit, true)
                .map_err(|err| format!("无法创建本地 main 分支: {err}"))?;
        }
    }
    repository
        .set_head(branch_ref)
        .map_err(|err| format!("无法切换到 main: {err}"))?;
    let mut checkout = CheckoutBuilder::new();
    checkout.force();
    repository
        .checkout_head(Some(&mut checkout))
        .map_err(|err| format!("无法检出新的 main 文件: {err}"))
}

fn write_json_atomically<T: Serialize>(path: &Path, value: &T) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| format!("状态文件路径无父目录: {:?}", path))?;
    fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    let temporary = path.with_extension("tmp");
    let content = serde_json::to_vec_pretty(value).map_err(|err| err.to_string())?;
    fs::write(&temporary, content).map_err(|err| err.to_string())?;
    if let Err(first_error) = fs::rename(&temporary, path) {
        // 某些旧版 Windows 文件系统不能覆盖现有文件；状态文件允许这一受控回退。
        if path.exists() {
            fs::remove_file(path).map_err(|err| err.to_string())?;
            fs::rename(&temporary, path).map_err(|err| err.to_string())?;
        } else {
            return Err(first_error.to_string());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use git2::{IndexAddOption, Signature};
    use std::{env, process};

    fn create_test_repository() -> (PathBuf, Repository) {
        let root = env::temp_dir().join(format!(
            "sparkarc-deployment-test-{}-{}",
            process::id(),
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        fs::create_dir_all(root.join("server")).unwrap();
        fs::write(root.join("server").join("app.py"), "VERSION = 'one'\n").unwrap();
        let repository = Repository::init(&root).unwrap();
        (root, repository)
    }

    fn commit_all(repository: &Repository, message: &str) -> Oid {
        let mut index = repository.index().unwrap();
        index
            .add_all(["*"].iter(), IndexAddOption::DEFAULT, None)
            .unwrap();
        index.write().unwrap();
        let tree_id = index.write_tree().unwrap();
        let tree = repository.find_tree(tree_id).unwrap();
        let signature = Signature::now("SparkArc Test", "test@example.invalid").unwrap();
        let parents = repository
            .head()
            .ok()
            .and_then(|head| head.peel_to_commit().ok())
            .into_iter()
            .collect::<Vec<_>>();
        let parent_refs = parents.iter().collect::<Vec<_>>();
        repository
            .commit(
                Some("HEAD"),
                &signature,
                &signature,
                message,
                &tree,
                &parent_refs,
            )
            .unwrap()
    }

    #[test]
    fn release_tag_normalization_only_accepts_semver() {
        assert_eq!(
            normalize_release_version("sparkarc-v1.2.3"),
            Some("1.2.3".to_string())
        );
        assert_eq!(
            normalize_release_version("v1.2.3-beta.1"),
            Some("1.2.3-beta.1".to_string())
        );
        assert_eq!(normalize_release_version("main"), None);
    }

    #[test]
    fn release_comparison_handles_launcher_prefixes() {
        assert!(is_newer_version("1.2.0", "sparkarc-v1.1.9"));
        assert!(!is_newer_version("1.2.0", "1.2.0"));
        assert!(!is_newer_version("1.2.0", "1.3.0"));
    }

    #[test]
    fn release_redirect_keeps_the_successful_proxy_source() {
        let proxy_page =
            "https://ghfast.top/https://github.com/1deaaa/spark-arc-studio/releases/latest";
        let direct_release =
            "https://github.com/1deaaa/spark-arc-studio/releases/tag/sparkarc-v0.5.0";
        let proxied_release = release_url_for_source(proxy_page, direct_release);

        assert_eq!(
            proxied_release,
            "https://ghfast.top/https://github.com/1deaaa/spark-arc-studio/releases/tag/sparkarc-v0.5.0"
        );
        assert_eq!(
            release_tag_from_url(&proxied_release),
            Some("sparkarc-v0.5.0".to_string())
        );
    }

    #[test]
    fn launcher_release_cache_has_a_bounded_lifetime() {
        let fresh = LauncherReleaseStatus {
            checked_at: now_string(),
            current_version: "0.0.1".to_string(),
            latest_version: Some("0.5.0".to_string()),
            update_available: true,
            release_url: Some("https://example.invalid/release".to_string()),
            last_error: None,
            source: Some("test".to_string()),
        };
        assert!(DeploymentManager::is_launcher_release_cache_fresh(&fresh));

        let expired = LauncherReleaseStatus {
            checked_at: (Utc::now() - chrono::Duration::hours(7)).to_rfc3339(),
            ..fresh
        };
        assert!(!DeploymentManager::is_launcher_release_cache_fresh(
            &expired
        ));
    }

    #[test]
    fn managed_process_identity_requires_the_managed_project_path() {
        let project_root = "/home/sparkarc/.sparkarc/sparkarc-server";
        assert!(command_mentions_project_root(
            "/home/sparkarc/.sparkarc/sparkarc-server/server/.runtime/python/bin/python3 /home/sparkarc/.sparkarc/sparkarc-server/server/app.py",
            project_root,
        ));
        assert!(command_mentions_project_root(
            "C:\\Users\\SparkArc\\.sparkarc\\sparkarc-server\\start.bat",
            "C:/Users/SparkArc/.sparkarc/sparkarc-server",
        ));
        assert!(!command_mentions_project_root(
            "/home/sparkarc/other-project/server/app.py",
            project_root,
        ));
    }

    #[test]
    fn runtime_paths_are_preserved_but_source_edits_are_rejected() {
        assert!(is_preserved_relative_path(Path::new(
            "server/data/users.db"
        )));
        assert!(is_preserved_relative_path(Path::new(
            "server/_userdata/u/demo.arc"
        )));
        assert!(is_preserved_relative_path(Path::new(
            "client/dist/assets/app.js"
        )));
        assert!(!is_preserved_relative_path(Path::new("server/app.py")));
        assert!(!is_preserved_relative_path(Path::new("client/src/App.vue")));
    }

    #[test]
    fn repository_identity_accepts_direct_and_proxy_urls() {
        assert!(is_project_repository(REPOSITORY_URL));
        assert!(is_project_repository(
            "https://ghfast.top/https://github.com/1deaaa/spark-arc-studio.git"
        ));
        assert!(!is_project_repository(
            "https://github.com/example/other.git"
        ));
    }

    #[test]
    fn managed_node_distribution_is_pinned_to_a_verified_archive() {
        let distribution = NodeDistribution::for_current_platform().unwrap();
        assert!(distribution
            .archive_name
            .starts_with(&format!("node-v{MANAGED_NODE_VERSION}-")));
        assert_eq!(distribution.archive_sha256.len(), 64);
        assert_eq!(
            node_archive_root_name(&distribution.archive_name),
            distribution
                .archive_name
                .trim_end_matches(".tar.gz")
                .trim_end_matches(".tar.xz")
                .trim_end_matches(".zip")
        );
    }

    #[test]
    fn checkout_switches_between_local_main_commits_without_system_git() {
        let (root, repository) = create_test_repository();
        let first = commit_all(&repository, "first");
        fs::write(root.join("server").join("app.py"), "VERSION = 'two'\n").unwrap();
        let second = commit_all(&repository, "second");

        checkout_main_commit(&repository, &first.to_string()).unwrap();
        assert_eq!(
            repository_head_commit(&repository).unwrap(),
            first.to_string()
        );
        assert_eq!(
            fs::read_to_string(root.join("server").join("app.py"))
                .unwrap()
                .replace("\r\n", "\n"),
            "VERSION = 'one'\n"
        );

        checkout_main_commit(&repository, &second.to_string()).unwrap();
        assert_eq!(
            repository_head_commit(&repository).unwrap(),
            second.to_string()
        );
        assert_eq!(
            fs::read_to_string(root.join("server").join("app.py"))
                .unwrap()
                .replace("\r\n", "\n"),
            "VERSION = 'two'\n"
        );
        fs::remove_dir_all(root).unwrap();
    }
}
