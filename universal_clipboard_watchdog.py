# -*- coding: utf-8 -*-
"""
Universal Clipboard Collector Watchdog (万能素材剪贴板采集器高可用看门狗)
========================================================================
功能：
1. 10 秒巡检一次剪贴板采集器进程心跳与存活性；
2. 进程挂掉、被杀或异常退出时，3 秒内自动拉起自愈；
3. 检查安全暂停锁（clipboard-collector.paused），若属于历史残留或非主动暂停则自动解除并恢复；
4. 确保 Windows 全局单实例运行，静默无黑框常驻（pythonw 运行）。
"""

import os
import sys
import time
import json
import subprocess
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

WATCHDOG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WATCHDOG_DIR
LOG_FILE = PROJECT_ROOT / "collector_watchdog.log"
COLLECTOR_SCRIPT = PROJECT_ROOT / "universal_clipboard_collector.py"
LOCAL_CONFIG_FILE = WATCHDOG_DIR / "config" / "config.json"
CONFIG_FILE = (
    LOCAL_CONFIG_FILE
    if LOCAL_CONFIG_FILE.exists()
    else Path(os.environ.get("MATERIAL_HUB_CONFIG") or LOCAL_CONFIG_FILE)
)
try:
    from collector_paths import load_json_config, resolve_paths
    _paths = resolve_paths(
        config=load_json_config(CONFIG_FILE),
        code_root=WATCHDOG_DIR,
        config_dir=CONFIG_FILE.parent,
    )
    HEARTBEAT_FILE = _paths.heartbeat_file
    FAILURE_STREAK_FILE = _paths.failure_streak_file
    PAUSE_FILE = _paths.pause_file
    LOG_FILE = _paths.data_dir / "collector_watchdog.log"
except Exception:
    # Fail closed to legacy paths if the resolver/config cannot be loaded.
    HEARTBEAT_FILE = PROJECT_ROOT / "collector_heartbeat.json"
    FAILURE_STREAK_FILE = PROJECT_ROOT / "collector_failure_streak.json"
    PAUSE_FILE = Path(r"D:\AICode\运行数据\应用状态\后台服务控制\clipboard-collector.paused")
    LOG_FILE = PROJECT_ROOT / "collector_watchdog.log"
PYTHONW = r"C:\Users\z\AppData\Local\Programs\Python\Python311\pythonw.exe"
if not os.path.exists(PYTHONW):
    PYTHONW = sys.executable.replace("python.exe", "pythonw.exe")


