"""xhs-dl V2 浏览器可视化界面。"""

import argparse
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
from xhs_dl.storage import history_path, add_history
from xhs_dl.web import toolbox_store
from xhs_dl.web.ui_template import TEMPLATE


def _compute_web_code_stamp():
    web_dir = Path(__file__).resolve().parent
    stamps = []
    for py_file in web_dir.glob("*.py"):
        try:
            stamps.append(int(py_file.stat().st_mtime))
        except OSError:
            pass
    return max(stamps) if stamps else 0


SERVER_CODE_STAMP = _compute_web_code_stamp()


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

    candidates = []
    if config_text:
        try:
            import tomllib
        except ImportError:
            tomllib = None
        if tomllib is not None:
            try:
                config = tomllib.loads(config_text)
                codex_val = str(
                    config.get("mcp_servers", {})
                    .get("jianghu_toolbox", {})
                    .get("env", {})
                    .get("JIANGHU_BRIDGE_DIR", "")
                ).strip()
                if codex_val:
                    candidates.append(codex_val)
            except (TypeError, ValueError):
                pass
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
                    if raw_value.strip():
                        candidates.append(raw_value.strip())
                    break

    antigravity_mcp = Path.home() / ".gemini" / "antigravity" / "mcp_config.json"
    try:
        mcp_cfg = json.loads(antigravity_mcp.read_text(encoding="utf-8-sig"))
        agy_val = str(
            mcp_cfg.get("mcpServers", {})
            .get("jianghu_toolbox", {})
            .get("env", {})
            .get("JIANGHU_BRIDGE_DIR", "")
        ).strip()
        if agy_val:
            candidates.append(agy_val)
    except (OSError, ValueError, TypeError):
        pass

    maintained_bridge = Path(r"D:\AICode\运行数据\江湖工具箱\repair-smoke-v4-20261112\runtime\bridge")
    candidates.append(str(maintained_bridge))

    for raw in candidates:
        candidate = Path(raw).expanduser()
        if candidate.is_dir():
            return candidate

    return Path(r"D:\Program Files\江湖工具箱\MinApp")


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


def _use_native_engine():
    return os.environ.get("XHS_DL_LEGACY_JIANGHU_ENGINE", "0") != "1"


def _toolbox_capability_snapshot():
    if _use_native_engine():
        from xhs_dl.web import native_collector
        return native_collector.get_engine().get_capabilities()

    cli_file = TOOLBOX_PROJECT / "jianghu_cli.py"
    status_file = TOOLBOX_BRIDGE_DIR / "bridge_status.json"
    progress_file = TOOLBOX_BRIDGE_DIR / "keyword_progress.json"
    status = "offline"
    age_seconds = None
    native = {}
    progress = {}
    try:
        age_seconds = max(0, time.time() - status_file.stat().st_mtime)
        if age_seconds <= 5:
            native = json.loads(status_file.read_text(encoding="utf-8-sig"))
            status = "online" if isinstance(native, dict) and native.get("running") is True else "offline"
        else:
            status = "stale"
    except (OSError, ValueError, TypeError):
        pass
    try:
        parsed_progress = json.loads(progress_file.read_text(encoding="utf-8-sig"))
        if isinstance(parsed_progress, dict):
            progress = parsed_progress
    except (OSError, ValueError, TypeError):
        progress = native.get("keyword_progress") if isinstance(native.get("keyword_progress"), dict) else {}
    ver_req = bool(native.get("verification_required"))
    if not ver_req and isinstance(progress, dict) and (
        progress.get("phase") == "verification"
        or progress.get("status") == "verification_required"
    ):
        progress = {}
    if ver_req:
        active_plat = str(native.get("active_platform") or "douyin")
        kw_name = str((progress or {}).get("keyword") or "")
        plat_cn = "小红书" if active_plat == "xiaohongshu" else "抖音"

        def _notify_verify():
            try:
                from xhs_dl.web import notifier
                notifier.dispatch_workbench_notification(
                    "verification",
                    f"⚠️ 万能采集器触发人机验证（{plat_cn}）",
                    f"关键词/任务：{kw_name or '当前采集'}\n已尝试自动弹出并置顶验证浏览器，请人工完成验证后点击「已完成验证，继续采集」。",
                    settings=toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR),
                    platform=active_plat,
                    dedup_key=f"cap-verify:{active_plat}:{kw_name}",
                    cooldown_seconds=90.0,
                    bring_verify_fn=lambda topmost=True: toolbox_store.focus_and_bring_verify_browser(
                        TOOLBOX_BRIDGE_DIR,
                        TOOLBOX_PROJECT,
                        _python_console_executable(),
                        topmost=topmost,
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=_notify_verify, daemon=True).start()

    return {
        "available": cli_file.is_file(),
        "status": status,
        "age_seconds": round(age_seconds, 1) if age_seconds is not None else None,
        "active_platform": native.get("active_platform"),
        "verification_required": ver_req,
        "busy": bool(
            (native.get("keyword") or {}).get("is_running")
            or (native.get("single") or {}).get("busy_or_unknown")
        ),
        "keyword_progress": progress,
        "supports": {
            "homepage": ["douyin"],
            "keyword": ["douyin", "xiaohongshu"],
            "xiaohongshu_homepage": False,
        },
    }


def _collection_task_payload(task):
    allowed = {
        "job_id", "kind", "label", "status", "stage", "created_at", "updated_at",
        "message", "discovered_count", "download_job_id", "completion_confirmed",
        "outcome", "native_job_id", "keyword", "target_count", "count", "ingest",
        "skipped_duplicate_count",
    }
    value = {key: copy.deepcopy(task[key]) for key in allowed if key in task}
    if value.get("kind") == "keyword" and value.get("status") in {"queued", "discovering"}:
        progress_data = _read_json(TOOLBOX_BRIDGE_DIR / "keyword_progress.json", {})
        if isinstance(progress_data, dict) and progress_data:
            value["keyword_progress"] = progress_data
            if str(progress_data.get("keyword") or "").strip() == str(task.get("keyword") or "").strip():
                live_msg = str(progress_data.get("message") or "").strip()
                if live_msg:
                    value["message"] = live_msg
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
                    f"已读取 {value.get('discovered_count', 0)} 条作品链接；"
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
    if task.get("direct_download") is False:
        return None
    clean_links = []
    seen = set()
    for value in links if isinstance(links, list) else []:
        urls = extract_urls_from_text(value) if isinstance(value, str) else []
        if len(urls) != 1:
            continue
        url = urls[0]
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        is_douyin = (
            host == "douyin.com"
            or host.endswith(".douyin.com")
            or host == "iesdouyin.com"
            or host.endswith(".iesdouyin.com")
        )
        is_xhs = (
            host == "xiaohongshu.com"
            or host.endswith(".xiaohongshu.com")
            or host == "xhslink.com"
            or host.endswith(".xhslink.com")
        )
        path_l = (parsed.path or "").lower()
        if parsed.scheme.lower() not in {"http", "https"} or not (is_douyin or is_xhs):
            continue
        if is_douyin and ("/note/" not in path_l and "/video/" not in path_l):
            continue
        if is_xhs and host != "xhslink.com" and (
            "/explore/" not in path_l and "/discovery/item/" not in path_l and len(path_l.strip("/")) < 6
        ):
            continue
        if url not in seen:
            seen.add(url)
            clean_links.append(url)
    clean_links = clean_links[:MAX_URLS_PER_JOB]
    if not clean_links:
        return None
    try:
        toolbox_store.record_discovered_artworks(
            clean_links,
            platform=task.get("platform") or "douyin",
            source=task.get("label") or task.get("kind") or "collection",
            mark_current=True,
            bridge_dir=TOOLBOX_BRIDGE_DIR,
        )
    except Exception:
        pass

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


