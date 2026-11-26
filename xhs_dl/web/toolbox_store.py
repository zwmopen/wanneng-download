"""Unified persistent workbench store & Jianghu engine bridge helpers."""

import copy
import csv
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULT_RUNTIME_DIR = Path(r"D:\AICode\运行数据\江湖工具箱\repair-smoke-v4-20261112")
JZH_GAP_KEYWORDS_FILE = Path(r"D:\AICode\工具开发\projects\jianghu-collector-gui\keywords\江浙沪补缺采集关键词.txt")
DEFAULT_TITLE_TEMPLATE = "评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}"
_STORE_LOCK = threading.RLock()


def default_workbench_settings():
    """Return 1:1 defaults matching all Jianghu + xhs-dl workbench panels."""
    downloads_dir = str(Path.home() / "Downloads")
    return {
        "single": {
            "platform": "douyin",
            "show_sift": True,
            "clear_before": True,
            "direct_download": True,
            "date_start_enabled": False,
            "date_start": "",
            "date_end_enabled": False,
            "date_end": "",
            "within_hours_enabled": False,
            "within_hours": 10,
            "duration_sift": False,
            "duration_min": 10,
            "duration_max": 30,
            "tuwen_sift": True,
            "min_images": 1,
            "max_images": 30,
            "only_landscape": False,
            "no_landscape": False,
            "anti_freq_enabled": False,
            "anti_freq_count": 100,
            "anti_freq_sleep": 30,
            "open_wait_enabled": False,
            "open_wait_sec": 30,
        },
        "keyword": {
            "platform": "douyin",
            "clear_before": True,
            "direct_download": True,
            "verify_remind": True,
            "anti_artwork_enabled": True,
            "anti_artwork_count": 10,
            "anti_artwork_sleep": 30,
            "anti_keyword_enabled": True,
            "anti_keyword_count": 1,
            "anti_keyword_sleep": 50,
            "show_sift": True,
            "type_video": False,
            "type_teletex": True,
            "unrecorded_only": False,
            "within_hours_enabled": False,
            "within_hours": 10,
            "max_per_keyword": 20,
            "date_start_enabled": False,
            "date_start": "",
            "date_end_enabled": False,
            "date_end": "",
            "duration_sift": False,
            "duration_min": 10,
            "duration_max": 30,
            "tuwen_sift": True,
            "min_images": 4,
            "max_images": 20,
            "local_life_only": False,
            "no_local_life": False,
            "product_only": False,
            "no_product": False,
            "only_landscape": False,
            "no_landscape": False,
            "vip_only": False,
            "no_vip": False,
            "web_sort": "综合排序",
            "web_publish_time": "不限",
            "media_type": "image",
            "schedule_enabled": False,
            "schedule_interval_min": 30,
        },
        "author": {
            "platform": "douyin",
            "mode": "author_works",
            "clear_before": True,
            "direct_download": False,
            "update_author_info": False,
            "anti_artwork_enabled": True,
            "anti_artwork_count": 10,
            "anti_artwork_sleep": 30,
            "anti_author_enabled": True,
            "anti_author_count": 10,
            "anti_author_sleep": 30,
            "open_home_wait_enabled": False,
            "open_home_wait_sec": 30,
            "show_sift": True,
            "type_video": False,
            "type_teletex": True,
            "unrecorded_only": False,
            "within_hours_enabled": False,
            "within_hours": 10,
            "max_per_author": 10,
            "date_start_enabled": False,
            "date_start": "",
            "date_end_enabled": False,
            "date_end": "",
            "duration_sift": False,
            "duration_min": 10,
            "duration_max": 30,
            "tuwen_sift": True,
            "min_images": 4,
            "max_images": 20,
            "only_landscape": False,
            "no_landscape": False,
            "schedule_enabled": False,
            "schedule_interval_min": 30,
        },
        "download": {
            "down_video": False,
            "down_dynamic_cover": False,
            "down_static_cover": False,
            "down_video_bgm": False,
            "down_audio": False,
            "down_teletex": True,
            "down_teletex_cover": True,
            "down_teletex_bgm": False,
            "teletex_single_dir": True,
            "down_product_img": False,
            "down_product_info": False,
            "title_by_copywriting": True,
            "set_file_time_to_publish": True,
            "check_download_state": False,
            "disk_guard_enabled": True,
            "disk_guard_mb": 500,
            "skip_downloaded_history": True,
            "output_dir": downloads_dir,
            "title_template": DEFAULT_TITLE_TEMPLATE,
            "video_quality": "原画优先",
            "image_format": "jpg",
            "delay_mode": "auto",
            "double_click_play": "local",
            "auto_ingest_material": True,
            "auto_ingest_copy_only": True,
            "write_metadata": True,
            "auto_ingest_config_path": str(Path(__file__).resolve().parents[2] / "config" / "config.json"),
        },
        "software": {
            "theme": "auto",
            "browser_profile": "default",
            "minimize_to_tray": False,
            "app_window_mode": True,
            "auto_start_engine": False,
            "proxy_url": "http://127.0.0.1:7896",
            "auto_topmost_verify_window": True,
            "notify_desktop_toast": True,
            "notify_feishu": True,
            "notify_on_complete": True,
            "notify_feishu_target": "素材采集通知群",
            "notify_feishu_app_id": "",
            "notify_feishu_app_secret": "",
            "notify_feishu_webhook": "",
            "theme_day_start": 7,
            "theme_night_start": 19,
            "theme_auto_style": "rotate",
        },
    }


def resolve_workbench_file():
    configured = os.environ.get("XHS_DL_WORKBENCH_FILE", "").strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".xhs-dl" / "workbench_hub.json"


def resolve_runtime_dir(bridge_dir=None):
    configured = os.environ.get("JIANGHU_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if bridge_dir is not None:
        bridge = Path(bridge_dir)
        if bridge.name.lower() == "bridge" and bridge.parent.name.lower() == "runtime":
            return bridge.parent.parent
    return DEFAULT_RUNTIME_DIR


def _now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_int(value, default=0):
    try:
        if value in (None, "", []):
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _read_json_safe(path, default):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        return data
    except (OSError, ValueError, TypeError):
        return default


def _write_json_atomic(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)


def _merge_settings(defaults, incoming):
    merged = copy.deepcopy(defaults)
    if not isinstance(incoming, dict):
        return merged
    for section, section_defaults in merged.items():
        candidate = incoming.get(section)
        if not isinstance(candidate, dict):
            continue
        for key, default_val in section_defaults.items():
            if key not in candidate:
                continue
            val = candidate[key]
            if isinstance(default_val, bool):
                section_defaults[key] = bool(val)
            elif isinstance(default_val, int):
                section_defaults[key] = _safe_int(val, default_val)
            elif isinstance(default_val, str):
                section_defaults[key] = str(val) if val is not None else default_val
    return merged


def _empty_state():
    return {
        "version": 1,
        "jianghu_synced_at": "",
        "keywords": [],
        "authors": [],
        "artworks": [],
        "keyword_groups": {"douyin": [], "xiaohongshu": []},
        "author_groups": {"douyin": [], "xiaohongshu": []},
        "settings": default_workbench_settings(),
    }


def _normalize_group_map(raw_map):
    out = {"douyin": [], "xiaohongshu": []}
    if not isinstance(raw_map, dict):
        return out
    for plat in ("douyin", "xiaohongshu"):
        seen = set()
        vals = raw_map.get(plat)
        if not isinstance(vals, list):
            continue
        for item in vals:
            name = str(item or "").strip()
            if name and name not in {"all", "全部", "全部分组"} and name not in seen:
                out[plat].append(name)
                seen.add(name)
    return out


def _load_jianghu_keywords_from_dir(runtime_dir):
    rows = []
    seen = set()
    candidates = [
        ("douyin", runtime_dir / "软件数据" / "DY提取作品_直开" / "关键词信息"),
        ("douyin", runtime_dir / "runtime" / "软件数据" / "DY提取作品_直开" / "关键词信息"),
        ("xiaohongshu", runtime_dir / "软件数据" / "XHS提取作品_直开" / "关键词信息"),
        ("xiaohongshu", runtime_dir / "runtime" / "软件数据" / "XHS提取作品_直开" / "关键词信息"),
    ]
    for platform, folder in candidates:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*_HomeInfo.txt")):
            data = _read_json_safe(path, None)
            if not isinstance(data, dict):
                continue
            keyword = str(data.get("关键词") or "").strip()
            if not keyword:
                keyword = path.name.replace("_HomeInfo.txt", "").strip()
            if not keyword:
                continue
            dedupe_key = (platform, keyword.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            rec_ids = data.get("已记录作品id")
            recorded_count = len(rec_ids) if isinstance(rec_ids, list) else _safe_int(data.get("记录提取作品id数量"), 0)
            last_time = str(data.get("上次提取作品时间") or "").replace("T", " ")[:19]
            rows.append({
                "id": f"kw-{hashlib.sha1(f'{platform}:{keyword}'.encode('utf-8')).hexdigest()[:12]}",
                "platform": platform,
                "checked": bool(data.get("是否选择", False)),
                "seq": _safe_int(data.get("序号"), len(rows) + 1),
                "keyword": keyword,
                "last_extracted": "是" if data.get("上次是否提取过作品") else "否",
                "last_count": _safe_int(data.get("上次提取作品数量"), 0),
                "last_time": last_time or "—",
                "recorded_ids": recorded_count,
                "group": str(data.get("分组") or data.get("group") or "默认分组").strip() or "默认分组",
                "remark": str(data.get("备注") or "默认").strip() or "默认",
                "added_at": str(data.get("添加时间") or last_time or _now_str())[:19],
            })
    rows.sort(key=lambda item: (item["seq"], item["keyword"]))
    _resequence(rows)
    return rows


def _decode_json_list_field(raw):
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    if isinstance(raw, str) and raw.strip().startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x) for x in parsed if x]
        except ValueError:
            pass
    return []


def _load_jianghu_artworks_from_dir(runtime_dir):
    rows = []
    seen = set()
    candidates = [
        ("douyin", runtime_dir / "runtime" / "软件数据" / "DY提取作品_直开" / "作品列表数据.txt"),
        ("douyin", runtime_dir / "软件数据" / "DY提取作品_直开" / "作品列表数据.txt"),
        ("xiaohongshu", runtime_dir / "runtime" / "软件数据" / "XHS提取作品_直开" / "作品列表数据.txt"),
        ("xiaohongshu", runtime_dir / "软件数据" / "XHS提取作品_直开" / "作品列表数据.txt"),
    ]
    for platform, data_file in candidates:
        if not data_file.is_file():
            continue
        raw_list = _read_json_safe(data_file, [])
        if not isinstance(raw_list, list):
            continue
        for entry in raw_list:
            obj = entry
            if isinstance(entry, str):
                try:
                    obj = json.loads(entry)
                except ValueError:
                    continue
            if not isinstance(obj, dict):
                continue
            artwork_id = str(obj.get("作品唯一id") or obj.get("作品网址") or uuid.uuid4().hex).strip()
            dedupe_key = (platform, artwork_id)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            images = _decode_json_list_field(obj.get("图文图片下载网址"))
            pub_time = str(obj.get("发布时间") or "").strip()
            if pub_time.startswith("0001-01-01"):
                pub_time = "—"
            rows.append({
                "id": artwork_id,
                "platform": platform,
                "checked": bool(obj.get("是否选择", True)),
                "seq": _safe_int(obj.get("序号"), len(rows) + 1),
                "artwork_type": str(obj.get("作品类型") or "图文").strip(),
                "keyword": str(obj.get("搜索关键词") or "").strip(),
                "author": str(obj.get("作者名称") or "未知作者").strip(),
                "author_fans": _safe_int(obj.get("作者粉丝数量"), 0),
                "title": str(obj.get("作品标题") or "未命名作品").strip(),
                "likes": _safe_int(obj.get("点赞量"), 0),
                "comments": _safe_int(obj.get("评论量"), 0),
                "favorites": _safe_int(obj.get("收藏量"), 0),
                "shares": _safe_int(obj.get("分享量"), 0),
                "image_count": len(images),
                "resolution": str(obj.get("视频分辨率") or "").strip(),
                "url": str(obj.get("作品网址") or "").strip(),
                "cover_url": str(obj.get("封面网址") or "").strip(),
                "image_urls": images,
                "publish_time": pub_time or "—",
                "extract_type": str(obj.get("提取类型") or "关键词").strip(),
                "download_status": str(obj.get("下载状态") or "待下载").strip(),
                "save_path": str(obj.get("保存路径") or "").strip(),
                "remark": str(obj.get("作品备注") or "默认").strip(),
                "source": "jianghu-persisted",
                "session_current": False,
            })
    return rows


