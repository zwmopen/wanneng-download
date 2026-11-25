"""Unified topmost browser focus + Windows desktop toast + Feishu notification dispatcher."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

SHARED_NOTIFY_PY = Path(r"D:\AICode\AI\skills\技能包\技能\shared-notification\scripts\notify.py")
SHARED_FEISHU_PY = Path(r"D:\AICode\AI\skills\技能包\技能\shared-notification\scripts\feishu_notify.py")
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.json"

_COOLDOWN_LOCK = threading.Lock()
_LAST_SENT: Dict[str, float] = {}


def _load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, str(path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_notification_config(config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    candidates = []
    if config_path:
        candidates.append(Path(config_path).expanduser())
    env_cfg = os.environ.get("MATERIAL_HUB_CONFIG", "").strip()
    if env_cfg:
        candidates.append(Path(env_cfg).expanduser())
    candidates.append(DEFAULT_CONFIG_PATH)
    for cand in candidates:
        if cand.is_file():
            try:
                data = json.loads(cand.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    return data.get("notification") if isinstance(data.get("notification"), dict) else {}
            except (OSError, ValueError):
                continue
    return {}


def _play_attention_beep(status: str) -> None:
    if os.name != "nt" or status not in {"warning", "error"}:
        return
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
    except Exception:
        pass


def send_desktop_toast(
    title: str,
    message: str,
    *,
    status: str = "info",
    action_target: str = "",
    duration_ms: int = 5500,
    enabled: bool = True,
) -> Dict[str, Any]:
    if not enabled:
        return {"sent": False, "channel": "disabled", "reason": "disabled"}

    _play_attention_beep(status)

    if SHARED_NOTIFY_PY.is_file():
        try:
            mod = _load_module(SHARED_NOTIFY_PY, "xhs_dl_shared_notify")
            if mod is not None and callable(getattr(mod, "notify", None)):
                res = mod.notify(
                    str(message or "")[:240],
                    title=str(title or "万能采集器")[:60],
                    status=status,
                    app_name="万能采集器",
                    position="BottomRight",
                    duration_ms=int(duration_ms),
                    icon_key="download",
                    action_target=str(action_target or ""),
                    action_label="打开目录" if action_target else "查看状态",
                    wait=False,
                )
                if res:
                    return {"sent": True, "channel": "shared-notification"}
        except Exception as exc:
            last_err = str(exc)
        else:
            last_err = ""
    else:
        last_err = ""

    if os.name == "nt":
        try:
            clean_title = str(title or "万能采集器").replace("'", " ").replace('"', " ").replace("\n", " ")[:50]
            clean_msg = str(message or "").replace("'", " ").replace('"', " ").replace("\n", " ")[:160]
            ps_cmd = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null; "
                "$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                "$xml = [xml]$template.GetXml(); "
                "$nodes = $xml.GetElementsByTagName('text'); "
                f"$nodes[0].InnerText = '{clean_title}'; "
                f"$nodes[1].InnerText = '{clean_msg}'; "
                "$doc = [Windows.Data.Xml.Dom.XmlDocument]::new(); "
                "$doc.LoadXml($xml.OuterXml); "
                "$toast = [Windows.UI.Notifications.ToastNotification]::new($doc); "
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe').Show($toast)"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                check=False,
                timeout=6,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return {"sent": True, "channel": "winrt-toast"}
        except Exception as exc:
            last_err = str(exc)

    return {"sent": False, "channel": "none", "error": last_err or "toast_unavailable"}


def _send_feishu_webhook(webhook_url: str, title: str, text: str) -> Dict[str, Any]:
    import requests

    url = str(webhook_url or "").strip()
    try:
        resp = requests.post(
            url,
            json={"msg_type": "text", "content": {"text": f"【{title}】\n{text}"}},
            timeout=10,
        )
        data = resp.json() if resp.content else {}
        code = data.get("code", data.get("StatusCode", 0)) if isinstance(data, dict) else -1
        ok = resp.status_code == 200 and code == 0
        return {"sent": ok, "channel": "feishu-webhook", "result": data}
    except Exception as exc:
        return {"sent": False, "channel": "feishu-webhook", "error": str(exc)[:240]}


def _send_feishu_openapi(
    app_id: str,
    app_secret: str,
    chat_target: str,
    title: str,
    text: str,
) -> Dict[str, Any]:
    import requests

    target = str(chat_target or "").strip()
    try:
        tok_resp = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": str(app_id).strip(), "app_secret": str(app_secret).strip()},
            timeout=10,
        )
        tok_data = tok_resp.json() if tok_resp.content else {}
        token = str((tok_data or {}).get("tenant_access_token") or "").strip()
        if not token:
            return {
                "sent": False,
                "channel": "feishu-openapi",
                "target": target,
                "error": (tok_data or {}).get("msg") or "获取飞书 tenant_access_token 失败",
            }
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        chat_id = target if target.startswith("oc_") else ""
        if not chat_id:
            chats_resp = requests.get(
                "https://open.feishu.cn/open-apis/im/v1/chats?page_size=100",
                headers=headers,
                timeout=10,
            )
            chats_data = chats_resp.json() if chats_resp.content else {}
            items = ((chats_data or {}).get("data") or {}).get("items") or []
            for item in items:
                if isinstance(item, dict) and str(item.get("name") or "").strip() == target:
                    chat_id = str(item.get("chat_id") or "").strip()
                    break
            if not chat_id and target:
                for item in items:
                    if isinstance(item, dict) and target in str(item.get("name") or ""):
                        chat_id = str(item.get("chat_id") or "").strip()
                        break
            if not chat_id and items and isinstance(items[0], dict):
                chat_id = str(items[0].get("chat_id") or "").strip()
        if not chat_id:
            return {"sent": False, "channel": "feishu-openapi", "error": f"未找到目标飞书群：{target or '未填写群名/群ID'}"}
        msg_resp = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            headers=headers,
            json={
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": f"【{title}】\n{text}"}, ensure_ascii=False),
            },
            timeout=10,
        )
        msg_data = msg_resp.json() if msg_resp.content else {}
        ok = msg_resp.status_code == 200 and isinstance(msg_data, dict) and msg_data.get("code") == 0
        return {"sent": ok, "channel": "feishu-openapi", "target": chat_id, "result": msg_data}
    except Exception as exc:
        return {"sent": False, "channel": "feishu-openapi", "target": target, "error": str(exc)[:240]}


def send_feishu_notification(
    title: str,
    text: str,
    *,
    target: str = "",
    app_id: str = "",
    app_secret: str = "",
    webhook_url: str = "",
    config_path: Optional[str | Path] = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    if not enabled:
        return {"sent": False, "channel": "disabled", "reason": "disabled"}

    notify_cfg = _load_notification_config(config_path)
    feishu_cfg = notify_cfg.get("feishu") if isinstance(notify_cfg.get("feishu"), dict) else {}
    eff_webhook = str(webhook_url or "").strip() or str(feishu_cfg.get("webhook_url") or "").strip()
    eff_app_id = str(app_id or "").strip()
    eff_app_secret = str(app_secret or "").strip()
    has_explicit_cfg = bool(eff_webhook or (eff_app_id and eff_app_secret))
    if not feishu_cfg.get("enabled", True) and not target and not has_explicit_cfg:
        return {"sent": False, "channel": "disabled", "reason": "feishu_config_disabled"}

    chat_target = (
        str(target or "").strip()
        or str(feishu_cfg.get("target_chat_id") or "").strip()
        or str(feishu_cfg.get("target_chat_name") or "").strip()
        or "素材采集通知群"
    )
    msg_title = str(title or "万能采集器通知")
    msg_text = str(text or "")

    # Priority 1: Direct group bot webhook
    if eff_webhook:
        return _send_feishu_webhook(eff_webhook, msg_title, msg_text)

    # Priority 2: User-supplied App ID + App Secret via Feishu OpenAPI
    if eff_app_id and eff_app_secret:
        return _send_feishu_openapi(eff_app_id, eff_app_secret, chat_target, msg_title, msg_text)

    # Priority 3: Local shared-notification script on configured machine
    script_raw = str(feishu_cfg.get("feishu_notify_script") or "").strip()
    script_path = Path(script_raw) if script_raw and Path(script_raw).is_file() else SHARED_FEISHU_PY
    if script_path.is_file():
        try:
            mod = _load_module(script_path, "xhs_dl_feishu_notify")
            if mod is not None and callable(getattr(mod, "send_feishu_msg", None)):
                res = mod.send_feishu_msg(chat_target, msg_text, title=msg_title)
                ok = isinstance(res, dict) and res.get("text_code") == 0
                return {"sent": ok, "target": chat_target, "result": res}
        except Exception as exc:
            return {"sent": False, "target": chat_target, "error": str(exc)[:240]}

    # Priority 4: Config file fallback App ID + App Secret via Feishu OpenAPI
    cfg_app_id = str(feishu_cfg.get("app_id") or "").strip()
    cfg_app_secret = str(feishu_cfg.get("app_secret") or "").strip()
    if cfg_app_id and cfg_app_secret:
        return _send_feishu_openapi(cfg_app_id, cfg_app_secret, chat_target, msg_title, msg_text)

    return {
        "sent": False,
        "channel": "unconfigured",
        "error": "未配置飞书机器人：请在设置中填写群机器人 Webhook 或企业应用 App ID 与密钥",
    }


def dispatch_workbench_notification(
    event_kind: str,
    title: str,
    message: str,
    *,
    settings: Optional[Dict[str, Any]] = None,
    action_target: str = "",
    platform: str = "douyin",
    dedup_key: str = "",
    cooldown_seconds: float = 90.0,
    force: bool = False,
    bring_verify_fn: Optional[Callable[..., int]] = None,
) -> Dict[str, Any]:
    now = time.monotonic()
    if not force and dedup_key:
        with _COOLDOWN_LOCK:
            last = _LAST_SENT.get(dedup_key)
            if last is not None and (now - last) < max(0.0, float(cooldown_seconds)):
                return {"skipped": True, "reason": "cooldown", "dedup_key": dedup_key}
            _LAST_SENT[dedup_key] = now

    sw = (settings or {}).get("software") if isinstance((settings or {}).get("software"), dict) else {}
    dl = (settings or {}).get("download") if isinstance((settings or {}).get("download"), dict) else {}
    cfg_path = dl.get("auto_ingest_config_path") or None

    notify_desktop = bool(sw.get("notify_desktop_toast", True))
    notify_feishu = bool(sw.get("notify_feishu", True))
    notify_complete = bool(sw.get("notify_on_complete", True))
    auto_topmost = bool(sw.get("auto_topmost_verify_window", True))
    feishu_target = str(sw.get("notify_feishu_target") or "").strip()
    feishu_app_id = str(sw.get("notify_feishu_app_id") or "").strip()
    feishu_app_secret = str(sw.get("notify_feishu_app_secret") or "").strip()
    feishu_webhook = str(sw.get("notify_feishu_webhook") or "").strip()

    if event_kind == "completed" and not notify_complete and not force:
        return {"skipped": True, "reason": "completed_notify_disabled"}

    windows_focused = 0
    if event_kind in {"verification", "login"} and auto_topmost and callable(bring_verify_fn):
        try:
            windows_focused = int(bring_verify_fn(topmost=True) or 0)
        except Exception:
            windows_focused = 0

    toast_status = "warning" if event_kind in {"verification", "login"} else ("error" if event_kind == "error" else "success")
    desktop_res = send_desktop_toast(
        title,
        message,
        status=toast_status,
        action_target=action_target,
        enabled=(notify_desktop or force),
    )
    feishu_extra: Dict[str, Any] = {}
    if feishu_app_id:
        feishu_extra["app_id"] = feishu_app_id
    if feishu_app_secret:
        feishu_extra["app_secret"] = feishu_app_secret
    if feishu_webhook:
        feishu_extra["webhook_url"] = feishu_webhook
    feishu_res = send_feishu_notification(
        title,
        message,
        target=feishu_target,
        config_path=cfg_path,
        enabled=(notify_feishu or force),
        **feishu_extra,
    )
    return {
        "event": event_kind,
        "platform": platform,
        "windows_focused": windows_focused,
        "desktop": desktop_res,
        "feishu": feishu_res,
    }
