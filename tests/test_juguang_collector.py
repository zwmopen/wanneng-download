# -*- coding: utf-8 -*-
import csv
import io
import json
from pathlib import Path

from xhs_dl.web import native_collector, toolbox_store, ui_template


def test_parse_juguang_payload_extracts_full_metrics_and_media():
    payload = {
        "code": 0,
        "success": True,
        "data": {
            "total": 1,
            "noteList": [
                {
                    "noteInfo": {
                        "noteId": "6740abc123456789def01234",
                        "title": "江浙沪团建两天一夜超全攻略",
                        "noteLink": "https://www.xiaohongshu.com/explore/6740abc123456789def01234?xsec_token=TOK123&xsec_source=pc_ad",
                        "notePublishTime": 1732579200000,
                        "likeNum": 328,
                        "cmtNum": 42,
                        "favNum": 510,
                        "readNum": 18500,
                        "shareNum": 29,
                        "noteType": 1,
                        "noteImages": [
                            {"imageUrl": "http://sns-img.xhscdn.com/a.jpg?imageview2/2/w/540/format/webp"},
                            {"imageUrl": "//sns-img.xhscdn.com/b.jpg?imageview2/2/w/540"},
                        ],
                    },
                    "userInfo": {"nickName": "江湖策划小助手", "userId": "u_999"},
                }
            ],
        },
    }
    items = native_collector._extract_juguang_items_from_api_payload(
        payload, keyword="江浙沪团建", category="客资收集"
    )
    assert len(items) == 1
    item = items[0]
    assert item["platform"] == "juguang"
    assert item["source_channel"] == "聚光内容广场"
    assert item["juguang_category"] == "客资收集"
    assert item["reads"] == "18500"
    assert item["likes"] == "328"
    assert item["comments"] == "42"
    assert item["favorites"] == "510"
    assert item["shares"] == "29"
    assert item["xsec_token"] == "TOK123"
    assert item["image_urls"] == ["https://sns-img.xhscdn.com/a.jpg", "https://sns-img.xhscdn.com/b.jpg"]
    assert item["artwork_type"] == "图文"


def test_ssr_initial_state_and_copywriting_extraction(monkeypatch):
    sample_state = {
        "note": {
            "noteDetailMap": {
                "abc123": {
                    "note": {
                        "title": "安吉温泉团建两天一夜",
                        "desc": "公司秋冬团建首选安吉私汤民宿，包含方案预算。\n#江浙沪团建[话题]# #安吉温泉[话题]#",
                        "tagList": [{"name": "公司团建"}, {"name": "江浙沪团建"}],
                        "imageList": [
                            {"urlDefault": "https://sns-img.xhscdn.com/p1.jpg"},
                            {"urlDefault": "https://sns-img.xhscdn.com/p2.jpg", "livePhoto": True, "stream": {"h264": [{"masterUrl": "https://sns-video.xhscdn.com/lp1.mp4"}]}},
                        ],
                    }
                }
            }
        }
    }
    html = f"<html><script>window.__INITIAL_STATE__={json.dumps(sample_state, ensure_ascii=False)};window.__X__=undefined;</script></html>"

    class FakeResp:
        status_code = 200
        text = html.replace('"安吉温泉团建两天一夜"', '"安吉温泉团建两天一夜"')

    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **kw: FakeResp())

    detail = native_collector._fetch_xhs_note_ssr_detail("https://www.xiaohongshu.com/explore/abc123?xsec_token=T")
    assert detail["title"] == "安吉温泉团建两天一夜"
    assert "[话题]" not in detail["desc"]
    assert "公司团建" in detail["topics"]
    assert "安吉温泉" in detail["topics"]
    assert "#公司团建" in detail["caption"]
    assert len(detail["image_urls"]) == 2
    assert detail["live_photo_urls"] == ["https://sns-video.xhscdn.com/lp1.mp4"]


def test_toolbox_store_juguang_metadata_copy_and_detailed_csv(monkeypatch, tmp_path):
    monkeypatch.setenv("XHS_DL_WORKBENCH_FILE", str(tmp_path / "workbench_hub.json"))
    monkeypatch.setenv("XHS_DL_AUTO_SYNC_JIANGHU", "0")
    assert toolbox_store._normalize_platform("小红书聚光") == "juguang"
    assert toolbox_store._normalize_platform("juguang") == "juguang"

    toolbox_store.mutate_keywords(
        "add", {"platform": "juguang", "group": "秋冬团建", "text": "江浙沪团建"}
    )
    kw_res = toolbox_store.list_keywords(platform="juguang")
    assert len(kw_res["items"]) == 1
    assert kw_res["items"][0]["platform"] == "juguang"

    monkeypatch.setattr(
        toolbox_store,
        "_download_one_image_bytes",
        lambda url: (b"FAKEJPEGDATA", "jpg"),
    )
    row = {
        "id": "jg_note_1",
        "platform": "juguang",
        "source_channel": "聚光内容广场",
        "juguang_category": "客资收集",
        "title": "杭州周边团建别墅推荐",
        "desc": "适合20-40人公司轰趴团建。",
        "topics": ["杭州团建", "公司轰趴"],
        "author": "杭州团建管家",
        "keyword": "杭州团建",
        "reads": 12400,
        "likes": 88,
        "comments": 19,
        "favorites": 140,
        "shares": 12,
        "image_urls": ["https://sns-img.xhscdn.com/1.jpg"],
    }
    toolbox_store.record_discovered_artworks([row], platform="juguang", source="collection")
    info, err = toolbox_store._download_single_artwork_row(row, str(tmp_path / "downloads"))
    assert not err and info
    pkg = Path(info["save_path"])
    copy_txt = (pkg / "文案.txt").read_text(encoding="utf-8")
    assert "杭州周边团建别墅推荐" in copy_txt
    assert "适合20-40人公司轰趴团建" in copy_txt
    assert "#杭州团建" in copy_txt

    meta = json.loads((pkg / "metadata.json").read_text(encoding="utf-8"))
    assert meta["reads_count"] == 12400
    assert meta["juguang_category"] == "客资收集"
    assert meta["source_channel"] == "聚光内容广场"
    assert meta["topics"] == ["杭州团建", "公司轰趴"]

    exported = toolbox_store.mutate_artworks("export_csv", {"mode": "history"})
    parsed_csv = list(csv.reader(io.StringIO(exported["csv"])))
    header = parsed_csv[0]
    assert "阅读量" in header
    assert "正文文案" in header
    assert "话题标签" in header
    assert "聚光分类" in header
    assert "来源渠道" in header
    data_row = next(r for r in parsed_csv[1:] if r[header.index("标题")] == "杭州周边团建别墅推荐")
    assert data_row[header.index("阅读量")] == "12400"
    assert "杭州团建" in data_row[header.index("话题标签")]


