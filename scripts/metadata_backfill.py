# -*- coding: utf-8 -*-
"""元数据回填：为素材库中没有 metadata.json 的历史素材目录补齐元数据。

信息来源（不上网、不猜平台数据）：
1. 目录名：评{评论数}-赞{点赞数}-{可选抖音ID}{标题}-{作者}
2. 文案.txt：首段作标题，全文作 content_preview / content_length
3. 路径：一级货架 → season / traffic_type / city
4. 文件清单：真实图片/视频文件名
"""
import json
import os
import re
import sys
import time
import traceback

ROOT = r"D:\AICode\项目推进/projects\江湖有旅人\主项目\01-素材库"
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".mp4", ".mov"}
VIDEO_EXT = {".mp4", ".mov"}
SKIP_PARTS = ("_", "已清理废弃素材")
SEASONS = ("春季", "夏季", "秋季", "冬季")
CITY_PARTS_SKIP = {"大合集", "团建游戏", "精准流量", "泛流量"}


def parse_folder_name(name):
    m = re.match(r"^评(\d+)-赞(\d+)-(.+)$", name)
    if not m:
        return 0, 0, "", "", ""
    comments = int(m.group(1))
    likes = int(m.group(2))
    rest = m.group(3)
    note_id = ""
    idm = re.match(r"^(\d{15,20})(.*)$", rest)
    if idm:
        note_id = idm.group(1)
        rest = idm.group(2)
    # 作者：最后一个"-"后的短词（允许中英文数字下划线，2~20字）
    author = ""
    if "-" in rest:
        head, tail = rest.rsplit("-", 1)
        if 2 <= len(tail) <= 20 and re.fullmatch(r"[\w\u4e00-\u9fa5·♨️🍁⭐]+", tail or "") and " " not in tail:
            author = tail
            rest = head
    return comments, likes, note_id, rest.strip(), author


def read_copy_file(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def backfill_one(dirpath, filenames):
    name = os.path.basename(dirpath)
    comments, likes, note_id, title_from_name, author = parse_folder_name(name)

    copy_txt = ""
    copy_file = next((f for f in filenames if f.lower().endswith(".txt") and "文案" in f), "")
    if copy_file:
        copy_txt = read_copy_file(os.path.join(dirpath, copy_file))

    # 标题优先级：文案首段 > 目录名标题
    title_from_txt = ""
    if copy_txt:
        first = re.split(r"[\r\n]", copy_txt, maxsplit=1)[0].strip()
        # 文案首段通常很短且含话题，取前 60 字
        title_from_txt = first[:60]
    title = title_from_name or title_from_txt or name

    media = sorted(f for f in filenames if os.path.splitext(f)[1].lower() in MEDIA_EXT)
    videos = [f for f in media if os.path.splitext(f)[1].lower() in VIDEO_EXT]
    images = [f for f in media if f not in videos]

    parts = dirpath.split(os.sep)
    season = next((s for s in SEASONS if any(p.startswith(s) for p in parts)), "四季通用")
    shelf = parts[0] if parts else ""
    traffic_type = ""
    if "精准流量" in parts:
        traffic_type = "精准流量"
    elif any("泛流量" in p for p in parts):
        traffic_type = "泛流量"
    city = ""
    for i, p in enumerate(parts):
        if p in ("精准流量", "泛流量") and i + 1 < len(parts) - 1:
            nxt = parts[i + 1]
            if nxt not in CITY_PARTS_SKIP:
                city = nxt
            break

    try:
        downloaded_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(dirpath)))
    except OSError:
        downloaded_at = ""

    platform = "抖音" if note_id else "小红书"

    metadata = {
        "title": title,
        "author": author,
        "likes_count": likes,
        "comments_count": comments,
        "city": city,
        "traffic_type": traffic_type,
        "category": city,
        "season": season,
        "is_unclassified": False,
        "collection_mode": "legacy",
        "source": "历史素材回填",
        "engine": "",
        "platform": platform,
        "note_id": note_id,
        "tags": [t for t in ["回填元数据", f"{platform}图文", traffic_type, city, f"{season}素材"] if t],
        "downloaded_at": downloaded_at,
        "images_count": len(images),
        "images_list": images,
        "videos_count": len(videos),
        "videos_list": videos,
        "content_length": len(copy_txt),
        "content_preview": re.sub(r"\s+", " ", copy_txt)[:120] if copy_txt else "",
        "copy_file": copy_file,
        "backfill": {
            "by": "metadata-backfill-20261106",
            "reason": "该素材目录缺失 metadata.json，本次从目录名+文案.txt+路径货架回填",
            "confidence": "高（含文案）" if copy_txt else "中（仅目录名与路径）",
            "note": "互动数据(赞/评)取目录名快照，可能与线上现值不一致；链接缺失，无法回填 share_url",
        },
    }
    out = os.path.join(dirpath, "metadata.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    return {"path": dirpath, "title": title, "platform": platform, "images": len(images), "has_copy": bool(copy_txt)}


def main():
    done, skipped, errors = [], [], []
    t0 = time.time()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = os.path.relpath(dirpath, ROOT)
        if rel == "." or any(p.startswith(SKIP_PARTS) for p in rel.split(os.sep)):
            continue
        if "metadata.json" in filenames:
            continue
        if not any(os.path.splitext(f)[1].lower() in MEDIA_EXT for f in filenames):
            continue
        try:
            # 写入前再防一次竞态
            if os.path.isfile(os.path.join(dirpath, "metadata.json")):
                continue
            done.append(backfill_one(dirpath, filenames))
        except Exception as e:
            errors.append({"path": dirpath, "error": f"{type(e).__name__}: {e}"})
    report = {
        "run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "root": ROOT,
        "backfilled": len(done),
        "errors": len(errors),
        "cost_seconds": round(time.time() - t0, 1),
        "by_platform": {"抖音": sum(1 for d in done if d["platform"] == "抖音"),
                        "小红书": sum(1 for d in done if d["platform"] == "小红书")},
        "with_copy_txt": sum(1 for d in done if d["has_copy"]),
        "error_samples": errors[:10],
    }
    rp = os.path.join(ROOT, f"_metadata_backfill_report_{int(time.time())}.json")
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
