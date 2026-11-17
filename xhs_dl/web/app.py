"""xhs-dl V2 浏览器可视化界面。"""

import copy
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from ctypes import wintypes

try:
    from collector_paths import load_json_config, resolve_paths
except ImportError:  # pragma: no cover - package launch from an alternate cwd
    _app_code_root = Path(__file__).resolve().parents[2]
    if str(_app_code_root) not in sys.path:
        sys.path.insert(0, str(_app_code_root))
    from collector_paths import load_json_config, resolve_paths

from xhs_dl.core.downloader import DELAY_MODES, extract_urls_from_text
from xhs_dl import __version__
from xhs_dl.branding import APP_NAME
from xhs_dl.core.unified_downloader import UnifiedDownloader
from xhs_dl.storage import history_path


JOBS = {}
JOBS_LOCK = threading.Lock()
JOB_CONDITION = threading.Condition(JOBS_LOCK)
JOB_IDEMPOTENCY = {}
DEFAULT_OUTPUT_DIR = str(Path.home() / "Downloads")
WEB_HISTORY_FILE = Path.home() / ".xhs-dl" / "web_history.json"
WEB_HISTORY_LOCK = threading.Lock()
COLLECTION_TASKS_FILE = Path.home() / ".xhs-dl" / "collection_tasks.json"
COLLECTION_TASKS_LOCK = threading.RLock()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_APP_CONFIG_PATH = os.environ.get("MATERIAL_HUB_CONFIG", "").strip()
APP_PATHS = resolve_paths(
    config=load_json_config(_APP_CONFIG_PATH),
    code_root=PROJECT_ROOT,
    config_dir=Path(_APP_CONFIG_PATH).parent if _APP_CONFIG_PATH else None,
)
TOOLBOX_PROJECT = Path(os.environ.get("JIANGHU_TOOLBOX_ROOT", r"D:\AICode\工具开发\projects\jianghu-collector-gui"))


def _resolve_toolbox_bridge_dir():
    configured = os.environ.get("JIANGHU_BRIDGE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()

    # The Jianghu MCP client and native host must use the same isolated bridge.
    # On this workstation that value is already configured for Codex; reading
    # only this non-secret path avoids treating an old install heartbeat as live.
    config_path = Path.home() / ".codex" / "config.toml"
    try:
        config_text = config_path.read_text(encoding="utf-8-sig")
    except OSError:
        config_text = ""

    value = ""
    if config_text:
        try:
            import tomllib
        except ImportError:
            tomllib = None
        if tomllib is not None:
            try:
                config = tomllib.loads(config_text)
                value = str(
                    config.get("mcp_servers", {})
                    .get("jianghu_toolbox", {})
                    .get("env", {})
                    .get("JIANGHU_BRIDGE_DIR", "")
                ).strip()
            except (TypeError, ValueError):
                value = ""
        else:
            in_env_section = False
            for line in config_text.splitlines():
                section = line.strip()
                if section.startswith("[") and section.endswith("]"):
                    in_env_section = section == "[mcp_servers.jianghu_toolbox.env]"
                    continue
                if in_env_section:
                    match = re.match(r"\s*JIANGHU_BRIDGE_DIR\s*=\s*(.+?)\s*(?:#.*)?$", line)
                    if not match:
                        continue
                    raw_value = match.group(1).strip()
                    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
                        raw_value = raw_value[1:-1]
                    value = raw_value.strip()
                    break

    return Path(value).expanduser() if value else Path(r"D:\Program Files\江湖工具箱\MinApp")


TOOLBOX_BRIDGE_DIR = _resolve_toolbox_bridge_dir()
CLIPBOARD_QUEUE_FILE = APP_PATHS.queue_file
CLIPBOARD_HISTORY_FILE = APP_PATHS.history_file
COLLECTOR_HEARTBEAT_FILE = APP_PATHS.heartbeat_file
MAX_URLS_PER_JOB = 100
MAX_DASHBOARD_ROWS = 100


def _load_web_history():
    try:
        value = json.loads(WEB_HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)][-100:]


WEB_HISTORY = _load_web_history()


def _load_collection_tasks():
    try:
        value = json.loads(COLLECTION_TASKS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(value, list):
        return {}
    tasks = {
        str(item.get("job_id")): item
        for item in value[-100:]
        if isinstance(item, dict) and item.get("job_id")
    }
    for item in tasks.values():
        if item.get("status") in {"queued", "discovering", "download_queued"}:
            item["status"] = "unknown"
            item["message"] = "服务重启后未能确认采集进程状态；先检查工具箱任务，避免重复提交"
    return tasks


COLLECTION_TASKS = _load_collection_tasks()


def _save_collection_tasks():
    with COLLECTION_TASKS_LOCK:
        snapshot = copy.deepcopy(list(COLLECTION_TASKS.values())[-100:])
    try:
        COLLECTION_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = COLLECTION_TASKS_FILE.with_suffix(".tmp")
        temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(COLLECTION_TASKS_FILE)
    except OSError:
        pass


def _update_collection_task(job_id, **values):
    with COLLECTION_TASKS_LOCK:
        task = COLLECTION_TASKS.get(job_id)
        if task is None:
            return
        task.update(values)
        task["updated_at"] = time.time()
    _save_collection_tasks()


def _toolbox_capability_snapshot():
    cli_file = TOOLBOX_PROJECT / "jianghu_cli.py"
    status_file = TOOLBOX_BRIDGE_DIR / "bridge_status.json"
    status = "offline"
    age_seconds = None
    native = {}
    try:
        age_seconds = max(0, time.time() - status_file.stat().st_mtime)
        if age_seconds <= 5:
            native = json.loads(status_file.read_text(encoding="utf-8-sig"))
            status = "online" if isinstance(native, dict) and native.get("running") is True else "offline"
        else:
            status = "stale"
    except (OSError, ValueError, TypeError):
        pass
    return {
        "available": cli_file.is_file(),
        "status": status,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "active_platform": native.get("active_platform"),
        "verification_required": bool(native.get("verification_required")),
        "busy": bool(
            (native.get("keyword") or {}).get("is_running")
            or (native.get("single") or {}).get("busy_or_unknown")
        ),
        "supports": {
            "homepage": ["douyin"],
            "keyword": ["douyin"],
            "xiaohongshu_homepage": False,
        },
    }


def _collection_task_payload(task):
    allowed = {
        "job_id", "kind", "label", "status", "stage", "created_at", "updated_at",
        "message", "discovered_count", "download_job_id", "completion_confirmed",
        "outcome", "native_job_id",
    }
    value = {key: copy.deepcopy(task[key]) for key in allowed if key in task}
    download_job = None
    download_id = value.get("download_job_id")
    if download_id:
        with JOBS_LOCK:
            download_job = copy.deepcopy(JOBS.get(download_id))
        if download_job is None:
            with WEB_HISTORY_LOCK:
                download_job = copy.deepcopy(next(
                    (item for item in WEB_HISTORY if item.get("job_id") == download_id), None
                ))
        if download_job:
            value["download_job"] = _job_summary(download_job)
            if download_job.get("status") == "completed":
                value["status"] = "completed"
                value["message"] = (
                    f"已发现 {value.get('discovered_count', 0)} 条链接；"
                    f"下载完成，成功 {download_job.get('success', 0)} 条，"
                    f"已存在 {download_job.get('skipped', 0)} 条，失败 {download_job.get('failed', 0)} 条"
                )
            elif download_job.get("status") == "error":
                value["status"] = "error"
                value["message"] = download_job.get("error") or "统一下载任务失败"
    return value


def _python_console_executable():
    configured = os.environ.get("JIANGHU_PYTHON", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate)

    toolbox_python = TOOLBOX_PROJECT / ".venv-agent" / "Scripts" / "python.exe"
    if toolbox_python.is_file():
        return str(toolbox_python)

    current = Path(sys.executable)
    if current.name.lower() == "pythonw.exe":
        console = current.with_name("python.exe")
        if console.is_file():
            return str(console)
    return shutil.which("python.exe") or sys.executable


def _last_json_object(output):
    for line in reversed((output or "").splitlines()):
        candidate = line.strip()
        if not candidate.startswith("{"):
            continue
        try:
            value = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _queue_collection_links(task, links):
    clean_links = []
    seen = set()
    for value in links if isinstance(links, list) else []:
        urls = extract_urls_from_text(value) if isinstance(value, str) else []
        if len(urls) != 1:
            continue
        url = urls[0]
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        if (parsed.scheme.lower() not in {"http", "https"}
                or not (host == "douyin.com" or host.endswith(".douyin.com")
                        or host == "iesdouyin.com" or host.endswith(".iesdouyin.com"))
                or "/note/" not in (parsed.path or "").lower()):
            continue
        if url not in seen:
            seen.add(url)
            clean_links.append(url)
    clean_links = clean_links[:MAX_URLS_PER_JOB]
    if not clean_links:
        return None

    mode = task.get("mode", "auto")
    image_format = task.get("image_format", "keep")
    output_dir = task.get("output_dir") or DEFAULT_OUTPUT_DIR
    job_id = uuid.uuid4().hex
    now = time.time()
    with JOBS_LOCK:
        if len(JOBS) >= 50:
            oldest = min(JOBS, key=lambda key: JOBS[key]["created_at"])
            JOBS.pop(oldest, None)
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "created_at": now,
            "total": len(clean_links),
            "done": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "items": [],
            "error": "",
            "output_dir": output_dir,
            "mode": mode,
            "image_format": image_format,
            "source": task.get("kind", "collection"),
            "collection_task_id": task.get("job_id"),
        }
    threading.Thread(
        target=_run_job,
        args=(job_id, clean_links, output_dir, DELAY_MODES[mode], image_format, mode == "auto"),
        daemon=True,
    ).start()
    return job_id


