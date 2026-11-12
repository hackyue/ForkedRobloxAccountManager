#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs::{self, OpenOptions};
use std::io::{Read, Write};
use std::net::{Shutdown, TcpStream};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, AtomicU16, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use tauri::{CustomMenuItem, Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

static ACTIVE_BACKEND_PORT: AtomicU16 = AtomicU16::new(5050);
static BACKEND_INITIALIZING: AtomicBool = AtomicBool::new(true);

fn get_active_port() -> u16 {
    ACTIVE_BACKEND_PORT.load(Ordering::SeqCst)
}

fn set_active_port(port: u16) {
    ACTIVE_BACKEND_PORT.store(port, Ordering::SeqCst);
}

struct BackendProcess(Mutex<Option<Child>>);
struct AuthToken(Mutex<String>);
struct BackendStartStatus(Mutex<BackendStatus>);
struct HttpClient(reqwest::Client);

#[derive(Clone, serde::Serialize)]
struct BackendStatus {
    started: bool,
    reason: String,
}

#[derive(Clone, serde::Serialize)]
struct BackendDiagnostics {
    app_dir: String,
    exe_path: String,
    launcher_pid: u32,
    port_open: bool,
    backend_healthy: bool,
    status_started: bool,
    status_reason: String,
    token_present: bool,
    backend_pid_info: String,
    launcher_log: String,
    backend_log: String,
    backend_err_log: String,
}

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

fn log_launcher(app_dir: &Path, level: &str, msg: &str) {
    let logs_dir = app_dir.join("logs");
    let _ = fs::create_dir_all(&logs_dir);
    let log_file = logs_dir.join("launcher.log");

    if let Ok(meta) = fs::metadata(&log_file) {
        if meta.len() > 2_000_000 {
            let backup_file = logs_dir.join("launcher.prev.log");
            let _ = fs::rename(&log_file, &backup_file);
        }
    }

    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let secs = (now_ms / 1000) % 86400;
    let h = secs / 3600;
    let m = (secs % 3600) / 60;
    let s = secs % 60;
    let ms = now_ms % 1000;

    let line = format!(
        "[{:02}:{:02}:{:02}.{:03}] [PID:{}] [{}] {}\n",
        h,
        m,
        s,
        ms,
        std::process::id(),
        level,
        msg
    );

    if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(&log_file) {
        let _ = f.write_all(line.as_bytes());
        let _ = f.flush();
    }
}

fn is_port_open_at(port: u16) -> bool {
    if let Ok(addr) = format!("127.0.0.1:{}", port).parse() {
        TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok()
    } else {
        false
    }
}

fn is_port_open() -> bool {
    is_port_open_at(get_active_port())
}

fn is_backend_healthy_at(port: u16) -> bool {
    let addr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(400)) {
        Ok(s) => s,
        Err(_) => return false,
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));

    let req = format!(
        "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
        port
    );
    if stream.write_all(req.as_bytes()).is_err() {
        return false;
    }
    let _ = stream.flush();

    let mut total_buf = Vec::with_capacity(2048);
    let mut chunk = [0u8; 1024];
    loop {
        match stream.read(&mut chunk) {
            Ok(0) => break,
            Ok(n) => {
                total_buf.extend_from_slice(&chunk[..n]);
                let partial = String::from_utf8_lossy(&total_buf);
                if (partial.contains("200 OK") || partial.contains("200 "))
                    && (partial.contains("\"healthy\"") || partial.contains("\"status\""))
                {
                    return true;
                }
                if total_buf.len() >= 8192 {
                    break;
                }
            }
            Err(ref e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
            Err(_) => break,
        }
    }

    let resp = String::from_utf8_lossy(&total_buf);
    (resp.contains("200 OK") || resp.contains("200 "))
        && (resp.contains("\"healthy\"") || resp.contains("\"status\"") || resp.contains("application/json"))
}

fn sync_port_from_pid_file(app_dir: &Path) {
    let pid_file = app_dir.join("data").join(".backend_pid");
    if let Ok(raw) = fs::read_to_string(&pid_file) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
            if let Some(p) = val.get("port").and_then(|v| v.as_u64()).map(|v| v as u16) {
                if p >= 1024 && p != get_active_port() {
                    set_active_port(p);
                }
            }
        }
    }
}

fn is_backend_healthy() -> bool {
    let port = get_active_port();
    if is_backend_healthy_at(port) {
        return true;
    }
    let app_dir = get_root_app_dir();
    sync_port_from_pid_file(&app_dir);
    let updated_port = get_active_port();
    if updated_port != port && is_backend_healthy_at(updated_port) {
        return true;
    }
    false
}

#[allow(dead_code)]
fn is_backend_running() -> bool {
    is_backend_healthy() || is_port_open()
}

fn is_valid_backend_exe(path: &Path) -> bool {
    if let Ok(meta) = fs::metadata(path) {
        meta.is_file() && meta.len() > 1_000_000
    } else {
        false
    }
}

fn is_valid_python_exe(path: &Path) -> bool {
    if let Ok(meta) = fs::metadata(path) {
        if !meta.is_file() || meta.len() == 0 {
            return false;
        }
        let path_lower = path.to_string_lossy().to_lowercase();
        if path_lower.contains("windowsapps") && meta.len() < 100_000 {
            return false;
        }
        true
    } else {
        false
    }
}

fn read_recent_error_log(err_log_path: &Path, log_path: &Path) -> String {
    for p in &[err_log_path, log_path] {
        if let Ok(content) = fs::read_to_string(p) {
            let trimmed = content.trim();
            if !trimmed.is_empty() {
                let lines: Vec<&str> = trimmed.lines().collect();
                let start = if lines.len() > 6 { lines.len() - 6 } else { 0 };
                return lines[start..].join(" | ");
            }
        }
    }
    String::new()
}