def test_collect_juguang_keyword_end_to_end_and_gate(monkeypatch, tmp_path):
    eng = native_collector.NativeBrowserCollector(profile_dir=tmp_path / "prof")
    eng._call_browser = lambda fn, timeout=30.0: fn()

    class FakeLoc:
        def count(self):
            return 0

    class FakePage:
        def __init__(self):
            self.listeners = {}

        def on(self, ev, fn):
            self.listeners.setdefault(ev, []).append(fn)

        def off(self, ev, fn):
            if ev in self.listeners and fn in self.listeners[ev]:
                self.listeners[ev].remove(fn)

        def goto(self, url, **kw):
            return None

        def wait_for_timeout(self, ms):
            return None

        def locator(self, sel):
            return FakeLoc()

        def get_by_text(self, *a, **kw):
            return FakeLoc()

        def evaluate(self, script):
            return {
                "href": "https://ad.xiaohongshu.com/microapp/creativity/inspire",
                "title": "内容广场 - 小红书聚光",
                "verification": False,
                "login_required": False,
                "cards": [
                    {
                        "id": "note_dom_1",
                        "url": "https://www.xiaohongshu.com/explore/note_dom_1",
                        "title": "江浙沪冬日温泉团建",
                        "author": "聚光作者",
                        "reads": "5600",
                        "likes": "92",
                        "favorites": "120",
                        "comments": "15",
                        "is_video": False,
                        "is_photo": True,
                        "image_count": 2,
                        "image_urls": ["https://sns-img.xhscdn.com/a.jpg", "https://sns-img.xhscdn.com/b.jpg"],
                    }
                ],
            }

    fake_page = FakePage()
    eng._ensure_page_in_worker = lambda proxy_url="": fake_page
    monkeypatch.setattr(
        native_collector,
        "_fetch_xhs_note_ssr_detail",
        lambda url, timeout=10.0: {
            "title": "江浙沪冬日温泉团建完整版",
            "desc": "详细行程安排与人均预算。",
            "topics": ["江浙沪团建", "温泉民宿"],
            "caption": "江浙沪冬日温泉团建完整版\n\n详细行程安排与人均预算。\n\n#江浙沪团建 #温泉民宿",
            "image_urls": ["https://sns-img.xhscdn.com/a.jpg", "https://sns-img.xhscdn.com/b.jpg"],
            "live_photo_urls": [],
            "success": True,
        },
    )

    res = eng.collect_juguang_keyword(
        "江浙沪团建",
        count=5,
        min_images=1,
        max_images=20,
        direct_download=False,
        juguang_category="客资收集",
        web_sort="阅读量",
        web_publish_time="近7日",
    )
    assert res["success"] is True
    assert res["status"] == "completed"
    assert len(res["candidates"]) == 1
    cand = res["candidates"][0]
    assert cand["platform"] == "juguang"
    assert cand["juguang_category"] == "客资收集"
    assert cand["desc"] == "详细行程安排与人均预算。"
    assert cand["topics"] == ["江浙沪团建", "温泉民宿"]

    # Login gate triggers paused job cleanly
    gate_events = []
    fake_page.evaluate = lambda script: {
        "href": "https://ad.xiaohongshu.com/login",
        "title": "登录 - 小红书聚光",
        "verification": False,
        "login_required": True,
        "cards": [],
    }
    eng._bring_to_front_in_worker = lambda **kw: 1
    gate_res = eng.collect_juguang_keyword(
        "江浙沪团建",
        juguang_category="客资收集",
        web_sort="阅读量",
        web_publish_time="近7日",
        on_gate_cb=lambda st, msg: gate_events.append((st, msg)),
    )
    assert gate_res["status"] == "login_required"
    assert gate_events and gate_events[0][0] == "login_required"
    paused = eng.consume_paused_job()
    assert paused and paused["platform"] == "juguang" and paused["juguang_category"] == "客资收集"


def test_ui_template_has_juguang_controls():
    html = ui_template.TEMPLATE
    assert 'data-plat="juguang"' in html
    assert 'id="k_juguang_category"' in html
    assert 'id="k_juguang_time"' in html
    assert 'id="k_juguang_sort"' in html
    assert "open_platform_login',{platform:'juguang'}" in html