def _sync_jianghu_into_state(state, runtime_dir, force=False):
    if os.environ.get("XHS_DL_AUTO_SYNC_JIANGHU", "1") == "0" and not force:
        return False
    changed = False
    if force or not state.get("jianghu_synced_at"):
        existing_kw = {(k.get("platform"), k.get("keyword", "").lower()) for k in state.get("keywords", [])}
        imported_kws = _load_jianghu_keywords_from_dir(runtime_dir)
        for row in imported_kws:
            key = (row["platform"], row["keyword"].lower())
            if key not in existing_kw:
                state["keywords"].append(row)
                existing_kw.add(key)
                changed = True

        existing_art = {(a.get("platform"), str(a.get("id"))) for a in state.get("artworks", [])}
        imported_arts = _load_jianghu_artworks_from_dir(runtime_dir)
        for row in imported_arts:
            key = (row["platform"], str(row["id"]))
            if key not in existing_art:
                state["artworks"].append(row)
                existing_art.add(key)
                changed = True

        if imported_kws or imported_arts or force:
            state["jianghu_synced_at"] = _now_str()
            changed = True
    if changed:
        _resequence(state["keywords"])
        _resequence(state["artworks"])
    return changed


def load_state(bridge_dir=None):
    path = resolve_workbench_file()
    runtime_dir = resolve_runtime_dir(bridge_dir)
    with _STORE_LOCK:
        raw = _read_json_safe(path, None)
        state = _empty_state()
        if isinstance(raw, dict):
            state["jianghu_synced_at"] = str(raw.get("jianghu_synced_at") or "")
            if isinstance(raw.get("keywords"), list):
                state["keywords"] = [copy.deepcopy(x) for x in raw["keywords"] if isinstance(x, dict)]
            if isinstance(raw.get("authors"), list):
                state["authors"] = [copy.deepcopy(x) for x in raw["authors"] if isinstance(x, dict)]
            if isinstance(raw.get("artworks"), list):
                state["artworks"] = [copy.deepcopy(x) for x in raw["artworks"] if isinstance(x, dict)]
            state["keyword_groups"] = _normalize_group_map(raw.get("keyword_groups"))
            state["author_groups"] = _normalize_group_map(raw.get("author_groups"))
            state["settings"] = _merge_settings(state["settings"], raw.get("settings"))
        synced = _sync_jianghu_into_state(state, runtime_dir, force=False)
        need_reseq = False
        for row in state["keywords"]:
            if not str(row.get("group") or "").strip():
                row["group"] = "江浙沪补缺" if row.get("remark") == "江浙沪补缺46词" else "默认分组"
        for row in state["authors"]:
            if not str(row.get("group") or "").strip():
                row["group"] = "默认分组"
        for key in ("keywords", "artworks"):
            rows = state[key]
            if rows and [r.get("seq") for r in rows] != list(range(1, len(rows) + 1)):
                _resequence(rows)
                need_reseq = True
        if synced or need_reseq or raw is None:
            try:
                _write_json_atomic(path, state)
            except OSError:
                pass
        return state


def _save_state(state):
    _write_json_atomic(resolve_workbench_file(), state)


def _normalize_platform(value):
    key = str(value or "").strip().lower()
    if key in {"xiaohongshu", "xhs", "小红书"}:
        return "xiaohongshu"
    if key in {"all", "全部"}:
        return "all"
    return "douyin"


def _summarize_groups(rows, default_name="默认分组", extra_names=None):
    counts = {}
    for raw_name in (extra_names or []):
        clean = str(raw_name or "").strip()
        if clean and clean not in {"all", "全部", "全部分组"}:
            counts.setdefault(clean, 0)
    for row in rows:
        name = str(row.get("group") or default_name).strip() or default_name
        counts[name] = counts.get(name, 0) + 1
    names = sorted(counts.keys(), key=lambda g: (0 if g == default_name else 1, g))
    return [{"name": name, "count": counts[name]} for name in names]


def _explicit_groups_for_platform(state, groups_key, plat):
    gmap = state.get(groups_key) if isinstance(state.get(groups_key), dict) else {}
    plats = ["douyin", "xiaohongshu"] if plat == "all" else [plat]
    names = []
    for p in plats:
        vals = gmap.get(p) or []
        if isinstance(vals, list):
            names.extend(vals)
    return names


def _mutate_group_op(state, rows_key, groups_key, op, payload, target_plat, entity_label):
    gmap = state.setdefault(groups_key, {"douyin": [], "xiaohongshu": []})
    for p in ("douyin", "xiaohongshu"):
        if not isinstance(gmap.get(p), list):
            gmap[p] = []
    plats = ["douyin", "xiaohongshu"] if target_plat == "all" else [target_plat]
    invalid = {"", "all", "全部", "全部分组"}

    if op == "create_group":
        group = str(payload.get("group") or "").strip()
        if group in invalid:
            raise ValueError("请输入有效的分组名称")
        for p in plats:
            if group not in gmap[p]:
                gmap[p].append(group)
        return f"已新建{entity_label}「{group}」"

    if op == "rename_group":
        old_group = str(payload.get("old_group") or "").strip()
        new_group = str(payload.get("new_group") or "").strip()
        if old_group in invalid or new_group in invalid:
            raise ValueError("请提供有效的原分组名称和新分组名称")
        if old_group == new_group:
            raise ValueError("新分组名称不能与原分组相同")
        updated = 0
        for row in state[rows_key]:
            if target_plat != "all" and row.get("platform", "douyin") != target_plat:
                continue
            cur_grp = str(row.get("group") or "默认分组").strip() or "默认分组"
            if cur_grp == old_group:
                row["group"] = new_group
                updated += 1
        found_explicit = False
        for p in plats:
            if old_group in gmap[p]:
                found_explicit = True
                gmap[p] = [g for g in gmap[p] if g != old_group]
                if new_group not in gmap[p]:
                    gmap[p].append(new_group)
        if updated == 0 and not found_explicit:
            raise ValueError(f"未找到分组「{old_group}」")
        return f"已将{entity_label}「{old_group}」重命名为「{new_group}」（共 {updated} 条）"

    if op == "delete_group":
        group = str(payload.get("group") or "").strip()
        if group in invalid:
            raise ValueError("请提供要删除的分组名称")
        delete_items = bool(payload.get("delete_items", False))
        if group == "默认分组" and not delete_items:
            raise ValueError("「默认分组」为基础分组，不能仅解散；如需清空请选择删除组内条目")
        found_explicit = False
        for p in plats:
            if group in gmap[p]:
                found_explicit = True
                gmap[p] = [g for g in gmap[p] if g != group]
        if delete_items:
            kept = []
            removed = 0
            for row in state[rows_key]:
                matches_plat = (target_plat == "all" or row.get("platform", "douyin") == target_plat)
                cur_grp = str(row.get("group") or "默认分组").strip() or "默认分组"
                if matches_plat and cur_grp == group:
                    removed += 1
                else:
                    kept.append(row)
            if removed == 0 and not found_explicit:
                raise ValueError(f"未找到分组「{group}」")
            state[rows_key] = kept
            _resequence(state[rows_key])
            return f"已删除{entity_label}「{group}」及组内 {removed} 条记录"
        moved = 0
        for row in state[rows_key]:
            if target_plat != "all" and row.get("platform", "douyin") != target_plat:
                continue
            cur_grp = str(row.get("group") or "默认分组").strip() or "默认分组"
            if cur_grp == group:
                row["group"] = "默认分组"
                moved += 1
        if moved == 0 and not found_explicit:
            raise ValueError(f"未找到分组「{group}」")
        return f"已删除{entity_label}「{group}」，原组内 {moved} 条记录已移至「默认分组」"

    raise ValueError(f"不支持的分组操作：{op}")


def list_keywords(platform="all", search="", group="all", sort_by="seq", sort_dir="asc", bridge_dir=None):
    state = load_state(bridge_dir)
    plat = _normalize_platform(platform)
    query = str(search or "").strip().lower()
    grp = str(group or "all").strip()
    plat_rows = [
        row for row in state["keywords"]
        if plat == "all" or row.get("platform", "douyin") == plat
    ]
    groups = _summarize_groups(plat_rows, extra_names=_explicit_groups_for_platform(state, "keyword_groups", plat))
    items = []
    for row in plat_rows:
        row_group = str(row.get("group") or "默认分组").strip() or "默认分组"
        if grp not in {"", "all", "全部", "全部分组"} and row_group != grp:
            continue
        if query and (
            query not in str(row.get("keyword", "")).lower()
            and query not in str(row.get("remark", "")).lower()
            and query not in row_group.lower()
        ):
            continue
        item = copy.deepcopy(row)
        item["group"] = row_group
        items.append(item)

    reverse = str(sort_dir).lower() == "desc"
    if sort_by == "keyword":
        items.sort(key=lambda r: str(r.get("keyword", "")).lower(), reverse=reverse)
    elif sort_by == "last_count":
        items.sort(key=lambda r: _safe_int(r.get("last_count"), 0), reverse=reverse)
    elif sort_by == "recorded_ids":
        items.sort(key=lambda r: _safe_int(r.get("recorded_ids"), 0), reverse=reverse)
    elif sort_by == "last_time":
        items.sort(key=lambda r: str(r.get("last_time", "")), reverse=reverse)
    elif sort_by == "group":
        items.sort(key=lambda r: (str(r.get("group") or "默认分组").lower(), _safe_int(r.get("seq"), 0)), reverse=reverse)
    else:
        items.sort(key=lambda r: _safe_int(r.get("seq"), 0), reverse=reverse)

    return {
        "items": items,
        "total": len(state["keywords"]),
        "filtered": len(items),
        "checked_count": sum(1 for row in items if row.get("checked")),
        "groups": groups,
    }


def _resequence(items):
    for idx, row in enumerate(items, start=1):
        row["seq"] = idx


def mark_keyword_collected(keyword, platform="douyin", count=0, bridge_dir=None):
    clean = str(keyword or "").strip()
    if not clean:
        return False
    plat = _normalize_platform(platform)
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        matched = False
        for row in state["keywords"]:
            if row.get("platform", "douyin") == plat and str(row.get("keyword", "")).strip().lower() == clean.lower():
                row["last_extracted"] = "是"
                row["last_count"] = max(_safe_int(count, 0), _safe_int(row.get("last_count"), 0)) if count == 0 else _safe_int(count, 0)
                row["last_time"] = _now_str()
                matched = True
        if matched:
            _save_state(state)
        return matched


