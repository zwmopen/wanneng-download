# -*- coding: utf-8 -*-
"""
小红书剪贴板极速无感自动采集入库守护程序 (Clipboard XHS Auto Collector) - V3.7.0
核心特性：
1. 0 内存抢占与 0 剪贴板污染：仅在剪贴板含有 xhslink.cn / xiaohongshu.com 时无感触发，其余内容 100% 穿透放行；
2. 待下载持久化队列 (Pending Queue)：连续复制多个链接时自动进队列暂存，绝不并发爆破小红书；
3. 智能风控与拟人冷却 (Risk Control & Cooldown)：
   - 正常采集后拟人间隔 (8~15秒随机抖动)，保护 IP 与网络；
   - 单篇受限(300031/404/0目录)秒级跳过，严禁触发全局冻结队头阻塞；
4. 本地万能下载器 V2 核心直解：无水印原画组图 + 完整文案，0 Cookie、0 依赖浏览器；
5. 智能地名分流：自动识别精准流量城市目录（宁波/金华义乌/安吉/台州等），自动建立秋季四季硬链接；
6. 元数据标定：自动写入 metadata.json（打上"剪切板下载"、"万能下载器下载"等标签）；
7. 桌面原生轻量通知：屏幕右下角弹出拟态系统通知卡片，绝不打扰飞书；
8. 单实例进程互斥：Win32 Global Mutex 防多开防冲突；
9. [v3.7.0] 长链 xsec_token 跨行截断根治：多行口令预处理拼接 + 宽松 token 正则，彻底修复 token=C 残缺失败问题。
"""

import os
import sys
import time
import re
import json
import shutil
import random
import threading
import subprocess
import traceback
import importlib.util
from pathlib import Path
import ctypes
from ctypes import wintypes

# ==================== 动态配置与解耦加载器 (MaterialHub Config Loader) ====================
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent

# 优先在自包含 lib 目录下寻找 xhs_dl
LIB_DIR = SCRIPT_DIR / "lib"
if (LIB_DIR / "xhs_dl").exists():
    sys.path.insert(0, str(LIB_DIR))

# 自动探测配置文件
CONFIG_FILE = None
for candidate in [
    os.environ.get("MATERIAL_HUB_CONFIG"),
    SKILL_ROOT / "config" / "config.json",
    SCRIPT_DIR / "config" / "config.json",
    SCRIPT_DIR / "config.json"
]:
    if candidate and Path(candidate).exists():
        CONFIG_FILE = Path(candidate)
        break

# 自愈配置：若无 config.json 则自动从 config.example.json 释放默认便携配置
if not CONFIG_FILE:
    for example_cand in [
        SKILL_ROOT / "config" / "config.example.json",
        SCRIPT_DIR / "config" / "config.example.json",
        SCRIPT_DIR / "config.example.json"
    ]:
        if example_cand and Path(example_cand).exists():
            target_cfg = example_cand.parent / "config.json"
            try:
                shutil.copy2(str(example_cand), str(target_cfg))
                CONFIG_FILE = target_cfg
                break
            except Exception:
                pass

LOADED_CONFIG = {}
if CONFIG_FILE and CONFIG_FILE.exists():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f_cfg:
            LOADED_CONFIG = json.load(f_cfg)
    except Exception:
        pass

storage_cfg = LOADED_CONFIG.get("storage", {})
bm_cfg = LOADED_CONFIG.get("benchmark", {})
rc_cfg = LOADED_CONFIG.get("risk_control", {})
notify_cfg = LOADED_CONFIG.get("notification", {})
feishu_cfg = notify_cfg.get("feishu", {})
rules_cfg = LOADED_CONFIG.get("classification_rules", {})
filter_cfg = LOADED_CONFIG.get("filter_rules", {})
MAX_IMAGE_ALLOWED = int(filter_cfg.get("max_images_allowed", 15))

# 运行时数据与日志目录 (自适应解耦：优先 config -> 宿主历史兼容路径 -> 本地 data 目录)
configured_data_dir = storage_cfg.get("data_dir")
if configured_data_dir:
    DATA_DIR = Path(configured_data_dir)
elif Path(r"D:\AICode\工具开发\projects\xhs-dl").exists() and (Path(r"D:\AICode\工具开发\projects\xhs-dl") / "clipboard_history.json").exists():
    DATA_DIR = Path(r"D:\AICode\工具开发\projects\xhs-dl")
else:
    DATA_DIR = SKILL_ROOT / "data"

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = Path.home() / ".material_hub"
    DATA_DIR.mkdir(parents=True, exist_ok=True)

PROJECT_ROOT = DATA_DIR
_workspace_root = next((p for p in SKILL_ROOT.parents if (p / 'routes.json').is_file()), None)
PAUSE_FILE = Path(os.environ.get('COLLECTOR_PAUSE_FILE') or
                  ((_workspace_root / '运行数据' / '应用状态' / '后台服务控制' / 'clipboard-collector.paused')
                   if _workspace_root else (DATA_DIR / 'clipboard-collector.paused')))

def collection_paused():
    """Fail closed; startup paths and both producer/consumer honor user intent."""
    try:
        PAUSE_FILE.stat()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True

import logging
from logging.handlers import RotatingFileHandler

DAEMON_LOG_FILE = DATA_DIR / "collector_daemon.log"
HISTORY_FILE = DATA_DIR / "clipboard_history.json"
QUEUE_FILE = DATA_DIR / "clipboard_pending_queue.json"
HEARTBEAT_FILE = DATA_DIR / "collector_heartbeat.json"
MODE_FILE = DATA_DIR / "collector_mode.json"