def _run_collection_discovery(job_id, command, cleanup_files=None):
    _update_collection_task(job_id, status="discovering", stage="browser",
                            message="正在通过内置 Edge 核心读取搜索列表/主页；遇到登录或验证会置顶弹窗提醒")
    try:
        with COLLECTION_TASKS_LOCK:
            pre_task = copy.deepcopy(COLLECTION_TASKS.get(job_id))

        result = None
        if _use_native_engine() and isinstance(pre_task, dict):
            from xhs_dl.web import native_collector, notifier
            eng = native_collector.get_engine()
            cur_settings = toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR) or {}
            sw_cfg = cur_settings.get("software") or {}
            proxy_url = str(sw_cfg.get("proxy_url") or "")
            skip_ids = (
                toolbox_store.collect_downloaded_artwork_ids(bridge_dir=TOOLBOX_BRIDGE_DIR)
                if pre_task.get("skip_downloaded_history", True)
                else set()
            )
            plat_code = str(pre_task.get("platform") or "douyin")
            kw_label = str(pre_task.get("label") or pre_task.get("keyword") or "采集任务")

            def _on_gate(gate_status, gate_msg):
                evt = "verification" if gate_status == "verification_required" else "login"
                def _send():
                    try:
                        notifier.dispatch_workbench_notification(
                            evt,
                            "⚠️ 万能采集器需要人工验证" if evt == "verification" else "⚠️ 万能采集器需要登录",
                            f"任务：{kw_label}\n{gate_msg}",
                            settings=toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR),
                            platform=plat_code,
                            dedup_key=f"gate:{evt}:{plat_code}:{kw_label}",
                            cooldown_seconds=45.0,
                        )
                    except Exception:
                        pass
                threading.Thread(target=_send, daemon=True).start()

            if pre_task.get("kind") == "homepage":
                hp_url = str(pre_task.get("profile_url") or "")
                is_xhs_hp = plat_code == "xiaohongshu" or "xiaohongshu.com" in hp_url.lower()
                if is_xhs_hp:
                    result = eng.collect_xhs_homepage(
                        hp_url,
                        max_works=int(pre_task.get("max_works") or 10),
                        min_images=int(pre_task.get("min_images") if pre_task.get("min_images") is not None else 1),
                        max_images=int(pre_task.get("max_images") or 50),
                        direct_download=bool(pre_task.get("direct_download", True)),
                        skip_ids=skip_ids,
                        output_dir=str(pre_task.get("output_dir") or DEFAULT_OUTPUT_DIR),
                        image_format=str(pre_task.get("image_format") or "jpg"),
                        title_template=str(pre_task.get("title_template") or toolbox_store.DEFAULT_TITLE_TEMPLATE),
                        set_file_time=bool(pre_task.get("set_file_time_to_publish", True)),
                        proxy_url=proxy_url,
                        on_gate_cb=_on_gate,
                        job_request=pre_task,
                    )
                else:
                    result = eng.collect_douyin_homepage(
                        hp_url,
                        max_works=int(pre_task.get("max_works") or 10),
                        min_images=int(pre_task.get("min_images") or 4),
                        max_images=int(pre_task.get("max_images") or 20),
                        direct_download=bool(pre_task.get("direct_download", True)),
                        skip_ids=skip_ids,
                        output_dir=str(pre_task.get("output_dir") or DEFAULT_OUTPUT_DIR),
                        image_format=str(pre_task.get("image_format") or "jpg"),
                        title_template=str(pre_task.get("title_template") or toolbox_store.DEFAULT_TITLE_TEMPLATE),
                        set_file_time=bool(pre_task.get("set_file_time_to_publish", True)),
                        proxy_url=proxy_url,
                        on_gate_cb=_on_gate,
                        job_request=pre_task,
                    )
            elif plat_code == "xiaohongshu":
                cnt_val = int(pre_task.get("count") if pre_task.get("count") is not None else 20)
                result = eng.collect_xhs_keyword(
                    pre_task.get("keyword") or "",
                    count=cnt_val,
                    min_images=int(pre_task.get("min_images") if pre_task.get("min_images") is not None else 1),
                    max_images=int(pre_task.get("max_images") or 50),
                    allow_video=bool(pre_task.get("allow_video", False)),
                    media_type=str(pre_task.get("media_type") or ("all" if pre_task.get("allow_video") else "image")),
                    direct_download=bool(pre_task.get("direct_download", True)),
                    web_sort=str(pre_task.get("web_sort") or "综合排序"),
                    web_publish_time=str(pre_task.get("web_publish_time") or "不限"),
                    skip_ids=skip_ids,
                    output_dir=str(pre_task.get("output_dir") or DEFAULT_OUTPUT_DIR),
                    image_format=str(pre_task.get("image_format") or "jpg"),
                    title_template=str(pre_task.get("title_template") or toolbox_store.DEFAULT_TITLE_TEMPLATE),
                    set_file_time=bool(pre_task.get("set_file_time_to_publish", True)),
                    proxy_url=proxy_url,
                    on_gate_cb=_on_gate,
                    job_request=pre_task,
                )
            else:
                cnt_val = int(pre_task.get("count") if pre_task.get("count") is not None else 20)
                result = eng.collect_douyin_keyword(
                    pre_task.get("keyword") or "",
                    count=cnt_val,
                    min_images=int(pre_task.get("min_images") or 4),
                    max_images=int(pre_task.get("max_images") or 20),
                    allow_video=bool(pre_task.get("allow_video", False)),
                    media_type=str(pre_task.get("media_type") or ("all" if pre_task.get("allow_video") else "image")),
                    no_filter=bool(pre_task.get("no_filter", False)),
                    all_results=(cnt_val == 0),
                    direct_download=bool(pre_task.get("direct_download", True)),
                    web_sort=str(pre_task.get("web_sort") or "综合排序"),
                    web_publish_time=str(pre_task.get("web_publish_time") or "不限"),
                    skip_ids=skip_ids,
                    output_dir=str(pre_task.get("output_dir") or DEFAULT_OUTPUT_DIR),
                    image_format=str(pre_task.get("image_format") or "jpg"),
                    title_template=str(pre_task.get("title_template") or toolbox_store.DEFAULT_TITLE_TEMPLATE),
                    set_file_time=bool(pre_task.get("set_file_time_to_publish", True)),
                    proxy_url=proxy_url,
                    on_gate_cb=_on_gate,
                    job_request=pre_task,
                )
        else:
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

        is_direct = bool(task and task.get("direct_download"))
        download_info = result.get("download") if isinstance(result.get("download"), dict) else {}
        download_items = download_info.get("items") or result.get("items") or []
        success_downloads = int(download_info.get("success_count") or sum(1 for it in download_items if it.get("completion_confirmed") or it.get("downloaded")))
        media_count = int(result.get("media_file_count") or sum(int(it.get("media_file_count") or 0) for it in download_items))
        skipped_dup = int(result.get("skipped_duplicate_count") or 0)

        dl_by_id = {str(it.get("id") or ""): it for it in download_items if isinstance(it, dict) and it.get("id")}
        raw_candidates = result.get("candidates") or download_items or []
        candidates = []
        seen_cids = set()
        for c in raw_candidates:
            if isinstance(c, dict):
                cid = str(c.get("id") or "")
                merged = dict(c)
                if cid and cid in dl_by_id:
                    for k in ("download_status", "save_directory", "image_count", "media_file_count", "downloaded", "completion_confirmed"):
                        if dl_by_id[cid].get(k) not in (None, ""):
                            merged[k] = dl_by_id[cid][k]
                    seen_cids.add(cid)
                candidates.append(merged)
            else:
                candidates.append(c)
        for cid, it in dl_by_id.items():
            if cid not in seen_cids:
                candidates.append(it)
        if not is_direct and task and not candidates and links:
            candidates = []
            for link in links:
                if not isinstance(link, str):
                    continue
                match = re.search(r"/(?:explore|discovery/item|note|video)/([a-zA-Z0-9]+)", urlsplit(link).path)
                if match:
                    candidates.append({"id": match.group(1), "url": link})
        if candidates and task:
            try:
                toolbox_store.record_discovered_artworks(
                    candidates,
                    platform=task.get("platform") or "douyin",
                    source=task.get("label") or task.get("kind") or "collection",
                    mark_current=True,
                    bridge_dir=TOOLBOX_BRIDGE_DIR,
                )
            except Exception:
                if not is_direct:
                    _update_collection_task(
                        job_id, status="error", stage="workbench",
                        message="已发现作品，写入作品列表失败",
                    )
                    return

        if is_direct and (success_downloads > 0 or result.get("success") is True):
            if task.get("kind") == "keyword" and task.get("keyword"):
                try:
                    toolbox_store.mark_keyword_collected(
                        task.get("keyword"),
                        platform=task.get("platform") or "douyin",
                        count=success_downloads,
                        bridge_dir=TOOLBOX_BRIDGE_DIR,
                    )
                except Exception:
                    pass
            saved_pkg_dirs = []
            for it in download_items:
                if it.get("completion_confirmed") or it.get("downloaded"):
                    sd = str(it.get("save_directory") or "").strip()
                    if sd:
                        saved_pkg_dirs.append(sd)
                    try:
                        add_history(
                            it.get("url") or "",
                            str(it.get("id") or ""),
                            it.get("title") or "抖音图文作品",
                            sd,
                        )
                    except Exception:
                        pass
            dl_cfg = copy.deepcopy((toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR) or {}).get("download", {}))
            auto_ingest = task.get("auto_ingest_material")
            if auto_ingest is None:
                auto_ingest = bool(dl_cfg.get("auto_ingest_material", False))
            ingest_summary = None
            if auto_ingest and saved_pkg_dirs:
                plat_hint = "小红书" if (task.get("platform") or "douyin") == "xiaohongshu" else "抖音"
                src_label = "万能采集器·关键词" if task.get("kind") == "keyword" else "万能采集器·主页"
                ingest_summary = toolbox_store.ingest_downloaded_packages(
                    saved_pkg_dirs,
                    dl_cfg,
                    source_label=src_label,
                    platform_hint=plat_hint,
                )
                by_source = ingest_summary.get("by_source", {})
                updated_rows = []
                for it in download_items:
                    sd = str(it.get("save_directory") or "").strip()
                    if not sd:
                        continue
                    src_key = str(Path(sd).expanduser().resolve())
                    if src_key in by_source:
                        row_patch = dict(it)
                        toolbox_store._apply_ingest_info_to_row(
                            row_patch,
                            by_source[src_key],
                            copy_only=bool(dl_cfg.get("auto_ingest_copy_only", True)),
                        )
                        updated_rows.append(row_patch)
                if updated_rows:
                    try:
                        toolbox_store.record_discovered_artworks(
                            updated_rows,
                            platform=task.get("platform") or "douyin",
                            source=task.get("label") or task.get("kind") or "collection",
                            mark_current=None,
                            bridge_dir=TOOLBOX_BRIDGE_DIR,
                        )
                    except Exception:
                        pass
            final_msg = f"已成功采集并下载 {success_downloads} 套作品（共 {media_count} 张图文素材）"
            if skipped_dup:
                final_msg += f"；已去重跳过 {skipped_dup} 条已采作品"
            if ingest_summary and ingest_summary.get("attempted"):
                final_msg += f"；自动入库：{ingest_summary['summary']}"
            _update_collection_task(
                job_id,
                status="completed",
                stage="completed",
                discovered_count=len(candidates) or len(links),
                skipped_duplicate_count=skipped_dup,
                message=final_msg,
                ingest=ingest_summary,
                completion_confirmed=True,
            )
            def _notify_done():
                try:
                    from xhs_dl.web import notifier
                    first_target = ""
                    if ingest_summary and ingest_summary.get("results"):
                        first_target = next((str(r.get("target_dir") or "") for r in ingest_summary["results"] if r.get("success")), "")
                    if not first_target and saved_pkg_dirs:
                        first_target = saved_pkg_dirs[0]
                    notifier.dispatch_workbench_notification(
                        "completed",
                        "✅ 万能采集器采集完成",
                        f"任务：{task.get('label') or task.get('keyword') or '采集任务'}\n{final_msg}",
                        settings=toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR),
                        action_target=first_target,
                        platform=task.get("platform") or "douyin",
                        dedup_key=f"done:{job_id}",
                        cooldown_seconds=10.0,
                    )
                except Exception:
                    pass
            threading.Thread(target=_notify_done, daemon=True).start()
            return

        if task and not is_direct and candidates and result.get("status") not in {"verification_required", "login_required", "cancelled", "partial"}:
            if task.get("kind") == "keyword" and task.get("keyword"):
                try:
                    toolbox_store.mark_keyword_collected(
                        task.get("keyword"),
                        platform=task.get("platform") or "douyin",
                        count=len(candidates),
                        bridge_dir=TOOLBOX_BRIDGE_DIR,
                    )
                except Exception:
                    pass
            msg_list = f"已采集 {len(candidates)} 条作品到作品列表，可勾选后手动下载"
            if skipped_dup:
                msg_list += f"；已去重跳过 {skipped_dup} 条已采作品"
            _update_collection_task(
                job_id,
                status="completed",
                stage="completed",
                discovered_count=len(candidates),
                skipped_duplicate_count=skipped_dup,
                message=msg_list,
                completion_confirmed=True,
            )
            return

        if is_direct and links and task and result.get("status") not in {"verification_required", "login_required", "cancelled", "partial", "error"}:
            download_job_id = _queue_collection_links(task, links)
            if download_job_id:
                _update_collection_task(
                    job_id,
                    status="download_queued",
                    stage="download",
                    discovered_count=len(links),
                    download_job_id=download_job_id,
                    message=f"已读取 {len(links)} 条作品链接，已加入万能下载器队列",
                    completion_confirmed=False,
                )
                return

        accepted = result.get("accepted") is True or result.get("outcome") == "accepted"
        status = "accepted" if accepted else (
            "completed" if result.get("success") is True else str(result.get("status") or "error")
        )
        msg_term = result.get("message") or "采集流程已返回"
        if status in {"verification_required", "login_required"} and not _use_native_engine():
            evt = "verification" if status == "verification_required" else "login"
            kw_label = (task or {}).get("label") or (task or {}).get("keyword") or "采集任务"
            plat_code = (task or {}).get("platform") or "douyin"
            def _notify_gate():
                try:
                    from xhs_dl.web import notifier
                    notifier.dispatch_workbench_notification(
                        evt,
                        "⚠️ 万能采集器需要人工验证" if evt == "verification" else "⚠️ 万能采集器需要重新登录",
                        f"任务：{kw_label}\n详情：{msg_term}\n已自动弹窗并置顶浏览器窗口，请人工完成后点击「继续采集」。",
                        settings=toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR),
                        platform=plat_code,
                        dedup_key=f"gate:{evt}:{plat_code}:{kw_label}",
                        cooldown_seconds=60.0,
                        bring_verify_fn=lambda topmost=True: toolbox_store.focus_and_bring_verify_browser(
                            TOOLBOX_BRIDGE_DIR,
                            TOOLBOX_PROJECT,
                            _python_console_executable(),
                            topmost=topmost,
                        ),
                    )
                except Exception:
                    pass
            threading.Thread(target=_notify_gate, daemon=True).start()

        _update_collection_task(
            job_id,
            status=status,
            stage=result.get("stage", "collection"),
            discovered_count=len(candidates) or len(links),
            skipped_duplicate_count=skipped_dup,
            outcome=result.get("outcome", ""),
            completion_confirmed=bool(result.get("completion_confirmed")),
            native_job_id=result.get("job_id", ""),
            message=msg_term,
        )
    finally:
        for cf in (cleanup_files or []):
            try:
                Path(cf).unlink(missing_ok=True)
            except OSError:
                pass


