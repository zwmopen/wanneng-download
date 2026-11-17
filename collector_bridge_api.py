# -*- coding: utf-8 -*-
"""本地万能采集器桥接 API。

这个服务给其他 AI 一个可验证的本机入口：提交链接，拿到 ``job_id``，
轮询真实状态，再读取已经落盘的媒体文件和元数据。XHS 模板任务只读取
XHS-Downloader 本地设置中已保存的 Cookie，不读取浏览器 Cookie；不会把
“已入队”伪报成“已解析”。默认只监听 127.0.0.1。

协议的最小约定：

* ``POST /api/v1/jobs`` 或 ``POST /api/v1/parse``：提交文本/链接；
* ``GET /api/v1/jobs/<job_id>``：读取回执和逐链接结果；
* ``GET /api/v1/jobs/<job_id>/files/<index>``：读取已经核实存在的本地文件；
* ``GET /api/v1/capabilities``、``GET /api/v1/status``：能力与运行状态。

长任务只使用一个串行工作线程，避免剪贴板采集器的全局暂存目录被并发覆盖。
"""

from __future__ import annotations

import argparse
import copy
import json
import mimetypes
import os
import queue
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit


PROJECT_ROOT = Path(__file__).resolve().parent
JOBS_FILE = PROJECT_ROOT / "collector_bridge_jobs.json"
BRIDGE_STAGING_DIR = PROJECT_ROOT / "bridge_staging"
UI_FILE = PROJECT_ROOT / "collector_bridge_ui.html"
DOC_FILE = PROJECT_ROOT / "docs" / "collector-bridge-api.md"
PROTOCOL = "collector-bridge/1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_LINKS = 100
MAX_PERSISTED_JOBS = 200

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif", ".bmp", ".avif",
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
}
TEXT_EXTENSIONS = {".txt", ".md", ".json"}
SENSITIVE_QUERY_KEYS = {"xsec_token", "xsec_source", "token", "access_token"}


try:
    import universal_clipboard_collector as _collector
except Exception as exc:  # pragma: no cover - reported through capabilities/status
    _collector = None
    _COLLECTOR_IMPORT_ERROR = str(exc)
else:
    _COLLECTOR_IMPORT_ERROR = ""

try:
    from xhs_dl.core.downloader import extract_urls_from_text
    from xhs_dl.core.platforms import detect_platform
    from xhs_dl.core.unified_downloader import UnifiedDownloader
except Exception as exc:  # pragma: no cover - reported through capabilities/status
    extract_urls_from_text = None
    detect_platform = None
    UnifiedDownloader = None
    _ENGINE_IMPORT_ERROR = str(exc)
else:
    _ENGINE_IMPORT_ERROR = ""


JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = threading.RLock()
JOB_QUEUE: queue.Queue[str] = queue.Queue()
EXECUTION_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _redact_url(value: str) -> str:
    """Remove access-like query values from status/receipt payloads."""
    try:
        parts = urlsplit(str(value))
        if not parts.query:
            return str(value)
        kept: list[tuple[str, str]] = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in SENSITIVE_QUERY_KEYS:
                kept.append((key, "[redacted]"))
            else:
                kept.append((key, val))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))
    except Exception:
        return str(value)


def _redact_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)([?&](?:xsec_token|xsec_source|token|access_token)=)[^&\s]+", r"\1[redacted]", text)
    return text[:1000]