def get_current_collector_mode() -> dict:
    """获取当前采集模式 (auto: 自动智能分类 | manual: 手动指定文件夹模式)"""
    if MODE_FILE.exists():
        try:
            with open(MODE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "mode" in data:
                    return data
        except Exception:
            pass
    return {"mode": "auto", "target_folder": "", "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

def set_collector_mode(mode: str, target_folder: str = "", reason: str = "") -> dict:
    """热更新当前采集模式并落盘 (无需重启后台守护进程，下一篇采集即时生效)"""
    data = {
        "mode": mode,
        "target_folder": target_folder,
        "reason": reason,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = MODE_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(MODE_FILE)
        log_daemon(f"⚙️ 采集模式已切换: mode={mode}, target_folder={target_folder}, reason={reason}")
    except Exception as ex:
        if sys.stdout:
            print(f"[Set Collector Mode Error]: {ex}")
    return data

# 配置 5MB 轮转日志 (最多保留 3 份归档，彻底根治日志无限膨胀，磁盘占用上限 15MB)
_daemon_logger = logging.getLogger("MaterialHubCollector")
_daemon_logger.setLevel(logging.INFO)
if not _daemon_logger.handlers:
    try:
        _rfh = RotatingFileHandler(
            str(DAEMON_LOG_FILE),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        _rfh.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        _daemon_logger.addHandler(_rfh)
    except Exception:
        pass

def log_daemon(msg: str):
    try:
        _daemon_logger.info(msg)
    except Exception:
        pass

def update_heartbeat(status: str = "idle", queue_len: int = 0, history_len: int = 0, extra: str = ""):
    """写入心跳文件，防止进程假死挂起并供外部体检与看门狗随时掌握活跃状态"""
    try:
        current_mode_info = get_current_collector_mode()
        hb = {
            "pid": os.getpid(),
            "status": status,
            "mode": current_mode_info.get("mode", "auto"),
            "target_folder": current_mode_info.get("target_folder", ""),
            "last_heartbeat": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "queue_len": queue_len,
            "history_len": history_len,
            "extra": extra,
            "version": "3.8.3"
        }
        tmp = HEARTBEAT_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(hb, f, ensure_ascii=False, indent=2)
        tmp.replace(HEARTBEAT_FILE)
    except Exception:
        pass

# 如果由 pythonw.exe 无窗口静默拉起，重定向输出至日志或空设备
if sys.stdout is None:
    try:
        sys.stdout = open(DAEMON_LOG_FILE, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    try:
        sys.stderr = open(DAEMON_LOG_FILE, "a", encoding="utf-8", buffering=1)
    except Exception:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

if hasattr(sys.stdout, "reconfigure") and sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:
        pass

# 基础存储路径自适应 (优先读取 config.json，若配置相对路径则基于 SKILL_ROOT；缺省时智能适配)
def _resolve_dir(cfg_path: str, default_name: str) -> Path:
    if cfg_path:
        p = Path(cfg_path)
        if not p.is_absolute():
            p = (SKILL_ROOT / p).resolve()
        return p
    native_cand = Path(r"D:\AICode\项目推进\projects\江湖有旅人\主项目\01-素材库")
    if native_cand.exists():
        return native_cand if not default_name else (native_cand / default_name)
    fallback_cand = Path.home() / "Downloads" / "MaterialHub" / "素材库"
    return fallback_cand if not default_name else (fallback_cand / default_name)

BASE_MATERIAL_DIR = _resolve_dir(storage_cfg.get("material_root_dir"), "")
PRECISION_DIR = _resolve_dir(storage_cfg.get("precision_dir"), "精准流量") if storage_cfg.get("precision_dir") else (BASE_MATERIAL_DIR / "精准流量")
PAN_TRAFFIC_DIR = _resolve_dir(storage_cfg.get("pan_traffic_dir"), "泛流量") if storage_cfg.get("pan_traffic_dir") else (BASE_MATERIAL_DIR / "泛流量")
SPRING_DIR = BASE_MATERIAL_DIR / "春季（3—5月·智能分类）"
SUMMER_DIR = BASE_MATERIAL_DIR / "夏季（6—8月·智能分类）"
AUTUMN_DIR = _resolve_dir(storage_cfg.get("autumn_dir"), "秋季（9—11月·智能分类）") if storage_cfg.get("autumn_dir") else (BASE_MATERIAL_DIR / "秋季（9—11月·智能分类）")
WINTER_DIR = BASE_MATERIAL_DIR / "冬季（12—2月·智能分类）"
ALL_SEASON_DIR = _resolve_dir(storage_cfg.get("all_season_dir"), "四季通用（全年·无季节限制）") if storage_cfg.get("all_season_dir") else (BASE_MATERIAL_DIR / "四季通用（全年·无季节限制）")

temp_cfg = storage_cfg.get("temp_download_dir")
if temp_cfg:
    p = Path(temp_cfg)
    TEMP_DOWNLOAD_DIR = (SKILL_ROOT / p).resolve() if not p.is_absolute() else p
elif Path(r"D:\AICode\运行数据\临时文件\xhs_clipboard_staging").parent.exists():
    TEMP_DOWNLOAD_DIR = Path(r"D:\AICode\运行数据\临时文件\xhs_clipboard_staging")
else:
    TEMP_DOWNLOAD_DIR = DATA_DIR / "temp_staging"

C_DOWNLOADS_DIR = Path(storage_cfg.get("unclassified_downloads_dir", str(Path.home() / "Downloads")))

# 对标账号清单
SECOND_BRAIN_BENCHMARK_FILE = Path(bm_cfg.get("second_brain_benchmark_file", r"D:\SecondBrain\zwm-second-brain\03-项目\01-团建项目—江湖有旅人\对标账号与样板观察清单.md"))
PROJECT_BENCHMARK_FILE = Path(bm_cfg.get("project_benchmark_file", r"D:\AICode\项目推进\projects\江湖有旅人\主项目\05-知识库\06-数据与复盘\复盘文件\素材库归档文档\对标账号完整清单.md"))
BENCHMARK_FILE = PROJECT_BENCHMARK_FILE if PROJECT_BENCHMARK_FILE.exists() else SECOND_BRAIN_BENCHMARK_FILE

# 风控与冷却配置
NORMAL_COOLDOWN_RANGE = tuple(rc_cfg.get("normal_cooldown_range", [15.0, 28.0]))
DEEP_COOLDOWN_BASE = rc_cfg.get("deep_cooldown_base_seconds", 60)
MAX_RETRIES = rc_cfg.get("max_retries", 4)

# 引入万能下载器 CLI
try:
    from xhs_dl.cli import main as xhs_dl_main
except Exception as e:
    if sys.stdout:
        print(f"Warning: Failed to import xhs_dl.cli directly: {e}")

# 引入本地桌面通知模块
NOTIFY_PY = None
_notify_candidates = [
    SKILL_ROOT.parent / "shared-notification" / "scripts" / "shared_notify.py",
    Path(r"D:\AICode\.agents\skills\shared-notification\scripts\shared_notify.py"),
    Path(r"D:\AICode\AI\skills\技能包\技能\shared-notification\scripts\shared_notify.py"),
]
for candidate in _notify_candidates:
    if candidate.exists():
        NOTIFY_PY = candidate
        break

if not NOTIFY_PY and SKILL_ROOT.parent.exists():
    for root, dirs, files in os.walk(str(SKILL_ROOT.parent)):
        if "shared_notify.py" in files:
            NOTIFY_PY = Path(root) / "shared_notify.py"
            break

def send_desktop_notification(msg: str, title: str = "素材采集中枢", status: str = "success", action_target: str = ""):
    if not notify_cfg.get("enable_desktop_toast", True):
        return False
    
    # 1. 优先尝试本地 shared-notification 技能卡片弹窗 (拟态悬浮卡片)
    if NOTIFY_PY and NOTIFY_PY.exists():
        try:
            spec = importlib.util.spec_from_file_location("shared_notify", str(NOTIFY_PY))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            res = mod.notify(
                msg,
                title=title,
                status=status,
                app_name="万能素材采集中枢",
                position="BottomRight",
                duration_ms=8000,
                icon_key="download",
                action_target=action_target,
                action_label="点击打开素材目录" if action_target else "点击查看",
                wait=False
            )
            if res:
                return True
        except Exception as ex:
            if sys.stdout:
                print(f"[Notify Skill Error]: {ex}")
                
    # 2. Windows 原生 Toast 弹窗硬核保底 (使用 WinRT DOM + PowerShell 官方 AUMID，100% 成功弹出)
    try:
        clean_msg = msg.replace('"', ' ').replace("'", " ")[:120]
        clean_title = title.replace('"', ' ').replace("'", " ")[:40]
        ps_cmd = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
            f"$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
            f"$xml = [xml]$template.GetXml(); "
            f"$nodes = $xml.GetElementsByTagName('text'); "
            f"$nodes[0].InnerText = '{clean_title}'; "
            f"$nodes[1].InnerText = '{clean_msg}'; "
            f"$doc = [Windows.Data.Xml.Dom.XmlDocument]::new(); "
            f"$doc.LoadXml($xml.OuterXml); "
            f"$toast = [Windows.UI.Notifications.ToastNotification]::new($doc); "
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($toast)"
        )
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd], check=False, timeout=5)
        return True
    except Exception as ex:
        if sys.stdout:
            print(f"[Native Toast Error]: {ex}")
    return False

# 飞书同步通知配置 (用户指令：推送到飞书采集通知群，已采集啥啥啥，入库啥啥啥就行)
ENABLE_FEISHU_SYNC = feishu_cfg.get("enabled", True)
FEISHU_SYNC_TARGET = feishu_cfg.get("target_chat_name") or feishu_cfg.get("target_chat_id") or "素材采集通知群"
_feishu_script_cfg = feishu_cfg.get("feishu_notify_script")
FEISHU_NOTIFY_PY = Path(_feishu_script_cfg) if _feishu_script_cfg and Path(_feishu_script_cfg).exists() else None
if not FEISHU_NOTIFY_PY:
    _feishu_candidates = [
        SKILL_ROOT.parent / "shared-notification" / "scripts" / "feishu_notify.py",
        Path(r"D:\AICode\.agents\skills\shared-notification\scripts\feishu_notify.py"),
        Path(r"D:\AICode\AI\skills\技能包\技能\shared-notification\scripts\feishu_notify.py")
    ]
    for candidate in _feishu_candidates:
        if candidate.exists():
            FEISHU_NOTIFY_PY = candidate
            break

def get_material_library_stats(target_city: str):
    """统计当前素材库实时大盘数据 (毫秒级)"""
    try:
        city_count = 0
        total_precision = 0
        total_autumn = 0
        if PRECISION_DIR.exists():
            city_dir = PRECISION_DIR / target_city
            if city_dir.exists():
                city_count = len([d for d in city_dir.iterdir() if d.is_dir()])
            for sub in PRECISION_DIR.iterdir():
                if sub.is_dir():
                    total_precision += len([d for d in sub.iterdir() if d.is_dir()])
        if AUTUMN_DIR.exists():
            total_autumn = len([d for d in AUTUMN_DIR.iterdir() if d.is_dir()])
        return {
            "city_count": city_count,
            "total_precision": total_precision,
            "total_autumn": total_autumn
        }
    except Exception:
        return {"city_count": 0, "total_precision": 0, "total_autumn": 0}

def send_feishu_material_sync(metadata: dict, queue_rem_count: int = 0):
    """
    向飞书专属【素材采集通知群】同步高信噪比入库交互卡片
    1. 标题超链接直达原笔记 (PC 端直开原画网页)
    2. 原文短链以独立代码块包裹 (移动端一键秒拷)
    3. 本地存储路径与四季归档路径以独立代码块包裹 (一键复制)
    4. 紧凑型大盘与规格摘要 (消除冗长平铺刷屏)
    """
    if not ENABLE_FEISHU_SYNC or not FEISHU_NOTIFY_PY or not FEISHU_NOTIFY_PY.exists():
        return
    try:
        title = metadata.get("title", "精选图文作品")
        url = metadata.get("share_url", "")
        city = metadata.get("city", "精选")
        img_cnt = metadata.get("images_count", 0)
        target_dir = metadata.get("target_dir", "")
        is_unclassified = metadata.get("is_unclassified", False)
        platform = metadata.get("platform", "小红书")
        season = metadata.get("season", "四季通用")
        content_len = metadata.get("content_length", 0)
        
        # 统计素材库大盘
        stats = get_material_library_stats(city)
        city_cnt = stats["city_count"]
        tot_prec = stats["total_precision"]
        tot_aut = stats["total_autumn"]
        
        queue_str = "已清空 (0 篇排队)" if queue_rem_count == 0 else f"剩余 {queue_rem_count} 篇排队中"

        season_work_dir = metadata.get("season_hardlink_dir", "")
        season_block = ""
        if season_work_dir:
            season_block = f"**🌿 四季归档路径 (点击一键复制)**：\n```text\n{season_work_dir}\n```\n\n"

        if is_unclassified:
            text = (
                f"**📌 标题**：[{title}]({url})\n\n"
                f"**🔗 原文短链 (点击一键复制)**：\n```text\n{url}\n```\n\n"
                f"**📂 本地暂存目录 (点击一键复制)**：\n```text\n{target_dir}\n```\n\n"
                f"**🏷️ 规格**：{platform}图文 ｜ {img_cnt} 张高清大图 ｜ {content_len} 字文案\n"
                f"**⚠️ 分类提示**：未识别到江浙沪地名（暂存 C 盘下载目录，请手动归入对应城市）\n"
                f"**📊 库容大盘**：精准库 {tot_prec} 套 ｜ 四季库 {tot_aut} 套 ｜ 队列: {queue_str}"
            )
            title_header = f"⚠️ 待分类暂存：{title[:22]}"
        elif metadata.get("collection_mode") == "manual":
            text = (
                f"**📌 标题**：[{title}]({url})\n\n"
                f"**🔗 原文短链 (点击一键复制)**：\n```text\n{url}\n```\n\n"
                f"**🎯 采集模式**：手动定向归档模式（目标专题：`{city}`）\n\n"
                f"**📂 本地存储目录 (点击一键复制)**：\n```text\n{target_dir}\n```\n\n"
                f"**🏷️ 规格**：{platform}图文 ｜ {img_cnt} 张高清大图 ｜ {content_len} 字文案\n"
                f"**📊 专题大盘**：已归入【{city}】专题 ｜ 队列: {queue_str}"
            )
            title_header = f"已定向采入【{city}】· {title[:20]}"
        else:
            text = (
                f"**📌 标题**：[{title}]({url})\n\n"
                f"**🔗 原文短链 (点击一键复制)**：\n```text\n{url}\n```\n\n"
                f"**📂 本地存储目录 (点击一键复制)**：\n```text\n{target_dir}\n```\n\n"
                f"{season_block}"
                f"**🏷️ 规格**：{platform}图文 ｜ {img_cnt} 张高清大图 ｜ {content_len} 字文案\n"
                f"**📊 大盘**：【{city}】现存 {city_cnt} 套 ｜ 精准库 {tot_prec} 套 ｜ 四季库 {tot_aut} 套 ｜ 队列: {queue_str}"
            )
            title_header = f"已采入【{city}】· {title[:20]}"

        # 用户严格指定：不要图，纯文本通知
        cmd = [
            sys.executable, str(FEISHU_NOTIFY_PY),
            "--target", FEISHU_SYNC_TARGET,
            "--title", title_header,
            "--text", text
        ]
        log_daemon(f"📢 向飞书推送采集详细通知: 《{title[:20]}》 -> {FEISHU_SYNC_TARGET}")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        log_daemon(f"❌ 飞书通知推送异常: {ex}")
        if sys.stdout:
            print(f"[Feishu Notify Error]: {ex}")

def send_feishu_error_sync(title_hint: str, url: str, reason: str):
    """向飞书素材采集通知群同步错误复制或异常提示"""
    if not ENABLE_FEISHU_SYNC or not FEISHU_NOTIFY_PY.exists():
        return
    try:
        text = (
            f"**❌ 采集异常提示**：\n\n"
            f"**📌 标题**：《{title_hint[:35]}》\n\n"
            f"**⚠️ 异常原因**：{reason}\n\n"
            f"**🔗 目标链接 (点击一键复制)**：\n```text\n{url}\n```"
        )
        cmd = [
            sys.executable, str(FEISHU_NOTIFY_PY),
            "--target", FEISHU_SYNC_TARGET,
            "--title", f"❌ 采集异常：{title_hint[:20]}",
            "--text", text
        ]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as ex:
        if sys.stdout:
            print(f"[Feishu Notify Error]: {ex}")

# 城市词库映射表 (优先从 config.json 获取，若无则使用标准江浙沪地名词库)
CITY_RULES = rules_cfg.get("city_rules") or {
    "金华义乌": ["义乌", "金华", "东阳", "横店", "武义", "永康", "浦江", "磐安", "兰溪"],
    "宁波": ["宁波", "余姚", "宁海", "象山", "慈溪", "奉化", "镇海", "东钱湖", "四明山"],
    "台州": ["台州", "温岭", "石塘", "仙居", "神仙居", "天台", "临海", "紫阳古街"],
    "舟山": ["舟山", "普陀山", "朱家尖", "东极岛", "嵊泗", "岱山", "衢山岛"],
    "安吉": ["安吉", "中南百草原", "云上草原", "大竹海", "藏龙百瀑", "浙北大峡谷"],
    "莫干山": ["莫干山", "德清", "下渚湖", "碧坞"],
    "千岛湖": ["千岛湖", "淳安"],
    "桐庐": ["桐庐", "大奇山", "瑶琳仙境", "严子陵", "omg心跳乐园"],
    "临安": ["临安", "青山湖", "风之谷", "大明山", "天目山", "太湖源"],
    "杭州": ["杭州", "西湖", "九溪", "良渚", "西溪", "湘湖", "富阳", "建德", "萧山", "余杭"],
    "绍兴": ["绍兴", "柯桥", "诸暨", "上虞", "新昌", "安昌古镇", "鲁迅故里"],
    "南京": ["南京", "栖霞山", "牛首山", "汤山", "高淳", "江宁", "玄武湖", "紫金山"],
    "宜兴溧阳": ["宜兴", "溧阳", "南山竹海", "天目湖", "善卷洞"],
    "苏州": ["苏州", "西山岛", "东山", "太湖", "昆山", "常熟", "同里", "周庄", "阳澄湖"],
    "上海": ["上海", "崇明", "青浦", "奉贤", "金山", "淀山湖", "滴水湖"],
    "湖州": ["湖州", "南浔", "龙之梦", "太湖龙之梦", "长兴", "图影", "仁皇山", "原乡小镇", "弁山"],
    "特色拓展地": ["婺源", "篁岭", "婺女洲", "黄山", "宏村", "西递", "丽水", "松阳", "缙云", "景德镇", "三清山", "望仙谷", "葛仙村", "衢州", "江山", "温州", "雁荡山", "楠溪江", "嘉兴", "乌镇", "西塘", "武夷山"]
}

def detect_city(title: str, content: str) -> str:
    # 1. 优先从标题中匹配（最精准，避免被文案末尾蹭流量的 #杭州周边 #上海团建 等标签带偏）
    t_lower = title.lower()
    for city, keywords in CITY_RULES.items():
        for kw in keywords:
            if kw.lower() in t_lower:
                return city

    # 2. 剥除 #话题 干扰后匹配正文主体
    clean_body = re.sub(r'#[^#\s]+', '', content).lower()
    for city, keywords in CITY_RULES.items():
        for kw in keywords:
            if kw.lower() in clean_body:
                return city

    # 3. 兜底全文本匹配
    full_text = (title + " " + content).lower()
    for city, keywords in CITY_RULES.items():
        for kw in keywords:
            if kw.lower() in full_text:
                return city

    return "地点待确认"

def is_autumn_content(title: str, content: str) -> bool:
    text = (title + " " + content).lower()
    autumn_keywords = ["秋", "桂花", "红叶", "枫叶", "采摘", "围炉", "柿子", "银杏", "徒步", "露营", "国庆", "中秋", "9月", "10月", "11月", "土灶", "户外"]
    return any(k in text for k in autumn_keywords)

GAME_KEYWORDS = [
    "破冰", "互动游戏", "桌游", "团建游戏", "年会游戏", "聚会游戏", 
    "晚会游戏", "惩罚游戏", "热身游戏", "室内游戏", "小游戏", "互动小游戏", 
    "游戏合集", "游戏推荐", "派对游戏", "搞怪游戏", "酒桌游戏"
]

COLLECTION_KEYWORDS = [
    "大合集", "旅行合集", "周边游合集", "攻略合集", "好去处合集", "短途游", 
    "周边游", "一站式畅游", "盘点", "汇总", "好去处", "自驾游路线", 
    "江浙沪周边", "避暑地", "玩水地", "江浙沪游", "多城", "宝藏景点攻略合集",
    "畅游", "目的地盘点", "路线推荐", "全部码住"
]

COLLECTION_PATTERNS = [
    r'\d+[个处座条]\w*(景点|好去处|避暑地|目的地|路线)',
    r'\d+城',
    r'\d+\+?\s*宝藏景点',
    r'江浙沪\w*合集',
]

def detect_traffic_and_category(title: str, content: str) -> tuple[str, str]:
    """智能识别流量类型 (精准流量/泛流量) 与目标二级分类/城市"""
    t_lower = title.lower()
    c_lower = content.lower()
    full_text = f"{t_lower} {c_lower}"

    # 1. 优先判定小游戏 / 破冰互动 (直接分流至泛流量/团建游戏)
    for kw in GAME_KEYWORDS:
        if kw in t_lower or kw in c_lower:
            return "泛流量", "团建游戏"

    # 2. 判定跨城大合集 / 周边游大盘 (直接分流至泛流量/大合集)
    is_collection = False
    for kw in COLLECTION_KEYWORDS:
        if kw in t_lower:
            is_collection = True
            break
    if not is_collection:
        for pat in COLLECTION_PATTERNS:
            if re.search(pat, title):
                is_collection = True
                break

    # 3. 城市匹配检测
    detected_city = detect_city(title, content)

    if is_collection:
        # 如果既是大合集又命中了城市，若标题明显强调"周边/多城/合集/N个景点/短途游"，仍归入泛流量大合集
        if detected_city == "地点待确认" or any(ck in t_lower for ck in ["江浙沪", "多城", "周边游", "合集", "短途游", "码住"]):
            return "泛流量", "大合集"

    if detected_city != "地点待确认":
        # 命中具体城市：判断是精准企业团建还是泛流量个人攻略
        precision_keywords = [
            "团建", "公司", "年会", "拓展", "策划", "方案", "hr", "会议", "轰趴", "开会", 
            "定制", "企业", "党建", "工会", "团队", "部门", "团建活动", "团建方案", 
            "团建策划", "团建定制", "团队建设", "破冰团建", "组织团建", "团建场地", "团建去哪"
        ]
        if any(pk in full_text for pk in precision_keywords):
            return "精准流量", detected_city
        else:
            # 个人自驾、徒步、打卡、亲子游、周末去处等无企业团建属性 -> 泛流量个人攻略
            return "泛流量", detected_city

    # 4. 再次兜底大合集判定 (例如文案中包含江浙沪周边游盘点)
    if "江浙沪" in full_text and any(w in full_text for w in ["周边游", "攻略", "自驾", "合集", "路线", "去处", "避暑"]):
        return "泛流量", "大合集"

    return "未分类", "地点待确认"

SEASON_RULES = {
    '春季': {
        'folder': '春季（3—5月·智能分类）',
        'dir_obj': SPRING_DIR,
        'words': ['春季', '春天', '春日', '春游', '踏青', '赏花', '采茶', '新茶', '明前茶', '春茶', '挖笋', '采笋', '春笋', '青团', '放风筝', '清明', '五一', '早春', '海棠', '杜鹃', '郁金香', '油菜花', '樱花', '桃花', '梨花'],
        'months': ['3月', '4月', '5月', '三月', '四月', '五月']
    },
    '夏季': {
        'folder': '夏季（6—8月·智能分类）',
        'dir_obj': SUMMER_DIR,
        'words': ['夏季', '夏天', '夏日', '夏游', '避暑', '漂流', '溯溪', '玩水', '水上乐园', '杨梅', '采杨梅', '西瓜', '桨板', '皮划艇', '赶海', '海岛', '瀑布', '纳凉', '夜市', '夜游', '萤火虫', '端午', '暑假', '梅雨', '入梅', '出梅'],
        'months': ['6月', '7月', '8月', '六月', '七月', '八月']
    },
    '秋季': {
        'folder': '秋季（9—11月·智能分类）',
        'dir_obj': AUTUMN_DIR,
        'words': ['秋季', '秋天', '秋日', '秋游', '赏秋', '大闸蟹', '吃蟹', '品蟹', '太湖蟹', '开捕', '开渔', '桂花', '桂花龙井', '板栗', '柿子', '枫叶', '红枫', '银杏', '稻田', '割稻', '秋收', '丰收', '晒秋', '芦苇', '粉黛乱子草', '重阳', '登高', '赏菊', '菊花', '秋意', '秋色', '中秋', '国庆'],
        'months': ['9月', '10月', '11月', '九月', '十月', '十一月']
    },
    '冬季': {
        'folder': '冬季（12—2月·智能分类）',
        'dir_obj': WINTER_DIR,
        'words': ['冬季', '冬天', '冬日', '冬游', '滑雪', '赏雪', '冰雪', '圣诞', '春节', '过年', '年会', '温泉', '泡汤', '私汤', '围炉煮茶', '杀年猪', '刨猪汤', '烤全羊', '跨年', '元旦', '尾牙', '雾凇', '年终总结'],
        'months': ['12月', '1月', '2月', '十二月', '一月', '二月']
    }
}

def detect_season_matches(title: str, content: str) -> list[str]:
    """返回匹配的季节列表（'春季', '夏季', '秋季', '冬季'，若均未命中则返回 ['四季通用']）"""
    text = f"{title} {content}".lower()
    scores = {}
    for s_name, s_data in SEASON_RULES.items():
        found_w = [w for w in s_data['words'] if w in text]
        found_m = [m for m in s_data['months'] if m in text]
        if found_w or found_m:
            scores[s_name] = len(found_w) * 2 + len(found_m) * 3
    if not scores:
        return ["四季通用"]
    max_score = max(scores.values())
    matched = [s for s, sc in scores.items() if not (max_score > sc * 2)]
    return matched if matched else ["四季通用"]

def extract_title_hint(raw_text: str) -> str:
    """从分享口令文本中提取有意义的笔记标题提示（兼容小红书与抖音图文）"""
    clean = re.sub(r'https?://\S+', '', raw_text)
    clean = re.sub(r'[，。！？\s\r\n]+', ' ', clean).strip()
    clean = re.sub(r'(带走口令|先复制这段文字|再进|发现精彩|来【小红书】|查看完整笔记|复制这段|小红书).*', '', clean).strip()
    clean = re.sub(r'^[\d.]+ 复制打开抖音[，,]?\s*看看【[^】]+】\s*', '', clean).strip()
    clean = re.sub(r'【[^】]+的图文作品】', '', clean).strip()
    return clean[:35] if clean else "精选图文作品"

def extract_creator_name(url: str, raw_text: str, title_hint: str) -> tuple[str, str]:
    """提取博主名字与平台"""
    platform = "小红书" if ("xhs" in url.lower() or "xiaohongshu" in url.lower() or "小红书" in raw_text) else "抖音"
    m_at = re.search(r'@([^\s，。！？\n\r]+)', raw_text)
    if m_at:
        return m_at.group(0), platform
    m_bracket = re.search(r'【([^】]+?)(?:的图文作品|的作品)?】', raw_text)
    if m_bracket:
        return f"@{m_bracket.group(1)}", platform
    return f"@{title_hint[:15]}", platform

def register_benchmark_account(target_url: str, raw_text: str, title_hint: str) -> tuple[bool, str]:
    """将复制的主页口令全自动双向建档至：
    1. 原团建项目《对标账号完整清单.md》（带 Axxx 编号大表 + 四维业务分类）
    2. 第二大脑《对标账号与样板观察清单.md》（带详细档案与拆解要点）
    """
    creator_name, platform = extract_creator_name(target_url, raw_text, title_hint)
    is_new = False
    now_str = time.strftime("%Y-%m-%d %H:%M")
    now_date = time.strftime("%Y-%m-%d")

    # 1. 录入原团建项目对标大表
    if PROJECT_BENCHMARK_FILE.exists():
        try:
            content_proj = PROJECT_BENCHMARK_FILE.read_text(encoding="utf-8")
            if target_url not in content_proj and (not creator_name or creator_name not in content_proj):
                # 寻找最大的 Axxx 编号
                all_ids = [int(m) for m in re.findall(r'\| A(\d{3}) \|', content_proj)]
                next_id = f"A{(max(all_ids) + 1):03d}" if all_ids else "A030"
                
                # 构建表格新行
                new_row = f"| {next_id} | {now_date} | {platform} | {creator_name} | {target_url} | 剪贴板自动识别对标主页 | 待拆解 | 剪贴板复制主页自动建档 | 是 |\n"
                
                # 寻找表格末尾（分割线或分类索引标记）
                if "\n---\n" in content_proj:
                    parts = content_proj.split("\n---\n", 1)
                    content_proj = parts[0].rstrip() + "\n" + new_row + "\n---\n" + parts[1]
                else:
                    content_proj += "\n" + new_row

                # 追加变更记录
                log_marker = "|---|---|---|"
                if log_marker in content_proj:
                    p1, p2 = content_proj.split(log_marker, 1)
                    log_row = f"\n| {now_str} | 反重力 | 剪贴板自动建档 {platform} 对标账号 {creator_name}（{next_id}） |"
                    content_proj = p1 + log_marker + log_row + p2
                
                PROJECT_BENCHMARK_FILE.write_text(content_proj, encoding="utf-8")
                is_new = True
                if sys.stdout:
                    print(f"[Benchmark] Recorded {creator_name} ({next_id}) into Project benchmark file.")
        except Exception as ex:
            if sys.stdout:
                print(f"[Project Benchmark Error]: {ex}")

    # 2. 录入第二大脑对标档案
    if SECOND_BRAIN_BENCHMARK_FILE.exists():
        try:
            content_sb = SECOND_BRAIN_BENCHMARK_FILE.read_text(encoding="utf-8")
            if target_url not in content_sb and (not creator_name or creator_name not in content_sb):
                new_entry = f"""
### 账号：{creator_name}（{platform}垂直对标）

| 属性 | 详情数据 / 说明 |
| :--- | :--- |
| **平台** | {platform} |
| **主页链接** | `{target_url}` |
| **录入来源** | 剪贴板自动识别对标主页口令 |
| **录入时间** | {now_str} |
| **原始口令** | `{raw_text[:80]}` |
| **业务定位** | 江浙沪团建/周边游对标参考 |
"""
                marker = "## 🔬 制作参考与拆解要点"
                if marker in content_sb:
                    parts = content_sb.split(marker, 1)
                    content_sb = parts[0].rstrip() + "\n" + new_entry + "\n---\n\n" + marker + parts[1]
                else:
                    content_sb += "\n" + new_entry
                
                log_marker = "|---|---|---|"
                if log_marker in content_sb:
                    p1, p2 = content_sb.split(log_marker, 1)
                    log_row = f"\n| {now_str} | 反重力 | 剪贴板自动识别并归档 {platform} 对标账号 {creator_name} |"
                    content_sb = p1 + log_marker + log_row + p2
                
                SECOND_BRAIN_BENCHMARK_FILE.write_text(content_sb, encoding="utf-8")
                is_new = True
                if sys.stdout:
                    print(f"[Benchmark] Recorded {creator_name} into Second Brain benchmark file.")
        except Exception as ex:
            if sys.stdout:
                print(f"[SecondBrain Benchmark Error]: {ex}")

    return is_new, creator_name

def is_profile_or_homepage(url: str, raw_text: str = "") -> bool:
    """快速识别口令或链接是否为博主主页，避免将主页当作单篇笔记下载"""
    u_lower = url.lower()
    t_lower = raw_text.lower()
    if "user/profile" in u_lower or "user/profile" in t_lower:
        return True
    if "/user/" in u_lower:
        return True
    if "ta的主页" in t_lower or "查看ta的主页" in t_lower or "的主页" in t_lower:
        return True
    return False

def check_url_type(target_url: str) -> tuple[bool, str]:
    """检查链接是否为单篇笔记。如果确定是主页返回 (False, 'UNSUPPORTED_PROFILE: 博主个人主页')"""
    u_lower = target_url.lower()
    if "user/profile" in u_lower or "/user/" in u_lower:
        return False, "UNSUPPORTED_PROFILE: 博主个人主页"
    if "xhslink" in u_lower:
        try:
            import urllib.request
            req = urllib.request.Request(target_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                final_url = resp.geturl().lower()
                if "user/profile" in final_url or "/user/" in final_url:
                    return False, "UNSUPPORTED_PROFILE: 短链重定向至博主个人主页"
        except Exception:
            pass
    return True, "OK"

# 历史防重库
def load_history() -> set:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("urls", []))
        except:
            return set()
    return set()

def save_history(urls: set):
    try:
        tmp_file = HISTORY_FILE.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"urls": list(urls), "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f, ensure_ascii=False, indent=2)
        tmp_file.replace(HISTORY_FILE)
    except Exception as e:
        if sys.stdout:
            print(f"[History Save Error]: {e}")

# 待下载队列管理器 (Thread-safe Pending Queue)
class QueueManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.queue = []         # 待下载项列表
        self.failed = []        # 彻底失败项列表
        self.cooldown_until = 0.0
        self.cooldown_reason = ""
        self.load()

    def load(self):
        with self.lock:
            if QUEUE_FILE.exists():
                try:
                    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.queue = data.get("queue", [])
                        self.failed = data.get("failed", [])
                        self.cooldown_until = data.get("cooldown_until", 0.0)
                        self.cooldown_reason = data.get("cooldown_reason", "")
                except Exception as e:
                    if sys.stdout:
                        print(f"[Queue Load Error]: {e}")
                    self.queue = []
                    self.failed = []

    def save(self):
        try:
            tmp_file = QUEUE_FILE.with_suffix(".tmp")
            data = {
                "queue": self.queue,
                "failed": self.failed,
                "cooldown_until": self.cooldown_until,
                "cooldown_reason": self.cooldown_reason,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp_file.replace(QUEUE_FILE)
            try:
                self._last_mtime = QUEUE_FILE.stat().st_mtime
            except Exception:
                pass
        except Exception as e:
            if sys.stdout:
                print(f"[Queue Save Error]: {e}")

    def add(self, url: str, raw_text: str, title_hint: str) -> tuple[bool, int, dict]:
        with self.lock:
            # 查重：已经在队列中则不重复入队
            for idx, item in enumerate(self.queue):
                if item.get("url") == url:
                    return False, idx + 1, item
            
            new_item = {
                "id": f"xhs_{int(time.time()*1000)}_{random.randint(100, 999)}",
                "url": url,
                "title_hint": title_hint,
                "raw_text": raw_text[:2000],
                "added_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "pending",
                "retry_count": 0,
                "last_error": None
            }
            self.queue.append(new_item)
            pos = len(self.queue)
            self.save()
            return True, pos, new_item

    def peek(self) -> dict | None:
        with self.lock:
            # 外部改动同步（若前端或外部移除了任务或清空了队列，自动重载内存）
            if QUEUE_FILE.exists():
                try:
                    mtime = QUEUE_FILE.stat().st_mtime
                    if mtime > getattr(self, "_last_mtime", 0):
                        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self.queue = data.get("queue", [])
                            self.failed = data.get("failed", [])
                            self.cooldown_until = data.get("cooldown_until", 0.0)
                            self.cooldown_reason = data.get("cooldown_reason", "")
                            self._last_mtime = mtime
                except Exception:
                    pass
            if self.queue:
                return dict(self.queue[0])
            return None

    def pop_success(self, item_id: str):
        with self.lock:
            self.queue = [x for x in self.queue if x.get("id") != item_id]
            self.save()

    def pop_discard(self, item_id: str, reason: str):
        with self.lock:
            target = None
            for item in self.queue:
                if item.get("id") == item_id:
                    target = item
                    break
            if target:
                target["status"] = "discarded"
                target["last_error"] = str(reason)[:200]
                self.queue.remove(target)
                self.failed.append(target)
            self.save()

    def mark_retry(self, item_id: str, error_msg: str, cooldown_seconds: float):
        with self.lock:
            target = None
            for item in self.queue:
                if item.get("id") == item_id:
                    target = item
                    break
            if target:
                target["retry_count"] = target.get("retry_count", 0) + 1
                target["last_error"] = str(error_msg)[:200]
                target["last_attempt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                if target["retry_count"] >= MAX_RETRIES:
                    target["status"] = "failed"
                    self.queue.remove(target)
                    self.failed.append(target)
                else:
                    target["status"] = "cooling_down"
            
            self.cooldown_until = time.time() + cooldown_seconds
            self.cooldown_reason = f"风控退避保护: {error_msg[:40]}"
            self.save()

    def set_cooldown(self, seconds: float, reason: str = "拟人间隔"):
        with self.lock:
            self.cooldown_until = time.time() + seconds
            self.cooldown_reason = reason
            self.save()

    def get_remaining_count(self) -> int:
        with self.lock:
            return len(self.queue)

    def is_cooling_down(self) -> tuple[bool, float, str]:
        with self.lock:
            now = time.time()
            if now < self.cooldown_until:
                return True, self.cooldown_until - now, self.cooldown_reason
            return False, 0.0, ""

# 剪贴板读取器 (pywin32 优先 + 64位 ctypes 兜底)
def get_clipboard_text() -> str:
    try:
        import win32clipboard
        import win32con
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return data or ""
            return ""
        finally:
            win32clipboard.CloseClipboard()
    except Exception:
        pass

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.OpenClipboard.restype = wintypes.BOOL
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = wintypes.HANDLE
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = wintypes.LPVOID
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalUnlock.restype = wintypes.BOOL

        if not user32.OpenClipboard(None):
            return ""
        try:
            CF_UNICODETEXT = 13
            h_clip = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_clip:
                return ""
            ptr = kernel32.GlobalLock(h_clip)
            if not ptr:
                return ""
            text = ctypes.wstring_at(ptr)
            kernel32.GlobalUnlock(h_clip)
            return text or ""
        finally:
            user32.CloseClipboard()
    except Exception:
        return ""

MEDIA_LINK_REGEX = re.compile(
    r'https?://(?:xhslink\.com|xhslink\.cn|www\.xiaohongshu\.com|v\.douyin\.com|www\.douyin\.com|iesdouyin\.com)/[A-Za-z0-9_/.\-]+(?:\?[^\s\u4e00-\u9fa5]+)?'
)

def normalize_clean_url(raw_text: str) -> str:
    """
    智能优选与清洗媒体链接 (全面支持小红书与抖音安全凭据) v3.7.0：
    1. 优先提取精炼短链 (xhslink.cn/o/..., xhslink.com/o/..., v.douyin.com/...)
    2. 对小红书长链 (discovery/item/..., explore/...)：
       - 剥离无用的营销追踪打点 (app_platform, app_version, shareRedId, apptime, share_channel 等)
       - 关键：强制完整保留 xsec_token 与 xsec_source (小红书 WAF 核心免登鉴权凭据)！
    3. 对抖音长链：提取干净路径。
    [v3.7.0] 新增多行口令预处理：小红书 App 分享的口令文本中，URL 参数有时因换行被截断
             导致 xsec_token 只剩单字符 'C'。预处理步骤将 URL 参数行合并后再提取 token。
    """
    if not raw_text:
        return ""

    # [v3.7.0] 预处理：将多行口令中被换行截断的 URL 参数重新拼接
    # 小红书 App 分享文本有时格式为：
    #   ...&xsec_token=ABCDEFGxxxx\n（换行在 token 中间或末尾）
    # 将所有换行后紧跟 '&' 或 URL 参数字符的行与前行合并
    preprocessed = re.sub(r'\r?\n(?=[A-Za-z0-9%_\-&=+])', '', raw_text)

    # 1. 优先探测小红书与抖音短链 (短链在服务端会自动补齐安全重定向)
    short_xhs = re.search(r'https?://(?:xhslink\.cn|xhslink\.com)/[A-Za-z0-9_/]+', preprocessed)
    if short_xhs:
        return short_xhs.group(0).split('?')[0].strip()

    short_dy = re.search(r'https?://v\.douyin\.com/[A-Za-z0-9_\-]+/?', preprocessed)
    if short_dy:
        return short_dy.group(0).split('?')[0].strip()

    # 2. 小红书长链探测与安全清洗
    # [v3.7.0] token 正则：[^\&\r\n]+ 而非 [^\&\s]+，允许 token 中含有 URL 编码的空格(%20)
    #          同时在 preprocessed 文本中搜索，防止换行截断残留
    token_match = re.search(r'[?&](xsec_token=[^&\r\n]+)', preprocessed)
    source_match = re.search(r'[?&](xsec_source=[^&\r\n\s]+)', preprocessed)
    extra_params = []
    if token_match:
        token_val = token_match.group(1).strip()
        # 安全校验：token 值至少 4 字符，否则为截断残留，忽略（避免带残缺 token 导致 300031）
        if len(token_val) > len("xsec_token=") + 3:
            extra_params.append(token_val)
    if source_match:
        extra_params.append(source_match.group(1).strip())
    query_suffix = ("?" + "&".join(extra_params)) if extra_params else ""

    # 2.1 explore 路由
    long_xhs_explore = re.search(r'https?://(?:www\.)?xiaohongshu\.com/explore/[a-fA-F0-9]+', preprocessed)
    if long_xhs_explore:
        return long_xhs_explore.group(0).strip() + query_suffix

    # 2.2 discovery/item 路由
    long_xhs_item = re.search(r'https?://(?:www\.)?xiaohongshu\.com/discovery/item/[a-fA-F0-9]+', preprocessed)
    if long_xhs_item:
        return long_xhs_item.group(0).strip() + query_suffix

    # 2.3 博主主页
    long_xhs_user = re.search(r'https?://(?:www\.)?xiaohongshu\.com/user/profile/[a-fA-F0-9]+', preprocessed)
    if long_xhs_user:
        return long_xhs_user.group(0).strip()

    # 3. 抖音长链 (剥离追踪参数)
    long_dy = re.search(r'https?://(?:www\.)?douyin\.com/(?:note|video)/\d+', preprocessed)
    if long_dy:
        return long_dy.group(0).strip()

    # 4. 通用正则匹配兜底
    m = re.search(r'https?://(?:xhslink\.com|xhslink\.cn|www\.xiaohongshu\.com|v\.douyin\.com|www\.douyin\.com|iesdouyin\.com)/[A-Za-z0-9_/.\-]+(?:\?[^\s\u4e00-\u9fa5]+)?', preprocessed)
    if m:
        matched_url = m.group(0).strip()
        if "xiaohongshu.com" in matched_url and extra_params:
            base_part = matched_url.split('?')[0]
            return base_part + query_suffix
        return matched_url.split('?')[0]

    return ""


def extract_all_clean_targets(raw_text: str) -> list[tuple[str, str, str]]:
    """
    智能从整段分享文本或剪贴板多行内容中提取所有有效作品或主页链接。
    全面支持单条与批量多条，返回列表: [(clean_url, title_hint, raw_segment), ...]
    """
    if not raw_text:
        return []
    
    # 查找所有支持平台的链接 (小红书/抖音)
    pattern = r'https?://(?:xhslink\.(?:cn|com)|(?:www\.)?xiaohongshu\.com|v\.douyin\.com|(?:www\.)?douyin\.com|iesdouyin\.com)/[A-Za-z0-9_/.\-]+(?:\?[^\s\u4e00-\u9fa5]+)?'
    matches = list(re.finditer(pattern, raw_text))
    if not matches:
        return []
    
    results = []
    seen_urls = set()
    for i, match in enumerate(matches):
        start_idx = 0 if i == 0 else matches[i-1].end()
        end_idx = len(raw_text) if i == len(matches) - 1 else matches[i+1].start()
        segment = raw_text[start_idx:end_idx]
        
        clean_url = normalize_clean_url(segment) or normalize_clean_url(match.group(0))
        if clean_url and clean_url not in seen_urls:
            seen_urls.add(clean_url)
            hint = extract_title_hint(segment)
            results.append((clean_url, hint, segment))
            
    return results


# 核心下载执行函数
def execute_download_and_file(target_url: str) -> tuple[bool, str, dict]:
    """
    执行万能下载器无感解包，并完成城市分流、四季硬链接、元数据打标。
    返回: (成功标志, 错误原因或最终文件夹名, 元数据字典)
    """
    is_note, type_msg = check_url_type(target_url)
    if not is_note:
        return False, type_msg, {}

    if TEMP_DOWNLOAD_DIR.exists():
        shutil.rmtree(TEMP_DOWNLOAD_DIR, ignore_errors=True)
    TEMP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    saved_argv = sys.argv[:]
    try:
        sys.argv = ["xhs-dl", target_url, "-o", str(TEMP_DOWNLOAD_DIR), "--mode", "fast", "--max-images", str(MAX_IMAGE_ALLOWED)]
        xhs_dl_main()
    except SystemExit:
        pass
    except Exception as e:
        return False, f"下载引擎异常: {e}", {}
    finally:
        sys.argv = saved_argv

    downloaded_dirs = [d for d in TEMP_DOWNLOAD_DIR.iterdir() if d.is_dir()]
    if not downloaded_dirs:
        return False, f"未生成素材目录 (可能触发超过 {MAX_IMAGE_ALLOWED} 张前置熔断拦截或页面验证受限)", {}

    work_dir = downloaded_dirs[0]
    folder_name = work_dir.name

    # 读取文案
    txt_file = work_dir / "文案.txt"
    content_text = ""
    title_text = folder_name
    if txt_file.exists():
        try:
            content_text = txt_file.read_text(encoding="utf-8", errors="ignore")
            m_title = re.search(r"标题[：:]\s*(.+)", content_text)
            if m_title:
                title_text = m_title.group(1).strip()
        except:
            pass

    # 校验是否真正下载到了图片 (防风控空壳)
    images = [f for f in work_dir.iterdir() if f.suffix.lower() in [".jpg", ".png", ".jpeg", ".webp"]]
    img_count = len(images)
    if img_count == 0:
        return False, "解析未包含有效图片资源(可能触发页面验证)", {}

    # 用户明确铁律：超过 15 张的超长素材一律不得落地入库，直接拦截丢弃
    MAX_IMAGE_ALLOWED = 15
    if img_count > MAX_IMAGE_ALLOWED:
        shutil.rmtree(work_dir, ignore_errors=True)
        return False, f"素材图片超限({img_count}张 > 上限{MAX_IMAGE_ALLOWED}张)，触发超长过滤策略直接拦截丢弃", {}

    # 动态检测当前采集路由模式 (自动识别模式 vs 手动定向归类模式)
    mode_info = get_current_collector_mode()
    curr_mode = mode_info.get("mode", "auto")
    manual_target = mode_info.get("target_folder", "").strip()

    if curr_mode == "manual" and manual_target:
        # 手动定向归类模式：暂停多分支动态识别，所有素材直接落地至指定目标文件夹 (如: 民宿合集)
        traffic_type = "手动定向"
        target_category = manual_target
        target_city = manual_target
        is_unclassified = False
        
        # 兼容相对路径（相对于素材库根目录）或绝对路径
        if Path(manual_target).is_absolute():
            city_dest_dir = Path(manual_target)
        else:
            city_dest_dir = BASE_MATERIAL_DIR / manual_target
        final_target_dir = city_dest_dir / folder_name
    else:
        # 智能流量类型与目标二级分类/城市识别 (大合集/团建游戏直通顶层平级货架)
        traffic_type, target_category = detect_traffic_and_category(title_text, content_text)
        is_unclassified = (traffic_type == "未分类")

        if is_unclassified:
            # 用户明确要求：无法判断分类时，下载到 C 盘下载文件夹 (C:\Users\z\Downloads)
            city_dest_dir = C_DOWNLOADS_DIR
            target_city = "未分类(暂存C盘下载)"
            final_target_dir = city_dest_dir / folder_name
        else:
            target_city = target_category
            if traffic_type == "泛流量":
                city_dest_dir = PAN_TRAFFIC_DIR / target_category
            else:
                city_dest_dir = PRECISION_DIR / target_category
            final_target_dir = city_dest_dir / folder_name

    city_dest_dir.mkdir(parents=True, exist_ok=True)
    if final_target_dir.exists():
        shutil.rmtree(final_target_dir, ignore_errors=True)

    shutil.move(str(work_dir), str(final_target_dir))

    # 从标准文件夹名解析作者与赞评互动元数据: 评X-赞Y-标题-作者
    author = ""
    comments_cnt = 0
    likes_cnt = 0
    m_stat = re.match(r"^评(\d+)-赞(\d+)-(.*?)(?:-([^-]+))?$", folder_name)
    if m_stat:
        try:
            comments_cnt = int(m_stat.group(1))
            likes_cnt = int(m_stat.group(2))
            if m_stat.group(4):
                author = m_stat.group(4).strip()
        except:
            pass

    # 季节判断与硬链接目录预备 (支持春、夏、秋、冬及四季通用多维穿透)
    # 注意：在手动定向模式下专注于该专项合集，不自动向四季目录扩散
    season_work_dirs = []
    if curr_mode == "auto":
        matched_seasons = detect_season_matches(title_text, content_text)
        season_name = "、".join(matched_seasons)
        if not is_unclassified:
            for s in matched_seasons:
                if s == "四季通用":
                    s_base = ALL_SEASON_DIR
                elif s in SEASON_RULES:
                    s_base = SEASON_RULES[s]['dir_obj']
                else:
                    s_base = ALL_SEASON_DIR
                # 严格按照 [季节]/[流量类型]/[城市或大盘]/[帖子包] 规范层级构建硬链接
                s_target_dir = s_base / traffic_type / target_category / folder_name
                season_work_dirs.append((s, s_target_dir))
    else:
        matched_seasons = ["指定专题"]
        season_name = f"手动定向({manual_target})"

    # 元数据打标 (metadata.json) - 100% 完备规范元数据
    platform = "抖音" if ("douyin" in target_url.lower()) else "小红书"
    metadata = {
        "title": title_text,
        "author": author,
        "likes_count": likes_cnt,
        "comments_count": comments_cnt,
        "city": target_city,
        "traffic_type": traffic_type,
        "category": target_category,
        "season": season_name,
        "is_unclassified": is_unclassified,
        "collection_mode": curr_mode,
        "manual_target_folder": manual_target if curr_mode == "manual" else "",
        "source": "剪贴板监听",
        "engine": "万能下载器 v3.8.3",
        "platform": platform,
        "tags": ["剪切板下载", "万能下载器下载", f"{platform}图文", traffic_type, target_city] + [f"{s}素材" for s in matched_seasons],
        "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": target_url,
        "source_url": target_url,
        "original_url": target_url,
        "share_url": target_url,
        "images_count": img_count,
        "images_list": [f.name for f in images],
        "content_length": len(content_text),
        "content_preview": content_text[:120].strip() if content_text else "",
        "folder_name": folder_name,
        "target_dir": str(final_target_dir),
        "season_hardlink_dirs": [str(d) for _, d in season_work_dirs],
        "version": "3.8.0",
        "status": "success",
        "captured_by": "universal-clipboard-collector"
    }
    try:
        (final_target_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        log_daemon(f"📝 元数据打标完成: {final_target_dir / 'metadata.json'} (包含 {len(metadata)} 项核心属性)")
    except Exception as e:
        log_daemon(f"❌ 元数据打标异常: {e}")
        if sys.stdout:
            print(f"[Metadata Error]: {e}")

    # 确保文案.txt 底部写入可点击的原链接，便于人工直读与追溯
    try:
        final_txt_file = final_target_dir / "文案.txt"
        if final_txt_file.exists():
            raw_txt = final_txt_file.read_text(encoding="utf-8", errors="ignore")
            if target_url not in raw_txt:
                final_txt_file.write_text(raw_txt.rstrip() + f"\n\n原链接：{target_url}\n", encoding="utf-8")
                log_daemon(f"📝 已在文案.txt底部追加原链接: {target_url}")
    except Exception as e:
        log_daemon(f"⚠️ 追加文案原链接异常: {e}")

    # 四季分类与 NTFS 原生硬链接分发 (已识别地名才分发，跨卷自动降级保障 100% 留存)
    if not is_unclassified and season_work_dirs:
        for s_tag, s_work_dir in season_work_dirs:
            try:
                s_work_dir.mkdir(parents=True, exist_ok=True)
                link_mode = "NTFS硬链接"
                for src_file in final_target_dir.iterdir():
                    if src_file.is_file():
                        dest_file = s_work_dir / src_file.name
                        if not dest_file.exists():
                            linked = False
                            # 1. 优先尝试 NTFS 原生硬链接 (要求同卷同盘符，0 存储占用)
                            src_drive = getattr(src_file, 'drive', '')
                            dest_drive = getattr(dest_file, 'drive', '')
                            if src_drive and dest_drive and src_drive.upper() == dest_drive.upper():
                                try:
                                    os.link(src_file, dest_file)
                                    linked = True
                                except Exception:
                                    linked = False
                            # 2. 跨驱动器容灾降级：尝试软链接或智能复制 (绝不静默丢失)
                            if not linked:
                                link_mode = "跨卷副本/软链"
                                try:
                                    os.symlink(src_file, dest_file)
                                except Exception:
                                    try:
                                        shutil.copy2(src_file, dest_file)
                                    except Exception:
                                        pass
                log_daemon(f"🔗 四季归档建立成功 ({s_tag}·{link_mode}): {s_work_dir}")
            except Exception as ex_link:
                log_daemon(f"❌ 建立四季归档异常 ({s_tag}): {ex_link}")
                if sys.stdout:
                    print(f"[Hardlink Error {s_tag}]: {ex_link}")

    return True, folder_name, metadata


# 消费工作线程 (Queue Worker Thread)
def queue_worker_loop(queue_mgr: QueueManager, history_set: set):
    """
    负责从待下载队列中按顺序消费链接。
    严格受风控冷却与拟人间隔控制，下载成功即入库并通知，失败则退避并保留队列。
    """
    while True:
        if collection_paused():
            time.sleep(1.0)
            continue
        try:
            # 1. 检查是否处于风控或拟人冷却状态
            is_cooling, remain_sec, reason = queue_mgr.is_cooling_down()
            if is_cooling:
                time.sleep(min(remain_sec, 2.0))
                continue

            # 2. 查看是否有待下载任务
            item = queue_mgr.peek()
            if not item:
                update_heartbeat(status="idle", queue_len=0, history_len=len(history_set), extra="")
                time.sleep(1.0)
                continue

            item_id = item["id"]
            url = item["url"]
            title_hint = item.get("title_hint", "小红书笔记")
            retry_count = item.get("retry_count", 0)

            rem_count = queue_mgr.get_remaining_count()
            update_heartbeat(status="downloading", queue_len=rem_count, history_len=len(history_set), extra=f"正在采集: {title_hint}")

            if sys.stdout:
                print(f"\n[Worker] Start downloading: {url} (Retry: {retry_count})")

            # 3. 执行下载
            success, result_msg, metadata = execute_download_and_file(url)

            if success:
                # 记录到历史去重账本
                history_set.add(url)
                save_history(history_set)
                
                # 从待下载队列中移除
                queue_mgr.pop_success(item_id)
                rem_count = queue_mgr.get_remaining_count()

                # 设置正常平缓拟人冷却
                cooldown_sec = random.uniform(*NORMAL_COOLDOWN_RANGE)
                queue_mgr.set_cooldown(cooldown_sec, "平缓拟人间隔")
                update_heartbeat(status="cooling", queue_len=rem_count, history_len=len(history_set), extra=f"平缓拟人冷却中 ({int(cooldown_sec)}s)")

                # 发送桌面原生通知
                final_title = metadata.get("title", title_hint)
                short_title = final_title[:24] + ("..." if len(final_title) > 24 else "")
                city = metadata.get("city", "精选")
                img_cnt = metadata.get("images_count", 0)
                target_folder = metadata.get("target_dir", "")
                is_unclassified = metadata.get("is_unclassified", False)
                
                platform = metadata.get("platform", "精选")
                queue_tip = f" (剩余 {rem_count} 篇排队中)" if rem_count > 0 else ""
                
                if is_unclassified:
                    notify_text = f"⚠️ 未能识别地名（已暂存至C盘下载）：《{short_title}》\n📍 点击可直接打开 Downloads 文件夹{queue_tip}"
                    send_desktop_notification(notify_text, title="素材待手动分类", status="warning", action_target=target_folder)
                elif metadata.get("collection_mode") == "manual":
                    notify_text = f"✅ 已定向采集入库（{platform}图文）：《{short_title}》\n📍 已归入【🎯 定向专题·{city}】（含 {img_cnt} 张原画大图+文案）{queue_tip}"
                    send_desktop_notification(notify_text, title=f"{platform}定向专题采集", status="success", action_target=target_folder)
                else:
                    traffic_type = metadata.get("traffic_type", "精准流量")
                    if city == "大合集":
                        shelf_desc = "顶层平级货架·泛流量合集"
                    elif city == "团建游戏":
                        shelf_desc = "顶层平级货架·泛流量小游戏"
                    elif traffic_type == "泛流量":
                        shelf_desc = f"顶层平级货架·泛流量个人攻略·{city}"
                    else:
                        shelf_desc = f"{traffic_type}·{city}"
                    notify_text = f"✅ 已自动采集入库（{platform}图文）：《{short_title}》\n📍 已归入【{shelf_desc}】库（含 {img_cnt} 张原画大图+文案）{queue_tip}"
                    send_desktop_notification(notify_text, title=f"{platform}剪贴板采集", status="success", action_target=target_folder)

                # 同步向飞书发送耗材入库卡片 (详细内容，不要图)
                send_feishu_material_sync(metadata, rem_count)
                
                if sys.stdout:
                    print(f"[Worker Success]: {final_title} filed to {city}")

            elif "素材图片超限" in result_msg or "超长过滤策略" in result_msg:
                # 用户铁律：单篇素材严格限制 <= 15 张图，超过直接拦截丢弃并显式通知
                queue_mgr.pop_discard(item_id, result_msg)
                rem_count = queue_mgr.get_remaining_count()
                short_hint = title_hint[:22] + ("..." if len(title_hint) > 22 else "")
                queue_tip = f" (队列剩余 {rem_count} 篇继续处理中)" if rem_count > 0 else ""
                warn_notify = (
                    f"🚫 超长素材已拦截丢弃：《{short_hint}》\n"
                    f"💡 规则：严格限制 ≤ 15 张图，{result_msg}，不予落地入库{queue_tip}"
                )
                send_desktop_notification(warn_notify, title="超长素材拦截 (已丢弃)", status="warning")
                send_feishu_error_sync(title_hint, url, f"超长素材拦截丢弃: {result_msg}")
                if sys.stdout:
                    print(f"[Worker Discard Oversized]: Discarded item {url} ({result_msg}), moving to next...")
                time.sleep(1.0)
                continue

            elif any(k in result_msg for k in ["未能成功解析", "0目录产出", "404", "无法浏览", "获取数据失败", "UNSUPPORTED_PROFILE", "提取小红书作品链接失败", "暂不支持"]):
                # 单篇资源级终态或解析受限（私密笔记/已删除/或缺少免登安全凭据）
                # 关键：这属于单篇笔记自身属性问题，绝非 IP 级风控，严禁触发长达数分钟的全局队头死锁！
                queue_mgr.pop_discard(item_id, result_msg)
                rem_count = queue_mgr.get_remaining_count()
                short_hint = title_hint[:22] + ("..." if len(title_hint) > 22 else "")
                queue_tip = f" (队列剩余 {rem_count} 篇继续处理中)" if rem_count > 0 else ""

                if "UNSUPPORTED_PROFILE" in result_msg or "提取小红书作品链接失败" in result_msg:
                    warn_notify = (
                        f"⚠️ 链接类型不符或非单篇图文笔记：《{short_hint}》\n"
                        f"💡 提示：万能下载器专精单篇图文笔记采集，非图文已跳过{queue_tip}"
                    )
                    send_desktop_notification(warn_notify, title="跳过非单篇笔记", status="warning")
                    send_feishu_error_sync(title_hint, url, f"链接类型不符或非单篇图文作品 ({result_msg[:40]})")
                else:
                    warn_notify = (
                        f"⚠️ 单篇笔记解析受限已移入异常：《{short_hint}》\n"
                        f"💡 原因: 笔记受限/私密或长链缺失Token{queue_tip}"
                    )
                    send_desktop_notification(warn_notify, title="单篇受限已跳过", status="warning")
                    send_feishu_error_sync(title_hint, url, f"单篇笔记解析受限或缺少Token ({result_msg[:40]})")

                if sys.stdout:
                    print(f"[Worker Discard]: Discarded item {url} ({result_msg}), moving to next...")
                # 仅保留拟人微间隔 1.5 秒，立即流转执行队列下一篇！
                time.sleep(1.5)
                continue

            else:
                # 真正的网络中断或频次告警处理：进入阶梯式风控退避冷却
                curr_retries = retry_count + 1
                backoff_sec = DEEP_COOLDOWN_BASE * curr_retries
                queue_mgr.mark_retry(item_id, result_msg, backoff_sec)
                rem_count = queue_mgr.get_remaining_count()

                if curr_retries >= MAX_RETRIES:
                    short_hint = title_hint[:20] + ("..." if len(title_hint) > 20 else "")
                    err_notify = f"❌ 连续多次网络异常，已移入异常待查：《{short_hint}》\n⚠️ 原因: {result_msg[:40]}"
                    send_desktop_notification(err_notify, title="采集异常挂起", status="error")
                    send_feishu_error_sync(title_hint, url, f"连续多次重试失败（网络或限制）: {result_msg[:40]}")
                else:
                    short_hint = title_hint[:20] + ("..." if len(title_hint) > 20 else "")
                    cd_notify = (
                        f"⚠️ 遇到网络波动/频次保护，已启动冷却缓冲\n"
                        f"⏳ 剩余 {rem_count} 篇已安全保存在【待下载队列】，将在 {int(backoff_sec)} 秒后自动续接"
                    )
                    send_desktop_notification(cd_notify, title="冷却缓冲保护中", status="warning")

                if sys.stdout:
                    print(f"[Worker Warning]: {result_msg}, enter cooldown {backoff_sec}s")

        except Exception as ex:
            if sys.stdout:
                print(f"[Worker Loop Exception]: {ex}")
            time.sleep(2.0)


def start_system_tray(queue_mgr: QueueManager, history_set: set):
    """启动轻量系统托盘图标，提供右键快捷菜单与运行感知，无 pystray 时优雅跳过"""
    try:
        import pystray
        from PIL import Image, ImageDraw

        def create_tray_image():
            img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            # 现代科技靛蓝底板
            d.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(14, 116, 144))
            # 绘制白色的 M 标识
            d.polygon([(18, 46), (18, 18), (26, 18), (32, 32), (38, 18), (46, 18), (46, 46), (39, 46), (39, 28), (34, 40), (30, 40), (25, 28), (25, 46)], fill=(255, 255, 255))
            return img

        def on_open_root(icon, item):
            try:
                os.startfile(str(BASE_MATERIAL_DIR))
            except Exception:
                pass

        def on_open_log(icon, item):
            try:
                os.startfile(str(DAEMON_LOG_FILE))
            except Exception:
                pass

        def on_check_status(icon, item):
            rem = queue_mgr.get_remaining_count()
            is_cooling, rem_sec, reason = queue_mgr.is_cooling_down()
            cool_str = f"，风控冷却中剩余 {int(rem_sec)}s" if is_cooling else ""
            msg = f"📊 MaterialHub 运行正常\n· 待下载队列：{rem} 篇{cool_str}\n· 历史已采集：{len(history_set)} 套\n· 日志路径：{DAEMON_LOG_FILE.name}"
            send_desktop_notification(msg, title="素材采集中枢状态", status="info")

        def on_exit(icon, item):
            icon.stop()
            os._exit(0)

        menu = pystray.Menu(
            pystray.MenuItem("📊 查看运行状态", on_check_status),
            pystray.MenuItem("📁 打开素材根目录", on_open_root),
            pystray.MenuItem("📋 打开运行日志", on_open_log),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🚪 退出采集中枢", on_exit)
        )

        icon = pystray.Icon("MaterialHub", create_tray_image(), "MaterialHub 万能素材采集中枢", menu)
        tray_t = threading.Thread(target=icon.run, daemon=True)
        tray_t.start()
        log_daemon("🎨 系统托盘图标启动成功，已常驻任务栏右下角。")
    except Exception as ex:
        log_daemon(f"ℹ️ 托盘组件未启用或初始化跳过: {ex}")


# 主剪贴板监听程序 (Producer Thread)
def main():
    import argparse
    parser = argparse.ArgumentParser(description="MaterialHub 智能采集中枢")
    parser.add_argument("--set-mode", choices=["auto", "manual"], help="设置采集模式：auto (自动识别) 或 manual (手动定向)")
    parser.add_argument("--target", help="手动定向模式下的目标文件夹名称 (如: 民宿合集)")
    parser.add_argument("--get-mode", action="store_true", help="查看当前采集模式与目标目录")
    parser.add_argument("--list-targets", action="store_true", help="列出本地素材库所有可选的目标文件夹")
    args, _ = parser.parse_known_args()

    if args.list_targets:
        folders = []
        if BASE_MATERIAL_DIR.exists():
            for item in sorted(BASE_MATERIAL_DIR.iterdir()):
                if item.is_dir() and not item.name.startswith((".", "_")):
                    folders.append(item.name)
        if sys.stdout:
            print(json.dumps(folders, ensure_ascii=False, indent=2))
        return

    if args.get_mode:
        m = get_current_collector_mode()
        if sys.stdout:
            print(json.dumps(m, ensure_ascii=False, indent=2))
        return

    if args.set_mode:
        target = args.target or ""
        if args.set_mode == "manual" and not target:
            target = "民宿主题素材"
        res = set_collector_mode(args.set_mode, target_folder=target, reason="CLI手动切换")
        mode_desc = f"🎯 手动定向归档（目标：{target}）" if res['mode'] == "manual" else "🤖 全自动智能识别分类"
        if sys.stdout:
            print(f"✔ 采集模式已切换：{mode_desc}")
        send_desktop_notification(f"采集中枢模式已切换为：\n{mode_desc}", title="采集中枢模式切换", status="info")
        return

    if collection_paused():
        return  # AtLogon/Run/Startup must not override an explicit pause.
    # Win32 全局互斥锁，确保同一时刻仅有唯一后台守护进程
    mutex_name = "Global\\XHS_Clipboard_Collector_Daemon_Mutex"
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    h_mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_err = kernel32.GetLastError()
    ERROR_ALREADY_EXISTS = 183
    if last_err == ERROR_ALREADY_EXISTS:
        log_daemon("⚠️ 检测到已有守护实例运行中，本进程原子退出。")
        if sys.stdout:
            print("⚠️ 守护程序已在后台运行中，无需重复拉起。")
        sys.exit(0)

    log_daemon("🚀 万能素材剪贴板采集守护神进程正式就绪并启动。")
    if sys.stdout:
        print("=" * 65)
        print("  🚀 万能素材剪贴板智能采集守护神已就绪 (万能下载器内核 V3.4)")
        print("  · 多平台图文：深度支持小红书与抖音全平台高清无水印原画+文案")
        print("  · 待下载队列：支持连续多次复制链接，全自动暂存排队")
        print("  · 智能风控冷却：拟人化 15~28s 间隔 + 异常阶梯式 60s/120s 自动退避")
        print("  · 智能分流建档：博主主页双向建档入对标库、单篇笔记自动分流地名+秋季硬链接")
        print("  · 飞书即时同频：素材采集通知群同步卡片、未分类暂存与错误报警")
        print("=" * 65)

    history_set = load_history()
    queue_mgr = QueueManager()

    # 启动后台消费线程
    worker_t = threading.Thread(target=queue_worker_loop, args=(queue_mgr, history_set), daemon=True)
    worker_t.start()

    # 启动后台心跳监控线程 (每10秒更新 collector_heartbeat.json)
    def heartbeat_loop():
        while True:
            try:
                is_cooling, _, _ = queue_mgr.is_cooling_down()
                rem = queue_mgr.get_remaining_count()
                status = "cooling" if is_cooling else ("downloading" if rem > 0 else "idle")
                update_heartbeat(status=status, queue_len=rem, history_len=len(history_set))
            except Exception:
                pass
            time.sleep(10.0)

    hb_t = threading.Thread(target=heartbeat_loop, daemon=True)
    hb_t.start()

    # 启动轻量系统托盘 (右键可直接打开目录与查看大盘)
    start_system_tray(queue_mgr, history_set)

    last_clipboard = ""

    while True:
        if collection_paused():
            return
        try:
            current_text = get_clipboard_text()
            if current_text and current_text != last_clipboard:
                last_clipboard = current_text
                
                # 检查是否包含小红书或抖音图文链接 (全面支持单条与批量多条，优先提取精炼短链，剥离追踪参数)
                targets = extract_all_clean_targets(current_text)
                if not targets:
                    single_url = normalize_clean_url(current_text)
                    if single_url:
                        targets = [(single_url, extract_title_hint(current_text), current_text)]
                
                for target_url, title_hint, raw_snippet in targets:
                    if target_url in history_set:
                        if sys.stdout:
                            print(f"[Skip] URL already captured previously: {target_url}")
                    elif is_profile_or_homepage(target_url, raw_snippet):
                        if sys.stdout:
                            print(f"[Benchmark] Detected profile page: {target_url}")
                        is_new, creator = register_benchmark_account(target_url, raw_snippet, title_hint)
                        if is_new:
                            notify_msg = (
                                f"🎯 已自动双向建档至【团建对标库】：《{creator}》\n"
                                f"📊 已同步记入项目《对标账号完整清单》与第二大脑观察库\n"
                                f"💡 点击卡片可直接查看原项目对标大表"
                            )
                            send_desktop_notification(
                                notify_msg,
                                title="对标账号自动建档",
                                status="success",
                                action_target=str(PROJECT_BENCHMARK_FILE)
                            )
                        else:
                            notify_msg = (
                                f"ℹ️ 该博主主页已在【团建对标库】中：《{creator}》\n"
                                f"💡 无需重复登记，对标清单已为最新"
                            )
                            send_desktop_notification(
                                notify_msg,
                                title="对标库已有记录",
                                status="info",
                                action_target=str(PROJECT_BENCHMARK_FILE)
                            )
                    else:
                        # 加入待下载队列
                        added, pos, item = queue_mgr.add(target_url, raw_snippet, title_hint)
                        if added:
                            if sys.stdout:
                                print(f"[Enqueued] Added to queue: {target_url} (Pos: {pos})")
                            
                            # 立即双段反馈：复制瞬间 0.1s 给予确定感反馈，彻底消除黑盒等待焦虑 (无声响)
                            short_hint = title_hint[:22] + ("..." if len(title_hint) > 22 else "")
                            is_cooling, rem_sec, _ = queue_mgr.is_cooling_down()
                            cool_tip = f" (风控冷却剩余 {int(rem_sec)}s)" if is_cooling and rem_sec > 1 else ""
                            notify_msg = (
                                f"📥 已捕获灵感，排队加工中：《{short_hint}》\n"
                                f"⏳ 当前排队: 第 {pos} 篇 (防风控拟人处理中{cool_tip}，完成后自动入库并同步飞书)"
                            )
                            send_desktop_notification(notify_msg, title="采集中枢已捕获", status="info")
                        else:
                            if sys.stdout:
                                print(f"[Skip] Already waiting in pending queue: {target_url}")

        except Exception as e:
            if sys.stdout:
                print(f"[Clipboard Monitor Error]: {e}")
            time.sleep(1.0)
        
        time.sleep(0.5)  # 500ms 极低负载轮询，0.0% CPU 占用


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_daemon(f"FATAL CRASH: {traceback.format_exc()}")
        raise
