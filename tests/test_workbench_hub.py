"""Tests for the unified 万能采集器 full-feature workbench & APIs."""

import json
import threading
from http.server import HTTPServer
from urllib.request import Request, urlopen

from xhs_dl.web import app as web_app
from xhs_dl.web import toolbox_store


def _post_json(url, payload):
    req = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _get_json(url):
    with urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def test_toolbox_store_imports_jianghu_keywords_and_artworks(monkeypatch, tmp_path):
    hub_file = tmp_path / "workbench_hub.json"
    runtime_dir = tmp_path / "jianghu_runtime"
    kw_dir = runtime_dir / "软件数据" / "DY提取作品_直开" / "关键词信息"
    art_dir = runtime_dir / "runtime" / "软件数据" / "DY提取作品_直开"
    kw_dir.mkdir(parents=True)
    art_dir.mkdir(parents=True)

    (kw_dir / "莫干山温泉_HomeInfo.txt").write_text(
        json.dumps({
            "是否选择": True,
            "序号": 3,
            "关键词": "莫干山温泉",
            "上次是否提取过作品": True,
            "上次提取作品数量": 12,
            "上次提取作品时间": "2026-11-20T10:30:00",
            "已记录作品id": ["1001", "1002", "1003"],
            "备注": "优质词",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (kw_dir / "安吉竹海_HomeInfo.txt").write_text(
        json.dumps({
            "是否选择": False,
            "序号": 3,
            "关键词": "安吉竹海",
            "上次是否提取过作品": False,
            "上次提取作品数量": 0,
            "备注": "备选",
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    (art_dir / "作品列表数据.txt").write_text(
        json.dumps([
            json.dumps({
                "序号": 1,
                "作品唯一id": "7574262098524677627",
                "作品类型": "图文",
                "搜索关键词": "莫干山温泉",
                "作者名称": "测试旅行号",
                "作品标题": "莫干山冬季温泉攻略",
                "点赞量": "320",
                "评论量": "18",
                "图文图片下载网址": json.dumps(["https://example.com/1.jpg", "https://example.com/2.jpg"]),
                "作品网址": "https://www.douyin.com/note/7574262098524677627",
                "下载状态": "已下载 2 张图",
            }, ensure_ascii=False)
        ], ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(hub_file))
    monkeypatch.setenv("JIANGHU_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "1")

    kws = toolbox_store.list_keywords()
    assert kws["total"] == 2
    assert [item["seq"] for item in kws["items"]] == [1, 2]
    mgs = next(item for item in kws["items"] if item["keyword"] == "莫干山温泉")
    assert mgs["recorded_ids"] == 3
    assert mgs["checked"] is True

    arts = toolbox_store.list_artworks(
        mode="history",
        include_kw="温泉",
        rules=[{"enabled": True, "field": "likes", "op": ">=", "value": 100}],
    )
    assert arts["shown_count"] == 1
    assert arts["items"][0]["title"] == "莫干山冬季温泉攻略"

    filtered_out = toolbox_store.list_artworks(
        mode="history",
        exclude_kw="温泉",
    )
    assert filtered_out["shown_count"] == 0


def test_workbench_http_crud_settings_and_4_themes(monkeypatch, tmp_path):
    hub_file = tmp_path / "workbench_hub.json"
    bridge_dir = tmp_path / "bridge"
    jobs_dir = bridge_dir / "jobs"
    jobs_dir.mkdir(parents=True)
    (jobs_dir / "jh-sample123.json").write_text(
        json.dumps({"job_id": "jh-sample123", "kind": "extract-keyword", "keyword": "杭州团建", "status": "completed"}),
        encoding="utf-8",
    )

    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(hub_file))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    monkeypatch.setattr(web_app, "TOOLBOX_BRIDGE_DIR", bridge_dir)

    server = HTTPServer(("127.0.0.1", 0), web_app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = f"http://127.0.0.1:{server.server_port}"
        html = urlopen(root + "/", timeout=5).read().decode("utf-8")
        for marker in (
            'data-theme="neo"',
            'data-theme="neo-dark"',
            'data-theme="glass"',
            'data-theme="glass-dark"',
            "color-scheme:light",
            "color-scheme:dark",
            "white-space:nowrap",
            "SOURCE_ZH",
            "navLiquidPill",
            "wbToast",
            "showToast",
            "extract_single",
            'max="500"',
            "kwImportPreset",
            "btnBannerPopBrowser",
            "btnBannerResume",
            "bring_verify_browser",
            "resume_keyword",
            'id="tabArtworks"',
            'id="tabLogin"',
            'id="tabSettings"',
            'id="kwGroupFilter"',
            'id="auGroupFilter"',
            'class="kpi-strip"',
            'id="kwFileInput"',
            'id="d_auto_ingest_material"',
            'id="k_auto_ingest_chip"',
            "ingestCheckedArtworks",
            "data-open-dir",
            "/favicon.ico",
            "/manifest.webmanifest",
        ):
            assert marker in html
        assert "同步江湖词库" not in html
        assert 'id="kwGroupBar"' not in html
        assert 'id="auGroupBar"' not in html
        assert 'id="tabTasks"' not in html
        assert 'id="tasksPanel"' not in html

        with urlopen(root + "/favicon.ico", timeout=5) as fav_resp:
            assert fav_resp.status == 200
            assert "icon" in (fav_resp.headers.get("Content-Type") or "").lower()
            assert len(fav_resp.read()) > 100
        with urlopen(root + "/app-icon.png", timeout=5) as png_resp:
            assert png_resp.status == 200
            assert png_resp.read().startswith(b"\x89PNG\r\n\x1a\n")
        _, manifest_doc = _get_json(root + "/manifest.webmanifest")
        assert manifest_doc["icons"][0]["src"] == "/app-icon.png"

        code, kw_res = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "add", "platform": "douyin", "group": "江浙沪温泉", "text": "湖州民宿\n莫干山露营"},
        )
        assert code == 200 and kw_res["total"] == 2
        assert kw_res["items"][0]["group"] == "江浙沪温泉"

        code, kw_add2 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "add", "platform": "douyin", "group": "餐饮探店", "text": "杭州私房菜"},
        )
        assert code == 200 and kw_add2["total"] == 3
        assert {g["name"]: g["count"] for g in kw_add2["groups"]} == {"餐饮探店": 1, "江浙沪温泉": 2}

        _, kw_filtered = _get_json(root + "/api/v1/workbench/keywords?platform=douyin&group=%E9%A4%90%E9%A5%AE%E6%8E%A2%E5%BA%97")
        assert len(kw_filtered["items"]) == 1 and kw_filtered["items"][0]["keyword"] == "杭州私房菜"

        code, kw_moved = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "update_group", "ids": [kw_filtered["items"][0]["id"]], "group": "新项目分组", "filter_platform": "douyin"},
        )
        assert code == 200 and any(g["name"] == "新项目分组" for g in kw_moved["groups"])

        code, kw_sorted = _get_json(root + "/api/v1/workbench/keywords?platform=douyin&sort_by=keyword&sort_dir=desc")
        assert [i["keyword"] for i in kw_sorted["items"]] == sorted([i["keyword"] for i in kw_sorted["items"]], key=str.lower, reverse=True)

        code, _ = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "batch_select", "mode": "none", "platform": "douyin", "group": "新项目分组"},
        )
        _, after_clear = _get_json(root + "/api/v1/workbench/keywords?platform=douyin&group=%E6%B1%9F%E6%B5%99%E6%B2%AA%E6%B8%A9%E6%B3%89")
        assert after_clear["checked_count"] == 2  # Clearing another group must not clear this group

        assert toolbox_store.mark_keyword_collected("莫干山露营", platform="douyin", count=18) is True
        _, after_mark = _get_json(root + "/api/v1/workbench/keywords?platform=douyin&search=%E8%8E%AB%E5%B9%B2%E5%B1%B1")
        assert after_mark["items"][0]["last_extracted"] == "是"
        assert after_mark["items"][0]["last_count"] == 18

        code, preset_res = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "import_jzh_preset", "platform": "douyin"},
        )
        assert code == 200 and preset_res["total"] >= 46

        code, au_res = _post_json(
            root + "/api/v1/workbench/authors",
            {"op": "add", "platform": "douyin", "group": "竞品账号", "text": "https://www.douyin.com/user/testuser1"},
        )
        assert code == 200 and au_res["total"] == 1
        assert au_res["groups"] == [{"name": "竞品账号", "count": 1}]
        _, au_grp = _get_json(root + "/api/v1/workbench/authors?platform=douyin&group=%E7%AB%9E%E5%93%81%E8%B4%A6%E5%8F%B7")
        assert len(au_grp["items"]) == 1

        _, default_s = _get_json(root + "/api/v1/workbench/settings")
        assert default_s["keyword"]["direct_download"] is True

        mat_root = tmp_path / "isolated_material_root"
        mat_root.mkdir(parents=True)
        ingest_cfg_path = tmp_path / "ingest_cfg.json"
        ingest_cfg_path.write_text(
            json.dumps({
                "storage": {
                    "material_root_dir": str(mat_root),
                    "enable_month_hardlink": True,
                    "unclassified_downloads_dir": str(tmp_path / "00-unclass"),
                },
            }),
            encoding="utf-8",
        )
        code, s_res = _post_json(
            root + "/api/v1/workbench/settings",
            {
                "software": {"theme": "glass-dark"},
                "keyword": {"min_images": 6, "max_images": 18},
                "download": {
                    "auto_ingest_material": True,
                    "auto_ingest_copy_only": True,
                    "auto_ingest_config_path": str(ingest_cfg_path),
                },
            },
        )
        assert code == 200
        assert s_res["software"]["theme"] == "glass-dark"
        assert s_res["keyword"]["min_images"] == 6
        assert s_res["download"]["auto_ingest_material"] is True

        toolbox_store.record_discovered_artworks(
            [{
                "id": "77001122334455",
                "keyword": "莫干山测试 ",
                "title": "莫干山温泉小院公司团建 . ",
                "caption": "文案测试内容",
                "author": "旅行笔记",
                "like_count": "88",
                "comment_count": "12",
                "collect_count": "34",
                "create_time": "1735099283",
                "url": "https://www.douyin.com/note/77001122334455",
                "image_urls": ["https://example.com/1.png", "https://example.com/2.png"],
            }],
            platform="douyin",
            source="test",
            mark_current=True,
        )
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as"
            b"\x00\x00\x00\x14IDATx\x9cc\xf8\xcf\xc0\x80\x01\x01\x00\x00\x00\x00\xff\xff\x03\x00\x07\x85\x01\x81"
            b"\x7f\x92\xbd\xd2\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        dl_out = tmp_path / "dl_artworks"

        class _FakeResp:
            content = png_bytes
            def raise_for_status(self):
                return None

        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
        import requests as _req
        monkeypatch.setattr(_req, "get", lambda *a, **kw: _FakeResp())
        code, dl_res = _post_json(
            root + "/api/v1/workbench/artworks",
            {"op": "download", "ids": ["77001122334455"], "output_dir": str(dl_out), "mode": "current"},
        )
        assert code == 200
        assert dl_res["downloaded_works"] == 1
        assert dl_res["downloaded_images"] == 2
        assert dl_res["ingest"]["ingested"] == 1
        saved_dir = tmp_path / "dl_artworks" / "关键词作品" / "莫干山测试" / "图文作品" / "评12-藏34-赞88-莫干山温泉小院公司团建-旅行笔记-2024-12-25"
        assert (saved_dir / "封面.jpg").is_file()
        assert (saved_dir / "内页1.jpg").is_file()
        assert (saved_dir / "文案.txt").is_file()
        meta = json.loads((saved_dir / "metadata.json").read_text(encoding="utf-8"))
        assert meta["id"] == "77001122334455"
        assert meta["likes_count"] == 88
        assert meta["comments_count"] == 12
        assert meta["favorites_count"] == 34
        assert meta["watermark_free"] is True
        assert dl_res["items"][0]["download_status"] == "已下载 2 张图"
        assert "已入库" in dl_res["items"][0]["ingest_status"]
        from pathlib import Path as _Path
        assert _Path(dl_res["items"][0]["ingested_dir"]).is_dir()

        code, ing_res = _post_json(
            root + "/api/v1/workbench/artworks",
            {"op": "ingest", "ids": ["77001122334455"], "mode": "current"},
        )
        assert code == 200
        assert ing_res["ingest"]["ingested"] == 1

        code, ai_res = _get_json(root + "/api/v1/workbench/ai-jobs")
        assert code == 200 and len(ai_res["jobs"]) == 1
        assert ai_res["jobs"][0]["keyword"] == "杭州团建"

        _, spec = _get_json(root + "/api/openapi.json")
        assert "/api/v1/workbench/keywords" in spec["paths"]
        assert "/api/v1/workbench/settings" in spec["paths"]
    finally:
        server.shutdown()
        server.server_close()


