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

// ---------------------------------------------------------------- PR mailbox
// Reads the player's GitHub notifications through the gh CLI (its own login, nothing stored here).
// Only runs when the player turned it on with `/pet pr on`.

fn find_gh() -> Option<PathBuf> {
    // apps started from Finder/login don't get the shell's PATH, so look where gh is usually installed
    for p in ["/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh"] {
        let path = PathBuf::from(p);
        if path.exists() {
            return Some(path);
        }
    }
    std::env::var_os("PATH")
        .and_then(|paths| std::env::split_paths(&paths).map(|d| d.join("gh")).find(|p| p.exists()))
}

fn gh(args: &[&str]) -> Result<String, String> {
    let bin = find_gh().ok_or_else(|| "gh 가 없어요. brew install gh 후 gh auth login 을 해 주세요".to_string())?;
    let out = Command::new(bin)
        .args(args)
        .env("GH_PROMPT_DISABLED", "1")
        .output()
        .map_err(|e| format!("gh 실행 실패: {e}"))?;
    if !out.status.success() {
        let err = String::from_utf8_lossy(&out.stderr);
        let first = err.lines().next().unwrap_or("").trim().to_string();
        return Err(if first.contains("auth login") || first.contains("not logged") {
            "GitHub 로그인이 필요해요: 터미널에서 gh auth login".to_string()
        } else {
            format!("GitHub 알림을 읽지 못했어요: {first}")
        });
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn pr_item(n: &serde_json::Value) -> Option<serde_json::Value> {
    let reason = n["reason"].as_str()?;
    let subject = &n["subject"];
    let kind = subject["type"].as_str()?;
    let title = subject["title"].as_str().unwrap_or("");
    let repo = n["repository"]["full_name"].as_str()?;
    let category = match (kind, reason) {
        ("PullRequest", "review_requested") => "review",
        ("PullRequest", "author" | "comment" | "state_change" | "assign") => "mine",
        ("PullRequest", "mention" | "team_mention") => "mention",
        ("CheckSuite", "ci_activity") if title.contains("failed") => "ci",
        _ => return None,
    };
    let api = subject["url"].as_str().unwrap_or("");
    let url = match api.strip_prefix("https://api.github.com/repos/") {
        Some(rest) => format!("https://github.com/{}", rest.replacen("/pulls/", "/pull/", 1)),
        None => format!("https://github.com/{repo}/actions"),
    };
    let number = api
        .rsplit('/')
        .next()
        .filter(|t| !t.is_empty() && t.chars().all(|c| c.is_ascii_digit()))
        .map(|t| t.to_string());
    Some(serde_json::json!({
        "id": n["id"], "category": category, "repo": repo, "title": title,
        "url": url, "number": number, "updated_at": n["updated_at"],
    }))
}

#[tauri::command]
async fn pr_inbox() -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let text = gh(&["api", "notifications?per_page=50"])?;
        let list: Vec<serde_json::Value> = serde_json::from_str(&text).map_err(|e| e.to_string())?;
        let items: Vec<serde_json::Value> = list.iter().filter_map(pr_item).collect();
        Ok(serde_json::json!({ "items": items }))
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
async fn pr_mark_read(id: String) -> Result<(), String> {
    if id.is_empty() || !id.chars().all(|c| c.is_ascii_digit()) {
        return Err("잘못된 알림 id".into());
    }
    tauri::async_runtime::spawn_blocking(move || {
        gh(&["api", "-X", "PATCH", &format!("notifications/threads/{id}")]).map(|_| ())
    })
    .await
    .map_err(|e| e.to_string())?
}

/// Open a GitHub page in the default browser (only github.com links).
#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if !url.starts_with("https://github.com/") {
        return Err("github.com 주소만 열 수 있어요".into());
    }
    Command::new("open").arg(&url).spawn().map(|_| ()).map_err(|e| e.to_string())
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
        .invoke_handler(tauri::generate_handler![read_state, pet, notify, pr_inbox, pr_mark_read, open_url])
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
