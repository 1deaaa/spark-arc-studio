use serde::{Deserialize, Serialize};
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::Mutex,
};
use tauri::{AppHandle, Manager};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct LauncherThemeState {
    theme_mode: Option<String>,
    prefers_dark: Option<bool>,
    primary_color_dark: Option<String>,
    primary_color_light: Option<String>,
    font_key: Option<String>,
    font_family: Option<String>,
    updated_at: Option<u64>,
}

const SPARKARC_REPO_URL: &str = "https://github.com/1deaaa/spark-arc-studio.git";

fn launcher_theme_state_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_data_dir().map_err(|err| err.to_string())?;
    fs::create_dir_all(&dir).map_err(|err| err.to_string())?;
    Ok(dir.join("launcher-theme.json"))
}

#[tauri::command]
fn get_launcher_theme_state(app: AppHandle) -> Result<Option<LauncherThemeState>, String> {
    let path = launcher_theme_state_path(&app)?;
    if !path.exists() {
        return Ok(None);
    }

    let raw = fs::read_to_string(path).map_err(|err| err.to_string())?;
    if raw.trim().is_empty() {
        return Ok(None);
    }

    serde_json::from_str(&raw)
        .map(Some)
        .map_err(|err| err.to_string())
}

#[tauri::command]
fn set_launcher_theme_state(app: AppHandle, state: LauncherThemeState) -> Result<(), String> {
    let path = launcher_theme_state_path(&app)?;
    let raw = serde_json::to_string_pretty(&state).map_err(|err| err.to_string())?;
    fs::write(path, raw).map_err(|err| err.to_string())
}

// ===== 本地部署相关命令 =====

/// 用户主目录下的 SparkArc 状态目录。
fn sparkarc_user_dir() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or_else(|| "无法获取用户主目录".to_string())?;
    Ok(home.join(".sparkarc"))
}

/// 服务安装记录文件路径：~/.sparkarc/service.json
fn service_record_path() -> Result<PathBuf, String> {
    Ok(sparkarc_user_dir()?.join("service.json"))
}

/// 部署日志文件路径：~/.sparkarc/deploy.log
fn deploy_log_path() -> Result<PathBuf, String> {
    Ok(sparkarc_user_dir()?.join("deploy.log"))
}

/// 读取服务安装记录。
fn read_service_record() -> Result<Option<serde_json::Value>, String> {
    let path = service_record_path()?;
    if !path.is_file() {
        return Ok(None);
    }
    let raw = fs::read_to_string(path).map_err(|err| err.to_string())?;
    serde_json::from_str(&raw)
        .map(Some)
        .map_err(|err| err.to_string())
}

/// 校验记录的 projectRoot 是否仍然有效。
fn is_record_valid(record: &serde_json::Value) -> bool {
    let Some(root_str) = record.get("projectRoot").and_then(|v| v.as_str()) else {
        return false;
    };
    let root = Path::new(root_str);
    if !root.is_dir() {
        return false;
    }
    (root.join("server").join("app.py")).is_file()
        || root.join("start.bat").is_file()
        || root.join("start.sh").is_file()
}

/// 返回服务记录中有效的项目根目录。
fn valid_record_project_root() -> Result<Option<PathBuf>, String> {
    let Some(record) = read_service_record()? else {
        return Ok(None);
    };
    if !is_record_valid(&record) {
        return Ok(None);
    }
    let Some(root_str) = record.get("projectRoot").and_then(|v| v.as_str()) else {
        return Ok(None);
    };
    Ok(Some(PathBuf::from(root_str)))
}

/// 获取当前可执行文件所在目录。
fn launcher_dir() -> Result<PathBuf, String> {
    let exe = std::env::current_exe().map_err(|err| err.to_string())?;
    exe.parent()
        .map(|p| p.to_path_buf())
        .ok_or_else(|| "无法获取启动器所在目录".to_string())
}

/// 探测 launcher 同级目录下是否已有 SparkArc 项目。
fn find_sibling_backend() -> Option<PathBuf> {
    let launcher_dir = launcher_dir().ok()?;
    for name in ["sparkarc", "sparkarc-server", "server"] {
        let candidate = launcher_dir.join(name);
        if candidate.is_dir()
            && ((candidate.join("server").join("app.py")).is_file()
                || candidate.join("start.bat").is_file()
                || candidate.join("start.sh").is_file())
        {
            return Some(candidate);
        }
    }
    None
}

/// 命令：检查本地后端目录是否存在且有效。
#[tauri::command]
fn check_local_backend_dir() -> Result<bool, String> {
    // 优先读取用户目录记录
    if let Some(record) = read_service_record()? {
        if is_record_valid(&record) {
            return Ok(true);
        }
    }
    // 回退到探测 launcher 同级目录
    Ok(find_sibling_backend().is_some())
}

