//! Token Pet widget: read-only view of ~/.claude/pet/state.json.
//! The plugin's petlib is the only writer; feeding shells out to `pet.py feed --json`.

use notify::{RecursiveMode, Watcher};
use std::path::PathBuf;
use std::process::Command;
use std::sync::mpsc;
use std::time::Duration;
use tauri::{Emitter, Manager};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
use tauri_plugin_notification::NotificationExt;

fn pet_home() -> PathBuf {
    if let Ok(p) = std::env::var("PET_HOME") {
        return PathBuf::from(p);
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    PathBuf::from(home).join(".claude").join("pet")
}

fn read_state_file() -> Result<serde_json::Value, String> {
    let path = pet_home().join("state.json");
    let text = std::fs::read_to_string(&path)
        .map_err(|_| "아직 펫이 없어요. Claude Code 세션을 한 번 시작해 주세요".to_string())?;
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

#[tauri::command]
fn read_state() -> Result<serde_json::Value, String> {
    read_state_file()
}

/// Run the plugin's pet.py with `args` and return its --json payload.
#[tauri::command]
fn pet(args: Vec<String>) -> Result<serde_json::Value, String> {
    let state = read_state_file()?;
    let root = state
        .get("plugin_root")
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .ok_or_else(|| "플러그인 위치를 몰라요. Claude Code 세션을 한 번 시작해 주세요".to_string())?;
    let script = PathBuf::from(root).join("scripts").join("pet.py");
    let output = Command::new("python3")
        .arg(&script)
        .args(&args)
        .arg("--json")
        .env("PET_HOME", pet_home())
        .output()
        .map_err(|e| format!("python3 실행 실패: {e}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    serde_json::from_str(stdout.trim()).map_err(|_| {
        let err = String::from_utf8_lossy(&output.stderr);
        format!("pet.py 응답을 읽지 못했어요: {}", if err.is_empty() { stdout.to_string() } else { err.to_string() })
    })
}

/// macOS notification from the widget (hungry pet, runaway warning).
#[tauri::command]
fn notify(app: tauri::AppHandle, title: String, body: String) -> Result<(), String> {
    app.notification().builder().title(title).body(body).show().map_err(|e| e.to_string())
}

/// Launch at login follows `settings.widget` in state.json (`/pet widget on|off`), on by default.
/// Dev builds skip it so `tauri dev` never registers a debug binary as a login item.
fn sync_autostart(app: &tauri::AppHandle, state: Option<&serde_json::Value>) {
    if cfg!(debug_assertions) {
        return;
    }
    let want = state
        .and_then(|s| s.pointer("/settings/widget"))
        .and_then(|v| v.as_bool())
        .unwrap_or(true);
    let al = app.autolaunch();
    if al.is_enabled().unwrap_or(false) != want {
        let res = if want { al.enable() } else { al.disable() };
        if let Err(e) = res {
            eprintln!("autostart sync failed: {e}");
        }
    }
}

fn watch_state(app: tauri::AppHandle) {
    let (tx, rx) = mpsc::channel();
    let mut watcher = match notify::recommended_watcher(move |res| {
        let _ = tx.send(res);
    }) {
        Ok(w) => w,
        Err(e) => {
            eprintln!("watcher init failed: {e}");
            return;
        }
    };
    let home = pet_home();
    let _ = std::fs::create_dir_all(&home);
    if let Err(e) = watcher.watch(&home, RecursiveMode::NonRecursive) {
        eprintln!("watch failed: {e}");
        return;
    }
    // state.json is replaced via rename, so watch the directory and debounce bursts.
    while rx.recv().is_ok() {
        while rx.recv_timeout(Duration::from_millis(200)).is_ok() {}
        if let Ok(v) = read_state_file() {
            sync_autostart(&app, Some(&v));
            let _ = app.emit("state", v);
        }
    }
}

fn place_bottom_right(win: &tauri::WebviewWindow) {
    if let Ok(Some(mon)) = win.primary_monitor() {
        let size = mon.size();
        let sf = mon.scale_factor();
        let x = size.width as f64 / sf - 120.0 - 24.0;
        let y = size.height as f64 / sf - 120.0 - 60.0;
        let _ = win.set_position(tauri::LogicalPosition::new(x, y));
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
        .invoke_handler(tauri::generate_handler![read_state, pet, notify])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            if let Some(win) = app.get_webview_window("main") {
                place_bottom_right(&win);
            }
            sync_autostart(app.handle(), read_state_file().ok().as_ref());
            let handle = app.handle().clone();
            std::thread::spawn(move || watch_state(handle));
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Token Pet");
}