def _validate_profile_url(value):
    urls = extract_urls_from_text(value) if isinstance(value, str) else []
    if len(urls) != 1:
        raise ValueError("主页采集一次只填写一个作者主页链接")
    url = urls[0]
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    path_lower = (parsed.path or "").lower()
    if parsed.scheme.lower() not in {"http", "https"} or parsed.username is not None or parsed.password is not None:
        raise ValueError("请输入合法的抖音或小红书作者主页网址")
    is_dy = (
        host == "douyin.com" or host.endswith(".douyin.com")
        or host == "iesdouyin.com" or host.endswith(".iesdouyin.com")
    )
    if is_dy and "/user/" in path_lower:
        return url, "douyin"
    is_xhs = host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com") or host in {"xhslink.com", "xhslink.cn"}
    if is_xhs and ("/user/profile/" in path_lower or host in {"xhslink.com", "xhslink.cn"}):
        return url, "xiaohongshu"
    raise ValueError("请输入抖音（含 /user/）或小红书（含 /user/profile/）作者主页链接")


def _validate_douyin_profile(value):
    url, plat = _validate_profile_url(value)
    if plat != "douyin":
        raise ValueError("请输入抖音作者主页链接（路径需包含 /user/）")
    return url


def _create_collection_task(kind, label, request, idempotency_key):
    request = copy.deepcopy(request)
    command = request.pop("_command")
    cleanup_files = request.pop("_cleanup_files", None)
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
        args=(job_id, command, cleanup_files),
        daemon=True,
        name=f"collection-{kind}-{job_id[:8]}",
    ).start()
    return _collection_task_payload(task), None, 202


