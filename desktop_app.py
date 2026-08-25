# desktop_app.py - 完整版（在创建窗口的进程内执行置顶）
import os
import subprocess
import sys
import threading
import time
import traceback
import multiprocessing
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_is_on_top = False
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


def get_window_size():
    try:
        import ctypes
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    except Exception:
        screen_w, screen_h = 1600, 900
    width = max(960, min(1320, int(screen_w * 0.78)))
    height = max(680, min(860, int(screen_h * 0.82)))
    return width, height


def write_startup_error(extra_text=""):
    log_path = BASE_DIR / "startup_error.log"
    content = traceback.format_exc()
    if extra_text:
        content = f"{extra_text}\n\n{content}"
    log_path.write_text(content, encoding="utf-8")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            f"Desktop app failed to start.\n\nSee log:\n{log_path}",
            "异环拍卖会分析工具",
            16,
        )
    except Exception:
        pass


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
    missing = missing_dependencies()
    if not missing:
        return True

    success, attempts = install_dependencies()
    if success:
        missing_after_install = missing_dependencies()
        if not missing_after_install:
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

    write_startup_error("\n".join(log_lines))
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            None,
            "Dependency installation failed. See startup_error.log for details.",
            "异环拍卖会分析工具",
            16,
        )
    except Exception:
        pass
    return False


def main():
    global _is_on_top
    
    try:
        if not ensure_dependencies():
            return 1

        from app import app
        import webview
        from werkzeug.serving import make_server
    except Exception:
        write_startup_error()
        return 1

    server = make_server("127.0.0.1", 0, app, threaded=True)
    port = server.server_port

    flask_thread = threading.Thread(target=server.serve_forever, daemon=True)
    flask_thread.start()
    time.sleep(0.8)

    width, height = get_window_size()
    
    # 创建窗口，用on_top参数
    window = webview.create_window(
        "异环拍卖会分析工具",
        f"http://127.0.0.1:{port}",
        width=width,
        height=height,
        resizable=True,
        min_size=(380, 640),
    )

    # 用pywebview自己的on_top属性切换（在创建窗口的进程内）
    import ctypes
    
    def toggle_top_in_process():
        global _is_on_top
        _is_on_top = not _is_on_top
        # 直接使用pywebview的on_top
        window.on_top = _is_on_top
        return _is_on_top
    
    # 暴露给app.py使用
    import builtins
    builtins.toggle_top_in_process = toggle_top_in_process

    webview.start()
    return 0


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        raise SystemExit(main())
    except Exception:
        write_startup_error()
        raise