def test_engine_extract_single_and_multiplatform_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("XHS_DL_LEGACY_JIANGHU_ENGINE", "1")
    project_dir = tmp_path / "toolbox"
    project_dir.mkdir(parents=True)
    (project_dir / "jianghu_cli.py").write_text("# stub cli\n", encoding="utf-8")
    bridge_dir = tmp_path / "bridge"
    bridge_dir.mkdir(parents=True)
    captured = {}

    class _Proc:
        returncode = 0
        stdout = '{"status":"ok","success":true,"title":"单作品标题","message":"提取成功"}\n'
        stderr = ""

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["timeout"] = kwargs.get("timeout")
        return _Proc()

    monkeypatch.setattr(toolbox_store.subprocess, "run", _fake_run)
    res = toolbox_store.run_engine_action(
        "extract_single",
        {
            "platform": "xiaohongshu",
            "url": "https://www.xiaohongshu.com/explore/65abcdef12345678",
            "min_images": 4,
            "max_images": 16,
            "direct_download": True,
            "wait_seconds": 30,
        },
        bridge_dir,
        project_dir,
        "python.exe",
    )
    assert res["success"] is True
    assert "extract-single" in captured["cmd"]
    assert "xiaohongshu" in captured["cmd"]
    assert "--metadata-only" not in captured["cmd"]
    assert captured["timeout"] >= 55

    queued = {}
    monkeypatch.setattr(web_app.toolbox_store, "record_discovered_artworks", lambda *a, **kw: None)
    monkeypatch.setattr(web_app, "_run_job", lambda job_id, urls, *a: queued.setdefault("urls", urls))
    job_id = web_app._queue_collection_links(
        {"job_id": "coll1", "kind": "keyword", "platform": "xiaohongshu"},
        [
            "https://www.douyin.com/note/7574262098524677627",
            "https://www.douyin.com/video/7574262098524677628",
            "https://www.xiaohongshu.com/explore/65abcdef12345678",
            "https://xhslink.com/o/abc123def",
            "https://www.baidu.com/",
        ],
    )
    assert job_id
    assert len(queued["urls"]) == 4
    assert "https://www.baidu.com/" not in queued["urls"]


