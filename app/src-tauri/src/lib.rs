//! Token Pet widget: read-only view of ~/.claude/pet/state.json.
//! The plugin's petlib is the only writer; feeding shells out to `pet.py feed --json`.

use notify::{RecursiveMode, Watcher};
use std::path::PathBuf;
use std::process::Command;
use std::sync::mpsc;
use std::time::Duration;
use tauri::image::Image;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

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
// Asks GitHub, through the gh CLI (its own login, nothing stored here), for the PRs matching the search
// conditions the player typed into the widget. Only runs when the player turned it on with `/pet pr on`.

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
            format!("GitHub 검색을 못 했어요: {first}")
        });
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}

fn pr_item(n: &serde_json::Value) -> Option<serde_json::Value> {
    let repo = n["repository_url"].as_str()?.strip_prefix("https://api.github.com/repos/")?;
    Some(serde_json::json!({
        "id": n["id"], "repo": repo,
        "title": n["title"].as_str().unwrap_or(""), "url": n["html_url"],
        "number": n["number"].as_u64().map(|v| v.to_string()), "updated_at": n["updated_at"],
        "draft": n["draft"].as_bool().unwrap_or(false),
    }))
}

fn search_prs(query: &str) -> Result<Vec<serde_json::Value>, String> {
    // for demos and tests: PET_PR_FAKE=<file> answers every query with a saved search result instead of GitHub
    let text = match std::env::var("PET_PR_FAKE") {
        Ok(path) => std::fs::read_to_string(path).map_err(|e| e.to_string())?,
        Err(_) => {
            let q = format!("q={query}");
            gh(&["api", "-X", "GET", "search/issues", "-f", &q, "-f", "per_page=50"])?
        }
    };
    let res: serde_json::Value = serde_json::from_str(&text).map_err(|e| e.to_string())?;
    Ok(res["items"].as_array().map(|a| a.iter().filter_map(pr_item).collect()).unwrap_or_default())
}

/// One GitHub search per condition the player added (`is:pr org:*** is:open`, ...), each with its
/// own result or error, so one bad condition doesn't hide the others. At most 50 PRs per condition.
#[tauri::command]
async fn pr_inbox(queries: Vec<String>) -> Result<serde_json::Value, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let results: Vec<serde_json::Value> = queries
            .iter()
            .map(|q| match search_prs(q) {
                Ok(items) => serde_json::json!({ "query": q, "items": items }),
                Err(e) => serde_json::json!({ "query": q, "items": [], "error": e }),
            })
            .collect();
        Ok(serde_json::json!({ "results": results }))
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

// ---------------------------------------------------------------- menu bar
// A pink mochi in the menu bar: who the pet is, hide/show the pet on screen, reload the widget,
// check for updates (`/pet update`), quit. The hidden choice is kept across launches.

struct Tray {
    title: MenuItem<tauri::Wry>,
    detail: MenuItem<tauri::Wry>,
    toggle: MenuItem<tauri::Wry>,
}

fn tray_file(app: &tauri::AppHandle) -> Option<PathBuf> {
    app.path().app_config_dir().ok().map(|d| d.join("tray.json"))
}

fn pet_hidden(app: &tauri::AppHandle) -> bool {
    tray_file(app)
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|t| serde_json::from_str::<serde_json::Value>(&t).ok())
        .and_then(|v| v["hidden"].as_bool())
        .unwrap_or(false)
}

fn set_pet_hidden(app: &tauri::AppHandle, hidden: bool) {
    if let Some(win) = app.get_webview_window("main") {
        let _ = if hidden { win.hide() } else { win.show() };
    }
    if let Some(tray) = app.try_state::<Tray>() {
        let _ = tray.toggle.set_text(if hidden { "캐릭터 보이기" } else { "캐릭터 숨기기" });
    }
    if let Some(path) = tray_file(app) {
        if let Some(dir) = path.parent() {
            let _ = std::fs::create_dir_all(dir);
        }
        let _ = std::fs::write(path, serde_json::json!({ "hidden": hidden }).to_string());
    }
}

