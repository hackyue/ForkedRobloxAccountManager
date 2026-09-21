#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use tauri::{CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

struct BackendProcess(Mutex<Option<Child>>);
struct AuthToken(Mutex<String>);
struct BackendStartStatus(Mutex<BackendStatus>);
struct HttpClient(reqwest::Client);

#[derive(Clone, serde::Serialize)]
struct BackendStatus {
    started: bool,
    reason: String,
}

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn is_backend_running() -> bool {
    TcpStream::connect_timeout(
        &"127.0.0.1:5050".parse().unwrap(),
        Duration::from_millis(500),
    )
    .is_ok()
}

fn is_valid_backend_exe(path: &Path) -> bool {
    if let Ok(meta) = fs::metadata(path) {
        meta.is_file() && meta.len() > 1_000_000
    } else {
        false
    }
}

fn find_python_executable(base_dirs: &[PathBuf]) -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    for dir in base_dirs {
        let venv_py = dir.join(".venv").join("Scripts").join("python.exe");
        if venv_py.exists() {
            candidates.push(venv_py);
        }
        let venv_py2 = dir.join("venv").join("Scripts").join("python.exe");
        if venv_py2.exists() {
            candidates.push(venv_py2);
        }
    }

    let exe_names = ["python.exe", "python3.exe", "py.exe", "pythonw.exe"];

    for dir in base_dirs {
        for name in &exe_names {
            let path = dir.join(name);
            if path.exists() && !candidates.contains(&path) {
                candidates.push(path);
            }
        }
    }

    if let Ok(path_var) = std::env::var("PATH") {
        for dir in std::env::split_paths(&path_var) {
            for name in &exe_names {
                let path = dir.join(name);
                if path.exists() && !candidates.contains(&path) {
                    candidates.push(path);
                }
            }
        }
    }

    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        let py_dir = PathBuf::from(&local_app_data).join("Programs").join("Python");
        if let Ok(entries) = fs::read_dir(&py_dir) {
            for entry in entries.flatten() {
                let py_exe = entry.path().join("python.exe");
                if py_exe.exists() && !candidates.contains(&py_exe) {
                    candidates.push(py_exe);
                }
            }
        }
        let win_app_py = PathBuf::from(&local_app_data).join("Microsoft").join("WindowsApps").join("python.exe");
        if let Ok(meta) = fs::metadata(&win_app_py) {
            if meta.len() > 100_000 && !candidates.contains(&win_app_py) {
                candidates.push(win_app_py);
            }
        }
    }

    candidates.push(PathBuf::from("python"));
    candidates.push(PathBuf::from("py"));
    candidates.push(PathBuf::from("python3"));

    candidates
}

fn find_backend_executable(search_dirs: &[PathBuf]) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    let exe_names = ["backend.exe", "FRAMBackend.exe", "fram_backend.exe"];

    for dir in search_dirs {
        for name in &exe_names {
            let path = dir.join(name);
            if is_valid_backend_exe(&path) {
                candidates.push(path);
            }
        }

        let res_dir = dir.join("resources");
        for name in &exe_names {
            let path = res_dir.join(name);
            if is_valid_backend_exe(&path) {
                candidates.push(path);
            }
        }
    }

    candidates
}

fn get_root_app_dir() -> PathBuf {
    if let Ok(local_appdata) = std::env::var("LOCALAPPDATA").or_else(|_| std::env::var("APPDATA")) {
        let app_dir = PathBuf::from(local_appdata).join("Forked Account Manager");
        let _ = fs::create_dir_all(app_dir.join("data"));
        let _ = fs::create_dir_all(app_dir.join("logs"));
        let _ = fs::create_dir_all(app_dir.join("cache"));
        let _ = fs::create_dir_all(app_dir.join("extensions"));
        return app_dir;
    }

    let exe_path = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("."));
    let exe_dir = exe_path.parent().unwrap_or_else(|| Path::new("."));
    let target_dir = exe_dir.join("Forked Account Manager");
    let _ = fs::create_dir_all(target_dir.join("data"));
    let _ = fs::create_dir_all(target_dir.join("logs"));
    let _ = fs::create_dir_all(target_dir.join("cache"));
    let _ = fs::create_dir_all(target_dir.join("extensions"));
    target_dir
}