def test_bring_verify_browser_and_resume_keyword_actions(monkeypatch, tmp_path):
    monkeypatch.setenv("XHS_DL_LEGACY_JIANGHU_ENGINE", "1")
    project_dir = tmp_path / "toolbox"
    project_dir.mkdir(parents=True)
    (project_dir / "jianghu_cli.py").write_text("# stub cli\n", encoding="utf-8")
    bridge_dir = tmp_path / "bridge"
    jobs_dir = bridge_dir / "jobs"
    jobs_dir.mkdir(parents=True)
    (jobs_dir / "jh-verify999.json").write_text(
        json.dumps({"job_id": "jh-verify999", "status": "verification_required", "verification_required": True}),
        encoding="utf-8",
    )

    calls = {}

    class _Proc:
        returncode = 0
        stdout = '{"status":"ok"}\n'
        stderr = ""

    def _fake_run(cmd, **kwargs):
        calls["focus_cmd"] = cmd
        return _Proc()

    def _fake_bring(topmost=True):
        calls["topmost"] = topmost
        return 1

    def _fake_popen(cmd, **kwargs):
        calls["resume_cmd"] = cmd
        return object()

    monkeypatch.setattr(toolbox_store.subprocess, "run", _fake_run)
    monkeypatch.setattr(toolbox_store, "_bring_native_browser_to_front", _fake_bring)
    monkeypatch.setattr(toolbox_store.subprocess, "Popen", _fake_popen)

    focus_res = toolbox_store.run_engine_action(
        "bring_verify_browser",
        {"platform": "douyin"},
        bridge_dir,
        project_dir,
        "python.exe",
    )
    assert focus_res["status"] == "ok"
    assert focus_res["windows_focused"] == 1
    assert "focus" in calls["focus_cmd"]
    assert calls["topmost"] is True

    resume_res = toolbox_store.run_engine_action(
        "resume_keyword",
        {},
        bridge_dir,
        project_dir,
        "python.exe",
    )
    assert resume_res["status"] == "resuming"
    assert resume_res["job_id"] == "jh-verify999"
    assert "resume-keyword" in calls["resume_cmd"]
    assert "jh-verify999" in calls["resume_cmd"]