def log(msg: str):
    now = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{now} {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _parse_iso_timestamp(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    elif len(text) >= 5 and text[-5] in {"+", "-"} and text[-4:].isdigit():
        text = text[:-2] + ":" + text[-2:]
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def is_collector_paused() -> bool:
    if not PAUSE_FILE.exists():
        return False
    try:
        content = PAUSE_FILE.read_text(encoding="utf-8").strip()
        if not content:
            # 空文件视为残留无效应清除
            PAUSE_FILE.unlink(missing_ok=True)
            log("检测到空内容的 clipboard-collector.paused 残留锁，已自动拔除")
            return False
        data = json.loads(content)
        if isinstance(data, dict):
            # 若标记了 paused 为 false，则放行
            if data.get("paused") is False:
                PAUSE_FILE.unlink(missing_ok=True)
                return False
            # 若超过 24 小时未更新的自动熔断锁，视作陈旧标记自动拔除（人工暂停或迁移锁绝不自动解除）
            if data.get("paused_by") == "auto-fail-guard":
                paused_ts = _parse_iso_timestamp(data.get("paused_at", ""))
                if paused_ts is not None and (time.time() - paused_ts) >= 86400.0:
                    PAUSE_FILE.unlink(missing_ok=True)
                    if FAILURE_STREAK_FILE.exists():
                        try:
                            s_data = json.loads(FAILURE_STREAK_FILE.read_text(encoding="utf-8"))
                            if isinstance(s_data, dict):
                                s_data["count"] = 0
                                s_data["reset_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                                FAILURE_STREAK_FILE.write_text(
                                    json.dumps(s_data, ensure_ascii=False, indent=2),
                                    encoding="utf-8",
                                )
                        except Exception:
                            pass
                    log("检测到超过 24 小时的陈旧 auto-fail-guard 熔断锁，已自动拔除并清零计数以恢复采集")
                    return False
                # 检查连续失败记录是否已被清理
                streak_file = FAILURE_STREAK_FILE
                if streak_file.exists():
                    try:
                        s_data = json.loads(streak_file.read_text(encoding="utf-8"))
                        if int(s_data.get("count", 0)) == 0:
                            PAUSE_FILE.unlink(missing_ok=True)
                            log("检测到失败计数已被清零，自动拔除旧熔断标志以恢复采集")
                            return False
                    except Exception:
                        pass
            return bool(data.get("paused", True))
    except Exception:
        pass
    return True


def is_collector_alive() -> bool:
    """检查采集器心跳与进程存活"""
    try:
        import psutil
        now = time.time()
        for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmd = " ".join(p.info['cmdline'] or [])
                if "universal_clipboard_collector" in cmd and "python" in p.info['name'].lower():
                    # 刚拉起小于 30 秒的进程处于启动初始化阶段，必须放行
                    create_time = p.info.get('create_time') or p.create_time()
                    proc_age = now - create_time
                    if proc_age < 30.0:
                        return True

                    # 超过 120 秒但缺失心跳、心跳损坏或心跳 PID 不匹配，说明进程已僵死
                    if proc_age > 120.0:
                        if not HEARTBEAT_FILE.exists():
                            log(f"采集器进程 PID={p.pid} 运行超 {int(proc_age)}s 但缺失心跳文件，终结进程自愈！")
                            p.kill()
                            return False
                        try:
                            hb = json.loads(HEARTBEAT_FILE.read_text(encoding="utf-8"))
                        except Exception:
                            log(f"采集器进程 PID={p.pid} 运行超 {int(proc_age)}s 但心跳文件损坏，终结进程自愈！")
                            p.kill()
                            return False
                        if hb.get("pid") != p.pid:
                            log(f"采集器进程 PID={p.pid} 运行超 {int(proc_age)}s 但心跳 PID={hb.get('pid')} 不匹配，终结进程自愈！")
                            p.kill()
                            return False
                        age = now - float(hb.get("timestamp", 0))
                        if age > 120.0:
                            log(f"采集器进程 PID={p.pid} 运行超 {int(proc_age)}s 但心跳已僵死 {int(age)} 秒，终结进程自愈！")
                            p.kill()
                            return False
                    return True
            except Exception:
                pass
    except Exception as e:
        log(f"进程检查异常: {e}")
    return False


def spawn_collector():
    """以独立脱壳无窗口模式启动采集器"""
    log("正在拉起 universal_clipboard_collector.py 守护进程...")
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    creationflags = (
        CREATE_NO_WINDOW
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    )
    env = os.environ.copy()
    config_path = str(CONFIG_FILE)
    if os.path.exists(config_path):
        env["MATERIAL_HUB_CONFIG"] = config_path

    try:
        p = subprocess.Popen(
            [PYTHONW, str(COLLECTOR_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True
        )
        log(f"已拉起采集器子进程 PID={p.pid}")
    except Exception as e:
        log(f"拉起采集器失败: {e}")


def main():
    # 全局互斥，确保只有唯一看门狗实例运行
    mutex_name = "Global\\Universal_Clipboard_Watchdog_Mutex"
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    h_mutex = kernel32.CreateMutexW(None, False, mutex_name)
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    log("万能素材剪贴板采集看门狗 (Universal Clipboard Watchdog) 正式启动常驻。")

    while True:
        try:
            if not is_collector_paused():
                if not is_collector_alive():
                    log("检测到剪贴板采集器离线，执行秒级自愈拉起！")
                    spawn_collector()
                    time.sleep(3.0)
            time.sleep(10.0)
        except Exception as e:
            log(f"看门狗巡检循环异常: {e}")
            time.sleep(5.0)


if __name__ == "__main__":
    main()