def _resume_native_paused_job(paused_req):
    req = dict(paused_req or {})
    kind = req.get("kind") or "keyword"
    label = req.get("label") or ("抖音主页" if kind == "homepage" else f"恢复采集：{req.get('keyword') or ''}")
    for k in ("job_id", "status", "stage", "created_at", "updated_at", "message", "discovered_count", "download_job_id", "completion_confirmed", "fingerprint", "idempotency_key"):
        req.pop(k, None)
    req["_command"] = []
    task, err, _code = _create_collection_task(kind, label, req, "")
    if err:
        raise ValueError(err)
    return task


toolbox_store.set_native_resume_callback(_resume_native_paused_job)



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
                    "summary": "采集抖音或小红书公开主页，默认只回填作品列表",
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
            "/api/v1/workbench/keywords": {
                "get": {"summary": "读取统一工作台关键词列表", "responses": {"200": {"description": "关键词与同步状态"}}},
                "post": {"summary": "管理工作台关键词（增删改/批量勾选/同步江湖词库）", "responses": {"200": {"description": "操作后列表"}}},
            },
            "/api/v1/workbench/authors": {
                "get": {"summary": "读取统一工作台作者主页列表", "responses": {"200": {"description": "主页作者列表"}}},
                "post": {"summary": "管理工作台作者主页", "responses": {"200": {"description": "操作后列表"}}},
            },
            "/api/v1/workbench/artworks": {
                "get": {"summary": "筛选与查看统一作品列表（当前/历史）", "responses": {"200": {"description": "作品列表"}}},
                "post": {"summary": "作品列表勾选/删除/同步/导出 CSV", "responses": {"200": {"description": "操作结果"}}},
            },
            "/api/v1/workbench/settings": {
                "get": {"summary": "读取统一工作台全部筛选、下载与主题设置", "responses": {"200": {"description": "完整设置对象"}}},
                "post": {"summary": "保存工作台设置", "responses": {"200": {"description": "已保存设置"}}},
            },
            "/api/v1/workbench/ai-jobs": {
                "get": {"summary": "读取 AI CLI/MCP 与后台采集任务实时流水", "responses": {"200": {"description": "任务列表"}}},
            },
            "/api/v1/workbench/engine": {
                "post": {"summary": "调度原生登录窗口、平台切换、引擎启动与目录打开", "responses": {"200": {"description": "执行结果"}}},
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

    def _read_json_body(self, max_bytes=256 * 1024):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            self._json({"error": "请求内容长度无效"}, 400)
            return None
        if length > max_bytes:
            self._json({"error": "请求内容过大"}, 413)
            return None
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._json({"error": "请求格式无效"}, 400)
            return None
        if not isinstance(body, dict):
            self._json({"error": "请求内容必须是 JSON 对象"}, 400)
            return None
        return body

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
        if path in ("/favicon.ico", "/app-icon.png"):
            ico_path, png_path = _app_icon_paths()
            target = ico_path if path == "/favicon.ico" else png_path
            ctype = "image/x-icon" if path == "/favicon.ico" else "image/png"
            if target and target.is_file():
                try:
                    data = target.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "public, max-age=3600")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except OSError:
                    pass
            self.send_response(404)
            self.end_headers()
            return
        if path == "/manifest.webmanifest":
            manifest = {
                "name": f"{APP_NAME} · 统一智能采集工作台",
                "short_name": "万能采集器",
                "start_url": "/",
                "display": "standalone",
                "background_color": "#e8edf3",
                "theme_color": "#263442",
                "icons": [{"src": "/app-icon.png", "sizes": "256x256", "type": "image/png"}],
            }
            data = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/openapi.json":
            self._json(_openapi_document())
            return
        if path == "/api/health":
            self._json({"status": "ok", "name": APP_NAME, "version": __version__, "code_stamp": SERVER_CODE_STAMP, "pid": os.getpid()})
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
                        "workbench_keywords": "GET/POST /api/v1/workbench/keywords",
                        "workbench_authors": "GET/POST /api/v1/workbench/authors",
                        "workbench_artworks": "GET/POST /api/v1/workbench/artworks",
                        "workbench_settings": "GET/POST /api/v1/workbench/settings",
                        "workbench_ai_jobs": "GET /api/v1/workbench/ai-jobs",
                        "workbench_engine": "POST /api/v1/workbench/engine",
                        "openapi": "GET /api/openapi.json",
                    },
                }
            )
            return
        if path == "/api/workbench/keywords":
            query = parse_qs(parsed.query)
            self._json(
                toolbox_store.list_keywords(
                    platform=query.get("platform", ["all"])[0],
                    search=query.get("search", [""])[0],
                    group=query.get("group", ["all"])[0],
                    sort_by=query.get("sort_by", ["seq"])[0],
                    sort_dir=query.get("sort_dir", ["asc"])[0],
                    bridge_dir=TOOLBOX_BRIDGE_DIR,
                )
            )
            return
        if path == "/api/workbench/authors":
            query = parse_qs(parsed.query)
            self._json(
                toolbox_store.list_authors(
                    platform=query.get("platform", ["all"])[0],
                    search=query.get("search", [""])[0],
                    sort_by=query.get("sort_by", ["seq"])[0],
                    sort_dir=query.get("sort_dir", ["asc"])[0],
                    group=query.get("group", ["all"])[0],
                    bridge_dir=TOOLBOX_BRIDGE_DIR,
                )
            )
            return
        if path == "/api/workbench/artworks":
            query = parse_qs(parsed.query)
            extra_history, _ = _download_history(limit=150, offset=0)
            ai_jobs_data = toolbox_store.read_ai_jobs(TOOLBOX_BRIDGE_DIR, limit=40)
            rules = []
            for key_name, field in (
                ("min_likes", "likes"),
                ("min_comments", "comments"),
                ("min_favorites", "favorites"),
                ("min_images", "image_count"),
            ):
                raw_v = query.get(key_name, ["0"])[0]
                try:
                    val = int(float(raw_v))
                except (TypeError, ValueError):
                    val = 0
                if val > 0:
                    rules.append({"enabled": True, "field": field, "op": ">=", "value": val})
            self._json(
                toolbox_store.list_artworks(
                    mode=query.get("mode", ["history"])[0],
                    search=query.get("search", [""])[0],
                    platform=query.get("platform", ["all"])[0],
                    artwork_type=query.get("artwork_type", ["all"])[0],
                    include_kw=query.get("include_kw", [""])[0],
                    exclude_kw=query.get("exclude_kw", [""])[0],
                    rules=rules,
                    sort_by=query.get("sort_by", ["seq"])[0],
                    sort_dir=query.get("sort_dir", ["asc"])[0],
                    extra_history=extra_history,
                    extra_ai_jobs=(ai_jobs_data.get("jobs") if isinstance(ai_jobs_data, dict) else []),
                    bridge_dir=TOOLBOX_BRIDGE_DIR,
                )
            )
            return
        if path == "/api/workbench/settings":
            self._json(toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR))
            return
        if path == "/api/workbench/ai-jobs":
            query = parse_qs(parsed.query)
            try:
                limit = max(1, min(int(query.get("limit", ["40"])[0]), 80))
            except (TypeError, ValueError):
                limit = 40
            self._json(toolbox_store.read_ai_jobs(TOOLBOX_BRIDGE_DIR, limit=limit))
            return
        if path == "/api/workbench/state":
            self._json({
                "capabilities": _toolbox_capability_snapshot(),
                "settings": toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR),
                "keywords": toolbox_store.list_keywords(bridge_dir=TOOLBOX_BRIDGE_DIR),
                "authors": toolbox_store.list_authors(bridge_dir=TOOLBOX_BRIDGE_DIR),
                "ai_jobs": toolbox_store.read_ai_jobs(TOOLBOX_BRIDGE_DIR, limit=25),
            })
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
        if api_path == "/api/server/shutdown":
            self._json({"status": "stopping", "pid": os.getpid()})

            def _graceful_stop():
                time.sleep(0.15)
                try:
                    if _use_native_engine():
                        from xhs_dl.web import native_collector
                        native_collector.get_engine().close()
                except Exception:
                    pass
                try:
                    self.server.shutdown()
                except Exception:
                    pass

            threading.Thread(target=_graceful_stop, daemon=True).start()
            return
        if api_path in {
            "/api/workbench/keywords",
            "/api/workbench/authors",
            "/api/workbench/artworks",
            "/api/workbench/settings",
            "/api/workbench/engine",
        }:
            body = self._read_json_body(max_bytes=512 * 1024)
            if body is None:
                return
            try:
                if api_path == "/api/workbench/keywords":
                    result = toolbox_store.mutate_keywords(str(body.get("op") or ""), body, bridge_dir=TOOLBOX_BRIDGE_DIR)
                elif api_path == "/api/workbench/authors":
                    result = toolbox_store.mutate_authors(str(body.get("op") or ""), body, bridge_dir=TOOLBOX_BRIDGE_DIR)
                elif api_path == "/api/workbench/artworks":
                    result = toolbox_store.mutate_artworks(str(body.get("op") or ""), body, bridge_dir=TOOLBOX_BRIDGE_DIR)
                elif api_path == "/api/workbench/settings":
                    result = toolbox_store.update_settings(body, bridge_dir=TOOLBOX_BRIDGE_DIR)
                else:
                    result = toolbox_store.run_engine_action(
                        str(body.get("action") or ""),
                        body.get("params") or {},
                        TOOLBOX_BRIDGE_DIR,
                        TOOLBOX_PROJECT,
                        _python_console_executable(),
                    )
                self._json(result)
            except ValueError as exc:
                self._json({"error": str(exc)}, 400)
            except Exception as exc:
                self._json({"error": str(exc)}, 503)
            return
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
                self._json({"error": "采集引擎不可用"}, 503)
                return
            if capability["status"] != "online":
                self._json({"error": "采集模块当前不在线；本次没有启动采集"}, 503)
                return
            requested_platform = "douyin"
            if api_path.endswith("/keyword"):
                raw_plat = str(body.get("platform") or "douyin").strip().lower()
                requested_platform = "xiaohongshu" if raw_plat in {"xiaohongshu", "xhs", "小红书"} else "douyin"
            if not _use_native_engine():
                if capability["verification_required"]:
                    self._json({"error": "原生浏览器正在等待人工验证；完成验证后再提交"}, 409)
                    return
                if capability["active_platform"] != requested_platform:
                    expected_name = "小红书" if requested_platform == "xiaohongshu" else "抖音"
                    self._json({"error": f"当前原生核心不是{expected_name}；请先在平台登录或江湖工具箱切换到{expected_name}"}, 409)
                    return
            if capability["busy"]:
                self._json({"error": "采集任务仍在运行中，请等待当前任务完成"}, 409)
                return

            all_cfg = toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR) or {}
            dl_cfg = all_cfg.get("download", {})
            kw_cfg = all_cfg.get("keyword", {})
            output_dir = body.get("output_dir") or dl_cfg.get("output_dir") or DEFAULT_OUTPUT_DIR
            mode = body.get("mode", dl_cfg.get("delay_mode") or "auto")
            image_format = body.get("image_format") or dl_cfg.get("image_format") or "jpg"
            title_template = str(
                body.get("title_template")
                or dl_cfg.get("title_template")
                or toolbox_store.DEFAULT_TITLE_TEMPLATE
            ).strip()
            set_file_time = bool(body.get("set_file_time_to_publish", dl_cfg.get("set_file_time_to_publish", True)))
            if not isinstance(output_dir, str) or not output_dir.strip() or len(output_dir) > 4096:
                self._json({"error": "保存位置格式无效"}, 400)
                return
            if not isinstance(mode, str) or mode not in DELAY_MODES:
                self._json({"error": "下载节奏无效"}, 400)
                return
            if not isinstance(image_format, str) or image_format not in {"keep", "jpg", "png"}:
                self._json({"error": "图片格式无效"}, 400)
                return

            auto_ingest_param = (
                bool(body["auto_ingest_material"])
                if "auto_ingest_material" in body
                else bool(dl_cfg.get("auto_ingest_material", False))
            )
            skip_downloaded_history = (
                bool(body["skip_downloaded_history"])
                if "skip_downloaded_history" in body
                else bool(dl_cfg.get("skip_downloaded_history", True))
            )
            skip_cleanup_files = []
            skip_cmd_args = []
            if skip_downloaded_history:
                skip_ids = toolbox_store.collect_downloaded_artwork_ids(bridge_dir=TOOLBOX_BRIDGE_DIR)
                if skip_ids:
                    TOOLBOX_BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
                    skip_file = TOOLBOX_BRIDGE_DIR / f".skip-ids-{uuid.uuid4().hex}.json"
                    skip_file.write_text(json.dumps(sorted(skip_ids), ensure_ascii=False), encoding="utf-8")
                    skip_cmd_args = ["--skip-ids-file", str(skip_file)]
                    skip_cleanup_files = [str(skip_file)]

            if api_path.endswith("/homepage"):
                try:
                    profile_url, profile_plat = _validate_profile_url(body.get("profile_url", ""))
                except ValueError as exc:
                    for path_str in skip_cleanup_files:
                        Path(path_str).unlink(missing_ok=True)
                    self._json({"error": str(exc)}, 400)
                    return
                direct_download = body.get("direct_download") is True
                max_works_cap = 150 if profile_plat == "xiaohongshu" and not direct_download and _use_native_engine() else 50
                max_works = body.get("max_works", 10)
                xmin, xmax = (0, 50) if profile_plat == "xiaohongshu" and not direct_download else (4, 20)
                min_images = body.get("min_images", xmin)
                max_images = body.get("max_images", xmax)
                if (isinstance(max_works, bool) or not isinstance(max_works, int) or not 1 <= max_works <= max_works_cap
                        or isinstance(min_images, bool) or not isinstance(min_images, int)
                        or isinstance(max_images, bool) or not isinstance(max_images, int)
                        or not 0 <= min_images <= max_images <= 50):
                    for path_str in skip_cleanup_files:
                        Path(path_str).unlink(missing_ok=True)
                    self._json({"error": f"主页作品数量需在 1–{max_works_cap}；图片范围需满足 0 ≤ 最小张数 ≤ 最大张数 ≤ 50"}, 400)
                    return
                command = [
                    _python_console_executable(), str(TOOLBOX_PROJECT / "jianghu_cli.py"),
                    "--bridge-dir", str(TOOLBOX_BRIDGE_DIR), "--timeout", "120",
                    "extract-author", "--url", profile_url,
                    "--max-works", str(max_works),
                    "--min-images", str(min_images),
                    "--max-images", str(max_images),
                    "--output-dir", output_dir,
                    "--image-format", image_format,
                    "--title-template", title_template,
                    "--set-file-time" if set_file_time else "--no-set-file-time",
                ]
                if not direct_download:
                    command.append("--no-auto-download")
                command.extend(skip_cmd_args)
                kind = "homepage"
                label = "小红书主页" if profile_plat == "xiaohongshu" else "抖音主页"
                request = {
                    "platform": profile_plat,
                    "profile_url": profile_url,
                    "max_works": max_works,
                    "min_images": min_images,
                    "max_images": max_images,
                    "direct_download": direct_download,
                    "auto_ingest_material": auto_ingest_param,
                    "skip_downloaded_history": skip_downloaded_history,
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                    "title_template": title_template,
                    "_command": command,
                    "_cleanup_files": skip_cleanup_files,
                }
            else:
                keyword = body.get("keyword", "")
                if not isinstance(keyword, str) or not keyword.strip() or len(keyword.strip()) > 100 or "\n" in keyword or "\r" in keyword:
                    for path_str in skip_cleanup_files:
                        Path(path_str).unlink(missing_ok=True)
                    self._json({"error": "请填写一个不超过 100 个字符的关键词"}, 400)
                    return
                count = body.get("count", 20)
                all_results = bool(body.get("all_results", False)) or count == 0
                min_images = body.get("min_images", 4)
                max_images = body.get("max_images", 20)
                if (isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 500
                        or isinstance(min_images, bool) or not isinstance(min_images, int)
                        or isinstance(max_images, bool) or not isinstance(max_images, int)
                        or not 0 <= min_images <= max_images <= 50):
                    for path_str in skip_cleanup_files:
                        Path(path_str).unlink(missing_ok=True)
                    self._json({"error": "数量需为 0–500（0=全部）；图片范围需满足 0 ≤ 最小张数 ≤ 最大张数 ≤ 50"}, 400)
                    return
                effective_count = 300 if all_results else count
                cli_timeout = max(60, min(180, effective_count * 2 + 40))
                wait_seconds = max(180, min(1500, effective_count * 8 + 60))
                raw_mtype = str(body.get("media_type") or "").strip().lower()
                if raw_mtype not in {"image", "video", "all"}:
                    media_type = "all" if bool(body.get("allow_video", False)) else "image"
                else:
                    media_type = raw_mtype
                allow_video = media_type in {"video", "all"}
                no_filter = bool(body.get("no_filter", False))
                direct_download = bool(body.get("direct_download", True))
                command = [
                    _python_console_executable(), str(TOOLBOX_PROJECT / "jianghu_cli.py"),
                    "--bridge-dir", str(TOOLBOX_BRIDGE_DIR), "--timeout", str(cli_timeout),
                    "extract-keyword", "--platform", requested_platform, "--keyword", keyword.strip(),
                    "--count", str(effective_count), "--min-images", str(min_images),
                    "--max-images", str(max_images), "--wait-seconds", str(wait_seconds),
                    "--output-dir", output_dir,
                    "--image-format", image_format,
                    "--title-template", title_template,
                    "--set-file-time" if set_file_time else "--no-set-file-time",
                ]
                if all_results and requested_platform == "douyin" and not allow_video:
                    command.append("--all-results")
                if allow_video:
                    command.append("--allow-video")
                if no_filter:
                    command.append("--no-filter")
                if not direct_download:
                    command.append("--metadata-only")
                command.extend(skip_cmd_args)
                web_sort = str(body.get("web_sort") or kw_cfg.get("web_sort") or "综合排序").strip()
                web_publish_time = str(body.get("web_publish_time") or kw_cfg.get("web_publish_time") or "不限").strip()
                kind = "keyword"
                plat_cn = "小红书" if requested_platform == "xiaohongshu" else "抖音"
                label = f"{plat_cn}关键词：{keyword.strip()}"
                request = {
                    "platform": requested_platform,
                    "keyword": keyword.strip(),
                    "count": count,
                    "min_images": min_images,
                    "max_images": max_images,
                    "allow_video": allow_video,
                    "media_type": media_type,
                    "no_filter": no_filter,
                    "direct_download": direct_download,
                    "web_sort": web_sort,
                    "web_publish_time": web_publish_time,
                    "auto_ingest_material": auto_ingest_param,
                    "skip_downloaded_history": skip_downloaded_history,
                    "output_dir": output_dir,
                    "mode": mode,
                    "image_format": image_format,
                    "title_template": title_template,
                    "_command": command,
                    "_cleanup_files": skip_cleanup_files,
                }

            idempotency_key = self.headers.get("Idempotency-Key", "").strip()
            if len(idempotency_key) > 128:
                for path_str in skip_cleanup_files:
                    Path(path_str).unlink(missing_ok=True)
                self._json({"error": "Idempotency-Key 最长 128 个字符"}, 400)
                return
            task, error, code = _create_collection_task(kind, label, request, idempotency_key)
            if error:
                for path_str in skip_cleanup_files:
                    Path(path_str).unlink(missing_ok=True)
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
        dl_cfg = (toolbox_store.get_settings(bridge_dir=TOOLBOX_BRIDGE_DIR) or {}).get("download", {})
        output_dir = body.get("output_dir") or dl_cfg.get("output_dir") or DEFAULT_OUTPUT_DIR
        if not isinstance(output_dir, str) or not output_dir.strip():
            self._json({"error": "保存位置格式无效"}, 400)
            return
        mode = body.get("mode", dl_cfg.get("delay_mode") or "auto")
        if mode not in DELAY_MODES:
            self._json({"error": "下载节奏无效", "supported_modes": sorted(DELAY_MODES)}, 400)
            return
        adaptive = mode == "auto"
        delay = DELAY_MODES[mode]
        image_format = body.get("image_format") or dl_cfg.get("image_format") or "jpg"
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


