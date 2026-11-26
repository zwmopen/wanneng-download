"""Cookie-free Chinese short-video & AI video downloader engine.

Ported from jiuhunwl/short_videos pure-HTTP parsers into native Python so
Kuaishou, Weibo, Toutiao, Pipixia, Pipigx, Zuiyou, Doubao AI, and Jimeng AI
links work out of the box with unified naming, 文案.txt, and local history.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit

import requests

from .media_names import convert_image_file, media_filename, normalize_stat_count, safe_title
from .models import NoteResult
from .platforms import detect_cn_subplatform
from xhs_dl.storage import add_history


DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)


@dataclass(frozen=True)
class CnMediaItem:
    url: str
    kind: str = "video"  # "video" | "image"
    extension: str = "mp4"
    referer: str = ""


@dataclass(frozen=True)
class CnWork:
    platform: str
    platform_label: str
    source_url: str
    work_id: str
    title: str
    author: str
    likes: str = "未知"
    published_at: str = ""
    media: List[CnMediaItem] = field(default_factory=list)

    @property
    def folder_name(self) -> str:
        title_part = safe_title(self.title or "未命名作品", 56)
        author_part = safe_title(self.author or "未知作者", 28)
        likes_part = normalize_stat_count(self.likes)
        return f"[{self.platform_label}]-赞{likes_part}-{title_part}-{author_part}"

    @property
    def copy_text(self) -> str:
        topics = list(dict.fromkeys(re.findall(r"#([^\s#]+)", self.title or "")))
        topic_text = " ".join(f"#{t}" for t in topics) or "（无话题）"
        return (
            f"标题：{self.title or '未命名作品'}\n\n"
            f"正文：\n{self.title or '（正文为空）'}\n\n"
            f"话题：\n{topic_text}\n\n"
            f"作者：{self.author or '未知作者'}\n"
            f"点赞：{self.likes}\n"
            f"发布时间：{self.published_at or '未知'}\n"
            f"来源平台：{self.platform_label}\n\n"
            f"原始链接：{self.source_url}\n"
            f"作品 ID：{self.work_id}\n"
        )


def _to_https(url: str) -> str:
    text = str(url or "").strip()
    if text.startswith("//"):
        return "https:" + text
    if text.startswith("http://"):
        return "https://" + text[7:]
    return text


def _guess_ext(url: str, default: str = "jpg") -> str:
    path = urlsplit(url).path.lower()
    for ext in (".mp4", ".mov", ".m4v", ".webm", ".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ext.lstrip(".")
    return default


def _format_ts(ts) -> str:
    try:
        val = int(ts)
        if val > 10**12:
            val //= 1000
        if val > 0:
            tz_cn = datetime.timezone(datetime.timedelta(hours=8))
            return datetime.datetime.fromtimestamp(val, tz=tz_cn).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return ""


class CnShortVideoEngine:
    """Download public works from Kuaishou, Weibo, Toutiao, Pipixia, Pipigx, Zuiyou, Doubao & Jimeng."""

    def __init__(self, timeout: int = 60, image_format: str = "keep"):
        self.timeout = timeout
        self.image_format = image_format

    @staticmethod
    def _proxies():
        proxy = os.environ.get("JIANGHU_PROXY_URL", "").strip()
        if not proxy:
            for env_name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
                candidate = os.environ.get(env_name, "").strip()
                if candidate:
                    proxy = candidate
                    break
        return {"http": proxy, "https": proxy} if proxy else None

    def _resolve_redirect(self, url: str, ua: str = DESKTOP_UA) -> str:
        resp = requests.get(
            url,
            headers={"User-Agent": ua},
            allow_redirects=True,
            timeout=(8, 15),
            stream=True,
            proxies=self._proxies(),
        )
        try:
            return str(resp.url or url)
        finally:
            resp.close()

    def parse(self, url: str) -> CnWork:
        sub = detect_cn_subplatform(url)
        dispatch = {
            "kuaishou": self._parse_kuaishou,
            "weibo": self._parse_weibo,
            "toutiao": self._parse_toutiao,
            "pipixia": self._parse_pipixia,
            "pipigx": self._parse_pipigx,
            "zuiyou": self._parse_zuiyou,
            "doubao": self._parse_doubao,
            "jimeng": self._parse_jimeng,
        }
        handler = dispatch.get(sub)
        if handler is None:
            raise ValueError(f"暂不支持该国内平台链接：{url}")
        return handler(url)

    # ---------- 1. 快手 ----------
    def _parse_kuaishou(self, url: str) -> CnWork:
        final_url = self._resolve_redirect(url, ua=MOBILE_UA)
        resp = requests.get(
            final_url,
            headers={"User-Agent": MOBILE_UA, "Accept-Language": "zh-CN,zh;q=0.9"},
            timeout=(8, 15),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        html = resp.text

        m = re.search(r"window\.INIT_STATE\s*=\s*(.*?)</script>", html, re.S)
        if not m:
            raise RuntimeError("快手页面未找到 INIT_STATE 数据，可能触发风控或链接已失效")
        raw_json = m.group(1).strip().rstrip(";")
        try:
            state = json.loads(raw_json)
        except json.JSONDecodeError:
            cleaned = raw_json.replace(
                '"{"err_msg":"launchApplication:fail"}"', '"launchApplication:fail"'
            ).replace(
                '"{"err_msg":"system:access_denied"}"', '"system:access_denied"'
            )
            state = json.loads(cleaned)

        photo = None
        if isinstance(state, dict):
            for val in state.values():
                if isinstance(val, dict) and isinstance(val.get("photo"), dict):
                    photo = val["photo"]
                    break
        if not photo:
            raise RuntimeError("快手页面未解析到作品信息")

        title = str(photo.get("caption") or "").strip()
        author = str(photo.get("userName") or "").strip()
        work_id = str(photo.get("photoId") or photo.get("id") or "")
        likes = str(photo.get("likeCount") if photo.get("likeCount") is not None else "未知")
        pub = _format_ts(photo.get("timestamp"))
        media: List[CnMediaItem] = []

        atlas = ((photo.get("ext_params") or {}).get("atlas") or {}).get("list") or []
        if isinstance(atlas, list) and atlas:
            for item in atlas:
                path = str(item or "").lstrip("/")
                if path:
                    img_url = path if path.startswith("http") else f"https://tx2.a.yximgs.com/{path}"
                    media.append(CnMediaItem(url=img_url, kind="image", extension=_guess_ext(img_url, "jpg"), referer="https://www.kuaishou.com/"))
        elif photo.get("photoType") == "SINGLE_PICTURE" or photo.get("singlePicture") is True:
            covers = photo.get("coverUrls") or []
            if covers and isinstance(covers[0], dict) and covers[0].get("url"):
                img_url = _to_https(covers[0]["url"])
                media.append(CnMediaItem(url=img_url, kind="image", extension=_guess_ext(img_url, "jpg"), referer="https://www.kuaishou.com/"))
        else:
            video_url = ""
            mv_urls = photo.get("mainMvUrls") or []
            if isinstance(mv_urls, list) and mv_urls and isinstance(mv_urls[0], dict):
                video_url = _to_https(mv_urls[0].get("url") or "")
            if not video_url:
                try:
                    video_url = _to_https(photo["manifest"]["adaptationSet"][0]["representation"][0]["url"])
                except Exception:
                    video_url = ""
            if video_url:
                media.append(CnMediaItem(url=video_url, kind="video", extension="mp4", referer="https://www.kuaishou.com/"))

        if not media:
            raise RuntimeError("快手作品未提取到有效视频或图集直链")
        return CnWork("kuaishou", "快手", url, work_id, title, author, likes, pub, media)

    # ---------- 2. 微博视频 ----------
    def _parse_weibo(self, url: str) -> CnWork:
        target = url
        if "t.cn/" in target:
            target = self._resolve_redirect(target, ua=DESKTOP_UA)
        parsed = urlsplit(target)
        query = parse_qs(parsed.query)
        video_id = (query.get("fid") or [""])[0]
        if not video_id:
            m = re.search(r"weibo\.com/tv/(?:show|v)/([^?&#/]+)", target)
            if m:
                video_id = m.group(1)
        if not video_id:
            raise RuntimeError("未能从微博链接中提取视频 ID（请使用微博视频分享链接）")

        page_path = f"/tv/show/{video_id}"
        api_url = f"https://weibo.com/tv/api/component?{urlencode({'page': page_path})}"
        payload = {"Component_Play_Playinfo": {"oid": video_id}}
        resp = requests.post(
            api_url,
            data={"data": json.dumps(payload, ensure_ascii=False)},
            headers={
                "User-Agent": DESKTOP_UA,
                "Referer": f"https://weibo.com{page_path}",
                "Origin": "https://weibo.com",
            },
            timeout=(8, 20),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        data = resp.json()
        info = ((data.get("data") or {}).get("Component_Play_Playinfo") or {})
        urls_map = info.get("urls") or {}
        if not isinstance(urls_map, dict) or not urls_map:
            raise RuntimeError("微博接口未返回视频直链，可能需要登录态或链接不支持")

        def _priority(label: str) -> int:
            for idx, key in enumerate(("360P", "480P", "720P", "1080P", "2K", "4K"), 1):
                if key in label.upper():
                    return idx
            return 0

        best_label = max(urls_map.keys(), key=_priority)
        best_url = _to_https(str(urls_map[best_label] or ""))
        if not best_url:
            raise RuntimeError("微博视频直链为空")
        return CnWork(
            platform="weibo",
            platform_label="微博",
            source_url=url,
            work_id=video_id,
            title=str(info.get("title") or info.get("text") or "").strip(),
            author=str(info.get("author") or info.get("nickname") or "").strip(),
            likes=str(info.get("attitudes_count") or "未知"),
            media=[CnMediaItem(url=best_url, kind="video", extension="mp4", referer="https://weibo.com/")],
        )

    # ---------- 3. 今日头条 ----------
    def _parse_toutiao(self, url: str) -> CnWork:
        final_url = self._resolve_redirect(url, ua=DESKTOP_UA)
        m = re.search(r"(?:video/|group/|item/)(\d+)", final_url) or re.search(r"(\d{10,})", final_url)
        if not m:
            raise RuntimeError("无法从今日头条链接提取视频 ID")
        vid = m.group(1)
        resp = requests.get(
            f"https://www.toutiao.com/video/{vid}",
            headers={"User-Agent": DESKTOP_UA},
            timeout=(8, 20),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        match = re.search(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', resp.text, re.S)
        if not match:
            raise RuntimeError("今日头条页面未找到 RENDER_DATA，可能受风控限制")
        render_data = json.loads(unquote(match.group(1)))
        data = render_data.get("data") or {}
        init_video = data.get("initialVideo") or {}
        video_list = (init_video.get("videoPlayInfo") or {}).get("video_list") or []
        video_url = ""
        if isinstance(video_list, list) and video_list:
            for item in reversed(video_list):
                if isinstance(item, dict) and item.get("main_url"):
                    video_url = _to_https(str(item["main_url"]))
                    break
        if not video_url:
            raise RuntimeError("今日头条未提取到有效视频直链")
        user_info = (init_video.get("itemCell") or {}).get("userInfo") or {}
        return CnWork(
            platform="toutiao",
            platform_label="今日头条",
            source_url=url,
            work_id=str(data.get("itemId") or vid),
            title=str(init_video.get("title") or "").strip(),
            author=str(user_info.get("name") or "").strip(),
            media=[CnMediaItem(url=video_url, kind="video", extension="mp4", referer="https://www.toutiao.com/")],
        )

    # ---------- 4. 皮皮虾 ----------
    def _parse_pipixia(self, url: str) -> CnWork:
        final_url = self._resolve_redirect(url, ua=DESKTOP_UA)
        m = re.search(r"item/(\d+)", final_url)
        if not m:
            raise RuntimeError("无法从皮皮虾链接中提取作品 ID")
        cell_id = m.group(1)
        api_url = f"https://h5.pipix.com/bds/cell/cell_h5_comment/?count=5&aid=1319&app_name=super&cell_id={cell_id}"
        resp = requests.get(api_url, headers={"User-Agent": DESKTOP_UA}, timeout=(8, 15), proxies=self._proxies())
        resp.raise_for_status()
        data = resp.json()
        comments = (data.get("data") or {}).get("cell_comments") or []
        item = None
        for entry in comments:
            cand = ((entry or {}).get("comment_info") or {}).get("item")
            if isinstance(cand, dict):
                item = cand
                break
        if not item:
            raise RuntimeError("皮皮虾接口未返回作品详情")

        media: List[CnMediaItem] = []
        v_list = ((item.get("video") or {}).get("video_high") or {}).get("url_list") or []
        if v_list and isinstance(v_list[0], dict) and v_list[0].get("url"):
            media.append(CnMediaItem(url=_to_https(v_list[0]["url"]), kind="video", extension="mp4"))
        multi_images = (item.get("note") or {}).get("multi_image") or []
        for img in multi_images:
            u_list = (img or {}).get("url_list") or []
            if u_list and isinstance(u_list[0], dict) and u_list[0].get("url"):
                u = _to_https(u_list[0]["url"])
                media.append(CnMediaItem(url=u, kind="image", extension=_guess_ext(u, "jpg")))
        if not media:
            raise RuntimeError("皮皮虾作品未提取到视频或图片")
        return CnWork(
            platform="pipixia",
            platform_label="皮皮虾",
            source_url=url,
            work_id=cell_id,
            title=str(item.get("content") or "").strip(),
            author=str((item.get("author") or {}).get("name") or "").strip(),
            media=media,
        )

    # ---------- 5. 皮皮搞笑 ----------
    def _parse_pipigx(self, url: str) -> CnWork:
        final_url = self._resolve_redirect(url, ua=DESKTOP_UA)
        query = parse_qs(urlsplit(final_url).query)
        pid = (query.get("pid") or [""])[0]
        mid = (query.get("mid") or [""])[0]
        if not pid or not mid:
            raise RuntimeError("无法从皮皮搞笑链接提取 pid/mid 参数")
        resp = requests.post(
            "https://h5.pipigx.com/ppapi/share/fetch_content",
            json={"pid": int(pid), "mid": int(mid), "type": "post"},
            headers={"User-Agent": DESKTOP_UA, "Content-Type": "application/json"},
            timeout=(8, 15),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        post = (resp.json().get("data") or {}).get("post") or {}
        videos = post.get("videos") or {}
        video_url = ""
        if isinstance(videos, dict):
            for v in videos.values():
                if isinstance(v, dict) and v.get("url"):
                    video_url = _to_https(str(v["url"]))
                    break
        elif isinstance(videos, list):
            for v in videos:
                if isinstance(v, dict) and v.get("url"):
                    video_url = _to_https(str(v["url"]))
                    break
        if not video_url:
            raise RuntimeError("皮皮搞笑未提取到有效视频直链")
        return CnWork(
            platform="pipigx",
            platform_label="皮皮搞笑",
            source_url=url,
            work_id=pid,
            title=str(post.get("content") or "").strip(),
            author=str((post.get("user") or {}).get("name") or "").strip(),
            media=[CnMediaItem(url=video_url, kind="video", extension="mp4")],
        )

    # ---------- 6. 最右 ----------
    def _parse_zuiyou(self, url: str) -> CnWork:
        query = parse_qs(urlsplit(url).query)
        pid = (query.get("pid") or [""])[0]
        if not pid:
            final_url = self._resolve_redirect(url, ua=DESKTOP_UA)
            pid = (parse_qs(urlsplit(final_url).query).get("pid") or [""])[0]
        if not pid:
            raise RuntimeError("无法从最右链接中提取 pid 参数")
        resp = requests.post(
            "https://share.izuiyou.com/api/post/detail",
            json={"pid": int(pid)},
            headers={"User-Agent": DESKTOP_UA, "Content-Type": "application/json"},
            timeout=(8, 15),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        post = (resp.json().get("data") or {}).get("post") or {}
        videos = post.get("videos") or {}
        media: List[CnMediaItem] = []
        if isinstance(videos, dict):
            for v in videos.values():
                if isinstance(v, dict) and v.get("url"):
                    media.append(CnMediaItem(url=_to_https(str(v["url"])), kind="video", extension="mp4"))
        if not media:
            for img in post.get("imgs") or []:
                urls = (img or {}).get("urls") or {}
                origin = (urls.get("origin") or urls.get("540") or {}).get("urls") or []
                if origin:
                    u = _to_https(str(origin[0]))
                    media.append(CnMediaItem(url=u, kind="image", extension=_guess_ext(u, "jpg")))
        if not media:
            raise RuntimeError("最右作品未提取到有效视频或图片")
        return CnWork(
            platform="zuiyou",
            platform_label="最右",
            source_url=url,
            work_id=pid,
            title=str(post.get("content") or "").strip(),
            author=str((post.get("member") or {}).get("name") or "").strip(),
            likes=str(post.get("likes") or "未知"),
            media=media,
        )

    # ---------- 7. 豆包 AI 视频 ----------
    def _parse_doubao(self, url: str) -> CnWork:
        final_url = self._resolve_redirect(url, ua=DESKTOP_UA)
        query = parse_qs(urlsplit(final_url).query)
        share_id = (query.get("share_id") or [""])[0]
        video_id = (query.get("video_id") or [""])[0]
        if not share_id or not video_id:
            raise RuntimeError("无法从豆包链接提取 share_id / video_id 参数")
        api_url = (
            "https://www.doubao.com/creativity/share/get_video_share_info"
            "?version_code=20800&language=zh-CN&device_platform=web&aid=497858"
            "&real_aid=497858&pkg_type=release_version&pc_version=3.8.3&samantha_web=1"
        )
        resp = requests.post(
            api_url,
            json={"share_id": share_id, "vid": video_id, "creation_id": ""},
            headers={
                "User-Agent": DESKTOP_UA,
                "Origin": "https://www.doubao.com",
                "Referer": final_url,
                "Content-Type": "application/json",
            },
            timeout=(8, 15),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"豆包视频接口返回错误：{payload.get('msg') or payload.get('code')}")
        data = payload.get("data") or {}
        video_url = ""
        for key in ("play_url", "video_url", "url", "download_url"):
            if isinstance(data.get(key), str) and data[key].startswith("http"):
                video_url = _to_https(data[key])
                break
        if not video_url and isinstance(data.get("play_info"), dict):
            video_url = _to_https(str(data["play_info"].get("main") or data["play_info"].get("url") or ""))
        if not video_url:
            raise RuntimeError("豆包视频接口未返回可用无水印直链")
        return CnWork(
            platform="doubao",
            platform_label="豆包AI",
            source_url=url,
            work_id=video_id,
            title=str(data.get("prompt") or data.get("title") or f"豆包AI视频_{video_id[:8]}").strip(),
            author=str(data.get("author_name") or "豆包AI").strip(),
            media=[CnMediaItem(url=video_url, kind="video", extension="mp4", referer="https://www.doubao.com/")],
        )

    # ---------- 8. 即梦 AI 视频 ----------
    def _parse_jimeng(self, url: str) -> CnWork:
        target = url
        if "/s/" in target:
            target = self._resolve_redirect(target, ua=DESKTOP_UA)
        query = parse_qs(urlsplit(target).query)
        item_id = ""
        for k in ("id", "item_id", "published_item_id", "work_id"):
            if query.get(k):
                item_id = query[k][0]
                break
        if not item_id:
            m = re.search(r"(\d{16,})", target)
            if m:
                item_id = m.group(1)
        if not item_id:
            raise RuntimeError("无法从即梦 AI 链接中提取作品 ID")
        resp = requests.post(
            "https://jimeng.jianying.com/mweb/v1/get_item_info",
            json={"published_item_id": item_id},
            headers={"User-Agent": DESKTOP_UA, "Content-Type": "application/json"},
            timeout=(8, 20),
            proxies=self._proxies(),
        )
        resp.raise_for_status()
        payload = resp.json()
        if str(payload.get("ret", "0")) != "0":
            raise RuntimeError(f"即梦接口返回错误：{payload.get('errmsg') or payload.get('ret')}")
        data = payload.get("data") or {}
        common = data.get("common_attr") or {}
        author = data.get("author") or {}
        video = data.get("video") or {}
        transcoded = video.get("transcoded_video") or {}
        origin_video = video.get("origin_video") or {}
        video_url = ""
        if isinstance(transcoded.get("origin"), dict) and transcoded["origin"].get("video_url"):
            video_url = _to_https(str(transcoded["origin"]["video_url"]))
        elif isinstance(origin_video, dict) and origin_video.get("video_url"):
            video_url = _to_https(str(origin_video["video_url"]))
        elif isinstance(transcoded, dict):
            for entry in transcoded.values():
                if isinstance(entry, dict) and entry.get("video_url"):
                    video_url = _to_https(str(entry["video_url"]))
                    break
        if not video_url:
            raise RuntimeError("即梦 AI 作品未提取到有效视频直链")
        return CnWork(
            platform="jimeng",
            platform_label="即梦AI",
            source_url=url,
            work_id=str(common.get("published_item_id") or item_id),
            title=str(common.get("description") or f"即梦AI视频_{item_id[-8:]}").strip(),
            author=str(author.get("name") or "即梦AI").strip(),
            likes=str((data.get("statistic") or {}).get("like_count") or "未知"),
            media=[CnMediaItem(url=video_url, kind="video", extension="mp4", referer="https://jimeng.jianying.com/")],
        )

    # ---------- 统一下载与落盘 ----------
    def _download_media(self, item: CnMediaItem, destination: Path) -> Path:
        partial = destination.with_name(destination.name + ".part")
        headers = {"User-Agent": DESKTOP_UA}
        if item.referer:
            headers["Referer"] = item.referer
        resp = None
        size = 0
        try:
            resp = requests.get(
                item.url,
                headers=headers,
                timeout=(15, max(30, self.timeout)),
                stream=True,
                proxies=self._proxies(),
            )
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "").lower()
            if ctype.startswith(("text/html", "application/json")):
                raise RuntimeError("目标返回了网页/JSON 而不是媒体文件，请稍后重试")
            with partial.open("wb") as stream:
                for chunk in resp.iter_content(chunk_size=128 * 1024):
                    if chunk:
                        stream.write(chunk)
                        size += len(chunk)
            if size < 200:
                raise RuntimeError("下载到的媒体文件过小")
            partial.replace(destination)
        except Exception:
            partial.unlink(missing_ok=True)
            raise
        finally:
            if resp is not None:
                resp.close()
        if item.kind != "video" and self.image_format != "keep":
            return convert_image_file(destination, self.image_format)
        return destination

    def download_one(self, url: str, output_dir) -> NoteResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        work = self.parse(url)
        note_dir = output_dir / work.folder_name
        note_dir.mkdir(parents=True, exist_ok=True)

        saved: List[Path] = []
        for idx, item in enumerate(work.media):
            ext = self.image_format if (item.kind != "video" and self.image_format != "keep") else item.extension
            dest = note_dir / media_filename(idx, work.title or work.platform_label, ext, is_video=item.kind == "video")
            if not (dest.is_file() and dest.stat().st_size >= 200):
                raw_dest = note_dir / media_filename(idx, work.title or work.platform_label, item.extension, is_video=item.kind == "video")
                dest = self._download_media(item, raw_dest)
            saved.append(dest)

        (note_dir / "文案.txt").write_text(work.copy_text, encoding="utf-8-sig")
        add_history(url, work.work_id, work.title or work.platform_label, str(note_dir.resolve()))
        videos = [m for m in work.media if m.kind == "video"]
        images = [m for m in work.media if m.kind != "video"]
        return NoteResult(
            url=url,
            success=True,
            note_id=work.work_id,
            title=work.title or work.platform_label,
            author=work.author,
            note_type="video" if videos else "normal",
            save_dir=str(note_dir),
            image_count=len(images),
            image_success=len(images),
            desc=work.title,
            engine=f"cn-{work.platform}",
            media_format=", ".join(sorted({p.suffix.lstrip(".").upper() for p in saved})),
        )
