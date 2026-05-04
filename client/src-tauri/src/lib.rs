use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};
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

    serde_json::from_str(&raw).map(Some).map_err(|err| err.to_string())
}

#[tauri::command]
fn set_launcher_theme_state(app: AppHandle, state: LauncherThemeState) -> Result<(), String> {
    let path = launcher_theme_state_path(&app)?;
    let raw = serde_json::to_string_pretty(&state).map_err(|err| err.to_string())?;
    fs::write(path, raw).map_err(|err| err.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_launcher_theme_state,
            set_launcher_theme_state
        ])
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_os::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