def _find_app_browser():
    candidates = [
        shutil.which("msedge.exe") or shutil.which("msedge"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        shutil.which("chrome.exe") or shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        candidates.extend([
            str(Path(local_app) / "Microsoft" / "Edge" / "Application" / "msedge.exe"),
            str(Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe"),
        ])
    for item in candidates:
        if item and Path(item).is_file():
            return str(Path(item))
    return None


def _is_server_alive(url):
    from urllib.error import URLError
    from urllib.request import urlopen

    try:
        with urlopen(url + "/api/v1/health", timeout=1.2) as resp:
            return resp.status == 200
    except (OSError, URLError, ValueError):
        return False


def _app_icon_paths():
    assets = PROJECT_ROOT / "assets"
    ico = assets / "universal-collector.ico"
    png = assets / "universal-collector-256.png"
    if not ico.is_file():
        ico = assets / "red-sweet-potato-download.ico"
    if not png.is_file():
        png = assets / "red-sweet-potato-download-256.png"
    return (ico if ico.is_file() else None), (png if png.is_file() else None)


def _apply_windows_taskbar_icon(title_keyword="万能下载器"):
    """Assign standalone taskbar AUMID + WM_SETICON to the workbench window."""
    if os.name != "nt":
        return 0
    ico_path, _ = _app_icon_paths()
    if ico_path is None:
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    except OSError:
        return 0

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class _PROPERTYKEY(ctypes.Structure):
        _fields_ = [("fmtid", _GUID), ("pid", wintypes.DWORD)]

    class _PROPVARIANT(ctypes.Structure):
        _fields_ = [
            ("vt", ctypes.c_ushort),
            ("wReserved1", ctypes.c_ushort),
            ("wReserved2", ctypes.c_ushort),
            ("wReserved3", ctypes.c_ushort),
            ("pwszVal", ctypes.c_wchar_p),
            ("pad", ctypes.c_size_t),
        ]

    IID_IPropertyStore = _GUID(0x886D8EEB, 0x8CF2, 0x4446, (ctypes.c_ubyte * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
    FMTID_AUM = _GUID(0x9F4C2855, 0x9F79, 0x4B39, (ctypes.c_ubyte * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3))
    PKEY_ID = _PROPERTYKEY(FMTID_AUM, 5)
    PKEY_ICON = _PROPERTYKEY(FMTID_AUM, 3)
    PKEY_NAME = _PROPERTYKEY(FMTID_AUM, 4)

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1
    VT_LPWSTR = 31

    h_big = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
    h_small = user32.LoadImageW(None, str(ico_path), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    if not h_big and not h_small:
        return 0

    matched = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(512)
        if user32.GetWindowTextW(hwnd, buf, 512) > 0:
            title = buf.value
            if title_keyword in title or "万能采集器" in title:
                matched.append(hwnd)
        return True

    user32.EnumWindows(enum_proc(_cb), 0)
    if not matched:
        return 0

    ole_init = False
    try:
        ole_init = ole32.CoInitialize(None) >= 0
    except Exception:
        pass

    shell32.SHGetPropertyStoreForWindow.argtypes = [
        wintypes.HWND, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)
    ]
    shell32.SHGetPropertyStoreForWindow.restype = ctypes.c_long

    updated = 0
    try:
        for hwnd in matched:
            if h_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, h_small)
            if h_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, h_big)
            try:
                store_ptr = ctypes.c_void_p()
                hr = shell32.SHGetPropertyStoreForWindow(hwnd, ctypes.byref(IID_IPropertyStore), ctypes.byref(store_ptr))
                if hr == 0 and store_ptr.value:
                    vtbl = ctypes.cast(
                        ctypes.cast(store_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents,
                        ctypes.POINTER(ctypes.c_void_p),
                    )
                    # IPropertyStore: QI(0), AddRef(1), Release(2), GetCount(3), GetAt(4), GetValue(5), SetValue(6), Commit(7)
                    set_val_fn = ctypes.WINFUNCTYPE(
                        ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT)
                    )(vtbl[6])
                    commit_fn = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)(vtbl[7])
                    release_fn = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtbl[2])
                    for pkey, val_str in (
                        (PKEY_ID, "UniversalCollector.Workbench.Desktop"),
                        (PKEY_ICON, f"{ico_path},0"),
                        (PKEY_NAME, "万能采集器"),
                    ):
                        pv = _PROPVARIANT(vt=VT_LPWSTR, pwszVal=val_str)
                        set_val_fn(store_ptr, ctypes.byref(pkey), ctypes.byref(pv))
                    commit_fn(store_ptr)
                    release_fn(store_ptr)
            except Exception:
                pass
            updated += 1
    finally:
        if ole_init:
            try:
                ole32.CoUninitialize()
            except Exception:
                pass
    return updated


def _open_workbench_ui(url, prefer_app=True):
    if prefer_app:
        native_shell = PROJECT_ROOT / "desktop_shell" / "万能采集器.exe"
        if native_shell.is_file():
            try:
                subprocess.Popen([str(native_shell)], cwd=str(native_shell.parent))
                return
            except OSError:
                pass
        browser = _find_app_browser()
        if browser:
            profile = Path.home() / ".xhs-dl" / "app-window-profile"
            try:
                profile.mkdir(parents=True, exist_ok=True)
                kwargs = {}
                if os.name == "nt":
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 1  # SW_SHOWNORMAL
                    kwargs["startupinfo"] = si
                subprocess.Popen(
                    [
                        browser,
                        f"--app={url}",
                        "--window-size=1520,940",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-background-mode",
                        f"--user-data-dir={profile}",
                    ],
                    **kwargs,
                )
                for delay in (1.2, 3.0):
                    threading.Timer(delay, _apply_windows_taskbar_icon).start()
                return
            except OSError:
                pass
    webbrowser.open(url)


def main(argv=None):
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="ignore")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="ignore")
    parser = argparse.ArgumentParser(description=f"{APP_NAME} 统一工作台服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5678)
    parser.add_argument("--app", action="store_true", help="优先以独立桌面应用窗口打开")
    parser.add_argument("--browser", action="store_true", help="以系统默认浏览器打开")
    parser.add_argument("--no-open", action="store_true", help="仅启动服务，不自动打开窗口")
    args, _ = parser.parse_known_args(argv)

    url = f"http://{args.host}:{args.port}"
    prefer_app = bool(args.app or not args.browser)

    if _is_server_alive(url):
        print(f"{APP_NAME} V{__version__} 已在运行: {url}")
        if not args.no_open:
            _open_workbench_ui(url, prefer_app=prefer_app)
        return

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("{} V{} Web: {}".format(APP_NAME, __version__, url))
    print("Press Ctrl+C to stop")
    if not args.no_open:
        threading.Timer(0.45, lambda: _open_workbench_ui(url, prefer_app=prefer_app)).start()
    else:
        threading.Timer(0.8, _apply_windows_taskbar_icon).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
