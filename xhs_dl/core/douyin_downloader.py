"""Douyin public work downloader backed by a clean system Edge session.

The browser profile is temporary and carries no user login state.  It renders
the public detail page because a plain HTTP client receives an anti-bot shell.
Only the current work's public metadata and media URLs are read.
"""

import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List
from urllib.parse import urlsplit
import requests

from .models import NoteResult
from .media_names import convert_image_file, media_filename, normalize_stat_count
from .v2_downloader import EngineNotReady
from xhs_dl.storage import add_history


@dataclass(frozen=True)
class DouyinMedia:
    url: str
    kind: str
    extension: str


@dataclass(frozen=True)
class DouyinWork:
    source_url: str
    final_url: str
    note_id: str
    title: str
    author: str
    likes: str
    comments: str
    favorites: str
    shares: str
    published_at: str
    topics: List[str]
    media: List[DouyinMedia]

    @classmethod
    def from_page_payload(cls, source_url, payload):
        final_url = str(payload.get("final_url") or source_url)
        match = re.search(r"/(?:note|video)/(\d+)", final_url)
        title = str(payload.get("title") or "").strip()
        topics = list(dict.fromkeys(re.findall(r"#([^\s#]+)", title)))
        media = [
            DouyinMedia(
                url=str(item.get("url") or ""),
                kind=str(item.get("kind") or "image"),
                extension=str(item.get("extension") or "webp").lower().lstrip("."),
            )
            for item in payload.get("media") or []
            if item.get("url")
        ]
        return cls(
            source_url=source_url,
            final_url=final_url,
            note_id=match.group(1) if match else "",
            title=title,
            author=str(payload.get("author") or "").strip(),
            likes=str(payload.get("likes") or "未知"),
            comments=str(payload.get("comments") or "未知"),
            favorites=str(payload.get("favorites") or "未知"),
            shares=str(payload.get("shares") or "未知"),
            published_at=str(payload.get("published_at") or ""),
            topics=topics,
            media=media,
        )

    @staticmethod
    def _safe(value, limit):
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .-")
        return (value or "未知")[:limit]

    @property
    def folder_name(self):
        return (
            f"评{normalize_stat_count(self.comments)}-赞{normalize_stat_count(self.likes)}-"
            f"{self._safe(self.title or '未命名作品', 56)}-"
            f"{self._safe(self.author or '未知作者', 32)}"
        )

    @property
    def copy_text(self):
        topic_text = " ".join(f"#{topic}" for topic in self.topics) or "（无话题）"
        return (
            f"标题：{self.title}\n\n"
            f"正文：\n{self.title or '（正文为空）'}\n\n"
            f"话题：\n{topic_text}\n\n"
            f"作者：{self.author or '未知作者'}\n"
            f"点赞：{self.likes}\n"
            f"评论：{self.comments}\n"
            f"收藏：{self.favorites}\n"
            f"分享：{self.shares}\n"
            f"发布时间：{self.published_at or '未知'}\n\n"
            f"原始链接：{self.source_url}\n"
            f"作品 ID：{self.note_id}\n"
        )