fn start_backend_if_needed(app_dir: &Path) -> (Option<Child>, BackendStatus) {
    if is_backend_running() {
        return (None, BackendStatus { started: true, reason: "Backend already running".to_string() });
    }

    let exe_path = std::env::current_exe().unwrap_or_else(|_| PathBuf::from("."));
    let exe_dir = exe_path.parent().unwrap_or_else(|| Path::new("."));
    let cur_dir = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

    let log_path = app_dir.join("logs").join("backend.log");
    let err_log_path = app_dir.join("logs").join("backend_err.log");

    let exe_search_dirs = vec![
        exe_dir.to_path_buf(),
        cur_dir.to_path_buf(),
        exe_dir.join("resources"),
        cur_dir.join("resources"),
        exe_dir.join("resources").join("bin"),
        cur_dir.join("src-tauri").join("resources"),
    ];

    let backend_exe_candidates = find_backend_executable(&exe_search_dirs);
    for be_exe in &backend_exe_candidates {
        if is_valid_backend_exe(be_exe) {
            let mut cmd = Command::new(be_exe);
            cmd.env("FRAM_APP_DIR", app_dir.to_str().unwrap_or_default());

            if let Ok(out_f) = fs::File::create(&log_path) {
                cmd.stdout(Stdio::from(out_f));
            }
            if let Ok(err_f) = fs::File::create(&err_log_path) {
                cmd.stderr(Stdio::from(err_f));
            }

            #[cfg(target_os = "windows")]
            cmd.creation_flags(CREATE_NO_WINDOW);

            match cmd.spawn() {
                Ok(child) => {
                    for _ in 0..60 {
                        std::thread::sleep(Duration::from_millis(50));
                        if is_backend_running() {
                            return (Some(child), BackendStatus { started: true, reason: "Backend started successfully (standalone)".to_string() });
                        }
                    }
                    return (Some(child), BackendStatus { started: true, reason: "Backend process spawned but health check timed out".to_string() });
                }
                Err(_) => continue,
            }
        }
    }

    let possible_paths = [
        exe_dir.join("backend").join("app.py"),
        exe_dir.join("resources").join("backend").join("app.py"),
        exe_dir.join("_up_").join("backend").join("app.py"),
        cur_dir.join("backend").join("app.py"),
        PathBuf::from("backend/app.py"),
    ];

    let mut script_path: Option<PathBuf> = None;
    for path in &possible_paths {
        if path.exists() {
            script_path = Some(path.clone());
            break;
        }
    }

    let target_script = match script_path {
        Some(p) => p,
        None => {
            let _ = fs::write(&log_path, "Error: Could not locate backend.exe or backend/app.py in application resources.");
            return (None, BackendStatus { started: false, reason: "Could not locate backend.exe or backend/app.py in application resources.".to_string() });
        }
    };

    let script_parent = target_script.parent().unwrap_or_else(|| Path::new("."));
    let base_dirs = vec![exe_dir.to_path_buf(), cur_dir.to_path_buf(), script_parent.to_path_buf()];
    let python_candidates = find_python_executable(&base_dirs);

    for py_exe in &python_candidates {
        let mut cmd = Command::new(py_exe);
        cmd.arg(&target_script);
        cmd.current_dir(script_parent);
        cmd.env("FRAM_APP_DIR", app_dir.to_str().unwrap_or_default());

        if let Ok(out_f) = fs::File::create(&log_path) {
            cmd.stdout(Stdio::from(out_f));
        }
        if let Ok(err_f) = fs::File::create(&err_log_path) {
            cmd.stderr(Stdio::from(err_f));
        }

        #[cfg(target_os = "windows")]
        cmd.creation_flags(CREATE_NO_WINDOW);

        match cmd.spawn() {
            Ok(child) => {
                for _ in 0..60 {
                    std::thread::sleep(Duration::from_millis(50));
                    if is_backend_running() {
                        return (Some(child), BackendStatus { started: true, reason: "Backend started successfully".to_string() });
                    }
                }
                return (Some(child), BackendStatus { started: true, reason: "Backend process spawned but health check timed out".to_string() });
            }
            Err(_) => continue,
        }
    }

    let _ = fs::write(&log_path, "Error: Could not find backend.exe or Python executable on host system.");
    (None, BackendStatus { started: false, reason: "Python is not installed. Please install Python 3.8+ from python.org and ensure it is added to your system PATH.".to_string() })
}

#[tauri::command]
fn minimize_window(window: tauri::Window) -> Result<(), String> {
    window.minimize().map_err(|e| e.to_string())
}

