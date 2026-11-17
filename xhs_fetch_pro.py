#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书单篇笔记解析（2026-11 版，免登录）
========================================
依据公开逆向资料（YaKun9/media-parser 文档）实现的三处关键修正：

1. App 分享短链在 PC UA 下会被判非移动环境 → 双 UA 降级（PC 优先，失败回退移动端）
2. `window.__INITIAL_STATE__` 里注入了 `new Map([])` / `new Set(...)` / `new Date(...)`
   和孤立 `undefined` → 直接 json.loads 必炸，需先做正则清洗
3. `xsec_token` 与 `xsec_source` 必须原样保留，清洗掉任何一个都会被安全网关打回 404

用法:
    python xhs_fetch_pro.py <笔记链接或短链>
    python xhs_fetch_pro.py <链接> --json
"""
import json
import re
import sys
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests

UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
UA_M = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

# 必须原样保留的签名参数（少一个就会被 404/sec_ 拦）
KEEP_PARAMS = ("xsec_token", "xsec_source", "source", "xhsshare", "app_platform", "share_from_user_hidden")


class XhsFetchError(Exception):
    def __init__(self, msg, terminal=False):
        super().__init__(msg)
        self.terminal = terminal  # True = 笔记本身没了，重试无意义


def clean_url(url: str) -> str:
    """只保留签名相关参数，剔除 apptime/share_id 等无关追踪参数。"""
    p = urlparse(url.strip())
    qs = parse_qs(p.query, keep_blank_values=True)
    kept = [(k, v[0]) for k, v in qs.items() if k in KEEP_PARAMS]
    return urlunparse(p._replace(query=urlencode(kept, safe="="), fragment=""))


def sanitize_ssr(state_json: str) -> str:
    """清洗 SSR 注水里的 JS 表达式，使其可被 json.loads。"""
    s = state_json
    s = re.sub(r"\bundefined\b", "null", s)
    s = re.sub(r"new\s+Map\s*\([^)]*\)", "{}", s)
    s = re.sub(r"new\s+Set\s*\([^)]*\)", "[]", s)
    s = re.sub(r"new\s+Date\s*\([^)]*\)", "null", s)
    return s


def extract_state(html: str):
    for pat in (r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})</script>",
                r"window\.__INITIAL_STATE__\s*=\s*(\{.*\})"):
        m = re.search(pat, html, re.DOTALL)
        if not m:
            continue
        raw = sanitize_ssr(m.group(1))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 兜底：把孤立 JS 值再宽松清一遍
            raw2 = re.sub(r",\s*null\s*:", ',"":', raw)
            try:
                return json.loads(raw2)
            except Exception:
                continue
    return None


def pick_note(state: dict, note_id: str = ""):
    """三种页面结构依次尝试：PC noteDetailMap → 移动 H5 noteData.data.noteData → 兜底。"""
    if not state:
        return None
    note_map = (state.get("note") or {}).get("noteDetailMap") or {}
    first_id = (state.get("note") or {}).get("firstNoteId") or note_id
    item = note_map.get(first_id) or {}
    note = item.get("note") if isinstance(item, dict) else None
    if isinstance(note, dict) and note:
        return note
    md = (state.get("noteData") or {}).get("data") or {}
    note = md.get("noteData")
    if isinstance(note, dict) and note:
        return note
    return (state.get("noteData") or {}).get("note") or (state.get("note") or {}).get("note") or None


def _first_url(img):
    if isinstance(img, str):
        return img
    if isinstance(img, dict):
        for k in ("urlDefault", "urlPre", "url", "url_default"):
            v = img.get(k)
            if v:
                return v
        info = img.get("infoList") or []
        for it in info:
            if it.get("url"):
                return it["url"]
    return None


def normalize(note: dict) -> dict:
    title = note.get("title") or ""
    desc = note.get("desc") or ""
    imgs = []
    for it in (note.get("imageList") or note.get("image_list") or []):
        u = _first_url(it)
        if u:
            imgs.append(u)
    video = ""
    v = note.get("video") or {}
    if isinstance(v, dict):
        media = ((v.get("media") or {}).get("stream") or {}).get("h264") or []
        streams = [s for s in media if s.get("streamType") not in (259, 309)] or media
        if streams:
            video = streams[0].get("masterUrl") or ""
    user = note.get("user") or {}
    interact = note.get("interactInfo") or note.get("interact_info") or {}
    return {
        "note_id": note.get("noteId") or note.get("note_id") or "",
        "title": title.strip(),
        "desc": desc.strip(),
        "author": user.get("nickname") or user.get("nickName") or "",
        "images": imgs,
        "image_count": len(imgs),
        "video": video,
        "likes": interact.get("likedCount") or interact.get("liked_count") or "",
        "type": note.get("type") or ("video" if video else "normal"),
    }


def fetch(url: str, timeout=15, referer="https://www.xiaohongshu.com/"):
    url = clean_url(url)
    errors = []
    for tag, ua in (("PC", UA_PC), ("MOBILE", UA_M)):
        headers = {"User-Agent": ua, "Referer": referer,
                   "Accept-Language": "zh-CN,zh;q=0.9",
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        try:
            r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        except requests.RequestException as e:
            errors.append(f"{tag}: 网络异常 {type(e).__name__}")
            continue

        final = r.url
        if r.status_code == 404:
            errors.append(f"{tag}: HTTP 404")
            continue
        if "/404/sec_" in final or "undertake_note_error" in final:
            errors.append(f"{tag}: 被安全网关拦截 → {final[:80]}")
            continue
        if "/login" in final:
            errors.append(f"{tag}: 跳登录页 → {final[:80]}")
            continue
        if final.rstrip("/") == "https://www.xiaohongshu.com":
            errors.append(f"{tag}: 被重定向回首页（笔记失效）")
            continue

        state = extract_state(r.text)
        note = pick_note(state, re.search(r"/(?:explore|item)/([0-9a-f]{24})", url).group(1)
                         if re.search(r"/(?:explore|item)/([0-9a-f]{24})", url) else "")
        if note:
            data = normalize(note)
            data["via"] = tag
            data["final_url"] = final
            return data
        errors.append(f"{tag}: 页面无笔记数据（HTTP {r.status_code}, {len(r.text)} 字节）")

    raise XhsFetchError(" | ".join(errors), terminal=all(("404" in e or "首页" in e or "安全网关" in e) for e in errors))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    url = sys.argv[1]
    as_json = "--json" in sys.argv
    t0 = time.time()
    try:
        d = fetch(url)
    except XhsFetchError as e:
        if as_json:
            print(json.dumps({"ok": False, "error": str(e), "terminal": e.terminal}, ensure_ascii=False))
        else:
            print("✗ 解析失败")
            for line in str(e).split(" | "):
                print("   ", line)
        return 2
    if as_json:
        print(json.dumps({"ok": True, "data": d}, ensure_ascii=False))
    else:
        print("✓ 解析成功 (via %s, %.1fs)" % (d["via"], time.time() - t0))
        print("  标题:", d["title"][:60])
        print("  作者:", d["author"], "| 点赞:", d["likes"], "| 类型:", d["type"])
        print("  图片:", d["image_count"], "张")
        if d["images"]:
            print("  首图:", d["images"][0][:100])
        print("  文案:", d["desc"][:80].replace("\n", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