class DouyinBrowserEngine:
    """Extract and download one public Douyin work without a login session."""

    PAGE_SCRIPT = r"""
() => {
  const current = location.href;
  const isNote = /\/note\//.test(current);
  const main = document.querySelector("main") || document.body;
  const player = document.querySelector('[data-e2e="video-detail"] [data-e2e="player-container"]')
    || document.querySelector("main");
  const text = main.innerText || "";
  const meta = document.querySelector('meta[name="description"]')?.content || "";
  let title = (document.title || "").replace(/\s*-\s*抖音\s*$/, "").trim();
  let author = "";
  for (const node of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const value = JSON.parse(node.textContent || "{}");
      const item = value.itemListElement?.find(x => Number(x.position) === 2);
      if (item?.name) { author = String(item.name); break; }
    } catch (_) {}
  }
  if (!author && meta.includes(" - ")) {
    const tail = meta.split(" - ").slice(1).join(" - ");
    author = (tail.match(/^(.*?)于\d{8}发布/) || [])[1] || "";
  }
  if (author && meta.includes(` - ${author}于`)) {
    title = meta.split(` - ${author}于`, 1)[0].trim() || title;
  }
  const read = selector => {
    const node = main.querySelector(selector);
    return node ? (node.innerText || node.textContent || "").trim() : "";
  };
  const unique = new Map();
  if (isNote) {
    for (const image of main.querySelectorAll('img')) {
      const src = image.currentSrc || image.src || "";
      if (!src || !/^https?:/.test(src)) continue;
      const lower = src.toLowerCase();
      if (/avatar|icon|emoji|head|logo|100x100|resize:100|tplv-dy-water/.test(lower)) continue;
      const isNoteCdn = src.includes("aweme-images")
        || ((lower.includes("douyinpic.com") || lower.includes("byteimg.com"))
            && (image.naturalWidth === 0 || image.naturalWidth >= 200));
      if (!isNoteCdn) continue;
      if (!unique.has(src)) unique.set(src, {
        url: src, kind: "image",
        extension: src.includes(".png") ? "png" : src.includes(".jpeg") || src.includes(".jpg") ? "jpg" : "webp"
      });
    }
  } else {
    for (const node of player?.querySelectorAll("video, video source") || []) {
      const src = node.currentSrc || node.src || "";
      if (!/^https?:/.test(src) || unique.has(src) || (node.closest("video")?.mediaKeys)) continue;
      unique.set(src, {url: src, kind: "video", extension: "mp4"});
      break;
    }
  }
  const mediaList = Array.from(unique.values());
  let gate = "";
  let gateReason = "";
  if (!mediaList.length) {
    const pageText = (document.body ? (document.body.innerText || "") : "") + " " + (document.title || "");
    function isVisible(el) {
      if (!el || !el.getBoundingClientRect) return false;
      try {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 40 || rect.height <= 40) return false;
        const style = window.getComputedStyle ? window.getComputedStyle(el) : null;
        if (style && (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || "1") <= 0)) {
          return false;
        }
        return true;
      } catch (_) {
        return false;
      }
    }
    const gateNodes = Array.from(document.querySelectorAll(
      'iframe[src*="captcha"], iframe[src*="verify"], .captcha_verify_container, .secsdk-captcha-drag-wrapper, #captcha_container'
    )).filter(isVisible);
    if (gateNodes.length > 0 || /验证码|人机验证|请完成验证|安全验证|滑块验证/i.test(document.title || "")) {
      gate = "verification";
      gateReason = "抖音触发人机验证/滑块，无法免登解析";
    } else if (/作品不存在|视频不存在|内容不存在|已被删除|暂不可见|私密作品|已设为私密|该作品无法查看/i.test(pageText)) {
      gate = "unavailable";
      gateReason = "抖音作品不存在、已删除或设为私密";
    } else if (/扫码登录|手机号登录|登录后查看更多|一键登录/i.test(pageText)
               && (!title || /^抖音[-—]记录美好生活$|^抖音$/.test(title))) {
      gate = "login";
      gateReason = "抖音要求登录后查看该作品";
    }
  }
  const published = (text.match(/发布时间[：:]\s*([^\n]+)/) || [])[1] || "";
  return {
    final_url: current,
    title,
    author,
    likes: read('[data-e2e="video-player-digg"]') || "未知",
    comments: read('[data-e2e="feed-comment-icon"]') || (text.match(/评论\(([^)]+)\)/) || [])[1] || "未知",
    favorites: read('[data-e2e="video-player-collect"]') || "未知",
    shares: read('[data-e2e="video-player-share"]') || "未知",
    published_at: published.trim(),
    media: mediaList,
    gate,
    gate_reason: gateReason
  };
}
"""

    def __init__(self, timeout=75, image_format="jpg", reusable_browser: bool = False):
        self.timeout = timeout
        self.image_format = image_format
        self.reusable_browser = bool(reusable_browser)
        self._playwright = None
        self._browser = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close any cached reusable browser and Playwright driver safely."""
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass

    def _acquire_browser(self):
        from playwright.sync_api import sync_playwright

        if self._browser is not None:
            try:
                if self._browser.is_connected():
                    return self._browser, False
            except Exception:
                pass
            self.close()

        playwright = sync_playwright().start()
        try:
            browser = playwright.chromium.launch(**self._browser_launch_options())
        except Exception:
            try:
                playwright.stop()
            except Exception:
                pass
            raise
        if self.reusable_browser:
            self._playwright = playwright
            self._browser = browser
            return browser, False
        return (playwright, browser), True

    @staticmethod
    def _browser_launch_options():
        """Use an explicit caller or process proxy for the public Douyin page."""
        options = {"channel": "msedge", "headless": True}
        proxy = os.environ.get("JIANGHU_PROXY_URL", "").strip()
        proxy_source = "JIANGHU_PROXY_URL"
        if not proxy:
            for env_name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
                candidate = os.environ.get(env_name, "").strip()
                if candidate:
                    proxy = candidate
                    proxy_source = env_name
                    break
        if not proxy:
            return options
        parsed = urlsplit(proxy)
        if (parsed.scheme not in {"http", "https", "socks5"}
                or not parsed.hostname or parsed.username is not None
                or parsed.password is not None):
            raise ValueError(f"{proxy_source} must be a valid HTTP(S) or SOCKS5 proxy URL")
        options["proxy"] = {"server": proxy}
        return options

    def _extract_page(self, url):
        try:
            import playwright.sync_api  # noqa: F401
        except ImportError as exc:
            raise EngineNotReady("抖音浏览器组件未安装，请重新安装最新版万能下载器。") from exc

        owned_driver = None
        context = None
        try:
            acquired, should_close = self._acquire_browser()
            if should_close:
                owned_driver, browser = acquired
            else:
                browser = acquired
            context = browser.new_context(
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            result = page.wait_for_function(
                f"() => {{ const work = ({self.PAGE_SCRIPT})(); "
                "return (work.media.length || work.gate) ? work : false; }",
                timeout=min(self.timeout, 40) * 1000,
            )
            payload = result.json_value()
        except Exception as exc:
            detail = str(exc).splitlines()[0][:180]
            raise RuntimeError(f"抖音公开页面解析失败：{detail}") from exc
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass
            if owned_driver is not None:
                try:
                    browser.close()
                except Exception:
                    pass
                try:
                    owned_driver.stop()
                except Exception:
                    pass
        if not payload:
            raise RuntimeError("抖音公开页面已打开，但没有取得当前作品媒体；请稍后重试。")
        if payload.get("gate"):
            raise RuntimeError(str(payload.get("gate_reason") or "抖音公开页面被风控或不可访问"))
        if not payload.get("media"):
            raise RuntimeError("抖音公开页面已打开，但没有取得当前作品媒体；请稍后重试。")
        return payload

    def _download_media(self, media, destination):
        destination = Path(destination)
        partial = destination.with_name(destination.name + ".part")
        response = None
        size = 0
        try:
            response = requests.get(
                media.url,
                timeout=(20, 75),
                stream=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"
                    ),
                    "Referer": "https://www.douyin.com/",
                },
            )
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type.startswith(("text/", "application/json")):
                raise RuntimeError("抖音返回了网页而不是媒体文件，请稍后重试")
            with partial.open("wb") as stream:
                for chunk in response.iter_content(chunk_size=128 * 1024):
                    if chunk:
                        stream.write(chunk)
                        size += len(chunk)
            if size < 200:
                raise RuntimeError("抖音媒体返回内容过小")
            if media.kind != "video":
                from PIL import Image

                try:
                    with Image.open(partial) as img:
                        img.verify()
                except Exception as exc:
                    raise RuntimeError("抖音返回的媒体文件损坏或非有效图片") from exc
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        finally:
            if response is not None:
                response.close()
        if media.kind != "video" and self.image_format != "keep":
            return convert_image_file(destination, self.image_format)
        return destination

    @staticmethod
    def _utf16_units(text: str) -> int:
        return len(str(text or "").encode("utf-16-le", errors="replace")) // 2

    @classmethod
    def _safe_note_dir(cls, output_dir: Path, work: DouyinWork) -> Path:
        """Keep the note folder within Windows MAX_PATH budget while preserving 75 units for filenames."""
        resolved_out = Path(output_dir).expanduser().resolve()
        candidate = resolved_out / work.folder_name
        max_dir_units = 255 - 75
        out_units = cls._utf16_units(str(resolved_out))
        if out_units + 1 + cls._utf16_units(work.folder_name) <= max_dir_units:
            return candidate
        comments = normalize_stat_count(work.comments)
        likes = normalize_stat_count(work.likes)
        tail = work.note_id[-8:] if work.note_id else work._safe(work.author or "未知", 16)
        prefix = f"评{comments}-赞{likes}-"
        suffix = f"-{tail}"
        avail = max(4, max_dir_units - out_units - 1 - cls._utf16_units(prefix) - cls._utf16_units(suffix))
        short_title = work._safe(work.title or "未命名作品", avail)
        while short_title and cls._utf16_units(prefix + short_title + suffix) > max_dir_units - out_units - 1:
            short_title = short_title[:-1]
        folder_name = f"{prefix}{short_title or '作品'}{suffix}"
        return resolved_out / folder_name

    @staticmethod
    def _usable_media(path):
        """Existing files are reusable only when they are non-empty media-sized files."""
        try:
            return Path(path).is_file() and Path(path).stat().st_size >= 200
        except OSError:
            return False

    def download_one(self, url, output_dir):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        work = DouyinWork.from_page_payload(url, self._extract_page(url))
        note_dir = self._safe_note_dir(output_dir, work)
        note_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for index, media in enumerate(work.media, 1):
            extension = (
                self.image_format
                if media.kind != "video" and self.image_format != "keep"
                else media.extension
            )
            destination = note_dir / media_filename(
                index - 1,
                work.title,
                extension,
                is_video=media.kind == "video",
            )
            if not self._usable_media(destination):
                downloaded = note_dir / media_filename(
                    index - 1,
                    work.title,
                    media.extension,
                    is_video=media.kind == "video",
                )
                destination = self._download_media(media, downloaded)
            saved.append(destination)
        (note_dir / "文案.txt").write_text(work.copy_text, encoding="utf-8-sig")
        add_history(url, work.note_id, work.title, str(note_dir.resolve()))
        videos = [item for item in work.media if item.kind == "video"]
        images = [item for item in work.media if item.kind != "video"]
        return NoteResult(
            url=url,
            success=True,
            note_id=work.note_id,
            title=work.title,
            author=work.author,
            note_type="video" if videos else "normal",
            save_dir=str(note_dir),
            image_count=len(images),
            image_success=len(images),
            desc=work.title,
            topics=" ".join(work.topics),
            engine="douyin-edge",
            media_format=", ".join(sorted({path.suffix.lstrip(".").upper() for path in saved})),
        )
