# -*- coding: utf-8 -*-
"""V2 无水印下载器。

通过独立安装的 XHS-Downloader CLI 获取原始媒体。第三方引擎保持独立目录，
避免把 GPL 源码复制进本项目；本模块只负责进程调用、逐条进度与本地结果清单。
"""

import json
import logging
import os
import random
import re
import subprocess
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .downloader import DELAY_MODES, extract_urls_from_text
from .models import DownloadResult, NoteResult
from .media_names import convert_image_file, media_filename, media_sort_key, normalize_stat_count
from xhs_dl.storage import add_history, download_claim

logger = logging.getLogger(__name__)

MEDIA_EXTENSIONS = {".png", ".webp", ".jpg", ".jpeg", ".heic", ".mp4", ".mov"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
METADATA_MARKER = "__XHS_DL_METADATA__"


class EngineNotReady(RuntimeError):
    """本地无水印引擎尚未安装或不可运行。"""


class LocalCliEngine:
    """XHS-Downloader 的本地 CLI 适配器。"""

    def __init__(self, home: Optional[str] = None, timeout: int = 300, image_format: str = "jpg", max_images: int = 15):
        self.home = self._discover_home(home)
        self.timeout = timeout
        self.image_format = image_format
        self.max_images = max_images
        self.python = self._discover_python()

    @staticmethod
    def _discover_home(explicit: Optional[str]) -> Path:
        candidates = []
        if explicit:
            candidates.append(Path(explicit))
        if os.environ.get("XHS_DOWNLOADER_HOME"):
            candidates.append(Path(os.environ["XHS_DOWNLOADER_HOME"]))

        project_root = Path(__file__).resolve().parents[2]
        candidates.extend([
            project_root / "vendor" / "XHS_Downloader",
            project_root.parent / "XHS_Downloader",
            Path(r"D:\AICode\工具开发\projects\XHS_Downloader"),
        ])
        for path in candidates:
            path = path.expanduser().resolve()
            if (path / "main.py").is_file() and (path / "source").is_dir():
                return path
        raise EngineNotReady(
            "未找到本地无水印引擎。请先运行 setup-v2.ps1，或用 "
            "--engine-home 指定 XHS_Downloader 目录。"
        )

    def _discover_python(self) -> Path:
        candidates = [
            self.home / ".venv" / "Scripts" / "python.exe",
            self.home / "venv" / "Scripts" / "python.exe",
        ]
        for path in candidates:
            if path.is_file():
                return path
        raise EngineNotReady(
            f"{self.home} 缺少隔离运行环境。请在该目录运行 python -m uv sync --no-dev。"
        )

    @staticmethod
    def _subprocess_environment(engine_home: Path) -> dict:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(engine_home)
        for pkey in list(environment.keys()):
            if pkey.lower() in ("http_proxy", "https_proxy", "all_proxy"):
                environment.pop(pkey, None)
        for key, value in list(environment.items()):
            if key.lower() != "no_proxy":
                continue
            # httpx 0.28 treats bare IPv6 NO_PROXY entries such as ::1 as
            # host:port patterns and raises InvalidURL before making a request.
            entries = [item.strip() for item in value.split(",") if item.strip()]
            environment[key] = ",".join(item for item in entries if item.count(":") < 2)
        return environment

    @staticmethod
    def _canonicalize_source_url(url: str) -> str:
        """Map the current xhslink.cn alias to the host understood by upstream."""
        return re.sub(
            r"(?i)^(https?://)(www\.)?xhslink\.cn(?=/)",
            r"\1\2xhslink.com",
            url,
            count=1,
        )

    @staticmethod
    def _media_files(root: Path, *, max_depth: Optional[int] = None) -> dict:
        result = {}
        for directory, subdirectories, filenames in os.walk(root, followlinks=False):
            folder = Path(directory)
            if max_depth is not None and len(folder.relative_to(root).parts) >= max_depth:
                subdirectories.clear()
            for name in filenames:
                path = folder / name
                if path.suffix.lower() not in MEDIA_EXTENSIONS:
                    continue
                try:
                    info = path.stat()
                    result[path.resolve()] = (info.st_size, info.st_mtime_ns)
                except OSError:
                    continue
        return result

    def download_one(self, url: str, output_dir: Path) -> NoteResult:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        before = self._media_files(output_dir)
        parent_dir = output_dir.parent
        before_parent = self._media_files(parent_dir, max_depth=2)
        bridge = Path(__file__).resolve().parents[1] / "engine_bridge.py"
        command = [
            str(self.python), str(bridge),
            "--url", self._canonicalize_source_url(url),
            "--work-path", str(output_dir.parent),
            "--folder-name", output_dir.name,
            "--max-images", str(self.max_images),
        ]
        environment = self._subprocess_environment(self.home)
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.home),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                env=environment,
            )
        except subprocess.TimeoutExpired:
            self._remove_engine_database(output_dir)
            return NoteResult(url=url, error=f"本地引擎超过 {self.timeout} 秒未完成", engine="local-cli")
        self._remove_engine_database(output_dir)

        stdout = (completed.stdout or "") + (completed.stderr or "")
        clean_stdout = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", stdout)
        metadata = self._extract_metadata(clean_stdout)

        # 检查前置熔断拦截：如果因图片超限被熔断，直接返回拦截结果，无需执行文件落地
        if metadata.get("_intercepted"):
            intercept_msg = metadata.get("_intercept_reason", f"图片数量超过限制({self.max_images}张)，前置熔断已跳过")
            title = str(metadata.get("作品标题") or "")
            author = str(metadata.get("作者昵称") or "")
            note_id = str(metadata.get("作品ID") or "")
            logger.warning(f"触发前置熔断拦截: 《{title}》- {intercept_msg}")
            return NoteResult(
                url=url,
                note_id=note_id,
                title=title,
                author=author,
                error=intercept_msg,
                engine="local-cli",
            )

        after = self._media_files(output_dir)
        new_files = sorted(
            path for path, signature in after.items()
            if path not in before or before[path] != signature
        )
        note_id_match = re.search(r"开始处理作品[：:]\s*([a-f0-9]{24})", clean_stdout)
        note_id = str(metadata.get("作品ID") or (note_id_match.group(1) if note_id_match else ""))

        # 上游会主动跳过已存在文件。通过输出中的完整文件名映射回本地结果，
        # 让重复运行成为成功的幂等操作，而不是误报“未生成文件”。
        selected_files = new_files
        if not selected_files and "文件已存在" in clean_stdout:
            selected_files = sorted(
                path for path in after
                if path.name in clean_stdout
            )
        if not selected_files and metadata:
            expected = self._expected_note_dir(output_dir, metadata)
            selected_files = sorted(
                path for path in after
                if path.parent == expected and path.suffix.lower() in MEDIA_EXTENSIONS
            )

        if not selected_files:
            # 上游 2.9 会清洗 folder_name（例如吞掉前导下划线）并把媒体写到同级目录，
            # 导致 output_dir 里空空如也、被误判为"未生成素材目录"。
            # 兜底：按"本次运行期间新增/变化"扫父目录，定位真实落盘目录。
            after_parent = self._media_files(parent_dir, max_depth=2)
            fresh = [
                path for path, signature in after_parent.items()
                if before_parent.get(path) != signature
            ]
            if fresh:
                candidate_dirs = [p.parent for p in fresh]
                note_dir_guess = max(set(candidate_dirs), key=candidate_dirs.count)
                selected_files = sorted(p for p in fresh if p.parent == note_dir_guess)

        if not selected_files:
            detail = self._last_useful_line(clean_stdout)
            return NoteResult(
                url=url,
                note_id=note_id,
                error=detail or f"本地引擎未生成媒体文件（退出码 {completed.returncode}）",
                engine="local-cli",
            )

        note_dirs = [p.parent for p in selected_files]
        note_dir = max(set(note_dirs), key=note_dirs.count)
        note_dir, selected_files = self._rename_note_folder(note_dir, selected_files, metadata)
        image_files = [p for p in selected_files if p.suffix.lower() not in VIDEO_EXTENSIONS]
        title = str(metadata.get("作品标题") or self._title_from_folder(note_dir.name))
        author = str(metadata.get("作者昵称") or "")
        description = str(metadata.get("作品描述") or "")
        topics = str(metadata.get("作品标签") or "")
        selected_files = self._rename_media_files(selected_files, title, self.image_format)
        result = NoteResult(
            url=url,
            success=True,
            note_id=note_id,
            title=title,
            author=author,
            likes=str(metadata.get("点赞数量") or ""),
            collections=str(metadata.get("收藏数量") or ""),
            comments=str(metadata.get("评论数量") or ""),
            note_type="video" if any(p.suffix.lower() in VIDEO_EXTENSIONS for p in selected_files) else "normal",
            save_dir=str(note_dir),
            image_count=len(image_files),
            image_success=len(image_files),
            desc=description,
            topics=topics,
            engine="local-cli",
            media_format=", ".join(sorted({p.suffix.lstrip(".").upper() for p in selected_files})),
        )
        self._write_copy_text(note_dir, result)
        add_history(url, result.note_id, result.title, result.save_dir)
        return result

    @staticmethod
    def _remove_engine_database(output_dir: Path) -> None:
        database = output_dir / "ExploreData.db"
        try:
            if database.is_file():
                database.unlink()
        except OSError:
            logger.warning("无法清理上游空数据文件：%s", database)

    @staticmethod
    def _extract_metadata(text: str) -> dict:
        for line in reversed(text.splitlines()):
            if line.startswith(METADATA_MARKER):
                try:
                    value = json.loads(line[len(METADATA_MARKER):])
                    return value if isinstance(value, dict) else {}
                except json.JSONDecodeError:
                    return {}
        return {}

    @staticmethod
    def _safe_name(value: str, limit: int = 56) -> str:
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .-")
        return value[:limit] or "未知"

    @classmethod
    def _rename_note_folder(cls, note_dir: Path, files: List[Path], metadata: dict):
        if not metadata:
            return note_dir, files
        comments = normalize_stat_count(metadata.get("评论数量"), limit=16)
        likes = normalize_stat_count(metadata.get("点赞数量"), limit=16)
        title = cls._safe_name(metadata.get("作品标题") or "未命名笔记")
        author = cls._safe_name(metadata.get("作者昵称") or "未知作者", 32)
        desired = note_dir.parent / f"评{comments}-赞{likes}-{title}-{author}"
        if desired != note_dir:
            if desired.exists():
                merged = []
                for path in files:
                    target = desired / path.relative_to(note_dir)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        path.unlink()
                    else:
                        path.rename(target)
                    merged.append(target)
                try:
                    note_dir.rmdir()
                except OSError:
                    pass
                files = merged
            else:
                note_dir.rename(desired)
                files = [desired / path.relative_to(note_dir) for path in files]
            note_dir = desired
        return note_dir, files

    @classmethod
    def _expected_note_dir(cls, output_dir: Path, metadata: dict) -> Path:
        comments = normalize_stat_count(metadata.get("评论数量"), limit=16)
        likes = normalize_stat_count(metadata.get("点赞数量"), limit=16)
        title = cls._safe_name(metadata.get("作品标题") or "未命名笔记")
        author = cls._safe_name(metadata.get("作者昵称") or "未知作者", 32)
        return output_dir / f"评{comments}-赞{likes}-{title}-{author}"

    @staticmethod
    def _rename_media_files(files: List[Path], title: str, image_format: str = "jpg") -> List[Path]:
        renamed = []
        ordered = sorted(files, key=media_sort_key)
        images = [path for path in ordered if path.suffix.lower() not in VIDEO_EXTENSIONS]
        videos = [path for path in ordered if path.suffix.lower() in VIDEO_EXTENSIONS]
        for index, path in enumerate(images):
            path = convert_image_file(path, image_format)
            target = path.with_name(
                media_filename(index, title, path.suffix, is_video=False)
            )
            if target != path:
                path.replace(target)
            renamed.append(target)
        for index, path in enumerate(videos):
            target = path.with_name(
                media_filename(index, title, path.suffix, is_video=True)
            )
            if target != path:
                path.replace(target)
            renamed.append(target)
        return renamed

    @staticmethod
    def _last_useful_line(text: str) -> str:
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.strip().startswith(METADATA_MARKER)
        ]
        # The CLI prints a generic aggregate summary after its per-item error.
        # Prefer the actual failed item so the bridge/UI can explain the cause.
        for line in reversed(lines):
            match = re.search(r"\[(?:FAIL|ERROR)\]\s*\[\d+/\d+\]\s*(.+)$", line, re.I)
            if match:
                return match.group(1).strip()[:300]
        summary = re.compile(r"(?:完成\s*)?(?:成功\s*[:：]?\s*\d+.*失败\s*[:：]?\s*\d+|共处理\s*\d+\s*个作品)", re.I)
        for line in reversed(lines):
            if not summary.search(line):
                return line[:300]
        return lines[-1][:300] if lines else ""

    @staticmethod
    def _title_from_folder(name: str) -> str:
        # 默认命名是“日期_时间_作者_标题”；仅剥离稳定的日期时间前缀。
        return re.sub(r"^\d{4}-\d{2}-\d{2}_\d{2}\.\d{2}\.\d{2}_", "", name)

    @staticmethod
    def _write_copy_text(note_dir: Path, result: NoteResult) -> None:
        # 严格遵守三大解耦铁律：文案.txt 仅保留纯正文+话题，零人工标签
        parts = []
        if result.title:
            parts.append(result.title.strip())
        if result.desc and result.desc.strip() != (result.title or '').strip():
            parts.append(result.desc.strip())
        if result.topics:
            t_str = ' '.join(t if t.startswith('#') else '#' + t for t in result.topics.split() if t)
            if t_str:
                parts.append(t_str)
        content = '\n\n'.join(parts) + '\n' if parts else '（正文为空）\n'
        (note_dir / '文案.txt').write_text(content, encoding='utf-8-sig')


