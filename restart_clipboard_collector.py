# -*- coding: utf-8 -*-
"""Safe manual restart helper for the Universal Clipboard Collector.

The batch file is intentionally a thin launcher.  This module resolves the
same runtime paths as the collector and refuses to clear the migration pause
lock.  It does not create directories or merge legacy state.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import time
from pathlib import Path

try:
    import psutil
except ImportError as exc:  # pragma: no cover
    print(f"缺少 psutil，拒绝重启: {exc}")
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parent
PYTHONW = Path(r"C:\Users\z\AppData\Local\Programs\Python\Python311\pythonw.exe")
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable.replace("python.exe", "pythonw.exe"))
LOCAL_CONFIG_PATH = ROOT / "config" / "config.json"
CONFIG_PATH = (
    LOCAL_CONFIG_PATH
    if LOCAL_CONFIG_PATH.exists()
    else Path(os.environ.get("MATERIAL_HUB_CONFIG") or LOCAL_CONFIG_PATH)
)
COLLECTOR_SCRIPT = ROOT / "universal_clipboard_collector.py"
WATCHDOG_SCRIPT = ROOT / "universal_clipboard_watchdog.py"

try:
    from collector_paths import load_json_config, resolve_paths

    PATHS = resolve_paths(
        config=load_json_config(CONFIG_PATH),
        code_root=ROOT,
        config_dir=CONFIG_PATH.parent,
    )
    PAUSE_FILE = PATHS.pause_file
    HEARTBEAT_FILE = PATHS.heartbeat_file
except Exception:
    PAUSE_FILE = Path(r"D:\AICode\运行数据\应用状态\后台服务控制\clipboard-collector.paused")
    HEARTBEAT_FILE = ROOT / "collector_heartbeat.json"


def read_pause_state() -> dict:
    if not PAUSE_FILE.exists():
        return {}
    try:
        value = json.loads(PAUSE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"   ⛔ 无法读取暂停锁，为避免误启动，本次不重启: {exc}")
        raise SystemExit(2)
    return value if isinstance(value, dict) else {}


def stop_existing_processes() -> set[int]:
    stopped: set[int] = set()
    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            command = " ".join(process.info.get("cmdline") or [])
            if "universal_clipboard_collector" in command or "universal_clipboard_watchdog" in command:
                stopped.add(int(process.pid))
                process.kill()
                try:
                    process.wait(timeout=3)
                except Exception:
                    pass
                print(f"   ✔ 已停止进程 PID={process.pid}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        except Exception:
            pass
    return stopped


def is_fresh_restart_heartbeat(
    heartbeat: dict | None,
    *,
    restart_started_at: float,
    stopped_pids: set[int],
    now: float | None = None,
    pid_exists=None,
) -> bool:
    """Ensure recovery heartbeat came from a newly started, live collector PID."""
    if not isinstance(heartbeat, dict):
        return False
    try:
        hb_ts = float(heartbeat.get("timestamp", 0))
    except (TypeError, ValueError):
        return False
    current_time = time.time() if now is None else float(now)
    if hb_ts < float(restart_started_at) or (current_time - hb_ts) > 15.0:
        return False
    hb_pid = heartbeat.get("pid")
    if type(hb_pid) is not int or hb_pid <= 0 or hb_pid in stopped_pids:
        return False
    check_pid = psutil.pid_exists if pid_exists is None else pid_exists
    try:
        return bool(check_pid(hb_pid))
    except Exception:
        return False


def main() -> int:
    print("=======================================================")
    print("  🔄 正在执行剪贴板采集器与看门狗一键重启...")
    print("=======================================================")
    print(f"   心跳真源: {HEARTBEAT_FILE}")
    state = read_pause_state()
    if state.get("paused") is True and state.get("paused_by") == "codex-migration-gate":
        print("   ⛔ 检测到项目迁移维护暂停锁；本次拒绝解除暂停或启动采集器。")
        return 3
    if PAUSE_FILE.exists():
        try:
            PAUSE_FILE.unlink()
            print("   ✔ 已清除普通暂停锁")
        except Exception as exc:
            print(f"   ⚠️ 清除普通暂停锁失败: {exc}")
            return 2

    stopped_pids = stop_existing_processes()
    time.sleep(1.0)
    restart_started_at = time.time()
    env = os.environ.copy()
    env["MATERIAL_HUB_CONFIG"] = str(CONFIG_PATH)
    creationflags = (
        getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    subprocess.Popen(
        [str(PYTHONW), str(WATCHDOG_SCRIPT)],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )

    print("3. 正在等待采集器自愈并校验心跳...", end="", flush=True)
    for _ in range(30):
        time.sleep(0.5)
        print(".", end="", flush=True)
        if not HEARTBEAT_FILE.exists():
            continue
        try:
            heartbeat = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
            if is_fresh_restart_heartbeat(
                heartbeat,
                restart_started_at=restart_started_at,
                stopped_pids=stopped_pids,
            ):
                print("\n✅ 心跳已恢复。")
                print(f"   PID: {heartbeat.get('pid')}")
                print(f"   历史: {heartbeat.get('history_len', 0)} ｜ 队列: {heartbeat.get('queue_len', 0)}")
                return 0
        except Exception:
            continue
    print("\n⚠️ 启动验证超时，请读取 doctor.py 和 heartbeat。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