fn find_python_executable(base_dirs: &[PathBuf]) -> Vec<PathBuf> {
    let mut candidates = Vec::new();

    for dir in base_dirs {
        let mut check_dirs = vec![dir.clone()];
        if let Some(parent) = dir.parent() {
            check_dirs.push(parent.to_path_buf());
        }
        for d in check_dirs {
            #[cfg(target_os = "windows")]
            {
                for venv_name in &[".venv", "venv"] {
                    let venv_py = d.join(venv_name).join("Scripts").join("python.exe");
                    if is_valid_python_exe(&venv_py) && !candidates.contains(&venv_py) {
                        candidates.push(venv_py);
                    }
                }
            }
            #[cfg(not(target_os = "windows"))]
            {
                for venv_name in &[".venv", "venv"] {
                    for bin_name in &["python3", "python"] {
                        let venv_py = d.join(venv_name).join("bin").join(bin_name);
                        if is_valid_python_exe(&venv_py) && !candidates.contains(&venv_py) {
                            candidates.push(venv_py);
                        }
                    }
                }
            }
        }
    }

    #[cfg(target_os = "windows")]
    let exe_names = ["python.exe", "python3.exe", "py.exe", "pythonw.exe"];
    #[cfg(not(target_os = "windows"))]
    let exe_names = ["python3", "python"];

    for dir in base_dirs {
        for name in &exe_names {
            let path = dir.join(name);
            if is_valid_python_exe(&path) && !candidates.contains(&path) {
                candidates.push(path);
            }
        }
    }

    #[cfg(target_os = "windows")]
    {
        if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
            let py_dir = PathBuf::from(&local_app_data).join("Programs").join("Python");
            if let Ok(entries) = fs::read_dir(&py_dir) {
                for entry in entries.flatten() {
                    let py_exe = entry.path().join("python.exe");
                    if is_valid_python_exe(&py_exe) && !candidates.contains(&py_exe) {
                        candidates.push(py_exe);
                    }
                }
            }
        }
        for env_key in &["ProgramFiles", "ProgramFiles(x86)", "SystemDrive"] {
            if let Ok(base) = std::env::var(env_key) {
                let base_path = PathBuf::from(&base);
                if let Ok(entries) = fs::read_dir(&base_path) {
                    for entry in entries.flatten() {
                        let fname = entry.file_name().to_string_lossy().to_lowercase();
                        if fname.starts_with("python") {
                            let py_exe = entry.path().join("python.exe");
                            if is_valid_python_exe(&py_exe) && !candidates.contains(&py_exe) {
                                candidates.push(py_exe);
                            }
                        }
                    }
                }
            }
        }
        if let Ok(windir) = std::env::var("WINDIR") {
            let py_launcher = PathBuf::from(windir).join("py.exe");
            if is_valid_python_exe(&py_launcher) && !candidates.contains(&py_launcher) {
                candidates.push(py_launcher);
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        let mac_dirs = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/Library/Frameworks/Python.framework/Versions/Current/bin",
            "/usr/bin",
        ];
        for mdir in &mac_dirs {
            for name in &exe_names {
                let path = PathBuf::from(mdir).join(name);
                if is_valid_python_exe(&path) && !candidates.contains(&path) {
                    candidates.push(path);
                }
            }
        }
    }

    if let Ok(path_var) = std::env::var("PATH") {
        for dir in std::env::split_paths(&path_var) {
            for name in &exe_names {
                let path = dir.join(name);
                if is_valid_python_exe(&path) && !candidates.contains(&path) {
                    candidates.push(path);
                }
            }
        }
    }

    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        let win_app_py = PathBuf::from(&local_app_data).join("Microsoft").join("WindowsApps").join("python.exe");
        if is_valid_python_exe(&win_app_py) && !candidates.contains(&win_app_py) {
            candidates.push(win_app_py);
        }
    }

    candidates
}

fn find_backend_executable(search_dirs: &[PathBuf]) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    let mut seen_canonical = Vec::new();
    #[cfg(target_os = "windows")]
    let exe_names = ["backend.exe", "FRAMBackend.exe", "fram_backend.exe"];
    #[cfg(not(target_os = "windows"))]
    let exe_names = ["backend", "FRAMBackend", "fram_backend", "backend.exe"];

    for dir in search_dirs {
        for sub in [dir.clone(), dir.join("resources")] {
            for name in &exe_names {
                let path = sub.join(name);
                if is_valid_backend_exe(&path) {
                    let canon = fs::canonicalize(&path).unwrap_or_else(|_| path.clone());
                    if !seen_canonical.contains(&canon) {
                        seen_canonical.push(canon);
                        candidates.push(path);
                    }
                }
            }
        }
    }

    candidates
}

fn generate_api_token() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let pid = std::process::id();
    let addr = (&nanos as *const u128) as usize;
    format!("fram_{:x}_{:x}_{:x}", nanos, pid, addr)
}

fn send_shutdown_http_at(port: u16, token: &str) -> bool {
    let addr = match format!("127.0.0.1:{}", port).parse() {
        Ok(a) => a,
        Err(_) => return false,
    };
    if let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(300)) {
        let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));
        let _ = stream.set_read_timeout(Some(Duration::from_millis(400)));
        let req = format!(
            "POST /api/system/shutdown HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nX-FRAM-Token: {}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            port, token
        );
        if stream.write_all(req.as_bytes()).is_ok() {
            let _ = stream.flush();
            let _ = stream.shutdown(Shutdown::Write);
            let mut resp_buf = [0u8; 256];
            let _ = stream.read(&mut resp_buf);
            return true;
        }
    }
    false
}

fn send_shutdown_http(token: &str) -> bool {
    send_shutdown_http_at(get_active_port(), token)
}

fn force_kill_pid_tree(app_dir: &Path, pid: u32, label: &str) {
    if pid <= 1 || pid == std::process::id() {
        return;
    }
    log_launcher(app_dir, "INFO", &format!("Terminating {} process tree (PID={})", label, pid));
    #[cfg(target_os = "windows")]
    {
        if let Ok(out) = Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
        {
            let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
            let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
            log_launcher(
                app_dir,
                "INFO",
                &format!("taskkill PID={} status={} stdout='{}' stderr='{}'", pid, out.status, stdout, stderr),
            );
        }
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = Command::new("pkill")
            .args(["-P", &pid.to_string()])
            .output();
        let _ = Command::new("kill")
            .args(["-9", &pid.to_string()])
            .output();
    }
}

#[cfg(target_os = "windows")]
fn find_pids_listening_on_port(port: u16) -> Vec<u32> {
    let mut pids = Vec::new();
    let port_suffix = format!(":{}", port);
    if let Ok(out) = Command::new("netstat")
        .args(["-ano", "-p", "tcp"])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
    {
        let stdout = String::from_utf8_lossy(&out.stdout);
        for line in stdout.lines() {
            let upper = line.to_uppercase();
            if upper.contains("LISTENING") {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() >= 5 {
                    let local_addr = parts[1];
                    let state = parts[parts.len() - 2];
                    let pid_str = parts[parts.len() - 1];
                    if state.eq_ignore_ascii_case("LISTENING") && local_addr.ends_with(&port_suffix) {
                        if let Ok(pid) = pid_str.parse::<u32>() {
                            if pid > 0 && !pids.contains(&pid) {
                                pids.push(pid);
                            }
                        }
                    }
                }
            }
        }
    }
    pids
}

