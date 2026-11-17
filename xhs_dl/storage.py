"""集中保存应用设置和精简下载历史。"""

import json
import hashlib
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


_LOCK = threading.Lock()
_CLAIM_LOCKS = {}
_CLAIM_LOCKS_GUARD = threading.Lock()
_MODES = {"auto", "fast", "normal", "cautious", "slow", "very-slow"}
_FORMATS = {"jpg", "png", "keep"}


def app_data_dir():
    root = os.environ.get("LOCALAPPDATA")
    path = Path(root) / "xhs-dl" if root else Path.home() / ".xhs-dl"
    path.mkdir(parents=True, exist_ok=True)
    return path


def history_path():
    return app_data_dir() / "history.json"


def settings_path():
    return app_data_dir() / "settings.json"


def download_claims_dir():
    """Return the shared same-note lock directory, with a writable-root override."""
    override = os.environ.get("XHS_DL_CLAIM_DIR")
    path = Path(override).expanduser() if override else app_data_dir() / "download_claims"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path, value):
    """Write JSON without sharing one fixed temp filename across processes.

    The clipboard daemon and the Web/desktop downloader can finish at the
    same time.  A shared ``history.json.tmp`` made those independent writers
    collide on Windows and turned an otherwise successful download into a
    failed task.  Give every writer its own sibling temp file and retry the
    final replace briefly when another process still has the target open.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    last_error = None
    for attempt in range(4):
        temporary = path.with_name(
            f".{path.name}.{os.getpid()}.{threading.get_ident()}."
            f"{uuid.uuid4().hex}.tmp"
        )
        try:
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, path)
            return
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.08 * (attempt + 1))
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    if last_error:
        raise last_error


@contextmanager
def _cross_process_lock(path):
    """Serialize history updates and same-item downloads across local processes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _url_identity(url):
    value = str(url or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
    except ValueError:
        return "url:" + value.rstrip("/").lower()

    host = (parts.hostname or "").lower()
    path = re.sub(r"/+", "/", parts.path or "").rstrip("/")
    if host in {"xhslink.cn", "xhslink.com"}:
        return "xhs-short:" + path
    if host in {"xiaohongshu.com", "www.xiaohongshu.com"}:
        match = re.search(r"/(?:explore|discovery/item)/([a-fA-F0-9]{16,})", path)
        if match:
            return "xhs-id:" + match.group(1).lower()
        return "xhs-url:" + path
    if host in {"douyin.com", "www.douyin.com"}:
        match = re.search(r"/(?:video|note)/(\d+)", path)
        if match:
            return "douyin-id:" + match.group(1)
    if host == "v.douyin.com":
        return "douyin-short:" + path

    # Generic media URLs may use query parameters as signed resource IDs.
    normalized_host = host[4:] if host.startswith("www.") else host
    normalized = urlunsplit((parts.scheme.lower() or "https", normalized_host, path, parts.query, ""))
    return "url:" + normalized


def _record_keys(item):
    if not isinstance(item, dict):
        return set()
    keys = set()
    note_id = str(item.get("笔记ID") or item.get("note_id") or "").strip()
    if note_id:
        keys.add("id:" + note_id.lower())
    url = item.get("下载网址") or item.get("url") or item.get("download_url") or ""
    identity = _url_identity(url)
    if identity:
        keys.add(identity)
        if identity.startswith("xhs-id:"):
            keys.add("id:" + identity.split(":", 1)[1])
    return keys


def _record_has_media(item):
    if not isinstance(item, dict):
        return False
    location_text = str(item.get("保存位置") or item.get("save_dir") or "").strip()
    if not location_text:
        return False
    location = Path(location_text)
    if not location.is_dir():
        return False
    try:
        return any(
            file.is_file() and file.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif", ".mp4", ".mov", ".webm"} and file.stat().st_size > 0
            for file in location.iterdir()
        )
    except OSError:
        return False


def find_downloaded(download_url="", note_id=""):
    """Return a successful local-history record matching a note ID or URL."""
    lookup = _record_keys({"下载网址": download_url, "笔记ID": note_id})
    if not lookup:
        return None
    entries = _read_json(history_path(), [])
    if not isinstance(entries, list):
        return None
    for item in reversed(entries):
        if isinstance(item, dict) and lookup.intersection(_record_keys(item)):
            return dict(item)
    return None


def same_download(download_url_a, download_url_b):
    """Compare public work links in a way stable across tracking parameters."""
    left = _url_identity(download_url_a)
    right = _url_identity(download_url_b)
    return bool(left and left == right)


def _merge_history_item(items, candidate):
    candidate_keys = _record_keys(candidate)
    if not candidate_keys:
        return False
    matches = [index for index, old in enumerate(items) if candidate_keys.intersection(_record_keys(old))]
    if not matches:
        items.append(candidate)
        return True
    first = matches[0]
    merged = dict(items[first])
    original = dict(merged)
    for key, value in candidate.items():
        if value not in (None, "") and (merged.get(key) in (None, "") or key in {"下载时间", "completed_at"}):
            merged[key] = value
    items[first] = merged
    for index in reversed(matches[1:]):
        items.pop(index)
    return len(matches) > 1 or merged != original


def merge_download_history(records):
    """Merge previously successful collectors into the common success ledger."""
    candidates = []
    for record in records or []:
        if isinstance(record, str):
            record = {"下载网址": record}
        if not isinstance(record, dict):
            continue
        url = record.get("下载网址") or record.get("url") or record.get("download_url") or ""
        if not url:
            continue
        candidates.append({
            "下载网址": str(url),
            "笔记ID": str(record.get("笔记ID") or record.get("note_id") or ""),
            "标题": str(record.get("标题") or record.get("title") or ""),
            "下载时间": str(record.get("下载时间") or record.get("completed_at") or ""),
        })
    if not candidates:
        return 0
    path = history_path()
    changed = False
    with _LOCK, _cross_process_lock(path.with_suffix(".lock")):
        items = _read_json(path, [])
        if not isinstance(items, list):
            items = []
        before = len(items)
        for candidate in candidates:
            changed = _merge_history_item(items, candidate) or changed
        changed = changed or len(items) != before
        if changed:
            try:
                _write_json(path, items)
            except OSError:
                pass
    return len(candidates)


@contextmanager
def download_claim(download_url):
    """Hold a per-work claim while downloading to prevent cross-app duplicates."""
    identity = _url_identity(download_url) or str(download_url)
    claim_name = hashlib.sha256(identity.encode("utf-8")).hexdigest() + ".lock"
    claim_path = download_claims_dir() / claim_name
    with _CLAIM_LOCKS_GUARD:
        thread_lock = _CLAIM_LOCKS.setdefault(identity, threading.Lock())
    with thread_lock:
        with _cross_process_lock(claim_path):
            existing = find_downloaded(download_url=download_url)
            # Older history entries sometimes have no saved path. They cannot
            # supply assets to a new caller, so let the downloader fetch again.
            if existing and not _record_has_media(existing):
                existing = None
            yield existing


def add_history(download_url, note_id, title, save_dir=""):
    item = {
        "下载网址": download_url,
        "笔记ID": note_id,
        "标题": title,
        "下载时间": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if save_dir:
        item["保存位置"] = str(save_dir)
    with _LOCK:
        path = history_path()
        with _cross_process_lock(path.with_suffix(".lock")):
            items = _read_json(path, [])
            if not isinstance(items, list):
                items = []
            _merge_history_item(items, item)
            try:
                _write_json(path, items)
            except OSError:
                # History is an index, not the downloaded asset.  A locked index
                # must not convert a valid local download into a failed task.
                pass
    return path


def update_history_location(download_url, note_id, title, save_dir):
    """Record the final organized folder after an importer moves downloaded files."""
    if not save_dir:
        return False
    item = {
        "下载网址": str(download_url or ""),
        "笔记ID": str(note_id or ""),
        "标题": str(title or ""),
        "保存位置": str(save_dir),
    }
    path = history_path()
    changed = False
    with _LOCK, _cross_process_lock(path.with_suffix(".lock")):
        items = _read_json(path, [])
        if not isinstance(items, list):
            items = []
        matches = [
            index for index, old in enumerate(items)
            if isinstance(old, dict)
            and _record_keys(item).intersection(_record_keys(old))
        ]
        if not matches:
            item["下载时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
            items.append(item)
            changed = True
        else:
            for index in matches:
                merged = dict(items[index])
                for key in ("下载网址", "笔记ID", "标题"):
                    if item[key] and not merged.get(key):
                        merged[key] = item[key]
                if merged.get("保存位置") != item["保存位置"]:
                    merged["保存位置"] = item["保存位置"]
                if merged != items[index]:
                    items[index] = merged
                    changed = True
        if changed:
            _write_json(path, items)
    return changed


def load_settings():
    defaults = {
        "output_dir": str(Path.home() / "Downloads"),
        "mode": "auto",
        "auto_update": True,
        "theme": "neo",
        "image_format": "keep",
    }
    with _LOCK:
        value = _read_json(settings_path(), {})
    if isinstance(value, dict):
        defaults.update(value)
    return _normalize_settings(defaults)


def _normalize_settings(value):
    output_dir = value.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir.strip():
        output_dir = str(Path.home() / "Downloads")
    mode = value.get("mode")
    image_format = value.get("image_format")
    return {
        "output_dir": output_dir,
        "mode": mode if mode in _MODES else "auto",
        "auto_update": value.get("auto_update")
        if isinstance(value.get("auto_update"), bool)
        else True,
        "theme": "glass" if value.get("theme") == "glass" else "neo",
        "image_format": image_format if image_format in _FORMATS else "keep",
    }


def save_settings(value):
    allowed = _normalize_settings(value if isinstance(value, dict) else {})
    with _LOCK:
        _write_json(settings_path(), allowed)
    return allowed
