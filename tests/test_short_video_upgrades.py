"""Tests for absorbed short_videos capabilities:
1. Douyin fast cookie-free API channel + browser fallback.
2. Chinese short-video & AI video platform routing + parsing.
3. Single-work UI platform list display.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_detect_platform_routes_cn_short_video_and_ai_platforms():
    from xhs_dl.core.platforms import detect_cn_subplatform, detect_platform

    cases = [
        ("https://v.kuaishou.com/abc123", "kuaishou"),
        ("https://www.kuaishou.com/short-video/3xabc", "kuaishou"),
        ("https://weibo.com/tv/show/1034:1234567890", "weibo"),
        ("https://video.weibo.com/show?fid=1034:1234567890", "weibo"),
        ("https://www.toutiao.com/video/7123456789012345678/", "toutiao"),
        ("https://h5.pipix.com/s/abcdef/", "pipixia"),
        ("https://h5.pipigx.com/pp/post/123?pid=111&mid=222", "pipigx"),
        ("https://share.izuiyou.com/hybrid/share/post?pid=999", "zuiyou"),
        ("https://www.doubao.com/video-sharing?share_id=abc&video_id=def", "doubao"),
        ("https://jimeng.jianying.com/ai-tool/video/7123456789012345678", "jimeng"),
    ]
    for url, expected_sub in cases:
        assert detect_platform(url) == "cn_video", f"Expected cn_video for {url}"
        assert detect_cn_subplatform(url) == expected_sub, f"Expected {expected_sub} for {url}"


def test_douyin_fast_api_extracts_original_video_and_falls_back_on_error(monkeypatch, tmp_path):
    from xhs_dl.core.douyin_downloader import DouyinBrowserEngine

    aweme_id = "7663398572494336177"
    fake_detail = {
        "status_code": 0,
        "aweme_detail": {
            "aweme_id": aweme_id,
            "desc": "原画测试视频 #风景",
            "create_time": 1766503530,
            "author": {"nickname": "测试作者"},
            "statistics": {
                "digg_count": 120,
                "comment_count": 15,
                "collect_count": 30,
                "share_count": 8,
            },
            "video": {
                "play_addr": {
                    "uri": "v0200fg10000testvid",
                    "url_list": ["https://v3-web.douyinvod.com/playwm/fallback.mp4"],
                }
            },
        },
    }

    class FakeResp:
        def __init__(self, status_code=200, json_data=None, headers=None, url=""):
            self.status_code = status_code
            self._json = json_data
            self.headers = headers or {}
            self.url = url

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._json

        def close(self):
            pass

    def fake_get(url, **kwargs):
        if "api.amemv.com" in url:
            return FakeResp(200, fake_detail)
        if "aweme.snssdk.com/aweme/v1/play/" in url:
            return FakeResp(302, headers={"Location": "https://cdn.douyinvod.com/original_hd.mp4"})
        return FakeResp(200, url=url)

    monkeypatch.setattr("xhs_dl.core.douyin_downloader.requests.get", fake_get)

    engine = DouyinBrowserEngine(image_format="keep")
    payload = engine._extract_page(f"https://www.douyin.com/video/{aweme_id}")
    assert payload["_engine"] == "douyin-fast-api"
    assert payload["title"] == "原画测试视频 #风景"
    assert payload["author"] == "测试作者"
    assert len(payload["media"]) == 1
    assert payload["media"][0]["kind"] == "video"
    assert "original_hd.mp4" in payload["media"][0]["url"]
    assert "mime_type=video_mp4" in payload["media"][0]["url"]

    # Fallback to browser when fast API fails
    monkeypatch.setattr(
        DouyinBrowserEngine,
        "_extract_via_fast_api",
        lambda self, url: (_ for _ in ()).throw(RuntimeError("api blocked")),
    )
    monkeypatch.setattr(
        DouyinBrowserEngine,
        "_extract_via_browser",
        lambda self, url: {
            "final_url": f"https://www.douyin.com/video/{aweme_id}",
            "title": "浏览器兜底作品",
            "author": "兜底作者",
            "media": [{"url": "https://cdn.example/video.mp4", "kind": "video", "extension": "mp4"}],
        },
    )
    fallback_payload = engine._extract_page(f"https://www.douyin.com/video/{aweme_id}")
    assert fallback_payload["title"] == "浏览器兜底作品"


def test_cn_short_video_engine_parses_jimeng_and_downloads(monkeypatch, tmp_path):
    from xhs_dl.core.cn_short_video_downloader import CnShortVideoEngine

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))

    class FakeResp:
        def __init__(self, json_data=None, content=b""):
            self._json = json_data
            self._content = content
            self.headers = {"Content-Type": "video/mp4"}

        def raise_for_status(self):
            pass

        def json(self):
            return self._json

        def iter_content(self, chunk_size=131072):
            yield self._content

        def close(self):
            pass

    jimeng_payload = {
        "ret": "0",
        "data": {
            "common_attr": {
                "published_item_id": "7123456789012345678",
                "description": "即梦AI赛博朋克短片",
            },
            "author": {"name": "AI创作者"},
            "statistic": {"like_count": 88},
            "video": {
                "transcoded_video": {
                    "origin": {"video_url": "https://cdn.jimeng.test/origin.mp4"}
                }
            },
        },
    }

    monkeypatch.setattr(
        "xhs_dl.core.cn_short_video_downloader.requests.post",
        lambda *a, **kw: FakeResp(json_data=jimeng_payload),
    )
    monkeypatch.setattr(
        "xhs_dl.core.cn_short_video_downloader.requests.get",
        lambda *a, **kw: FakeResp(content=b"\x00" * 512),
    )

    engine = CnShortVideoEngine()
    res = engine.download_one(
        "https://jimeng.jianying.com/ai-tool/video/7123456789012345678",
        tmp_path / "out",
    )
    assert res.success is True
    assert res.engine == "cn-jimeng"
    assert res.note_type == "video"
    save_dir = Path(res.save_dir)
    assert (save_dir / "文案.txt").is_file()
    assert any(p.suffix == ".mp4" for p in save_dir.iterdir())


def test_single_work_ui_lists_all_supported_platforms():
    from xhs_dl.web.ui_template import TEMPLATE

    for label in ("抖音", "小红书", "快手", "B站", "微博", "今日头条", "豆包 AI", "即梦 AI", "皮皮虾", "YouTube"):
        assert label in TEMPLATE, f"Missing platform label {label} in UI"
    assert 'id="singlePlatformSeg"' not in TEMPLATE
    assert "badge-pill" not in TEMPLATE
    assert 'data-plat="xiaohongshu">小红书</button>' in TEMPLATE
    assert "小红书（暂未开放）" not in TEMPLATE


def test_job_summary_returns_readable_title_and_artworks_include_source_fields(tmp_path):
    from xhs_dl.web import app as web_app
    from xhs_dl.web import toolbox_store

    summary = web_app._job_summary({
        "job_id": "09fd8491444a4bfdae4440898875356b",
        "status": "completed",
        "total": 10,
        "items": [{"title": "测试作品标题"}],
    })
    assert summary["title"] == "测试作品标题 等 10 条"

    summary_empty = web_app._job_summary({
        "job_id": "09fd8491444a4bfdae4440898875356b",
        "status": "completed",
        "total": 5,
        "items": [],
    })
    assert summary_empty["title"] == "批量下载任务（共 5 条）"

    bridge = tmp_path / "bridge"
    bridge.mkdir(parents=True, exist_ok=True)
    listed = toolbox_store.list_artworks(
        bridge_dir=bridge,
        extra_ai_jobs=[{
            "job_id": "jh-ai-shell",
            "kind": "universal-download",
            "status": "completed",
            "message": "universal-download",
            "updated_at": "2026-11-26 12:00:00",
        }],
    )
    ai_row = next(r for r in listed["items"] if r["id"] == "aijob:jh-ai-shell")
    assert ai_row["source_channel"] == "AI"
    assert ai_row["is_shell_job"] is True


def test_desktop_shell_filters_about_blank_and_watches_core_dir():
    cs = (Path(__file__).resolve().parents[1] / "desktop_shell" / "UniversalCollectorShell.cs").read_text(encoding="utf-8")
    assert "_navigatedToApp" in cs
    assert "args.IsSuccess" in cs
    assert 'Path.Combine(_projectRoot, "xhs_dl", "core")' in cs


def test_cloudflare_workers_and_desktop_403_proxy_fallback(monkeypatch, tmp_path):
    from xhs_dl.core.cn_short_video_downloader import CnMediaItem, CnShortVideoEngine

    root = Path(__file__).resolve().parents[1]
    assert (root / "cloudflare_workers" / "douyin-parser" / "workers.js").is_file()
    assert (root / "cloudflare_workers" / "media-proxy" / "worker.js").is_file()
    assert (root / "cloudflare_workers" / "deploy.cmd").is_file()

    monkeypatch.setenv("CF_SV_PROXY_URL", "https://proxy.example.workers.dev")
    seen_urls = []

    class FakeResp:
        def __init__(self, status_code, content=b""):
            self.status_code = status_code
            self._content = content
            self.headers = {"Content-Type": "video/mp4"}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def iter_content(self, chunk_size=131072):
            yield self._content

        def close(self):
            pass

    def fake_get(url, **kwargs):
        seen_urls.append(url)
        if "proxy.example.workers.dev" in url:
            return FakeResp(200, b"\x00" * 300)
        return FakeResp(403)

    monkeypatch.setattr("xhs_dl.core.cn_short_video_downloader.requests.get", fake_get)
    dest = tmp_path / "video.mp4"
    out = CnShortVideoEngine()._download_media(
        CnMediaItem(url="https://cdn.example/video.mp4", kind="video", extension="mp4", referer="https://weibo.com/"),
        dest,
    )
    assert out.is_file()
    assert len(seen_urls) == 2
    assert "proxy.example.workers.dev" in seen_urls[1]
    assert "type=weibo" in seen_urls[1]