#[cfg(not(target_os = "windows"))]
fn find_pids_listening_on_port(port: u16) -> Vec<u32> {
    let mut pids = Vec::new();
    if let Ok(out) = Command::new("lsof")
        .args(["-ti", &format!(":{}", port)])
        .output()
    {
        let stdout = String::from_utf8_lossy(&out.stdout);
        for line in stdout.lines() {
            if let Ok(pid) = line.trim().parse::<u32>() {
                if pid > 0 && !pids.contains(&pid) {
                    pids.push(pid);
                }
            }
        }
    }
    pids
}

fn select_clean_backend_port(app_dir: &Path) -> u16 {
    for candidate in 5050..=5065 {
        let listening_pids = find_pids_listening_on_port(candidate);
        if !listening_pids.is_empty() {
            log_launcher(
                app_dir,
                "WARN",
                &format!(
                    "Port {} has existing/phantom listener PIDs {:?}; skipping to next port",
                    candidate, listening_pids
                ),
            );
            continue;
        }
        if is_port_open_at(candidate) {
            log_launcher(
                app_dir,
                "WARN",
                &format!("Port {} responded to TCP connect; skipping to next port", candidate),
            );
            continue;
        }
        if std::net::TcpListener::bind(("127.0.0.1", candidate)).is_ok() {
            if candidate != 5050 {
                log_launcher(
                    app_dir,
                    "INFO",
                    &format!("Selected clean fallback port {} (port 5050 was occupied/wedged)", candidate),
                );
            }
            set_active_port(candidate);
            return candidate;
        }
    }
    set_active_port(5050);
    5050
}

fn cleanup_stale_backend(app_dir: &Path) -> bool {
    let pid_file = app_dir.join("data").join(".backend_pid");
    let current_launcher_pid = std::process::id().to_string();

    let mut recorded_pid: Option<u32> = None;
    let mut recorded_ppid: Option<u32> = None;
    let mut recorded_parent_pid: Option<String> = None;
    let mut recorded_port: u16 = get_active_port();

    if let Ok(raw) = fs::read_to_string(&pid_file) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
            recorded_pid = val.get("pid").and_then(|v| v.as_u64()).map(|v| v as u32);
            recorded_ppid = val.get("ppid").and_then(|v| v.as_u64()).map(|v| v as u32);
            if let Some(p) = val.get("port").and_then(|v| v.as_u64()).map(|v| v as u16) {
                if p >= 1024 {
                    recorded_port = p;
                }
            }
            recorded_parent_pid = val
                .get("parent_pid")
                .and_then(|v| v.as_str())
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty());
        }
    }

    let port_open = is_port_open_at(recorded_port) || is_port_open_at(5050);
    let healthy = if is_port_open_at(recorded_port) && is_backend_healthy_at(recorded_port) {
        set_active_port(recorded_port);
        true
    } else if is_port_open_at(5050) && is_backend_healthy_at(5050) {
        set_active_port(5050);
        true
    } else {
        false
    };

    let is_orphaned_from_previous_launcher = match &recorded_parent_pid {
        Some(pp) => pp != &current_launcher_pid,
        None => false,
    };

    // If a healthy external dev backend is running (no FRAM_PARENT_PID set) and we have or can fetch its token, reuse it
    if healthy && !is_orphaned_from_previous_launcher && recorded_parent_pid.is_none() {
        log_launcher(
            app_dir,
            "INFO",
            &format!(
                "Detected healthy external backend on port {} without FRAM_PARENT_PID; reusing instance.",
                get_active_port()
            ),
        );
        return true;
    }

    let mut listening_pids = find_pids_listening_on_port(5050);
    if recorded_port != 5050 {
        for p in find_pids_listening_on_port(recorded_port) {
            if !listening_pids.contains(&p) {
                listening_pids.push(p);
            }
        }
    }

    if !port_open && recorded_pid.is_none() && listening_pids.is_empty() {
        return false;
    }

    log_launcher(
        app_dir,
        "WARN",
        &format!(
            "Cleaning up stale/previous backend state (port_open={}, healthy={}, recorded_pid={:?}, recorded_ppid={:?}, recorded_parent_pid={:?}, listening_pids={:?})",
            port_open, healthy, recorded_pid, recorded_ppid, recorded_parent_pid, listening_pids
        ),
    );

    if port_open {
        let existing_token = read_auth_token(app_dir);
        let _ = send_shutdown_http_at(recorded_port, &existing_token);
        if recorded_port != 5050 {
            let _ = send_shutdown_http_at(5050, &existing_token);
        }
        for _ in 0..15 {
            std::thread::sleep(Duration::from_millis(50));
            if !is_port_open_at(recorded_port) && !is_port_open_at(5050) {
                break;
            }
        }
    }

    if let Some(p) = recorded_pid {
        force_kill_pid_tree(app_dir, p, "recorded backend");
    }
    if let Some(pp) = recorded_ppid {
        if Some(pp) != recorded_pid {
            force_kill_pid_tree(app_dir, pp, "recorded backend bootloader");
        }
    }

    for lp in &listening_pids {
        if *lp != std::process::id() && Some(*lp) != recorded_pid && Some(*lp) != recorded_ppid {
            force_kill_pid_tree(app_dir, *lp, "stale port listener");
        }
    }

    #[cfg(target_os = "windows")]
    {
        for exe in &["backend.exe", "FRAMBackend.exe"] {
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/IM", exe])
                .creation_flags(CREATE_NO_WINDOW)
                .output();
        }
    }

    let _ = fs::remove_file(&pid_file);

    for _ in 0..15 {
        if !is_port_open_at(recorded_port) && !is_port_open_at(5050) {
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }

    false
}

fn read_tail_file(path: &Path, max_lines: usize) -> String {
    if let Ok(content) = fs::read_to_string(path) {
        let trimmed = content.trim();
        if trimmed.is_empty() {
            return String::new();
        }
        let lines: Vec<&str> = trimmed.lines().collect();
        let start = if lines.len() > max_lines { lines.len() - max_lines } else { 0 };
        return lines[start..].join("\n");
    }
    String::new()
}

