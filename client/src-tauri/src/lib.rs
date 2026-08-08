use serde::{Deserialize, Serialize};
#[cfg(windows)]
use std::os::windows::process::CommandExt;
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::Mutex,
};
use tauri::{AppHandle, Manager};

mod deployment;
mod project_config;

use deployment::{DeploymentManager, DeploymentStatus, LauncherReleaseStatus};

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

/// 部署日志文件路径：~/.sparkarc/deploy.log
fn deploy_log_path() -> Result<PathBuf, String> {
    Ok(sparkarc_user_dir()?.join("deploy.log"))
}

fn managed_backend_is_ready(project_root: Option<&Path>, is_windows: bool) -> bool {
    project_root.is_some_and(|root| {
        let server_root = root.join("server");
        let python_root = server_root.join(".runtime").join("python");
        let start_script = if is_windows {
            root.join("start.bat")
        } else {
            root.join("start.sh")
        };
        let python_executable = if is_windows {
            python_root.join("python.exe")
        } else {
            python_root.join("bin").join("python3")
        };

        server_root.join("app.py").is_file()
            && start_script.is_file()
            && python_executable.is_file()
            && python_root.join(".deploy_complete").is_file()
            && root
                .join("client")
                .join("dist")
                .join("index.html")
                .is_file()
            && root
                .join("client")
                .join(".frontend_build_complete")
                .is_file()
    })
}

/// 命令：检查 APP 数据目录中的本地后端是否已完成最小可运行部署。
#[tauri::command]
fn check_local_backend_ready() -> Result<bool, String> {
    if is_mobile_runtime() {
        return Ok(false);
    }

    let project_root = DeploymentManager::new()?.managed_project_root()?;
    let is_windows = matches!(tauri_plugin_os::type_(), tauri_plugin_os::OsType::Windows);
    Ok(managed_backend_is_ready(
        project_root.as_deref(),
        is_windows,
    ))
}