/// 命令：读取部署日志的最后 N 行。
#[tauri::command]
fn read_deployment_log(lines: Option<usize>) -> Result<String, String> {
    let path = deploy_log_path()?;
    if !path.is_file() {
        return Ok(String::new());
    }
    let bytes = fs::read(path).map_err(|err| err.to_string())?;
    let raw = String::from_utf8_lossy(&bytes).to_string();
    let limit = lines.unwrap_or(200);
    let collected: Vec<&str> = raw.lines().collect();
    if collected.len() <= limit {
        Ok(raw)
    } else {
        Ok(collected[collected.len() - limit..].join("\n"))
    }
}

/// 全局部署子进程句柄，用于避免重复启动。
static DEPLOYMENT_CHILD: Mutex<Option<std::process::Child>> = Mutex::new(None);

fn deployment_child_is_running() -> Result<bool, String> {
    let mut guard = DEPLOYMENT_CHILD.lock().map_err(|err| err.to_string())?;
    let Some(child) = guard.as_mut() else {
        return Ok(false);
    };
    match child.try_wait().map_err(|err| err.to_string())? {
        Some(_) => {
            *guard = None;
            Ok(false)
        }
        None => Ok(true),
    }
}

/// 命令：启动本地一键部署。
///
/// 流程：
/// 1. 优先复用用户目录注册的项目或 launcher 同级项目。
/// 2. 若不存在可用项目，再探测网络环境，选择 Git 克隆 URL（国内使用 gh-proxy）。
/// 3. 调用系统 Git 克隆仓库。
/// 4. 克隆完成后运行平台对应的 start 脚本。
#[tauri::command]
async fn start_local_deployment(_app: AppHandle) -> Result<(), String> {
    // 幂等：如果已经有部署进程在跑，直接返回
    if deployment_child_is_running()? {
        return Ok(());
    }

    let user_dir = sparkarc_user_dir()?;
    let target_dir = user_dir.join("sparkarc-server");
    fs::create_dir_all(&user_dir).map_err(|err| err.to_string())?;
    let launcher_dir = launcher_dir()?;
    let log_path = deploy_log_path()?;

    // 清空旧日志
    let _ = fs::write(&log_path, "");

    let os = tauri_plugin_os::type_();
    let is_windows = matches!(os, tauri_plugin_os::OsType::Windows);

    // 写入启动日志
    let append_log = |msg: &str| {
        let line = format!(
            "{} {}\n",
            chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
            msg
        );
        let _ = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&log_path)
            .and_then(|mut f| std::io::Write::write_all(&mut f, line.as_bytes()));
    };

    append_log("开始本地部署...");

    if let Some(project_root) = valid_record_project_root()? {
        append_log(&format!(
            "检测到已注册的后端目录，尝试启动: {:?}",
            project_root
        ));
        return start_backend(&project_root, is_windows, &append_log).await;
    }

    if let Some(project_root) = find_sibling_backend() {
        append_log(&format!(
            "检测到启动器同级后端目录，尝试启动: {:?}",
            project_root
        ));
        return start_backend(&project_root, is_windows, &append_log).await;
    }

    // 先尝试 probe 脚本 / Python 获取网络镜像信息
    let probe_result = probe_network_for_git_url(&launcher_dir, &append_log).await?;
    let git_url = probe_result.git_url;
    append_log(&format!("使用 Git URL: {}", git_url));

    // 如果目标目录已存在，先尝试复用
    if target_dir.is_dir() {
        append_log("检测到已有后端目录，尝试直接启动...");
        return start_backend(&target_dir, is_windows, &append_log).await;
    }

    // 克隆仓库
    append_log(&format!("正在克隆仓库到 {:?} ...", target_dir));
    let clone_output = if is_windows {
        Command::new("powershell.exe")
            .args([
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                &format!(
                    "git clone --depth 1 --single-branch {} '{}'",
                    git_url,
                    target_dir.to_string_lossy()
                ),
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .map_err(|err| format!("Git 克隆失败: {}", err))?
    } else {
        Command::new("git")
            .args([
                "clone",
                "--depth",
                "1",
                "--single-branch",
                &git_url,
                &target_dir.to_string_lossy(),
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .map_err(|err| format!("Git 克隆失败: {}", err))?
    };

    let clone_stdout = String::from_utf8_lossy(&clone_output.stdout);
    let clone_stderr = String::from_utf8_lossy(&clone_output.stderr);
    for line in clone_stdout.lines() {
        append_log(line);
    }
    for line in clone_stderr.lines() {
        append_log(line);
    }

    if !clone_output.status.success() {
        return Err(format!("Git 克隆失败: {}", clone_stderr));
    }

    append_log("仓库克隆完成，准备启动后端...");

    // 写入服务记录
    let record = serde_json::json!({
        "projectRoot": target_dir,
        "installedAt": chrono::Utc::now().to_rfc3339(),
        "platform": std::env::consts::OS,
        "machine": std::env::consts::ARCH,
    });
    fs::write(
        service_record_path()?,
        serde_json::to_string_pretty(&record).unwrap(),
    )
    .map_err(|err| err.to_string())?;

    start_backend(&target_dir, is_windows, &append_log).await
}

#[derive(Debug, Clone)]
struct ProbeResult {
    git_url: String,
}

/// 通过 PowerShell 或 Python 探测网络环境，返回推荐 Git URL。
async fn probe_network_for_git_url<F>(launcher_dir: &Path, log: &F) -> Result<ProbeResult, String>
where
    F: Fn(&str),
{
    let repo_url = SPARKARC_REPO_URL;

    // Windows 优先用 PowerShell probe
    #[cfg(target_os = "windows")]
    {
        let probe_script = launcher_dir
            .join("..")
            .join("scripts")
            .join("network_probe.ps1");
        if probe_script.is_file() {
            let output = Command::new("powershell.exe")
                .args([
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    &probe_script.to_string_lossy(),
                ])
                .stdout(Stdio::piped())
                .stderr(Stdio::piped())
                .output()
                .map_err(|err| format!("网络探测失败: {}", err))?;
            let stdout = String::from_utf8_lossy(&output.stdout);
            if let Some(json_start) = stdout.find('{') {
                if let Ok(json) = serde_json::from_str::<serde_json::Value>(&stdout[json_start..]) {
                    if let Some(git_url) = json.get("git_clone").and_then(|v| v.as_str()) {
                        return Ok(ProbeResult {
                            git_url: git_url.to_string(),
                        });
                    }
                }
            }
        }
    }

    // 非 Windows 或 probe 失败时，尝试 Python probe
    let python_probe = launcher_dir
        .join("..")
        .join("server")
        .join("core")
        .join("network_probe.py");
    if python_probe.is_file() {
        let output = Command::new("python3")
            .arg(&python_probe)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .or_else(|_| {
                Command::new("python")
                    .arg(&python_probe)
                    .stdout(Stdio::piped())
                    .stderr(Stdio::piped())
                    .output()
            })
            .map_err(|err| format!("网络探测失败: {}", err))?;
        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Some(json_start) = stdout.find('{') {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&stdout[json_start..]) {
                if let Some(git_url) = json.get("git_clone").and_then(|v| v.as_str()) {
                    return Ok(ProbeResult {
                        git_url: git_url.to_string(),
                    });
                }
            }
        }
    }

    if let Some(country_code) = probe_country_code_without_repo_files() {
        log(&format!("内置网络探测国家/地区: {}", country_code));
        if country_code == "CN" {
            return Ok(ProbeResult {
                git_url: format!("https://gh-proxy.com/{}", repo_url),
            });
        }
    } else {
        log("内置网络探测失败，使用默认 GitHub 地址。");
    }

    Ok(ProbeResult {
        git_url: repo_url.to_string(),
    })
}

fn probe_country_code_without_repo_files() -> Option<String> {
    let providers = [
        "https://freeipapi.com/api/json/",
        "https://ipapi.co/json/",
        "https://ipwho.is/json/",
    ];

    for provider in providers {
        let Some(stdout) = fetch_geoip_json(provider) else {
            continue;
        };
        let Ok(json) = serde_json::from_str::<serde_json::Value>(&stdout) else {
            continue;
        };
        let country_code = json
            .get("countryCode")
            .or_else(|| json.get("country_code"))
            .or_else(|| json.get("country"))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .trim()
            .to_uppercase();
        if country_code.len() >= 2 {
            return Some(country_code);
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn fetch_geoip_json(url: &str) -> Option<String> {
    let script = format!(
        "(Invoke-WebRequest -Uri '{}' -TimeoutSec 3 -UseBasicParsing).Content",
        url.replace('\'', "''")
    );
    let output = Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            &script,
        ])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&output.stdout).to_string())
}

#[cfg(not(target_os = "windows"))]
fn fetch_geoip_json(url: &str) -> Option<String> {
    let output = Command::new("curl")
        .args(["-fsSL", "--max-time", "3", url])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8_lossy(&output.stdout).to_string())
}

