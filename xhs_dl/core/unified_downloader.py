"""One ordered downloader for Xiaohongshu and Douyin share links."""

import random
import time
from pathlib import Path

from .cn_short_video_downloader import CnShortVideoEngine
from .douyin_downloader import DouyinBrowserEngine
from .generic_downloader import YtDlpEngine
from .models import DownloadResult, NoteResult
from .pacing import AdaptiveRetryPolicy, blocking_failure_kind
from .platforms import detect_platform
from xhs_dl.storage import download_claim
from .v2_downloader import LocalCliEngine


class UnifiedDownloader:
    def __init__(
        self,
        output_dir="./downloads",
        delay=(8, 15),
        on_progress=None,
        engine_home=None,
        timeout=300,
        image_format="keep",
        max_images=15,
        engines=None,
        adaptive=False,
        pause_on_barrier=False,
    ):
        self.output_dir = output_dir
        self.delay = delay
        self.on_progress = on_progress
        self.engine_home = engine_home
        self.timeout = timeout
        self.image_format = image_format
        self.max_images = max_images
        self.engines = dict(engines or {})
        self._owned_engines = []
        self._reuse_browser = False
        self.adaptive = bool(adaptive)
        self.pause_on_barrier = pause_on_barrier
        self.retry_policy = AdaptiveRetryPolicy()

    def _engine(self, platform):
        if platform not in self.engines:
            if platform == "xhs":
                engine = LocalCliEngine(
                    self.engine_home, timeout=self.timeout, image_format=self.image_format, max_images=self.max_images
                )
                self.engines[platform] = engine
                self._owned_engines.append(engine)
            elif platform == "douyin":
                engine = DouyinBrowserEngine(
                    timeout=min(self.timeout, 90),
                    image_format=self.image_format,
                    reusable_browser=self._reuse_browser,
                )
                self.engines[platform] = engine
                self._owned_engines.append(engine)
            elif platform == "cn_video":
                engine = CnShortVideoEngine(
                    timeout=min(self.timeout, 90), image_format=self.image_format
                )
                self.engines[platform] = engine
                self._owned_engines.append(engine)
            elif platform == "generic":
                engine = YtDlpEngine(
                    timeout=self.timeout, image_format=self.image_format
                )
                self.engines[platform] = engine
                self._owned_engines.append(engine)
        return self.engines.get(platform)

    def close(self):
        """Close any internally created engines (for example reusable Playwright browsers)."""
        for engine in list(self._owned_engines):
            close_fn = getattr(engine, "close", None)
            if callable(close_fn):
                try:
                    close_fn()
                except Exception:
                    pass
        self._owned_engines.clear()
        for key in list(self.engines):
            if getattr(self.engines[key], "reusable_browser", False):
                self.engines.pop(key, None)

    def download(self, urls):
        seen = set()
        unique = []
        for url in urls:
            key = url.rstrip("/")
            if key not in seen:
                seen.add(key)
                unique.append(url)

        douyin_count = sum(1 for url in unique if detect_platform(url) == "douyin")
        self._reuse_browser = douyin_count > 1

        root = Path(self.output_dir)
        root.mkdir(parents=True, exist_ok=True)
        result = DownloadResult(output_dir=str(root.resolve()))
        try:
            for index, url in enumerate(unique, 1):
                barrier = ""
                platform = detect_platform(url)
                with download_claim(url) as existing:
                    if existing:
                        item = NoteResult(
                            url=url,
                            note_id=str(existing.get("笔记ID") or ""),
                            title=str(existing.get("标题") or "已下载素材"),
                            save_dir=str(existing.get("保存位置") or ""),
                            engine="history",
                            deduplicated=True,
                        )
                    else:
                        engine = self._engine(platform)
                        if engine is None:
                            item = NoteResult(url=url, error="暂不支持这个链接来源")
                        else:
                            retries_done = 0
                            while True:
                                try:
                                    item = engine.download_one(url, root)
                                except Exception as exc:
                                    item = NoteResult(url=url, error=str(exc), engine=platform)
                                if self.pause_on_barrier and not item.success:
                                    barrier = blocking_failure_kind(item.error, item.http_status)
                                if (
                                    barrier
                                    or not self.adaptive
                                    or item.success
                                    or not self.retry_policy.should_retry(
                                        item.error, retries_done=retries_done
                                    )
                                ):
                                    break
                                retries_done += 1
                                time.sleep(
                                    self.retry_policy.retry_delay(item.error, retries_done)
                                )
                result.results.append(item)
                if self.on_progress:
                    self.on_progress(item, index, len(unique))
                if barrier:
                    result.pause_reason = barrier
                    break
                if index < len(unique) and not item.deduplicated:
                    if self.adaptive:
                        time.sleep(
                            self.retry_policy.next_item_delay(
                                item.success, item.error
                            )
                        )
                    else:
                        time.sleep(random.uniform(*self.delay))
            return result
        finally:
            self.close()