fn get_root_app_dir() -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        if let Ok(home) = std::env::var("HOME") {
            let app_dir = PathBuf::from(home)
                .join("Library")
                .join("Application Support")
                .join("Forked Account Manager");
            let _ = fs::create_dir_all(app_dir.join("data"));
            let _ = fs::create_dir_all(app_dir.join("logs"));
            let _ = fs::create_dir_all(app_dir.join("cache"));
            let _ = fs::create_dir_all(app_dir.join("extensions"));
            return app_dir;
        }
    }

    if let Ok(local_appdata) = std::env::var("LOCALAPPDATA").or_else(|_| std::env::var("APPDATA")) {
        let app_dir = PathBuf::from(local_appdata).join("Forked Account Manager");
        let _ = fs::create_dir_all(app_dir.join("data"));
        let _ = fs::create_dir_all(app_dir.join("logs"));
        let _ = fs::create_dir_all(app_dir.join("cache"));
        let _ = fs::create_dir_all(app_dir.join("extensions"));
        return app_dir;
    }

    if let Ok(home) = std::env::var("HOME") {
        let app_dir = PathBuf::from(home).join(".local").join("share").join("Forked Account Manager");
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

fn start_backend_if_needed(app_dir: &Path, auth_token: &str) -> (Option<Child>, BackendStatus) {
    let parent_pid = std::process::id().to_string();
    log_launcher(
        app_dir,
        "INFO",
        &format!("start_backend_if_needed called (launcher_pid={})", parent_pid),
    );

    let already_running = cleanup_stale_backend(app_dir);
    if already_running && is_backend_healthy() {
        let p = get_active_port();
        log_launcher(app_dir, "INFO", &format!("Reusing healthy existing backend instance on port {}", p));
        return (
            None,
            BackendStatus {
                started: true,
                reason: format!("Backend already running (healthy on port {})", p),
            },
        );
    }

    let target_port = select_clean_backend_port(app_dir);

    let stale_token_path = app_dir.join("data").join(".api_token");
    let _ = fs::remove_file(&stale_token_path);

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
        cur_dir.join("..").join("src-tauri").join("resources"),
        cur_dir.join("dist"),
        cur_dir.join("..").join("dist"),
        cur_dir.join("backend").join("dist"),
        cur_dir.join("..").join("backend").join("dist"),
        exe_dir.join("..").join("Resources"),
        exe_dir.join("..").join("Resources").join("resources"),
    ];

    let backend_exe_candidates = find_backend_executable(&exe_search_dirs);
    log_launcher(
        app_dir,
        "INFO",
        &format!("Found {} candidate backend binaries (target_port={})", backend_exe_candidates.len(), target_port),
    );

    for be_exe in &backend_exe_candidates {
        if is_valid_backend_exe(be_exe) {
            log_launcher(app_dir, "INFO", &format!("Attempting to spawn standalone backend: {} on port {}", be_exe.display(), target_port));

            #[cfg(target_os = "windows")]
            {
                let ads_path = format!("{}:Zone.Identifier", be_exe.display());
                let _ = fs::remove_file(ads_path);
            }

            let mut cmd = Command::new(be_exe);
            cmd.current_dir(app_dir);
            cmd.env("FRAM_APP_DIR", app_dir.to_str().unwrap_or_default());
            cmd.env("FRAM_PARENT_PID", &parent_pid);
            cmd.env("FRAM_API_TOKEN", auth_token);
            cmd.env("PORT", target_port.to_string());
            cmd.env("PYTHONUNBUFFERED", "1");

            if let Ok(out_f) = fs::File::create(&log_path) {
                cmd.stdout(Stdio::from(out_f));
            }
            if let Ok(err_f) = fs::File::create(&err_log_path) {
                cmd.stderr(Stdio::from(err_f));
            }

            #[cfg(target_os = "windows")]
            cmd.creation_flags(CREATE_NO_WINDOW);

            match cmd.spawn() {
                Ok(mut child) => {
                    let child_id = child.id();
                    log_launcher(
                        app_dir,
                        "INFO",
                        &format!("Spawned backend process (PID={}); waiting up to 15s for /api/health on port {}...", child_id, target_port),
                    );
                    let mut crashed = false;
                    let start_wait = Instant::now();
                    while start_wait.elapsed() < Duration::from_secs(15) {
                        std::thread::sleep(Duration::from_millis(80));
                        sync_port_from_pid_file(app_dir);
                        if is_backend_healthy() {
                            let active_p = get_active_port();
                            log_launcher(
                                app_dir,
                                "INFO",
                                &format!(
                                    "Backend healthy after {}ms (PID={}, port={})",
                                    start_wait.elapsed().as_millis(),
                                    child_id,
                                    active_p
                                ),
                            );
                            return (
                                Some(child),
                                BackendStatus {
                                    started: true,
                                    reason: format!("Backend started successfully (port {})", active_p),
                                },
                            );
                        }
                        if let Ok(Some(status)) = child.try_wait() {
                            log_launcher(
                                app_dir,
                                "ERROR",
                                &format!("Backend process PID={} exited early with status: {:?}", child_id, status),
                            );
                            crashed = true;
                            break;
                        }
                    }
                    if !crashed {
                        log_launcher(
                            app_dir,
                            "ERROR",
                            &format!(
                                "Backend process PID={} timed out after {}ms without becoming healthy",
                                child_id,
                                start_wait.elapsed().as_millis()
                            ),
                        );
                        force_kill_pid_tree(app_dir, child_id, "timed-out backend");
                        let _ = child.kill();
                    }
                }
                Err(e) => {
                    log_launcher(
                        app_dir,
                        "ERROR",
                        &format!("Failed to spawn backend binary {}: {}", be_exe.display(), e),
                    );
                    continue;
                }
            }
        }
    }

    log_launcher(app_dir, "WARN", "Standalone backend candidates failed; checking for Python app.py script fallback");

    let possible_paths = [
        exe_dir.join("backend").join("app.py"),
        exe_dir.join("resources").join("backend").join("app.py"),
        exe_dir.join("_up_").join("backend").join("app.py"),
        exe_dir.join("..").join("Resources").join("backend").join("app.py"),
        exe_dir.join("..").join("Resources").join("_up_").join("backend").join("app.py"),
        cur_dir.join("backend").join("app.py"),
        cur_dir.join("..").join("backend").join("app.py"),
        exe_dir.join("..").join("backend").join("app.py"),
        exe_dir.join("..").join("..").join("backend").join("app.py"),
        exe_dir.join("..").join("..").join("..").join("backend").join("app.py"),
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
            let err_detail = read_recent_error_log(&err_log_path, &log_path);
            let msg = if err_detail.is_empty() {
                "Could not locate backend binary or backend/app.py in application resources.".to_string()
            } else {
                format!("Standalone backend failed to start ({}) and backend/app.py was not found.", err_detail)
            };
            log_launcher(app_dir, "ERROR", &msg);
            let _ = OpenOptions::new()
                .create(true)
                .append(true)
                .open(&log_path)
                .and_then(|mut f| f.write_all(format!("\nError: {}\n", msg).as_bytes()));
            return (None, BackendStatus { started: false, reason: msg });
        }
    };

    let fallback_port = select_clean_backend_port(app_dir);
    let script_parent = target_script.parent().unwrap_or_else(|| Path::new("."));
    let base_dirs = vec![exe_dir.to_path_buf(), cur_dir.to_path_buf(), script_parent.to_path_buf()];
    let python_candidates = find_python_executable(&base_dirs);

    let fallback_log_path = app_dir.join("logs").join("backend_fallback.log");
    let fallback_err_log_path = app_dir.join("logs").join("backend_fallback_err.log");

    for py_exe in &python_candidates {
        log_launcher(
            app_dir,
            "INFO",
            &format!("Attempting to spawn Python fallback: {} {} on port {}", py_exe.display(), target_script.display(), fallback_port),
        );

        let mut cmd = Command::new(py_exe);
        cmd.arg(&target_script);
        cmd.current_dir(script_parent);
        cmd.env("FRAM_APP_DIR", app_dir.to_str().unwrap_or_default());
        cmd.env("FRAM_PARENT_PID", &parent_pid);
        cmd.env("FRAM_API_TOKEN", auth_token);
        cmd.env("PORT", fallback_port.to_string());
        cmd.env("PYTHONUNBUFFERED", "1");

        if let Ok(out_f) = fs::File::create(&fallback_log_path) {
            cmd.stdout(Stdio::from(out_f));
        }
        if let Ok(err_f) = fs::File::create(&fallback_err_log_path) {
            cmd.stderr(Stdio::from(err_f));
        }

        #[cfg(target_os = "windows")]
        cmd.creation_flags(CREATE_NO_WINDOW);

        match cmd.spawn() {
            Ok(mut child) => {
                let child_id = child.id();
                let mut crashed = false;
                let start_wait = Instant::now();
                while start_wait.elapsed() < Duration::from_secs(12) {
                    std::thread::sleep(Duration::from_millis(80));
                    sync_port_from_pid_file(app_dir);
                    if is_backend_healthy() {
                        let active_p = get_active_port();
                        log_launcher(
                            app_dir,
                            "INFO",
                            &format!(
                                "Python fallback backend healthy after {}ms (PID={}, port={})",
                                start_wait.elapsed().as_millis(),
                                child_id,
                                active_p
                            ),
                        );
                        return (
                            Some(child),
                            BackendStatus {
                                started: true,
                                reason: format!("Backend started successfully (Python fallback, port {})", active_p),
                            },
                        );
                    }
                    if let Ok(Some(status)) = child.try_wait() {
                        log_launcher(
                            app_dir,
                            "ERROR",
                            &format!("Python fallback PID={} exited early with status: {:?}", child_id, status),
                        );
                        crashed = true;
                        break;
                    }
                }
                if !crashed {
                    force_kill_pid_tree(app_dir, child_id, "timed-out python backend");
                    let _ = child.kill();
                }
            }
            Err(e) => {
                log_launcher(
                    app_dir,
                    "ERROR",
                    &format!("Failed to spawn python interpreter {}: {}", py_exe.display(), e),
                );
                continue;
            }
        }
    }

    let err_detail = read_recent_error_log(&err_log_path, &log_path);
    let fallback_detail = read_recent_error_log(&fallback_err_log_path, &fallback_log_path);
    let combined_detail = if !fallback_detail.is_empty() {
        fallback_detail
    } else {
        err_detail
    };

    let active_p = get_active_port();
    let reason_msg = if !combined_detail.is_empty() {
        format!("Backend process failed to start or bind port {}: {}", active_p, combined_detail)
    } else {
        format!("Backend failed to start on port {}. Ensure Windows Defender or security software has not blocked backend.exe.", active_p)
    };

    log_launcher(app_dir, "ERROR", &reason_msg);
    (None, BackendStatus { started: false, reason: reason_msg })
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
    let app_handle = window.app_handle();
    let _ = window.hide();
    std::thread::spawn(move || {
        std::thread::spawn(|| {
            std::thread::sleep(Duration::from_millis(2500));
            std::process::exit(0);
        });
        shutdown_backend_process(&app_handle);
        std::process::exit(0);
    });
    Ok(())
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
async fn get_backend_status(state: tauri::State<'_, BackendStartStatus>) -> Result<BackendStatus, String> {
    let wait_start = Instant::now();
    while BACKEND_INITIALIZING.load(Ordering::SeqCst) && wait_start.elapsed() < Duration::from_secs(16) {
        if is_backend_healthy() {
            break;
        }
        tokio::time::sleep(Duration::from_millis(80)).await;
    }
    if is_backend_healthy() {
        return Ok(BackendStatus {
            started: true,
            reason: format!("Backend running and healthy (port {})", get_active_port()),
        });
    }
    let lock = state.0.lock().map_err(|e| e.to_string())?;
    Ok(lock.clone())
}