class XhsV2Downloader:
    """逐条调用本地无水印引擎，支持批量、去重、延时与进度回调。"""

    def __init__(self, output_dir: str = "./xhs_downloads",
                 delay: Tuple[float, float] = DELAY_MODES["cautious"],
                 on_progress: Optional[Callable] = None,
                 engine_home: Optional[str] = None,
                 timeout: int = 300, image_format: str = "jpg"):
        self.output_dir = output_dir
        self.delay = delay
        self.on_progress = on_progress
        self.engine = LocalCliEngine(engine_home, timeout=timeout, image_format=image_format)

    def download_text(self, text: str) -> DownloadResult:
        return self.download(extract_urls_from_text(text))

    def download(self, urls: List[str]) -> DownloadResult:
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
            with download_claim(url) as existing:
                if existing:
                    note_result = NoteResult(
                        url=url,
                        note_id=str(existing.get("笔记ID") or ""),
                        title=str(existing.get("标题") or ""),
                        save_dir=str(existing.get("保存位置") or ""),
                        engine="history",
                        deduplicated=True,
                    )
                else:
                    note_result = self.engine.download_one(url, root)
            result.results.append(note_result)
            if self.on_progress:
                self.on_progress(note_result, index, len(unique))
            if index < len(unique) and not note_result.deduplicated:
                time.sleep(random.uniform(*self.delay))
        return result