def mutate_keywords(op, payload, bridge_dir=None):
    payload = payload if isinstance(payload, dict) else {}
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        items = state["keywords"]
        platform = _normalize_platform(payload.get("platform") or "douyin")
        if platform == "all":
            platform = "douyin"
        message = ""

        if op == "add":
            raw_text = str(payload.get("text") or "")
            raw_list = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
            default_group = str(payload.get("group") or "默认分组").strip() or "默认分组"
            if default_group in {"all", "全部", "全部分组"}:
                default_group = "默认分组"
            parse_group = bool(payload.get("parse_group", False))
            candidates = list(raw_list) + [line.strip() for line in raw_text.replace("\r", "\n").split("\n")]
            existing = {(r.get("platform"), str(r.get("keyword", "")).lower()): r for r in items}
            added = 0
            for entry in candidates:
                raw_item = str(entry).strip()
                if not raw_item:
                    continue
                item_group = default_group
                clean = raw_item
                if parse_group:
                    for sep in ("\t", ",", "，"):
                        if sep in raw_item:
                            left, right = raw_item.split(sep, 1)
                            if left.strip() and right.strip():
                                item_group = left.strip()
                                clean = right.strip()
                            break
                if clean.lower() in {"keyword", "关键词"} and item_group.lower() in {"group", "分组", default_group.lower()}:
                    continue
                key = (platform, clean.lower())
                if key in existing:
                    existing[key]["checked"] = True
                    if item_group != "默认分组":
                        existing[key]["group"] = item_group
                    continue
                row = {
                    "id": f"kw-{uuid.uuid4().hex[:10]}",
                    "platform": platform,
                    "checked": True,
                    "seq": len(items) + 1,
                    "keyword": clean,
                    "group": item_group,
                    "last_extracted": "否",
                    "last_count": 0,
                    "last_time": "—",
                    "recorded_ids": 0,
                    "remark": str(payload.get("remark") or "默认").strip() or "默认",
                    "added_at": _now_str(),
                }
                items.append(row)
                existing[key] = row
                added += 1
            _resequence(items)
            message = f"已添加 {added} 个关键词（重复词已自动勾选并去重）"

        elif op == "toggle":
            row_id = str(payload.get("id") or "")
            for row in items:
                if row.get("id") == row_id:
                    row["checked"] = bool(payload.get("checked", not row.get("checked")))
                    break
            message = "已更新关键词勾选状态"

        elif op == "batch_select":
            mode = str(payload.get("mode") or "all")
            target_plat = _normalize_platform(payload.get("platform") or "all")
            target_group = str(payload.get("group") or "all").strip()
            for row in items:
                if target_plat != "all" and row.get("platform") != target_plat:
                    continue
                row_group = str(row.get("group") or "默认分组").strip() or "默认分组"
                if target_group not in {"", "all", "全部", "全部分组"} and row_group != target_group:
                    continue
                if mode == "all":
                    row["checked"] = True
                elif mode == "none":
                    row["checked"] = False
                elif mode == "invert":
                    row["checked"] = not bool(row.get("checked"))
            message = "已完成批量勾选操作"

        elif op == "update_group":
            group = str(payload.get("group") or "").strip()
            if not group or group in {"all", "全部", "全部分组"}:
                raise ValueError("请提供有效的分组名称")
            ids = set(payload.get("ids") or [])
            updated = 0
            for row in items:
                if (ids and row.get("id") in ids) or (not ids and row.get("checked")):
                    row["group"] = group
                    updated += 1
            message = f"已将 {updated} 条关键词归入分组「{group}」"

        elif op in {"create_group", "rename_group", "delete_group"}:
            target_plat = _normalize_platform(payload.get("platform") or "all")
            message = _mutate_group_op(state, "keywords", "keyword_groups", op, payload, target_plat, "分组")

        elif op == "edit_item":
            row_id = str(payload.get("id") or "").strip()
            target = next((r for r in items if str(r.get("id") or "") == row_id), None)
            if target is None:
                raise ValueError("未找到要编辑的关键词记录")
            new_kw = str(payload.get("keyword") or "").strip()
            if not new_kw:
                raise ValueError("关键词不能为空")
            row_plat = target.get("platform", "douyin")
            conflict = next(
                (r for r in items if r is not target and r.get("platform", "douyin") == row_plat and str(r.get("keyword", "")).strip().lower() == new_kw.lower()),
                None,
            )
            if conflict is not None:
                raise ValueError(f"当前平台已存在关键词「{new_kw}」")
            new_grp = str(payload.get("group") or "默认分组").strip() or "默认分组"
            if new_grp in {"all", "全部", "全部分组"}:
                new_grp = "默认分组"
            new_rm = str(payload.get("remark") if payload.get("remark") is not None else target.get("remark") or "默认").strip() or "默认"
            target["keyword"] = new_kw
            target["group"] = new_grp
            target["remark"] = new_rm
            message = f"已更新关键词「{new_kw}」"

        elif op == "update_remark":
            remark = str(payload.get("remark") or "默认").strip() or "默认"
            group = str(payload.get("group") or "").strip()
            ids = set(payload.get("ids") or [])
            updated = 0
            for row in items:
                if (ids and row.get("id") in ids) or (not ids and row.get("checked")):
                    row["remark"] = remark
                    if group and group not in {"all", "全部", "全部分组"}:
                        row["group"] = group
                    updated += 1
            message = f"已更新 {updated} 条关键词备注"

        elif op == "delete":
            ids = set(payload.get("ids") or [])
            before = len(items)
            if ids:
                state["keywords"] = [row for row in items if row.get("id") not in ids]
            else:
                state["keywords"] = [row for row in items if not row.get("checked")]
            _resequence(state["keywords"])
            message = f"已移除 {before - len(state['keywords'])} 条关键词"

        elif op == "sync_jianghu":
            _sync_jianghu_into_state(state, resolve_runtime_dir(bridge_dir), force=True)
            for row in state["keywords"]:
                if not str(row.get("group") or "").strip():
                    row["group"] = "江浙沪补缺" if row.get("remark") == "江浙沪补缺46词" else "默认分组"
            message = "已同步历史关键词与作品档案"

        elif op == "import_jzh_preset":
            if not JZH_GAP_KEYWORDS_FILE.is_file():
                raise RuntimeError(f"未找到江浙沪补缺词库文件：{JZH_GAP_KEYWORDS_FILE}")
            raw_lines = [
                line.strip()
                for line in JZH_GAP_KEYWORDS_FILE.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            existing = {(r.get("platform"), str(r.get("keyword", "")).lower()): r for r in items}
            added = 0
            for clean in raw_lines:
                key = (platform, clean.lower())
                if key in existing:
                    if not str(existing[key].get("group") or "").strip() or existing[key].get("group") == "默认分组":
                        existing[key]["group"] = "江浙沪补缺"
                    continue
                row = {
                    "id": f"kw-{uuid.uuid4().hex[:10]}",
                    "platform": platform,
                    "checked": False,
                    "seq": len(items) + 1,
                    "keyword": clean,
                    "group": "江浙沪补缺",
                    "last_extracted": "否",
                    "last_count": 0,
                    "last_time": "—",
                    "recorded_ids": 0,
                    "remark": "江浙沪补缺46词",
                    "added_at": _now_str(),
                }
                items.append(row)
                existing[key] = row
                added += 1
            _resequence(items)
            message = f"已导入江浙沪补缺词库：新增 {added} 个，总计 {len(raw_lines)} 个"

        else:
            raise ValueError(f"不支持的关键词操作：{op}")

        _save_state(state)
        result = list_keywords(
            payload.get("filter_platform") or "all",
            payload.get("search") or "",
            group=payload.get("filter_group") or "all",
            sort_by=payload.get("sort_by") or "seq",
            sort_dir=payload.get("sort_dir") or "asc",
            bridge_dir=bridge_dir,
        )
        result["message"] = message
        return result


def list_authors(platform="all", search="", sort_by="seq", sort_dir="asc", group="all", bridge_dir=None):
    state = load_state(bridge_dir)
    plat = _normalize_platform(platform)
    query = str(search or "").strip().lower()
    grp = str(group or "all").strip()
    plat_rows = [
        row for row in state["authors"]
        if plat == "all" or row.get("platform", "douyin") == plat
    ]
    groups = _summarize_groups(plat_rows, extra_names=_explicit_groups_for_platform(state, "author_groups", plat))
    items = []
    for row in plat_rows:
        row_group = str(row.get("group") or "默认分组").strip() or "默认分组"
        if grp not in {"", "all", "全部", "全部分组"} and row_group != grp:
            continue
        haystack = " ".join([
            str(row.get("name", "")),
            str(row.get("url", "")),
            row_group,
            str(row.get("remark", "")),
        ]).lower()
        if query and query not in haystack:
            continue
        item = copy.deepcopy(row)
        item["group"] = row_group
        items.append(item)

    reverse = str(sort_dir).lower() == "desc"
    if sort_by == "name":
        items.sort(key=lambda r: str(r.get("name", "")).lower(), reverse=reverse)
    elif sort_by == "fans":
        items.sort(key=lambda r: _safe_int(r.get("fans"), 0), reverse=reverse)
    elif sort_by == "works":
        items.sort(key=lambda r: _safe_int(r.get("works_count"), 0), reverse=reverse)
    elif sort_by == "publish_time":
        items.sort(key=lambda r: str(r.get("last_publish_at", "")), reverse=reverse)
    elif sort_by == "group":
        items.sort(key=lambda r: (str(r.get("group") or "默认分组").lower(), _safe_int(r.get("seq"), 0)), reverse=reverse)
    else:
        items.sort(key=lambda r: _safe_int(r.get("seq"), 0), reverse=reverse)

    return {
        "items": items,
        "total": len(state["authors"]),
        "filtered": len(items),
        "checked_count": sum(1 for row in items if row.get("checked")),
        "groups": groups,
    }


def _author_name_hint(url):
    cleaned = str(url or "").strip().rstrip("/")
    tail = cleaned.rsplit("/", 1)[-1].split("?")[0]
    return tail[:24] or "主页作者"


def mutate_authors(op, payload, bridge_dir=None):
    payload = payload if isinstance(payload, dict) else {}
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        items = state["authors"]
        platform = _normalize_platform(payload.get("platform") or "douyin")
        if platform == "all":
            platform = "douyin"
        message = ""

        if op == "add":
            raw_text = str(payload.get("text") or "")
            raw_list = payload.get("urls") if isinstance(payload.get("urls"), list) else []
            candidates = list(raw_list) + [line.strip() for line in raw_text.replace("\r", "\n").split("\n")]
            existing = {str(r.get("url", "")).strip(): r for r in items}
            added = 0
            for raw_url in candidates:
                clean = str(raw_url).strip()
                if not clean or "http" not in clean.lower():
                    continue
                if "xiaohongshu.com" in clean.lower() or "xhslink.com" in clean.lower():
                    inferred_platform = "xiaohongshu"
                else:
                    inferred_platform = platform
                if clean in existing:
                    existing[clean]["checked"] = True
                    continue
                row = {
                    "id": f"au-{uuid.uuid4().hex[:10]}",
                    "platform": inferred_platform,
                    "checked": True,
                    "seq": len(items) + 1,
                    "group": str(payload.get("group") or "默认分组").strip() or "默认分组",
                    "name": _author_name_hint(clean),
                    "url": clean,
                    "following": 0,
                    "fans": 0,
                    "likes": 0,
                    "favorites": 0,
                    "works_count": 0,
                    "last_publish_at": "—",
                    "recorded_ids": 0,
                    "local_count": 0,
                    "remark": str(payload.get("remark") or "默认").strip() or "默认",
                    "added_at": _now_str(),
                }
                items.append(row)
                existing[clean] = row
                added += 1
            _resequence(items)
            message = f"已添加 {added} 个主页作者"

        elif op == "toggle":
            row_id = str(payload.get("id") or "")
            for row in items:
                if row.get("id") == row_id:
                    row["checked"] = bool(payload.get("checked", not row.get("checked")))
                    break
            message = "已更新主页作者勾选状态"

        elif op == "batch_select":
            mode = str(payload.get("mode") or "all")
            target_plat = _normalize_platform(payload.get("platform") or "all")
            target_group = str(payload.get("group") or "all").strip()
            for row in items:
                if target_plat != "all" and row.get("platform") != target_plat:
                    continue
                row_group = str(row.get("group") or "默认分组").strip() or "默认分组"
                if target_group not in {"", "all", "全部", "全部分组"} and row_group != target_group:
                    continue
                if mode == "all":
                    row["checked"] = True
                elif mode == "none":
                    row["checked"] = False
                elif mode == "invert":
                    row["checked"] = not bool(row.get("checked"))
            message = "已完成主页作者批量选择"

        elif op == "update_meta":
            group = payload.get("group")
            remark = payload.get("remark")
            ids = set(payload.get("ids") or [])
            updated = 0
            for row in items:
                if (ids and row.get("id") in ids) or (not ids and row.get("checked")):
                    if group is not None and str(group).strip():
                        row["group"] = str(group).strip()
                    if remark is not None and str(remark).strip():
                        row["remark"] = str(remark).strip()
                    updated += 1
            message = f"已修改 {updated} 条主页分组/备注"

        elif op in {"create_group", "rename_group", "delete_group"}:
            target_plat = _normalize_platform(payload.get("platform") or "all")
            message = _mutate_group_op(state, "authors", "author_groups", op, payload, target_plat, "主页分组")

        elif op == "edit_item":
            row_id = str(payload.get("id") or "").strip()
            target = next((r for r in items if str(r.get("id") or "") == row_id), None)
            if target is None:
                raise ValueError("未找到要编辑的主页记录")
            new_name = str(payload.get("name") or "").strip()
            if not new_name:
                raise ValueError("作者名称不能为空")
            new_url = str(payload.get("url") or "").strip()
            if new_url:
                if "http" not in new_url.lower():
                    raise ValueError("主页网址必须包含 http/https")
                target["url"] = new_url
            new_grp = str(payload.get("group") or "默认分组").strip() or "默认分组"
            if new_grp in {"all", "全部", "全部分组"}:
                new_grp = "默认分组"
            new_rm = str(payload.get("remark") if payload.get("remark") is not None else target.get("remark") or "默认").strip() or "默认"
            target["name"] = new_name
            target["group"] = new_grp
            target["remark"] = new_rm
            message = f"已更新主页「{new_name}」"

        elif op == "delete":
            ids = set(payload.get("ids") or [])
            before = len(items)
            if ids:
                state["authors"] = [row for row in items if row.get("id") not in ids]
            else:
                state["authors"] = [row for row in items if not row.get("checked")]
            _resequence(state["authors"])
            message = f"已删除 {before - len(state['authors'])} 条主页"

        else:
            raise ValueError(f"不支持的主页操作：{op}")

        _save_state(state)
        result = list_authors(
            payload.get("filter_platform") or "all",
            payload.get("search") or "",
            payload.get("sort_by") or "seq",
            payload.get("sort_dir") or "asc",
            payload.get("filter_group") or "all",
            bridge_dir,
        )
        result["message"] = message
        return result


def _first_non_empty(mapping, keys, default=None):
    for key in keys:
        val = mapping.get(key)
        if val is not None and val != "":
            return val
    return default


def _format_artwork_publish_times(raw_create_time, collected_dt=None):
    now_dt = collected_dt or datetime.datetime.now()
    raw = str(raw_create_time or "").strip()
    if raw:
        try:
            num = float(raw)
            if num > 1e11:
                num /= 1000.0
            if 946684800 <= num <= 4102444800:
                dt = datetime.datetime.fromtimestamp(num)
                return (
                    int(num),
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%Y-%m-%d_%H.%M.%S"),
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                )
        except (ValueError, OSError, OverflowError):
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d_%H.%M.%S", "%Y-%m-%d"):
            try:
                dt = datetime.datetime.strptime(raw[:19], fmt)
                return (
                    int(dt.timestamp()),
                    dt.strftime("%Y-%m-%d"),
                    dt.strftime("%Y-%m-%d_%H.%M.%S"),
                    dt.strftime("%Y-%m-%d %H:%M:%S"),
                )
            except ValueError:
                continue
    return (
        None,
        now_dt.strftime("%Y-%m-%d"),
        now_dt.strftime("%Y-%m-%d_%H.%M.%S"),
        now_dt.strftime("%Y-%m-%d %H:%M:%S"),
    )


def record_discovered_artworks(items, platform="douyin", source="collection", mark_current=True, bridge_dir=None):
    if not items:
        return 0
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        existing = {(a.get("platform"), str(a.get("id"))): a for a in state["artworks"]}
        if mark_current:
            for row in state["artworks"]:
                row["session_current"] = False
        added_or_updated = 0
        for raw in items:
            if isinstance(raw, str):
                url = raw.strip()
                row_data = {"id": url, "url": url, "title": url, "artwork_type": "图文"}
            elif isinstance(raw, dict):
                row_data = raw
            else:
                continue
            art_id = str(
                row_data.get("artwork_id")
                or row_data.get("id")
                or row_data.get("note_id")
                or row_data.get("url")
                or ""
            ).strip()
            if not art_id:
                continue
            raw_create = _first_non_empty(row_data, ("create_time", "createTime", "publish_time"), "")
            _, _, _, resolved_pub_time = _format_artwork_publish_times(raw_create)
            likes_val = _safe_int(_first_non_empty(row_data, ("likes", "like_count", "digg_count")), None)
            comments_val = _safe_int(_first_non_empty(row_data, ("comments", "comment_count")), None)
            favorites_val = _safe_int(_first_non_empty(row_data, ("favorites", "collect_count")), None)
            shares_val = _safe_int(_first_non_empty(row_data, ("shares", "share_count")), None)
            caption_val = str(_first_non_empty(row_data, ("caption", "text", "title"), "") or "")
            key = (platform, art_id)
            target = existing.get(key)
            if target is None:
                target = {
                    "id": art_id,
                    "platform": platform,
                    "checked": True,
                    "seq": len(state["artworks"]) + 1,
                    "artwork_type": str(row_data.get("artwork_type") or "图文"),
                    "keyword": str(row_data.get("keyword") or row_data.get("search_keyword") or ""),
                    "author": str(row_data.get("author") or row_data.get("author_name") or "未知作者"),
                    "author_uid": str(row_data.get("author_uid") or ""),
                    "author_sec_uid": str(row_data.get("author_sec_uid") or ""),
                    "author_fans": _safe_int(row_data.get("author_fans"), 0),
                    "title": str(row_data.get("title") or art_id),
                    "caption": caption_val[:12000],
                    "likes": likes_val,
                    "comments": comments_val,
                    "favorites": favorites_val,
                    "shares": shares_val,
                    "image_count": _safe_int(row_data.get("image_count"), len(row_data.get("image_urls") or [])),
                    "resolution": str(row_data.get("resolution") or ""),
                    "url": str(row_data.get("url") or ""),
                    "cover_url": str(row_data.get("cover_url") or ""),
                    "image_urls": list(row_data.get("image_urls") or []),
                    "image_sizes": list(row_data.get("image_sizes") or []),
                    "create_time": str(row_data.get("create_time") or row_data.get("createTime") or ""),
                    "publish_time": resolved_pub_time if raw_create else "—",
                    "collected_at": str(row_data.get("collected_at") or _now_str()),
                    "extract_type": str(row_data.get("extract_type") or source),
                    "download_status": str(row_data.get("download_status") or "已读取未下载"),
                    "save_path": str(row_data.get("save_path") or row_data.get("save_dir") or row_data.get("save_directory") or ""),
                    "ingest_status": str(row_data.get("ingest_status") or ""),
                    "ingested_dir": str(row_data.get("ingested_dir") or ""),
                    "ingest_city": str(row_data.get("ingest_city") or ""),
                    "ingest_season": str(row_data.get("ingest_season") or ""),
                    "remark": str(row_data.get("remark") or "默认"),
                    "source": source,
                    "session_current": bool(mark_current),
                }
                state["artworks"].append(target)
                existing[key] = target
            else:
                if mark_current is not None:
                    target["session_current"] = bool(mark_current)
                for field in (
                    "download_status", "save_path", "title", "author",
                    "author_uid", "author_sec_uid", "url", "keyword",
                    "cover_url", "caption", "artwork_type", "ingest_status", "ingested_dir",
                    "ingest_city", "ingest_season",
                ):
                    if row_data.get(field):
                        target[field] = row_data[field]
                if not row_data.get("save_path") and (row_data.get("save_dir") or row_data.get("save_directory")):
                    target["save_path"] = str(row_data.get("save_dir") or row_data.get("save_directory") or "")
                target["collected_at"] = str(row_data.get("collected_at") or _now_str())
                if raw_create:
                    if row_data.get("create_time") or row_data.get("createTime"):
                        target["create_time"] = str(row_data.get("create_time") or row_data.get("createTime") or "")
                    target["publish_time"] = resolved_pub_time
                for stat_key, val in (("likes", likes_val), ("comments", comments_val), ("favorites", favorites_val), ("shares", shares_val)):
                    if val is not None and (val > 0 or target.get(stat_key) is None or platform == "xiaohongshu"):
                        target[stat_key] = val
                if row_data.get("image_urls"):
                    target["image_urls"] = list(row_data.get("image_urls") or [])
                    target["image_count"] = max(_safe_int(target.get("image_count"), 0), _safe_int(row_data.get("image_count"), len(target["image_urls"])))
                if row_data.get("image_sizes"):
                    target["image_sizes"] = list(row_data.get("image_sizes") or [])
            added_or_updated += 1
        _save_state(state)
        return added_or_updated


def _passes_numeric_rule(row, rule):
    if not isinstance(rule, dict) or not rule.get("enabled", True):
        return True
    field = str(rule.get("field") or "")
    op = str(rule.get("op") or ">=")
    threshold = _safe_int(rule.get("value"), 0)
    field_map = {
        "seq": "seq",
        "序号": "seq",
        "author_fans": "author_fans",
        "作者粉丝": "author_fans",
        "likes": "likes",
        "点赞量": "likes",
        "comments": "comments",
        "评论量": "comments",
        "favorites": "favorites",
        "收藏量": "favorites",
        "shares": "shares",
        "分享量": "shares",
        "image_count": "image_count",
        "图片数量": "image_count",
    }
    actual = _safe_int(row.get(field_map.get(field, field)), 0)
    if op == ">=":
        return actual >= threshold
    if op == "<=":
        return actual <= threshold
    if op == "==":
        return actual == threshold
    return True


def list_artworks(
    mode="history",
    search="",
    platform="all",
    artwork_type="all",
    include_kw="",
    exclude_kw="",
    rules=None,
    sort_by="seq",
    sort_dir="asc",
    extra_history=None,
    extra_ai_jobs=None,
    bridge_dir=None,
):
    state = load_state(bridge_dir)
    all_rows = [copy.deepcopy(r) for r in state["artworks"]]
    for row in all_rows:
        st_raw = str(row.get("download_status") or "").strip()
        if st_raw in {"", "已发现", "待下载", "已发现链接"}:
            row["download_status"] = "已读取未下载"
        row["collected_at"] = str(row.get("collected_at") or "")
        if not str(row.get("keyword") or "").strip():
            row["keyword"] = str(row.get("extract_type") or "单作品").strip()

    known_ids = {str(r.get("id") or "") for r in all_rows}
    for hist in (extra_history or []):
        if not isinstance(hist, dict):
            continue
        hid = str(hist.get("note_id") or hist.get("url") or hist.get("job_id") or "")
        if not hid or hid in known_ids:
            continue
        known_ids.add(hid)
        url = str(hist.get("url") or "")
        save_dir = str(hist.get("save_dir") or "")
        completed_at = str(hist.get("completed_at") or "")
        plat = "xiaohongshu" if ("xiaohongshu" in url or "xhslink" in url) else "douyin"
        is_clip = hist.get("source") == "clipboard" or any(
            tok in save_dir for tok in ("02-图文原料", "剪贴板", "staging")
        )
        all_rows.append({
            "id": hid,
            "platform": plat,
            "checked": False,
            "seq": len(all_rows) + 1,
            "artwork_type": "图文",
            "keyword": "剪贴板采集" if is_clip else "单作品下载",
            "author": "—",
            "author_fans": 0,
            "title": str(hist.get("title") or "未命名作品"),
            "likes": 0,
            "comments": 0,
            "favorites": 0,
            "shares": 0,
            "image_count": 0,
            "resolution": "",
            "url": url,
            "cover_url": "",
            "image_urls": [],
            "publish_time": "—",
            "collected_at": completed_at,
            "extract_type": "剪贴板" if is_clip else "单作品",
            "download_status": "已下载",
            "ingest_status": "已入库" if "02-图文原料" in save_dir else "",
            "ingested_dir": save_dir if "02-图文原料" in save_dir else "",
            "save_path": save_dir,
            "remark": "默认",
            "source": "downloader-history",
            "session_current": False,
        })

    for job in (extra_ai_jobs or []):
        if not isinstance(job, dict):
            continue
        jid = str(job.get("job_id") or "").strip()
        if not jid:
            continue
        art_id = f"aijob:{jid}"
        if art_id in known_ids:
            continue
        known_ids.add(art_id)
        st_raw = str(job.get("status") or "").lower()
        if any(tok in st_raw for tok in ("complet", "accept", "ok", "success")):
            status_text = "成功"
        elif any(tok in st_raw for tok in ("err", "fail")):
            status_text = "失败"
        elif job.get("verification_required") or "verify" in st_raw or "login" in st_raw:
            status_text = "等待验证"
        elif "cancel" in st_raw:
            status_text = "已取消"
        else:
            status_text = "进行中"
        kw_val = str(job.get("keyword") or job.get("kind") or "AI 采集").strip()
        title_val = str(job.get("message") or job.get("target_url") or job.get("author_url") or kw_val or jid).strip()
        all_rows.append({
            "id": art_id,
            "platform": _normalize_platform(job.get("platform") or "douyin"),
            "checked": False,
            "seq": len(all_rows) + 1,
            "artwork_type": "AI任务",
            "keyword": kw_val if kw_val.startswith("AI") else f"AI · {kw_val}",
            "author": "CLI / MCP",
            "author_fans": 0,
            "title": title_val,
            "likes": 0,
            "comments": 0,
            "favorites": 0,
            "shares": 0,
            "image_count": 0,
            "resolution": "",
            "url": str(job.get("target_url") or job.get("author_url") or ""),
            "cover_url": "",
            "image_urls": [],
            "publish_time": "—",
            "collected_at": str(job.get("updated_at") or job.get("created_at") or ""),
            "extract_type": "AI任务",
            "download_status": status_text,
            "ingest_status": "",
            "save_path": "",
            "remark": jid,
            "source": "ai-job",
            "session_current": False,
        })

    plat = _normalize_platform(platform)
    query = str(search or "").strip().lower()
    inc_terms = [t.strip().lower() for t in str(include_kw or "").replace("，", ",").split(",") if t.strip()]
    exc_terms = [t.strip().lower() for t in str(exclude_kw or "").replace("，", ",").split(",") if t.strip()]
    current_count = sum(1 for r in all_rows if r.get("session_current"))
    use_current = (mode == "current") and current_count > 0

    filtered = []
    for row in all_rows:
        if use_current and not row.get("session_current"):
            continue
        if plat != "all" and row.get("platform") != plat:
            continue
        if artwork_type not in {"all", "全部"} and row.get("artwork_type") != artwork_type:
            continue
        title_l = str(row.get("title") or "").lower()
        haystack = " ".join([title_l, str(row.get("author") or "").lower(), str(row.get("keyword") or "").lower()])
        if query and query not in haystack:
            continue
        if inc_terms and not any(term in title_l for term in inc_terms):
            continue
        if exc_terms and any(term in title_l for term in exc_terms):
            continue
        if rules and not all(_passes_numeric_rule(row, rule) for rule in rules):
            continue
        filtered.append(row)

    reverse = str(sort_dir).lower() == "desc"
    if sort_by == "collected_at":
        filtered.sort(key=lambda r: (str(r.get("collected_at") or ""), _safe_int(r.get("seq"), 0)), reverse=reverse)
    elif sort_by in {"likes", "comments", "favorites", "shares", "author_fans", "image_count", "seq"}:
        filtered.sort(key=lambda r: _safe_int(r.get(sort_by), 0), reverse=reverse)
    elif sort_by in {"title", "author", "artwork_type", "publish_time"}:
        filtered.sort(key=lambda r: str(r.get(sort_by) or "").lower(), reverse=reverse)

    return {
        "items": filtered[:300],
        "total": len(all_rows),
        "current_count": current_count,
        "history_count": len(all_rows),
        "shown_count": len(filtered),
        "checked_count": sum(1 for row in filtered if row.get("checked")),
    }


def _safe_dir_part(value, default="图文", max_len=48):
    limit = max(0, int(max_len))
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "")).strip(" .")
    if limit == 0:
        return ""
    sliced = cleaned[:limit].strip(" .")
    return sliced or str(default or "图文")[:limit].strip(" .")


