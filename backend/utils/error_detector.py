import sys
import os
import platform
import traceback
import re
from typing import Dict, Any, Optional
from urllib.parse import urlencode


class ErrorDetector:
    APP_VERSION = "3.0.0.2"
    GITHUB_REPO = "hackyue/ForkedRobloxAccountManager"

    def __init__(self):
        self.last_error_report: Optional[Dict[str, Any]] = None
        self._setup_excepthook()

    def _setup_excepthook(self):
        original_excepthook = sys.excepthook
        def custom_excepthook(exc_type, exc_value, exc_traceback):
            if exc_type not in (KeyboardInterrupt, SystemExit):
                self.record_exception(exc_type, exc_value, exc_traceback, source="backend_uncaught")
            original_excepthook(exc_type, exc_value, exc_traceback)
        sys.excepthook = custom_excepthook

    def sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        redacted = str(text)
        patterns = [
            (r'(?i)("(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)"\s*:\s*")([^"]*)(")', r'\1[REDACTED]\3'),
            (r"(?i)('(?:password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)'\s*:\s*')([^']*)(')", r'\1[REDACTED]\3'),
            (r"(?i)\b(password|pass|passwd|pwd|cookie|token|authorization|access_token|refresh_token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;]+)", r'\1\2[REDACTED]'),
            (r"(?i)([?&](?:password|pass|token|cookie|auth|authorization)=)([^&\s]+)", r'\1[REDACTED]'),
            (r"(?i)(\.ROBLOSECURITY\s*[:=]\s*)([^;\s]+)", r'\1[REDACTED]'),
            (r"(?i)(authorization\s*:\s*bearer\s+)([^\s]+)", r'\1[REDACTED]'),
            (r"(?i)(sessionid\s*[:=]\s*)([^;\s]+)", r'\1[REDACTED]')
        ]
        for pattern, replacement in patterns:
            redacted = re.sub(pattern, replacement, redacted)
        return redacted

    def record_exception(self, exc_type: Any, exc_value: Any, exc_traceback: Any, source: str = "backend", extra_context: Optional[str] = None) -> Dict[str, Any]:
        exception_name = getattr(exc_type, "__name__", str(exc_type) or "Exception")
        exception_message = str(exc_value or "").strip() or "(no message)"
        
        if exc_traceback:
            raw_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        elif isinstance(exc_value, Exception):
            raw_traceback = "".join(traceback.format_exception(type(exc_value), exc_value, exc_value.__traceback__))
        else:
            raw_traceback = f"{exception_name}: {exception_message}"

        sanitized_tb = self.sanitize_text(raw_traceback).strip()
        sanitized_msg = self.sanitize_text(exception_message).strip()

        title = f"Crash: {exception_name} ({source})"
        body_lines = [
            "## Summary",
            f"Unhandled exception detected in `{source}`.",
            "",
            "## Environment",
            f"- App Version: {self.APP_VERSION}",
            f"- OS: {platform.system()} {platform.release()}",
            f"- Python: {sys.version.split()[0]}",
        ]
        if extra_context:
            body_lines.extend(["- Context: " + self.sanitize_text(extra_context)])
        body_lines.extend([
            "",
            "## Exception",
            f"- Type: `{exception_name}`",
            f"- Message: `{sanitized_msg}`",
            "",
            "## Traceback (sanitized)",
            "```text",
            f"{sanitized_tb}",
            "```"
        ])
        body = "\n".join(body_lines)

        try:
            query = urlencode({
                "title": self.sanitize_text(title)[:180],
                "body": body[:7000],
                "labels": "bug,auto-report"
            })
            issue_url = f"https://github.com/{self.GITHUB_REPO}/issues/new?{query}"
        except Exception:
            issue_url = f"https://github.com/{self.GITHUB_REPO}/issues/new"

        report = {
            "has_error": True,
            "exception_name": exception_name,
            "exception_message": sanitized_msg,
            "source": source,
            "traceback": sanitized_tb,
            "github_issue_url": issue_url,
            "title": title,
            "body": body
        }
        self.last_error_report = report
        return report


error_detector = ErrorDetector()


def log_detailed_error(context_message: str, exc: Optional[BaseException] = None, extra_info: Optional[Dict[str, Any]] = None, level: str = "ERROR", source: str = "backend") -> str:
    from datetime import datetime
    try:
        from utils.paths import get_logs_folder
        logs_folder = get_logs_folder()
    except Exception:
        logs_folder = None

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"[{timestamp}] [{level.upper()}] [{source}] {context_message}"]

    if extra_info and isinstance(extra_info, dict):
        for k, v in extra_info.items():
            lines.append(f"  Context -> {k}: {v}")

    if exc is not None:
        lines.append(f"  Exception -> {type(exc).__name__}: {str(exc)}")
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        lines.append("  Traceback:")
        for line in tb_str.strip().splitlines():
            lines.append(f"    {line}")
    elif sys.exc_info()[0] is not None:
        exc_type, exc_val, exc_tb = sys.exc_info()
        lines.append(f"  Exception -> {getattr(exc_type, '__name__', 'Exception')}: {str(exc_val)}")
        tb_str = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
        lines.append("  Traceback:")
        for line in tb_str.strip().splitlines():
            lines.append(f"    {line}")

    raw_output = "\n".join(lines)
    sanitized_output = error_detector.sanitize_text(raw_output)

    print(sanitized_output)

    if logs_folder:
        try:
            log_file = os.path.join(logs_folder, "application_errors.log")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(sanitized_output + "\n\n")
        except Exception:
            pass

    return sanitized_output