/// 启动后端服务。
async fn start_backend<F>(project_root: &Path, is_windows: bool, log: &F) -> Result<(), String>
where
    F: Fn(&str),
{
    let script_path = if is_windows {
        project_root.join("start.bat")
    } else {
        project_root.join("start.sh")
    };

    if !script_path.is_file() {
        return Err(format!("启动脚本不存在: {:?}", script_path));
    }
    let log_path = deploy_log_path()?;

    let log_file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|err| err.to_string())?;
    let err_log_file = log_file.try_clone().map_err(|err| err.to_string())?;

    let child = if is_windows {
        Command::new("cmd.exe")
            .args(["/C", &format!("\"{}\"", script_path.to_string_lossy())])
            .current_dir(project_root)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log_file))
            .stderr(Stdio::from(err_log_file))
            .spawn()
            .map_err(|err| format!("启动后端失败: {}", err))?
    } else {
        Command::new("bash")
            .arg(&script_path)
            .current_dir(project_root)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log_file))
            .stderr(Stdio::from(err_log_file))
            .spawn()
            .map_err(|err| format!("启动后端失败: {}", err))?
    };

    {
        let mut guard = DEPLOYMENT_CHILD.lock().map_err(|err| err.to_string())?;
        *guard = Some(child);
    }

    log("后端启动命令已发出，正在等待服务就绪...");
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_launcher_theme_state,
            set_launcher_theme_state,
            check_local_backend_dir,
            read_deployment_log,
            start_local_deployment
        ])
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