def _detect_image_suffix(content):
    if not content or len(content) < 64:
        raise OSError("图片响应为空或过小")
    try:
        from PIL import Image
        with Image.open(io.BytesIO(content)) as img:
            fmt = str(img.format or "").upper()
            img.verify()
        mapping = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif", "BMP": "bmp"}
        if fmt in mapping:
            return mapping[fmt]
    except Exception:
        pass
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    raise OSError("响应不是有效图片")


def _referer_for_media_url(url):
    lowered = str(url or "").lower()
    if "xhscdn" in lowered or "xiaohongshu" in lowered or "xhslink" in lowered:
        return "https://www.xiaohongshu.com/"
    return "https://www.douyin.com/"


def _download_one_image_bytes(url):
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        ),
        "Referer": _referer_for_media_url(url),
    }
    resp = requests.get(str(url), headers=headers, timeout=(15, 45))
    resp.raise_for_status()
    content = resp.content or b""
    suffix = _detect_image_suffix(content)
    return content, suffix


def _download_binary_file(url, dest_path, referer=""):
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        ),
        "Referer": referer or _referer_for_media_url(url),
    }
    resp = requests.get(str(url), headers=headers, stream=True, timeout=(15, 60))
    resp.raise_for_status()
    dest = Path(dest_path)
    tmp = dest.with_suffix(dest.suffix + ".part")
    written = 0
    with tmp.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                fh.write(chunk)
                written += len(chunk)
    if written <= 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _utf16_units(text):
    return len(str(text or "").encode("utf-16-le", errors="replace")) // 2


