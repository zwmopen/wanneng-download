"""由 XHS-Downloader 的隔离 Python 调用：一次完成下载并返回笔记元数据。"""

import argparse
import asyncio
import json
import os
import sys


MARKER = "__XHS_DL_METADATA__"


async def run(url, work_path, folder_name, max_images=15):
    sys.path.insert(0, os.getcwd())
    from source import Settings, XHS

    # 仅使用 XHS-Downloader 自己的本地设置；不读取浏览器配置，也不回显 Cookie。
    saved_settings = Settings()
    try:
        cookie = str(saved_settings.read().get("cookie") or "") if saved_settings.path.is_file() else ""
    except Exception:
        cookie = ""

    async with XHS(
        work_path=work_path,
        folder_name=folder_name,
        image_format="PNG",
        folder_mode=True,
        record_data=False,
        download_record=False,
        author_archive=False,
        language="zh_CN",
        cookie=cookie,
    ) as client:
        # 前置熔断预检：若配置了 max_images，先仅提取元数据 (download=False) 校验图片总数
        if max_images and max_images > 0:
            preview_items = await client.extract(url, download=False)
            if preview_items:
                preview = preview_items[0]
                img_urls = preview.get("下载地址", [])
                if isinstance(img_urls, str):
                    img_urls = [u for u in img_urls.split() if u]
                note_type = preview.get("作品类型", "")
                if note_type != "视频" and len(img_urls) > max_images:
                    preview["_intercepted"] = True
                    preview["_intercept_reason"] = f"图片数量超限 ({len(img_urls)}张 > {max_images}张)，触发前置熔断拦截，跳过下载"
                    print(
                        f"[前置拦截] 作品《{preview.get('作品标题', '')}》图片共 {len(img_urls)} 张，超过上限 {max_images} 张，前置熔断拒绝下载！",
                        file=sys.stderr,
                    )
                    print(MARKER + json.dumps(preview, ensure_ascii=False, default=str))
                    return

        items = await client.extract(url, download=True)
    payload = items[0] if items else {}
    print(MARKER + json.dumps(payload, ensure_ascii=False, default=str))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--work-path", required=True)
    parser.add_argument("--folder-name", required=True)
    parser.add_argument("--max-images", type=int, default=15, help="单篇笔记图片张数上限，超过则前置熔断拒绝下载")
    args = parser.parse_args()
    asyncio.run(run(args.url, args.work_path, args.folder_name, max_images=args.max_images))


if __name__ == "__main__":
    main()
