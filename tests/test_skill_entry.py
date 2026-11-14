import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "universal-downloader" / "scripts" / "download.py"


def _load_skill_entry():
    spec = importlib.util.spec_from_file_location("xhs_download_skill_entry", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_skill_json_output_is_utf8_even_when_windows_console_defaults_to_gbk(monkeypatch):
    module = _load_skill_entry()
    raw = io.BytesIO()
    gbk_stdout = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    monkeypatch.setattr(module.sys, "stdout", gbk_stdout)

    module.emit_payload({"title": "山野小院🍃"})
    gbk_stdout.flush()

    assert "山野小院🍃" in raw.getvalue().decode("utf-8")


def test_skill_uses_core_url_parser_for_chinese_share_punctuation():
    module = _load_skill_entry()
    text = "先复制一下，打开【小红书】看看这篇好文！http://xhslink.cn/o/97Pz4siAYx4》"

    assert module.extract_urls(text) == ["http://xhslink.cn/o/97Pz4siAYx4"]


def test_progress_callback_writes_sanitized_jsonl_with_relative_save_path(tmp_path):
    module = _load_skill_entry()
    output = tmp_path / "downloads"
    save_dir = output / "作品-作者"
    save_dir.mkdir(parents=True)
    progress_file = tmp_path / "events" / "progress.jsonl"
    item = SimpleNamespace(
        success=True,
        title="图文标题",
        note_id="note-123",
        image_count=4,
        engine="douyin",
        save_dir=str(save_dir),
        url="https://v.douyin.com/private-link/",
        error="private failure detail",
    )

    callback = module._progress_callback(progress_file, output)
    callback(item, 1, 2)

    event = json.loads(progress_file.read_text(encoding="utf-8").strip())
    assert event == {
        "type": "item_complete",
        "index": 1,
        "total": 2,
        "success": True,
        "title": "图文标题",
        "note_id": "note-123",
        "image_count": 4,
        "engine": "douyin",
        "save_dir": "作品-作者",
    }
    assert "private-link" not in json.dumps(event, ensure_ascii=False)
    assert "private failure detail" not in json.dumps(event, ensure_ascii=False)


def test_progress_callback_omits_save_path_outside_output_directory(tmp_path):
    module = _load_skill_entry()
    output = tmp_path / "downloads"
    outside = tmp_path / "outside"
    outside.mkdir()
    progress_file = tmp_path / "progress.jsonl"
    callback = module._progress_callback(progress_file, output)
    callback(SimpleNamespace(success=False, save_dir=str(outside)), 1, 1)

    event = json.loads(progress_file.read_text(encoding="utf-8").strip())
    assert event["save_dir"] == ""