def test_collection_keyword_forwards_format_and_title_template_to_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(tmp_path / "workbench_hub.json"))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    monkeypatch.setattr(web_app, "TOOLBOX_BRIDGE_DIR", tmp_path / "bridge")
    monkeypatch.setattr(web_app, "TOOLBOX_PROJECT", tmp_path / "toolbox")
    monkeypatch.setattr(web_app, "COLLECTION_TASKS_FILE", tmp_path / "collection_tasks.json")
    monkeypatch.setattr(web_app, "COLLECTION_TASKS", {})
    monkeypatch.setattr(
        web_app,
        "_toolbox_capability_snapshot",
        lambda: {
            "available": True,
            "status": "online",
            "verification_required": False,
            "active_platform": "douyin",
            "busy": False,
        },
    )
    dispatched = {}

    def _fake_spawn(job_id, command, cleanup_files=None):
        dispatched["job_id"] = job_id
        dispatched["command"] = command
        dispatched["cleanup_files"] = cleanup_files or []

    monkeypatch.setattr(web_app, "_run_collection_discovery", _fake_spawn)
    monkeypatch.setattr(toolbox_store, "collect_downloaded_artwork_ids", lambda bridge_dir=None: {"7700112233445566778"})
    server = HTTPServer(("127.0.0.1", 0), web_app.Handler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        code, body = _post_json(
            f"http://127.0.0.1:{port}/api/collections/keyword",
            {
                "keyword": "安吉温泉",
                "count": 3,
                "output_dir": str(tmp_path / "custom_out"),
                "image_format": "jpg",
                "title_template": "评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}",
                "set_file_time_to_publish": True,
                "skip_downloaded_history": True,
            },
        )
        assert code == 202
        import time as _time
        _time.sleep(0.15)
        cmd = dispatched.get("command") or []
        assert "--output-dir" in cmd and str(tmp_path / "custom_out") in cmd
        assert "--image-format" in cmd and "jpg" in cmd
        assert "--title-template" in cmd and "评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}" in cmd
        assert "--set-file-time" in cmd
        assert "--skip-ids-file" in cmd
        skip_path = cmd[cmd.index("--skip-ids-file") + 1]
        assert json.loads((tmp_path / "bridge" / skip_path.split("\\")[-1]).read_text(encoding="utf-8")) == ["7700112233445566778"]

        web_app.COLLECTION_TASKS.clear()
        code_hp, _ = _post_json(
            f"http://127.0.0.1:{port}/api/collections/homepage",
            {
                "profile_url": "https://www.douyin.com/user/MS4wLjABAAAA_test_user",
                "max_works": 15,
                "min_images": 5,
                "max_images": 18,
                "direct_download": True,
                "output_dir": str(tmp_path / "hp_out"),
            },
        )
        assert code_hp == 202
        _time.sleep(0.15)
        hp_cmd = dispatched.get("command") or []
        assert "extract-author" in hp_cmd
        assert "--max-works" in hp_cmd and "15" in hp_cmd
        assert "--min-images" in hp_cmd and "5" in hp_cmd
        assert "--no-auto-download" not in hp_cmd
        assert "--skip-ids-file" in hp_cmd
    finally:
        server.shutdown()
        server.server_close()


def test_dedup_collect_downloaded_ids_and_batch_download_skip_vs_force(monkeypatch, tmp_path):
    hub_file = tmp_path / "workbench_hub.json"
    hist_file = tmp_path / "history.json"
    existing_dir = tmp_path / "existing_work"
    existing_dir.mkdir(parents=True)
    (existing_dir / "封面.jpg").write_bytes(b"\xff\xd8\xff\xd9" * 100)

    hist_file.write_text(
        json.dumps(
            [
                {
                    "笔记ID": "7500000000000000001",
                    "下载网址": "https://www.douyin.com/note/7500000000000000001",
                    "保存位置": str(existing_dir),
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(hub_file))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    monkeypatch.setattr("xhs_dl.storage.history_path", lambda: hist_file)

    toolbox_store.record_discovered_artworks(
        [
            {
                "id": "7500000000000000001",
                "title": "历史命中作品",
                "url": "https://www.douyin.com/note/7500000000000000001",
                "image_urls": ["https://example.com/0.jpg"],
            },
            {
                "id": "7500000000000000002",
                "title": "已下载作品",
                "url": "https://www.douyin.com/note/7500000000000000002",
                "image_urls": ["https://example.com/1.jpg"],
                "download_status": "已下载 1 张图",
                "save_path": str(existing_dir),
            },
        ],
        platform="douyin",
        source="test",
    )

    ids = toolbox_store.collect_downloaded_artwork_ids()
    assert "7500000000000000001" in ids
    assert "7500000000000000002" in ids

    skip_res = toolbox_store.mutate_artworks(
        "download",
        {"ids": ["7500000000000000001", "7500000000000000002"], "output_dir": str(tmp_path / "out")},
    )
    assert skip_res["downloaded_works"] == 0
    assert skip_res["skipped_duplicates"] == 2
    assert "已去重跳过" in skip_res["message"]


def test_notifier_dispatch_topmost_desktop_feishu_and_cooldown(monkeypatch):
    from xhs_dl.web import notifier

    notifier._LAST_SENT.clear()
    calls = {"topmost": [], "desktop": [], "feishu": []}

    monkeypatch.setattr(
        notifier,
        "send_desktop_toast",
        lambda title, message, status="info", action_target="", enabled=True: (
            calls["desktop"].append((title, message, status, action_target, enabled))
            or {"sent": bool(enabled), "backend": "mock"}
        ),
    )
    monkeypatch.setattr(
        notifier,
        "send_feishu_notification",
        lambda title, message, target="", config_path=None, enabled=True: (
            calls["feishu"].append((title, message, target, enabled))
            or {"sent": bool(enabled), "text_code": 0}
        ),
    )

    def _bring(topmost=True):
        calls["topmost"].append(topmost)
        return 1

    cfg = {
        "software": {
            "auto_topmost_verify_window": True,
            "notify_desktop_toast": True,
            "notify_feishu": True,
            "notify_on_complete": False,
            "notify_feishu_target": "素材采集通知群",
        }
    }

    r1 = notifier.dispatch_workbench_notification(
        "verification",
        "触发验证码",
        "请完成人工验证",
        settings=cfg,
        dedup_key="verify:test",
        cooldown_seconds=60.0,
        bring_verify_fn=_bring,
    )
    assert r1["windows_focused"] == 1
    assert r1["desktop"]["sent"] is True
    assert r1["feishu"]["sent"] is True
    assert calls["topmost"] == [True]
    assert len(calls["desktop"]) == 1
    assert len(calls["feishu"]) == 1

    # Immediate duplicate suppressed by cooldown
    r2 = notifier.dispatch_workbench_notification(
        "verification",
        "触发验证码",
        "请完成人工验证",
        settings=cfg,
        dedup_key="verify:test",
        cooldown_seconds=60.0,
        bring_verify_fn=_bring,
    )
    assert r2["skipped"] is True and r2["reason"] == "cooldown"
    assert len(calls["feishu"]) == 1

    # Completed suppressed when notify_on_complete=False
    r3 = notifier.dispatch_workbench_notification(
        "completed",
        "采集完成",
        "共 2 套",
        settings=cfg,
        dedup_key="done:1",
    )
    assert r3["skipped"] is True and r3["reason"] == "completed_notify_disabled"


def test_ui_template_has_dedup_and_notification_controls():
    html = web_app.TEMPLATE
    for marker in (
        'id="k_skip_dup_chip"',
        'id="k_media_type"',
        'id="k_web_sort"',
        'id="k_web_publish_time"',
        'id="themeButton"',
        'CYCLE_THEMES',
        '主题：自动切换',
        'data-theme="light"',
        'data-theme="dark"',
        'resolveAutoTheme',
        'id="artMinFavorites"',
        'id="inputModal"',
        'rename_group',
        'id="subAi"',
        'AI 接入',
        'id="aiMasterPrompt"',
        '一键复制给 AI Agent',
        'copyAiSnippet',
        'id="d_write_metadata"',
        '读取时间',
        '已读取未下载',
        'collected_at',
        'id="sw_auto_topmost_verify_window"',
        'id="sw_notify_desktop_toast"',
        'id="sw_notify_feishu"',
        'id="sw_notify_on_complete"',
        'id="sw_notify_feishu_target"',
        'id="feishuConfigDrawer"',
        'id="sw_notify_feishu_app_id"',
        'id="sw_notify_feishu_app_secret"',
        'id="sw_notify_feishu_webhook"',
        'id="groupManagerModal"',
        'id="rowEditModal"',
        'id="sw_proxy_url"',
        'id="sw_theme_day_start"',
        'id="sw_theme_night_start"',
        'id="sw_theme_auto_style"',
        'id="titleTemplatePreview"',
        'artResetFilters',
        'pickFolderInto',
        'openConfigFileEditor',
        'insertTemplateToken',
        'create_group',
        'delete_group',
        'edit_item',
        "test_notification",
        'id="queueList"',
        'id="progressBar"',
        "xhs-dl-active-tab",
    ):
        assert marker in html
    assert html.index('id="kwLaunchCard"') < html.index('id="kwTableBody"')
    assert 'class="right-stack"' not in html
    assert 'id="historyList"' not in html
    for removed in (
        'id="singleFilterDrawer"',
        'id="d_down_dynamic_cover"',
        'id="k_local_life_only"',
        'id="themePickerCards"',
        'id="themePopover"',
        'id="settingsButton"',
        'id="settingsDialog"',
        'id="aiCurlExample"',
        'id="tabTasks"',
        'id="tasksPanel"',
        "onmouseleave=\"this.removeAttribute('open')\"",
        'artSyncJianghu',
    ):
        assert removed not in html


def test_douyin_search_url_builder_and_health_code_stamp(monkeypatch):
    from xhs_dl.web import native_collector

    assert native_collector._build_douyin_search_url("安吉温泉", "综合排序", "不限").endswith("?type=general")
    u1 = native_collector._build_douyin_search_url("安吉温泉", "最多点赞", "一天内")
    assert "sort_type=1" in u1 and "publish_time=1" in u1
    u2 = native_collector._build_douyin_search_url("安吉温泉", "最新发布", "一周内")
    assert "sort_type=2" in u2 and "publish_time=7" in u2
    u3 = native_collector._build_douyin_search_url("安吉温泉", "综合排序", "半年内")
    assert "sort_type=" not in u3 and "publish_time=180" in u3
    u_vid = native_collector._build_douyin_search_url("安吉温泉", "综合排序", "不限", media_type="video")
    assert "?type=video" in u_vid
    u_all = native_collector._build_douyin_search_url("安吉温泉", "综合排序", "不限", media_type="all")
    assert "?type=general" in u_all
    assert web_app.SERVER_CODE_STAMP > 0


def test_capability_snapshot_ignores_stale_verification_progress_when_engine_clean(monkeypatch, tmp_path):
    monkeypatch.setenv("XHS_DL_LEGACY_JIANGHU_ENGINE", "1")
    bridge = tmp_path / "bridge"
    bridge.mkdir(parents=True)
    proj = tmp_path / "proj"
    proj.mkdir(parents=True)
    (proj / "jianghu_cli.py").write_text("# stub\n", encoding="utf-8")
    (bridge / "bridge_status.json").write_text(
        json.dumps({"running": True, "active_platform": "douyin", "verification_required": False}),
        encoding="utf-8",
    )
    (bridge / "keyword_progress.json").write_text(
        json.dumps({"phase": "verification", "status": "verification_required", "keyword": "旧词", "message": "旧验证"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(web_app, "TOOLBOX_BRIDGE_DIR", bridge)
    monkeypatch.setattr(web_app, "TOOLBOX_PROJECT", proj)
    snap = web_app._toolbox_capability_snapshot()
    assert snap["status"] == "online"
    assert snap["verification_required"] is False
    assert snap["keyword_progress"].get("status") != "verification_required"


def test_focus_and_bring_verify_browser_falls_back_to_open_platform_login(monkeypatch, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir(parents=True)
    (proj / "jianghu_cli.py").write_text("# stub\n", encoding="utf-8")
    bridge = tmp_path / "bridge"
    bridge.mkdir(parents=True)

    cmds = []
    bring_results = [0, 1]

    def _fake_run(cmd, **_kwargs):
        cmds.append(cmd)
        return None

    def _fake_bring(topmost=True):
        return bring_results.pop(0) if bring_results else 1

    monkeypatch.setattr(toolbox_store.subprocess, "run", _fake_run)
    monkeypatch.setattr(toolbox_store, "_bring_native_browser_to_front", _fake_bring)
    monkeypatch.setattr(toolbox_store.time, "sleep", lambda _s: None)

    focused = toolbox_store.focus_and_bring_verify_browser(
        bridge, proj, "python.exe", topmost=True, open_login=False, platform="douyin"
    )
    assert focused == 1
    assert any("focus" in c for c in cmds)
    assert any("open-platform-login" in c for c in cmds)


def test_native_collector_capabilities_always_online_and_proxy_probe(monkeypatch):
    from xhs_dl.web import native_collector

    for env_k in ("JIANGHU_PROXY_URL", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        monkeypatch.delenv(env_k, raising=False)
    eng = native_collector.NativeBrowserCollector()
    cap = eng.get_capabilities()
    assert cap["available"] is True
    assert cap["status"] == "online"
    assert cap["engine_mode"] == "native-playwright"
    assert cap["supports"]["keyword"] == ["douyin", "xiaohongshu"]
    # Unreachable local proxy port must be safely skipped rather than breaking Edge launch
    assert native_collector._resolve_reachable_proxy("http://127.0.0.1:1") is None


def test_native_collector_douyin_keyword_dedup_and_direct_download(monkeypatch, tmp_path):
    from xhs_dl.web import native_collector

    eng = native_collector.NativeBrowserCollector(profile_dir=tmp_path / "profile")
    snapshots = [
        {
            "verification": False,
            "login_required": False,
            "cards": [
                {
                    "index": 0,
                    "is_photo": True,
                    "is_video": False,
                    "id": "1000000000000000001",
                    "image_count": 4,
                    "title": "已采作品",
                    "author": "A",
                    "image_urls": [f"https://img.test/a{i}.jpg" for i in range(4)],
                },
                {
                    "index": 1,
                    "is_photo": True,
                    "is_video": False,
                    "id": "1000000000000000002",
                    "image_count": 4,
                    "title": "新作品1",
                    "author": "B",
                    "image_urls": [f"https://img.test/b{i}.jpg" for i in range(4)],
                },
            ],
        },
        {
            "verification": False,
            "login_required": False,
            "cards": [
                {
                    "index": 2,
                    "is_photo": True,
                    "is_video": False,
                    "id": "1000000000000000003",
                    "image_count": 5,
                    "title": "新作品2",
                    "author": "C",
                    "image_urls": [f"https://img.test/c{i}.jpg" for i in range(5)],
                },
            ],
        },
    ]
    call_idx = {"n": 0}

    class _FakePage:
        url = "about:blank"

        def is_closed(self):
            return False

        def goto(self, url, **_kwargs):
            self.url = url

        def evaluate(self, script):
            if "scrollHeight" in script or "window.scrollTo" in script:
                call_idx["n"] = min(call_idx["n"] + 1, len(snapshots) - 1)
                return {"before": 2, "after": 3, "at_bottom": False}
            return snapshots[call_idx["n"]]

    fake_page = _FakePage()
    monkeypatch.setattr(eng, "_ensure_page_in_worker", lambda proxy_url="": fake_page)
    monkeypatch.setattr(eng, "_call_browser", lambda fn, timeout=120.0: fn())
    monkeypatch.setattr(native_collector.time, "sleep", lambda _s: None)
    monkeypatch.setattr(
        toolbox_store,
        "_download_single_artwork_row",
        lambda row, base_out, download_settings=None: (
            {"save_path": str(tmp_path / f"work_{row['id']}"), "image_count": row["image_count"]},
            "",
        ),
    )

    res = eng.collect_douyin_keyword(
        "测试团建",
        count=2,
        direct_download=True,
        skip_ids={"1000000000000000001"},
        output_dir=str(tmp_path / "out"),
    )
    assert res["status"] == "completed"
    assert res["skipped_duplicate_count"] == 1
    assert [c["id"] for c in res["candidates"]] == ["1000000000000000002", "1000000000000000003"]
    assert res["download"]["success_count"] == 2
    assert res["media_file_count"] == 9


def test_native_collector_verification_gate_raises_topmost_and_notifies(monkeypatch, tmp_path):
    from xhs_dl.web import native_collector

    eng = native_collector.NativeBrowserCollector(profile_dir=tmp_path / "profile")

    class _GatePage:
        url = "about:blank"

        def is_closed(self):
            return False

        def goto(self, url, **_kwargs):
            self.url = url

        def evaluate(self, _script):
            return {"verification": True, "login_required": False, "cards": []}

    raised = []
    gates = []
    monkeypatch.setattr(eng, "_ensure_page_in_worker", lambda proxy_url="": _GatePage())
    monkeypatch.setattr(eng, "_call_browser", lambda fn, timeout=120.0: fn())
    monkeypatch.setattr(eng, "_bring_to_front_in_worker", lambda **kw: raised.append(kw) or 1)

    res = eng.collect_douyin_keyword(
        "安吉团建",
        count=2,
        on_gate_cb=lambda st, msg: gates.append((st, msg)),
        job_request={"kind": "keyword", "platform": "douyin", "keyword": "安吉团建"},
    )
    assert res["status"] == "verification_required"
    assert len(raised) == 1 and raised[0].get("topmost") is True
    assert len(gates) == 1 and gates[0][0] == "verification_required"
    paused = eng.consume_paused_job()
    assert paused and paused["keyword"] == "安吉团建"


def test_group_rename_favorites_filter_media_types_and_browser_minimize(monkeypatch, tmp_path):
    from xhs_dl.web import native_collector

    hub_file = tmp_path / "workbench_hub.json"
    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(hub_file))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    monkeypatch.setattr(web_app, "TOOLBOX_BRIDGE_DIR", tmp_path / "bridge")

    server = HTTPServer(("127.0.0.1", 0), web_app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = f"http://127.0.0.1:{server.server_port}"
        _post_json(root + "/api/v1/workbench/keywords", {"op": "add", "platform": "douyin", "group": "老分组A", "text": "词1\n词2"})
        code, rn_kw = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "rename_group", "platform": "douyin", "old_group": "老分组A", "new_group": "新分组B"},
        )
        assert code == 200
        assert all(it["group"] == "新分组B" for it in rn_kw["items"])

        _post_json(root + "/api/v1/workbench/authors", {"op": "add", "platform": "douyin", "group": "竞品A", "text": "https://www.douyin.com/user/u1"})
        code, rn_au = _post_json(
            root + "/api/v1/workbench/authors",
            {"op": "rename_group", "platform": "douyin", "old_group": "竞品A", "new_group": "重点对标"},
        )
        assert code == 200
        assert all(it["group"] == "重点对标" for it in rn_au["items"])

        toolbox_store.record_discovered_artworks(
            [
                {"id": "art1", "title": "低赞藏", "likes": 10, "favorites": 5, "comments": 1, "image_count": 4},
                {"id": "art2", "title": "高收藏", "likes": 20, "favorites": 120, "comments": 2, "image_count": 6},
            ],
            platform="douyin",
            source="test",
            mark_current=True,
        )
        _, fav_filtered = _get_json(root + "/api/v1/workbench/artworks?mode=current&min_favorites=50")
        assert fav_filtered["shown_count"] == 1
        assert fav_filtered["items"][0]["id"] == "art2"
    finally:
        server.shutdown()
        server.server_close()

    snap = {
        "cards": [
            {"id": "p1", "is_photo": True, "is_video": False, "image_count": 5},
            {"id": "v1", "is_photo": False, "is_video": True, "image_count": 0},
        ]
    }
    assert [c["id"] for c in native_collector._candidate_records(snap, 10, min_images=4, max_images=20, media_type="image")] == ["p1"]
    assert [c["id"] for c in native_collector._candidate_records(snap, 10, min_images=4, max_images=20, media_type="video")] == ["v1"]
    assert [c["id"] for c in native_collector._candidate_records(snap, 10, min_images=4, max_images=20, media_type="all")] == ["p1", "v1"]

    eng = native_collector.NativeBrowserCollector(profile_dir=tmp_path / "profile")
    args = eng._build_launch_args()
    assert "--window-position=140,70" in args
    assert all("-3200" not in a for a in args)

    moved_offscreen = []
    minimized = []
    monkeypatch.setattr(eng, "_move_window_cdp_in_worker", lambda *a, **kw: moved_offscreen.append(a))
    monkeypatch.setattr(eng, "_minimize_window_in_worker", lambda: minimized.append(True) or 1)
    assert eng._hide_window_in_worker() == 1
    assert minimized == [True]
    assert moved_offscreen == []


def test_collected_at_unified_history_ingest_labels_and_write_metadata_toggle(monkeypatch, tmp_path):
    from pathlib import Path
    import material_ingestor as mi

    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(tmp_path / "workbench_hub.json"))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")

    toolbox_store.record_discovered_artworks(
        [
            {"id": "w1", "title": "老时间作品", "collected_at": "2026-11-24 10:00:00", "image_urls": ["https://a/1.jpg"]},
        ],
        platform="douyin",
        source="作者主页",
        mark_current=False,
    )
    listed = toolbox_store.list_artworks(
        mode="history",
        sort_by="collected_at",
        sort_dir="desc",
        extra_history=[
            {
                "note_id": "clip1",
                "title": "剪贴板测试作品",
                "url": "https://www.xiaohongshu.com/explore/clip1",
                "completed_at": "2026-11-25 22:01:00",
                "save_dir": str(tmp_path / "02-图文原料" / "01月" / "剪贴板测试作品"),
            }
        ],
        extra_ai_jobs=[
            {
                "job_id": "jh-ai-01",
                "kind": "extract-keyword",
                "keyword": "杭州团建",
                "status": "completed",
                "message": "已采集完成 5 条",
                "updated_at": "2026-11-25 22:02:00",
            }
        ],
    )
    ids = [r["id"] for r in listed["items"]]
    assert ids == ["aijob:jh-ai-01", "clip1", "w1"]
    assert listed["items"][0]["artwork_type"] == "AI任务"
    assert listed["items"][0]["download_status"] == "成功"
    assert listed["items"][1]["keyword"] == "剪贴板采集"
    assert listed["items"][1]["ingest_status"] == "已入库"
    assert listed["items"][2]["download_status"] == "已读取未下载"
    assert listed["items"][2]["keyword"] == "作者主页"

    # Flattened month ingest status labels
    r_months = {}
    toolbox_store._apply_ingest_info_to_row(
        r_months,
        {"success": True, "city": "杭州", "seasons": ["冬季"], "months": ["01月", "02月", "12月"], "target_dir": "D:/out"},
    )
    assert r_months["ingest_status"] == "已入库·01月/02月/12月"
    r_all12 = {}
    toolbox_store._apply_ingest_info_to_row(
        r_all12,
        {"success": True, "city": "莫干山", "months": [f"{m:02d}月" for m in range(1, 13)], "target_dir": "D:/out2"},
    )
    assert r_all12["ingest_status"] == "已入库·全12月"

    # write_metadata toggle in both _download_single_artwork_row and material_ingestor.ingest_work_package
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as"
        b"\x00\x00\x00\x14IDATx\x9cc\xf8\xcf\xc0\x80\x01\x01\x00\x00\x00\x00\xff\xff\x03\x00\x07\x85\x01\x81"
        b"\x7f\x92\xbd\xd2\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    class _FakeResp:
        content = png_bytes
        def raise_for_status(self):
            return None

    import requests as _req
    monkeypatch.setattr(_req, "get", lambda *a, **kw: _FakeResp())

    info_no_meta, _ = toolbox_store._download_single_artwork_row(
        {"id": "nometa1", "title": "关闭元数据测试", "keyword": "测试", "image_urls": ["https://e/1.png"]},
        str(tmp_path / "dl_no_meta"),
        download_settings={"write_metadata": False},
    )
    assert info_no_meta and not (Path(info_no_meta["save_path"]) / "metadata.json").exists()

    mat_root = tmp_path / "mat_root"
    mat_root.mkdir(parents=True)
    cfg = {"storage": {"material_root_dir": str(mat_root), "unclassified_downloads_dir": str(tmp_path / "00")}}
    ing_no_meta = mi.ingest_work_package(info_no_meta["save_path"], config=cfg, copy_only=True, write_metadata=False)
    assert ing_no_meta["success"] is True
    assert not (Path(ing_no_meta["target_dir"]) / "metadata.json").exists()

    ing_with_meta = mi.ingest_work_package(info_no_meta["save_path"], config=cfg, copy_only=True, write_metadata=True)
    assert ing_with_meta["success"] is True
    assert (Path(ing_with_meta["target_dir"]) / "metadata.json").is_file()


def test_open_feishu_webhook_openapi_and_browser_channel_detection(monkeypatch):
    import requests as _req
    from xhs_dl.web import native_collector, notifier

    # 1. Browser channel auto-detection returns one of msedge/chrome/chromium and capabilities exposes it
    detected = native_collector._detect_available_browser_channel()
    assert detected in {"msedge", "chrome", "chromium"}
    eng = native_collector.NativeBrowserCollector()
    assert eng.get_capabilities()["browser_channel"] == detected

    # 2. Direct Webhook delivery works with zero external script
    posted = []

    class _FakeHttpResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.content = json.dumps(payload).encode("utf-8")

        def json(self):
            return self._payload

    def _fake_post(url, json=None, headers=None, timeout=10):
        posted.append((url, json, headers))
        if "bot/v2/hook" in url:
            return _FakeHttpResp(200, {"StatusCode": 0, "msg": "ok"})
        if "tenant_access_token" in url:
            return _FakeHttpResp(200, {"code": 0, "tenant_access_token": "tok_test_123"})
        if "/im/v1/messages" in url:
            return _FakeHttpResp(200, {"code": 0, "data": {"message_id": "om_test"}})
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(_req, "post", _fake_post)

    wh_res = notifier.send_feishu_notification(
        "测试标题",
        "Webhook 正文",
        webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/abc123",
        enabled=True,
    )
    assert wh_res["sent"] is True and wh_res["channel"] == "feishu-webhook"

    # 3. Direct OpenAPI delivery using App ID + Secret + oc_ group ID
    oa_res = notifier.send_feishu_notification(
        "企业机器人测试",
        "OpenAPI 正文",
        target="oc_test123",
        app_id="cli_user_bot",
        app_secret="sec_xyz",
        enabled=True,
    )
    assert oa_res["sent"] is True
    assert oa_res["channel"] == "feishu-openapi"
    assert oa_res["target"] == "oc_test123"
    assert any("/im/v1/messages" in call[0] for call in posted)

    # 4. dispatch_workbench_notification forwards UI-configured credentials
    notifier._LAST_SENT.clear()
    monkeypatch.setattr(
        notifier,
        "send_desktop_toast",
        lambda *a, **kw: {"sent": True},
    )
    d_res = notifier.dispatch_workbench_notification(
        "verification",
        "触发验证码",
        "请完成人工验证",
        settings={
            "software": {
                "notify_desktop_toast": True,
                "notify_feishu": True,
                "notify_feishu_target": "oc_group_ui",
                "notify_feishu_app_id": "cli_ui_1",
                "notify_feishu_app_secret": "sec_ui_1",
                "notify_feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/uihook",
            }
        },
        dedup_key="test:open:feishu",
        cooldown_seconds=60.0,
    )
    assert d_res["feishu"]["sent"] is True and d_res["feishu"]["channel"] == "feishu-webhook"


def test_group_crud_row_edit_and_diy_settings(monkeypatch, tmp_path):
    hub_file = tmp_path / "workbench_hub.json"
    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(hub_file))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    monkeypatch.setattr(web_app, "TOOLBOX_BRIDGE_DIR", tmp_path / "bridge")

    server = HTTPServer(("127.0.0.1", 0), web_app.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        root = f"http://127.0.0.1:{server.server_port}"

        # 1. Keyword empty group create -> rename -> add -> edit_item -> delete_group (move & cascade)
        code, k1 = _post_json(root + "/api/v1/workbench/keywords", {"op": "create_group", "platform": "douyin", "group": "江浙沪"})
        assert code == 200 and any(g["name"] == "江浙沪" and g["count"] == 0 for g in k1["groups"])

        code, k2 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "rename_group", "platform": "douyin", "old_group": "江浙沪", "new_group": "长三角"},
        )
        assert code == 200
        assert any(g["name"] == "长三角" for g in k2["groups"])
        assert not any(g["name"] == "江浙沪" for g in k2["groups"])

        _, k3 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "add", "platform": "douyin", "group": "长三角", "text": "莫干山\n千岛湖"},
        )
        target_row = next(r for r in k3["items"] if r["keyword"] == "莫干山")
        _, k4 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "edit_item", "id": target_row["id"], "keyword": "莫干山温泉", "group": "长三角", "remark": "核心词"},
        )
        edited = next(r for r in k4["items"] if r["id"] == target_row["id"])
        assert edited["keyword"] == "莫干山温泉" and edited["remark"] == "核心词"

        _, k5 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "delete_group", "platform": "douyin", "group": "长三角", "delete_items": False},
        )
        assert not any(g["name"] == "长三角" for g in k5["groups"])
        moved = next(r for r in k5["items"] if r["id"] == target_row["id"])
        assert moved["group"] == "默认分组"

        _, k6 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "add", "platform": "douyin", "group": "临时分组", "text": "临时词A"},
        )
        assert any(r["keyword"] == "临时词A" for r in k6["items"])
        _, k7 = _post_json(
            root + "/api/v1/workbench/keywords",
            {"op": "delete_group", "platform": "douyin", "group": "临时分组", "delete_items": True},
        )
        assert not any(r["keyword"] == "临时词A" for r in k7["items"])
        assert not any(g["name"] == "临时分组" for g in k7["groups"])

        # 2. Author group create -> add -> edit_item -> delete_group
        _, a1 = _post_json(root + "/api/v1/workbench/authors", {"op": "create_group", "platform": "douyin", "group": "民宿达人"})
        assert any(g["name"] == "民宿达人" and g["count"] == 0 for g in a1["groups"])
        _, a2 = _post_json(
            root + "/api/v1/workbench/authors",
            {"op": "add", "platform": "douyin", "group": "民宿达人", "text": "https://www.douyin.com/user/MS4wLjABAAAA_demo_author"},
        )
        au_row = a2["items"][0]
        _, a3 = _post_json(
            root + "/api/v1/workbench/authors",
            {
                "op": "edit_item",
                "id": au_row["id"],
                "name": "安吉小住",
                "url": "https://www.douyin.com/user/MS4wLjABAAAA_demo_author_v2",
                "group": "精选达人",
                "remark": "高赞稳定",
            },
        )
        au_edited = next(r for r in a3["items"] if r["id"] == au_row["id"])
        assert au_edited["name"] == "安吉小住"
        assert au_edited["group"] == "精选达人"
        assert au_edited["remark"] == "高赞稳定"

        # 3. DIY settings persistence (proxy_url & Beijing auto-theme schedule/style)
        code, saved = _post_json(
            root + "/api/v1/workbench/settings",
            {
                "software": {
                    "proxy_url": "http://127.0.0.1:7890",
                    "theme_day_start": 8,
                    "theme_night_start": 20,
                    "theme_auto_style": "glass",
                }
            },
        )
        assert code == 200
        assert saved["software"]["proxy_url"] == "http://127.0.0.1:7890"
        assert saved["software"]["theme_day_start"] == 8
        assert saved["software"]["theme_night_start"] == 20
        assert saved["software"]["theme_auto_style"] == "glass"
        _, reloaded = _get_json(root + "/api/v1/workbench/settings")
        assert reloaded["software"]["proxy_url"] == "http://127.0.0.1:7890"
        assert reloaded["software"]["theme_auto_style"] == "glass"
    finally:
        server.shutdown()
        server.server_close()


