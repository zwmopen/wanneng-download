"""One ordered downloader for Xiaohongshu and Douyin share links."""

import random
import time
from pathlib import Path

from .douyin_downloader import DouyinBrowserEngine
from .generic_downloader import YtDlpEngine
from .models import DownloadResult, NoteResult
from .pacing import AdaptiveRetryPolicy
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
    ):
        self.output_dir = output_dir
        self.delay = delay
        self.on_progress = on_progress
        self.engine_home = engine_home
        self.timeout = timeout
        self.image_format = image_format
        self.max_images = max_images
        self.engines = dict(engines or {})
        self.adaptive = bool(adaptive)
        self.retry_policy = AdaptiveRetryPolicy()

    def _engine(self, platform):
        if platform not in self.engines:
            if platform == "xhs":
                self.engines[platform] = LocalCliEngine(
                    self.engine_home, timeout=self.timeout, image_format=self.image_format, max_images=self.max_images
                )
            elif platform == "douyin":
                self.engines[platform] = DouyinBrowserEngine(
                    timeout=min(self.timeout, 90), image_format=self.image_format
                )
            elif platform == "generic":
                self.engines[platform] = YtDlpEngine(
                    timeout=self.timeout, image_format=self.image_format
                )
        return self.engines.get(platform)

    def download(self, urls):
        seen = set()
        unique = []
        for url in urls:
            key = url.rstrip("/")
            if key not in seen:
                seen.add(key)
                unique.append(url)

        root = Path(self.output_dir)
        root.mkdir(parents=True, exist_ok=True)
        result = DownloadResult(output_dir=str(root.resolve()))
        for index, url in enumerate(unique, 1):
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
                            if (
                                not self.adaptive
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