/// The widget page keeps the two info lines current (live hunger, unread PRs).
#[tauri::command]
fn tray_status(app: tauri::AppHandle, title: String, detail: String) {
    if let Some(tray) = app.try_state::<Tray>() {
        let _ = tray.title.set_text(title);
        let _ = tray.detail.set_text(detail);
    }
}

/// `/pet update` answers in two full lines; the pet's bubble has room for a few words.
fn short_update_text(full: &str) -> String {
    let mut parts = Vec::new();
    for line in full.lines() {
        let plugin = line.starts_with("플러그인");
        if line.contains("이미 최신") {
            continue;
        } else if line.contains("못") || line.contains("없어요") {
            parts.push(if plugin { "플러그인 업데이트 실패" } else { "위젯 업데이트 실패" });
        } else if plugin {
            parts.push("플러그인 새 버전 받았어요");
        } else {
            parts.push("위젯 새 버전으로 바꿨어요");
        }
    }
    if parts.is_empty() { "이미 최신이에요!".into() } else { parts.join(" · ") }
}

fn check_updates(app: tauri::AppHandle) {
    let _ = app.emit("tray-say", "업데이트를 확인하고 있어요…");
    std::thread::spawn(move || {
        // the same as `/pet update`; a newer widget quits this one and starts itself
        let text = match pet(vec!["update".into()]) {
            Ok(v) => short_update_text(v["text"].as_str().unwrap_or("")),
            Err(_) => "업데이트를 확인하지 못했어요".into(),
        };
        let _ = app.emit("tray-say", text);
    });
}

fn build_tray(app: &tauri::App) -> tauri::Result<()> {
    let title = MenuItem::with_id(app, "title", "토큰 펫", false, None::<&str>)?;
    let detail = MenuItem::with_id(app, "detail", "", false, None::<&str>)?;
    let hidden = pet_hidden(app.handle());
    let toggle = MenuItem::with_id(app, "toggle", if hidden { "캐릭터 보이기" } else { "캐릭터 숨기기" }, true, None::<&str>)?;
    let reload = MenuItem::with_id(app, "reload", "위젯 다시 불러오기", true, None::<&str>)?;
    let update = MenuItem::with_id(app, "update", "업데이트 확인…", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "토큰 펫 종료", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[
        &title, &detail,
        &PredefinedMenuItem::separator(app)?,
        &toggle,
        &PredefinedMenuItem::separator(app)?,
        &reload, &update,
        &PredefinedMenuItem::separator(app)?,
        &quit,
    ])?;
    TrayIconBuilder::with_id("main")
        .icon(Image::from_bytes(include_bytes!("../icons/tray.png"))?)
        .icon_as_template(false)
        .tooltip("토큰 펫")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "toggle" => {
                let visible = app.get_webview_window("main").and_then(|w| w.is_visible().ok()).unwrap_or(true);
                set_pet_hidden(app, visible);
            }
            "reload" => {
                if let Some(win) = app.get_webview_window("main") {
                    let _ = win.eval("location.reload()");
                }
            }
            "update" => check_updates(app.clone()),
            "quit" => app.exit(0),
            _ => {}
        })
        .build(app)?;
    app.manage(Tray { title, detail, toggle });
    if hidden {
        set_pet_hidden(app.handle(), true);
    }
    Ok(())
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
        .plugin(tauri_plugin_autostart::init(MacosLauncher::LaunchAgent, None))
        .invoke_handler(tauri::generate_handler![read_state, pet, pr_inbox, open_url, tray_status])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);
            if let Some(win) = app.get_webview_window("main") {
                place_bottom_right(&win);
            }
            sync_autostart(app.handle(), read_state_file().ok().as_ref());
            if let Err(e) = build_tray(app) {
                eprintln!("menu bar icon failed: {e}");
            }
            let handle = app.handle().clone();
            std::thread::spawn(move || watch_state(handle));
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Token Pet");
}