def test_patchright_loader_and_network_json_parsers_for_douyin_and_xhs():
    from xhs_dl.web import native_collector

    _sync_fn, driver_name = native_collector._load_sync_playwright()
    assert callable(_sync_fn)
    assert driver_name == "patchright"

    # Douyin search + author_list JSON parsing
    dy_search_payload = {
        "data": [
            {
                "aweme_info": {
                    "aweme_id": "7580000000000000123",
                    "aweme_type": 68,
                    "media_type": 2,
                    "desc": "莫干山温泉度假文案",
                    "create_time": 1735099283,
                    "author": {"nickname": "小旅", "uid": "1001", "sec_uid": "MS4w_test"},
                    "statistics": {"digg_count": 88, "comment_count": 12, "collect_count": 34, "share_count": 5},
                    "images": [
                        {
                            "width": 1080,
                            "height": 1440,
                            "url_list": [
                                "https://p3-sign.douyinpic.com/tplv-dy-water/abc.jpeg",
                                "https://p3-sign.douyinpic.com/origin/clean1.jpeg",
                            ],
                        },
                        {
                            "width": 1080,
                            "height": 1440,
                            "url_list": ["https://p3-sign.douyinpic.com/origin/clean2.png"],
                        },
                    ],
                }
            }
        ]
    }
    dy_items = native_collector._extract_douyin_items_from_api_payload(dy_search_payload)
    assert len(dy_items) == 1
    assert dy_items[0]["source_layer"] == "network_api"
    assert dy_items[0]["is_photo"] is True
    assert dy_items[0]["image_urls"] == [
        "https://p3-sign.douyinpic.com/origin/clean1.jpeg",
        "https://p3-sign.douyinpic.com/origin/clean2.png",
    ]
    assert dy_items[0]["collect_count"] == "34"

    dy_author_payload = {
        "aweme_list": [
            {
                "aweme_id": "7580000000000000456",
                "aweme_type": 0,
                "media_type": 4,
                "desc": "安吉竹海航拍",
                "video": {"duration": 15000, "play_addr": {"url_list": ["https://v26.douyinvod.com/demo.mp4"]}},
            }
        ]
    }
    dy_vids = native_collector._extract_douyin_items_from_api_payload(dy_author_payload)
    assert len(dy_vids) == 1 and dy_vids[0]["is_video"] is True and "demo.mp4" in dy_vids[0]["video_url"]

    # Xiaohongshu search + feed detail + user_posted JSON parsing with xsec_token & LivePhoto
    xhs_feed_payload = {
        "data": {
            "items": [
                {
                    "id": "6738ab12000000001e01a2b3",
                    "xsec_token": "ABcDeF123+/",
                    "note_card": {
                        "type": "normal",
                        "display_title": "桐庐绝美民宿",
                        "desc": "weekend stay",
                        "time": 1735099283000,
                        "user": {"nickname": "宿集", "user_id": "u_99"},
                        "interact_info": {"liked_count": "1.2万", "collected_count": "890", "comment_count": "45"},
                        "image_list": [
                            {
                                "width": 1242,
                                "height": 1660,
                                "info_list": [
                                    {"image_scene": "WB_PRV", "url": "http://sns-webpic-qc.xhscdn.com/prv/1.jpg"},
                                    {"image_scene": "WB_DFT", "url": "http://sns-webpic-qc.xhscdn.com/dft/1.jpg"},
                                ],
                                "live_photo": True,
                                "stream": {"h264": [{"master_url": "http://sns-video-qc.xhscdn.com/live1.mp4"}]},
                            },
                            {
                                "width": 1242,
                                "height": 1660,
                                "url_default": "https://sns-webpic-qc.xhscdn.com/dft/2.jpg",
                            },
                        ],
                    },
                }
            ]
        }
    }
    xhs_items = native_collector._extract_xhs_items_from_api_payload(xhs_feed_payload, source="pc_search")
    assert len(xhs_items) == 1
    x = xhs_items[0]
    assert "xsec_token=ABcDeF123%2B%2F" in x["url"]
    assert x["image_urls"] == [
        "https://sns-webpic-qc.xhscdn.com/dft/1.jpg",
        "https://sns-webpic-qc.xhscdn.com/dft/2.jpg",
    ]
    assert x["live_photo_urls"] == ["https://sns-video-qc.xhscdn.com/live1.mp4"]
    assert x["like_count"] == "12000"
    assert x["create_time"] == "1735099283"

    xhs_user_payload = {
        "data": {
            "notes": [
                {
                    "note_id": "6738ab12000000001e01a2b4",
                    "xsec_token": "USER_TOK",
                    "type": "normal",
                    "display_title": "达人主页合集",
                    "user": {"nick_name": "博主A", "user_id": "u_1"},
                    "cover": {"url_default": "https://sns-webpic-qc.xhscdn.com/cover.jpg"},
                }
            ]
        }
    }
    hp_items = native_collector._extract_xhs_items_from_api_payload(xhs_user_payload, source="pc_user")
    assert len(hp_items) == 1 and hp_items[0]["id"] == "6738ab12000000001e01a2b4"
    assert "xsec_source=pc_user" in hp_items[0]["url"]