def _truncate_utf16_units(text, max_units):
    limit = max(0, int(max_units))
    if limit == 0:
        return ""
    out = []
    used = 0
    for ch in str(text or ""):
        u = _utf16_units(ch)
        if used + u > limit:
            break
        out.append(ch)
        used += u
    return "".join(out).strip(" .")


def _convert_artwork_image_bytes(content, detected_suffix, target_format):
    fmt = str(target_format or "keep").strip().lower()
    if fmt not in {"jpg", "png"} or fmt == detected_suffix:
        return content, detected_suffix
    from PIL import Image
    buf = io.BytesIO()
    with Image.open(io.BytesIO(content)) as img:
        if fmt == "jpg":
            if img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info):
                rgba = img.convert("RGBA")
                bg = Image.new("RGB", rgba.size, "white")
                bg.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, "JPEG", quality=95, subsampling=0)
            return buf.getvalue(), "jpg"
        if img.mode == "P" and "transparency" not in img.info:
            img = img.convert("RGB")
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue(), "png"


def _render_artwork_package_dir(row, target_root, *, title_template="", collected_dt=None):
    tmpl = str(title_template or "").strip() or DEFAULT_TITLE_TEMPLATE
    now_dt = collected_dt or datetime.datetime.now()
    raw_create = _first_non_empty(row, ("create_time", "createTime", "publish_time"), "")
    _, publish_date, publish_datetime, _ = _format_artwork_publish_times(raw_create, now_dt)
    art_id = _safe_dir_part(row.get("id") or "work", default="work", max_len=32)
    comments = _safe_int(_first_non_empty(row, ("comments", "comment_count"), 0), 0)
    favorites = _safe_int(_first_non_empty(row, ("favorites", "collect_count"), 0), 0)
    likes = _safe_int(_first_non_empty(row, ("likes", "like_count", "digg_count"), 0), 0)
    shares = _safe_int(_first_non_empty(row, ("shares", "share_count"), 0), 0)
    author = _safe_dir_part(row.get("author") or row.get("author_name") or "", default="未知作者", max_len=24)
    kw_part = _safe_dir_part(row.get("keyword") or "", default="作品列表", max_len=24)
    raw_title = str(row.get("title") or row.get("caption") or "").strip()

    tokens = {
        "comments": str(comments),
        "favorites": str(favorites),
        "likes": str(likes),
        "shares": str(shares),
        "author": author,
        "publish_time": publish_date,
        "publish_datetime": publish_datetime,
        "collect_time": now_dt.strftime("%Y-%m-%d"),
        "id": art_id,
        "keyword": kw_part,
    }

    def _substitute(title_value):
        mapping = dict(tokens, title=title_value)
        rendered = re.sub(
            r"\{([a-zA-Z0-9_]+)\}",
            lambda m: mapping.get(m.group(1), m.group(0)),
            tmpl,
        )
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", rendered).strip(" .")

    resolved_root = Path(target_root).expanduser().resolve()
    parent_units = _utf16_units(str(resolved_root))
    max_folder_units = max(12, 218 - parent_units)
    skeleton_units = _utf16_units(_substitute(""))
    avail_for_title = max(4, min(52, max_folder_units - skeleton_units))
    title_part = _safe_dir_part(raw_title, default="图文", max_len=avail_for_title)
    folder_name = _substitute(title_part)
    if _utf16_units(folder_name) > max_folder_units:
        folder_name = _truncate_utf16_units(folder_name, max_folder_units)
    if not folder_name:
        folder_name = _truncate_utf16_units(art_id or "图文", max_folder_units) or "图文"

    candidate = resolved_root / folder_name
    if candidate.exists():
        existing_meta = candidate / "metadata.json"
        if existing_meta.is_file():
            try:
                meta_obj = json.loads(existing_meta.read_text(encoding="utf-8"))
                existing_id = str(meta_obj.get("id") or meta_obj.get("note_id") or "").strip()
                if existing_id and art_id and existing_id != art_id:
                    suffix = f"-{art_id[-6:]}"
                    base_limit = max(6, max_folder_units - _utf16_units(suffix))
                    candidate = resolved_root / (
                        (_truncate_utf16_units(folder_name, base_limit) or "图文") + suffix
                    )
            except (OSError, ValueError, TypeError):
                pass
    return candidate


