# -*- coding: utf-8 -*-
"""Comprehensive regression tests for Step 1 and Step 2 collector upgrades."""
from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _png_bytes(size=(64, 64)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size)
    px = img.load()
    for y in range(size[1]):
        for x in range(size[0]):
            px[x, y] = ((x * 17 + y * 31) % 256, (x * 53 + y * 7) % 256, (x * 11 + y * 43) % 256)
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_douyin_short_and_long_url_dedup_via_note_id(tmp_path, monkeypatch):
    from xhs_dl import storage

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    note_dir = tmp_path / "downloads" / "评10-赞20-测试-作者"
    note_dir.mkdir(parents=True)
    (note_dir / "封面.png").write_bytes(_png_bytes())

    storage.add_history("https://v.douyin.com/AbCdEfG/", "7663398572494336177", "测试", str(note_dir))

    hit_long = storage.find_downloaded(download_url="https://www.douyin.com/video/7663398572494336177")
    hit_ies = storage.find_downloaded(download_url="https://www.iesdouyin.com/note/7663398572494336177")
    assert hit_long is not None and hit_long["笔记ID"] == "7663398572494336177"
    assert hit_ies is not None and hit_ies["保存位置"] == str(note_dir)
    assert storage.same_download(
        "https://www.douyin.com/note/7663398572494336177?from=a",
        "https://www.iesdouyin.com/video/7663398572494336177",
    )


def test_douyin_engine_fast_fails_on_gate_and_reuses_browser_for_batches(tmp_path, monkeypatch):
    from xhs_dl.core.douyin_downloader import DouyinBrowserEngine, DouyinMedia, DouyinWork
    from xhs_dl.core.unified_downloader import UnifiedDownloader

    created_browsers = []
    contexts_created = []

    class FakeContext:
        def new_page(self):
            return FakePage()

        def close(self):
            pass

    class FakePage:
        def goto(self, *args, **kwargs):
            pass

        def wait_for_function(self, *args, **kwargs):
            return SimpleNamespace(
                json_value=lambda: {
                    "final_url": "https://www.douyin.com/note/1111111111111111111",
                    "title": "",
                    "media": [],
                    "gate": "verification",
                    "gate_reason": "抖音触发人机验证/滑块，无法免登解析",
                }
            )

    class FakeBrowser:
        def __init__(self):
            self.closed = False

        def is_connected(self):
            return not self.closed

        def new_context(self, **kwargs):
            contexts_created.append(kwargs)
            return FakeContext()

        def close(self):
            self.closed = True

    class FakePlaywrightDriver:
        def __init__(self):
            self.stopped = False

        @property
        def chromium(self):
            driver = self

            class _Chromium:
                def launch(self, **kwargs):
                    b = FakeBrowser()
                    created_browsers.append(b)
                    return b

            return _Chromium()

        def stop(self):
            self.stopped = True

    class FakeSyncPlaywrightCM:
        def __init__(self):
            self.driver = FakePlaywrightDriver()

        def start(self):
            return self.driver

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: FakeSyncPlaywrightCM())

    engine = DouyinBrowserEngine(reusable_browser=True)
    with pytest.raises(RuntimeError, match="人机验证"):
        engine._extract_page("https://v.douyin.com/first/")
    assert len(created_browsers) == 1
    assert not created_browsers[0].closed
    with pytest.raises(RuntimeError, match="人机验证"):
        engine._extract_page("https://v.douyin.com/second/")
    assert len(created_browsers) == 1  # reused same browser
    assert len(contexts_created) == 2
    engine.close()
    assert created_browsers[0].closed

    # Batch UnifiedDownloader should pass reusable_browser=True when >1 douyin URL and close on finish
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XHS_DL_CLAIM_DIR", str(tmp_path / "claims"))
    closed_flags = []
    orig_close = DouyinBrowserEngine.close

    def tracked_close(self):
        closed_flags.append(self.reusable_browser)
        return orig_close(self)

    monkeypatch.setattr(DouyinBrowserEngine, "close", tracked_close)
    dl = UnifiedDownloader(output_dir=str(tmp_path / "out"), delay=(0, 0))
    res = dl.download(["https://v.douyin.com/a/", "https://v.douyin.com/b/"])
    assert res.fail_count == 2
    assert all("人机验证" in (item.error or "") for item in res.results)
    assert closed_flags == [True]

    # MAX_PATH budget protection
    long_work = DouyinWork(
        source_url="https://v.douyin.com/x/",
        final_url="https://www.douyin.com/note/7663398572494336177",
        note_id="7663398572494336177",
        title="超级无敌长的抖音图文标题" * 12,
        author="作者名字也很长",
        likes="100",
        comments="20",
        favorites="5",
        shares="3",
        published_at="",
        topics=[],
        media=[],
    )
    deep_out = tmp_path / ("子目录" * 8)
    safe_dir = DouyinBrowserEngine._safe_note_dir(deep_out, long_work)
    assert DouyinBrowserEngine._utf16_units(str(safe_dir)) <= 255 - 75

    # Image decode verification even when image_format == "keep"
    class CorruptImgResponse:
        headers = {"Content-Type": "image/jpeg"}

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            yield b"NOT_AN_IMAGE_PAYLOAD" * 20

        def close(self):
            return None

    monkeypatch.setattr("xhs_dl.core.douyin_downloader.requests.get", lambda *a, **k: CorruptImgResponse())
    dest = tmp_path / "keep_test.jpg"
    with pytest.raises(RuntimeError, match="损坏或非有效图片"):
        DouyinBrowserEngine(image_format="keep")._download_media(
            DouyinMedia("https://example/img.jpg", "image", "jpg"), dest
        )
    assert not dest.exists()
    assert not dest.with_name("keep_test.jpg.part").exists()


