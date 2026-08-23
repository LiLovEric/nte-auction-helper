import ctypes
import os
import subprocess
import sys
import traceback
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
MARKER_FILE = BASE_DIR / ".deps_ready"
ERROR_LOG = BASE_DIR / "startup_error.log"
REQUIRED_MODULES = [
    ("flask", "flask"),
    ("numpy", "numpy"),
    ("webview", "pywebview"),
    ("PIL", "pillow"),
    ("rapidocr_onnxruntime", "rapidocr-onnxruntime"),
    ("werkzeug", "werkzeug"),
]
PIP_INDEXES = [
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://pypi.org/simple",
]
PIP_TIMEOUT = "20"


def show_error(title, message):
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 16)
    except Exception:
        pass


def write_error_log(extra_text=""):
    content = traceback.format_exc()
    if extra_text:
        content = f"{extra_text}\n\n{content}"
    ERROR_LOG.write_text(content, encoding="utf-8")


def run_hidden(cmd):
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    return subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )


def missing_dependencies():
    missing = []
    for module_name, package_name in REQUIRED_MODULES:
        try:
            __import__(module_name)
        except Exception:
            missing.append((module_name, package_name))
    return missing


def install_dependencies():
    packages = sorted({package_name for _, package_name in REQUIRED_MODULES})
    wheelhouse = BASE_DIR / "wheels"
    attempts = []

    if wheelhouse.exists():
        local_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--disable-pip-version-check",
            "--timeout",
            PIP_TIMEOUT,
            *packages,
        ]
        result = run_hidden(local_cmd)
        attempts.append(("local-wheelhouse", result))
        if result.returncode == 0:
            return True, attempts

    for index_url in PIP_INDEXES:
        pip_cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--retries",
            "2",
            "--timeout",
            PIP_TIMEOUT,
            "--prefer-binary",
            "-i",
            index_url,
            *packages,
        ]
        result = run_hidden(pip_cmd)
        attempts.append((index_url, result))
        if result.returncode == 0:
            return True, attempts

    return False, attempts


def ensure_dependencies():
    if MARKER_FILE.exists() and not missing_dependencies():
        return True

    missing = missing_dependencies()
    if not missing:
        MARKER_FILE.write_text("ready\n", encoding="utf-8")
        return True

    success, attempts = install_dependencies()
    if success and not missing_dependencies():
        MARKER_FILE.write_text("ready\n", encoding="utf-8")
        return True

    log_lines = ["Missing dependencies detected:"]
    for module_name, package_name in missing:
        log_lines.append(f"- {module_name} -> {package_name}")
    for source, result in attempts:
        log_lines.append("")
        log_lines.append(f"Install attempt: {source}")
        if result.stdout:
            log_lines.append("[stdout]")
            log_lines.append(result.stdout)
        if result.stderr:
            log_lines.append("[stderr]")
            log_lines.append(result.stderr)
        log_lines.append(f"returncode={result.returncode}")
    write_error_log("\n".join(log_lines))
    show_error("Desktop App", "Dependency installation failed. See startup_error.log for details.")
    return False


def main():
    try:
        if not ensure_dependencies():
            return 1

        app_cmd = [sys.executable, str(BASE_DIR / "desktop_app.py")]
        result = run_hidden(app_cmd)
        return result.returncode or 0
    except Exception:
        write_error_log()
        show_error(
            "异环拍卖会分析工具",
            f"Desktop app failed to start.\n\nSee log:\n{ERROR_LOG}",
        )
        return False
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