def _download_single_artwork_row(row, base_output_dir, download_settings=None):
    dl_cfg = download_settings if isinstance(download_settings, dict) else {}
    effective_format = str(dl_cfg.get("image_format") or "jpg").strip().lower()
    if effective_format not in {"keep", "jpg", "png"}:
        effective_format = "jpg"
    title_template = str(dl_cfg.get("title_template") or DEFAULT_TITLE_TEMPLATE).strip()
    set_mtime = bool(dl_cfg.get("set_file_time_to_publish", True))

    art_id = str(row.get("id") or "work").strip()
    title = str(row.get("title") or "").strip()
    keyword = _safe_dir_part(row.get("keyword") or "作品列表下载", default="作品列表下载", max_len=40)
    urls = [str(u).strip() for u in (row.get("image_urls") or []) if str(u).strip()]
    video_url = str(row.get("video_url") or "").strip()
    live_photo_urls = [str(u).strip() for u in (row.get("live_photo_urls") or []) if str(u).strip()]
    if not urls and not video_url:
        return None, str(row.get("url") or "")
    target_root = Path(base_output_dir).expanduser().resolve()
    if target_root.name not in {"图文作品", "视频作品"}:
        kind_dir = "视频作品" if (not urls and video_url) else "图文作品"
        target_root = target_root / "关键词作品" / keyword / kind_dir

    now_dt = datetime.datetime.now()
    collected_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    raw_create = _first_non_empty(row, ("create_time", "createTime", "publish_time"), "")
    publish_ts, publish_date, _, publish_iso_space = _format_artwork_publish_times(raw_create, now_dt)

    pkg_dir = _render_artwork_package_dir(
        row, target_root, title_template=title_template, collected_dt=now_dt,
    )
    pkg_dir.mkdir(parents=True, exist_ok=True)

    downloaded_map = {}
    errors = []
    if urls:
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(urls)))) as pool:
            futures = {pool.submit(_download_one_image_bytes, u): idx for idx, u in enumerate(urls[:50], 1)}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    downloaded_map[idx] = fut.result()
                except Exception as exc:
                    errors.append(str(exc)[:140])

    saved_files = []
    saved_paths = []
    inner = 0
    saved = 0
    for pos, idx in enumerate(sorted(downloaded_map), 1):
        content, suffix = downloaded_map[idx]
        try:
            content, suffix = _convert_artwork_image_bytes(content, suffix, effective_format)
        except Exception:
            pass
        if pos == 1:
            dst = pkg_dir / f"封面.{suffix}"
        else:
            inner += 1
            dst = pkg_dir / f"内页{inner}.{suffix}"
        tmp = dst.with_suffix(dst.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(dst)
        saved_files.append(dst.name)
        saved_paths.append(dst)
        saved += 1

    live_photo_files = []
    for lp_idx, lp_url in enumerate(live_photo_urls[:50], 1):
        lp_dst = pkg_dir / f"实况{lp_idx}.mp4"
        try:
            if _download_binary_file(lp_url, lp_dst, referer=_referer_for_media_url(lp_url)):
                live_photo_files.append(lp_dst.name)
                saved_paths.append(lp_dst)
        except Exception:
            pass

    video_file = ""
    if not urls and video_url:
        v_dst = pkg_dir / "视频.mp4"
        try:
            if _download_binary_file(video_url, v_dst, referer=_referer_for_media_url(video_url)):
                video_file = v_dst.name
                saved_paths.append(v_dst)
        except Exception as exc:
            errors.append(str(exc)[:140])

    if not saved and not video_file:
        raise RuntimeError(errors[0] if errors else "媒体全部下载失败")

    caption = str(row.get("caption") or row.get("title") or "").strip()
    copy_written = False
    if caption:
        try:
            copy_path = pkg_dir / "文案.txt"
            copy_path.write_text(caption[:12000], encoding="utf-8")
            saved_paths.append(copy_path)
            copy_written = True
        except OSError:
            pass

    likes_val = _safe_int(_first_non_empty(row, ("likes", "like_count", "digg_count"), 0), 0)
    comments_val = _safe_int(_first_non_empty(row, ("comments", "comment_count"), 0), 0)
    favorites_val = _safe_int(_first_non_empty(row, ("favorites", "collect_count"), 0), 0)
    shares_val = _safe_int(_first_non_empty(row, ("shares", "share_count"), 0), 0)
    has_watermark = any(re.search(r"tplv-dy-water|watermark", u, re.I) for u in urls[:50])
    meta_payload = {
        "schema_version": "2.0",
        "platform": str(row.get("platform") or "douyin"),
        "id": art_id,
        "note_id": art_id,
        "url": str(row.get("url") or ""),
        "keyword": str(row.get("keyword") or ""),
        "title": title,
        "caption": caption,
        "author": str(row.get("author") or row.get("author_name") or ""),
        "author_uid": str(row.get("author_uid") or ""),
        "author_sec_uid": str(row.get("author_sec_uid") or ""),
        "likes_count": likes_val,
        "comments_count": comments_val,
        "favorites_count": favorites_val,
        "shares_count": shares_val,
        "publish_timestamp": publish_ts,
        "publish_time": publish_iso_space,
        "publish_date": publish_date,
        "collected_at": collected_at,
        "downloaded_at": collected_at,
        "images_count": saved,
        "images_list": saved_files,
        "image_urls": urls[:50],
        "image_sizes": list(row.get("image_sizes") or []),
        "image_format": effective_format,
        "watermark_free": not has_watermark,
        "live_photo_files": live_photo_files,
        "video_file": video_file,
        "copy_file": "文案.txt" if copy_written else "",
        "save_dir": str(pkg_dir),
        "folder_name": pkg_dir.name,
        "engine": "artwork-direct-download",
    }
    if bool(dl_cfg.get("write_metadata", True)):
        try:
            meta_path = pkg_dir / "metadata.json"
            meta_tmp = pkg_dir / ".metadata.json.tmp"
            meta_tmp.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            meta_tmp.replace(meta_path)
            saved_paths.append(meta_path)
        except OSError:
            pass
    if set_mtime and publish_ts:
        for path in saved_paths:
            try:
                os.utime(path, (publish_ts, publish_ts))
            except OSError:
                pass
        try:
            os.utime(pkg_dir, (publish_ts, publish_ts))
        except OSError:
            pass
    return {"save_path": str(pkg_dir), "image_count": saved, "video_file": video_file, "live_photo_count": len(live_photo_files)}, ""


def _load_material_ingestor():
    import sys
    project_root = str(Path(__file__).resolve().parents[2])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    import material_ingestor
    return material_ingestor


def ingest_downloaded_packages(
    package_dirs,
    download_settings=None,
    *,
    source_label="万能采集器",
    platform_hint="",
):
    dl_cfg = download_settings if isinstance(download_settings, dict) else {}
    cfg_raw = str(
        dl_cfg.get("auto_ingest_config_path")
        or os.environ.get("MATERIAL_HUB_CONFIG")
        or (Path(__file__).resolve().parents[2] / "config" / "config.json")
    ).strip()
    cfg_path = Path(cfg_raw).expanduser() if cfg_raw else None
    copy_only = bool(dl_cfg.get("auto_ingest_copy_only", True))
    ingestor = _load_material_ingestor()

    results = []
    by_source = {}
    ok_count = 0
    filtered_count = 0
    failed_count = 0
    seen = set()
    for raw_dir in (package_dirs or []):
        raw_str = str(raw_dir or "").strip()
        if not raw_str:
            continue
        src_path = Path(raw_str).expanduser()
        if not src_path.is_dir():
            continue
        key = str(src_path.resolve())
        if key in seen:
            continue
        seen.add(key)
        try:
            res = ingestor.ingest_work_package(
                src_path,
                config_path=(str(cfg_path) if cfg_path and cfg_path.is_file() else None),
                source_label=source_label,
                platform_hint=platform_hint,
                copy_only=copy_only,
                dry_run=False,
                write_metadata=bool(dl_cfg.get("write_metadata", True)),
            )
        except Exception as exc:
            res = {
                "status": "error",
                "success": False,
                "outcome": "ingest_exception",
                "source_dir": key,
                "message": f"自动入库异常：{exc}",
            }
        results.append(res)
        by_source[key] = res
        if res.get("success") is True:
            ok_count += 1
        elif res.get("status") == "filtered":
            filtered_count += 1
        else:
            failed_count += 1

    parts = []
    if ok_count:
        parts.append(f"入库 {ok_count} 套")
    if filtered_count:
        parts.append(f"广告/规则过滤 {filtered_count} 套")
    if failed_count:
        parts.append(f"异常 {failed_count} 套")
    return {
        "attempted": len(results),
        "ingested": ok_count,
        "filtered": filtered_count,
        "failed": failed_count,
        "copy_only": copy_only,
        "config_path": str(cfg_path) if cfg_path else "",
        "results": results,
        "by_source": by_source,
        "summary": "、".join(parts) if parts else "未执行入库",
    }


def _apply_ingest_info_to_row(row, ingest_res, *, copy_only=True):
    if not isinstance(ingest_res, dict):
        return
    if ingest_res.get("success") is True:
        city = str(ingest_res.get("city") or ingest_res.get("category") or "").strip()
        seasons = ingest_res.get("seasons") or []
        months = ingest_res.get("months") or []
        is_unclassified = bool(ingest_res.get("is_unclassified"))
        project_route = str((ingest_res.get("metadata") or {}).get("project_route") or "").strip()
        target_dir = str(ingest_res.get("target_dir") or "").strip()
        if project_route == "doubao_pullnew" or city == "豆包拉新":
            status_label = "已入库·豆包拉新"
        elif is_unclassified:
            status_label = "已入库·00待识别"
        elif len(months) >= 12:
            status_label = "已入库·全12月"
        elif months:
            status_label = "已入库·" + "/".join(months[:3]) + ("…" if len(months) > 3 else "")
        else:
            status_label = f"已入库·{city}" if city else "已入库"
        row["ingest_status"] = status_label
        row["ingest_city"] = city
        row["ingest_season"] = "|".join(seasons) if isinstance(seasons, list) else str(seasons or "")
        if target_dir:
            row["ingested_dir"] = target_dir
            if not copy_only:
                row["save_path"] = target_dir
    elif ingest_res.get("status") == "filtered":
        row["ingest_status"] = "广告拦截" if ingest_res.get("outcome") == "filtered_ad" else "超图过滤"
    else:
        row["ingest_status"] = "入库失败"


def _has_existing_media_dir(path_str):
    raw = str(path_str or "").strip()
    if not raw:
        return False
    target = Path(raw).expanduser()
    if not target.is_dir():
        return False
    media_exts = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".avif", ".mp4", ".mov", ".webm"}
    try:
        return any(f.is_file() and f.suffix.lower() in media_exts and f.stat().st_size > 200 for f in target.iterdir())
    except OSError:
        return False


def record_queued_artwork_downloads(results, bridge_dir=None):
    """Attach successful queue downloads to their existing workbench rows."""
    from xhs_dl.core.platforms import detect_platform

    downloaded = {}
    platforms = {"xhs": "xiaohongshu", "douyin": "douyin"}
    for item in results:
        if not item.success or not item.note_id:
            continue
        platform = platforms.get(detect_platform(item.url))
        if platform and _has_existing_media_dir(item.save_dir):
            downloaded[(platform, str(item.note_id))] = item
    if not downloaded:
        return 0

    updated = 0
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        for row in state["artworks"]:
            item = downloaded.get((row.get("platform"), str(row.get("id"))))
            if item is None:
                continue
            count = _safe_int(item.image_success, 0)
            row["save_path"] = item.save_dir
            row["download_status"] = f"已下载 {count} 张图" if count else "已下载"
            row["image_count"] = max(_safe_int(row.get("image_count"), 0), count)
            updated += 1
        if updated:
            _save_state(state)
    return updated


def collect_downloaded_artwork_ids(bridge_dir=None):
    """Collect already-downloaded artwork IDs from both workbench_hub.json and central history.json."""
    ids = set()
    id_re = re.compile(r"/(?:note|video)/(\d{8,})|/explore/([a-fA-F0-9]{12,})")
    try:
        state = load_state(bridge_dir)
        for row in state.get("artworks") or []:
            if not isinstance(row, dict):
                continue
            status = str(row.get("download_status") or "")
            sp = str(row.get("save_path") or "").strip()
            id_dir = str(row.get("ingested_dir") or "").strip()
            if ("已下载" in status or sp or id_dir):
                rid = str(row.get("id") or "").strip()
                if rid:
                    ids.add(rid)
    except Exception:
        pass
    try:
        from xhs_dl.storage import history_path
        hp = history_path()
        if hp.is_file():
            entries = _read_json_safe(hp, [])
            if isinstance(entries, list):
                for item in entries:
                    if not isinstance(item, dict):
                        continue
                    nid = str(item.get("笔记ID") or item.get("note_id") or "").strip()
                    if nid:
                        ids.add(nid)
                    url = str(item.get("下载网址") or item.get("url") or "").strip()
                    m = id_re.search(url)
                    if m:
                        ids.add(m.group(1) or m.group(2))
    except Exception:
        pass
    return ids