#[tauri::command]
fn get_backend_diagnostics(
    status_state: tauri::State<BackendStartStatus>,
    auth_token_state: tauri::State<AuthToken>,
) -> Result<BackendDiagnostics, String> {
    let app_dir = get_root_app_dir();
    let log_path = app_dir.join("logs").join("backend.log");
    let err_log_path = app_dir.join("logs").join("backend_err.log");
    let launcher_log_path = app_dir.join("logs").join("launcher.log");
    let pid_path = app_dir.join("data").join(".backend_pid");

    let (started, reason) = if let Ok(lock) = status_state.0.lock() {
        (lock.started, lock.reason.clone())
    } else {
        (false, "Lock error".to_string())
    };

    let pid_info = fs::read_to_string(&pid_path).unwrap_or_default();
    let token = if let Ok(lock) = auth_token_state.0.lock() {
        lock.clone()
    } else {
        read_auth_token(&app_dir)
    };

    Ok(BackendDiagnostics {
        app_dir: app_dir.to_string_lossy().to_string(),
        exe_path: std::env::current_exe().map(|p| p.to_string_lossy().to_string()).unwrap_or_default(),
        launcher_pid: std::process::id(),
        port_open: is_port_open(),
        backend_healthy: is_backend_healthy(),
        status_started: started,
        status_reason: reason,
        token_present: !token.is_empty(),
        backend_pid_info: pid_info,
        launcher_log: read_tail_file(&launcher_log_path, 80),
        backend_log: read_tail_file(&log_path, 80),
        backend_err_log: read_tail_file(&err_log_path, 80),
    })
}