def test_material_ingestor_parsing_filtering_routing_and_non_self_hardlinks(tmp_path, monkeypatch):
    import material_ingestor as mi

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    mat_root = tmp_path / "图文原料"
    theme = mat_root / "06-主题合集"
    unclass = tmp_path / "00-待识别"
    for d in (mat_root, theme, unclass):
        d.mkdir(parents=True, exist_ok=True)
    (theme / "01-♨️全域精选·秋冬私汤与真温泉专区").mkdir(parents=True, exist_ok=True)

    cfg = {
        "storage": {
            "material_root_dir": str(mat_root),
            "enable_month_hardlink": True,
            "theme_dir": str(theme),
            "unclassified_downloads_dir": str(unclass),
        },
        "filter_rules": {"max_images_allowed": 5},
        "project_routing": {"doubao_pullnew": {"enabled": True, "keywords": ["豆包"]}},
    }

    assert mi.parse_cn_count("1.2万") == 12000
    assert mi.parse_cn_count("未知") == 0
    c, l, a, nid = mi.parse_folder_stats("评未知-赞1.5w-杭州温泉团建-小旅")
    assert (c, l, a, nid) == (0, 15000, "小旅", "")

    # 1. Labeled copy decoupling + top-level month (01月/02月/12月) + theme hardlinks (no 01~04 / 05)
    pkg1 = tmp_path / "staging" / "评12-赞1.2万-杭州温泉团建包栋-探店君"
    pkg1.mkdir(parents=True)
    (pkg1 / "封面.png").write_bytes(_png_bytes())
    (pkg1 / "内页1.png").write_bytes(_png_bytes())
    (pkg1 / "文案.txt").write_text(
        "标题：杭州温泉团建包栋别墅\n\n"
        "正文：\n冬季公司团建泡私汤包栋超爽\n\n"
        "话题：\n#杭州团建 #温泉\n\n"
        "作者：探店君\n点赞：1.2万\n原始链接：https://v.douyin.com/xyz/\n作品 ID：7663398572494336177\n",
        encoding="utf-8-sig",
    )

    dry = mi.ingest_work_package(
        pkg1, config=cfg, url="https://v.douyin.com/xyz/", dry_run=True
    )
    assert dry["status"] == "ok" and dry["outcome"] == "dry_run"
    assert pkg1.exists()  # dry_run must not move source
    assert dry["category"] == "杭州"
    assert dry["traffic_type"] == "精准流量"

    res = mi.ingest_work_package(
        pkg1, config=cfg, url="https://v.douyin.com/xyz/", dry_run=False
    )
    assert res["status"] == "ok" and res["outcome"] == "ingested"
    dest_dir = Path(res["target_dir"])
    assert dest_dir.parent == mat_root / "01月"
    assert str(dest_dir) not in res["month_hardlink_dirs"]  # never self-hardlink
    assert len(res["month_hardlink_dirs"]) == 2
    assert any(Path(d).parent == mat_root / "02月" for d in res["month_hardlink_dirs"])
    assert any(Path(d).parent == mat_root / "12月" for d in res["month_hardlink_dirs"])
    assert not any("专区" in p.name for p in mat_root.iterdir() if p.is_dir())
    assert any("01-♨️全域精选" in p for p in res["theme_hardlink_dirs"])

    cleaned_copy = (dest_dir / "文案.txt").read_text(encoding="utf-8-sig")
    assert "原始链接：" not in cleaned_copy
    assert "作品 ID：" not in cleaned_copy
    assert "杭州温泉团建包栋别墅" in cleaned_copy
    assert "冬季公司团建泡私汤包栋超爽" in cleaned_copy

    meta = json.loads((dest_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["likes_count"] == 12000
    assert meta["comments_count"] == 12
    assert meta["city"] == "杭州"
    assert "温泉/私汤" in meta["themes"]
    assert meta["url"] == "https://v.douyin.com/xyz/"

    # 2. Plain copy (XHS v2_downloader style) + true year-round hardlinks across 01月~12月 (11 secondary links)
    pkg2 = tmp_path / "staging" / "评5-赞88-莫干山日常民宿-民宿主"
    pkg2.mkdir(parents=True)
    (pkg2 / "封面.png").write_bytes(_png_bytes())
    (pkg2 / "文案.txt").write_text("莫干山团建推荐\n\n适合部门聚会\n\n#莫干山\n", encoding="utf-8-sig")
    res2 = mi.ingest_work_package(pkg2, config=cfg, url="https://xhslink.com/o/abc", copy_only=True)
    assert res2["success"] is True
    assert pkg2.exists()  # copy_only leaves source intact
    assert res2["months"] == [f"{m:02d}月" for m in range(1, 13)]
    assert Path(res2["target_dir"]).parent == mat_root / "01月"
    assert len(res2["month_hardlink_dirs"]) == 11
    assert all("05-四季通用" not in d and "专区" not in d for d in res2["month_hardlink_dirs"])
    for sec in res2["month_hardlink_dirs"]:
        assert os.path.samefile(Path(res2["target_dir"]) / "封面.png", Path(sec) / "封面.png")

    # 3. Oversized filter + Ad filter
    pkg3 = tmp_path / "staging" / "超图"
    pkg3.mkdir(parents=True)
    for i in range(6):
        (pkg3 / f"p{i}.png").write_bytes(_png_bytes())
    oversized = mi.ingest_work_package(pkg3, config=cfg, max_images=5)
    assert oversized["status"] == "filtered" and oversized["outcome"] == "filtered_oversized"

    pkg4 = tmp_path / "staging" / "广告"
    pkg4.mkdir(parents=True)
    (pkg4 / "封面.png").write_bytes(_png_bytes())
    (pkg4 / "文案.txt").write_text("喜提新车试驾体验分享\n", encoding="utf-8")
    ad = mi.ingest_work_package(pkg4, config=cfg)
    assert ad["status"] == "filtered" and ad["outcome"] == "filtered_ad"

    # 4. New 评-藏-赞-标题-作者-日期 naming + existing metadata preservation
    c5, l5, a5, _ = mi.parse_folder_stats("评18-藏45-赞320-安吉温泉团建天花板-旅行策划师-2025-11-25")
    assert (c5, l5, a5) == (18, 320, "旅行策划师")
    pkg5 = tmp_path / "staging" / "评18-藏45-赞320-安吉温泉团建天花板-旅行策划师-2025-11-25"
    pkg5.mkdir(parents=True)
    (pkg5 / "封面.jpg").write_bytes(_png_bytes())
    (pkg5 / "文案.txt").write_text("安吉温泉团建天花板\n冬日公司团建泡私汤首选\n", encoding="utf-8")
    (pkg5 / "metadata.json").write_text(
        json.dumps({
            "platform": "douyin",
            "id": "7699116520023207578",
            "note_id": "7699116520023207578",
            "title": "安吉温泉团建天花板",
            "author": "旅行策划师",
            "likes_count": 320,
            "comments_count": 18,
            "favorites_count": 45,
            "publish_time": "2025-11-25 17:07:11",
            "publish_date": "2025-11-25",
            "watermark_free": True,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    res5 = mi.ingest_work_package(pkg5, config=cfg, copy_only=True)
    assert res5["success"] is True and res5["category"] == "安吉"
    dest5 = Path(res5["target_dir"])
    assert dest5.is_dir()
    meta5 = json.loads((dest5 / "metadata.json").read_text(encoding="utf-8"))
    assert meta5["favorites_count"] == 45
    assert meta5["publish_time"] == "2025-11-25 17:07:11"
    assert meta5["watermark_free"] is True
    assert meta5["platform"] == "抖音"


def test_clipboard_collector_error_passthrough_and_three_strike_pause(tmp_path, monkeypatch):
    import universal_clipboard_collector as ucc
    from xhs_dl.core.models import DownloadResult, NoteResult

    monkeypatch.setattr(ucc, "TEMP_DOWNLOAD_DIR", tmp_path / "staging")
    monkeypatch.setattr(ucc, "FAIL_STREAK_FILE", tmp_path / "streak.json")
    monkeypatch.setattr(ucc, "PAUSE_FILE", tmp_path / "paused.json")
    monkeypatch.setattr(ucc, "QUEUE_FILE", tmp_path / "queue.json")
    monkeypatch.setattr(ucc, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(ucc, "HEARTBEAT_FILE", tmp_path / "hb.json")
    monkeypatch.setattr(ucc, "FAIL_PAUSE_THRESHOLD", 3)
    monkeypatch.setattr(ucc, "MAX_RETRIES", 3)
    monkeypatch.setattr(ucc, "DEEP_COOLDOWN_BASE", 0.01)
    monkeypatch.setattr(ucc, "send_desktop_notification", lambda *a, **k: None)
    monkeypatch.setattr(ucc, "send_feishu_error_sync", lambda *a, **k: None)

    class FakeUnifiedDownloader:
        def __init__(self, **kwargs):
            pass

        def download(self, urls):
            res = DownloadResult(output_dir=str(tmp_path / "staging"))
            res.results.append(NoteResult(url=urls[0], error="抖音触发人机验证/滑块，无法免登解析"))
            return res

    monkeypatch.setattr(ucc, "UnifiedDownloader", FakeUnifiedDownloader)

    ok, msg, meta = ucc.execute_download_and_file("https://v.douyin.com/verify1/")
    assert ok is False
    assert "人机验证" in msg
    assert "UNKNOWN_NO_OUTPUT" not in msg

    # Three-strike circuit breaker MUST trip after 3 consecutive failures even when MAX_RETRIES == 3
    qm = ucc.QueueManager()
    qm.queue = [{
        "id": "xhs_test_1",
        "url": "https://v.douyin.com/verify1/",
        "title_hint": "测试作品",
        "raw_text": "https://v.douyin.com/verify1/",
        "status": "pending",
        "retry_count": 0,
    }]
    qm.save()

    monkeypatch.setattr(ucc, "execute_download_and_file", lambda u: (False, "抖音触发人机验证/滑块，无法免登解析", {}))
    monkeypatch.setattr(ucc, "_already_in_shared_history", lambda u: None)
    monkeypatch.setattr(ucc.time, "sleep", lambda s: None)

    # Clear cooldowns between retries inside queue_worker_loop test
    orig_is_cooling = qm.is_cooling_down
    monkeypatch.setattr(qm, "is_cooling_down", lambda: (False, 0.0, ""))

    ucc.queue_worker_loop(qm, set())

    assert ucc.PAUSE_FILE.exists(), "Three-strike circuit breaker failed to create PAUSE_FILE"
    pause_data = json.loads(ucc.PAUSE_FILE.read_text(encoding="utf-8"))
    assert pause_data["paused_by"] == "auto-fail-guard"
    assert pause_data["consecutive_failures"] == 3
    assert len(qm.failed) == 1

    # Verify retry_failed_items restores failed item back to pending queue
    ucc.PAUSE_FILE.unlink()
    requeued = qm.retry_failed_items()
    assert requeued["moved_count"] == 1
    assert len(qm.queue) == 1
    assert qm.queue[0]["retry_count"] == 0
    assert len(qm.failed) == 0


def test_watchdog_clears_24h_stale_guard_and_kills_headless_zombie(tmp_path, monkeypatch):
    import universal_clipboard_watchdog as wdog

    pause_file = tmp_path / "paused.json"
    streak_file = tmp_path / "streak.json"
    hb_file = tmp_path / "hb.json"
    monkeypatch.setattr(wdog, "PAUSE_FILE", pause_file)
    monkeypatch.setattr(wdog, "FAILURE_STREAK_FILE", streak_file)
    monkeypatch.setattr(wdog, "HEARTBEAT_FILE", hb_file)
    monkeypatch.setattr(wdog, "LOG_FILE", tmp_path / "wdog.log")

    # 1. Stale 25h auto-fail-guard lock should be auto-cleared
    stale_iso = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 90000))
    pause_file.write_text(json.dumps({
        "paused": True, "paused_by": "auto-fail-guard", "paused_at": stale_iso,
    }), encoding="utf-8")
    streak_file.write_text(json.dumps({"count": 3}), encoding="utf-8")
    assert wdog.is_collector_paused() is False
    assert not pause_file.exists()
    assert json.loads(streak_file.read_text(encoding="utf-8"))["count"] == 0

    # 2. Manual / migration locks MUST NOT be cleared even if > 24h old
    pause_file.write_text(json.dumps({
        "paused": True, "paused_by": "codex-migration-gate", "paused_at": stale_iso,
    }), encoding="utf-8")
    assert wdog.is_collector_paused() is True
    assert pause_file.exists()

    # 3. Zombie collector (>120s alive, missing or mismatched heartbeat PID) must be killed
    killed = []

    class FakeProc:
        pid = 99999
        info = {
            "pid": 99999,
            "name": "pythonw.exe",
            "cmdline": ["pythonw.exe", "universal_clipboard_collector.py"],
            "create_time": time.time() - 300.0,
        }

        def kill(self):
            killed.append(self.pid)

    import psutil
    monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: [FakeProc()])
    assert wdog.is_collector_alive() is False
    assert killed == [99999]

    # Heartbeat PID mismatch also kills zombie
    killed.clear()
    hb_file.write_text(json.dumps({"pid": 11111, "timestamp": time.time()}), encoding="utf-8")
    assert wdog.is_collector_alive() is False
    assert killed == [99999]


def test_restart_helper_rejects_stale_heartbeat_or_stopped_pid():
    import restart_clipboard_collector as rcc

    t0 = 2000.0
    # 1. Pre-restart timestamp (wrote by old killed process just before restart) must be rejected
    assert rcc.is_fresh_restart_heartbeat(
        {"pid": 9001, "timestamp": t0 - 2.0},
        restart_started_at=t0,
        stopped_pids={7588},
        now=t0 + 1.0,
        pid_exists=lambda pid: True,
    ) is False

    # 2. Stopped PID reuse must be rejected
    assert rcc.is_fresh_restart_heartbeat(
        {"pid": 7588, "timestamp": t0 + 0.5},
        restart_started_at=t0,
        stopped_pids={7588},
        now=t0 + 1.0,
        pid_exists=lambda pid: True,
    ) is False

    # 3. Dead PID must be rejected
    assert rcc.is_fresh_restart_heartbeat(
        {"pid": 9002, "timestamp": t0 + 0.5},
        restart_started_at=t0,
        stopped_pids={7588},
        now=t0 + 1.0,
        pid_exists=lambda pid: False,
    ) is False

    # 4. Fresh timestamp from live new PID is accepted
    assert rcc.is_fresh_restart_heartbeat(
        {"pid": 9003, "timestamp": t0 + 0.5},
        restart_started_at=t0,
        stopped_pids={7588},
        now=t0 + 1.0,
        pid_exists=lambda pid: pid == 9003,
    ) is True