def test_xhs_homepage_routing_live_photo_download_profiles_and_rule_health(monkeypatch, tmp_path):
    import requests as _req
    from xhs_dl.web import native_collector, ui_template

    # 1. Dual-platform profile URL validation
    dy_url, dy_plat = web_app._validate_profile_url("https://www.douyin.com/user/MS4wLjABAAAA_test")
    assert dy_plat == "douyin" and "/user/" in dy_url
    xhs_url, xhs_plat = web_app._validate_profile_url("https://www.xiaohongshu.com/user/profile/5f1234abcd")
    assert xhs_plat == "xiaohongshu" and "/user/profile/" in xhs_url

    # 2. LivePhoto & Xiaohongshu Referer download in _download_single_artwork_row
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\xfd\xd4\x9as"
        b"\x00\x00\x00\x14IDATx\x9cc\xf8\xcf\xc0\x80\x01\x01\x00\x00\x00\x00\xff\xff\x03\x00\x07\x85\x01\x81"
        b"\x7f\x92\xbd\xd2\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    seen_referers = []

    class _FakeResp:
        def __init__(self, payload_bytes):
            self.content = payload_bytes

        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size=65536):
            yield self.content

    def _fake_get(url, headers=None, stream=False, timeout=None):
        seen_referers.append((url, (headers or {}).get("Referer")))
        if "live1.mp4" in url:
            return _FakeResp(b"\x00\x00\x00\x18ftypmp42livephoto")
        return _FakeResp(png_bytes)

    monkeypatch.setattr(_req, "get", _fake_get)
    row = {
        "id": "xhs_lp_1",
        "platform": "xiaohongshu",
        "keyword": "杭州赏秋",
        "title": "实况图文测试",
        "author": "旅行拍客",
        "image_urls": ["https://sns-webpic-qc.xhscdn.com/dft/1.jpg"],
        "live_photo_urls": ["https://sns-video-qc.xhscdn.com/live1.mp4"],
    }
    dl_info, _ = toolbox_store._download_single_artwork_row(row, str(tmp_path / "xhs_dl_out"))
    from pathlib import Path as _P
    pkg_dir = _P(dl_info["save_path"])
    assert (pkg_dir / "封面.jpg").is_file()
    assert (pkg_dir / "实况1.mp4").is_file()
    meta = json.loads((pkg_dir / "metadata.json").read_text(encoding="utf-8"))
    assert meta["live_photo_files"] == ["实况1.mp4"]
    assert all(ref == "https://www.xiaohongshu.com/" for _, ref in seen_referers)

    # 3. Multi-account profiles + rule_health + UI markers
    monkeypatch.setenv("XHS_DL_PROFILES_ROOT", str(tmp_path / "profiles"))
    eng = native_collector.NativeBrowserCollector()
    assert eng.get_capabilities()["browser_driver"] == "patchright"
    assert eng.get_capabilities()["supports"]["xiaohongshu_homepage"] is True

    created = eng.create_profile("小红书备用号")
    assert any(p["name"] == "小红书备用号" for p in created["profiles"])
    switched = eng.switch_profile("小红书备用号")
    assert switched["active_profile"] == "小红书备用号"
    deleted = eng.delete_profile("小红书备用号")
    assert deleted["active_profile"] == "default"

    assert eng._record_rule_health("douyin", api_items=0, dom_items=0) == "possible_rule_break"
    assert eng._record_rule_health("xiaohongshu", api_items=12, dom_items=0) == "ok"
    caps = eng.get_capabilities()
    assert caps["rule_health"]["douyin"]["status"] == "possible_rule_break"
    assert caps["rule_health"]["xiaohongshu"]["status"] == "ok"

    html = web_app.TEMPLATE
    for marker in ("profileSelect", "engineRuleHealthBox", "createBrowserProfile", "switchBrowserProfile", "deleteBrowserProfile"):
        assert marker in html