#[tauri::command]
async fn relaunch_backend(
    app_handle: tauri::AppHandle,
    process_state: tauri::State<'_, BackendProcess>,
    auth_token_state: tauri::State<'_, AuthToken>,
    status_state: tauri::State<'_, BackendStartStatus>,
) -> Result<BackendStatus, String> {
    let app_dir = get_root_app_dir();
    log_launcher(&app_dir, "INFO", "relaunch_backend command invoked");

    BACKEND_INITIALIZING.store(true, Ordering::SeqCst);
    shutdown_backend_process(&app_handle);
    SHUTDOWN_CALLED.store(false, Ordering::SeqCst);
    std::thread::sleep(Duration::from_millis(300));
    cleanup_stale_backend(&app_dir);

    let new_token = generate_api_token();
    let (child, backend_status) = start_backend_if_needed(&app_dir, &new_token);

    if let Ok(mut lock) = process_state.0.lock() {
        *lock = child;
    }

    if let Ok(mut lock) = status_state.0.lock() {
        *lock = backend_status.clone();
    }

    if let Ok(mut lock) = auth_token_state.0.lock() {
        *lock = new_token;
    }

    BACKEND_INITIALIZING.store(false, Ordering::SeqCst);
    Ok(backend_status)
}

#[tauri::command]
async fn get_api_token(
    state: tauri::State<'_, AuthToken>,
    http_client: tauri::State<'_, HttpClient>,
) -> Result<String, String> {
    let app_dir = get_root_app_dir();
    let disk_token = read_auth_token(&app_dir);
    if !disk_token.is_empty() {
        if let Ok(mut lock) = state.0.lock() {
            *lock = disk_token.clone();
        }
        return Ok(disk_token);
    }

    let current_token = {
        let lock = state.0.lock().map_err(|e| e.to_string())?;
        lock.clone()
    };
    if !current_token.trim().is_empty() {
        return Ok(current_token);
    }

    if !is_port_open() {
        return Ok(String::new());
    }

    let active_port = get_active_port();
    let client = &http_client.0;
    if let Ok(resp) = client.get(format!("http://127.0.0.1:{}/api/auth/token", active_port)).send().await {
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
    let app_dir = get_root_app_dir();
    let log_path = app_dir.join("logs").join("backend.log");
    let err_log_path = app_dir.join("logs").join("backend_err.log");

    let wait_start = Instant::now();
    while BACKEND_INITIALIZING.load(Ordering::SeqCst) && wait_start.elapsed() < Duration::from_secs(16) {
        tokio::time::sleep(Duration::from_millis(60)).await;
    }

    sync_port_from_pid_file(&app_dir);
    let active_port = get_active_port();

    if !is_port_open_at(active_port) {
        let err_detail = read_recent_error_log(&err_log_path, &log_path);
        let msg = if !err_detail.is_empty() {
            format!("Python backend is not running on port {} ({})", active_port, err_detail)
        } else {
            format!("Python backend is not running on port {}. Check logs at {}", active_port, err_log_path.display())
        };
        log_launcher(&app_dir, "WARN", &format!("Request {} {} rejected: backend not listening on port {}", method, endpoint, active_port));
        return Err(msg);
    }

    let mut token = {
        let lock = state.0.lock().map_err(|e| e.to_string())?;
        lock.clone()
    };

    let client = &http_client.0;

    if token.trim().is_empty() {
        token = read_auth_token(&app_dir);
        if token.trim().is_empty() {
            if let Ok(resp) = client.get(format!("http://127.0.0.1:{}/api/auth/token", active_port)).send().await {
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

    let url = format!("http://127.0.0.1:{}/{}", active_port, endpoint);

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
        // Only refresh token on 401 Unauthorized if it's an actual token rejection (not vault lock)
        if resp.status() == 401 {
            let mut new_token = read_auth_token(&app_dir);
            if new_token.is_empty() || new_token == token {
                if let Ok(token_resp) = client.get(format!("http://127.0.0.1:{}/api/auth/token", active_port)).send().await {
                    if let Ok(json) = token_resp.json::<serde_json::Value>().await {
                        if let Some(t) = json.get("token").and_then(|v| v.as_str()) {
                            new_token = t.to_string();
                        }
                    }
                }
            }
            if !new_token.is_empty() && new_token != token {
                if let Ok(mut lock) = state.0.lock() {
                    *lock = new_token.clone();
                }
                response = send_req(new_token).await;
            }
        }
    }

    match response {
        Ok(resp) => {
            let text = resp.text().await.map_err(|e| e.to_string())?;
            Ok(text)
        }
        Err(e) => {
            log_launcher(&app_dir, "ERROR", &format!("HTTP request error for {} {}: {}", method, endpoint, e));
            Err(format!("Failed to connect to Python backend on port {}: {}. Check logs at {}.", active_port, e, err_log_path.display()))
        }
    }
}

static SHUTDOWN_CALLED: AtomicBool = AtomicBool::new(false);

fn shutdown_backend_process(app_handle: &tauri::AppHandle) {
    if SHUTDOWN_CALLED.swap(true, Ordering::SeqCst) {
        return;
    }

    let app_dir = get_root_app_dir();
    log_launcher(&app_dir, "INFO", "shutdown_backend_process initiated");

    let token = {
        if let Some(token_state) = app_handle.try_state::<AuthToken>() {
            if let Ok(lock) = token_state.0.lock() {
                lock.clone()
            } else {
                read_auth_token(&app_dir)
            }
        } else {
            read_auth_token(&app_dir)
        }
    };

    // 1. Send graceful shutdown request and wait for it
    if is_port_open() {
        let sent = send_shutdown_http(&token);
        log_launcher(&app_dir, "INFO", &format!("Sent HTTP shutdown signal (delivered={})", sent));
    }

    // 2. Read recorded backend PID from .backend_pid before child is killed
    let pid_file = app_dir.join("data").join(".backend_pid");
    let mut recorded_child_pid: Option<u32> = None;
    if let Ok(raw) = fs::read_to_string(&pid_file) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
            recorded_child_pid = val.get("pid").and_then(|v| v.as_u64()).map(|v| v as u32);
        }
    }

    // 3. Give process a brief moment to exit cleanly
    let mut exited = false;
    if let Some(be_state) = app_handle.try_state::<BackendProcess>() {
        let mut child_proc = None;
        if let Ok(mut lock) = be_state.0.lock() {
            child_proc = lock.take();
        }
        if let Some(mut child) = child_proc {
            for _ in 0..25 {
                match child.try_wait() {
                    Ok(Some(status)) => {
                        log_launcher(&app_dir, "INFO", &format!("Child backend exited cleanly with status: {:?}", status));
                        exited = true;
                        break;
                    }
                    Ok(None) => {
                        std::thread::sleep(Duration::from_millis(40));
                    }
                    Err(_) => {
                        break;
                    }
                }
            }

            if !exited {
                let pid = child.id();
                log_launcher(&app_dir, "WARN", &format!("Backend child PID={} did not exit cleanly; terminating tree...", pid));

                #[cfg(target_os = "windows")]
                {
                    // CRITICAL: On Windows with PyInstaller, taskkill must run BEFORE child.kill()
                    // so the process tree can be traversed and all child processes killed.
                    force_kill_pid_tree(&app_dir, pid, "spawned child");
                }

                #[cfg(not(target_os = "windows"))]
                {
                    let _ = Command::new("pkill").args(["-P", &pid.to_string()]).output();
                    let _ = Command::new("kill").args(["-9", &pid.to_string()]).output();
                }

                let _ = child.kill();
            }
        }
    }

    // 4. Also kill the recorded Python worker PID if PyInstaller spawned a separate worker
    if let Some(wpid) = recorded_child_pid {
        force_kill_pid_tree(&app_dir, wpid, "recorded worker");
    }

    // 5. Clean up stale pid and token files
    let _ = fs::remove_file(&pid_file);
    let _ = fs::remove_file(app_dir.join("data").join(".api_token"));

    // 6. Wait for active backend port to close
    let active_p = get_active_port();
    for _ in 0..15 {
        if !is_port_open_at(active_p) {
            break;
        }
        std::thread::sleep(Duration::from_millis(40));
    }

    let remaining_pids = find_pids_listening_on_port(active_p);
    for rp in remaining_pids {
        if rp != std::process::id() {
            force_kill_pid_tree(&app_dir, rp, "shutdown lingering port listener");
        }
    }

    #[cfg(target_os = "windows")]
    {
        for exe in &["backend.exe", "FRAMBackend.exe"] {
            let _ = Command::new("taskkill")
                .args(["/F", "/T", "/IM", exe])
                .creation_flags(CREATE_NO_WINDOW)
                .output();
        }
    }

    log_launcher(&app_dir, "INFO", "shutdown_backend_process completed");
    let _ = fs::remove_file(app_dir.join("data").join(".app_instance"));
}

#[cfg(target_os = "windows")]
mod single_instance {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;

    extern "system" {
        fn CreateMutexW(
            lpMutexAttributes: *mut std::ffi::c_void,
            bInitialOwner: i32,
            lpName: *const u16,
        ) -> *mut std::ffi::c_void;
        fn GetLastError() -> u32;
        fn CloseHandle(hObject: *mut std::ffi::c_void) -> i32;
        fn FindWindowW(lpClassName: *const u16, lpWindowName: *const u16) -> *mut std::ffi::c_void;
        fn ShowWindow(hWnd: *mut std::ffi::c_void, nCmdShow: i32) -> i32;
        fn SetForegroundWindow(hWnd: *mut std::ffi::c_void) -> i32;
    }

    const ERROR_ALREADY_EXISTS: u32 = 183;
    const SW_SHOW: i32 = 5;
    const SW_RESTORE: i32 = 9;

    #[allow(dead_code)]
    pub struct SingleInstanceGuard(*mut std::ffi::c_void);

    unsafe impl Send for SingleInstanceGuard {}
    unsafe impl Sync for SingleInstanceGuard {}

    impl Drop for SingleInstanceGuard {
        fn drop(&mut self) {
            if !self.0.is_null() {
                unsafe { CloseHandle(self.0) };
            }
        }
    }

    pub fn focus_existing_window() -> bool {
        let title: Vec<u16> = OsStr::new("FRAM")
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        unsafe {
            let hwnd = FindWindowW(std::ptr::null(), title.as_ptr());
            if !hwnd.is_null() {
                ShowWindow(hwnd, SW_SHOW);
                ShowWindow(hwnd, SW_RESTORE);
                SetForegroundWindow(hwnd);
                return true;
            }
        }
        false
    }

    pub fn acquire_single_instance() -> Option<SingleInstanceGuard> {
        let name: Vec<u16> = OsStr::new("Local\\ForkedRobloxAccountManager_AppMutex")
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();

        unsafe {
            let handle = CreateMutexW(std::ptr::null_mut(), 0, name.as_ptr());
            if handle.is_null() {
                return None;
            }
            if GetLastError() == ERROR_ALREADY_EXISTS {
                let _ = focus_existing_window();
                CloseHandle(handle);
                return None;
            }
            Some(SingleInstanceGuard(handle))
        }
    }
}

#[cfg(not(target_os = "windows"))]
mod single_instance {
    use std::fs::OpenOptions;
    use std::os::unix::fs::OpenOptionsExt;
    use std::os::unix::io::AsRawFd;
    use std::path::Path;

    #[allow(dead_code)]
    pub struct SingleInstanceGuard(std::fs::File);

    unsafe impl Send for SingleInstanceGuard {}
    unsafe impl Sync for SingleInstanceGuard {}

    pub fn acquire_single_instance(app_dir: &Path) -> Option<SingleInstanceGuard> {
        let data_dir = app_dir.join("data");
        let _ = std::fs::create_dir_all(&data_dir);
        let lock_path = data_dir.join(".fram_instance.lock");
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .mode(0o600)
            .open(&lock_path)
            .ok()?;

        let fd = file.as_raw_fd();
        let res = unsafe { libc::flock(fd, libc::LOCK_EX | libc::LOCK_NB) };
        if res != 0 {
            return None;
        }
        Some(SingleInstanceGuard(file))
    }
}

fn notify_existing_instance(app_dir: &Path) -> bool {
    let ipc_file = app_dir.join("data").join(".app_instance");
    if let Ok(raw) = fs::read_to_string(&ipc_file) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&raw) {
            if let Some(port) = val.get("port").and_then(|p| p.as_u64()).map(|p| p as u16) {
                if let Ok(addr) = format!("127.0.0.1:{}", port).parse::<std::net::SocketAddr>() {
                    if let Ok(mut stream) = TcpStream::connect_timeout(&addr, Duration::from_millis(300)) {
                        let _ = stream.set_write_timeout(Some(Duration::from_millis(300)));
                        let _ = stream.set_read_timeout(Some(Duration::from_millis(300)));
                        if stream.write_all(b"FOCUS\n").is_ok() {
                            let _ = stream.flush();
                            let mut ack = [0u8; 16];
                            if let Ok(n) = stream.read(&mut ack) {
                                if n > 0 {
                                    return true;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    false
}

fn start_instance_ipc_server(app_handle: tauri::AppHandle, app_dir: PathBuf) {
    std::thread::spawn(move || {
        let listener = match std::net::TcpListener::bind("127.0.0.1:0") {
            Ok(l) => l,
            Err(_) => return,
        };
        let port = match listener.local_addr() {
            Ok(addr) => addr.port(),
            Err(_) => return,
        };

        let ipc_file = app_dir.join("data").join(".app_instance");
        let payload = serde_json::json!({
            "pid": std::process::id(),
            "port": port
        });
        let _ = fs::write(&ipc_file, payload.to_string());

        for stream in listener.incoming() {
            if let Ok(mut s) = stream {
                let _ = s.set_read_timeout(Some(Duration::from_millis(500)));
                let mut buf = [0u8; 64];
                if let Ok(n) = s.read(&mut buf) {
                    let msg = String::from_utf8_lossy(&buf[..n]);
                    if msg.contains("FOCUS") {
                        if let Some(w) = app_handle.get_window("main") {
                            let _ = w.show();
                            let _ = w.unminimize();
                            let _ = w.set_focus();
                        }
                        let _ = s.write_all(b"OK\n");
                    }
                }
            }
        }
    });
}

fn main() {
    let app_dir = get_root_app_dir();

    #[cfg(target_os = "windows")]
    let _instance_guard = match single_instance::acquire_single_instance() {
        Some(g) => g,
        None => {
            let ipc_notified = notify_existing_instance(&app_dir);
            let win_focused = single_instance::focus_existing_window();
            if ipc_notified || win_focused {
                log_launcher(
                    &app_dir,
                    "INFO",
                    &format!(
                        "Another instance of FRAM is already running (ipc_notified={}, win_focused={}). Exiting duplicate instance (PID={}).",
                        ipc_notified, win_focused, std::process::id()
                    ),
                );
                std::process::exit(0);
            } else {
                log_launcher(
                    &app_dir,
                    "WARN",
                    "Detected unresponsive/headless existing FRAM instance; terminating stale instance and continuing startup.",
                );
                let _ = Command::new("taskkill")
                    .args([
                        "/F",
                        "/FI",
                        &format!("PID ne {}", std::process::id()),
                        "/IM",
                        "FRAM.exe",
                    ])
                    .creation_flags(CREATE_NO_WINDOW)
                    .output();
                std::thread::sleep(Duration::from_millis(250));
                match single_instance::acquire_single_instance() {
                    Some(g) => g,
                    None => std::process::exit(0),
                }
            }
        }
    };

    #[cfg(not(target_os = "windows"))]
    let _instance_guard = match single_instance::acquire_single_instance(&app_dir) {
        Some(g) => g,
        None => {
            log_launcher(
                &app_dir,
                "INFO",
                &format!(
                    "Another instance of FRAM is already running. Focus requested. Exiting duplicate instance (PID={}).",
                    std::process::id()
                ),
            );
            let _ = notify_existing_instance(&app_dir);
            std::process::exit(0);
        }
    };

    log_launcher(
        &app_dir,
        "INFO",
        &format!("=== FRAM Starting (PID={}, OS={}) ===", std::process::id(), std::env::consts::OS),
    );

    let token = generate_api_token();
    let initial_status = BackendStatus {
        started: false,
        reason: "Initializing backend service...".to_string(),
    };
    let http_client = reqwest::Client::builder()
        .no_proxy()
        .tcp_nodelay(true)
        .connect_timeout(Duration::from_millis(1500))
        .pool_idle_timeout(Duration::from_secs(60))
        .timeout(Duration::from_secs(15))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new());

    let startup_token = token.clone();
    let startup_app_dir = app_dir.clone();

    let app = tauri::Builder::default()
        .setup(move |app| {
            let app_handle = app.handle();
            start_instance_ipc_server(app_handle.clone(), startup_app_dir.clone());

            if let Some(w) = app.get_window("main") {
                let _ = w.show();
                let _ = w.set_focus();
            }

            let bg_handle = app_handle.clone();
            let bg_dir = startup_app_dir.clone();
            let bg_token = startup_token.clone();
            std::thread::spawn(move || {
                let (child, backend_status) = start_backend_if_needed(&bg_dir, &bg_token);
                if let Some(proc_state) = bg_handle.try_state::<BackendProcess>() {
                    if let Ok(mut lock) = proc_state.0.lock() {
                        *lock = child;
                    }
                }
                if let Some(st_state) = bg_handle.try_state::<BackendStartStatus>() {
                    if let Ok(mut lock) = st_state.0.lock() {
                        *lock = backend_status;
                    }
                }
                BACKEND_INITIALIZING.store(false, Ordering::SeqCst);
            });

            Ok(())
        })
        .manage(BackendProcess(Mutex::new(None)))
        .manage(AuthToken(Mutex::new(token)))
        .manage(BackendStartStatus(Mutex::new(initial_status)))
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
            get_backend_diagnostics,
            relaunch_backend
        ])
        .on_window_event(|event| match event.event() {
            tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed => {
                let app_handle = event.window().app_handle();
                std::thread::spawn(move || {
                    std::thread::spawn(|| {
                        std::thread::sleep(Duration::from_millis(2500));
                        std::process::exit(0);
                    });
                    shutdown_backend_process(&app_handle);
                    std::process::exit(0);
                });
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
