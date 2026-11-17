"""Pure path resolver for the clipboard collector preflight.

The resolver only parses environment/config values and returns paths.  It never
creates directories, copies data, deletes old state, or starts a service.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Mapping

DEFAULT_RUNTIME_ROOT = Path(r"D:\江湖有旅人\04-经营运营\本地运行数据\剪贴板采集器")
DEFAULT_MATERIAL_ROOT = Path(r"D:\江湖有旅人\03-生产车间\01-原料库\02-图文原料\团建图文")
DEFAULT_UNCLASSIFIED_ROOT = Path(r"D:\江湖有旅人\03-生产车间\01-原料库\00-待识别")
DEFAULT_PAUSE_FILE = Path(r"D:\AICode\运行数据\应用状态\后台服务控制\clipboard-collector.paused")
DEFAULT_DOUBAO_ROOT = Path(r"D:\AICode\项目推进\projects\豆包拉新\素材库\参考爆款")
DEFAULT_DOUBAO_LINKS = Path(r"D:\AICode\项目推进\projects\豆包拉新\对标灵感链接.md")


@dataclass(frozen=True)
class CollectorPaths:
    code_root: Path
    data_dir: Path
    history_file: Path
    queue_file: Path
    heartbeat_file: Path
    mode_file: Path
    failure_streak_file: Path
    daemon_log_file: Path
    pause_file: Path
    temp_download_dir: Path
    bridge_staging_dir: Path
    bridge_jobs_file: Path
    legacy_data_dir: Path
    legacy_bridge_staging_dir: Path
    legacy_bridge_jobs_file: Path
    material_root_dir: Path
    unclassified_dir: Path
    doubao_material_dir: Path
    doubao_link_file: Path


def load_json_config(path: str | Path | None) -> dict[str, Any]:
    """Load a config for path resolution only; malformed/missing config is empty."""
    if not path:
        return {}
    try:
        value = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _value(env_name: str, storage: Mapping[str, Any], key: str, default: Any = None) -> Any:
    env_value = os.environ.get(env_name, "").strip()
    if env_value:
        return env_value
    value = storage.get(key)
    return value if value not in (None, "") else default


def _as_path(value: Any, base: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(os.path.expandvars(os.path.expanduser(str(value))))
    return (base / path).resolve() if not path.is_absolute() else path


def resolve_paths(
    config: Mapping[str, Any] | None = None,
    *,
    code_root: str | Path,
    config_dir: str | Path | None = None,
) -> CollectorPaths:
    """Resolve active and legacy paths without touching the filesystem.

    Explicit env/config paths win.  Without explicit values, the existing
    xhs-dl state and bridge locations remain the compatibility defaults.  A
    later cutover must preserve/read back those legacy files before switching.
    """
    cfg = config if isinstance(config, Mapping) else {}
    storage = cfg.get("storage", {}) if isinstance(cfg.get("storage", {}), Mapping) else {}
    routing = cfg.get("project_routing", {}) if isinstance(cfg.get("project_routing", {}), Mapping) else {}
    doubao = routing.get("doubao_pullnew", {}) if isinstance(routing.get("doubao_pullnew", {}), Mapping) else {}
    code = Path(code_root).expanduser().resolve()
    base = Path(config_dir).expanduser().resolve() if config_dir else code
    legacy_data = code
    legacy_bridge = code / "bridge_staging"
    legacy_jobs = code / "collector_bridge_jobs.json"

    configured_data = _as_path(_value("MATERIAL_HUB_DATA_DIR", storage, "data_dir"), base)
    data_dir = configured_data or (legacy_data if (legacy_data / "clipboard_history.json").exists() else DEFAULT_RUNTIME_ROOT / "state")
    configured_bridge = _as_path(_value("MATERIAL_HUB_BRIDGE_DIR", storage, "bridge_staging_dir"), base)
    bridge_dir = configured_bridge or (legacy_bridge if legacy_bridge.exists() else DEFAULT_RUNTIME_ROOT / "bridge_staging")
    configured_jobs = _as_path(_value("MATERIAL_HUB_BRIDGE_JOBS_FILE", storage, "bridge_jobs_file"), base)
    jobs_file = configured_jobs or (legacy_jobs if legacy_jobs.exists() else DEFAULT_RUNTIME_ROOT / "collector_bridge_jobs.json")

    configured_temp = _value("MATERIAL_HUB_TEMP_DOWNLOAD_DIR", storage, "temp_download_dir")
    temp_dir = _as_path(configured_temp, base) or DEFAULT_RUNTIME_ROOT / "download_staging"
    configured_material = _value("MATERIAL_HUB_MATERIAL_ROOT_DIR", storage, "material_root_dir")
    material_root = _as_path(configured_material, base) or DEFAULT_MATERIAL_ROOT
    configured_unclassified = _value("MATERIAL_HUB_UNCLASSIFIED_DIR", storage, "unclassified_downloads_dir")
    unclassified = _as_path(configured_unclassified, base) or DEFAULT_UNCLASSIFIED_ROOT
    configured_pause = os.environ.get("COLLECTOR_PAUSE_FILE", "").strip() or storage.get("pause_file")
    pause_file = _as_path(configured_pause, base) or DEFAULT_PAUSE_FILE
    doubao_material = _as_path(doubao.get("material_dir"), base) or DEFAULT_DOUBAO_ROOT
    doubao_links = _as_path(doubao.get("link_md_file"), base) or DEFAULT_DOUBAO_LINKS

    return CollectorPaths(
        code_root=code,
        data_dir=data_dir,
        history_file=data_dir / "clipboard_history.json",
        queue_file=data_dir / "clipboard_pending_queue.json",
        heartbeat_file=data_dir / "collector_heartbeat.json",
        mode_file=data_dir / "collector_mode.json",
        failure_streak_file=data_dir / "collector_failure_streak.json",
        daemon_log_file=data_dir / "collector_daemon.log",
        pause_file=pause_file,
        temp_download_dir=temp_dir,
        bridge_staging_dir=bridge_dir,
        bridge_jobs_file=jobs_file,
        legacy_data_dir=legacy_data,
        legacy_bridge_staging_dir=legacy_bridge,
        legacy_bridge_jobs_file=legacy_jobs,
        material_root_dir=material_root,
        unclassified_dir=unclassified,
        doubao_material_dir=doubao_material,
        doubao_link_file=doubao_links,
    )