def mutate_artworks(op, payload, bridge_dir=None):
    payload = payload if isinstance(payload, dict) else {}
    if op == "download":
        with _STORE_LOCK:
            state = load_state(bridge_dir)
            ids = [str(x) for x in (payload.get("ids") or []) if str(x).strip()]
            id_set = set(ids)
            targets = [
                copy.deepcopy(r) for r in state["artworks"]
                if (id_set and str(r.get("id")) in id_set) or (not id_set and r.get("checked"))
            ]
            dl_cfg = copy.deepcopy((state.get("settings") or {}).get("download") or {})
            if payload.get("image_format"):
                dl_cfg["image_format"] = str(payload.get("image_format"))
            if payload.get("title_template"):
                dl_cfg["title_template"] = str(payload.get("title_template"))
            if "auto_ingest_material" in payload:
                dl_cfg["auto_ingest_material"] = bool(payload.get("auto_ingest_material"))
            if "auto_ingest_copy_only" in payload:
                dl_cfg["auto_ingest_copy_only"] = bool(payload.get("auto_ingest_copy_only"))
            if payload.get("auto_ingest_config_path"):
                dl_cfg["auto_ingest_config_path"] = str(payload.get("auto_ingest_config_path"))
            skip_dup = bool(dl_cfg.get("skip_downloaded_history", True)) and not bool(payload.get("force_redownload"))
            base_output = str(
                payload.get("output_dir")
                or dl_cfg.get("output_dir")
                or (resolve_runtime_dir(bridge_dir) / "downloads")
            )
        if not targets:
            raise ValueError("请先在列表中勾选至少一条作品")

        ok_works = 0
        ok_images = 0
        skipped_dups = 0
        saved_dirs = []
        fallback_urls = []
        failed = []
        updates = {}
        try:
            from xhs_dl.storage import find_downloaded
        except Exception:
            find_downloaded = None
        for row in targets:
            rid = str(row.get("id") or "")
            if skip_dup:
                existing_ok = (
                    _has_existing_media_dir(row.get("ingested_dir"))
                    or _has_existing_media_dir(row.get("save_path"))
                )
                if not existing_ok and callable(find_downloaded):
                    hist = find_downloaded(download_url=row.get("url") or "", note_id=rid)
                    if hist and _has_existing_media_dir(hist.get("保存位置") or hist.get("save_dir")):
                        existing_ok = True
                if existing_ok:
                    skipped_dups += 1
                    continue
            try:
                info, fb_url = _download_single_artwork_row(row, base_output, download_settings=dl_cfg)
                if info:
                    ok_works += 1
                    ok_images += info["image_count"]
                    saved_dirs.append(info["save_path"])
                    updates[rid] = info
                    try:
                        from xhs_dl.storage import add_history
                        add_history(row.get("url") or "", rid, row.get("title") or "图文作品", info["save_path"])
                    except Exception:
                        pass
                elif fb_url:
                    fallback_urls.append(fb_url)
            except Exception as exc:
                failed.append({"id": rid, "title": row.get("title", ""), "error": str(exc)[:180]})

        ingest_summary = None
        if saved_dirs and bool(dl_cfg.get("auto_ingest_material", False)) and not payload.get("skip_ingest"):
            ingest_summary = ingest_downloaded_packages(
                saved_dirs,
                dl_cfg,
                source_label="作品列表下载",
            )

        with _STORE_LOCK:
            state = load_state(bridge_dir)
            for row in state["artworks"]:
                rid = str(row.get("id") or "")
                if rid in updates:
                    info = updates[rid]
                    row["download_status"] = f"已下载 {info['image_count']} 张图"
                    row["save_path"] = info["save_path"]
                    row["image_count"] = max(_safe_int(row.get("image_count"), 0), info["image_count"])
                    if ingest_summary:
                        src_key = str(Path(info["save_path"]).expanduser().resolve())
                        _apply_ingest_info_to_row(
                            row,
                            ingest_summary.get("by_source", {}).get(src_key),
                            copy_only=bool(dl_cfg.get("auto_ingest_copy_only", True)),
                        )
            _save_state(state)
            res = list_artworks(mode=payload.get("mode") or "history", bridge_dir=bridge_dir)

        msg_parts = []
        if ok_works:
            msg_parts.append(f"已直连下载 {ok_works} 套作品（共 {ok_images} 张图片）")
        if skipped_dups:
            msg_parts.append(f"已去重跳过 {skipped_dups} 条已下载作品")
        if ingest_summary and ingest_summary.get("attempted"):
            msg_parts.append(f"自动入库：{ingest_summary['summary']}")
        if fallback_urls:
            msg_parts.append(f"{len(fallback_urls)} 条无缓存直链已交由统一下载队列")
        if failed and not ok_works:
            msg_parts.append(f"下载失败：{failed[0].get('error', '未知错误')}")
        res["message"] = "；".join(msg_parts) or "没有可下载的作品"
        res["downloaded_works"] = ok_works
        res["downloaded_images"] = ok_images
        res["skipped_duplicates"] = skipped_dups
        res["saved_dirs"] = saved_dirs
        res["fallback_urls"] = fallback_urls
        res["failed"] = failed
        if ingest_summary:
            res["ingest"] = ingest_summary
        return res

    if op == "ingest":
        with _STORE_LOCK:
            state = load_state(bridge_dir)
            ids = [str(x) for x in (payload.get("ids") or []) if str(x).strip()]
            id_set = set(ids)
            dl_cfg = copy.deepcopy((state.get("settings") or {}).get("download") or {})
            if "auto_ingest_copy_only" in payload:
                dl_cfg["auto_ingest_copy_only"] = bool(payload.get("auto_ingest_copy_only"))
            if payload.get("auto_ingest_config_path"):
                dl_cfg["auto_ingest_config_path"] = str(payload.get("auto_ingest_config_path"))
            targets = [
                copy.deepcopy(r) for r in state["artworks"]
                if ((id_set and str(r.get("id")) in id_set) or (not id_set and r.get("checked")))
                and str(r.get("save_path") or "").strip()
                and Path(str(r.get("save_path"))).expanduser().is_dir()
            ]
        if not targets:
            raise ValueError("请先勾选至少一条「已下载落盘」的作品进行入库")
        ingest_summary = ingest_downloaded_packages(
            [t["save_path"] for t in targets],
            dl_cfg,
            source_label="手工触发入库",
        )
        with _STORE_LOCK:
            state = load_state(bridge_dir)
            for row in state["artworks"]:
                sp = str(row.get("save_path") or "").strip()
                if not sp:
                    continue
                src_key = str(Path(sp).expanduser().resolve())
                if src_key in ingest_summary.get("by_source", {}):
                    _apply_ingest_info_to_row(
                        row,
                        ingest_summary["by_source"][src_key],
                        copy_only=bool(dl_cfg.get("auto_ingest_copy_only", True)),
                    )
            _save_state(state)
            res = list_artworks(mode=payload.get("mode") or "history", bridge_dir=bridge_dir)
        res["ingest"] = ingest_summary
        res["message"] = f"本地规则入库完成：{ingest_summary['summary']}"
        return res

    with _STORE_LOCK:
        state = load_state(bridge_dir)
        items = state["artworks"]
        message = ""

        if op == "toggle":
            row_id = str(payload.get("id") or "")
            for row in items:
                if str(row.get("id")) == row_id:
                    row["checked"] = bool(payload.get("checked", not row.get("checked")))
                    break
            message = "已更新作品勾选状态"

        elif op == "batch_select":
            mode = str(payload.get("mode") or "all")
            for row in items:
                if mode == "all":
                    row["checked"] = True
                elif mode == "none":
                    row["checked"] = False
                elif mode == "invert":
                    row["checked"] = not bool(row.get("checked"))
            message = "已完成作品批量勾选"

        elif op == "delete":
            ids = set(str(x) for x in (payload.get("ids") or []))
            before = len(items)
            if ids:
                state["artworks"] = [r for r in items if str(r.get("id")) not in ids]
            else:
                state["artworks"] = [r for r in items if not r.get("checked")]
            _resequence(state["artworks"])
            message = f"已移除 {before - len(state['artworks'])} 条作品记录"

        elif op == "export_csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["序号", "平台", "类型", "标题", "作者", "来源/关键词", "图片数", "评论", "收藏", "点赞", "发布时间", "读取时间", "状态", "入库状态", "网址", "保存路径"])
            for r in items:
                writer.writerow([
                    r.get("seq", ""), r.get("platform", ""), r.get("artwork_type", ""),
                    r.get("title", ""), r.get("author", ""), r.get("keyword") or r.get("extract_type") or "",
                    r.get("image_count", 0), r.get("comments", 0), r.get("favorites", 0), r.get("likes", 0),
                    r.get("publish_time", ""), r.get("collected_at", ""),
                    r.get("download_status", ""), r.get("ingest_status", ""), r.get("url", ""), r.get("save_path", ""),
                ])
            return {"csv": buf.getvalue(), "count": len(items)}

        elif op == "sync_jianghu":
            _sync_jianghu_into_state(state, resolve_runtime_dir(bridge_dir), force=True)
            message = "已刷新江湖作品库缓存"

        else:
            raise ValueError(f"不支持的作品操作：{op}")

        _save_state(state)
        res = list_artworks(mode=payload.get("mode") or "history", bridge_dir=bridge_dir)
        res["message"] = message
        return res


def get_settings(bridge_dir=None):
    return copy.deepcopy(load_state(bridge_dir)["settings"])


def update_settings(patch, bridge_dir=None):
    if not isinstance(patch, dict):
        raise ValueError("设置参数必须是 JSON 对象")
    with _STORE_LOCK:
        state = load_state(bridge_dir)
        merged = copy.deepcopy(state["settings"])
        defaults = default_workbench_settings()
        for key, value in patch.items():
            if key in merged and isinstance(value, dict):
                merged[key] = _merge_settings({key: defaults[key]}, {key: {**merged[key], **value}})[key]
        state["settings"] = merged
        _save_state(state)
        return copy.deepcopy(merged)