/// 命令：读取部署日志的最后 N 行。
#[tauri::command]
fn read_deployment_log(lines: Option<usize>) -> Result<String, String> {
    if is_mobile_runtime() {
        return Ok(String::new());
    }

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

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn is_mobile_runtime() -> bool {
    cfg!(mobile)
        || matches!(
            tauri_plugin_os::type_(),
            tauri_plugin_os::OsType::Android | tauri_plugin_os::OsType::IOS
        )
}

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

/// 命令：启动本地服务。
///
/// Launcher 始终启动用户目录下自己管理的 `main` 工作树，不读取手动源码目录。
#[tauri::command]
async fn start_local_deployment(_app: AppHandle) -> Result<(), String> {
    if is_mobile_runtime() {
        return Err("移动端不支持本地部署后端，请填写远程或局域网后端地址。".to_string());
    }

    // 幂等：如果已经有部署进程在跑，直接返回
    if deployment_child_is_running()? {
        return Ok(());
    }

    let manager = DeploymentManager::new()?;

    let os = tauri_plugin_os::type_();
    let is_windows = matches!(os, tauri_plugin_os::OsType::Windows);
    let append_log = |msg: &str| manager.append_log(msg);

    append_log("开始本地部署...");

    let install_manager = manager.clone();
    let project_root =
        tauri::async_runtime::spawn_blocking(move || install_manager.ensure_managed_checkout())
            .await
            .map_err(|err| format!("本地源码部署任务异常结束: {err}"))??;
    let node_manager = manager.clone();
    let node_bin_dir =
        tauri::async_runtime::spawn_blocking(move || node_manager.ensure_node_runtime())
            .await
            .map_err(|err| format!("Launcher 内置 Node.js 准备任务异常结束: {err}"))??;
    append_log(&format!(
        "APP 数据目录中的 main 源码已就绪，尝试启动: {:?}",
        project_root
    ));
    start_backend(
        &project_root,
        is_windows,
        Some(&node_bin_dir),
        true,
        &append_log,
    )
    .await
}

/// 返回 APP 数据目录中 main 工作树的持久状态，不会执行网络请求。
#[tauri::command]
fn get_deployment_status() -> Result<DeploymentStatus, String> {
    if is_mobile_runtime() {
        return Ok(DeploymentStatus::default());
    }
    Ok(DeploymentManager::new()?.read_status())
}

/// 静默检查 main 是否有新提交。该命令只 fetch，不会改写当前工作树。
#[tauri::command]
async fn check_local_update() -> Result<DeploymentStatus, String> {
    if is_mobile_runtime() {
        return Err("移动端不支持本地服务更新。".to_string());
    }
    let manager = DeploymentManager::new()?;
    tauri::async_runtime::spawn_blocking(move || manager.check_main_update())
        .await
        .map_err(|err| format!("更新检查任务异常结束: {err}"))?
}

/// 显式应用 main 更新。运行中的服务必须先停止，避免进程内外代码混合。
#[tauri::command]
async fn apply_local_update() -> Result<DeploymentStatus, String> {
    if is_mobile_runtime() {
        return Err("移动端不支持本地服务更新。".to_string());
    }
    if deployment_child_is_running()? {
        return Err("本地服务仍在运行。请返回 Launcher 并停止当前服务后再应用更新。".to_string());
    }
    let manager = DeploymentManager::new()?;
    manager.ensure_managed_service_stopped()?;
    tauri::async_runtime::spawn_blocking(move || manager.apply_main_update())
        .await
        .map_err(|err| format!("应用更新任务异常结束: {err}"))?
}

/// 显式停止 Launcher 自己启动并登记的本地后端，为更新切换留出无进程占用的窗口。
#[tauri::command]
async fn stop_managed_local_backend() -> Result<(), String> {
    if is_mobile_runtime() {
        return Err("移动端不支持本地服务更新。".to_string());
    }
    let manager = DeploymentManager::new()?;
    tauri::async_runtime::spawn_blocking(move || manager.stop_managed_service())
        .await
        .map_err(|err| format!("停止本地服务任务异常结束: {err}"))??;
    let mut guard = DEPLOYMENT_CHILD.lock().map_err(|err| err.to_string())?;
    if let Some(mut child) = guard.take() {
        let _ = child.wait();
    }
    Ok(())
}

/// 直接查询 GitHub Releases API，首期仅用于提示 Launcher 壳更新。
#[tauri::command]
async fn check_launcher_update(app: AppHandle) -> Result<LauncherReleaseStatus, String> {
    let manager = DeploymentManager::new()?;
    let current_version = app.package_info().version.to_string();
    tauri::async_runtime::spawn_blocking(move || {
        Ok::<LauncherReleaseStatus, String>(manager.check_launcher_release(&current_version))
    })
    .await
    .map_err(|err| format!("Launcher Release 检查任务异常结束: {err}"))?
}

/// 下载并启动当前平台对应的 Launcher 安装资产，成功后退出当前 Launcher。
#[tauri::command]
async fn apply_launcher_update(app: AppHandle) -> Result<(), String> {
    if is_mobile_runtime() {
        return Err("移动端不支持 Launcher 自动更新。".to_string());
    }
    let manager = DeploymentManager::new()?;
    let current_version = app.package_info().version.to_string();
    tauri::async_runtime::spawn_blocking(move || {
        manager.download_and_launch_launcher_update(&current_version)
    })
    .await
    .map_err(|err| format!("Launcher 更新任务异常结束: {err}"))??;
    app.exit(0);
    Ok(())
}

/// 启动后端服务。
async fn start_backend<F>(
    project_root: &Path,
    is_windows: bool,
    managed_node_bin_dir: Option<&Path>,
    managed_process: bool,
    log: &F,
) -> Result<(), String>
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

    let mut command = if is_windows {
        let mut command = Command::new("cmd.exe");
        // CMD 不遵循 C 运行时的引号转义；原样传入可保留路径中的空格和 `&`。
        command.args(["/D", "/S", "/C"]);
        #[cfg(windows)]
        {
            command.raw_arg(format!(r#"call "{}""#, script_path.to_string_lossy()));
            command.creation_flags(CREATE_NO_WINDOW);
        }
        #[cfg(not(windows))]
        command.arg(format!(r#"call "{}""#, script_path.to_string_lossy()));
        command
    } else {
        let mut command = Command::new("bash");
        command.arg(&script_path);
        command
    };
    command
        .current_dir(project_root)
        .stdin(Stdio::null())
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(err_log_file));
    if let Some(node_bin_dir) = managed_node_bin_dir {
        prepend_command_path(&mut command, node_bin_dir)?;
    }
    let mut child = command
        .spawn()
        .map_err(|err| format!("启动后端失败: {}", err))?;

    if managed_process {
        let manager = DeploymentManager::new()?;
        if let Err(err) = manager.record_managed_service_process(child.id()) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!(
                "无法登记 Launcher 本地后端进程，已终止本次启动: {err}"
            ));
        }
    }

    {
        let mut guard = DEPLOYMENT_CHILD.lock().map_err(|err| err.to_string())?;
        *guard = Some(child);
    }

    log("后端启动命令已发出，正在等待服务就绪...");
    Ok(())
}

fn prepend_command_path(command: &mut Command, directory: &Path) -> Result<(), String> {
    let mut paths = vec![directory.to_path_buf()];
    if let Some(existing) = std::env::var_os("PATH") {
        paths.extend(std::env::split_paths(&existing));
    }
    let joined = std::env::join_paths(paths)
        .map_err(|err| format!("无法为 Launcher 内置 Node.js 设置 PATH: {err}"))?;
    command.env("PATH", joined);
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Libgit2 超时是进程级设置，必须早于 Tauri 运行时创建。
    unsafe {
        deployment::configure_git_network_timeouts().expect("无法初始化 Launcher 的 Git 网络超时");
    }
    let builder = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_launcher_theme_state,
            set_launcher_theme_state,
            check_local_backend_ready,
            read_deployment_log,
            start_local_deployment,
            get_deployment_status,
            check_local_update,
            apply_local_update,
            stop_managed_local_backend,
            check_launcher_update,
            apply_launcher_update
        ])
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_os::init());

    #[cfg(not(mobile))]
    let builder = builder.plugin(tauri_plugin_fs::init());

    builder
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod launcher_window_tests {
    use super::managed_backend_is_ready;
    use std::fs;
    use std::path::{Path, PathBuf};

    fn test_root(label: &str) -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join(".tmp")
            .join("tests")
            .join("launcher_backend_ready")
            .join(format!(
                "{}-{}-{}",
                label,
                std::process::id(),
                chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
            ))
    }

    fn write_file(path: &Path) {
        fs::create_dir_all(path.parent().expect("测试文件必须有父目录")).expect("应能创建测试目录");
        fs::write(path, b"test").expect("应能创建测试文件");
    }

    #[test]
    fn managed_backend_requires_complete_windows_deployment() {
        let root = test_root("windows");

        write_file(&root.join("server").join("app.py"));
        write_file(&root.join("start.bat"));
        assert!(!managed_backend_is_ready(Some(&root), true));

        write_file(
            &root
                .join("server")
                .join(".runtime")
                .join("python")
                .join("python.exe"),
        );
        write_file(
            &root
                .join("server")
                .join(".runtime")
                .join("python")
                .join(".deploy_complete"),
        );
        assert!(!managed_backend_is_ready(Some(&root), true));

        write_file(&root.join("client").join("dist").join("index.html"));
        write_file(&root.join("client").join(".frontend_build_complete"));
        assert!(managed_backend_is_ready(Some(&root), true));
        assert!(!managed_backend_is_ready(None, true));

        fs::remove_dir_all(root).expect("应能清理临时服务目录");
    }

    #[test]
    fn managed_backend_checks_unix_runtime_layout() {
        let root = test_root("unix");
        for path in [
            root.join("server").join("app.py"),
            root.join("start.sh"),
            root.join("server")
                .join(".runtime")
                .join("python")
                .join("bin")
                .join("python3"),
            root.join("server")
                .join(".runtime")
                .join("python")
                .join(".deploy_complete"),
            root.join("client").join("dist").join("index.html"),
            root.join("client").join(".frontend_build_complete"),
        ] {
            write_file(&path);
        }

        assert!(managed_backend_is_ready(Some(&root), false));
        assert!(!managed_backend_is_ready(Some(&root), true));
        fs::remove_dir_all(root).expect("应能清理临时服务目录");
    }
}
