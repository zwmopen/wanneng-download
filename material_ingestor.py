# -*- coding: utf-8 -*-
"""Unified post-download material ingestion pipeline for MaterialHub and Jianghu.

Handles copy extraction/decoupling, interaction count parsing, ad and image
count filtering, project routing, city/traffic/season/theme classification,
metadata.json tagging, conflict-free move/copy, non-self NTFS hardlinks, and
shared download history location updates.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Mapping

try:
    from collector_paths import load_json_config, resolve_paths
except ImportError:  # pragma: no cover
    _root = Path(__file__).resolve().parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from collector_paths import load_json_config, resolve_paths

try:
    from xhs_dl.storage import find_downloaded, update_history_location
except ImportError:  # pragma: no cover
    find_downloaded = None
    update_history_location = None


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
MIN_MEDIA_BYTES = 200

DEFAULT_CITY_RULES: dict[str, list[str]] = {
    "临安": ["临安", "青山湖", "风之谷", "大明山", "天目山", "太湖源", "浙西大峡谷", "湍口"],
    "莫干山": ["莫干山", "德清", "下渚湖", "碧坞", "新市古镇", "劳岭"],
    "安吉": ["安吉", "中南百草原", "云上草原", "大竹海", "藏龙百瀑", "浙北大峡谷", "龙王山", "竹博园", "江南天池"],
    "桐庐": ["桐庐", "大奇山", "瑶琳仙境", "严子陵", "omg心跳乐园", "富春江", "垂云通天河", "深澳古村"],
    "千岛湖": ["千岛湖", "淳安", "天屿山"],
    "杭州": ["杭州", "西湖", "九溪", "良渚", "西溪", "湘湖", "富阳", "建德", "萧山", "余杭", "径山", "龙坞"],
    "湖州": ["湖州", "南浔", "龙之梦", "太湖龙之梦", "长兴", "图影", "仁皇山", "原乡小镇", "弁山"],
    "嘉兴": ["嘉兴", "乌镇", "西塘", "盐官", "海宁", "桐乡", "嘉善", "海盐", "平湖", "南湖", "南北湖"],
    "绍兴": ["绍兴", "柯桥", "诸暨", "上虞", "新昌", "安昌古镇", "鲁迅故里", "越城", "会稽山", "五泄", "嵊州"],
    "宁波": ["宁波", "余姚", "宁海", "象山", "慈溪", "奉化", "镇海", "东钱湖", "四明山", "石浦", "雪窦山"],
    "舟山": ["舟山", "普陀山", "朱家尖", "东极岛", "嵊泗", "岱山", "衢山岛", "花鸟岛", "枸杞岛"],
    "金华义乌": ["金华义乌", "义乌", "金华", "东阳", "横店", "武义", "永康", "浦江", "磐安", "兰溪"],
    "台州": ["台州", "温岭", "石塘", "仙居", "神仙居", "天台", "临海", "紫阳古街", "玉环", "三门", "小箬村"],
    "温州": ["温州", "雁荡山", "楠溪江", "洞头", "苍南", "永嘉", "泰顺", "平阳", "乐清", "瑞安", "南麂岛"],
    "丽水": ["丽水", "缙云", "仙都", "松阳", "云和梯田", "云和", "古堰画乡", "遂昌", "龙泉", "青田"],
    "衢州": ["衢州", "开化", "江山", "龙游", "廿八都", "根宫佛国"],
    "宜兴溧阳": ["宜兴溧阳", "宜兴", "溧阳", "南山竹海", "天目湖", "善卷洞", "窑湖小镇"],
    "苏州": ["苏州", "西山岛", "东山", "东山岛", "太湖", "昆山", "常熟", "同里", "周庄", "阳澄湖", "张家港", "太仓", "金鸡湖", "姑苏"],
    "南京": ["南京", "栖霞山", "牛首山", "汤山", "高淳", "江宁", "玄武湖", "紫金山", "老门东", "夫子庙", "浦口", "溧水"],
    "无锡": ["无锡", "鼋头渚", "拈花湾", "军嶂古道", "军嶂", "灵山胜境", "灵山大佛", "太湖翠屏", "江阴"],
    "常州": ["常州", "东方盐湖城", "茅山", "恐龙园", "龙凤谷", "冠嶂古道", "太湖湾", "金坛"],
    "扬州": ["扬州", "瘦西湖", "仪征", "高邮", "宝应"],
    "镇江": ["镇江", "金山寺", "西津渡", "句容", "宝华山", "焦山"],
    "南通": ["南通", "狼山", "启东", "圆陀角", "如皋", "海门", "通州湾"],
    "泰州": ["泰州", "溱湖", "兴化", "千垛", "靖江"],
    "徐州": ["徐州", "云龙湖", "窑湾古镇", "潘安湖"],
    "盐城": ["盐城", "大丰", "荷兰花海", "黄海森林", "东台"],
    "淮安": ["淮安", "洪泽湖", "盱眙"],
    "连云港": ["连云港", "花果山", "连岛"],
    "宿迁": ["宿迁", "骆马湖", "三台山"],
    "上海": ["上海", "崇明", "长兴岛", "横沙岛", "青浦", "奉贤", "金山", "淀山湖", "滴水湖", "松江", "朱家角", "佘山", "迪士尼", "嘉定", "海湾", "浦东", "宝山", "闵行"],
    "江西婺源": ["婺源", "篁岭", "婺女洲", "望仙谷", "葛仙村", "三清山", "景德镇"],
}

GAME_KEYWORDS = [
    "破冰", "互动游戏", "桌游", "团建游戏", "年会游戏", "聚会游戏",
    "晚会游戏", "惩罚游戏", "热身游戏", "室内游戏", "小游戏", "互动小游戏",
    "游戏合集", "游戏推荐", "派对游戏", "搞怪游戏", "酒桌游戏",
]

COLLECTION_KEYWORDS = [
    "大合集", "旅行合集", "周边游合集", "攻略合集", "好去处合集", "短途游",
    "周边游", "一站式畅游", "盘点", "汇总", "好去处", "自驾游路线",
    "江浙沪周边", "避暑地", "玩水地", "江浙沪游", "多城", "宝藏景点攻略合集",
    "畅游", "目的地盘点", "路线推荐", "全部码住",
]

COLLECTION_PATTERNS = [
    r"\d+[个处座条]\w*(景点|好去处|避暑地|目的地|路线)",
    r"\d+城",
    r"\d+\+?\s*宝藏景点",
    r"江浙沪\w*合集",
]

PRECISION_KEYWORDS = [
    "团建", "公司", "年会", "拓展", "策划", "方案", "hr", "会议", "轰趴", "开会",
    "定制", "企业", "党建", "工会", "团队", "部门", "团建活动", "团建方案",
    "团建策划", "团建定制", "团队建设", "破冰团建", "组织团建", "团建场地", "团建去哪",
]

SEASON_SPECS: dict[str, dict[str, Any]] = {
    "春季": {
        "cfg_key": "spring_dir",
        "standard": "03-春季专区（3—5月·踏青赏花）",
        "legacy": "春季（3—5月·智能分类）",
        "words": [
            "春季", "春天", "春日", "春游", "踏青", "赏花", "采茶", "新茶", "明前茶",
            "春茶", "挖笋", "采笋", "春笋", "青团", "放风筝", "清明", "五一", "早春",
            "海棠", "杜鹃", "郁金香", "油菜花", "樱花", "桃花", "梨花",
        ],
        "months": ["3月", "4月", "5月", "三月", "四月", "五月"],
    },
    "夏季": {
        "cfg_key": "summer_dir",
        "standard": "04-夏季专区（6—8月·溯溪漂流避暑）",
        "legacy": "夏季（6—8月·智能分类）",
        "words": [
            "夏季", "夏天", "夏日", "夏游", "避暑", "漂流", "溯溪", "玩水", "水上乐园",
            "杨梅", "采杨梅", "西瓜", "桨板", "皮划艇", "赶海", "海岛", "瀑布", "纳凉",
            "夜市", "夜游", "萤火虫", "端午", "暑假", "梅雨", "入梅", "出梅",
        ],
        "months": ["6月", "7月", "8月", "六月", "七月", "八月"],
    },
    "秋季": {
        "cfg_key": "autumn_dir",
        "standard": "01-秋季专区（9—11月·时令团建）",
        "legacy": "秋季（9—11月·智能分类）",
        "words": [
            "秋季", "秋天", "秋日", "秋游", "赏秋", "大闸蟹", "吃蟹", "品蟹", "太湖蟹",
            "开捕", "开渔", "桂花", "桂花龙井", "板栗", "柿子", "枫叶", "红枫", "银杏",
            "稻田", "割稻", "秋收", "丰收", "晒秋", "芦苇", "粉黛乱子草", "重阳", "登高",
            "赏菊", "菊花", "秋意", "秋色", "中秋", "国庆",
        ],
        "months": ["9月", "10月", "11月", "九月", "十月", "十一月"],
    },
    "冬季": {
        "cfg_key": "winter_dir",
        "standard": "02-冬季专区（12—2月·温泉滑雪年会）",
        "legacy": "冬季（12—2月·智能分类）",
        "words": [
            "冬季", "冬天", "冬日", "冬游", "滑雪", "赏雪", "冰雪", "圣诞", "春节",
            "过年", "年会", "温泉", "泡汤", "私汤", "围炉煮茶", "杀年猪", "刨猪汤",
            "烤全羊", "跨年", "元旦", "尾牙", "雾凇", "年终总结",
        ],
        "months": ["12月", "1月", "2月", "十二月", "一月", "二月"],
    },
}

THEME_RULES: list[dict[str, Any]] = [
    {"name": "01-♨️全域精选·秋冬私汤与真温泉专区", "keywords": ["温泉", "私汤", "泡汤", "汤池", "温泉民宿", "温泉酒店", "真温泉", "私汤温泉", "私汤民宿"]},
    {"name": "02-🏡江浙沪包栋轰趴与山野小院专区", "keywords": ["包栋", "小院", "独栋", "包栋小院", "轰趴馆", "独栋轰趴", "包院", "农庄包栋", "独栋小院"]},
    {"name": "03-🏊夏日泳池·溯溪玩水度假美宿", "keywords": ["泳池", "无边泳池", "恒温泳池", "玩水", "溯溪", "漂流", "溯溪玩水", "夏日避暑"]},
    {"name": "04-🍁秋日徒步与品蟹", "keywords": ["银杏", "红枫", "赏秋", "品蟹", "大闸蟹", "阳澄湖蟹", "蟹宴", "秋日银杏", "赏枫", "秋日徒步"]},
    {"name": "05-📸个人攻略C端种草", "keywords": ["个人精选", "拍照出片", "打卡机位", "机位分享", "C端种草", "拍照打卡"]},
    {"name": "06-🎉节日", "keywords": ["中秋", "国庆", "五一", "元旦", "跨年", "端午", "清明", "春节", "圣诞", "年会", "尾牙", "节庆", "节日团建"]},
    {"name": "07-🎮团建小游戏", "keywords": ["破冰", "小游戏", "团建游戏", "互动游戏", "桌游", "热身游戏", "室内游戏", "户外游戏", "破冰小游戏"]},
    {"name": "10-📚攻略与团建方案大合集", "keywords": [
        "江浙沪大合集", "江浙沪合集", "江浙沪方案", "团建方案", "两天一夜方案", "2天1夜方案",
        "方案合集", "HR抄作业", "大厂同款", "短途游大合集", "神仙目的地合集", "徒步路线合集",
        "场地合集", "团建大合集", "路线地图", "全景攻略", "地图攻略", "攻略合集",
    ]},
    {"name": "11-🍳胡闹厨房", "keywords": ["胡闹厨房", "现实版胡闹厨房", "真人胡闹厨房", "烹饪团建", "做饭团建", "厨房团建", "全员厨神"]},
]

_FOLDER_DATE_TAIL_RE = re.compile(r"-\d{4}-\d{2}-\d{2}(?:[_\s]\d{2}\.\d{2}\.\d{2})?$")
_FOLDER_STAT_RE = re.compile(
    r"^评([0-9]+(?:\.[0-9]+)?[万wWkK]?|抢首评|未知)-(?:藏([0-9]+(?:\.[0-9]+)?[万wWkK]?|未知|收藏)-)?赞([0-9]+(?:\.[0-9]+)?[万wWkK]?|赞|点赞|未知)-(.+?)(?:-([^-]+))?$"
)
_LEGACY_CN_STAT_RE = re.compile(
    r"^评论点赞-评论([0-9]+|未知|抢首评)-点赞([0-9]+|未知|赞)-(.+?)(?:-([^-]+))?$"
)
_DIRECT_FOLDER_RE = re.compile(r"^直采_(\d+)_(.*)$")
_METADATA_LINE_PREFIXES = (
    "作者：", "作者:",
    "点赞：", "点赞:",
    "评论：", "评论:",
    "收藏：", "收藏:",
    "分享：", "分享:",
    "发布时间：", "发布时间:",
    "原始链接：", "原始链接:",
    "作品 ID：", "作品 ID:", "作品ID：", "作品ID:",
    "来源：", "来源:",
)


def parse_cn_count(raw: Any) -> int:
    """Parse Chinese/compact interaction counts like '1.2万', '3k', '抢首评', or '未知'."""
    if raw is None or isinstance(raw, bool):
        return 0
    if isinstance(raw, (int, float)):
        return max(0, int(raw))
    text = str(raw).strip()
    if not text or text in {"未知", "抢首评", "赞", "点赞", "评论", "收藏", "分享", "-", "—", "无"}:
        return 0
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)\s*([万wWkK])?", text)
    if not match:
        digits = re.search(r"([0-9]+)", text)
        return int(digits.group(1)) if digits else 0
    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    if unit in {"万", "w"}:
        number *= 10000.0
    elif unit == "k":
        number *= 1000.0
    return max(0, int(round(number)))


def parse_folder_stats(folder_name: str) -> tuple[int, int, str, str]:
    """Extract (comments, likes, author, note_id) from a work folder name."""
    name = _FOLDER_DATE_TAIL_RE.sub("", str(folder_name or "").strip())
    legacy_match = _LEGACY_CN_STAT_RE.match(name)
    if legacy_match:
        comments = parse_cn_count(legacy_match.group(1))
        likes = parse_cn_count(legacy_match.group(2))
        author = str(legacy_match.group(4) or "").strip()
        return comments, likes, author, ""
    stat_match = _FOLDER_STAT_RE.match(name)
    if stat_match:
        comments = parse_cn_count(stat_match.group(1))
        likes = parse_cn_count(stat_match.group(3))
        author = str(stat_match.group(5) or "").strip()
        return comments, likes, author, ""
    direct_match = _DIRECT_FOLDER_RE.match(name)
    if direct_match:
        return 0, 0, "", direct_match.group(1)
    return 0, 0, "", ""


def sanitize_ingested_folder_name(folder_name: str, comments: int, likes: int) -> str:
    """Clean UI placeholders (评抢首评/赞赞/评论点赞-) when staging dirs are written to formal shelves."""
    raw = str(folder_name or "").strip()
    if not raw:
        return "评0-赞0-未命名作品"
    m_legacy = re.match(r"^评论点赞-评论[^\s-]+-点赞[^\s-]+-(.*)$", raw)
    if m_legacy:
        return f"评{comments}-赞{likes}-{m_legacy.group(1).strip() or '未命名作品'}"
    m_std = re.match(r"^评(抢首评|未知|\d+)-(藏[^\s-]+-)?赞(赞|点赞|未知|\d+)-(.*)$", raw)
    if m_std:
        c_raw, fav_part, l_raw, rest = m_std.group(1), m_std.group(2) or "", m_std.group(3), m_std.group(4)
        if c_raw in {"抢首评", "未知"} or l_raw in {"赞", "点赞", "未知"} or re.match(r"^(?:评|赞)\d+-", rest):
            rest_clean = re.sub(r"^(?:(?:评\d+|赞\d+)-)+", "", rest).strip() or "未命名作品"
            return f"评{comments}-{fav_part}赞{likes}-{rest_clean}"
    return raw


def _build_clean_copy(title: str, body: str, topics: str) -> str:
    parts: list[str] = []
    title_clean = title.strip()
    body_clean = body.strip()
    topics_clean = topics.strip()
    if title_clean:
        parts.append(title_clean)
    if body_clean and body_clean != title_clean:
        parts.append(body_clean)
    if topics_clean and topics_clean not in {"（无话题）", "(无话题)"}:
        if topics_clean not in body_clean and topics_clean not in title_clean:
            parts.append(topics_clean)
    return ("\n\n".join(parts) + "\n") if parts else ""


def extract_copy_and_clean(
    txt_path: Path | None,
    fallback_title: str,
    fallback_author: str = "",
) -> dict[str, Any]:
    """Read 文案.txt in either labeled or plain format and return decoupled fields."""
    raw_text = ""
    if txt_path and txt_path.is_file():
        try:
            raw_text = txt_path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            raw_text = ""

    title = ""
    author = fallback_author.strip()
    likes_raw = ""
    comments_raw = ""
    source_url = ""
    note_id = ""
    topics_line = ""
    body_lines: list[str] = []

    if raw_text:
        is_labeled = bool(
            re.search(r"^(?:标题|正文|原始链接|作品\s*ID)[：:]", raw_text, re.M)
        )
        if is_labeled:
            section = ""
            for raw_line in raw_text.splitlines():
                stripped = raw_line.strip()
                if stripped.startswith(("标题：", "标题:")):
                    title = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    section = "title"
                elif stripped in {"正文：", "正文:"}:
                    section = "body"
                elif stripped.startswith(("正文：", "正文:")):
                    val = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    if val and val != "（正文为空）":
                        body_lines.append(val)
                    section = "body"
                elif stripped in {"话题：", "话题:"}:
                    section = "topics"
                elif stripped.startswith(("话题：", "话题:")):
                    topics_line = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    section = "topics"
                elif stripped.startswith(("作者：", "作者:")):
                    author = stripped.split("：", 1)[-1].split(":", 1)[-1].strip() or author
                    section = "meta"
                elif stripped.startswith(("点赞：", "点赞:")):
                    likes_raw = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    section = "meta"
                elif stripped.startswith(("评论：", "评论:")):
                    comments_raw = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    section = "meta"
                elif stripped.startswith(("原始链接：", "原始链接:")):
                    source_url = stripped.split("：", 1)[-1].split(":", 1)[-1].strip()
                    section = "meta"
                elif stripped.startswith(("作品 ID：", "作品 ID:", "作品ID：", "作品ID:")):
                    note_id = re.split(r"[：:]", stripped, maxsplit=1)[-1].strip()
                    section = "meta"
                elif stripped.startswith(_METADATA_LINE_PREFIXES):
                    section = "meta"
                elif section == "body":
                    if stripped != "（正文为空）":
                        body_lines.append(raw_line.rstrip())
                elif section == "topics" and stripped and stripped not in {"（无话题）", "(无话题)"}:
                    topics_line = f"{topics_line} {stripped}".strip()
        else:
            non_empty_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            content_lines: list[str] = []
            for line in non_empty_lines:
                if line.startswith(_METADATA_LINE_PREFIXES):
                    if line.startswith(("原始链接：", "原始链接:")):
                        source_url = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                    elif line.startswith(("作品 ID：", "作品 ID:", "作品ID：", "作品ID:")):
                        note_id = re.split(r"[：:]", line, maxsplit=1)[-1].strip()
                    elif line.startswith(("作者：", "作者:")):
                        author = line.split("：", 1)[-1].split(":", 1)[-1].strip() or author
                    continue
                content_lines.append(line)
            if content_lines:
                title = content_lines[0]
                body_lines = content_lines[1:] if len(content_lines) > 1 else []

    if not title:
        clean_fallback = _FOLDER_DATE_TAIL_RE.sub("", fallback_title.strip())
        stat_match = _FOLDER_STAT_RE.match(clean_fallback)
        if stat_match:
            title = stat_match.group(4).strip()
        else:
            direct_match = _DIRECT_FOLDER_RE.match(fallback_title)
            if direct_match:
                title = direct_match.group(2).strip() or fallback_title
            else:
                title = fallback_title.strip()

    body = "\n".join(body_lines).strip()
    clean_copy = _build_clean_copy(title, body, topics_line)
    return {
        "title": title or "未命名作品",
        "author": author,
        "body": body,
        "topics": topics_line,
        "clean_copy": clean_copy,
        "raw_text": raw_text,
        "source_url": source_url,
        "note_id": note_id,
        "likes_count": parse_cn_count(likes_raw),
        "comments_count": parse_cn_count(comments_raw),
    }


def _find_shelf_dir(base: Path, standard_name: str, legacy_name: str) -> Path:
    for cand in (base / standard_name, base / legacy_name):
        if cand.exists():
            return cand
    prefix = standard_name.split("（", 1)[0]
    if base.exists():
        for child in base.iterdir():
            if child.is_dir() and prefix in child.name:
                return child
    return base / standard_name


def _resolve_storage_dirs(config: Mapping[str, Any], code_root: Path, config_dir: Path | None) -> dict[str, Path | dict[int, Path]]:
    paths = resolve_paths(config=config, code_root=code_root, config_dir=config_dir)
    storage = config.get("storage", {}) if isinstance(config.get("storage"), Mapping) else {}
    base = paths.material_root_dir

    precision_raw = str(storage.get("precision_dir") or "").strip()
    precision = Path(os.path.expandvars(os.path.expanduser(precision_raw))) if precision_raw else (base / "01月")
    pan_raw = str(storage.get("pan_traffic_dir") or "").strip()
    pan = Path(os.path.expandvars(os.path.expanduser(pan_raw))) if pan_raw else (base / "01月")
    theme_raw = str(storage.get("theme_dir") or "").strip()
    theme = Path(os.path.expandvars(os.path.expanduser(theme_raw))) if theme_raw else _find_shelf_dir(base, "06-主题合集", "06-主题合集（特色玩法·垂直专题）")
    hr_raw = str(storage.get("hr_dir") or "").strip()
    hr_dir = Path(os.path.expandvars(os.path.expanduser(hr_raw))) if hr_raw else (base / "行政HR图文")

    month_dirs = {m: base / f"{m:02d}月" for m in range(1, 13)}
    return {
        "material_root": base,
        "unclassified": paths.unclassified_dir,
        "doubao_material": paths.doubao_material_dir,
        "doubao_link_md": paths.doubao_link_file,
        "precision": precision,
        "pan": pan,
        "theme": theme,
        "hr_dir": hr_dir,
        "month_dirs": month_dirs,
    }


def detect_city(title: str, content: str, city_rules: Mapping[str, list[str]] | None = None) -> str:
    rules = city_rules or DEFAULT_CITY_RULES
    t_lower = str(title or "").lower()
    for city, keywords in rules.items():
        for kw in keywords:
            if kw.lower() in t_lower:
                return city

    clean_body = re.sub(r"#[^#\s]+", "", str(content or "")).lower()
    for city, keywords in rules.items():
        for kw in keywords:
            if kw.lower() in clean_body:
                return city

    full_text = f"{title} {content}".lower()
    for city, keywords in rules.items():
        for kw in keywords:
            if kw.lower() in full_text:
                return city
    return "地点待确认"


def detect_project_route(title: str, content: str, config: Mapping[str, Any] | None = None) -> str | None:
    routing = config.get("project_routing", {}) if isinstance(config, Mapping) else {}
    doubao = routing.get("doubao_pullnew", {}) if isinstance(routing, Mapping) else {}
    if not doubao or not bool(doubao.get("enabled", True)):
        return None
    keywords = [str(k).lower() for k in (doubao.get("keywords") or []) if str(k).strip()]
    if not keywords:
        return None
    full_text = f"{title} {content}".lower()
    if any(kw in full_text for kw in keywords):
        return "doubao_pullnew"
    return None


def detect_traffic_and_category(
    title: str,
    content: str,
    city_rules: Mapping[str, list[str]] | None = None,
) -> tuple[str, str]:
    t_lower = str(title or "").lower()
    c_lower = str(content or "").lower()
    full_text = f"{t_lower} {c_lower}"

    detected_city = detect_city(title, content, city_rules=city_rules)
    if detected_city == "地点待确认":
        for kw in GAME_KEYWORDS:
            if kw in t_lower or kw in c_lower:
                return "泛流量", "团建游戏"

    is_collection = any(kw in t_lower for kw in COLLECTION_KEYWORDS)
    if not is_collection:
        is_collection = any(re.search(pat, str(title or "")) for pat in COLLECTION_PATTERNS)

    if is_collection:
        if detected_city == "地点待确认" or any(
            ck in t_lower for ck in ["江浙沪", "多城", "周边游", "合集", "短途游", "码住"]
        ):
            return "泛流量", "大合集"

    if detected_city != "地点待确认":
        if any(pk in full_text for pk in PRECISION_KEYWORDS):
            return "精准流量", detected_city
        return "泛流量", detected_city

    if "江浙沪" in full_text and any(
        w in full_text for w in ["周边游", "攻略", "自驾", "合集", "路线", "去处", "避暑"]
    ):
        return "泛流量", "大合集"

    return "未分类", "地点待确认"


ALL_SEASON_LIST = ["秋季", "冬季", "春季", "夏季"]

_MI_FOLDER_STAT_PREFIX_RE = re.compile(r"^评[^\s-]+-(?:藏[^\s-]+-)?赞[^\s-]+-")
_MI_SHOP_AUTHOR_TAIL_RE = re.compile(r"^(?P<head>.+?)-(?P<tail>[^-]{1,35})$")
_MI_PERIOD_AUTHOR_HINT_RE = re.compile(
    r"作[一二三四五六七八九十七]|策划|团建|旅游|旅行|定制|民宿|公司|本地宝|可子|酱|君|行者|出行|游玩|票务|酒店|营地|农庄"
)
_MI_AGENCY_TAIL_HINT_RE = re.compile(
    r"民宿|团建|策划|旅游|旅行|票务|农庄|年会|酒店|营地|研究|定制|拓展|文化|户外|风景区|农家乐|山庄|度假|俱乐部|工作室|咨询|小旅|旅行ing|旅记|日记|客斯"
)
_MI_SEASON_CORE_RE = re.compile(
    r"攻略|指南|合集|玩法|方案|赏花|樱花|油菜花|桃花|梨花|郁金香|滑雪|赏雪|温泉|私汤|泡汤|漂流|溯溪|玩水|水上|桨板|皮划艇|海岛|海边|出海|游艇|帆船|避暑|红枫|银杏|红叶|大闸蟹|品蟹|桂花|圣诞|元旦|跨年|春节|过年|新春|清明|五一|端午|中秋|国庆|七夕|春游|踏青|秋游|赏秋|秋景"
)
_MI_STRONG_SUMMER_RE = re.compile(
    r"避暑|夏天|夏季|夏日|盛夏|初夏|漂流|溯溪|玩水|戏水|水上(?!森林)(?:乐园|运动|快乐|团建|项目|嘉年华)|泼水|泼浪"
)
_MI_STRONG_WINTER_RE = re.compile(
    r"冬季|冬天|冬日|暖冬|滑雪|赏雪|冰雪|雪景|圣诞|春节|过年|跨年|元旦|年会|尾牙"
)


def _strip_season_noise(text: str, *, is_body: bool) -> str:
    if not text:
        return ""
    s = str(text).replace("🈷", "月")
    cleaned = []
    for raw in s.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.search(r"发布时间|下载时间|采集时间|原链接|原始链接|作品\s*ID|https?://", line):
            continue
        line = re.sub(r"\s*(?:博主|作者)[：:].*$", "", line).strip()
        if not line:
            continue
        line = line.replace("消夏湾", "西山岛").replace("银杏湖", "南京游乐园")
        if is_body:
            if re.search(r"全年可约|四季皆宜|承接.*团建|主营业务|联系我们|欢迎咨询|私信我|主页更多", line):
                continue
            if len(re.findall(r"#[^\s#]+", line)) >= 4 and len(re.sub(r"#[^\s#]+", "", line).strip()) < 15:
                continue
            line = re.sub(r"20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", " ", line)
            if "。" in line:
                _h, _t = line.rsplit("。", 1)
                if len(_t.strip()) <= 28 and _MI_PERIOD_AUTHOR_HINT_RE.search(_t.strip()):
                    line = _h.strip()
        else:
            line = re.sub(r"20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", " ", line)
            cur = _MI_FOLDER_STAT_PREFIX_RE.sub("", line).strip()
            cur = re.sub(r"^\d{15,20}", "", cur).strip()
            cur = re.sub(r"^20\d{2}-\d{2}-\d{2}[_\s]+\d{2}\.\d{2}\.\d{2}_?", "", cur).strip()
            for _ in range(2):
                m = _MI_SHOP_AUTHOR_TAIL_RE.match(cur)
                if not m:
                    break
                head = m.group("head").strip()
                tail = m.group("tail").strip()
                if len(head) < 6 or not tail or re.match(r"^\d", tail):
                    break
                if _MI_AGENCY_TAIL_HINT_RE.search(tail) or not _MI_SEASON_CORE_RE.search(tail):
                    cur = head
                else:
                    break
            if "。" in cur:
                head, tail = cur.rsplit("。", 1)
                tail_s = tail.strip()
                if len(head.strip()) >= 6 and tail_s and len(tail_s) <= 28 and _MI_PERIOD_AUTHOR_HINT_RE.search(tail_s):
                    cur = head.strip()
            line = cur
        line = re.sub(r"20\d{2}[-./年]?\d{1,2}(?:[-./月]?\d{1,2}日?)?", " ", line)
        line = re.sub(r"20\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])", " ", line)
        line = re.sub(r"(?:\d+|[一二两三四五六七八九十]+)\s*个月", " ", line)
        cleaned.append(line)
    return "\n".join(cleaned)


_MONTH_TO_SEASON_MAP = {
    3: "春季", 4: "春季", 5: "春季",
    6: "夏季", 7: "夏季", 8: "夏季",
    9: "秋季", 10: "秋季", 11: "秋季",
    12: "冬季", 1: "冬季", 2: "冬季",
}
_CN_MONTH_TOKENS = {"十二": 12, "十一": 11, "十": 10, "九": 9, "八": 8, "七": 7, "六": 6, "五": 5, "四": 4, "三": 3, "二": 2, "一": 1, "元": 1}
_CN_M_RE = re.compile(r"(?<![第满近超前每])(十[一二]|[一二三四五六七八九十])[、,，~～—–到至\-]?(十[一二]|[二三四五六七八九十])?月份?")
_NUM_M_RANGE_RE = re.compile(r"(?<![\d.第前近每])(\d{1,2})\s*(?:[-~～—–至到/]|、|和|及)\s*(\d{1,2})(?:\s*(?:、|和|及)\s*(\d{1,2}))?\s*月(?![份]?(?:前|后|内|半|天|个|龄|岁))")
_NUM_M_SINGLE_RE = re.compile(r"(?<![\d.第前近每满超])(\d{1,2})\s*月(?![份]?(?:前|后|内|半|天|个|龄|岁|起|止))")

_PRECISION_MONTH_RULES: list[tuple[str, list[int], list[str], bool, int]] = [
    (r"圣诞", [12], ["冬季"], False, 3),
    (r"元旦|跨年|双旦", [12, 1], ["冬季"], False, 2),
    (r"春节|过年|除夕|拜年|年味|新春", [1, 2], ["冬季"], False, 2),
    (r"清明", [4], ["春季"], False, 3),
    (r"五一|劳动节|51小长假", [4, 5], ["春季"], False, 2),
    (r"端午|粽子|龙舟", [6], ["夏季"], False, 3),
    (r"七夕", [8], ["夏季"], False, 3),
    (r"中秋|月饼|开渔|开捕", [9], ["秋季"], False, 3),
    (r"国庆|十一假期|十一出游|十一去哪|十一旅游|十一团建|黄金周", [10], ["秋季"], False, 3),
    (r"年会|尾牙|年终总结|年终盛会", [12, 1], ["冬季"], False, 2),
    (r"滑雪|赏雪|雾凇|冰雪|雪景|雪乡|玩雪", [12, 1, 2], ["冬季"], False, 1),
    (r"赏梅|梅花山|蜡梅|腊梅|探梅", [1, 2, 3], ["冬季", "春季"], False, 1),
    (r"摘草莓|草莓采摘", [12, 1, 2, 3], ["冬季", "春季"], False, 1),
    (r"温泉|私汤|泡汤|汤池|围炉煮茶|围炉|杀年猪|刨猪汤|烤全羊|暖冬|冬季|冬天|冬日|冬游", [12, 1, 2], ["冬季"], False, 1),
    (r"樱花|赏樱|油菜花|桃花|梨花|郁金香|明前茶|采茶|春茶|春笋|挖笋|采笋|青团(?!建)|早春|开春", [3, 4], ["春季"], False, 2),
    (r"月季|绣球|杜鹃|海棠|紫藤|蔷薇", [4, 5], ["春季"], False, 2),
    (r"(?<!新)春游|踏青|春季|春天|春日|赏花|花海|放风筝", [3, 4, 5], ["春季"], False, 1),
    (r"杨梅|采杨梅|梅雨|梅雨季|入梅|出梅|枇杷|夏至", [6], ["夏季"], False, 2),
    (r"暑假|暑期|大暑|三伏", [7, 8], ["夏季"], False, 2),
    (r"漂流|溯溪|玩水|戏水|水上(?!森林)(?:乐园|运动|快乐|团建|项目|嘉年华|拓展|玩法)|泼水|泼浪|避暑|初夏|盛夏|夏季|夏天|夏日|夏游", [6, 7, 8], ["夏季"], False, 2),
    (r"水枪|纳凉|清凉|瀑布|荷花|萤火虫|西瓜", [6, 7, 8], ["夏季"], False, 1),
    (r"桂花", [10], ["秋季"], False, 2),
    (r"银杏|红枫|红叶|枫叶|晒秋|深秋|栖霞山|天平山", [11], ["秋季"], False, 2),
    (r"稻田|割稻|秋收|丰收|板栗|柿子|粉黛|芦苇|重阳|赏菊|菊花", [10, 11], ["秋季"], False, 2),
    (r"大闸蟹|品蟹|吃蟹|太湖蟹|阳澄湖蟹|蟹宴|秋游|赏秋|秋景|秋季|秋天|秋日|金秋|初秋|秋色|秋意", [9, 10, 11], ["秋季"], False, 1),
    (r"海岛|海边|沙滩|赶海|看海|出海|游艇|帆船|浮潜|跳岛|东极岛|枸杞岛|花鸟岛|嵊泗|朱家尖|南麂岛", [5, 6, 7, 8, 9, 10], ["春季", "夏季", "秋季"], False, 2),
    (r"桨板|皮划艇", [5, 6, 7, 8, 9, 10], ["春季", "夏季", "秋季"], False, 2),
    (r"露营|野餐|天幕|搭帐篷|草坪野餐", [3, 4, 5, 9, 10, 11], ["春季", "秋季"], True, 1),
    (r"徒步|古道|爬山|登山|骑行", [3, 4, 5, 9, 10, 11], ["春季", "秋季"], True, 1),
]


def _extract_explicit_months_list(text: str) -> list[int]:
    if not text:
        return []
    found: set[int] = set()
    for m in _NUM_M_RANGE_RE.finditer(text):
        a, b = int(m.group(1)), int(m.group(2))
        c = int(m.group(3)) if m.group(3) else None
        if 1 <= a <= 12 and 1 <= b <= 12:
            if c and 1 <= c <= 12:
                found.update([a, b, c])
            else:
                span = (b - a) % 12
                if 1 <= span <= 5:
                    cur = a
                    while True:
                        found.add(cur)
                        if cur == b:
                            break
                        cur = 1 if cur == 12 else cur + 1
                else:
                    found.update([a, b])
    masked = _NUM_M_RANGE_RE.sub(" ", text)
    for m in _NUM_M_SINGLE_RE.finditer(masked):
        v = int(m.group(1))
        if 1 <= v <= 12:
            found.add(v)
    for m in _CN_M_RE.finditer(text):
        m1 = _CN_MONTH_TOKENS.get(m.group(1))
        m2 = _CN_MONTH_TOKENS.get(m.group(2)) if m.group(2) else None
        if m1:
            if m2 and m2 != m1:
                span = (m2 - m1) % 12
                if 1 <= span <= 4:
                    cur = m1
                    while True:
                        found.add(cur)
                        if cur == m2:
                            break
                        cur = 1 if cur == 12 else cur + 1
                else:
                    found.update([m1, m2])
            else:
                found.add(m1)
    return sorted(found)


def _resolve_effective_title(title: str, body: str) -> str:
    raw_t = str(title or "").strip()
    if not body:
        return raw_t
    t_core = _MI_FOLDER_STAT_PREFIX_RE.sub("", raw_t).strip()
    t_core = re.sub(r"^\d{15,20}", "", t_core).strip()
    first_line = ""
    for raw in str(body).splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.search(r"^(?:博主|作者|点赞|评论|收藏|分享|发布时间|下载时间|采集时间|原链接|原始链接|作品\s*ID|https?://)", line):
            continue
        line = re.sub(r"^(?:标题|正文)[：:]\s*", "", line).strip()
        if not line or line == "（正文为空）":
            continue
        first_line = line
        break
    if not first_line:
        return raw_t
    first_m = _extract_explicit_months_list(_strip_season_noise(first_line[:160], is_body=False))
    title_m = _extract_explicit_months_list(_strip_season_noise(raw_t, is_body=False))
    if re.match(r"^\s*\d?\s*[月🈷]", t_core) and first_m and len(first_m) <= 6 and first_m != title_m:
        return first_line[:160]
    if first_m and len(first_m) <= 6 and not title_m:
        t_cjk = re.sub(r"[^\u4e00-\u9fff]", "", t_core)[:8]
        f_cjk = re.sub(r"[^\u4e00-\u9fff]", "", first_line)
        if t_cjk and len(t_cjk) >= 4 and (t_cjk in f_cjk or f_cjk[:6] in t_cjk):
            return first_line[:160]
    return raw_t


def detect_season_and_months(title: str, content: str) -> tuple[list[str], list[int]]:
    eff_title = _resolve_effective_title(title, content)
    title_c = _strip_season_noise(eff_title, is_body=False)
    body_c = _strip_season_noise(content, is_body=True)

    def _scan(tc: str, bc: str):
        ss: dict[str, int] = {}
        ms: dict[int, int] = {}
        for txt, w, is_t in ((tc, 3, True), (bc, 1, False)):
            if not txt:
                continue
            for pat, r_mo, r_sn, t_only, mult in _PRECISION_MONTH_RULES:
                if t_only and not is_t:
                    continue
                if re.search(pat, txt, re.IGNORECASE):
                    eff = w * mult
                    for s in r_sn:
                        ss[s] = ss.get(s, 0) + eff
                    for mo in r_mo:
                        ms[mo] = ms.get(mo, 0) + eff
            if re.search(r"无边泳池|泳池", txt) and not re.search(r"恒温泳池|室内泳池|温泉泳池|温水泳池", txt):
                ss["夏季"] = ss.get("夏季", 0) + w
                for mo in (6, 7, 8):
                    ms[mo] = ms.get(mo, 0) + w
        return ss, ms

    t_ss, t_ms = _scan(title_c, "")
    all_ss, all_ms = _scan(title_c, body_c)

    t_exp = _extract_explicit_months_list(title_c)
    b_exp = _extract_explicit_months_list(body_c)
    exp = t_exp if (t_exp and len(t_exp) <= 6) else (b_exp if (not t_ss and b_exp and len(b_exp) <= 6) else [])
    if exp:
        hit_s = {_MONTH_TO_SEASON_MAP[m] for m in exp if m in _MONTH_TO_SEASON_MAP}
        seasons = [s for s in ALL_SEASON_LIST if s in hit_s] or list(ALL_SEASON_LIST)
        return seasons, exp

    use_ss = dict(t_ss if t_ss else all_ss)
    use_ms = dict(t_ms if t_ss else all_ms)
    if t_ss:
        allowed = set(t_ss.keys())
        for s, sc in all_ss.items():
            if s in allowed:
                use_ss[s] = max(use_ss.get(s, 0), sc)
        for mo, sc in all_ms.items():
            if _MONTH_TO_SEASON_MAP[mo] in allowed:
                use_ms[mo] = max(use_ms.get(mo, 0), sc)

    if not use_ss:
        return list(ALL_SEASON_LIST), list(range(1, 13))

    max_sc = max(use_ss.values())
    kept_s = [s for s in ALL_SEASON_LIST if s in use_ss and not (max_sc > use_ss[s] * 2)]
    if "冬季" in kept_s and "夏季" in kept_s:
        if _MI_STRONG_SUMMER_RE.search(title_c) and not _MI_STRONG_WINTER_RE.search(title_c):
            kept_s = [s for s in kept_s if s != "冬季"]
        elif not ("冬季" in t_ss and "夏季" in t_ss):
            if use_ss.get("冬季", 0) >= use_ss.get("夏季", 0):
                kept_s = [s for s in kept_s if s != "夏季"]
            else:
                kept_s = [s for s in kept_s if s != "冬季"]

    kept_set = set(kept_s)
    max_m_s: dict[str, int] = {}
    for mo, sc in use_ms.items():
        sn = _MONTH_TO_SEASON_MAP[mo]
        if sn in kept_set:
            max_m_s[sn] = max(max_m_s.get(sn, 0), sc)
    kept_m = sorted(mo for mo, sc in use_ms.items() if _MONTH_TO_SEASON_MAP[mo] in kept_set and not (max_m_s[_MONTH_TO_SEASON_MAP[mo]] > sc * 2))
    if not kept_m:
        kept_m = sorted({m for m, sn in _MONTH_TO_SEASON_MAP.items() if sn in kept_set})
    return (kept_s or list(ALL_SEASON_LIST)), kept_m


def detect_season_matches(title: str, content: str) -> list[str]:
    return detect_season_and_months(title, content)[0]


def detect_theme_matches(title: str, content: str) -> list[str]:
    text = f"{title} {content}".lower()
    matched: list[str] = []
    for rule in THEME_RULES:
        if any(kw.lower() in text for kw in rule["keywords"]):
            matched.append(rule["name"])
    return matched


def detect_commercial_ad(
    title: str,
    content: str,
    author: str = "",
    filter_cfg: Mapping[str, Any] | None = None,
) -> tuple[bool, str]:
    cfg = filter_cfg if isinstance(filter_cfg, Mapping) else {}
    title_s = str(title or "").strip()
    content_s = str(content or "").strip()
    author_s = str(author or "").strip()
    full_text = f"{title_s} {author_s} {content_s}"

    topic_keep = cfg.get("topic_keep_patterns") or [r"胡闹厨房", r"团建", r"年会游戏", r"年会活动"]
    if any(re.search(pat, full_text) for pat in topic_keep):
        return False, "命中团建主题素材保留规则"

    author_blacklist = cfg.get("author_blacklist_keywords") or [
        "汽车租赁", "租车公司", "租车服务", "汽车服务部", "汽车销售",
        "名车汇", "二手车", "4S店", "泊车", "代泊", "停车服务", "婚纱摄影", "装修设计",
        "行李寄存", "无忧存", "小铁", "途简单", "存知己", "存包", "寄存平台",
    ]
    for akw in author_blacklist:
        if akw and akw in author_s:
            return True, f"商业营销账号主体(作者包含'{akw}')"

    title_patterns = cfg.get("title_ad_patterns") or [
        r"提车(日记|记录|分享)?", r"喜提", r"新座驾", r"试驾(体验|报告)?",
        r"购车(指南|攻略|心得)?", r"选车(攻略)?", r"落地价", r"交付(日记|实况)",
        r"(租车|包车)首选", r"专业的?(上海|杭州|江浙沪)?租车公司", r"\d+[-~至]\d+座.*(大巴|中巴|商务车).*包车",
        r"机场停车(攻略)?.*(仅需|只要|天)", r"室内每天仅需\d+元", r"代泊",
        r"摩登汽车", r"车模", r"车展实拍", r"车主真实(口碑|感受)",
        r"寄存(点|柜|处|攻略)?", r"行李寄存", r"储物柜", r"存包(处|点|攻略)?", r"不拖箱",
        r"亚宠展", r"宠物展", r"逛展(攻略)?", r"展会攻略", r"漫展", r"婚博会", r"铲屎官", r"养宠人",
    ]
    for pat in title_patterns:
        if re.search(pat, full_text):
            return True, f"采集后入库拦截：正文/标题/话题命中营销杂质特征('{pat}')"

    content_patterns = cfg.get("content_ad_patterns") or [
        "摩登汽车", "岚图追光", r"充电站\d+\s*处", "沿途充电站", "纯电续航", "百公里电耗",
        r"行李寄存", r"寄存点", r"自助寄存", r"储物柜", r"寄存柜", r"存包",
        r"亚宠展", r"宠物展", r"逛展攻略", r"展会门票", r"薅羊毛指南",
    ]
    for pat in content_patterns:
        if re.search(pat, full_text):
            return True, f"内容命中车企营销特征('{pat}')"

    if any(k in title_s for k in ["租车", "包车", "客运"]) and any(
        k in full_text for k in ["常年提供", "苏沛", "锦路", "华轶"]
    ):
        return True, "内容命中租车/客运商业广告"

    return False, ""


def _shelf_target_dir(base: Path, traffic_type: str, target_category: str, folder_name: str, dirs: Mapping[str, Path]) -> Path:
    if re.fullmatch(r"(0[1-9]|1[0-2])月", base.name):
        return base / folder_name
    cat = "大合集与特色" if target_category in {"大合集", "团建游戏"} else target_category
    if (base / cat).exists() or not (base / "精准流量").exists():
        return base / cat / folder_name
    if traffic_type == "泛流量":
        return (base / "泛流量" / cat / folder_name) if (base / "泛流量").exists() else (dirs["pan"] / cat / folder_name)
    return (base / "精准流量" / cat / folder_name) if (base / "精准流量").exists() else (dirs["precision"] / cat / folder_name)


def _link_or_copy_dir(src_dir: Path, dest_dir: Path) -> str:
    dest_dir.mkdir(parents=True, exist_ok=True)
    mode = "NTFS硬链接"
    for src_file in src_dir.iterdir():
        if not src_file.is_file():
            continue
        dest_file = dest_dir / src_file.name
        if dest_file.exists():
            if os.path.samefile(src_file, dest_file):
                continue
            if src_file.drive and dest_file.drive and src_file.drive.upper() == dest_file.drive.upper():
                dest_file.unlink()
                os.link(src_file, dest_file)
                continue
        same_drive = bool(src_file.drive and dest_file.drive and src_file.drive.upper() == dest_file.drive.upper())
        if same_drive:
            # 同盘符唯一文件铁律：只允许 NTFS 硬链接，严禁静默降级复制出第二份副本
            os.link(src_file, dest_file)
        else:
            mode = "跨卷副本/软链"
            try:
                os.symlink(src_file, dest_file)
            except OSError:
                shutil.copy2(src_file, dest_file)
    return mode


def _append_project_link_record(link_file: Path, route_key: str | None, title: str, url: str) -> None:
    if route_key != "doubao_pullnew" or not url:
        return
    link_file.parent.mkdir(parents=True, exist_ok=True)
    content = link_file.read_text(encoding="utf-8", errors="ignore") if link_file.exists() else ""
    if url in content:
        return
    ts = time.strftime("%Y-%m-%d %H:%M")
    if not content:
        content = (
            "# 豆包拉新 · 手机端对标灵感链接库\n\n"
            "> 手机随时点开看灵感、找对标。\n\n---\n\n## 📌 灵感对标池\n\n"
        )
        link_file.write_text(content, encoding="utf-8")
    seq = content.count("### ") + 1
    section = (
        f"\n### {seq:02d}. {title[:40]}（统一入库采集）\n"
        f"- **采集时间**：{ts}\n"
        f"- **直达链接**：[{url}]({url})\n"
    )
    with link_file.open("a", encoding="utf-8") as stream:
        stream.write(section)


def _list_media_files(work_dir: Path) -> tuple[list[Path], list[Path]]:
    images: list[Path] = []
    videos: list[Path] = []
    for entry in sorted(work_dir.iterdir()):
        if not entry.is_file():
            continue
        try:
            if entry.stat().st_size < MIN_MEDIA_BYTES:
                continue
        except OSError:
            continue
        suffix = entry.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            images.append(entry)
        elif suffix in VIDEO_EXTENSIONS:
            videos.append(entry)
    return images, videos


def _load_default_config(config_path: Path | None = None) -> tuple[dict[str, Any], Path | None]:
    code_root = Path(__file__).resolve().parent
    candidates = []
    if config_path:
        candidates.append(Path(config_path).expanduser())
    env_cfg = os.environ.get("MATERIAL_HUB_CONFIG", "").strip()
    if env_cfg:
        candidates.append(Path(env_cfg).expanduser())
    candidates.append(code_root / "config" / "config.json")
    for cand in candidates:
        if cand.is_file():
            return load_json_config(cand), cand
    return {}, None


def ingest_work_package(
    source_dir: str | Path,
    *,
    config: Mapping[str, Any] | None = None,
    config_path: str | Path | None = None,
    url: str = "",
    mode: str = "auto",
    target_folder: str = "",
    source_label: str = "统一入库",
    engine_label: str = "",
    platform_hint: str = "",
    max_images: int | None = None,
    copy_only: bool = False,
    dry_run: bool = False,
    clean_copy_file: bool = True,
    write_metadata: bool = True,
    extra_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Ingest one downloaded note/work directory into the canonical material shelf."""
    src = Path(source_dir).expanduser()
    if not src.is_dir():
        return {
            "status": "error", "success": False, "outcome": "missing_source",
            "source_dir": str(src), "message": f"源素材目录不存在：{src}",
        }
    src = src.resolve()
    images, videos = _list_media_files(src)
    if not images and not videos:
        return {
            "status": "error", "success": False, "outcome": "no_media",
            "source_dir": str(src), "message": "源目录中没有非空有效图片或视频文件",
        }

    resolved_cfg: Mapping[str, Any]
    resolved_cfg_path: Path | None = None
    if config is not None:
        resolved_cfg = config
        if config_path:
            resolved_cfg_path = Path(config_path).expanduser()
    else:
        resolved_cfg, resolved_cfg_path = _load_default_config(
            Path(config_path) if config_path else None
        )

    code_root = Path(__file__).resolve().parent
    dirs = _resolve_storage_dirs(
        resolved_cfg,
        code_root=code_root,
        config_dir=(resolved_cfg_path.parent if resolved_cfg_path else code_root),
    )
    filter_cfg = resolved_cfg.get("filter_rules", {}) if isinstance(resolved_cfg.get("filter_rules"), Mapping) else {}
    rules_cfg = resolved_cfg.get("classification_rules", {}) if isinstance(resolved_cfg.get("classification_rules"), Mapping) else {}
    city_rules = rules_cfg.get("city_rules") if isinstance(rules_cfg.get("city_rules"), Mapping) else DEFAULT_CITY_RULES

    if max_images is None:
        try:
            max_images = int(filter_cfg.get("max_images_allowed", 30))
        except (TypeError, ValueError):
            max_images = 30

    if max_images > 0 and len(images) > max_images:
        return {
            "status": "filtered",
            "success": False,
            "outcome": "filtered_oversized",
            "source_dir": str(src),
            "images_count": len(images),
            "max_images_allowed": max_images,
            "message": f"素材图片超限({len(images)}张 > 上限{max_images}张)，触发超长过滤策略拦截",
        }

    existing_meta: dict[str, Any] = {}
    meta_file = src / "metadata.json"
    if meta_file.is_file():
        try:
            loaded = json.loads(meta_file.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict):
                existing_meta = loaded
        except (OSError, ValueError):
            existing_meta = {}

    raw_folder_name = src.name
    folder_comments, folder_likes, folder_author, folder_note_id = parse_folder_stats(raw_folder_name)
    copy_info = extract_copy_and_clean(src / "文案.txt", raw_folder_name, fallback_author=folder_author)

    title_text = str(existing_meta.get("title") or copy_info["title"] or raw_folder_name).strip()
    author_text = str(existing_meta.get("author") or copy_info["author"] or folder_author or "").strip()
    content_text = copy_info["clean_copy"] or copy_info["raw_text"]
    effective_url = str(
        url or existing_meta.get("url") or existing_meta.get("source_url") or copy_info.get("source_url") or ""
    ).strip()
    effective_note_id = str(
        existing_meta.get("note_id") or folder_note_id or copy_info.get("note_id") or ""
    ).strip()

    extra_dict = dict(extra_metadata) if isinstance(extra_metadata, Mapping) else {}
    likes_cnt = parse_cn_count(
        extra_dict.get("likes_count")
        or existing_meta.get("likes_count")
        or copy_info.get("likes_count")
        or folder_likes
    )
    comments_cnt = parse_cn_count(
        extra_dict.get("comments_count")
        or existing_meta.get("comments_count")
        or copy_info.get("comments_count")
        or folder_comments
    )
    folder_name = sanitize_ingested_folder_name(raw_folder_name, comments_cnt, likes_cnt)

    is_ad, ad_reason = detect_commercial_ad(title_text, content_text, author_text, filter_cfg=filter_cfg)
    if is_ad:
        return {
            "status": "filtered",
            "success": False,
            "outcome": "filtered_ad",
            "source_dir": str(src),
            "title": title_text,
            "author": author_text,
            "reason": ad_reason,
            "message": f"检测到商业广告/营销软文({ad_reason})，触发广告拦截策略",
        }

    curr_mode = "manual" if (mode == "manual" and str(target_folder or "").strip()) else "auto"
    manual_target = str(target_folder or "").strip()
    project_routed: str | None = None
    is_unclassified = False
    matched_months: list[int] = []

    if curr_mode == "manual":
        traffic_type = "手动定向"
        target_category = manual_target
        target_city = manual_target
        target_path = Path(os.path.expandvars(os.path.expanduser(manual_target)))
        dest_parent = target_path if target_path.is_absolute() else (dirs["material_root"] / target_path)
        matched_seasons = ["指定专题"]
        season_name = f"手动定向({manual_target})"
    else:
        project_routed = detect_project_route(title_text, content_text, config=resolved_cfg)
        if project_routed == "doubao_pullnew":
            traffic_type = "项目路由"
            target_category = "豆包拉新·参考爆款"
            target_city = "豆包拉新"
            dest_parent = dirs["doubao_material"]
            matched_seasons = ["项目路由"]
            season_name = "项目直达(无季节扩散)"
        else:
            traffic_type, target_category = detect_traffic_and_category(
                title_text, content_text, city_rules=city_rules
            )
            matched_seasons, matched_months = detect_season_and_months(title_text, content_text)
            if not matched_months:
                matched_months = list(range(1, 13))
            season_name = "全12月通用（已硬链01月~12月）" if len(matched_months) == 12 else "|".join(f"{m:02d}月" for m in matched_months)
            is_unclassified = (traffic_type == "未分类")
            if is_unclassified:
                matched_months = []
                target_city = "未分类(00-待识别暂存)"
                dest_parent = dirs["unclassified"]
            else:
                target_city = target_category
                primary_month = matched_months[0]
                primary_base = dirs["month_dirs"][primary_month]
                dest_parent = _shelf_target_dir(primary_base, traffic_type, target_category, folder_name, dirs).parent

    final_target_dir = (dest_parent / folder_name).resolve()
    if not dry_run and final_target_dir != src and final_target_dir.exists():
        shutil.rmtree(final_target_dir, ignore_errors=True)
        if final_target_dir.exists():
            final_target_dir = (dest_parent / f"{folder_name}_{int(time.time())}").resolve()

    month_work_dirs: list[tuple[str, Path]] = []
    if curr_mode == "auto" and not project_routed and not is_unclassified:
        for mo in matched_months:
            m_base = dirs["month_dirs"][mo]
            m_target = _shelf_target_dir(m_base, traffic_type, target_category, folder_name, dirs).resolve()
            if m_target == final_target_dir:
                continue
            month_work_dirs.append((f"{mo:02d}月", m_target))

    matched_themes = detect_theme_matches(title_text, content_text) if (curr_mode == "auto" and not project_routed and not is_unclassified) else []
    theme_work_dirs: list[Path] = []
    if matched_themes and dirs["theme"].exists():
        for theme_name in matched_themes:
            t_base = dirs["theme"] / theme_name
            if not t_base.exists():
                continue
            if (t_base / target_category).is_dir():
                t_dest = (t_base / target_category / folder_name).resolve()
            else:
                t_dest = (t_base / folder_name).resolve()
            if t_dest != final_target_dir:
                theme_work_dirs.append(t_dest)

    if platform_hint:
        platform = platform_hint
    elif "douyin" in effective_url.lower() or folder_name.startswith("直采_") or str(existing_meta.get("platform") or "").lower() == "douyin":
        platform = "抖音"
    elif "xhs" in effective_url.lower() or "xiaohongshu" in effective_url.lower() or "rednote" in effective_url.lower() or str(existing_meta.get("platform") or "").lower() in {"xiaohongshu", "xhs"}:
        platform = "小红书"
    else:
        platform = str(existing_meta.get("platform") or "精选")

    favorites_cnt = parse_cn_count(
        extra_dict.get("favorites_count")
        or existing_meta.get("favorites_count")
        or 0
    )
    shares_cnt = parse_cn_count(
        extra_dict.get("shares_count")
        or existing_meta.get("shares_count")
        or 0
    )
    matched_month_labels = [f"{m:02d}月" for m in matched_months]
    geo_info = {
        "province": "行政HR" if target_city in {"行政HR图文", "HR行政"} else ("上海" if target_city == "上海" else "浙江"),
        "city": target_city,
        "cities": [target_city],
        "spots": [],
        "themes": [],
    }
    try:
        _skill_scripts = Path(r"D:\AICode\AI\skills\技能包\技能\jianghu-toolbox-material-ingestion\scripts")
        if _skill_scripts.is_dir() and str(_skill_scripts) not in sys.path:
            sys.path.insert(0, str(_skill_scripts))
        import flatten_months_and_enrich_metadata as _fme
        geo_info = _fme.extract_location_and_themes(
            title_text,
            content_text,
            primary_city=target_city,
            content_months=matched_month_labels,
        )
    except Exception:
        pass

    metadata: dict[str, Any] = {
        "title": title_text,
        "author": author_text,
        "author_uid": str(existing_meta.get("author_uid") or ""),
        "note_id": effective_note_id,
        "keyword": str(existing_meta.get("keyword") or ""),
        "likes_count": likes_cnt,
        "comments_count": comments_cnt,
        "favorites_count": favorites_cnt,
        "shares_count": shares_cnt,
        "publish_timestamp": existing_meta.get("publish_timestamp"),
        "publish_time": str(existing_meta.get("publish_time") or ""),
        "publish_date": str(existing_meta.get("publish_date") or ""),
        "province": geo_info["province"],
        "city": geo_info["city"],
        "cities": geo_info["cities"],
        "spots": geo_info["spots"],
        "themes": geo_info["themes"],
        "traffic_type": traffic_type,
        "category": target_category,
        "season": season_name,
        "matched_seasons": matched_seasons,
        "matched_months": matched_months,
        "content_months": matched_month_labels,
        "season_classified_by": "season_month_classifier_v3",
        "matched_themes": matched_themes,
        "is_unclassified": is_unclassified,
        "collection_mode": curr_mode,
        "manual_target_folder": manual_target if curr_mode == "manual" else "",
        "source": source_label,
        "engine": engine_label or str(existing_meta.get("engine") or "万能下载器 v3.8.3"),
        "platform": platform,
        "tags": [
            source_label,
            f"{platform}{'视频' if videos else '图文'}",
            traffic_type,
            target_city,
        ] + [f"{m}素材" for m in matched_month_labels],
        "project_route": project_routed or "",
        "downloaded_at": str(existing_meta.get("downloaded_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
        "ingested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "url": effective_url,
        "source_url": effective_url,
        "original_url": effective_url,
        "share_url": effective_url,
        "images_count": len(images),
        "images_list": [p.name for p in images],
        "image_urls": list(existing_meta.get("image_urls") or []),
        "image_format": str(existing_meta.get("image_format") or ""),
        "watermark_free": existing_meta.get("watermark_free", True),
        "note_type": "视频" if videos else "图文",
        "videos_count": len(videos),
        "videos_list": [p.name for p in videos],
        "content_length": len(content_text),
        "content_preview": content_text[:120].strip() if content_text else "",
        "folder_name": final_target_dir.name,
        "target_dir": str(final_target_dir),
        "month_hardlink_dirs": [str(d) for _, d in month_work_dirs],
        "season_hardlink_dirs": [str(d) for _, d in month_work_dirs],
        "theme_hardlink_dirs": [str(d) for d in theme_work_dirs],
        "version": "3.9.0",
        "status": "success",
        "captured_by": "material-ingestor",
    }
    for key, value in extra_dict.items():
        if key not in metadata or metadata[key] in ("", 0, None, []):
            metadata[key] = value

    if dry_run:
        return {
            "status": "ok",
            "success": True,
            "outcome": "dry_run",
            "dry_run": True,
            "source_dir": str(src),
            "target_dir": str(final_target_dir),
            "title": title_text,
            "author": author_text,
            "platform": platform,
            "traffic_type": traffic_type,
            "category": target_category,
            "city": target_city,
            "is_unclassified": is_unclassified,
            "seasons": matched_seasons,
            "months": matched_month_labels,
            "month_hardlink_dirs": [str(d) for _, d in month_work_dirs],
            "season_hardlink_dirs": [str(d) for _, d in month_work_dirs],
            "themes": matched_themes,
            "theme_hardlink_dirs": [str(d) for d in theme_work_dirs],
            "images_count": len(images),
            "videos_count": len(videos),
            "clean_copy_preview": content_text[:200],
            "metadata": metadata,
            "message": f"预演成功：将归入【{traffic_type}·{target_city}】-> {final_target_dir}",
        }

    dest_parent.mkdir(parents=True, exist_ok=True)
    if final_target_dir != src:
        if copy_only:
            shutil.copytree(str(src), str(final_target_dir))
        else:
            try:
                shutil.move(str(src), str(final_target_dir))
            except OSError:
                shutil.copytree(str(src), str(final_target_dir))
                shutil.rmtree(str(src), ignore_errors=True)

    if clean_copy_file and copy_info["clean_copy"]:
        (final_target_dir / "文案.txt").write_text(copy_info["clean_copy"], encoding="utf-8-sig")

    if write_metadata:
        (final_target_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    hardlink_modes: dict[str, str] = {}
    for month_tag, month_dir in month_work_dirs:
        try:
            hardlink_modes[month_tag] = _link_or_copy_dir(final_target_dir, month_dir)
        except OSError:
            pass

    for theme_dir in theme_work_dirs:
        try:
            _link_or_copy_dir(final_target_dir, theme_dir)
        except OSError:
            pass

    try:
        _append_project_link_record(dirs["doubao_link_md"], project_routed, title_text, effective_url)
    except OSError:
        pass

    if update_history_location is not None and effective_url:
        try:
            existing_hist = find_downloaded(download_url=effective_url) if find_downloaded else None
            update_history_location(
                effective_url,
                (existing_hist or {}).get("笔记ID", "") or effective_note_id,
                (existing_hist or {}).get("标题") or title_text,
                str(final_target_dir),
            )
        except Exception:
            pass

    return {
        "status": "ok",
        "success": True,
        "outcome": "ingested",
        "dry_run": False,
        "copy_only": bool(copy_only),
        "source_dir": str(src),
        "target_dir": str(final_target_dir),
        "folder_name": final_target_dir.name,
        "title": title_text,
        "author": author_text,
        "platform": platform,
        "traffic_type": traffic_type,
        "category": target_category,
        "city": target_city,
        "is_unclassified": is_unclassified,
        "seasons": matched_seasons,
        "months": matched_month_labels,
        "month_hardlink_dirs": [str(d) for _, d in month_work_dirs],
        "season_hardlink_dirs": [str(d) for _, d in month_work_dirs],
        "hardlink_modes": hardlink_modes,
        "themes": matched_themes,
        "theme_hardlink_dirs": [str(d) for d in theme_work_dirs],
        "images_count": len(images),
        "videos_count": len(videos),
        "metadata": metadata,
        "message": f"已归入【{traffic_type}·{target_city}】({len(images)}图/{len(videos)}视频)",
    }


def ingest_path(
    source_path: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    """Ingest either one work directory or a batch directory containing child work packages."""
    target = Path(source_path).expanduser()
    if not target.is_dir():
        return {
            "status": "error", "success": False, "outcome": "missing_source",
            "source_dir": str(target), "message": f"源目录不存在：{target}",
        }
    images, videos = _list_media_files(target)
    if images or videos:
        return ingest_work_package(target, **kwargs)

    child_packages = []
    for child in sorted(target.iterdir()):
        if not child.is_dir():
            continue
        c_imgs, c_vids = _list_media_files(child)
        if c_imgs or c_vids:
            child_packages.append(child)
    if not child_packages:
        return {
            "status": "error", "success": False, "outcome": "no_media",
            "source_dir": str(target), "message": "源目录及其直接子目录中没有发现非空媒体作品包",
        }

    items = [ingest_work_package(pkg, **kwargs) for pkg in child_packages]
    ok_count = sum(1 for item in items if item.get("success") is True)
    filtered_count = sum(1 for item in items if item.get("status") == "filtered")
    failed_count = len(items) - ok_count - filtered_count
    overall_ok = ok_count > 0 or (filtered_count == len(items))
    return {
        "status": "ok" if overall_ok and failed_count == 0 else ("partial" if ok_count else "error"),
        "success": ok_count > 0 and failed_count == 0,
        "outcome": "dry_run" if kwargs.get("dry_run") else ("completed" if failed_count == 0 else "completed_partial"),
        "dry_run": bool(kwargs.get("dry_run")),
        "batch": True,
        "source_dir": str(target.resolve()),
        "total": len(items),
        "ingested_count": ok_count,
        "filtered_count": filtered_count,
        "failed_count": failed_count,
        "items": items,
        "message": f"批量处理 {len(items)} 个作品包：入库/预演 {ok_count} 条，过滤 {filtered_count} 条，失败 {failed_count} 条",
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="MaterialHub 统一素材后处理与入库管线")
    parser.add_argument("--source", required=True, help="单作品目录或包含多个作品子目录的父目录")
    parser.add_argument("--config", help="指定 config.json 路径")
    parser.add_argument("--url", default="", help="作品原始分享链接")
    parser.add_argument("--mode", choices=["auto", "manual"], default="auto", help="路由模式")
    parser.add_argument("--target", default="", help="manual 模式下的目标文件夹")
    parser.add_argument("--source-label", default="统一入库", help="metadata.source 标记")
    parser.add_argument("--max-images", type=int, default=None, help="最大图片张数阈值")
    parser.add_argument("--copy", action="store_true", help="复制入库而非移动源目录")
    parser.add_argument("--dry-run", action="store_true", help="只读预演，不实际写盘或移动")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    args = parser.parse_args(argv)

    result = ingest_path(
        args.source,
        config_path=args.config,
        url=args.url,
        mode=args.mode,
        target_folder=args.target,
        source_label=args.source_label,
        max_images=args.max_images,
        copy_only=args.copy,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "filtered"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