#[tauri::command]
fn maximize_window(window: tauri::Window) -> Result<(), String> {
    let is_max = window.is_maximized().map_err(|e| e.to_string())?;
    if is_max {
        window.unmaximize().map_err(|e| e.to_string())
    } else {
        window.maximize().map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn close_window(window: tauri::Window) -> Result<(), String> {
    window.close().map_err(|e| e.to_string())
}

#[tauri::command]
fn hide_window(window: tauri::Window) -> Result<(), String> {
    window.hide().map_err(|e| e.to_string())
}

#[tauri::command]
fn show_window(window: tauri::Window) -> Result<(), String> {
    let _ = window.show();
    let _ = window.unminimize();
    window.set_focus().map_err(|e| e.to_string())
}

fn create_system_tray() -> SystemTray {
    let show = CustomMenuItem::new("show".to_string(), "Show FRAM");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit");
    let tray_menu = SystemTrayMenu::new()
        .add_item(show)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);
    SystemTray::new().with_menu(tray_menu)
}

fn read_auth_token(app_dir: &Path) -> String {
    let token_path = app_dir.join("data").join(".api_token");
    for _ in 0..5 {
        if let Ok(token) = fs::read_to_string(&token_path) {
            let trimmed = token.trim().to_string();
            if !trimmed.is_empty() {
                return trimmed;
            }
        }
        std::thread::sleep(Duration::from_millis(20));
    }
    String::new()
}

#[tauri::command]
fn get_backend_status(state: tauri::State<BackendStartStatus>) -> Result<BackendStatus, String> {
    let lock = state.0.lock().map_err(|e| e.to_string())?;
    Ok(lock.clone())
}

#[tauri::command]
async fn relaunch_backend(
    app_handle: tauri::AppHandle,
    process_state: tauri::State<'_, BackendProcess>,
    auth_token_state: tauri::State<'_, AuthToken>,
    status_state: tauri::State<'_, BackendStartStatus>,
) -> Result<BackendStatus, String> {
    shutdown_backend_process(&app_handle);
    std::thread::sleep(Duration::from_millis(300));

    let app_dir = get_root_app_dir();
    let (child, backend_status) = start_backend_if_needed(&app_dir);

    if let Ok(mut lock) = process_state.0.lock() {
        *lock = child;
    }

    if let Ok(mut lock) = status_state.0.lock() {
        *lock = backend_status.clone();
    }

    let new_token = read_auth_token(&app_dir);
    if let Ok(mut lock) = auth_token_state.0.lock() {
        *lock = new_token;
    }

    Ok(backend_status)
}

#[tauri::command]
async fn get_api_token(
    state: tauri::State<'_, AuthToken>,
    http_client: tauri::State<'_, HttpClient>,
) -> Result<String, String> {
    let current_token = {
        let lock = state.0.lock().map_err(|e| e.to_string())?;
        lock.clone()
    };
    if !current_token.trim().is_empty() {
        return Ok(current_token);
    }

    let app_dir = get_root_app_dir();
    let disk_token = read_auth_token(&app_dir);
    if !disk_token.is_empty() {
        if let Ok(mut lock) = state.0.lock() {
            *lock = disk_token.clone();
        }
        return Ok(disk_token);
    }

    let client = &http_client.0;
    if let Ok(resp) = client.get("http://127.0.0.1:5050/api/auth/token").send().await {
        if let Ok(json) = resp.json::<serde_json::Value>().await {
            if let Some(t) = json.get("token").and_then(|v| v.as_str()) {
                let token_str = t.to_string();
                if let Ok(mut lock) = state.0.lock() {
                    *lock = token_str.clone();
                }
                return Ok(token_str);
            }
        }
    }

    Ok(String::new())
}

#[tauri::command]
async fn python_backend_request(
    endpoint: String,
    method: String,
    body: Option<String>,
    state: tauri::State<'_, AuthToken>,
    http_client: tauri::State<'_, HttpClient>,
) -> Result<String, String> {
    let mut token = {
        let lock = state.0.lock().map_err(|e| e.to_string())?;
        lock.clone()
    };

    let client = &http_client.0;

    if token.trim().is_empty() {
        let app_dir = get_root_app_dir();
        token = read_auth_token(&app_dir);
        if token.trim().is_empty() {
            if let Ok(resp) = client.get("http://127.0.0.1:5050/api/auth/token").send().await {
                if let Ok(json) = resp.json::<serde_json::Value>().await {
                    if let Some(t) = json.get("token").and_then(|v| v.as_str()) {
                        token = t.to_string();
                    }
                }
            }
        }
        if !token.trim().is_empty() {
            if let Ok(mut lock) = state.0.lock() {
                *lock = token.clone();
            }
        }
    }

    let url = format!("http://127.0.0.1:5050/{}", endpoint);

    let send_req = |t: String| {
        let c = client.clone();
        let u = url.clone();
        let m = method.clone();
        let b = body.clone();
        async move {
            let res = match m.as_str() {
                "GET" => c.get(&u).header("X-FRAM-Token", &t).send().await,
                "POST" => {
                    c.post(&u)
                        .header("Content-Type", "application/json")
                        .header("X-FRAM-Token", &t)
                        .body(b.unwrap_or_default())
                        .send()
                        .await
                }
                "PUT" => {
                    c.put(&u)
                        .header("Content-Type", "application/json")
                        .header("X-FRAM-Token", &t)
                        .body(b.unwrap_or_default())
                        .send()
                        .await
                }
                "DELETE" => c.delete(&u).header("X-FRAM-Token", &t).send().await,
                _ => return Err("Unsupported HTTP method".to_string()),
            };
            res.map_err(|e| e.to_string())
        }
    };

    let mut response = send_req(token.clone()).await;

    if let Ok(ref resp) = response {
        if resp.status() == 401 {
            if let Ok(token_resp) = client.get("http://127.0.0.1:5050/api/auth/token").send().await {
                if let Ok(json) = token_resp.json::<serde_json::Value>().await {
                    if let Some(t) = json.get("token").and_then(|v| v.as_str()) {
                        let new_token = t.to_string();
                        if let Ok(mut lock) = state.0.lock() {
                            *lock = new_token.clone();
                        }
                        response = send_req(new_token).await;
                    }
                }
            }
        }
    }

    match response {
        Ok(resp) => {
            let text = resp.text().await.map_err(|e| e.to_string())?;
            Ok(text)
        }
        Err(e) => Err(format!("Failed to connect to Python backend on port 5050: {}. Check AppData/Local/Forked Account Manager/logs/backend_err.log.", e)),
    }
}

fn shutdown_backend_process(app_handle: &tauri::AppHandle) {
    let token = {
        if let Some(token_state) = app_handle.try_state::<AuthToken>() {
            if let Ok(lock) = token_state.0.lock() {
                lock.clone()
            } else {
                String::new()
            }
        } else {
            String::new()
        }
    };

    if let Ok(mut stream) = TcpStream::connect_timeout(
        &"127.0.0.1:5050".parse().unwrap(),
        Duration::from_millis(300),
    ) {
        use std::io::Write;
        let req = format!(
            "POST /api/system/shutdown HTTP/1.1\r\nHost: 127.0.0.1:5050\r\nX-FRAM-Token: {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            token
        );
        let _ = stream.write_all(req.as_bytes());
    }

    if let Some(be_state) = app_handle.try_state::<BackendProcess>() {
        let mut child_proc = None;
        if let Ok(mut lock) = be_state.0.lock() {
            child_proc = lock.take();
        }
        if let Some(mut child) = child_proc {
            let mut exited = false;
            for _ in 0..50 {
                match child.try_wait() {
                    Ok(Some(_)) => {
                        exited = true;
                        break;
                    }
                    Ok(None) => {
                        std::thread::sleep(Duration::from_millis(50));
                    }
                    Err(_) => {
                        break;
                    }
                }
            }

            if !exited {
                let pid = child.id();
                let _ = child.kill();
                #[cfg(target_os = "windows")]
                {
                    let _ = Command::new("taskkill")
                        .args(["/F", "/T", "/PID", &pid.to_string()])
                        .creation_flags(CREATE_NO_WINDOW)
                        .output();
                }
            }
        }
    }
}

fn main() {
    let app_dir = get_root_app_dir();
    let (child, backend_status) = start_backend_if_needed(&app_dir);
    let token = read_auth_token(&app_dir);
    let http_client = reqwest::Client::builder()
        .tcp_nodelay(true)
        .pool_idle_timeout(Duration::from_secs(60))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let app = tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(child)))
        .manage(AuthToken(Mutex::new(token)))
        .manage(BackendStartStatus(Mutex::new(backend_status)))
        .manage(HttpClient(http_client))
        .system_tray(create_system_tray())
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::LeftClick { .. } => {
                if let Some(window) = app.get_window("main") {
                    let is_visible = window.is_visible().unwrap_or(false);
                    if is_visible {
                        let _ = window.hide();
                    } else {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                    }
                }
            }
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "show" => {
                    if let Some(window) = app.get_window("main") {
                        let _ = window.show();
                        let _ = window.unminimize();
                        let _ = window.set_focus();
                    }
                }
                "quit" => {
                    shutdown_backend_process(&app.app_handle());
                    std::process::exit(0);
                }
                _ => {}
            },
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            minimize_window,
            maximize_window,
            close_window,
            hide_window,
            show_window,
            python_backend_request,
            get_api_token,
            get_backend_status,
            relaunch_backend
        ])
        .on_window_event(|event| match event.event() {
            tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed => {
                shutdown_backend_process(&event.window().app_handle());
            }
            _ => {}
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app_handle, event| match event {
        tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit => {
            shutdown_backend_process(app_handle);
        }
        _ => {}
    });
}