def _public_value(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {str(k): _public_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_public_value(v, key) for v in value]
    if isinstance(value, str):
        if "url" in key.lower() or key.lower() in SENSITIVE_QUERY_KEYS:
            return _redact_url(value)
        return value[:4000]
    return value


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _persist_jobs_locked() -> None:
    ordered = sorted(JOBS.values(), key=lambda item: item.get("created_at", ""))[-MAX_PERSISTED_JOBS:]
    _atomic_write_json(JOBS_FILE, {"version": 1, "updated_at": utc_now(), "jobs": ordered})


def _load_jobs() -> None:
    data = _read_json_file(JOBS_FILE, {})
    loaded = data.get("jobs", []) if isinstance(data, dict) else []
    if not isinstance(loaded, list):
        return
    with JOBS_LOCK:
        for item in loaded[-MAX_PERSISTED_JOBS:]:
            if not isinstance(item, dict) or not item.get("job_id"):
                continue
            status = item.get("status")
            if status in {"queued", "running", "accepted"}:
                item["status"] = "failed"
                item["error"] = "桥接服务曾重启，未完成任务未自动恢复；请用原链接新建任务"
                item["retryable"] = True
                item["updated_at"] = utc_now()
            JOBS[str(item["job_id"])] = item


def _collector_paths() -> list[Path]:
    # Do not expose the repository itself through an asset path. Only the
    # configured material/download roots and this bridge's staging directory
    # are eligible for file reads.
    paths: list[Path] = [BRIDGE_STAGING_DIR]
    if _collector is not None:
        for name in ("BASE_MATERIAL_DIR", "DATA_DIR", "C_DOWNLOADS_DIR", "TEMP_DOWNLOAD_DIR"):
            value = getattr(_collector, name, None)
            if value:
                paths.append(Path(value))
    return [path.expanduser().resolve() for path in paths]


def _allowed_file(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        if not resolved.is_file():
            return False
        for root in _collector_paths():
            try:
                if os.path.commonpath([str(resolved), str(root)]) == str(root):
                    return True
            except ValueError:
                continue
    except OSError:
        return False
    return False


def _kind_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}:
        return "video"
    if suffix in MEDIA_EXTENSIONS:
        return "image"
    if path.name == "metadata.json":
        return "metadata"
    if suffix in TEXT_EXTENSIONS:
        return "text"
    return "file"


def _enumerate_assets(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    target_value = metadata.get("target_dir") if isinstance(metadata, dict) else ""
    if not target_value:
        return []
    try:
        target_dir = Path(str(target_value)).expanduser().resolve()
    except OSError:
        return []
    if not target_dir.is_dir():
        return []
    files: list[Path] = []
    try:
        for path in target_dir.iterdir():
            if path.is_file() and (path.suffix.lower() in MEDIA_EXTENSIONS or path.name in {"文案.txt", "metadata.json"}):
                if _allowed_file(path):
                    files.append(path.resolve())
    except OSError:
        return []
    assets: list[dict[str, Any]] = []
    for path in sorted(files, key=lambda item: (item.name.lower(), item.name)):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        assets.append({"name": path.name, "kind": _kind_for_path(path), "size": size, "path": str(path)})
    return assets


def _pause_info() -> dict[str, Any]:
    if _collector is None:
        return {"paused": False, "reason": "采集器模块未加载", "source": "unavailable"}
    pause_file = Path(getattr(_collector, "PAUSE_FILE", PROJECT_ROOT / "clipboard-collector.paused"))
    if not pause_file.exists():
        return {"paused": False, "file": str(pause_file)}
    data = _read_json_file(pause_file, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("paused", True)
    data["file"] = str(pause_file)
    data["reason"] = _redact_text(data.get("reason", "暂停标记存在"))
    return data


def _pause_blocks(platform: str, manual_override: bool = False) -> tuple[bool, str, bool]:
    """Return (blocked, reason, manual_override).

    The current pause marker is specifically for an XHS public-link/login issue.
    A direct Douyin API request can continue in that case because it uses a
    separate public browser engine. Any generic/global pause remains fail-closed.
    """
    info = _pause_info()
    if not info.get("paused"):
        return False, "", False
    reason = str(info.get("reason") or "采集暂停标记存在")
    is_xhs_specific = bool(re.search(r"小红书|xhs|登录|public.?note", reason, re.I))
    if platform == "douyin" and is_xhs_specific:
        return False, reason, True
    # The daemon remains paused, but an explicitly submitted public XHS link
    # carrying its own xsec_token may be tried once through the bridge. This
    # does not resume the background queue or invent authentication for ID-only
    # inputs; it only prevents the stale global pause marker from hiding the
    # real result of a user-provided public link.
    if platform == "xhs" and manual_override:
        return False, reason, True
    return True, reason, False


def _extract_targets(raw_text: str = "", links: Iterable[Any] | None = None) -> list[dict[str, str]]:
    candidates: list[tuple[str, str]] = []
    for item in links or []:
        if isinstance(item, dict):
            value = str(item.get("url") or item.get("link") or "").strip()
            hint = str(item.get("title_hint") or item.get("title") or "").strip()
        else:
            value = str(item or "").strip()
            hint = ""
        if not value:
            continue
        if extract_urls_from_text is not None:
            found = extract_urls_from_text(re.sub(r"https?\\+://", "https://", value))
            if found:
                candidates.extend((url, hint) for url in found)
                continue
        candidates.append((value, hint))

    normalized_text = re.sub(r"https?\\+://", "https://", raw_text or "")
    if normalized_text and _collector is not None:
        try:
            for url, hint, _segment in _collector.extract_all_clean_targets(normalized_text):
                candidates.append((url, hint))
        except Exception:
            pass
    if normalized_text and extract_urls_from_text is not None:
        try:
            candidates.extend((url, "") for url in extract_urls_from_text(normalized_text))
        except Exception:
            pass

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_url, hint in candidates:
        url = str(raw_url).strip().strip(".,;:!?()[]{}<>，。；：！？、）】》」』")
        if not re.match(r"^https?://", url, re.I):
            continue
        key = url.rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        platform = detect_platform(url) if detect_platform is not None else "unknown"
        result.append({"url": url, "title_hint": str(hint or "")[:300], "platform": platform})
    return result


def _new_link_record(target: dict[str, str]) -> dict[str, Any]:
    return {
        "url": _redact_url(target["url"]),
        "platform": target.get("platform", "unknown"),
        "title_hint": target.get("title_hint", ""),
        "status": "queued",
        "success": False,
        "error": "",
        "retryable": False,
        "manual_api_override": False,
        "metadata": {},
        "assets": [],
    }


def _set_job(job_id: str, **values: Any) -> dict[str, Any] | None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return None
        job.update(values)
        job["updated_at"] = utc_now()
        _persist_jobs_locked()
        return copy.deepcopy(job)


def _update_link(job_id: str, index: int, **values: Any) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        links = job.get("links", [])
        if index >= len(links):
            return
        links[index].update(values)
        job["updated_at"] = utc_now()
        _persist_jobs_locked()


def _direct_unified_download(job_id: str, index: int, url: str, image_format: str, max_images: int) -> tuple[bool, str, dict[str, Any], list[dict[str, Any]], bool]:
    """Download media into isolated bridge staging without general-material routing."""
    if UnifiedDownloader is None:
        return False, _ENGINE_IMPORT_ERROR or "万能下载器核心未加载", {}, [], True
    output_dir = BRIDGE_STAGING_DIR / job_id / f"link-{index + 1:03d}"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        downloader = UnifiedDownloader(
            output_dir=str(output_dir), delay=(0, 0), image_format=image_format, max_images=max_images,
        )
        result = downloader.download([url])
        item = result.results[0] if result.results else None
        if item is None or (not item.success and not item.deduplicated):
            error = getattr(item, "error", "万能引擎未产出媒体") if item is not None else "万能引擎未产出媒体"
            return False, _redact_text(error), {}, [], True
        target_dir = Path(item.save_dir or output_dir)
        metadata = {
            "title": item.title,
            "author": item.author,
            "note_id": item.note_id,
            "platform": detect_platform(url) if detect_platform else "generic",
            "note_type": item.note_type,
            "url": url,
            "target_dir": str(target_dir),
            "images_count": item.image_success,
            "engine": item.engine,
            "stats": {
                "likes": str(getattr(item, "likes", "") or ""),
                "collections": str(getattr(item, "collections", "") or ""),
                "comments": str(getattr(item, "comments", "") or ""),
            },
            "status": "success",
        }
        assets = _enumerate_assets(metadata)
        if not assets:
            return False, "下载引擎返回成功，但未核实到非空媒体文件", metadata, [], True
        metadata["images_count"] = sum(1 for asset in assets if asset.get("kind") == "image")
        metadata["deduplicated"] = bool(item.deduplicated)
        return True, "", metadata, assets, False
    except Exception as exc:
        return False, _redact_text(exc), {}, [], True


def _collect_one(job_id: str, index: int, target: dict[str, str], options: dict[str, Any]) -> dict[str, Any]:
    url = target["url"]
    platform = target.get("platform", "unknown")
    base = _new_link_record(target)
    base["status"] = "running"
    base["started_at"] = utc_now()
    _update_link(job_id, index, **base)

    if platform == "unknown":
        base.update({"status": "blocked", "error": "暂不支持该链接来源", "retryable": False, "completed_at": utc_now()})
        _update_link(job_id, index, **base)
        return base

    if options.get("dry_run"):
        base.update({
            "status": "validated",
            "success": None,
            "error": "",
            "retryable": False,
            "completed_at": utc_now(),
            "metadata": {"platform": platform, "no_cookie_path": True},
        })
        _update_link(job_id, index, **base)
        return base

    blocked, reason, manual_override = _pause_blocks(platform, bool(options.get("manual_override")))
    if blocked:
        base.update({
            "status": "blocked",
            "error": f"采集暂停：{_redact_text(reason)}",
            "retryable": True,
            "completed_at": utc_now(),
        })
        _update_link(job_id, index, **base)
        return base

    image_format = str(options.get("image_format") or "keep")
    if image_format not in {"jpg", "png", "keep"}:
        image_format = "jpg"
    try:
        max_images = min(max(1, int(options.get("max_images", 30))), 50)
    except (TypeError, ValueError):
        max_images = 30

    try:
        with EXECUTION_LOCK:
            if platform in {"xhs", "douyin"} and not options.get("template_library"):
                if _collector is None:
                    ok, message, metadata = False, _COLLECTOR_IMPORT_ERROR or "剪切板采集器模块未加载", {}
                else:
                    ok, message, metadata = _collector.execute_download_and_file(url)
                assets = _enumerate_assets(metadata if isinstance(metadata, dict) else {}) if ok else []
            else:
                ok, message, metadata, assets, _retryable = _direct_unified_download(
                    job_id, index, url, image_format, max_images,
                )
    except Exception as exc:
        ok, message, metadata, assets = False, _redact_text(exc), {}, []

    if ok and assets:
        base.update({
            "status": "completed",
            "success": True,
            "error": "",
            "retryable": False,
            "manual_api_override": manual_override,
            "metadata": _public_value(metadata if isinstance(metadata, dict) else {}),
            "assets": assets,
            "completed_at": utc_now(),
        })
    elif ok:
        base.update({
            "status": "failed",
            "error": "下载引擎未核实到已落盘媒体文件",
            "retryable": True,
            "manual_api_override": manual_override,
            "metadata": _public_value(metadata if isinstance(metadata, dict) else {}),
            "completed_at": utc_now(),
        })
    else:
        base.update({
            "status": "failed",
            "error": _redact_text(message or "下载失败，未返回具体原因"),
            "retryable": True,
            "manual_api_override": manual_override,
            "metadata": _public_value(metadata if isinstance(metadata, dict) else {}),
            "completed_at": utc_now(),
        })
    _update_link(job_id, index, **base)
    return base


def _finalize_assets(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        all_assets: list[dict[str, Any]] = []
        for link_index, link in enumerate(job.get("links", [])):
            updated_assets: list[dict[str, Any]] = []
            for asset in link.get("assets", []):
                path = Path(str(asset.get("path", "")))
                if not _allowed_file(path):
                    continue
                index = len(all_assets)
                record = {
                    "index": index,
                    "link_index": link_index,
                    "name": asset.get("name", path.name),
                    "kind": asset.get("kind", _kind_for_path(path)),
                    "size": int(asset.get("size", path.stat().st_size if path.exists() else 0)),
                    "path": str(path.resolve()),
                    "download_url": f"/api/v1/jobs/{job_id}/files/{index}",
                }
                all_assets.append(record)
                updated_assets.append({k: v for k, v in record.items() if k != "link_index"})
            link["assets"] = updated_assets
        job.setdefault("result", {})["assets"] = all_assets
        job["updated_at"] = utc_now()
        _persist_jobs_locked()


def _run_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
        job["started_at"] = utc_now()
        job["updated_at"] = utc_now()
        _persist_jobs_locked()
        targets = [
            {"url": str(link.get("_raw_url") or link.get("url", "")), "platform": link.get("platform", "unknown"), "title_hint": link.get("title_hint", "")}
            for link in job.get("links", [])
        ]
        options = dict(job.get("options", {}))

    for index, target in enumerate(targets):
        _collect_one(job_id, index, target, options)

    _finalize_assets(job_id)
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job is None:
            return
        links = job.get("links", [])
        dry_run = bool(options.get("dry_run"))
        succeeded = sum(1 for item in links if item.get("success") is True)
        failed = sum(1 for item in links if item.get("status") == "failed")
        blocked = sum(1 for item in links if item.get("status") == "blocked")
        validated = sum(1 for item in links if item.get("status") == "validated")
        if dry_run:
            status = "completed"
        elif succeeded == len(links) and links:
            status = "completed"
        elif succeeded == 0 and blocked == len(links) and links:
            status = "blocked"
        elif succeeded:
            status = "partial"
        else:
            status = "failed"
        job["status"] = status
        job["done_at"] = utc_now()
        job["result"] = {
            "dry_run": dry_run,
            "total": len(links),
            "succeeded": succeeded,
            "failed": failed,
            "blocked": blocked,
            "validated": validated,
            "assets": job.get("result", {}).get("assets", []),
        }
        job["updated_at"] = utc_now()
        _persist_jobs_locked()


def _worker_loop() -> None:
    while True:
        job_id = JOB_QUEUE.get()
        try:
            _run_job(job_id)
        except Exception as exc:  # keep the bridge alive after one bad job
            _set_job(job_id, status="failed", error=_redact_text(exc), retryable=True, done_at=utc_now())
        finally:
            JOB_QUEUE.task_done()


def _start_worker() -> None:
    thread = threading.Thread(target=_worker_loop, name="collector-bridge-worker", daemon=True)
    thread.start()


def _queue_job(targets: list[dict[str, str]], client: dict[str, Any], conversation_id: str, options: dict[str, Any]) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    message_id = f"msg_{uuid.uuid4().hex}"
    task_id = f"task_{job_id}"
    links = [_new_link_record(target) for target in targets]
    for index, target in enumerate(targets):
        links[index]["_raw_url"] = target["url"]  # internal only; stripped in public payload
    now = utc_now()
    job = {
        "protocol": PROTOCOL,
        "message_id": message_id,
        "conversation_id": conversation_id,
        "task_id": task_id,
        "job_id": job_id,
        "operation": "collect_and_parse",
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "client": {"name": str(client.get("name") or "unknown")[:120], "version": str(client.get("version") or "")[:80]},
        "receipt": {"state": "accepted", "accepted_at": now},
        "links": links,
        "options": {
            "dry_run": bool(options.get("dry_run")),
            "image_format": options.get("image_format", "keep"),
            "max_images": options.get("max_images", 30),
            "manual_override": bool(options.get("manual_override")),
            "template_library": bool(options.get("template_library")),
        },
        "result": {"dry_run": bool(options.get("dry_run")), "total": len(links), "succeeded": 0, "failed": 0, "blocked": 0, "validated": 0, "assets": []},
        "error": "",
        "retryable": False,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job
        _persist_jobs_locked()
    JOB_QUEUE.put(job_id)
    return _public_job(job)


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(job)
    value.pop("options", None)
    for link in value.get("links", []):
        link.pop("_raw_url", None)
    return value


def _job_list() -> dict[str, Any]:
    with JOBS_LOCK:
        jobs = sorted(JOBS.values(), key=lambda item: item.get("created_at", ""), reverse=True)
        items = []
        for job in jobs[:50]:
            result = job.get("result", {}) if isinstance(job.get("result"), dict) else {}
            items.append({
                "job_id": job.get("job_id"),
                "task_id": job.get("task_id"),
                "conversation_id": job.get("conversation_id"),
                "operation": job.get("operation"),
                "status": job.get("status"),
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
                "client": job.get("client", {}),
                "result": {
                    "total": result.get("total", len(job.get("links", []))),
                    "succeeded": result.get("succeeded", 0),
                    "failed": result.get("failed", 0),
                    "blocked": result.get("blocked", 0),
                    "validated": result.get("validated", 0),
                },
            })
    return {
        "protocol": PROTOCOL,
        "message_id": f"msg_{uuid.uuid4().hex}",
        "api_online": True,
        "items": items,
    }


def _capabilities() -> dict[str, Any]:
    pause = _pause_info()
    xhs_state = "blocked" if pause.get("paused") and re.search(r"小红书|xhs|登录", str(pause.get("reason", "")), re.I) else "unverified"
    engine_home = Path(os.environ.get("XHS_DOWNLOADER_HOME") or PROJECT_ROOT.parent / "XHS_Downloader")
    xhs_settings = _read_json_file(engine_home / "Volume" / "settings.json", {})
    xhs_cookie_configured = bool(str(xhs_settings.get("cookie") or "").strip()) if isinstance(xhs_settings, dict) else False
    return {
        "protocol": PROTOCOL,
        "service": "universal-collector-bridge",
        "api_online": True,
        "bind_default": DEFAULT_HOST,
        "related_web_ui": {
            "url": "http://127.0.0.1:5678/",
            "port": 5678,
            "role": "原版万能下载器 Web 界面；8766 控制台调用同一套本地引擎",
        },
        "operations": ["capabilities", "status", "collect_and_parse", "fetch_asset"],
        "authentication": {
            "cookies_used": xhs_cookie_configured,
            "browser_login_used": False,
            "public_only": not xhs_cookie_configured,
            "note": "只读取 XHS-Downloader 本机设置中已保存的 Cookie（只回报是否配置）；不读取浏览器 Cookie。" if xhs_cookie_configured else "当前只尝试公开链接；不会读取浏览器 Cookie。",
        },
        "platforms": {
            "xhs": {
                "state": xhs_state,
                "mode": "local_cli_saved_cookie" if xhs_cookie_configured else "local_cli_public_only",
                "cookie_configured": xhs_cookie_configured,
                "blocked_reason": pause.get("reason", "") if xhs_state == "blocked" else "",
                "manual_public_link": "24 位 ID 会转成公开笔记地址尝试；分享链接保留 xsec_token。能否下载取决于笔记公开状态及本机下载器登录配置。",
            },
            "douyin": {
                "state": "available",
                "mode": "local_browser_public_page",
                "pause_note": "仅在暂停标记明确针对小红书登录时允许手动 API 请求继续。",
            },
            "generic": {
                "state": "available_if_engine_supported",
                "mode": "existing_unified_engine",
            },
        },
        "result_contract": {
            "accepted_is_not_completed": True,
            "poll": "GET /api/v1/jobs/{job_id}",
            "asset_read": "GET /api/v1/jobs/{job_id}/files/{index}",
            "statuses": ["accepted", "queued", "running", "validated", "completed", "partial", "blocked", "failed"],
        },
        "module_errors": {"collector": _COLLECTOR_IMPORT_ERROR, "engine": _ENGINE_IMPORT_ERROR},
    }


def _queue_status() -> dict[str, Any]:
    queue_file = getattr(_collector, "QUEUE_FILE", PROJECT_ROOT / "clipboard_pending_queue.json") if _collector is not None else PROJECT_ROOT / "clipboard_pending_queue.json"
    history_file = getattr(_collector, "HISTORY_FILE", PROJECT_ROOT / "clipboard_history.json") if _collector is not None else PROJECT_ROOT / "clipboard_history.json"
    queue_data = _read_json_file(Path(queue_file), {})
    history_data = _read_json_file(Path(history_file), {})
    queue_items = queue_data.get("queue", []) if isinstance(queue_data, dict) else []
    history_items = history_data.get("urls", []) if isinstance(history_data, dict) else []
    heartbeat_file = getattr(_collector, "HEARTBEAT_FILE", PROJECT_ROOT / "collector_heartbeat.json") if _collector is not None else PROJECT_ROOT / "collector_heartbeat.json"
    heartbeat = _read_json_file(Path(heartbeat_file), {})
    timestamp = heartbeat.get("timestamp") if isinstance(heartbeat, dict) else None
    try:
        age = max(0.0, datetime.now(timezone.utc).timestamp() - float(timestamp)) if timestamp else None
    except (TypeError, ValueError):
        age = None
    return {
        "protocol": PROTOCOL,
        "message_id": f"msg_{uuid.uuid4().hex}",
        "api_online": True,
        "collector": {
            "pause": _pause_info(),
            "queue_count": len(queue_items) if isinstance(queue_items, list) else 0,
            "history_count": len(history_items) if isinstance(history_items, list) else 0,
            "heartbeat": heartbeat,
            "heartbeat_age_seconds": age,
            "process_alive": "unknown" if not heartbeat.get("pid") else "unverified",
        },
        "bridge": {
            "queued_jobs": JOB_QUEUE.qsize(),
            "persisted_jobs": len(JOBS),
            "worker": "serial",
        },
    }


def _queue_items() -> dict[str, Any]:
    queue_file = getattr(_collector, "QUEUE_FILE", PROJECT_ROOT / "clipboard_pending_queue.json") if _collector is not None else PROJECT_ROOT / "clipboard_pending_queue.json"
    data = _read_json_file(Path(queue_file), {})
    raw_items = data.get("queue", []) if isinstance(data, dict) else []
    items = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        items.append({
            "id": item.get("id", ""),
            "url": _redact_url(str(item.get("url", ""))),
            "title_hint": str(item.get("title_hint", ""))[:300],
            "status": item.get("status", "pending"),
            "retry_count": item.get("retry_count", 0),
            "last_error": _redact_text(item.get("last_error", "")) if item.get("last_error") else "",
            "added_at": item.get("added_at", ""),
        })
    return {
        "protocol": PROTOCOL,
        "message_id": f"msg_{uuid.uuid4().hex}",
        "api_online": True,
        "queue_count": len(items),
        "items": items,
    }


def _history_items() -> dict[str, Any]:
    history_file = getattr(_collector, "HISTORY_FILE", PROJECT_ROOT / "clipboard_history.json") if _collector is not None else PROJECT_ROOT / "clipboard_history.json"
    data = _read_json_file(Path(history_file), {})
    raw_urls = data.get("urls", []) if isinstance(data, dict) else []
    urls = [_redact_url(str(value)) for value in raw_urls if value]
    return {
        "protocol": PROTOCOL,
        "message_id": f"msg_{uuid.uuid4().hex}",
        "api_online": True,
        "history_count": len(urls),
        "updated_at": data.get("updated_at", "") if isinstance(data, dict) else "",
        "items": list(reversed(urls[-50:])),
    }


def _queue_url_for_id(item_id: str) -> str:
    queue_file = getattr(_collector, "QUEUE_FILE", PROJECT_ROOT / "clipboard_pending_queue.json") if _collector is not None else PROJECT_ROOT / "clipboard_pending_queue.json"
    data = _read_json_file(Path(queue_file), {})
    raw_items = data.get("queue", []) if isinstance(data, dict) else []
    for item in raw_items if isinstance(raw_items, list) else []:
        if isinstance(item, dict) and str(item.get("id", "")) == item_id:
            url = str(item.get("url", ""))
            if re.match(r"^https?://", url, re.I):
                return url
            break
    return ""


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "UniversalCollectorBridge/1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep the console useful for the server owner without dumping request bodies.
        print(f"[collector-bridge] {self.address_string()} {fmt % args}")

    def _headers(self, content_type: str, length: int | None = None) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Client-Name, X-Client-Version")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        if length is not None:
            self.send_header("Content-Length", str(length))

    def _json(self, value: Any, status: int = 200) -> None:
        data = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self._headers("application/json; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"protocol": PROTOCOL, "message_id": f"msg_{uuid.uuid4().hex}", "status": "failed", "error": _redact_text(message)}, status)

    def _read_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._error("Content-Length 无效", 400)
            return None
        if length <= 0:
            self._error("请求体不能为空", 400)
            return None
        if length > MAX_BODY_BYTES:
            self._error("请求体过大，请分批提交", 413)
            return None
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error("请求必须是 UTF-8 JSON", 400)
            return None
        if not isinstance(value, dict):
            self._error("JSON 根节点必须是对象", 400)
            return None
        return value

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._headers("text/plain; charset=utf-8", 0)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path in {"/", "/ui"}:
            self._serve_ui()
            return
        if path == "/docs/collector-bridge-api.md":
            self._serve_doc()
            return
        if path == "/api/v1/capabilities":
            self._json(_capabilities())
            return
        if path == "/api/v1/status":
            self._json(_queue_status())
            return
        if path == "/api/v1/queue":
            self._json(_queue_items())
            return
        if path == "/api/v1/history":
            self._json(_history_items())
            return
        match = re.fullmatch(r"/api/v1/queue/([A-Za-z0-9_-]+)/open", path)
        if match:
            target_url = _queue_url_for_id(match.group(1))
            if not target_url:
                self._error("队列链接不存在", 404)
                return
            self.send_response(302)
            self._headers("text/plain; charset=utf-8", 0)
            self.send_header("Location", target_url)
            self.end_headers()
            return
        if path == "/api/v1/jobs":
            self._json(_job_list())
            return
        match = re.fullmatch(r"/api/v1/jobs/([A-Za-z0-9_-]+)", path)
        if match:
            with JOBS_LOCK:
                job = copy.deepcopy(JOBS.get(match.group(1)))
            if job is None:
                self._error("任务不存在", 404)
            else:
                self._json(_public_job(job))
            return
        match = re.fullmatch(r"/api/v1/jobs/([A-Za-z0-9_-]+)/metadata", path)
        if match:
            with JOBS_LOCK:
                job = copy.deepcopy(JOBS.get(match.group(1)))
            if job is None:
                self._error("任务不存在", 404)
            else:
                self._json({"job_id": match.group(1), "status": job.get("status"), "result": job.get("result", {}), "links": job.get("links", [])})
            return
        match = re.fullmatch(r"/api/v1/jobs/([A-Za-z0-9_-]+)/files/(\d+)", path)
        if match:
            self._serve_asset(match.group(1), int(match.group(2)))
            return
        self._error("not found", 404)

    def _serve_ui(self) -> None:
        try:
            data = UI_FILE.read_bytes()
        except OSError:
            data = b"<!doctype html><meta charset='utf-8'><title>Collector bridge</title><p>collector_bridge_ui.html not found.</p>"
        self.send_response(200)
        self._headers("text/html; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_doc(self) -> None:
        try:
            data = DOC_FILE.read_bytes()
        except OSError:
            self._error("接口说明不存在", 404)
            return
        self.send_response(200)
        self._headers("text/markdown; charset=utf-8", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _serve_asset(self, job_id: str, asset_index: int) -> None:
        with JOBS_LOCK:
            job = copy.deepcopy(JOBS.get(job_id))
        if job is None:
            self._error("任务不存在", 404)
            return
        assets = job.get("result", {}).get("assets", [])
        if not isinstance(assets, list) or asset_index < 0 or asset_index >= len(assets):
            self._error("文件索引不存在", 404)
            return
        item = assets[asset_index]
        path = Path(str(item.get("path", "")))
        if not _allowed_file(path):
            self._error("文件不在允许读取范围，或已不在磁盘", 410)
            return
        try:
            data = path.read_bytes()
        except OSError:
            self._error("文件读取失败", 410)
            return
        self.send_response(200)
        self._headers(mimetypes.guess_type(path.name)[0] or "application/octet-stream", len(data))
        # ``send_header`` is latin-1 based. Keep an ASCII fallback and carry
        # the original UTF-8 filename through RFC 5987 for capable clients.
        ascii_name = path.name.encode("ascii", "replace").decode("ascii").replace('"', "_")
        encoded_name = quote(path.name, safe="")
        self.send_header("Content-Disposition", f'inline; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path.rstrip("/")
        if path not in {"/api/v1/jobs", "/api/v1/parse"}:
            self._error("not found", 404)
            return
        body = self._read_body()
        if body is None:
            return
        raw_text = body.get("text", "")
        if raw_text is not None and not isinstance(raw_text, str):
            self._error("text 必须是字符串", 400)
            return
        raw_links = body.get("links", [])
        if isinstance(raw_links, str):
            raw_links = [raw_links]
        if not isinstance(raw_links, list):
            self._error("links 必须是数组", 400)
            return
        targets = _extract_targets(raw_text or "", raw_links)
        if not targets:
            self._error("未检测到可处理的公开链接", 400)
            return
        if len(targets) > MAX_LINKS:
            self._error(f"单次最多提交 {MAX_LINKS} 条链接", 413)
            return
        client = body.get("client") if isinstance(body.get("client"), dict) else {}
        conversation_id = str(body.get("conversation_id") or f"conv_{uuid.uuid4().hex}")[:160]
        options = body.get("options") if isinstance(body.get("options"), dict) else {}
        safe_options = {
            "dry_run": bool(options.get("dry_run", False)),
            "image_format": str(options.get("image_format") or "keep"),
            "max_images": options.get("max_images", 30),
            "manual_override": bool(options.get("manual_override", False)),
            "template_library": bool(options.get("template_library", False)),
        }
        response = _queue_job(targets, client, conversation_id, safe_options)
        self._json(response, 202)


def create_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    _load_jobs()
    _start_worker()
    server = ThreadingHTTPServer((host, port), BridgeHandler)
    server.daemon_threads = True
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="万能采集器本地桥接 API")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址，默认仅本机")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口，默认 8766")
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"万能采集器桥接 API 已启动: http://{args.host}:{args.port}")
    print("能力: /api/v1/capabilities | 状态: /api/v1/status | 任务: /api/v1/jobs")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