def read_ai_jobs(bridge_dir, limit=40):
    bridge = Path(bridge_dir)
    jobs_dir = bridge / "jobs"
    items = []
    if jobs_dir.is_dir():
        files = sorted(
            (p for p in jobs_dir.glob("*.json") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[: max(1, min(limit, 80))]
        for path in files:
            data = _read_json_safe(path, None)
            if isinstance(data, dict):
                data.setdefault("job_id", path.stem)
                items.append(data)

    status = _read_json_safe(bridge / "bridge_status.json", {})
    progress = _read_json_safe(bridge / "keyword_progress.json", {})
    browser = _read_json_safe(bridge / "browser_status.json", {})
    return {
        "jobs": items,
        "bridge_status": status if isinstance(status, dict) else {},
        "keyword_progress": progress if isinstance(progress, dict) else {},
        "browser_status": browser if isinstance(browser, dict) else {},
    }


def _open_local_folder(path_str):
    target = Path(str(path_str or "").strip() or str(Path.home() / "Downloads")).expanduser()
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        target = target.parent
    subprocess.Popen(["explorer.exe", str(target)])
    return {"status": "ok", "message": f"已打开目录：{target}"}


def _iter_native_host_windows():
    """Yield (user32, wintypes, hwnd, title) for Jianghu native host windows."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    fallback_tokens = ("浏览器", "DY提取作品", "XHS提取作品")
    proc_tokens = ("dy提取作品", "xhs提取作品")
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum_cb(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = ""
        if pid.value:
            handle = kernel32.OpenProcess(0x1000, False, pid.value)
            if handle:
                try:
                    img_buf = ctypes.create_unicode_buffer(512)
                    size = wintypes.DWORD(512)
                    if kernel32.QueryFullProcessImageNameW(handle, 0, img_buf, ctypes.byref(size)):
                        proc_name = Path(img_buf.value).name.lower()
                finally:
                    kernel32.CloseHandle(handle)
        if proc_name:
            if any(pt in proc_name for pt in proc_tokens):
                found.append((hwnd, title))
        elif any(ft in title for ft in fallback_tokens):
            found.append((hwnd, title))
        return True

    user32.EnumWindows(_enum_cb, 0)
    return found


def _bring_native_browser_to_front(topmost=True):
    """Restore, center onscreen if offscreen, and raise Jianghu verification browser windows."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        user32 = ctypes.windll.user32
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int

        insert_after = wintypes.HWND(-1 if topmost else -2)
        sw = max(800, int(user32.GetSystemMetrics(0) or 1920))
        sh = max(600, int(user32.GetSystemMetrics(1) or 1080))
        focused = 0
        for hwnd, title in _iter_native_host_windows():
            if "浏览器" not in title:
                continue
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            rect = _RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            resize_needed = w < 300 or h < 200
            if resize_needed:
                w = min(1280, max(960, sw - 120))
                h = min(820, max(680, sh - 120))
            offscreen = (
                rect.left < -100
                or rect.top < -100
                or rect.left >= sw - 80
                or rect.top >= sh - 80
            )
            flags = 0x0040  # SWP_SHOWWINDOW
            if resize_needed:
                x = max(40, (sw - w) // 2) if offscreen else rect.left
                y = max(40, (sh - h) // 2) if offscreen else rect.top
            elif offscreen:
                x = max(40, (sw - w) // 2)
                y = max(40, (sh - h) // 2)
                flags |= 0x0001  # SWP_NOSIZE
            else:
                x, y = 0, 0
                flags |= 0x0001 | 0x0002  # SWP_NOSIZE | SWP_NOMOVE
            user32.SetWindowPos(hwnd, insert_after, x, y, w, h, flags)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            focused += 1
        return focused
    except Exception:
        return 0


def focus_and_bring_verify_browser(
    bridge_dir,
    toolbox_project,
    python_exe,
    *,
    topmost=True,
    open_login=False,
    platform="douyin",
):
    """Send native CLI focus/login-open command, then restore, center, and pin verification browser topmost."""
    cli = Path(toolbox_project) / "jianghu_cli.py"
    plat = str(platform or "douyin").strip().lower()
    if plat not in {"douyin", "xiaohongshu", "bilibili"}:
        plat = "douyin"

    def _run_cli(args):
        if not cli.is_file():
            return
        try:
            subprocess.run(
                [str(python_exe), str(cli), "--bridge-dir", str(bridge_dir), "--timeout", "15", *args],
                cwd=str(toolbox_project),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    if open_login:
        _run_cli(["open-platform-login", "--platform", plat])
    else:
        _run_cli(["focus"])

    focused = _bring_native_browser_to_front(topmost=bool(topmost))
    if focused == 0 and cli.is_file():
        if not open_login:
            _run_cli(["open-platform-login", "--platform", plat])
        attempts = 8 if not open_login else 6
        for idx in range(attempts):
            time.sleep(0.5)
            focused = _bring_native_browser_to_front(topmost=bool(topmost))
            if focused > 0:
                break
            if idx == 3 and not open_login:
                _run_cli(["focus"])
    return focused


def _hide_legacy_native_host_window():
    """Move legacy DY/XHS WinForms main shell windows offscreen without SW_HIDE (so WinForms WebView clicks still work)."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        hidden = 0
        for hwnd, title in _iter_native_host_windows():
            if "浏览器" in title:
                continue
            user32.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE
            user32.SetWindowPos(hwnd, 0, -3200, -3200, 0, 0, 0x0001 | 0x0004 | 0x0010)
            hidden += 1
        return hidden
    except Exception:
        return 0


_NATIVE_RESUME_CALLBACK = None


def set_native_resume_callback(fn):
    global _NATIVE_RESUME_CALLBACK
    _NATIVE_RESUME_CALLBACK = fn


def _use_native_engine():
    return os.environ.get("XHS_DL_LEGACY_JIANGHU_ENGINE", "0") != "1"


def _pick_local_folder(initial_dir=""):
    if os.name != "nt":
        return {"status": "unsupported", "path": "", "message": "仅支持 Windows 系统文件夹选择弹窗"}
    target = str(initial_dir or "").strip()
    if target:
        try:
            target = str(Path(target).expanduser())
        except Exception:
            target = ""
    safe_init = target.replace("'", "''")
    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dlg = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dlg.Description = '选择作品保存根目录'; "
        "$dlg.ShowNewFolderButton = $true; "
        + (f"if (Test-Path -LiteralPath '{safe_init}') {{ $dlg.SelectedPath = '{safe_init}' }}; " if safe_init else "")
        + "if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dlg.SelectedPath }"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-STA", "-WindowStyle", "Hidden", "-Command", ps_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    chosen = (proc.stdout or "").strip().splitlines()[-1].strip() if (proc.stdout or "").strip() else ""
    if chosen:
        return {"status": "ok", "path": chosen, "message": f"已选择保存目录：{chosen}"}
    return {"status": "cancelled", "path": "", "message": "已取消目录选择"}


def _open_local_file(path_str=""):
    raw = str(path_str or "").strip()
    if not raw:
        raise ValueError("请先填写配置文件路径")
    target = Path(raw).expanduser()
    if not target.exists():
        example = Path(__file__).resolve().parents[2] / "config.example.json"
        if target.name.lower() == "config.json" and example.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            raise FileNotFoundError(f"配置文件不存在：{target}")
    if os.name == "nt":
        os.startfile(str(target))
    return {"status": "ok", "path": str(target), "message": f"已打开配置文件：{target}"}


def run_engine_action(action, params, bridge_dir, toolbox_project, python_exe):
    params = params if isinstance(params, dict) else {}
    if action == "open_folder":
        return _open_local_folder(params.get("path"))
    if action == "pick_folder":
        return _pick_local_folder(params.get("initial_dir"))
    if action == "open_file":
        return _open_local_file(params.get("path"))
    if action == "test_notification":
        from xhs_dl.web import notifier
        res = notifier.dispatch_workbench_notification(
            "test",
            "✅ 万能采集器通知通道测试",
            "电脑桌面弹窗与飞书采集通知群已打通；后续遇到人机验证会自动弹窗并置顶浏览器窗口、同步提醒。",
            settings=get_settings(bridge_dir=bridge_dir),
            force=True,
        )
        desktop_ok = bool((res.get("desktop") or {}).get("sent"))
        feishu_ok = bool((res.get("feishu") or {}).get("sent"))
        feishu_err = (res.get("feishu") or {}).get("error") or ""
        return {
            "status": "ok" if (desktop_ok or feishu_ok) else "error",
            "result": res,
            "message": (
                f"桌面弹窗：{'已发送' if desktop_ok else '失败'} · "
                f"飞书通知：{'已发送' if feishu_ok else ('未送达 ' + feishu_err)}"
            ),
        }
    if _use_native_engine() and not params.get("_legacy_cli"):
        from xhs_dl.web import native_collector
        eng = native_collector.get_engine()
        settings = get_settings(bridge_dir=bridge_dir) or {}
        dl_cfg = settings.get("download") or {}
        sw_cfg = settings.get("software") or {}
        proxy_url = str(sw_cfg.get("proxy_url") or "")
        if action == "hide_legacy_host":
            return {"status": "ok", "windows_hidden": 0, "message": "已切换至内置 Edge 引擎，无需隐藏旧版外壳"}
        if action in {"start_engine", "switch_platform"}:
            return eng.start_engine(platform=params.get("platform") or "douyin", proxy_url=proxy_url)
        if action == "open_platform_login":
            return eng.open_platform_login(platform=params.get("platform") or "douyin", proxy_url=proxy_url)
        if action in {"bring_verify_browser", "focus_engine"}:
            cnt = eng.bring_verify_browser(
                platform=params.get("platform") or "douyin",
                topmost=bool(params.get("topmost", True)),
                open_login=bool(params.get("open_login")),
                proxy_url=proxy_url,
            )
            return {
                "status": "ok",
                "windows_focused": cnt,
                "message": "已在屏幕中央弹出并置顶内置 Edge 浏览器窗口",
            }
        if action == "hide_browser":
            return eng.hide_browser()
        if action == "stop_keyword":
            return eng.stop_collection()
        if action == "list_profiles":
            return {"status": "ok", "profiles": eng.list_profiles()}
        if action == "create_profile":
            return eng.create_profile(params.get("name") or "")
        if action == "switch_profile":
            res = eng.switch_profile(params.get("name") or "default")
            try:
                update_settings({"software": {"browser_profile": res.get("active_profile") or "default"}}, bridge_dir=bridge_dir)
            except Exception:
                pass
            return res
        if action == "delete_profile":
            res = eng.delete_profile(params.get("name") or "")
            try:
                update_settings({"software": {"browser_profile": res.get("active_profile") or "default"}}, bridge_dir=bridge_dir)
            except Exception:
                pass
            return res
        if action == "browser_status":
            cap = eng.get_capabilities()
            return {"status": "ready" if cap.get("browser_ready") else "idle", "capabilities": cap}
        if action == "resume_keyword":
            paused = eng.consume_paused_job()
            if not paused:
                raise ValueError("当前没有等待恢复的验证任务，请直接点击开始采集")
            if callable(_NATIVE_RESUME_CALLBACK):
                resumed = _NATIVE_RESUME_CALLBACK(paused)
                return {
                    "status": "resuming",
                    "job_id": (resumed or {}).get("job_id") or "",
                    "message": "已继续采集任务，正在基于当前已验证会话继续抓取…",
                }
            return {"status": "ok", "paused": paused, "message": "验证标记已清除，请点开始采集继续"}
        if action == "extract_single":
            url = str(params.get("url") or "").strip()
            if not url:
                raise ValueError("请提供有效作品链接")
            from xhs_dl.core.unified_downloader import UnifiedDownloader
            base_out = str(params.get("output_dir") or dl_cfg.get("output_dir") or str(Path.home() / "Downloads"))
            dl = UnifiedDownloader(
                output_dir=base_out,
                image_format=str(dl_cfg.get("image_format") or "jpg"),
            )
            res_items = dl.download_urls([url])
            first = res_items[0] if res_items else None
            if first and getattr(first, "success", False):
                title = getattr(first, "title", "") or "单作品"
                save_dir = getattr(first, "save_dir", "") or ""
                return {"status": "ok", "success": True, "title": title, "save_dir": save_dir, "message": f"已完成下载：{title}"}
            err_msg = (getattr(first, "error", "") if first else "") or "单作品下载未成功"
            return {"status": "error", "success": False, "message": err_msg}
        if action == "apply_filter":
            return {"status": "ok", "message": "筛选参数已实时应用"}
        if action == "download_native_artworks":
            return mutate_artworks("download", {"output_dir": dl_cfg.get("output_dir")}, bridge_dir=bridge_dir)
    if action == "hide_legacy_host":
        count = _hide_legacy_native_host_window()
        return {"status": "ok", "windows_hidden": count, "message": f"已隐藏 {count} 个旧版原生外壳窗口"}

    project = Path(toolbox_project)
    bridge = Path(bridge_dir)
    bridge.mkdir(parents=True, exist_ok=True)

    if action == "start_engine":
        platform = _normalize_platform(params.get("platform") or "douyin")
        if platform == "all":
            platform = "douyin"
        status_file = bridge / "bridge_status.json"
        try:
            if status_file.is_file() and (time.time() - status_file.stat().st_mtime) <= 5:
                st = _read_json_safe(status_file, {})
                if isinstance(st, dict) and st.get("running") is True and st.get("active_platform") == platform:
                    _hide_legacy_native_host_window()
                    return {"status": "ok", "platform": platform, "message": f"{platform} 底层引擎已在线，无需重复启动"}
        except OSError:
            pass
        progress_file = bridge / "keyword_progress.json"
        if progress_file.is_file():
            try:
                old_prog = _read_json_safe(progress_file, {})
                if isinstance(old_prog, dict) and (
                    old_prog.get("status") in {"verification_required", "running"}
                    or old_prog.get("phase") == "verification"
                ):
                    progress_file.unlink(missing_ok=True)
            except OSError:
                pass
        cmd_script = project / "start_native_module.cmd"
        if not cmd_script.is_file():
            raise RuntimeError(f"未找到底层引擎启动脚本：{cmd_script}")
        subprocess.Popen(
            ["cmd.exe", "/c", str(cmd_script), platform],
            cwd=str(project),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        def _auto_hide_shell():
            for delay in (3, 3, 4):
                time.sleep(delay)
                _hide_legacy_native_host_window()

        threading.Thread(target=_auto_hide_shell, daemon=True).start()
        return {"status": "starting", "platform": platform, "message": f"正在后台静默拉起 {platform} 底层引擎与登录态…"}

    cli = project / "jianghu_cli.py"
    if not cli.is_file():
        raise RuntimeError(f"未找到底层 CLI：{cli}")

    if action == "bring_verify_browser":
        count = focus_and_bring_verify_browser(
            bridge,
            project,
            python_exe,
            topmost=bool(params.get("topmost", True)),
            open_login=bool(params.get("open_login")),
            platform=params.get("platform") or "douyin",
        )
        return {
            "status": "ok",
            "windows_focused": count,
            "message": (
                "已弹出并置顶平台验证浏览器窗口，请完成验证后点击“继续采集”"
                if count
                else "已向底层发送唤醒指令；若未看到验证窗口，请确认引擎已在当前桌面启动"
            ),
        }

    if action == "resume_keyword":
        job_id = str(params.get("job_id") or "").strip()
        if not job_id:
            jobs_dir = bridge / "jobs"
            if jobs_dir.is_dir():
                for path in sorted(
                    (p for p in jobs_dir.glob("*.json") if p.is_file()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                ):
                    data = _read_json_safe(path, None)
                    if isinstance(data, dict) and (
                        data.get("status") == "verification_required" or data.get("verification_required") is True
                    ):
                        job_id = str(data.get("job_id") or path.stem).strip()
                        if job_id:
                            break
        if not job_id:
            raise ValueError("未找到待恢复的人机验证采集任务")
        resume_cmd = [
            str(python_exe),
            str(cli),
            "--bridge-dir",
            str(bridge),
            "--timeout",
            "600",
            "resume-keyword",
            "--job-id",
            job_id,
            "--wait-seconds",
            "420",
        ]
        subprocess.Popen(
            resume_cmd,
            cwd=str(project),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return {
            "status": "resuming",
            "job_id": job_id,
            "message": f"已恢复采集任务 {job_id}，前端将实时同步采集进度…",
        }

    cli_timeout = 35
    run_timeout = 40
    if action == "extract_single":
        wait_sec = max(0, min(_safe_int(params.get("wait_seconds"), 45), 180))
        cli_timeout = max(35, wait_sec + 15)
        run_timeout = max(60, wait_sec + 25)

    cmd = [str(python_exe), str(cli), "--bridge-dir", str(bridge), "--timeout", str(cli_timeout)]
    if action == "open_platform_login":
        plat = str(params.get("platform") or "douyin").strip().lower()
        if plat not in {"douyin", "xiaohongshu", "bilibili"}:
            plat = "douyin"
        cmd.extend(["open-platform-login", "--platform", plat])
    elif action == "switch_platform":
        plat = _normalize_platform(params.get("platform") or "douyin")
        cmd.extend(["switch-platform", "--platform", "xiaohongshu" if plat == "xiaohongshu" else "douyin"])
    elif action == "hide_browser":
        cmd.append("hide-browser")
    elif action == "focus_engine":
        cmd.append("focus")
    elif action == "stop_keyword":
        cmd.append("stop-keyword")
    elif action == "browser_status":
        cmd.append("browser-status")
    elif action == "extract_single":
        url = str(params.get("url") or "").strip()
        if not url:
            raise ValueError("请提供有效作品链接")
        plat = "xiaohongshu" if _normalize_platform(params.get("platform") or "douyin") == "xiaohongshu" else "douyin"
        min_img = max(0, _safe_int(params.get("min_images"), 0))
        max_img = max(min_img, _safe_int(params.get("max_images"), 50))
        direct_down = bool(params.get("direct_download", True))
        wait_sec = max(0, min(_safe_int(params.get("wait_seconds"), 45), 180))
        cmd.extend([
            "extract-single",
            "--platform", plat,
            "--url", url,
            "--min-images", str(min_img),
            "--max-images", str(max_img),
            "--wait-seconds", str(wait_sec),
        ])
        if not direct_down:
            cmd.append("--metadata-only")
    elif action == "download_native_artworks":
        cmd.append("download-artworks")
        if params.get("all", True):
            cmd.append("--all")
    elif action == "apply_filter":
        cmd.extend([
            "set-filter",
            "--min-images", str(_safe_int(params.get("min_images"), 4)),
            "--max-images", str(_safe_int(params.get("max_images"), 20)),
        ])
        if params.get("allow_video"):
            cmd.append("--allow-video")
        if params.get("disabled"):
            cmd.append("--disabled")
    else:
        raise ValueError(f"不支持的引擎动作：{action}")

    proc = subprocess.run(
        cmd,
        cwd=str(project),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=run_timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    out = (proc.stdout or proc.stderr or "").strip()
    for line in reversed(out.splitlines()):
        text = line.strip()
        if text.startswith("{"):
            try:
                return json.loads(text)
            except ValueError:
                pass
    if proc.returncode != 0:
        raise RuntimeError(out or f"命令执行失败（退出码 {proc.returncode}）")
    return {"status": "ok", "message": out or "操作已完成"}
