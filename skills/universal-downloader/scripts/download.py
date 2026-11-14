#!/usr/bin/env python3
"""Stable JSON interface for Codex and OpenClaw callers."""

import argparse
import json
import sys
from pathlib import Path


def emit_payload(payload) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_args():
    parser = argparse.ArgumentParser(description="Download supported public social-media works")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Share text or one/more URLs")
    source.add_argument("--file", help="UTF-8 file containing share text or URLs")
    parser.add_argument("--output", default="./universal_downloads")
    parser.add_argument(
        "--mode", default="cautious",
        choices=["fast", "normal", "cautious", "slow", "very-slow"],
    )
    parser.add_argument("--engine-home")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--progress-file",
        help="append one UTF-8 JSONL event after each URL; final JSON remains on stdout",
    )
    return parser.parse_args()


def _progress_callback(progress_file, output_directory=None):
    if not progress_file:
        return None
    path = Path(progress_file)
    output_root = Path(output_directory).expanduser().resolve() if output_directory else None

    def emit(item, index, total):
        relative_save_dir = ""
        if output_root is not None:
            try:
                save_dir = Path(str(getattr(item, "save_dir", "") or "")).expanduser().resolve()
                relative_save_dir = save_dir.relative_to(output_root).as_posix()
            except (OSError, ValueError):
                pass
        event = {
            "type": "item_complete",
            "index": int(index),
            "total": int(total),
            "success": bool(getattr(item, "success", False)),
            "title": str(getattr(item, "title", "") or "")[:300],
            "note_id": str(getattr(item, "note_id", "") or "")[:100],
            "image_count": int(getattr(item, "image_count", 0) or 0),
            "engine": str(getattr(item, "engine", "") or "")[:60],
            "save_dir": relative_save_dir[:500],
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                stream.flush()
        except OSError:
            # Progress is advisory; a progress file failure must not interrupt
            # an otherwise valid public-media download.
            return

    return emit


def extract_urls(text):
    """Use the same URL grammar as the desktop/web/core download paths."""
    from xhs_dl.core.downloader import extract_urls_from_text

    return extract_urls_from_text(text or "")


def main() -> int:
    args = parse_args()
    try:
        from xhs_dl.core.downloader import DELAY_MODES
        from xhs_dl.core.unified_downloader import UnifiedDownloader
        from xhs_dl.storage import history_path
    except ImportError as exc:
        emit_payload({
            "success": 0,
            "failed": 1,
            "error": f"xhs-dl is not installed: {exc}",
        })
        return 2

    text = args.text
    if args.file:
        try:
            text = Path(args.file).read_text(encoding="utf-8")
        except OSError as exc:
            emit_payload({"success": 0, "failed": 1, "error": str(exc)})
            return 2
    urls = extract_urls(text)
    if not urls:
        emit_payload({"success": 0, "failed": 1, "error": "No supported URL found"})
        return 2

    try:
        downloader = UnifiedDownloader(
            output_dir=args.output,
            delay=DELAY_MODES[args.mode],
            on_progress=_progress_callback(args.progress_file, args.output),
            engine_home=args.engine_home,
            timeout=args.timeout,
        )
        result = downloader.download(urls)
    except Exception as exc:
        emit_payload({"success": 0, "failed": len(urls), "error": str(exc)})
        return 2

    payload = {
        "success": result.success_count,
        "failed": result.fail_count,
        "total": result.total,
        "output_dir": result.output_dir,
        "history": str(history_path()),
        "items": [
            {
                "url": item.url,
                "success": item.success,
                "title": item.title,
                "note_id": item.note_id,
                "save_dir": item.save_dir,
                "image_count": item.image_count,
                "media_format": item.media_format,
                "error": item.error,
            }
            for item in result.results
        ],
    }
    emit_payload(payload)
    return 0 if result.fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