def _run_collection_discovery(job_id, command):
    _update_collection_task(job_id, status="discovering", stage="browser",
                            message="正在读取公开主页或搜索列表；遇到登录/验证会安全停止")
    try:
        process = subprocess.run(
            command,
            cwd=str(TOOLBOX_PROJECT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        _update_collection_task(
            job_id, status="unknown", stage="timeout",
            message="等待超时，无法确认原生采集是否结束；先查看原生任务状态，避免重复提交",
        )
        return
    except (OSError, ValueError) as exc:
        _update_collection_task(job_id, status="error", stage="worker", message=f"无法启动采集流程：{exc}")
        return

    result = _last_json_object(process.stdout) or _last_json_object(process.stderr)
    if not result:
        details = (process.stderr or process.stdout or "").strip()
        _update_collection_task(
            job_id, status="error", stage="worker",
            message=(details[-500:] if details else f"采集流程未返回结果（退出码 {process.returncode}）"),
        )
        return

    links = result.get("discovered_links") or []
    task = None
    with COLLECTION_TASKS_LOCK:
        task = copy.deepcopy(COLLECTION_TASKS.get(job_id))
    if links and task:
        download_job_id = _queue_collection_links(task, links)
        if download_job_id:
            _update_collection_task(
                job_id,
                status="download_queued",
                stage="download",
                discovered_count=len(links),
                download_job_id=download_job_id,
                message=f"已发现 {len(links)} 条公开链接，已加入万能下载器队列",
                completion_confirmed=False,
            )
            return

    accepted = result.get("accepted") is True or result.get("outcome") == "accepted"
    status = "accepted" if accepted else (
        "completed" if result.get("success") is True else str(result.get("status") or "error")
    )
    _update_collection_task(
        job_id,
        status=status,
        stage=result.get("stage", "collection"),
        discovered_count=len(links),
        outcome=result.get("outcome", ""),
        completion_confirmed=bool(result.get("completion_confirmed")),
        native_job_id=result.get("job_id", ""),
        message=result.get("message") or "采集流程已返回",
    )


def _validate_douyin_profile(value):
    urls = extract_urls_from_text(value) if isinstance(value, str) else []
    if len(urls) != 1:
        raise ValueError("主页采集一次只填写一个抖音主页链接")
    url = urls[0]
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed_host = (
        host == "douyin.com" or host.endswith(".douyin.com")
        or host == "iesdouyin.com" or host.endswith(".iesdouyin.com")
    )
    if (parsed.scheme.lower() not in {"http", "https"} or not allowed_host
            or parsed.username is not None or parsed.password is not None
            or "/user/" not in (parsed.path or "").lower()):
        raise ValueError("请输入抖音作者主页链接（路径需包含 /user/）")
    return url


def _create_collection_task(kind, label, request, idempotency_key):
    request = copy.deepcopy(request)
    command = request.pop("_command")
    fingerprint = hashlib.sha256(
        json.dumps(request, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    with COLLECTION_TASKS_LOCK:
        if idempotency_key:
            prior = next((item for item in COLLECTION_TASKS.values()
                          if item.get("idempotency_key") == idempotency_key), None)
            if prior:
                if prior.get("fingerprint") != fingerprint:
                    return None, "幂等键已用于不同的采集请求", 409
                return _collection_task_payload(prior), None, 200
        active = next((item for item in COLLECTION_TASKS.values()
                       if item.get("status") in {"queued", "discovering"}), None)
        if active:
            return None, "已有主页或关键词发现任务正在运行，请等当前任务返回后再提交", 409

        job_id = uuid.uuid4().hex
        now = time.time()
        task = {
            "job_id": job_id,
            "kind": kind,
            "label": label,
            "status": "queued",
            "stage": "queued",
            "created_at": now,
            "updated_at": now,
            "message": "已排入发现任务",
            "discovered_count": 0,
            "download_job_id": "",
            "completion_confirmed": False,
            "fingerprint": fingerprint,
            "idempotency_key": idempotency_key,
            **request,
        }
        COLLECTION_TASKS[job_id] = task
        for old_id in list(COLLECTION_TASKS)[:-100]:
            COLLECTION_TASKS.pop(old_id, None)
    _save_collection_tasks()
    threading.Thread(
        target=_run_collection_discovery,
        args=(job_id, command),
        daemon=True,
        name=f"collection-{kind}-{job_id[:8]}",
    ).start()
    return _collection_task_payload(task), None, 202


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>xhs-dl · 无水印下载</title>
<style>
:root{--radius-xl:28px;--radius-lg:22px;--radius-md:14px;--ease:220ms ease}
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:"Microsoft YaHei UI","PingFang SC","Noto Sans CJK SC",sans-serif}
body[data-theme="neo"]{
  --bg:#e8edf3;--panel:#e2eaf2;--soft:#dce4ec;--line:#d1dbe4;
  --text:#242a31;--muted:#61758a;--primary:#263442;--primary-hover:#17222e;
  --active:#d7e4ef;--input:rgba(255,255,255,.34);--ok:#2f7b62;--bad:#a95055;
  --shadow:8px 8px 20px #c8d0d8,-8px -8px 20px #fbfdff;
  --shadow-hover:10px 10px 22px #c0c8d0,-10px -10px 22px #fff;
  --shadow-small:5px 5px 12px #c7cfd7,-5px -5px 12px #fbfdff;
  --shadow-inset:inset 3px 3px 7px #c8d0d8,inset -3px -3px 7px #f8fbfe;
}
body[data-theme="glass"]{
  --bg:#dfeaf2;--panel:rgba(235,244,249,.86);--soft:rgba(216,229,238,.72);
  --line:rgba(117,145,166,.18);--text:#102b45;--muted:#617a91;
  --primary:#2f6f9f;--primary-hover:#245c86;--active:#d6e7f8;
  --input:rgba(245,250,253,.66);--ok:#27785d;--bad:#a44d55;
  --shadow:8px 9px 20px rgba(105,132,151,.18),-5px -5px 13px rgba(255,255,255,.72);
  --shadow-hover:10px 12px 24px rgba(95,123,143,.22),-5px -5px 15px rgba(255,255,255,.78);
  --shadow-small:5px 6px 13px rgba(105,132,151,.16),-3px -3px 9px rgba(255,255,255,.68);
  --shadow-inset:inset 2px 2px 5px rgba(117,145,166,.16),inset -2px -2px 5px rgba(255,255,255,.52);
}
body{background:var(--bg);color:var(--text);padding:32px;transition:background var(--ease),color var(--ease)}
body[data-theme="glass"]:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 14% 18%,rgba(255,255,255,.55),transparent 34%),radial-gradient(circle at 84% 76%,rgba(146,181,204,.22),transparent 36%)}
.shell{position:relative;z-index:1;max-width:1480px;margin:0 auto}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;padding:4px 6px;gap:16px}
.brand{display:flex;align-items:center;gap:14px}
.mark{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;background:var(--panel);box-shadow:var(--shadow-small);font-family:Georgia,serif;font-size:21px;font-weight:700;letter-spacing:-1px}
.brand h1{font-family:Georgia,"Noto Serif SC",serif;font-size:25px;line-height:1;margin:0 0 7px;letter-spacing:-.4px}
.brand p{margin:0;color:var(--muted);font-size:13px}
.top-actions{display:flex;align-items:center;gap:10px;flex:0 0 auto}
.theme-switch,.settings-button{white-space:nowrap;border:1px solid var(--line);background:var(--panel);color:var(--text);box-shadow:var(--shadow-small);border-radius:999px;padding:10px 15px;cursor:pointer;transition:box-shadow var(--ease),transform var(--ease)}
.collector-switch{display:flex;align-items:center;gap:8px;white-space:nowrap;border:1px solid var(--line);background:var(--panel);color:var(--text);box-shadow:var(--shadow-small);border-radius:999px;padding:8px 12px;cursor:pointer;transition:box-shadow var(--ease),transform var(--ease);font:inherit;font-size:12px}
.collector-switch:hover{box-shadow:var(--shadow-hover)}.collector-switch:active{box-shadow:var(--shadow-inset);transform:translateY(1px)}.collector-switch:disabled{cursor:not-allowed;opacity:.62}
.collector-led{width:9px;height:9px;border-radius:50%;background:var(--ok);box-shadow:0 0 0 4px rgba(47,123,98,.12)}.collector-switch[aria-checked="false"] .collector-led{background:#a95055;box-shadow:0 0 0 4px rgba(169,80,85,.12)}
.theme-switch:hover{box-shadow:var(--shadow-hover)}
.settings-button:hover{box-shadow:var(--shadow-hover)}
.theme-switch:active{box-shadow:var(--shadow-inset);transform:translateY(1px)}
.settings-button:active{box-shadow:var(--shadow-inset);transform:translateY(1px)}
.workspace{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(300px,.75fr);gap:24px;align-items:start}
.app-layout{display:grid;grid-template-columns:184px minmax(0,1fr);gap:18px;align-items:start}
.side-nav{position:sticky;top:18px;display:grid;gap:8px;padding:16px 12px;border:1px solid var(--line);border-radius:22px;background:var(--panel);box-shadow:var(--shadow-small)}
.nav-caption{padding:4px 9px 7px;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.08em}
.nav-item{width:100%;display:grid;gap:4px;text-align:left;border:1px solid transparent;border-radius:14px;background:transparent;color:var(--text);padding:12px 10px;cursor:pointer;font:inherit;transition:background var(--ease),border-color var(--ease),box-shadow var(--ease)}
.nav-item span{font-size:13px;font-weight:800}.nav-item small{color:var(--muted);font-size:10px;line-height:1.4}
.nav-item:hover{background:var(--soft)}.nav-item[aria-selected="true"]{background:var(--active);border-color:var(--line);box-shadow:var(--shadow-small)}
.nav-tip{margin:8px 8px 2px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);font-size:11px;line-height:1.65}
.work-panel{display:none;min-width:0}.work-panel.active{display:block}
.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:20px}
.form-grid .wide{grid-column:1/-1}
.form-help{margin:8px 0 0;color:var(--muted);font-size:11px;line-height:1.6}
.capability-status{margin:10px 0 0;color:var(--muted);font-size:11px;line-height:1.6}
.collection-status{margin-top:16px;padding:13px 14px;border:1px solid var(--line);border-radius:14px;background:var(--soft);color:var(--muted);font-size:12px;line-height:1.65;overflow-wrap:anywhere}
.collection-status strong{display:block;margin-bottom:3px;color:var(--text);font-size:13px}
.collection-status[data-state="running"]{border-color:rgba(71,123,157,.45)}.collection-status[data-state="error"],.collection-status[data-state="verification_required"],.collection-status[data-state="login_required"]{border-color:rgba(169,80,85,.45);color:var(--bad)}
.collection-status[hidden]{display:none}
.right-stack{display:grid;gap:18px;min-width:0}
.surface{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius-xl);box-shadow:var(--shadow);padding:28px;transition:background var(--ease),box-shadow var(--ease)}
body[data-theme="glass"] .surface{backdrop-filter:blur(16px) saturate(115%);-webkit-backdrop-filter:blur(16px) saturate(115%)}
.eyebrow{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:12px;letter-spacing:.12em;text-transform:uppercase;margin-bottom:10px}
.eyebrow:before{content:"";width:24px;height:2px;border-radius:2px;background:var(--primary)}
h2{font-family:Georgia,"Noto Serif SC",serif;font-size:29px;line-height:1.28;margin:0 0 10px;letter-spacing:-.5px}
.lead{margin:0 0 24px;color:var(--muted);line-height:1.75;font-size:14px}
label{display:block;font-size:13px;font-weight:700;margin-bottom:9px}
textarea,input,select{width:100%;border:1px solid var(--line);background:var(--input);color:var(--text);border-radius:var(--radius-md);outline:none;box-shadow:var(--shadow-inset);transition:border-color var(--ease),box-shadow var(--ease);font:inherit}
textarea{min-height:218px;padding:17px;resize:vertical;line-height:1.72}
input,select{height:46px;padding:0 13px}
textarea:focus,input:focus,select:focus{border-color:#6f9ab8;box-shadow:var(--shadow-inset),0 0 0 3px rgba(75,129,168,.15)}
textarea::placeholder,input::placeholder{color:#8092a2}
.settings{display:grid;grid-template-columns:minmax(220px,1fr) 160px 190px;gap:14px;padding:2px 14px 14px}
.settings-dialog{width:min(460px,calc(100vw - 32px));max-width:none;max-height:min(88vh,640px);overflow:auto;border:1px solid var(--line);border-radius:24px;background:var(--panel);color:var(--text);padding:24px;box-shadow:var(--shadow-hover)}
.settings-dialog::backdrop{background:rgba(22,34,46,.30);backdrop-filter:blur(3px)}
.settings-dialog[open]{animation:modal-in 150ms ease-out}
.dialog-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:22px}
.dialog-heading h2{font-size:23px;margin:0}
.dialog-heading p{margin:0 0 7px;color:var(--muted);font-size:12px}
.settings-dialog .settings{grid-template-columns:1fr;gap:16px;padding:0}
.settings-dialog .settings-note{margin:18px 0 0;padding:0;color:var(--muted);font-size:12px;line-height:1.7}
.dialog-actions{display:flex;justify-content:flex-end;margin-top:22px}
.dialog-close,.dialog-done{border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--text);padding:9px 15px;cursor:pointer;box-shadow:var(--shadow-small);font:inherit}
.dialog-close{width:36px;height:36px;padding:0;font-size:20px;line-height:1}
.dialog-done{min-width:92px;font-weight:700}
.primary{width:100%;height:52px;margin-top:20px;border:0;border-radius:16px;background:var(--primary);color:#f7fafc;font-size:15px;font-weight:800;letter-spacing:.04em;cursor:pointer;box-shadow:0 10px 22px rgba(38,52,66,.2);transition:background var(--ease),transform var(--ease),box-shadow var(--ease)}
.primary:hover{background:var(--primary-hover);transform:translateY(-1px);box-shadow:0 12px 26px rgba(38,52,66,.25)}
.primary:active{transform:translateY(1px);box-shadow:0 5px 12px rgba(38,52,66,.22)}
.primary:disabled{cursor:not-allowed;opacity:.58;transform:none;box-shadow:none}
.privacy{display:flex;gap:10px;margin-top:16px;color:var(--muted);font-size:12px;line-height:1.65}
.shield{flex:0 0 25px;height:25px;border-radius:9px;display:grid;place-items:center;background:var(--active);font-size:12px}
.settings-note{margin:2px 0 0;padding:0 14px 14px;color:var(--muted);font-size:11px;line-height:1.65}
.waiting-card,.queue-card,.history-card{padding:22px 24px}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
.panel-title{font-size:16px;font-weight:800;margin:0}.panel-sub{font-size:12px;color:var(--muted);margin:6px 0 0;line-height:1.55}
.count-badge{min-width:42px;height:34px;padding:0 10px;display:grid;place-items:center;border-radius:12px;background:var(--active);color:var(--text);font-size:18px;font-weight:800;box-shadow:var(--shadow-small)}
.queue-list,.history-list{display:flex;flex-direction:column;gap:9px;margin-top:15px;max-height:220px;overflow:auto;padding:2px 4px 2px 1px}
.history-more{margin-top:12px;border:1px solid var(--line);border-radius:12px;background:var(--panel);color:var(--text);padding:9px 13px;cursor:pointer;box-shadow:var(--shadow-small);font:inherit;font-size:12px}.history-more:hover{box-shadow:var(--shadow-hover)}.history-more:disabled{cursor:wait;opacity:.65}
.task-row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border:1px solid var(--line);border-radius:13px;background:var(--soft);font-size:12px;line-height:1.45}
.task-main{min-width:0;flex:1}.task-title{display:block;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-meta{display:block;color:var(--muted);margin-top:3px;font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.task-location{display:block;color:var(--muted);margin-top:4px;font-size:11px;line-height:1.45;white-space:normal;overflow-wrap:anywhere}.history-row{align-items:flex-start}.history-row .task-state{padding-top:2px}.task-state{flex:0 0 auto;color:var(--muted);font-size:11px}.task-state.ok{color:var(--ok)}.task-state.fail{color:var(--bad)}
.panel-empty{padding:13px 4px 2px;color:var(--muted);font-size:12px}
.status-card{min-height:420px;display:flex;flex-direction:column}
.status-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.state-dot{width:11px;height:11px;border-radius:999px;background:#8da0af;box-shadow:0 0 0 6px rgba(141,160,175,.12);margin-top:6px;transition:background var(--ease)}
.state-dot.running{background:#477b9d;animation:pulse 1.8s infinite}
.state-dot.done{background:var(--ok);box-shadow:0 0 0 6px rgba(47,123,98,.12)}
.state-dot.error{background:var(--bad);box-shadow:0 0 0 6px rgba(169,80,85,.12)}
.status-title{font-size:17px;font-weight:800;margin:0}.status-sub{font-size:12px;color:var(--muted);margin:6px 0 0}
.progress-wrap{margin:24px 0 18px}.progress-track{height:9px;border-radius:999px;background:var(--soft);box-shadow:var(--shadow-inset);overflow:hidden}
.progress-bar{height:100%;width:0;background:linear-gradient(90deg,#426f8d,#6b91aa);border-radius:inherit;transition:width 520ms ease}
.progress-bar.active{width:38%;animation:travel 1.1s ease-in-out infinite}
.progress-meta{display:flex;justify-content:space-between;margin-top:9px;color:var(--muted);font-size:12px}
.empty{margin:auto 0;text-align:center;color:var(--muted);padding:34px 16px}
.empty-symbol{width:72px;height:72px;border-radius:24px;margin:0 auto 18px;display:grid;place-items:center;background:var(--panel);box-shadow:var(--shadow-small);font-family:Georgia,serif;font-size:28px;color:#6d8192}
.empty strong{display:block;color:var(--text);font-size:14px;margin-bottom:8px}
.results{display:none;gap:10px;flex-direction:column;max-height:330px;overflow:auto;padding:4px 5px 4px 2px}
.results.show{display:flex}.result{padding:13px 14px;border-radius:14px;background:var(--soft);border:1px solid var(--line);font-size:13px;line-height:1.55}
.result-top{display:flex;justify-content:space-between;gap:10px}.result-name{font-weight:700;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.result-count{white-space:nowrap;color:var(--muted);font-size:12px}
.result.ok{border-left:3px solid var(--ok)}.result.fail{border-left:3px solid var(--bad)}
.result-error{color:var(--bad);font-size:12px;margin-top:4px}
.footnote{text-align:center;color:var(--muted);font-size:11px;margin-top:22px;line-height:1.7}
button:focus-visible,textarea:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid rgba(47,111,159,.32);outline-offset:3px}
@keyframes pulse{0%,100%{box-shadow:0 0 0 5px rgba(71,123,157,.13)}50%{box-shadow:0 0 0 10px rgba(71,123,157,.04)}}
@keyframes travel{0%{transform:translateX(-110%)}50%{transform:translateX(80%)}100%{transform:translateX(280%)}}
@keyframes modal-in{from{opacity:0;transform:translateY(8px) scale(.985)}to{opacity:1;transform:translateY(0) scale(1)}}
@media(max-width:980px){.app-layout{grid-template-columns:1fr}.side-nav{position:static;grid-template-columns:1fr}.nav-items{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.nav-tip{grid-column:1/-1;margin-top:3px}}
@media(max-width:760px){body{padding:18px 14px}.workspace{grid-template-columns:1fr}.surface{padding:20px;border-radius:22px}.settings{grid-template-columns:1fr}.topbar{align-items:flex-start}.brand p{max-width:210px}.status-card{min-height:330px}}
@media(max-width:480px){.topbar{gap:10px}.brand{min-width:0;gap:10px}.brand p{display:none}.mark{width:40px;height:40px;border-radius:13px;font-size:18px}.brand h1{font-size:22px;margin:9px 0 0}.theme-switch,.settings-button{padding:9px 11px;font-size:12px}.collector-switch{padding:8px 9px;font-size:11px;gap:6px}.surface{padding:18px}textarea{min-height:190px}.side-nav{padding:11px 9px}.nav-items{gap:5px}.nav-item{padding:10px 7px}.nav-item span{font-size:11px}.nav-item small{font-size:9px}.form-grid{grid-template-columns:1fr}.form-grid .wide{grid-column:auto}}
@media(prefers-reduced-motion:reduce){*,*:before,*:after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){body[data-theme="glass"] .surface{background:#edf4f8}}
</style>
</head>
<body data-theme="neo">
<main class="shell">
  <header class="topbar">
    <div class="brand"><div class="mark">∞</div><div><h1>__APP_NAME__</h1><p>多平台公开媒体 · 本地保存 · 无需登录</p></div></div>
    <div class="top-actions"><button class="collector-switch" id="collectorToggle" type="button" role="switch" aria-checked="true" aria-label="剪贴板单链接采集开关" title="独立后台监控剪贴板；每条复制内容只采集一条链接"><span class="collector-led" aria-hidden="true"></span><span id="collectorToggleText">剪贴板采集 开</span></button><button class="settings-button" id="settingsButton" type="button" aria-haspopup="dialog" aria-controls="settingsDialog">设置</button><button class="theme-switch" id="themeButton" type="button" aria-label="切换视觉主题">玻璃主题</button></div>
  </header>
  <div class="app-layout">
    <aside class="side-nav" aria-label="采集入口">
      <div class="nav-caption">采集入口</div>
      <div class="nav-items" role="tablist" aria-orientation="vertical">
        <button class="nav-item" id="tabSingle" type="button" role="tab" aria-selected="true" aria-controls="singlePanel" data-view="single"><span>单作品采集</span><small>万能下载器</small></button>
        <button class="nav-item" id="tabHomepage" type="button" role="tab" aria-selected="false" aria-controls="homepagePanel" data-view="homepage"><span>主页采集</span><small>发现主页公开图文</small></button>
        <button class="nav-item" id="tabKeyword" type="button" role="tab" aria-selected="false" aria-controls="keywordPanel" data-view="keyword"><span>关键词采集</span><small>发现抖音公开图文</small></button>
      </div>
      <p class="nav-tip">剪贴板是独立后台入口，每次只处理一条链接；下载成功后与手动下载共用本机查重和历史。</p>
    </aside>
  <section class="workspace">
    <section class="surface work-panel active" id="singlePanel" role="tabpanel" aria-labelledby="tabSingle" data-panel="single">
      <div class="eyebrow">Original media</div>
      <h2>粘贴链接，保存原图。</h2>
      <p class="lead">当前万能下载器入口。手动粘贴支持单条或多条公开链接；右上角剪贴板后台仍按每次一条链接采集。默认保存到电脑的“下载”文件夹。</p>
      <label for="input">分享文本或链接</label>
      <textarea id="input" placeholder="例如：复制小红书或抖音分享文本到这里，也可以一次粘贴多条链接。"></textarea>
      <button class="primary" id="go" type="button">开始下载</button>
      <div class="privacy"><span class="shield">✓</span><span>公开笔记无需账号、密码或 Cookie。链接默认只交给本机引擎，不会静默发送到在线解析网站。</span></div>
    </section>
    <section class="surface work-panel" id="homepagePanel" role="tabpanel" aria-labelledby="tabHomepage" data-panel="homepage" hidden>
      <div class="eyebrow">Homepage collection</div>
      <h2>从主页发现公开图文。</h2>
      <p class="lead">填写一个抖音作者主页。发现的作品会加入右侧同一万能下载队列，沿用保存位置、原格式、查重和历史记录。</p>
      <label for="authorUrl">抖音作者主页链接</label>
      <textarea id="authorUrl" style="min-height:112px" placeholder="https://www.douyin.com/user/…"></textarea>
      <p class="form-help">默认读取主页前 10 条可见图文。需要登录或遇到验证时会停止，并提示你在原生浏览器处理。</p>
      <p class="capability-status" id="homepageCapability" role="status">正在读取江湖工具箱状态…</p>
      <div class="collection-status" id="homepageStatus" role="status" aria-live="polite" hidden></div>
      <button class="primary" id="startHomepage" type="button">采集主页并加入下载队列</button>
      <div class="privacy"><span class="shield">✓</span><span>目前主页发现支持抖音公开页面；小红书主页采集未接入此入口。</span></div>
    </section>
    <section class="surface work-panel" id="keywordPanel" role="tabpanel" aria-labelledby="tabKeyword" data-panel="keyword" hidden>
      <div class="eyebrow">Keyword collection</div>
      <h2>按关键词发现图文。</h2>
      <p class="lead">搜索列表只读取公开图文卡片，不打开详情页。发现的作品加入同一个万能下载器队列。</p>
      <div class="form-grid">
        <div class="wide"><label for="keywordValue">关键词</label><input id="keywordValue" type="text" maxlength="100" placeholder="例如：江浙沪团建"></div>
        <div><label for="keywordCount">目标作品数</label><input id="keywordCount" type="number" min="1" max="30" value="20"></div>
        <div><label for="minImages">最少图片数</label><input id="minImages" type="number" min="0" max="50" value="4"></div>
        <div class="wide"><label for="maxImages">最多图片数</label><input id="maxImages" type="number" min="0" max="50" value="20"></div>
      </div>
      <p class="form-help">一次提交一个关键词，最多发现 30 条；默认只采图文，图片张数筛选为 4–20 张。</p>
      <p class="capability-status" id="keywordCapability" role="status">正在读取江湖工具箱状态…</p>
      <div class="collection-status" id="keywordStatus" role="status" aria-live="polite" hidden></div>
      <button class="primary" id="startKeyword" type="button">发现图文并加入下载队列</button>
      <div class="privacy"><span class="shield">✓</span><span>目前此面板接入抖音列表流程。遇到登录或人机验证会停下；不会绕过验证。小红书关键词仍需其原生核心，不从这里跨平台补采。</span></div>
    </section>
    <aside class="right-stack" aria-live="polite">
      <section class="surface waiting-card">
        <div class="panel-head"><div><p class="panel-title">等待任务</p><p class="panel-sub" id="waitingSub">当前没有排队的下载</p></div><span class="count-badge" id="waitingCount">0</span></div>
      </section>
      <section class="surface status-card">
        <div class="status-head"><div><p class="status-title" id="statusTitle">正在进行的任务</p><p class="status-sub" id="statusSub">还没有开始下载</p></div><span class="state-dot" id="stateDot"></span></div>
        <div class="progress-wrap"><div class="progress-track"><div class="progress-bar" id="progressBar"></div></div><div class="progress-meta"><span id="progressText">0 / 0</span><span id="successText">成功 0</span></div></div>
        <div class="empty" id="empty"><div class="empty-symbol">↓</div><strong>结果会在这里逐条出现</strong><span>关闭页面不会删除已经保存到本地的文件。</span></div>
        <div class="results" id="results"></div>
      </section>
      <section class="surface queue-card">
        <div class="panel-head"><div><p class="panel-title">排队任务</p><p class="panel-sub" id="queueSub">读取本机下载队列和剪贴板队列</p></div></div>
        <div class="queue-list" id="queueList"><div class="panel-empty">暂无排队任务</div></div>
      </section>
      <section class="surface history-card">
        <div class="panel-head"><div><p class="panel-title">历史下载记录</p><p class="panel-sub" id="historySub">正在读取本机下载档案</p></div></div>
        <div class="history-list" id="historyList"><div class="panel-empty">暂无历史记录</div></div>
        <button class="history-more" id="historyMore" type="button" hidden>加载更多历史记录</button>
      </section>
    </aside>
  </section>
  </div>
  <p class="footnote">仅处理你有权保存的公开内容 · 创作者嵌入原图的署名会保留 · __APP_NAME__ V__APP_VERSION__</p>
</main>
<dialog class="settings-dialog" id="settingsDialog" aria-labelledby="settingsTitle">
  <div class="dialog-heading"><div><p>本机下载偏好</p><h2 id="settingsTitle">下载设置</h2></div><button class="dialog-close" id="settingsClose" type="button" aria-label="关闭设置">×</button></div>
  <div class="settings">
    <div><label for="outdir">保存位置</label><input id="outdir" type="text" autocomplete="off"></div>
    <div><label for="mode">下载节奏</label><select id="mode"><option value="auto" selected>智能 · 随结果调节</option><option value="fast">快速 · 3–8 秒</option><option value="normal">标准 · 8–15 秒</option><option value="cautious">稳妥 · 35–55 秒</option><option value="slow">慢速 · 55–85 秒</option><option value="very-slow">极慢 · 110–160 秒</option></select></div>
    <div><label for="format">图片格式</label><select id="format"><option value="keep" selected>保持原格式（推荐）</option><option value="jpg">JPG</option><option value="png">PNG（无损）</option></select></div>
  </div>
  <p class="settings-note">修改后会自动保存在本机。其他本机软件也可调用 <code>POST /api/v1/jobs</code>；<a href="/api/openapi.json" target="_blank" rel="noreferrer">查看接口规范</a>。</p>
  <div class="dialog-actions"><button class="dialog-done" id="settingsDone" type="button">完成</button></div>
</dialog>
<script>
const THEME_KEY='xhs-dl-theme',OUTPUT_KEY='xhs-dl-output',MODE_KEY='xhs-dl-mode',FORMAT_KEY='xhs-dl-format',DEFAULT_OUTPUT=__DEFAULT_OUTPUT_JSON__,MIN_PROGRESS_MS=1100;
const $=id=>document.getElementById(id);let activeJob=null,pollTimer=null,jobStartedAt=0,collectorEnabled=true,collectorOnline=false,collectorStartingUntil=0,historyItems=[],historyOffset=0,historyTotal=0;
function applyTheme(theme){const next=theme==='glass'?'glass':'neo';document.body.dataset.theme=next;localStorage.setItem(THEME_KEY,next);$('themeButton').textContent=next==='neo'?'玻璃主题':'拟态主题'}
applyTheme(localStorage.getItem(THEME_KEY)||'neo');
$('themeButton').addEventListener('click',()=>applyTheme(document.body.dataset.theme==='neo'?'glass':'neo'));
const settingsDialog=$('settingsDialog');
$('settingsButton').addEventListener('click',()=>settingsDialog.showModal());
$('settingsClose').addEventListener('click',()=>settingsDialog.close());
$('settingsDone').addEventListener('click',()=>settingsDialog.close());
settingsDialog.addEventListener('click',event=>{if(event.target===settingsDialog)settingsDialog.close()});
$('outdir').value=localStorage.getItem(OUTPUT_KEY)||DEFAULT_OUTPUT;
if(localStorage.getItem(MODE_KEY)==='cautious')localStorage.setItem(MODE_KEY,'auto');
if(localStorage.getItem(FORMAT_KEY)==='jpg')localStorage.setItem(FORMAT_KEY,'keep');
$('mode').value=localStorage.getItem(MODE_KEY)||'auto';$('format').value=localStorage.getItem(FORMAT_KEY)||'keep';
$('outdir').addEventListener('change',e=>localStorage.setItem(OUTPUT_KEY,e.target.value.trim()));$('mode').addEventListener('change',e=>localStorage.setItem(MODE_KEY,e.target.value));$('format').addEventListener('change',e=>localStorage.setItem(FORMAT_KEY,e.target.value));
function setState(status,title,sub){$('stateDot').className='state-dot '+status;$('statusTitle').textContent=title;$('statusSub').textContent=sub}
function render(job){const total=job.total||0,done=job.done||0,success=job.success||0,running=job.status==='running'||job.status==='queued';$('progressBar').classList.toggle('active',running&&done===0);if(!(running&&done===0)){$('progressBar').style.transform='none';$('progressBar').style.width=(total?Math.round(done/total*100):0)+'%'}$('progressText').textContent=`${done} / ${total}`;$('successText').textContent=`成功 ${success}`;
  const items=job.items||[];$('empty').style.display=items.length?'none':'block';$('results').classList.toggle('show',items.length>0);$('results').innerHTML='';items.forEach(it=>{const d=document.createElement('div');d.className='result '+(it.deduplicated?'ok':it.success?'ok':'fail');const top=document.createElement('div');top.className='result-top';const name=document.createElement('span');name.className='result-name';name.textContent=it.title||it.error||'未命名作品';const count=document.createElement('span');count.className='result-count';count.textContent=it.deduplicated?'已存在 · 跳过':it.success?`${it.image_success||0} 张`:'失败';top.append(name,count);d.append(top);if(!it.success&&!it.deduplicated&&it.error){const err=document.createElement('div');err.className='result-error';err.textContent=it.error;d.append(err)}$('results').append(d)});
  const skipped=job.skipped||0;if(job.status==='queued')setState('running','等待执行',total?`排队中，共 ${total} 条`:'等待本地引擎');else if(job.status==='running')setState('running','正在逐条提取',total?`已完成 ${done} 条，共 ${total} 条`:'正在准备本地引擎');else if(job.status==='completed')setState(job.failed?'error':'done',job.failed?'任务完成，有失败项':skipped&&!(job.success||0)?'重复项已跳过':skipped?'任务完成（含重复项跳过）':'全部保存完成',`成功 ${job.success||0} 条，跳过 ${skipped} 条，失败 ${job.failed||0} 条`);else if(job.status==='error')setState('error','任务没有完成',job.error||'请稍后重试')}
function renderRows(target,list,kind){target.innerHTML='';if(!list||!list.length){const empty=document.createElement('div');empty.className='panel-empty';empty.textContent=kind==='history'?'还没有本地成功下载记录':'当前队列为空';target.append(empty);return}list.forEach(job=>{const row=document.createElement('div');row.className='task-row'+(kind==='history'?' history-row':'');const main=document.createElement('div');main.className='task-main';const title=document.createElement('span');title.className='task-title';const first=(job.items||[])[0];title.textContent=job.title||job.title_hint||(first&&first.title)||(job.url||`任务 ${String(job.job_id||'').slice(0,8)}`);const meta=document.createElement('span');meta.className='task-meta';if(kind==='history'){const parts=[];if(job.completed_at)parts.push(job.completed_at);if(job.note_id)parts.push(`笔记 ${job.note_id}`);meta.textContent=parts.join(' · ')||job.url||'旧记录未保存时间'}else if(job.note_id)meta.textContent=`笔记 ${job.note_id}`;else if(job.retry_count)meta.textContent=`${job.url||''} · 已重试 ${job.retry_count} 次`;else if(job.url)meta.textContent=job.url;else meta.textContent=`${job.done||0} / ${job.total||0} 条 · 成功 ${job.success||0}`;main.append(title,meta);if(kind==='history'){const location=document.createElement('span');location.className='task-location';location.textContent=job.save_dir?`保存位置：${job.save_dir}`:'旧记录位置未登记（未找到可确认的素材目录）';if(job.save_dir)location.title=job.save_dir;main.append(location)}const state=document.createElement('span');const status=job.status||'';const ok=kind==='history'||status==='completed'||status==='success';const failed=status==='error'||status==='failed';state.className='task-state '+(ok?'ok':failed?'fail':'');state.textContent=kind==='history'?'已保存':status==='running'?'进行中':status==='cooling_down'?'冷却中':failed?'失败':'等待';row.append(main,state);target.append(row)})}
function updateCollectorSwitch(collector){collectorEnabled=collector.enabled!==false;collectorOnline=collector.online===true;if(collectorOnline)collectorStartingUntil=0;const control=$('collectorToggle');control.setAttribute('aria-checked',String(collectorEnabled));control.disabled=collector.control_available===false;const starting=!collectorOnline&&collectorStartingUntil>Date.now();const label=starting?'剪贴板采集 启动中':collectorOnline?(collectorEnabled?'剪贴板采集 开':'剪贴板采集 关'):'剪贴板采集 离线';$('collectorToggleText').textContent=label;const state=collectorOnline?'在线':collector.status==='offline'?'离线':'';control.title=`${label}${state?` · 守护进程${state}`:''}${!collectorOnline?' · 点击启动': ''}${collector.pause_reason?` · ${collector.pause_reason}`:''}`}
function historyKey(item){return String(item.job_id||item.url||item.note_id||'')}
function updateHistoryFromDashboard(data){const incoming=data.history||[],counts=data.counts||{},collector=data.collector||{};let changed=false;if(!historyItems.length){historyItems=incoming;historyOffset=incoming.length;changed=true}else{const seen=new Set(historyItems.map(historyKey));const added=incoming.filter(item=>!seen.has(historyKey(item)));if(added.length){historyItems=[...added,...historyItems];historyOffset+=added.length;changed=true}}historyTotal=counts.download_history||0;if(changed){const list=$('historyList'),oldHeight=list.scrollHeight,oldTop=list.scrollTop;renderRows(list,historyItems,'history');if(oldHeight&&oldTop)list.scrollTop=Math.min(list.scrollHeight-list.clientHeight,oldTop+Math.max(0,list.scrollHeight-oldHeight))}$('historySub').textContent=`显示 ${Math.min(historyOffset,historyTotal)} / ${historyTotal} 条共享成功记录 · 剪贴板历史 ${collector.history_count||0} 条`;$('historyMore').hidden=historyOffset>=historyTotal;$('historyMore').textContent=`加载更多（剩余 ${Math.max(0,historyTotal-historyOffset)} 条）`}
async function loadMoreHistory(){const button=$('historyMore');if(button.disabled||historyOffset>=historyTotal)return;button.disabled=true;const oldText=button.textContent;button.textContent='正在读取…';try{const requestOffset=historyOffset;const r=await fetch(`/api/v1/jobs?limit=50&history_offset=${requestOffset}`);const data=await r.json();if(!r.ok)throw new Error(data.error||'读取历史失败');const page=data.history||[],seen=new Set(historyItems.map(historyKey)),added=page.filter(item=>!seen.has(historyKey(item)));historyItems=historyItems.concat(added);historyOffset=requestOffset+page.length;historyTotal=data.counts?.download_history??historyTotal;renderRows($('historyList'),historyItems,'history');$('historySub').textContent=`显示 ${Math.min(historyOffset,historyTotal)} / ${historyTotal} 条共享成功记录 · 剪贴板历史 ${data.collector?.history_count||0} 条`;button.hidden=historyOffset>=historyTotal;button.textContent=`加载更多（剩余 ${Math.max(0,historyTotal-historyOffset)} 条）`}catch(e){button.textContent='读取失败，点击重试';button.title=e.message}finally{button.disabled=false;if(!button.hidden&&button.textContent==='正在读取…')button.textContent=oldText}}
async function toggleCollector(){const control=$('collectorToggle'),enable=!collectorEnabled||!collectorOnline;control.disabled=true;try{const r=await fetch('/api/v1/collector',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:enable})});const data=await r.json();if(!r.ok)throw new Error(data.error||'剪贴板采集设置失败');collectorEnabled=Boolean(data.enabled);if(data.starting)collectorStartingUntil=Date.now()+15000;updateCollectorSwitch({...data,control_available:true});refreshDashboard()}catch(e){setState('error','剪贴板开关未生效',e.message);control.disabled=false}}
async function refreshDashboard(){try{const r=await fetch('/api/v1/jobs?limit=50&history_offset=0');if(!r.ok)return;const data=await r.json();const counts=data.counts||{},collector=data.collector||{};updateCollectorSwitch(collector);updateHistoryFromDashboard(data);const waiting=data.waiting||[];const queue=data.queue||waiting;const running=data.running||[];$('waitingCount').textContent=counts.waiting??waiting.length;$('waitingSub').textContent=waiting.length?`有 ${waiting.length} 条任务等待 · 剪贴板 ${collector.pending_count||0} 条`:'当前队列为空 · 剪贴板待采集 0 条';$('queueSub').textContent=`剪贴板队列 ${collector.pending_count||0} 条 · 失败归档 ${collector.failed_archive_count||0} 条（不在等待队列）`;renderRows($('queueList'),queue,'queue');if(activeJob)return;if(running.length){const current=running[0];if(current.source==='clipboard'){setState('running','剪贴板正在采集',current.title||current.url||'正在处理当前链接');$('progressBar').classList.add('active');$('progressText').textContent='采集进行中';$('successText').textContent='';$('empty').style.display='none';$('results').classList.remove('show')}else setState('running','正在逐条提取',`任务进行中，共 ${current.total||0} 条`);return}if(collector.status==='offline'){setState('error','剪贴板采集器离线',collector.last_heartbeat?`最近心跳：${collector.last_heartbeat}`:'没有可用心跳');$('progressBar').classList.remove('active')}else if(collector.status==='paused'){setState('','剪贴板采集已暂停',collector.pending_count?`仍有 ${collector.pending_count} 条等待恢复`:'当前没有等待任务');$('progressBar').classList.remove('active')}else if(collector.status==='cooling'){setState('running','采集器冷却中',collector.cooldown_remaining_seconds?`约 ${collector.cooldown_remaining_seconds} 秒后继续 · ${collector.cooldown_reason||'按限速策略等待'}`:'按限速策略等待');$('progressBar').classList.add('active')}else{setState('done','当前没有进行中的下载',collector.status==='idle'?'下载器已就绪，采集器空闲':'等待任务启动');$('progressBar').classList.remove('active')}}catch(_){}}
$('collectorToggle').addEventListener('click',toggleCollector);
$('historyMore').addEventListener('click',loadMoreHistory);
function finish(){activeJob=null;$('go').disabled=false;$('go').textContent='开始下载';refreshDashboard()}
async function poll(){if(!activeJob)return;try{const r=await fetch('/api/jobs/'+activeJob);const job=await r.json();if(!r.ok)throw new Error(job.error||'读取任务失败');if(job.status==='completed'||job.status==='error'){const wait=Math.max(0,MIN_PROGRESS_MS-(Date.now()-jobStartedAt));if(wait){pollTimer=setTimeout(()=>{render(job);finish()},wait);return}render(job);finish();return}render(job);refreshDashboard();pollTimer=setTimeout(poll,700)}catch(e){setState('error','连接中断',e.message);$('progressBar').classList.remove('active');$('go').disabled=false;$('go').textContent='重新开始';activeJob=null}}
async function start(){if(activeJob)return;const text=$('input').value.trim();if(!text){$('input').focus();setState('error','还缺少分享文本','请先粘贴至少一条公开媒体链接');return}const output_dir=$('outdir').value.trim()||DEFAULT_OUTPUT,mode=$('mode').value,image_format=$('format').value;localStorage.setItem(OUTPUT_KEY,output_dir);localStorage.setItem(MODE_KEY,mode);localStorage.setItem(FORMAT_KEY,image_format);jobStartedAt=Date.now();$('go').disabled=true;$('go').textContent='正在准备…';$('progressBar').classList.add('active');$('progressBar').style.width='38%';$('progressText').textContent='准备中';$('successText').textContent='';$('results').innerHTML='';$('results').classList.remove('show');$('empty').style.display='block';setState('running','正在准备','连接本地无水印引擎');try{const r=await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,output_dir,mode,image_format})});const data=await r.json();if(!r.ok)throw new Error(data.error||'创建任务失败');activeJob=data.job_id;$('go').textContent='下载进行中';poll()}catch(e){$('progressBar').classList.remove('active');setState('error','无法开始',e.message);$('go').disabled=false;$('go').textContent='重新开始'}}
function activateView(name){document.querySelectorAll('[data-view]').forEach(tab=>{const active=tab.dataset.view===name;tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1});document.querySelectorAll('[data-panel]').forEach(panel=>{const active=panel.dataset.panel===name;panel.classList.toggle('active',active);panel.hidden=!active});localStorage.setItem('xhs-dl-active-view',name)}
document.querySelectorAll('[data-view]').forEach(tab=>{tab.addEventListener('click',()=>activateView(tab.dataset.view));tab.addEventListener('keydown',event=>{if(!['ArrowDown','ArrowUp','ArrowRight','ArrowLeft'].includes(event.key))return;event.preventDefault();const tabs=[...document.querySelectorAll('[data-view]')],index=tabs.indexOf(tab),delta=['ArrowDown','ArrowRight'].includes(event.key)?1:-1,next=tabs[(index+delta+tabs.length)%tabs.length];activateView(next.dataset.view);next.focus()})});
activateView(['single','homepage','keyword'].includes(localStorage.getItem('xhs-dl-active-view'))?localStorage.getItem('xhs-dl-active-view'):'single');
const collectionPollTimers={};
function collectionSettings(){const output_dir=$('outdir').value.trim()||DEFAULT_OUTPUT,mode=$('mode').value,image_format=$('format').value;localStorage.setItem(OUTPUT_KEY,output_dir);localStorage.setItem(MODE_KEY,mode);localStorage.setItem(FORMAT_KEY,image_format);return{output_dir,mode,image_format}}
function setCollectionStatus(kind,task,errorText=''){const box=$(kind==='homepage'?'homepageStatus':'keywordStatus');box.hidden=false;box.replaceChildren();const title=document.createElement('strong');const message=document.createElement('span');const state=errorText?'error':task?.status||'error';box.dataset.state=state;if(errorText){title.textContent='未能提交';message.textContent=errorText}else{const names={queued:'已排队',discovering:'正在发现公开作品',download_queued:'已进入下载队列',completed:'下载完成',accepted:'原生工具已接收',unknown:'状态待确认',verification_required:'需要人工验证',login_required:'需要登录',completed_zero:'没有发现作品',error:'采集失败'};title.textContent=names[state]||'采集状态';let detail=task.message||'正在读取状态';if(task.download_job){const job=task.download_job;detail+=` · 下载 ${job.done||0}/${job.total||0}，成功 ${job.success||0}，跳过 ${job.skipped||0}，失败 ${job.failed||0}`}if(task.discovered_count)detail=`发现 ${task.discovered_count} 条。${detail}`;if(state==='accepted'&&!task.discovered_count)detail+='；完成情况尚未确认，请在江湖工具箱任务里查看后再决定是否重试';message.textContent=detail}box.append(title,message);if(task?.download_job_id){const link=document.createElement('button');link.type='button';link.className='history-more';link.textContent='查看统一下载队列';link.addEventListener('click',()=>{activateView('single');$('queueList').scrollIntoView({behavior:'smooth',block:'center'})});box.append(link)}}
async function pollCollection(kind,jobId){try{const response=await fetch('/api/v1/collections/jobs/'+encodeURIComponent(jobId)),task=await response.json();if(!response.ok)throw new Error(task.error||'读取采集状态失败');setCollectionStatus(kind,task);if(['queued','discovering','download_queued'].includes(task.status)){collectionPollTimers[kind]=setTimeout(()=>pollCollection(kind,jobId),1200);return}sessionStorage.setItem('xhs-dl-collection-last-'+kind,jobId);if(task.status!=='unknown')sessionStorage.removeItem('xhs-dl-collection-key-'+kind)}catch(error){setCollectionStatus(kind,null,error.message)}}
async function startCollection(kind){const button=$(kind==='homepage'?'startHomepage':'startKeyword'),box=$(kind==='homepage'?'homepageStatus':'keywordStatus');if(button.disabled)return;let request;if(kind==='homepage'){const profile_url=$('authorUrl').value.trim();if(!profile_url){$('authorUrl').focus();setCollectionStatus(kind,null,'请填写一个抖音作者主页链接');return}request={profile_url,...collectionSettings()}}else{const keyword=$('keywordValue').value.trim(),count=Number($('keywordCount').value),min_images=Number($('minImages').value),max_images=Number($('maxImages').value);if(!keyword){$('keywordValue').focus();setCollectionStatus(kind,null,'请填写一个关键词');return}request={keyword,count,min_images,max_images,...collectionSettings()}}const endpoint='/api/v1/collections/'+kind,fingerprint=JSON.stringify(request),cacheKey='xhs-dl-collection-key-'+kind;let cached;try{cached=JSON.parse(sessionStorage.getItem(cacheKey)||'null')}catch(_){}if(!cached||cached.fingerprint!==fingerprint){cached={fingerprint,key:`${kind}-${crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random().toString(16).slice(2)}`};sessionStorage.setItem(cacheKey,JSON.stringify(cached))}button.disabled=true;button.textContent='正在提交…';setCollectionStatus(kind,{status:'queued',message:'正在连接本地采集流程'});try{const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':cached.key},body:JSON.stringify(request)}),task=await response.json();if(!response.ok)throw new Error(task.error||'提交失败');sessionStorage.setItem('xhs-dl-collection-last-'+kind,task.job_id);if(collectionPollTimers[kind])clearTimeout(collectionPollTimers[kind]);await pollCollection(kind,task.job_id);refreshDashboard()}catch(error){setCollectionStatus(kind,null,error.message)}finally{button.disabled=false;button.textContent=kind==='homepage'?'采集主页并加入下载队列':'发现图文并加入下载队列'}}
async function loadLastCollection(kind){const jobId=sessionStorage.getItem('xhs-dl-collection-last-'+kind);if(jobId){setCollectionStatus(kind,{status:'queued',message:'正在读取最近任务'});await pollCollection(kind,jobId)}}
async function refreshCollectionCapabilities(){const targets=[$('homepageCapability'),$('keywordCapability')];try{const response=await fetch('/api/v1/collections/capabilities'),data=await response.json();let message;if(!data.available)message='未找到江湖工具箱采集接口。';else if(data.status!=='online')message=`江湖工具箱当前${data.status==='stale'?'心跳已过期':'离线'}；打开工具箱后即可使用此入口。`;else if(data.verification_required)message='原生浏览器正在等待人工验证；完成后再提交采集。';else if(data.active_platform!=='douyin')message='当前原生核心不是抖音；请先在江湖工具箱切换到抖音。';else if(data.busy)message='原生采集任务正在运行或状态待确认；请先查看现有任务。';else message='抖音原生采集在线。发现链接后会送入本页的万能下载器队列。';targets.forEach(target=>target.textContent=message)}catch(_){targets.forEach(target=>target.textContent='暂时无法读取江湖工具箱状态；提交时会再次检查。')}}
$('startHomepage').addEventListener('click',()=>startCollection('homepage'));$('startKeyword').addEventListener('click',()=>startCollection('keyword'));
loadLastCollection('homepage');loadLastCollection('keyword');refreshCollectionCapabilities();setInterval(refreshCollectionCapabilities,5000);
$('go').addEventListener('click',start);$('input').addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')start()});refreshDashboard();setInterval(refreshDashboard,2500);
</script>
</body>
</html>"""


def _item_payload(item):
    return {
        "success": item.success,
        "deduplicated": item.deduplicated,
        "title": item.title,
        "error": item.error,
        "image_count": item.image_count,
        "image_success": item.image_success,
        "save_dir": item.save_dir,
        "note_id": item.note_id,
    }


def _job_summary(job):
    """Return the small, safe shape used by the queue and history panels."""
    return {
        "job_id": job.get("job_id", ""),
        "status": job.get("status", ""),
        "created_at": job.get("created_at", 0),
        "finished_at": job.get("finished_at", 0),
        "total": job.get("total", 0),
        "done": job.get("done", 0),
        "success": job.get("success", 0),
        "failed": job.get("failed", 0),
        "skipped": job.get("skipped", 0),
        "output_dir": job.get("output_dir", ""),
        "error": job.get("error", ""),
        "items": [
            {
                "success": item.get("success", False),
                "deduplicated": item.get("deduplicated", False),
                "title": item.get("title", ""),
                "error": item.get("error", ""),
                "image_success": item.get("image_success", 0),
            }
            for item in (job.get("items") or [])[-8:]
            if isinstance(item, dict)
        ],
    }


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _collector_pause_file(heartbeat=None):
    heartbeat = heartbeat if isinstance(heartbeat, dict) else _read_json(COLLECTOR_HEARTBEAT_FILE, {})
    configured = os.environ.get("COLLECTOR_PAUSE_FILE") or heartbeat.get("pause_file")
    if configured:
        return Path(configured).expanduser()
    workspace_root = next(
        (parent for parent in (PROJECT_ROOT, *PROJECT_ROOT.parents) if (parent / "routes.json").is_file()),
        None,
    )
    if workspace_root:
        return workspace_root / "运行数据" / "应用状态" / "后台服务控制" / "clipboard-collector.paused"
    return APP_PATHS.pause_file


def _collector_pause_state(heartbeat=None):
    pause_file = _collector_pause_file(heartbeat)
    try:
        content = json.loads(pause_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        content = {}
    return pause_file, pause_file.exists(), str(content.get("reason") or "") if isinstance(content, dict) else ""


def _collector_pid_alive(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() == 5  # Access denied: conservatively assume it still exists.
    try:
        exit_code = wintypes.DWORD()
        return bool(kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))) and exit_code.value == 259
    finally:
        kernel32.CloseHandle(handle)


def _start_collector_if_stopped():
    heartbeat = _read_json(COLLECTOR_HEARTBEAT_FILE, {})
    pid = heartbeat.get("pid") if isinstance(heartbeat, dict) else None
    try:
        age = time.time() - float(heartbeat.get("timestamp"))
    except (TypeError, ValueError):
        age = None
    if age is not None and 0 <= age <= 45 and _collector_pid_alive(pid):
        return False
    if _collector_pid_alive(pid):
        raise OSError("采集器心跳已过期，但原进程仍在；为避免重复启动，先保留该进程")

    script = PROJECT_ROOT / "clipboard_xhs_auto_collector.py"
    if not script.is_file():
        raise FileNotFoundError(f"找不到剪贴板采集器入口：{script}")
    env = os.environ.copy()
    config_path = env.get("MATERIAL_HUB_CONFIG", "")
    if not config_path:
        launcher = PROJECT_ROOT / "XHS-Clipboard-Collector.vbs"
        try:
            launcher_text = launcher.read_text(encoding="utf-8-sig")
            match = re.search(
                r'ProcessEnvironment\("MATERIAL_HUB_CONFIG"\)\s*=\s*"([^"]+)"',
                launcher_text,
                flags=re.IGNORECASE,
            )
            config_path = match.group(1) if match else ""
        except OSError:
            config_path = ""
    if config_path:
        if not Path(config_path).is_file():
            raise FileNotFoundError(f"剪贴板采集配置不存在：{config_path}")
        env["MATERIAL_HUB_CONFIG"] = config_path

    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [sys.executable, str(script)],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
    return True


def _set_collector_enabled(enabled):
    pause_file, paused, _reason = _collector_pause_state()
    started = False
    if enabled:
        if paused:
            try:
                pause_state = json.loads(pause_file.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as exc:
                raise OSError(f"暂停锁无法读取，拒绝恢复采集：{exc}") from exc
            if not isinstance(pause_state, dict):
                raise OSError("暂停锁格式无效，拒绝恢复采集")
            if pause_state.get("paused") is True and pause_state.get("paused_by") == "codex-migration-gate":
                raise PermissionError("项目迁移维护暂停期间，不能从界面恢复剪贴板采集")
            pause_file.unlink()
        started = _start_collector_if_stopped()
    else:
        pause_file.parent.mkdir(parents=True, exist_ok=True)
        if not paused:
            pause_file.write_text(
                json.dumps(
                    {
                        "paused": True,
                        "paused_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "paused_by": "universal-downloader-ui",
                        "reason": "用户在万能下载器界面暂停剪贴板采集",
                        "resume": "在万能下载器界面恢复剪贴板采集即可继续；待采集队列会保留。",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
    return not pause_file.exists(), started


def _collector_snapshot():
    queue_data = _read_json(CLIPBOARD_QUEUE_FILE, {})
    heartbeat = _read_json(COLLECTOR_HEARTBEAT_FILE, {})
    clipboard_history = _read_json(CLIPBOARD_HISTORY_FILE, {})
    queue = queue_data.get("queue", []) if isinstance(queue_data, dict) else []
    failed = queue_data.get("failed", []) if isinstance(queue_data, dict) else []
    queue = [item for item in queue if isinstance(item, dict)] if isinstance(queue, list) else []
    failed = [item for item in failed if isinstance(item, dict)] if isinstance(failed, list) else []

    timestamp = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
    try:
        age = max(0.0, time.time() - float(timestamp))
    except (TypeError, ValueError):
        age = None
    pid = heartbeat.get("pid") if isinstance(heartbeat, dict) else None
    fresh = age is not None and age <= 45.0 and bool(pid)
    raw_extra = heartbeat.get("extra", "") if isinstance(heartbeat, dict) else ""
    extra = {}
    if isinstance(raw_extra, dict):
        extra = raw_extra
    elif isinstance(raw_extra, str) and raw_extra.lstrip().startswith("{"):
        try:
            parsed = json.loads(raw_extra)
            if isinstance(parsed, dict):
                extra = parsed
        except ValueError:
            pass

    current_url = str(extra.get("current_url") or "")
    current_title = str(extra.get("current_title") or "")
    current = None
    if fresh and heartbeat.get("status") == "downloading":
        matched = next((item for item in queue if item.get("url") == current_url), None)
        if matched is None and queue:
            matched = queue[0]
        if matched:
            current = {
                "job_id": matched.get("id", ""),
                "title": current_title or matched.get("title_hint") or "正在采集",
                "url": matched.get("url", ""),
                "status": "running",
                "source": "clipboard",
                "retry_count": matched.get("retry_count", 0),
            }
            queue = [item for item in queue if item.get("id") != matched.get("id")]
    elif fresh and current_url:
        current = {
            "job_id": "clipboard-current",
            "title": current_title or heartbeat.get("extra", "剪贴板采集任务"),
            "url": current_url,
            "status": "running",
            "source": "clipboard",
        }

    try:
        remaining = max(0, float(queue_data.get("cooldown_until", 0) or 0) - time.time()) if isinstance(queue_data, dict) else 0
    except (TypeError, ValueError):
        remaining = 0
    pause_file, marker_paused, pause_reason = _collector_pause_state(heartbeat)
    paused = marker_paused or (fresh and heartbeat.get("status") == "paused")
    if not fresh:
        status = "offline"
    elif paused:
        status = "paused"
    elif heartbeat.get("status") == "cooling" or remaining > 0:
        status = "cooling"
    elif current:
        status = "downloading"
    else:
        status = "idle"

    urls = clipboard_history.get("urls", []) if isinstance(clipboard_history, dict) else []
    return {
        "status": status,
        "online": fresh,
        "paused": paused,
        "enabled": not paused,
        "control_available": True,
        "control_file": str(pause_file),
        "pause_reason": pause_reason,
        "heartbeat_age_seconds": round(age, 1) if age is not None else None,
        "last_heartbeat": heartbeat.get("last_heartbeat", "") if isinstance(heartbeat, dict) else "",
        "pid": pid,
        "current": current,
        "pending": [
            {
                "job_id": item.get("id", ""),
                "title": item.get("title_hint") or "剪贴板采集任务",
                "url": item.get("url", ""),
                "status": item.get("status", "pending"),
                "source": "clipboard",
                "retry_count": item.get("retry_count", 0),
                "last_error": item.get("last_error") or "",
            }
            for item in queue[:MAX_DASHBOARD_ROWS]
        ],
        "pending_count": len(queue),
        "failed_archive_count": len(failed),
        "history_count": len(urls) if isinstance(urls, list) else 0,
        "cooldown_remaining_seconds": round(remaining),
        "cooldown_reason": str(queue_data.get("cooldown_reason", "") or "") if isinstance(queue_data, dict) else "",
    }


def _download_history(limit=MAX_DASHBOARD_ROWS, offset=0):
    entries = _read_json(history_path(), [])
    if not isinstance(entries, list):
        return [], 0
    rows = []
    for item in reversed(entries):
        if not isinstance(item, dict):
            continue
        url = item.get("下载网址") or item.get("url") or ""
        rows.append(
            {
                "job_id": item.get("笔记ID") or url,
                "note_id": item.get("笔记ID") or "",
                "title": item.get("标题") or "未命名作品",
                "url": url,
                "completed_at": item.get("下载时间") or item.get("completed_at") or "",
                "save_dir": item.get("保存位置") or item.get("save_dir") or "",
                "status": "completed",
                "source": "downloader-history",
            }
        )
    return rows[offset : offset + limit], len(rows)


def _dashboard_payload(limit=50, history_offset=0):
    with JOBS_LOCK:
        current_jobs = [copy.deepcopy(value) for value in JOBS.values()]
    current_jobs.sort(key=lambda item: item.get("created_at", 0))
    web_waiting = [
        {**_job_summary(job), "source": "web"}
        for job in current_jobs
        if job.get("status") == "queued"
    ]
    web_running = [
        {**_job_summary(job), "source": "web"}
        for job in current_jobs
        if job.get("status") == "running"
    ]
    with WEB_HISTORY_LOCK:
        web_history = copy.deepcopy(list(reversed(WEB_HISTORY[-limit:])))

    collector = _collector_snapshot()
    downloads, download_count = _download_history(limit, history_offset)
    clipboard_waiting = collector["pending"]
    waiting = web_waiting + clipboard_waiting
    running = web_running + ([collector["current"]] if collector["current"] else [])
    return {
        "waiting": waiting,
        "running": running,
        "queue": waiting,
        "history": downloads,
        "history_offset": history_offset,
        "history_has_more": history_offset + len(downloads) < download_count,
        "web_history": web_history,
        "collector": collector,
        "counts": {
            "waiting": len(waiting),
            "running": len(running),
            "history": download_count,
            "download_history": download_count,
            "web_history": len(WEB_HISTORY),
            "clipboard_history": collector["history_count"],
            "clipboard_failed_archive": collector["failed_archive_count"],
        },
        "history_limit": limit,
    }


def _openapi_document():
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "万能下载器本地 API",
            "version": __version__,
            "description": "供本机 AI、脚本和桌面应用提交公开媒体下载任务并读取真实进度。默认只监听本机回环地址。",
        },
        "servers": [{"url": "http://127.0.0.1:5678"}],
        "paths": {
            "/api/v1/capabilities": {
                "get": {
                    "summary": "读取下载器能力和默认设置",
                    "responses": {"200": {"description": "支持的平台、格式和接口信息", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Capabilities"}}}}},
                }
            },
            "/api/v1/health": {
                "get": {
                    "summary": "检查本地 API 是否可用",
                    "responses": {"200": {"description": "服务健康状态", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Health"}}}}},
                }
            },
            "/api/v1/collections/capabilities": {
                "get": {
                    "summary": "读取主页和关键词采集能力及原生在线状态",
                    "responses": {"200": {"description": "当前工具箱能力和心跳状态"}},
                }
            },
            "/api/v1/collections/homepage": {
                "post": {
                    "summary": "发现抖音主页公开图文并加入统一下载队列",
                    "parameters": [{"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "maxLength": 128}}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["profile_url"], "properties": {"profile_url": {"type": "string", "format": "uri"}, "output_dir": {"type": "string"}, "mode": {"type": "string", "enum": ["auto", "fast", "normal", "cautious", "slow", "very-slow"]}, "image_format": {"type": "string", "enum": ["keep", "jpg", "png"]}}}}}},
                    "responses": {"202": {"description": "主页发现任务已排队；随后下载任务进入统一任务列表"}, "200": {"description": "幂等请求返回原任务"}, "400": {"description": "主页链接或保存设置无效"}, "409": {"description": "原生验证中、平台不符或另一个发现任务正在运行"}, "503": {"description": "江湖工具箱离线或未安装"}},
                }
            },
            "/api/v1/collections/keyword": {
                "post": {
                    "summary": "发现抖音关键词公开图文并加入统一下载队列",
                    "parameters": [{"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "maxLength": 128}}],
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object", "required": ["keyword"], "properties": {"keyword": {"type": "string", "maxLength": 100}, "count": {"type": "integer", "minimum": 1, "maximum": 30, "default": 20}, "min_images": {"type": "integer", "minimum": 0, "maximum": 50, "default": 4}, "max_images": {"type": "integer", "minimum": 0, "maximum": 50, "default": 20}, "output_dir": {"type": "string"}, "mode": {"type": "string", "enum": ["auto", "fast", "normal", "cautious", "slow", "very-slow"]}, "image_format": {"type": "string", "enum": ["keep", "jpg", "png"]}}}}}},
                    "responses": {"202": {"description": "关键词发现任务已排队；随后下载任务进入统一任务列表"}, "200": {"description": "幂等请求返回原任务"}, "400": {"description": "关键词、筛选或保存设置无效"}, "409": {"description": "原生验证中、平台不符或另一个发现任务正在运行"}, "503": {"description": "江湖工具箱离线或未安装"}},
                }
            },
            "/api/v1/collections/jobs/{job_id}": {
                "get": {
                    "summary": "读取主页或关键词发现任务，并回读对应统一下载进度",
                    "parameters": [{"name": "job_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "发现阶段状态和关联下载任务摘要"}, "404": {"description": "采集任务不存在"}},
                }
            },
            "/api/v1/jobs": {
                "get": {
                    "summary": "读取等待、进行中、剪贴板队列与本机成功历史",
                    "parameters": [
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50}},
                        {"name": "history_offset", "in": "query", "schema": {"type": "integer", "minimum": 0, "default": 0}, "description": "下载历史偏移量，用于逐页查看全部共享历史。"},
                    ],
                    "responses": {"200": {"description": "合并后的本机任务看板", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Dashboard"}}}}},
                },
                "post": {
                    "summary": "提交一个或多个公开媒体链接",
                    "parameters": [{"name": "Idempotency-Key", "in": "header", "required": False, "schema": {"type": "string", "maxLength": 128}, "description": "可选；同一服务进程内避免网络重试造成重复提交，保留 24 小时。"}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateJobRequest"},
                                "examples": {
                                    "url-list": {"value": {"urls": ["https://example.com/public-media"], "image_format": "keep", "mode": "auto"}},
                                    "share-text": {"value": {"text": "复制的分享文案和链接", "image_format": "keep", "mode": "auto"}},
                                },
                            }
                        },
                    },
                    "responses": {
                        "202": {"description": "已接收；使用响应中的 job_id 继续轮询任务状态。", "headers": {"Location": {"description": "任务状态资源路径。", "schema": {"type": "string"}}, "Retry-After": {"description": "建议轮询间隔，秒。", "schema": {"type": "integer"}}}, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AcceptedJob"}}}},
                        "200": {"description": "同一个幂等键已提交过，返回原任务。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/AcceptedJob"}}}},
                        "400": {"description": "请求内容无效或未检测到链接。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                        "409": {"description": "幂等键已用于不同的请求内容。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                        "413": {"description": "请求文本超过 1 MiB 或单批超过 100 条链接。", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}},
                    },
                },
            },
            "/api/v1/jobs/{job_id}": {
                "get": {
                    "summary": "轮询单个下载任务",
                    "parameters": [{"name": "job_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "任务进度和已完成条目", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/JobStatus"}}}}, "404": {"description": "任务不存在", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ApiError"}}}}},
                }
            },
            "/api/v1/collector": {
                "post": {
                    "summary": "暂停、恢复或启动剪贴板守护进程",
                    "description": "通过守护进程共用的暂停标记控制采集；若恢复时原进程已退出，则启动同一个采集器入口并保留单实例互斥；正在执行的单条下载会先完成，待采集队列会保留。",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"type": "object", "required": ["enabled"], "properties": {"enabled": {"type": "boolean"}}}}},
                    },
                    "responses": {"200": {"description": "开关状态已更新；starting 表示正在启动离线采集器"}, "400": {"description": "enabled 必须是布尔值"}, "503": {"description": "本机暂停标记或采集器启动失败"}},
                }
            },
        },
        "components": {
            "schemas": {
                "CreateJobRequest": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "整段分享文案或一个/多个链接。"},
                        "urls": {"type": "array", "items": {"type": "string", "format": "uri"}, "maxItems": 100},
                        "output_dir": {"type": "string", "description": "本机保存目录；省略时使用下载文件夹。"},
                        "mode": {"type": "string", "enum": ["auto", "fast", "normal", "cautious", "slow", "very-slow"], "default": "auto"},
                        "image_format": {"type": "string", "enum": ["keep", "jpg", "png"], "default": "keep"},
                    },
                    "anyOf": [{"required": ["text"]}, {"required": ["urls"]}],
                },
                "AcceptedJob": {
                    "type": "object",
                    "required": ["job_id", "status", "total"],
                    "properties": {"job_id": {"type": "string"}, "status": {"type": "string", "enum": ["queued", "running", "completed", "error"]}, "total": {"type": "integer", "minimum": 0}, "deduplicated": {"type": "boolean"}},
                },
                "JobStatus": {
                    "type": "object",
                    "required": ["job_id", "status", "total"],
                    "properties": {
                        "job_id": {"type": "string"}, "status": {"type": "string", "enum": ["queued", "running", "completed", "error"]},
                        "created_at": {"type": "number"}, "finished_at": {"type": "number"}, "total": {"type": "integer", "minimum": 0},
                        "done": {"type": "integer", "minimum": 0}, "success": {"type": "integer", "minimum": 0}, "failed": {"type": "integer", "minimum": 0}, "skipped": {"type": "integer", "minimum": 0},
                        "items": {"type": "array", "items": {"type": "object", "properties": {"success": {"type": "boolean"}, "deduplicated": {"type": "boolean"}, "note_id": {"type": "string"}, "title": {"type": "string"}, "error": {"type": "string"}, "save_dir": {"type": "string"}, "image_success": {"type": "integer"}}, "additionalProperties": True}}, "error": {"type": "string"}, "output_dir": {"type": "string"},
                    },
                },
                "TaskSummary": {
                    "type": "object", "additionalProperties": True,
                    "properties": {"job_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"}, "status": {"type": "string"}, "source": {"type": "string"}, "completed_at": {"type": "string"}},
                },
                "Dashboard": {
                    "type": "object",
                    "required": ["waiting", "running", "queue", "history", "collector", "counts"],
                    "properties": {
                        "waiting": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "running": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "queue": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "history": {"type": "array", "items": {"$ref": "#/components/schemas/TaskSummary"}},
                        "web_history": {"type": "array", "items": {"$ref": "#/components/schemas/JobStatus"}},
                        "collector": {"type": "object", "additionalProperties": True},
                        "counts": {"type": "object", "properties": {"waiting": {"type": "integer"}, "running": {"type": "integer"}, "history": {"type": "integer"}, "download_history": {"type": "integer"}, "web_history": {"type": "integer"}, "clipboard_history": {"type": "integer"}, "clipboard_failed_archive": {"type": "integer"}}, "additionalProperties": True},
                        "history_limit": {"type": "integer"},
                        "history_offset": {"type": "integer", "minimum": 0},
                        "history_has_more": {"type": "boolean"},
                    },
                },
                "Capabilities": {
                    "type": "object", "required": ["api_version", "transport", "endpoints"],
                    "properties": {"name": {"type": "string"}, "version": {"type": "string"}, "api_version": {"type": "string"}, "transport": {"type": "string"}, "auth": {"type": "string"}, "platforms": {"type": "array", "items": {"type": "string"}}, "image_formats": {"type": "array", "items": {"type": "string"}}, "default_image_format": {"type": "string"}, "default_mode": {"type": "string"}, "endpoints": {"type": "object", "additionalProperties": {"type": "string"}}},
                },
                "Health": {"type": "object", "required": ["status", "name", "version"], "properties": {"status": {"type": "string"}, "name": {"type": "string"}, "version": {"type": "string"}}},
                "ApiError": {"type": "object", "required": ["error"], "properties": {"error": {"type": "string"}, "supported_modes": {"type": "array", "items": {"type": "string"}}}},
            }
        },
    }


def _save_web_history():
    with WEB_HISTORY_LOCK:
        snapshot = copy.deepcopy(WEB_HISTORY[-100:])
    try:
        WEB_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = WEB_HISTORY_FILE.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(WEB_HISTORY_FILE)
    except OSError:
        # Download results should never fail because the optional UI history
        # file is unavailable or read-only.
        pass


def _record_web_history(job):
    if not job:
        return
    summary = _job_summary(job)
    with WEB_HISTORY_LOCK:
        WEB_HISTORY[:] = [
            value for value in WEB_HISTORY if value.get("job_id") != summary["job_id"]
        ]
        WEB_HISTORY.append(summary)
        del WEB_HISTORY[:-100]
    _save_web_history()


def _update_job(job_id, **values):
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)


def _run_job(job_id, urls, output_dir, delay, image_format, adaptive=False):
    # Run one download job at a time.  This keeps the original UI's queue
    # meaningful and avoids turning a burst of pasted links into concurrent
    # requests against a public platform.
    with JOB_CONDITION:
        while True:
            job = JOBS.get(job_id)
            if job is None:
                return
            running = any(
                value.get("status") == "running"
                for key, value in JOBS.items()
                if key != job_id
            )
            if not running:
                job["status"] = "running"
                break
            JOB_CONDITION.wait(timeout=0.5)

    def on_progress(item, index, total):
        with JOBS_LOCK:
            job = JOBS[job_id]
            job["items"].append(_item_payload(item))
            job["done"] = index
            job["success"] = sum(1 for value in job["items"] if value["success"])
            job["skipped"] = sum(1 for value in job["items"] if value.get("deduplicated"))
            job["failed"] = index - job["success"] - job["skipped"]

    try:
        downloader = UnifiedDownloader(
            output_dir=output_dir,
            delay=delay,
            on_progress=on_progress,
            image_format=image_format,
            adaptive=adaptive,
        )
        result = downloader.download(urls)
        _update_job(
            job_id,
            status="completed",
            finished_at=time.time(),
            done=result.total,
            success=result.success_count,
            failed=result.fail_count,
            skipped=result.skipped_count,
            output_dir=result.output_dir,
        )
    except Exception as exc:
        _update_job(job_id, status="error", finished_at=time.time(), error=str(exc))
    finally:
        with JOBS_LOCK:
            finished = copy.deepcopy(JOBS.get(job_id))
        if finished and finished.get("status") in {"completed", "error"}:
            _record_web_history(finished)
        with JOB_CONDITION:
            JOB_CONDITION.notify_all()


class Handler(BaseHTTPRequestHandler):
    """HTTP 请求处理。"""

    def _api_path(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/v1/"):
            return "/api/" + path[len("/api/v1/"):]
        return path

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = self._api_path()
        if path in ("/", "/index.html"):
            html = TEMPLATE.replace(
                "__DEFAULT_OUTPUT_JSON__",
                json.dumps(DEFAULT_OUTPUT_DIR, ensure_ascii=False),
            ).replace("__APP_VERSION__", __version__).replace("__APP_NAME__", APP_NAME)
            self._html(html)
            return
        if path == "/api/openapi.json":
            self._json(_openapi_document())
            return
        if path == "/api/health":
            self._json({"status": "ok", "name": APP_NAME, "version": __version__})
            return
        if path == "/api/capabilities":
            self._json(
                {
                    "name": APP_NAME,
                    "version": __version__,
                    "api_version": "v1",
                    "transport": "local-http",
                    "auth": "local-only; service binds to loopback",
                    "platforms": ["xiaohongshu", "douyin", "public-media"],
                    "image_formats": ["keep", "jpg", "png"],
                    "default_image_format": "keep",
                    "default_mode": "auto",
                    "endpoints": {
                        "submit": "POST /api/v1/jobs",
                        "job": "GET /api/v1/jobs/<job_id>",
                        "dashboard": "GET /api/v1/jobs",
                        "clipboard_control": "POST /api/v1/collector",
                        "collection_capabilities": "GET /api/v1/collections/capabilities",
                        "homepage_collection": "POST /api/v1/collections/homepage",
                        "keyword_collection": "POST /api/v1/collections/keyword",
                        "collection_job": "GET /api/v1/collections/jobs/<job_id>",
                        "openapi": "GET /api/openapi.json",
                    },
                }
            )
            return
        if path == "/api/collections/capabilities":
            self._json(_toolbox_capability_snapshot())
            return
        if path.startswith("/api/collections/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with COLLECTION_TASKS_LOCK:
                task = copy.deepcopy(COLLECTION_TASKS.get(job_id))
            if task is None:
                self._json({"error": "采集任务不存在"}, 404)
            else:
                self._json(_collection_task_payload(task))
            return
        if path == "/api/jobs":
            try:
                query = parse_qs(parsed.query)
                limit = max(1, min(int(query.get("limit", ["50"])[0]), MAX_DASHBOARD_ROWS))
                history_offset = max(0, int(query.get("history_offset", ["0"])[0]))
            except (TypeError, ValueError):
                limit = 50
                history_offset = 0
            self._json(_dashboard_payload(limit, history_offset))
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            with JOBS_LOCK:
                job = copy.deepcopy(JOBS.get(job_id))
            if job is None:
                with WEB_HISTORY_LOCK:
                    job = copy.deepcopy(next((value for value in WEB_HISTORY if value.get("job_id") == job_id), None))
            if job is None:
                self._json({"error": "任务不存在"}, 404)
            else:
                self._json(job)
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        api_path = self._api_path()
        if api_path in {"/api/collections/homepage", "/api/collections/keyword"}:
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > 64 * 1024:
                    self._json({"error": "请求内容过大"}, 413)
                    return
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "请求格式无效"}, 400)
                return
            if not isinstance(body, dict):
                self._json({"error": "请求内容必须是 JSON 对象"}, 400)
                return

            capability = _toolbox_capability_snapshot()
            if not capability["available"]:
                self._json({"error": "没有找到江湖工具箱采集接口"}, 503)
                return
            if capability["status"] != "online":
                self._json({"error": "江湖工具箱原生采集模块当前不在线；本次没有启动采集"}, 503)
                return
            if capability["verification_required"]:
                self._json({"error": "原生浏览器正在等待人工验证；完成验证后再提交"}, 409)
                return
            if capability["active_platform"] != "douyin":
                self._json({"error": "当前原生核心不是抖音；请先在江湖工具箱切换到抖音"}, 409)
                return
            if capability["busy"]:
                self._json({"error": "原生采集任务仍在运行或状态待确认；先核对现有任务，避免重复启动"}, 409)
                return

            output_dir = body.get("output_dir") or DEFAULT_OUTPUT_DIR
            mode = body.get("mode", "auto")
            image_format = body.get("image_format", "keep")
            if not isinstance(output_dir, str) or not output_dir.strip() or len(output_dir) > 4096:
                self._json({"error": "保存位置格式无效"}, 400)
                return
            if not isinstance(mode, str) or mode not in DELAY_MODES:
                self._json({"error": "下载节奏无效"}, 400)
                return
            if not isinstance(image_format, str) or image_format not in {"keep", "jpg", "png"}:
                self._json({"error": "图片格式无效"}, 400)
                return

            if api_path.endswith("/homepage"):
                try:
                    profile_url = _validate_douyin_profile(body.get("profile_url", ""))
                except ValueError as exc:
                    self._json({"error": str(exc)}, 400)
                    return
                command = [
                    _python_console_executable(), str(TOOLBOX_PROJECT / "jianghu_cli.py"),
                    "--bridge-dir", str(TOOLBOX_BRIDGE_DIR), "--timeout", "60",
                    "extract-author", "--url", profile_url, "--no-auto-download",
                ]
                kind = "homepage"
                label = "抖音主页"
                request = {
                    "profile_url": profile_url,
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                    "_command": command,
                }
            else:
                keyword = body.get("keyword", "")
                if not isinstance(keyword, str) or not keyword.strip() or len(keyword.strip()) > 100 or "\n" in keyword or "\r" in keyword:
                    self._json({"error": "请填写一个不超过 100 个字符的关键词"}, 400)
                    return
                count = body.get("count", 20)
                min_images = body.get("min_images", 4)
                max_images = body.get("max_images", 20)
                if (isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 30
                        or isinstance(min_images, bool) or not isinstance(min_images, int)
                        or isinstance(max_images, bool) or not isinstance(max_images, int)
                        or not 0 <= min_images <= max_images <= 50):
                    self._json({"error": "数量需为 1–30；图片范围需满足 0 ≤ 最小张数 ≤ 最大张数 ≤ 50"}, 400)
                    return
                command = [
                    _python_console_executable(), str(TOOLBOX_PROJECT / "jianghu_cli.py"),
                    "--bridge-dir", str(TOOLBOX_BRIDGE_DIR), "--timeout", "60",
                    "extract-keyword", "--platform", "douyin", "--keyword", keyword.strip(),
                    "--count", str(count), "--min-images", str(min_images),
                    "--max-images", str(max_images), "--metadata-only",
                ]
                kind = "keyword"
                label = f"抖音关键词：{keyword.strip()}"
                request = {
                    "keyword": keyword.strip(),
                    "count": count,
                    "min_images": min_images,
                    "max_images": max_images,
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                    "_command": command,
                }

            idempotency_key = self.headers.get("Idempotency-Key", "").strip()
            if len(idempotency_key) > 128:
                self._json({"error": "Idempotency-Key 最长 128 个字符"}, 400)
                return
            task, error, code = _create_collection_task(kind, label, request, idempotency_key)
            if error:
                self._json({"error": error}, code)
                return
            self._json(
                task,
                code,
                {"Location": f"/api/v1/collections/jobs/{task['job_id']}", "Retry-After": "2"},
            )
            return
        if api_path == "/api/collector":
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length > 1024 * 1024:
                    self._json({"error": "请求内容过大"}, 413)
                    return
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "请求格式无效"}, 400)
                return
            if not isinstance(body, dict) or type(body.get("enabled")) is not bool:
                self._json({"error": "enabled 必须是布尔值"}, 400)
                return
            try:
                enabled, starting = _set_collector_enabled(body["enabled"])
            except OSError as exc:
                self._json({"error": f"无法更新本机剪贴板开关：{exc}"}, 503)
                return
            snapshot = _collector_snapshot()
            self._json(
                {
                    "enabled": enabled,
                    "paused": not enabled,
                    "starting": starting,
                    "online": snapshot["online"],
                    "status": snapshot["status"],
                    "pending_count": snapshot["pending_count"],
                    "pause_reason": snapshot["pause_reason"],
                }
            )
            return
        if api_path != "/api/jobs":
            self._json({"error": "not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 1024 * 1024:
                self._json({"error": "粘贴内容过大，请分批处理"}, 413)
                return
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "请求格式无效"}, 400)
            return

        if not isinstance(body, dict):
            self._json({"error": "请求内容必须是 JSON 对象"}, 400)
            return
        text = body.get("text", "")
        supplied_urls = body.get("urls")
        if not isinstance(text, str):
            self._json({"error": "text 必须是字符串"}, 400)
            return
        if supplied_urls is not None:
            if not isinstance(supplied_urls, list) or not all(isinstance(url, str) for url in supplied_urls):
                self._json({"error": "urls 必须是字符串数组"}, 400)
                return
            if len(supplied_urls) > MAX_URLS_PER_JOB:
                self._json({"error": f"单批最多提交 {MAX_URLS_PER_JOB} 条链接"}, 413)
                return
            text = "\n".join([text, *supplied_urls])
        urls = extract_urls_from_text(text)
        if not urls:
            self._json({"error": "未检测到有效链接"}, 400)
            return
        if len(urls) > MAX_URLS_PER_JOB:
            self._json({"error": f"单批最多提交 {MAX_URLS_PER_JOB} 条链接"}, 413)
            return
        output_dir = body.get("output_dir") or DEFAULT_OUTPUT_DIR
        if not isinstance(output_dir, str) or not output_dir.strip():
            self._json({"error": "保存位置格式无效"}, 400)
            return
        mode = body.get("mode", "auto")
        if mode not in DELAY_MODES:
            self._json({"error": "下载节奏无效", "supported_modes": sorted(DELAY_MODES)}, 400)
            return
        adaptive = mode == "auto"
        delay = DELAY_MODES[mode]
        image_format = body.get("image_format", "keep")
        if image_format not in {"jpg", "png", "keep"}:
            self._json({"error": "图片格式无效"}, 400)
            return

        idempotency_key = self.headers.get("Idempotency-Key", "").strip()
        if len(idempotency_key) > 128:
            self._json({"error": "Idempotency-Key 最长 128 个字符"}, 400)
            return
        fingerprint = hashlib.sha256(
            json.dumps(
                {"urls": urls, "output_dir": output_dir, "mode": mode, "image_format": image_format},
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
        job_id = uuid.uuid4().hex
        duplicate = None
        conflict = False
        with JOBS_LOCK:
            now = time.time()
            for key in [key for key, value in JOB_IDEMPOTENCY.items() if value["expires_at"] <= now]:
                JOB_IDEMPOTENCY.pop(key, None)
            cached = JOB_IDEMPOTENCY.get(idempotency_key) if idempotency_key else None
            if cached and cached["fingerprint"] != fingerprint:
                conflict = True
            elif cached:
                duplicate = copy.deepcopy(JOBS.get(cached["job_id"]))
                if duplicate is None:
                    with WEB_HISTORY_LOCK:
                        duplicate = copy.deepcopy(next((value for value in WEB_HISTORY if value.get("job_id") == cached["job_id"]), None))
                    if duplicate is None:
                        JOB_IDEMPOTENCY.pop(idempotency_key, None)
            if not conflict and duplicate is None:
                if len(JOBS) >= 50:
                    oldest = min(JOBS, key=lambda key: JOBS[key]["created_at"])
                    JOBS.pop(oldest, None)
                JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "created_at": now,
                    "total": len(urls),
                    "done": 0,
                    "success": 0,
                    "failed": 0,
                    "skipped": 0,
                    "items": [],
                    "error": "",
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                }
                if idempotency_key:
                    JOB_IDEMPOTENCY[idempotency_key] = {
                        "fingerprint": fingerprint,
                        "job_id": job_id,
                        "expires_at": now + 24 * 60 * 60,
                    }
                    while len(JOB_IDEMPOTENCY) > 2000:
                        JOB_IDEMPOTENCY.pop(next(iter(JOB_IDEMPOTENCY)))
        if conflict:
            self._json({"error": "Idempotency-Key 已用于不同的请求内容"}, 409)
            return
        if duplicate is not None:
            status_code = 200 if duplicate.get("status") in {"completed", "error"} else 202
            self._json(
                {"job_id": duplicate.get("job_id", ""), "status": duplicate.get("status", "queued"), "total": duplicate.get("total", len(urls)), "deduplicated": True},
                status_code,
                {"Location": f"/api/v1/jobs/{duplicate.get('job_id', '')}", "Retry-After": "2"},
            )
            return
        worker = threading.Thread(
            target=_run_job,
            args=(job_id, urls, output_dir, delay, image_format, adaptive),
            daemon=True,
        )
        worker.start()
        self._json(
            {"job_id": job_id, "status": "queued", "total": len(urls)},
            202,
            {"Location": f"/api/v1/jobs/{job_id}", "Retry-After": "2"},
        )

    def _html(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200, headers=None):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        origin = self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        if not self._api_path().startswith("/api/"):
            self._json({"error": "not found"}, 404)
            return
        origin = self.headers.get("Origin", "")
        parsed_origin = urlsplit(origin)
        self.send_response(204)
        if parsed_origin.scheme in {"http", "https"} and parsed_origin.hostname in {"localhost", "127.0.0.1", "::1"}:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Idempotency-Key")
            self.send_header("Access-Control-Max-Age", "600")
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    host = "127.0.0.1"
    port = 5678
    server = ThreadingHTTPServer((host, port), Handler)
    url = "http://{}:{}".format(host, port)
    print("{} V{} Web: {}".format(APP_NAME, __version__, url))
    print("Press Ctrl+C to stop")
    threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
