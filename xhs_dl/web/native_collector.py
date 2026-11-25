"""Built-in Playwright + persistent Edge/Chrome browser collector for 万能采集器.

Runs keyword search and author homepage discovery directly inside Python using a
persistent Edge/Chrome user profile (~/.xhs-dl/browser_profiles/collector). No
external .NET helper (DY提取作品_直开.exe / jianghu_cli.py) is required.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import queue
import re
import socket
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set
from urllib.parse import quote, urlsplit


DEFAULT_TITLE_TEMPLATE = "评{comments}-藏{favorites}-赞{likes}-{title}-{author}-{publish_time}"
DEFAULT_PROFILE_DIR = Path.home() / ".xhs-dl" / "browser_profiles" / "collector"
MAX_SEARCH_CANDIDATES = 300
MAX_SEARCH_SCROLL_ROUNDS = 45
SEARCH_SCROLL_SETTLE_SECONDS = 1.15


_DOUYIN_SEARCH_SNAPSHOT_SCRIPT = r"""
(function () {
  function findCardData(value, depth, seen) {
    if (!value || typeof value !== "object" || depth > 8) return null;
    seen = seen || [];
    if (seen.indexOf(value) >= 0) return null;
    seen.push(value);
    try {
      if (value.awemeInfo && typeof value.awemeInfo === "object") return value.awemeInfo;
    } catch (_) {}
    var keys = [];
    try { keys = Object.keys(value); } catch (_) { return null; }
    for (var i = 0; i < Math.min(keys.length, 80); i++) {
      try {
        var found = findCardData(value[keys[i]], depth + 1, seen);
        if (found) return found;
      } catch (_) {}
    }
    return null;
  }

  function unique(values) {
    var seen = {};
    return (values || []).filter(function (value) {
      value = String(value || "").trim();
      if (!value || seen[value]) return false;
      seen[value] = true;
      return true;
    }).slice(0, 50);
  }

  function isWatermarkedUrl(url) {
    return /tplv-dy-water|watermark/i.test(String(url || ""));
  }

  function isPreferredImageExt(url) {
    return /\.(?:jpe?g|png)(?:[?#]|$)/i.test(String(url || ""));
  }

  function pickCleanImageUrl(image) {
    var originals = Array.isArray(image.urlList) ? image.urlList : [];
    var downloads = Array.isArray(image.downloadUrlList) ? image.downloadUrlList : [];
    var buckets = [
      originals.filter(function (u) { return u && !isWatermarkedUrl(u) && isPreferredImageExt(u); }),
      originals.filter(function (u) { return u && !isWatermarkedUrl(u); }),
      downloads.filter(function (u) { return u && !isWatermarkedUrl(u) && isPreferredImageExt(u); }),
      downloads.filter(function (u) { return u && !isWatermarkedUrl(u); })
    ];
    for (var i = 0; i < buckets.length; i++) {
      if (buckets[i].length) return String(buckets[i][0] || "");
    }
    if (image.url && !isWatermarkedUrl(image.url)) return String(image.url);
    return String(originals[0] || image.url || downloads[0] || "");
  }

  function imageUrls(aweme) {
    var values = [];
    var images = Array.isArray(aweme && aweme.images) ? aweme.images : [];
    images.forEach(function (image) {
      if (!image || typeof image !== "object") return;
      values.push(pickCleanImageUrl(image));
    });
    return unique(values);
  }

  function imageSizes(aweme) {
    var values = [];
    var images = Array.isArray(aweme && aweme.images) ? aweme.images : [];
    images.forEach(function (image) {
      if (!image || typeof image !== "object") return;
      var width = image.width || 0;
      var height = image.height || 0;
      if (width && height) values.push(String(width) + "x" + String(height));
    });
    return values;
  }

  function coverUrls(card, aweme) {
    var values = imageUrls(aweme);
    var video = aweme && aweme.video;
    if (video && typeof video === "object") {
      [video.originCover, video.cover]
        .concat(video.originCoverUrlList || [])
        .concat(video.coverUrlList || [])
        .forEach(function (url) {
          if (url && !isWatermarkedUrl(url)) values.push(url);
        });
    }
    var avatarHint = /(?:avatar|avatars|icon|icons|emoji|head|logo|badge|pendant|sticker)/i;
    Array.prototype.slice.call(card.querySelectorAll('img')).forEach(function (img) {
      var src = String(img.currentSrc || img.src || img.getAttribute('src') || "");
      if (!src || isWatermarkedUrl(src)) return;
      var hint = String(img.className || "") + " " + String(img.alt || "") + " " + src;
      if (avatarHint.test(hint)) return;
      var naturalWidth = Number(img.naturalWidth || 0);
      if (naturalWidth > 0 && naturalWidth < 180) return;
      var widthAttr = Number(img.getAttribute('width') || 0);
      if (widthAttr > 0 && widthAttr < 120) return;
      values.push(src);
    });
    return unique(values).slice(0, 50);
  }

  var body = document.body ? (document.body.innerText || "") : "";
  var href = String(location.href || "");
  var title = document.title || "";
  var pageText = body + " " + title + " " + href;
  function isVisible(el) {
    if (!el || !el.getBoundingClientRect) return false;
    try {
      var rect = el.getBoundingClientRect();
      if (rect.width <= 40 || rect.height <= 40) return false;
      var style = window.getComputedStyle ? window.getComputedStyle(el) : null;
      if (style && (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || "1") <= 0)) {
        return false;
      }
      return true;
    } catch (_) {
      return false;
    }
  }
  var gateMarkers = 0;
  try {
    var gateNodes = Array.prototype.slice.call(document.querySelectorAll(
      'iframe[src*="captcha"], iframe[src*="verify"], '
      + '.captcha_verify_container, .secsdk-captcha-drag-wrapper, #captcha_container, '
      + '[id*="captcha"], [class*="captcha"]'
    ));
    gateMarkers = gateNodes.filter(isVisible).length;
    if (!gateMarkers) {
      var challengeNodes = Array.prototype.slice.call(document.querySelectorAll('[class*="challenge"]'));
      gateMarkers = challengeNodes.filter(function (el) {
        if (!isVisible(el)) return false;
        var rect = el.getBoundingClientRect();
        return rect.width > 180 && rect.height > 120 && /验证|滑块|captcha|拼图/i.test(el.innerText || "");
      }).length;
    }
  } catch (_) {}
  var cards = Array.prototype.slice.call(document.querySelectorAll('.search-result-card'));
  var result = cards.map(function (card, index) {
    var text = (card.innerText || "").trim();
    var isPhoto = !!card.querySelector('span.TtoFOFHo, .DQFiFTgl');
    var aweme = null;
    var elementKeys = [];
    try { elementKeys = Object.keys(card); } catch (_) {}
    for (var i = 0; i < elementKeys.length; i++) {
      if (!/react/i.test(elementKeys[i])) continue;
      try {
        aweme = findCardData(card[elementKeys[i]], 0, []);
        if (aweme) break;
      } catch (_) {}
    }
    var id = aweme && (aweme.awemeId || aweme.groupId || aweme.docId);
    var desc = aweme && (aweme.desc || aweme.itemTitle || aweme.caption);
    var authorInfo = aweme && (aweme.authorInfo || aweme.author);
    var stats = aweme && (aweme.statistics || aweme.stats);
    var author = authorInfo && (authorInfo.nickname || authorInfo.name);
    var imageArray = Array.isArray(aweme && aweme.images) ? aweme.images : [];
    var video = aweme && aweme.video;
    var awemeType = Number(aweme && aweme.awemeType);
    var mediaType = Number(aweme && aweme.mediaType);
    var imageNoteSignal = imageArray.length > 0 && (
      isPhoto || awemeType === 68 || mediaType === 2
    );
    var explicitVideoType = mediaType === 4 || (awemeType === 0 && !imageNoteSignal);
    var playableVideo = !!(video && typeof video === "object" && (
      Number(video.duration) > 0 || video.playAddr || video.playApi ||
      (Array.isArray(video.playAddrUrlList) && video.playAddrUrlList.length) ||
      (Array.isArray(video.playUrlList) && video.playUrlList.length)
    ));
    var hasVideo = explicitVideoType || (!imageNoteSignal && imageArray.length === 0 && playableVideo);
    var url = id ? ("https://www.douyin.com/" + (hasVideo ? "video/" : "note/") + String(id)) : "";
    return {
      index: index,
      artwork_type: hasVideo ? "视频" : "图文",
      is_photo: !hasVideo && imageNoteSignal,
      is_video: hasVideo,
      id: id ? String(id) : "",
      group_id: aweme && aweme.groupId ? String(aweme.groupId) : "",
      aweme_type: aweme && aweme.awemeType != null ? String(aweme.awemeType) : "",
      image_count: imageArray.length,
      title: String(desc || "").trim().slice(0, 300),
      caption: String(desc || "").trim().slice(0, 12000),
      author: String(author || "").trim().slice(0, 120),
      author_uid: authorInfo && (authorInfo.uid || authorInfo.authorId) ? String(authorInfo.uid || authorInfo.authorId) : "",
      author_sec_uid: authorInfo && authorInfo.secUid ? String(authorInfo.secUid) : "",
      create_time: aweme && aweme.createTime ? String(aweme.createTime) : "",
      play_count: stats && (stats.playCount || stats.play_count) ? String(stats.playCount || stats.play_count) : "0",
      like_count: stats && (stats.diggCount || stats.likeCount || stats.like_count) ? String(stats.diggCount || stats.likeCount || stats.like_count) : "0",
      comment_count: stats && (stats.commentCount || stats.comment_count) ? String(stats.commentCount || stats.comment_count) : "0",
      collect_count: stats && (stats.collectCount || stats.collect_count) ? String(stats.collectCount || stats.collect_count) : "0",
      share_count: stats && (stats.shareCount || stats.share_count) ? String(stats.shareCount || stats.share_count) : "0",
      text: text.slice(0, 1800),
      url: url,
      image_urls: imageUrls(aweme),
      image_sizes: imageSizes(aweme),
      cover_urls: coverUrls(card, aweme)
    };
  });
  return {
    href: href,
    title: title,
    ready_state: document.readyState,
    verification: gateMarkers > 0
      || /验证码|人机验证|请完成验证|安全验证|滑块验证/i.test(title)
      || /\/verify\b|captcha|verifycenter/i.test(href)
      || (cards.length === 0 && /验证码|人机验证|请完成验证|安全验证|滑块验证/i.test(body)),
    login_required: /扫码登录|手机号登录|登录后查看更多|登录后即可搜索更多精彩视频|一键登录|抖音登录/i.test(pageText)
      && !/退出登录|已登录|个人主页/i.test(body),
    cards: result
  };
})()
""".strip()


_DOUYIN_SCROLL_SCRIPT = r"""
(function () {
  var before = document.querySelectorAll('.search-result-card').length;
  var scrollers = [];
  try { if (document.scrollingElement) scrollers.push(document.scrollingElement); } catch (_) {}
  try {
    Array.prototype.slice.call(document.querySelectorAll('main, [class*="search"], [class*="list"]'))
      .forEach(function (node) { if (node && scrollers.indexOf(node) < 0) scrollers.push(node); });
  } catch (_) {}
  scrollers.forEach(function (node) {
    try { node.scrollTop = node.scrollHeight; } catch (_) {}
  });
  try { window.scrollTo(0, Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)); } catch (_) {}
  var root = document.scrollingElement || document.documentElement;
  var rootTop = Math.max(0, Number(root.scrollTop) || 0);
  var rootHeight = Math.max(0, Number(root.scrollHeight) || 0);
  var rootClient = Math.max(0, Number(root.clientHeight) || 0);
  var rootHasScroll = rootHeight > rootClient + 24;
  var rootAtBottom = rootTop + rootClient >= rootHeight - 8;
  var listScrollables = [];
  try {
    Array.prototype.slice.call(document.querySelectorAll('main, [class*="search"], [class*="list"]'))
      .forEach(function (node) {
        if (!node || node === root) return;
        var rect = node.getBoundingClientRect();
        var style = window.getComputedStyle(node);
        var overflowY = style && style.overflowY || "";
        var height = Number(node.scrollHeight) || 0;
        var client = Number(node.clientHeight) || 0;
        if (rect.height <= 0 || client <= 0 || height <= client + 24
            || !/^(auto|scroll|overlay)$/.test(overflowY)) return;
        var top = Math.max(0, Number(node.scrollTop) || 0);
        listScrollables.push({at_bottom: top + client >= height - 8});
      });
  } catch (_) {}
  var nestedAtBottom = listScrollables.length
    ? listScrollables.every(function (item) { return item.at_bottom; })
    : true;
  var atBottom = rootHasScroll ? (rootAtBottom && nestedAtBottom) : nestedAtBottom;
  return {
    before: before,
    after: document.querySelectorAll('.search-result-card').length,
    at_bottom: atBottom
  };
})()
""".strip()


_DOUYIN_AUTHOR_SNAPSHOT_SCRIPT = r"""
(function () {
  var title = document.title || "";
  var body = document.body ? (document.body.innerText || "") : "";
  function findAweme(value, depth, seen) {
    if (!value || typeof value !== "object" || depth > 8) return null;
    seen = seen || [];
    if (seen.indexOf(value) >= 0) return null;
    seen.push(value);
    try { if (value.awemeInfo && typeof value.awemeInfo === "object") return value.awemeInfo; } catch (_) {}
    var keys = [];
    try { keys = Object.keys(value); } catch (_) { return null; }
    for (var i = 0; i < Math.min(keys.length, 60); i++) {
      try {
        var found = findAweme(value[keys[i]], depth + 1, seen);
        if (found) return found;
      } catch (_) {}
    }
    return null;
  }
  function cardAweme(anchor) {
    var node = anchor;
    for (var depth = 0; node && depth < 8; depth++, node = node.parentElement) {
      var keys = [];
      try { keys = Object.keys(node); } catch (_) { continue; }
      for (var i = 0; i < keys.length; i++) {
        if (!/react/i.test(keys[i])) continue;
        try {
          var aweme = findAweme(node[keys[i]], 0, []);
          if (aweme) return aweme;
        } catch (_) {}
      }
    }
    return null;
  }
  function isWatermarkedUrl(url) {
    return /tplv-dy-water|watermark/i.test(String(url || ""));
  }
  function isPreferredImageExt(url) {
    return /\.(?:jpe?g|png)(?:[?#]|$)/i.test(String(url || ""));
  }
  function pickCleanImageUrl(image) {
    var originals = Array.isArray(image.urlList) ? image.urlList : [];
    var downloads = Array.isArray(image.downloadUrlList) ? image.downloadUrlList : [];
    var buckets = [
      originals.filter(function (u) { return u && !isWatermarkedUrl(u) && isPreferredImageExt(u); }),
      originals.filter(function (u) { return u && !isWatermarkedUrl(u); }),
      downloads.filter(function (u) { return u && !isWatermarkedUrl(u) && isPreferredImageExt(u); }),
      downloads.filter(function (u) { return u && !isWatermarkedUrl(u); })
    ];
    for (var i = 0; i < buckets.length; i++) {
      if (buckets[i].length) return String(buckets[i][0] || "");
    }
    if (image.url && !isWatermarkedUrl(image.url)) return String(image.url);
    return String(originals[0] || image.url || downloads[0] || "");
  }
  function imageUrls(aweme) {
    var values = [];
    var images = Array.isArray(aweme && aweme.images) ? aweme.images : [];
    images.forEach(function (image) {
      if (!image || typeof image !== "object") return;
      var url = pickCleanImageUrl(image);
      if (url && values.indexOf(url) < 0) values.push(url);
    });
    return values.slice(0, 50);
  }
  var links = [];
  var items = [];
  var seen = {};
  Array.prototype.slice.call(document.querySelectorAll('a[href*="/note/"], a[href*="/video/"]')).forEach(function (anchor) {
    var href = anchor.href || "";
    var hrefMatch = href.match(/\/(?:note|video)\/(\d{10,})/i);
    var aweme = cardAweme(anchor);
    var id = aweme && (aweme.awemeId || aweme.groupId || aweme.docId);
    id = id ? String(id) : (hrefMatch ? hrefMatch[1] : "");
    var url = id ? ("https://www.douyin.com/note/" + id) : href;
    var images = imageUrls(aweme);
    var imageArray = Array.isArray(aweme && aweme.images) ? aweme.images : [];
    var awemeType = Number(aweme && aweme.awemeType);
    var mediaType = Number(aweme && aweme.mediaType);
    var photoBadge = !!anchor.querySelector('span.TtoFOFHo, .DQFiFTgl');
    var imageNoteSignal = imageArray.length > 0 && (
      photoBadge || awemeType === 68 || mediaType === 2
    );
    var explicitVideoType = mediaType === 4 || (awemeType === 0 && !imageNoteSignal);
    var video = aweme && aweme.video;
    var playableVideo = !!(video && typeof video === "object" && (
      Number(video.duration) > 0 || video.playAddr || video.playApi ||
      (Array.isArray(video.playAddrUrlList) && video.playAddrUrlList.length) ||
      (Array.isArray(video.playUrlList) && video.playUrlList.length)
    ));
    var hasVideo = explicitVideoType || (!imageNoteSignal && imageArray.length === 0 && playableVideo);
    if (!id || !/^\d{10,}$/.test(id) || !imageNoteSignal || hasVideo || !images.length || seen[id]) return;
    if (links.indexOf(url) < 0) links.push(url);
    seen[id] = true;
    var stats = aweme && (aweme.statistics || aweme.stats);
    var author = aweme && (aweme.authorInfo || aweme.author);
    var description = aweme && (aweme.desc || aweme.itemTitle || aweme.caption);
    items.push({
      id: id,
      url: url,
      title: String(description || anchor.innerText || "").trim().slice(0, 300),
      caption: String(description || anchor.innerText || "").trim().slice(0, 12000),
      text: String(anchor.innerText || description || "").trim().slice(0, 1800),
      author: String(author && (author.nickname || author.name) || "").trim().slice(0, 120),
      author_uid: String(author && (author.uid || author.authorId) || ""),
      author_sec_uid: String(author && author.secUid || ""),
      image_count: images.length,
      image_urls: images,
      image_sizes: (Array.isArray(aweme.images) ? aweme.images : []).map(function (image) {
        return image && image.width && image.height ? String(image.width) + "x" + String(image.height) : "";
      }).filter(Boolean),
      is_photo: true,
      is_video: false,
      aweme_type: aweme && aweme.awemeType != null ? String(aweme.awemeType) : "",
      media_type: aweme && aweme.mediaType != null ? String(aweme.mediaType) : "",
      create_time: aweme && aweme.createTime ? String(aweme.createTime) : "",
      play_count: stats && (stats.playCount || stats.play_count) ? String(stats.playCount || stats.play_count) : "0",
      like_count: stats && (stats.diggCount || stats.likeCount || stats.like_count) ? String(stats.diggCount || stats.likeCount || stats.like_count) : "0",
      comment_count: stats && (stats.commentCount || stats.comment_count) ? String(stats.commentCount || stats.comment_count) : "0",
      collect_count: stats && (stats.collectCount || stats.collect_count) ? String(stats.collectCount || stats.collect_count) : "0",
      share_count: stats && (stats.shareCount || stats.share_count) ? String(stats.shareCount || stats.share_count) : "0"
    });
  });
  var root = document.scrollingElement || document.documentElement;
  return {
    href: location.href,
    title: title,
    readyState: document.readyState,
    verification: /验证码|人机验证|请完成验证|安全验证|captcha|challenge/i.test(title + " " + body.slice(0, 1200)),
    login_required: /扫码登录|手机号登录|登录后查看|一键登录/i.test(body)
      && !/退出登录|已登录|个人主页/i.test(body),
    links: links.slice(0, 80),
    items: items.slice(0, 80),
    height: root ? root.scrollHeight : 0,
    top: root ? root.scrollTop : 0
  };
})()
""".strip()


_XHS_SEARCH_SNAPSHOT_SCRIPT = r"""
(function () {
  var body = document.body ? (document.body.innerText || "") : "";
  var href = String(location.href || "");
  var title = document.title || "";
  var cards = Array.prototype.slice.call(document.querySelectorAll('section.note-item, [data-index]'));
  var items = [];
  var seen = {};
  cards.forEach(function (card, index) {
    var linkEl = card.querySelector('a[href*="/explore/"], a[href*="/search_result/"]') || card.querySelector('a[href]');
    if (!linkEl) return;
    var rawHref = String(linkEl.href || linkEl.getAttribute('href') || "");
    var m = rawHref.match(/\/(?:explore|search_result)\/([0-9a-fA-F]{12,})/);
    var id = m ? m[1] : "";
    if (!id || seen[id]) return;
    seen[id] = true;
    var fullUrl = rawHref.startsWith('http') ? rawHref : ('https://www.xiaohongshu.com/explore/' + id);
    var titleEl = card.querySelector('.title span, .title, a.title');
    var authorEl = card.querySelector('.author .name, .author-wrapper .name, .name');
    var likeEl = card.querySelector('.like-wrapper .count, .count');
    var imgEl = card.querySelector('img');
    var imgSrc = imgEl ? String(imgEl.currentSrc || imgEl.src || imgEl.getAttribute('src') || "") : "";
    var isVideo = !!(card.querySelector('.play-icon, svg.play-icon, [class*="video-icon"]'));
    items.push({
      index: index,
      id: id,
      url: fullUrl,
      title: String((titleEl && titleEl.innerText) || "").trim().slice(0, 200),
      author: String((authorEl && authorEl.innerText) || "").trim().slice(0, 100),
      like_count: String((likeEl && likeEl.innerText) || "0").trim(),
      is_video: isVideo,
      is_photo: !isVideo,
      image_count: isVideo ? 0 : 1,
      cover_urls: imgSrc ? [imgSrc] : [],
      image_urls: imgSrc ? [imgSrc] : []
    });
  });
  var gate = /验证码|滑块|安全验证|访问受限|请完成验证/i.test(title + " " + body.slice(0, 1200));
  var loginWall = /登录解锁更多|扫码登录|手机号登录/i.test(body.slice(0, 1500)) && items.length === 0;
  return {
    href: href,
    title: title,
    verification: gate,
    login_required: loginWall,
    cards: items
  };
})()
""".strip()


def _build_douyin_search_url(
    keyword: str,
    web_sort: str = "综合排序",
    web_publish_time: str = "不限",
    media_type: str = "image",
) -> str:
    sort_map = {"最多点赞": "1", "最新发布": "2", "1": "1", "2": "2"}
    pub_map = {"一天内": "1", "一周内": "7", "半年内": "180", "1": "1", "7": "7", "180": "180"}
    search_tab = "video" if str(media_type or "").strip().lower() == "video" else "general"
    url = "https://www.douyin.com/search/" + quote(str(keyword or "").strip(), safe="") + f"?type={search_tab}"
    sort_code = sort_map.get(str(web_sort or "").strip())
    if sort_code:
        url += f"&sort_type={sort_code}"
    pub_code = pub_map.get(str(web_publish_time or "").strip())
    if pub_code:
        url += f"&publish_time={pub_code}"
    return url


def _detect_available_browser_channel() -> str:
    if os.name == "nt":
        edge_paths = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        if any(p.is_file() for p in edge_paths):
            return "msedge"
        chrome_paths = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        if any(p.is_file() for p in chrome_paths):
            return "chrome"
    return "chromium"


def _sanitize_json_unicode(value: Any) -> Any:
    if isinstance(value, str):
        return "".join("\ufffd" if 0xD800 <= ord(ch) <= 0xDFFF else ch for ch in value)
    if isinstance(value, list):
        return [_sanitize_json_unicode(v) for v in value]
    if isinstance(value, dict):
        return {
            (_sanitize_json_unicode(k) if isinstance(k, str) else k): _sanitize_json_unicode(v)
            for k, v in value.items()
        }
    return value


def _resolve_reachable_proxy(proxy_url: str = "") -> Optional[str]:
    candidates = [str(proxy_url or "").strip()]
    for env_key in ("JIANGHU_PROXY_URL", "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(env_key, "").strip()
        if v:
            candidates.append(v)
    for raw in candidates:
        if not raw:
            continue
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https", "socks5"} or not parsed.hostname:
            continue
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        sock = socket.socket()
        sock.settimeout(0.35)
        try:
            if sock.connect_ex((parsed.hostname, port)) == 0:
                return raw
        except OSError:
            pass
        finally:
            try:
                sock.close()
            except OSError:
                pass
    return None


def _find_browser_hwnd(user32: Any, wintypes: Any, title_hint: str = "") -> int:
    import ctypes

    clean_hint = (title_hint or "").strip()[:36]
    matched: List[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lp):
        if not (user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd)):
            return True
        tbuf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, tbuf, 256)
        title = tbuf.value.strip()
        if not title or "万能采集器" in title:
            return True
        cbuf = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cbuf, 128)
        if cbuf.value != "Chrome_WidgetWin_1":
            return True
        if clean_hint and clean_hint in title:
            matched.insert(0, hwnd)
        elif any(tok in title for tok in ("抖音", "小红书", "哔哩哔哩", "bilibili", "verify", "captcha", "about:blank", "新标签页", "New Tab")):
            matched.append(hwnd)
        return True

    user32.EnumWindows(_cb, 0)
    if not matched:
        fg = user32.GetForegroundWindow()
        if fg:
            tbuf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(fg, tbuf, 256)
            cbuf = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(fg, cbuf, 128)
            if cbuf.value == "Chrome_WidgetWin_1" and "万能采集器" not in tbuf.value:
                matched.append(fg)
    return matched[0] if matched else 0


def _win32_minimize_browser_window(title_hint: str = "") -> int:
    """Clear topmost flag and minimize the Chromium browser window to taskbar."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = _find_browser_hwnd(user32, wintypes, title_hint)
        if not hwnd:
            return 0
        user32.SetWindowPos(hwnd, wintypes.HWND(-2), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # NOTOPMOST|NOSIZE|NOMOVE|NOACTIVATE
        user32.ShowWindow(hwnd, 7)  # SW_SHOWMINNOACTIVE
        return 1
    except Exception:
        return 0


def _win32_raise_browser_window(title_hint: str = "", *, topmost: bool = True) -> int:
    """Restore from minimized/hidden state, center onscreen, and raise Chromium HWND."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        from ctypes import wintypes

        class _RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [
            wintypes.HWND, wintypes.HWND,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(_RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.BringWindowToTop.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]

        target_hwnd = _find_browser_hwnd(user32, wintypes, title_hint)
        if not target_hwnd:
            return 0
        sw = max(800, int(user32.GetSystemMetrics(0) or 1920))
        sh = max(600, int(user32.GetSystemMetrics(1) or 1080))
        insert_after = wintypes.HWND(-1 if topmost else -2)

        user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
        rect = _RECT()
        user32.GetWindowRect(target_hwnd, ctypes.byref(rect))
        cur_w = rect.right - rect.left
        cur_h = rect.bottom - rect.top
        w = max(960, min(1360, cur_w if cur_w >= 300 else 1280))
        h = max(680, min(900, cur_h if cur_h >= 200 else 840))
        x = max(30, (sw - w) // 2)
        y = max(24, (sh - h) // 2)
        user32.SetWindowPos(target_hwnd, insert_after, x, y, w, h, 0x0040)

        fg_hwnd = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
        cur_tid = kernel32.GetCurrentThreadId()
        attached = False
        try:
            if fg_tid and fg_tid != cur_tid:
                attached = bool(user32.AttachThreadInput(cur_tid, fg_tid, True))
            user32.BringWindowToTop(target_hwnd)
            user32.SetForegroundWindow(target_hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_tid, fg_tid, False)
        return 1
    except Exception:
        return 0


def _candidate_records(
    snapshot: Dict[str, Any],
    max_items: int,
    *,
    min_images: int = 0,
    max_images: int = 50,
    allow_video: bool = False,
    media_type: str = "",
    no_filter: bool = False,
) -> List[Dict[str, Any]]:
    cards = snapshot.get("cards") if isinstance(snapshot, dict) else None
    if not isinstance(cards, list):
        return []
    mtype = str(media_type or "").strip().lower()
    if mtype not in {"image", "video", "all"}:
        mtype = "all" if allow_video else "image"
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        rid = str(card.get("id") or "").strip()
        if not rid or rid in seen:
            continue
        is_video = bool(card.get("is_video"))
        is_photo = bool(card.get("is_photo"))
        if not no_filter:
            if mtype == "image":
                if is_video or not is_photo:
                    continue
                img_cnt = int(card.get("image_count") or len(card.get("image_urls") or []) or 0)
                if not (min_images <= img_cnt <= max_images):
                    continue
            elif mtype == "video":
                if not is_video:
                    continue
            else:
                if not is_video:
                    img_cnt = int(card.get("image_count") or len(card.get("image_urls") or []) or 0)
                    if not is_photo or not (min_images <= img_cnt <= max_images):
                        continue
        seen.add(rid)
        out.append(card)
        if len(out) >= max_items:
            break
    return out


class NativeBrowserCollector:
    """Single-owner Playwright persistent Edge/Chrome collector engine."""

    PLATFORM_LOGIN_URLS = {
        "douyin": "https://www.douyin.com/",
        "xiaohongshu": "https://www.xiaohongshu.com/",
        "bilibili": "https://www.bilibili.com/",
    }

    def __init__(self, profile_dir: Optional[str | Path] = None):
        env_dir = os.environ.get("XHS_DL_BROWSER_PROFILE_DIR", "").strip()
        self.profile_dir = Path(profile_dir or env_dir or DEFAULT_PROFILE_DIR).expanduser()
        self._state_lock = threading.Lock()
        self._cmd_queue: queue.Queue = queue.Queue()
        self._worker_started = False
        self._worker_lock = threading.Lock()
        self._pw = None
        self._context = None
        self._page = None
        self._cdp = None
        self._channel_used = ""
        self._active_platform = "douyin"
        self._busy = False
        self._verification_required = False
        self._cancel_event = threading.Event()
        self._paused_job: Optional[Dict[str, Any]] = None
        self._keyword_progress: Dict[str, Any] = {}

    # ── Worker thread plumbing (Playwright sync API thread-safety) ────
    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker_started:
                return
            self._worker_started = True
            t = threading.Thread(target=self._worker_loop, daemon=True, name="native-browser-worker")
            t.start()

    def _worker_loop(self) -> None:
        while True:
            fn, fut = self._cmd_queue.get()
            try:
                res = fn()
                fut.set_result(res)
            except Exception as exc:
                fut.set_exception(exc)

    def _call_browser(self, fn: Callable[[], Any], timeout: float = 120.0) -> Any:
        self._ensure_worker()
        fut: Future = Future()
        self._cmd_queue.put((fn, fut))
        return fut.result(timeout=timeout)

    def _close_browser_in_worker(self) -> None:
        try:
            if self._cdp is not None:
                self._cdp.detach()
        except Exception:
            pass
        try:
            if self._context is not None:
                self._context.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                self._pw.stop()
        except Exception:
            pass
        self._cdp = None
        self._page = None
        self._context = None
        self._pw = None

    def _build_launch_args(self) -> List[str]:
        return [
            "--disable-blink-features=AutomationControlled",
            "--window-position=140,70",
            "--window-size=1280,840",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=msEdgeSidebarV2",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-background-timer-throttling",
        ]

    def _ensure_page_in_worker(self, proxy_url: str = "", start_minimized: bool = True) -> Any:
        if self._context is not None:
            try:
                if self._page is None or self._page.is_closed():
                    pages = self._context.pages
                    self._page = pages[0] if pages else self._context.new_page()
                    self._cdp = self._context.new_cdp_session(self._page)
                # Touch title to confirm context is alive
                _ = self._page.url
                return self._page
            except Exception:
                self._close_browser_in_worker()

        from playwright.sync_api import sync_playwright

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        # Clear stale SingletonLock left by hard-killed previous processes
        for lock_name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lp = self.profile_dir / lock_name
            if lp.exists() or lp.is_symlink():
                try:
                    lp.unlink(missing_ok=True)
                except OSError:
                    pass

        self._pw = sync_playwright().start()
        proxy = _resolve_reachable_proxy(proxy_url)
        launch_args = self._build_launch_args()
        last_exc: Optional[Exception] = None
        for channel in ("msedge", "chrome", None):
            for use_sandbox in (True, False):
                try:
                    kwargs: Dict[str, Any] = {
                        "user_data_dir": str(self.profile_dir),
                        "headless": False,
                        "viewport": None,
                        "locale": "zh-CN",
                        "chromium_sandbox": use_sandbox,
                        "args": launch_args,
                        "ignore_default_args": ["--enable-automation"],
                    }
                    if channel:
                        kwargs["channel"] = channel
                    if proxy:
                        kwargs["proxy"] = {"server": proxy}
                    self._context = self._pw.chromium.launch_persistent_context(**kwargs)
                    self._channel_used = channel or "chromium"
                    break
                except Exception as exc:
                    last_exc = exc
            if self._context is not None:
                break
        if self._context is None:
            self._close_browser_in_worker()
            raise RuntimeError(f"无法启动内置浏览器组件：{last_exc}")

        try:
            self._context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
            )
        except Exception:
            pass
        pages = self._context.pages
        self._page = pages[0] if pages else self._context.new_page()
        try:
            self._cdp = self._context.new_cdp_session(self._page)
        except Exception:
            self._cdp = None
        if start_minimized:
            self._minimize_window_in_worker()
        return self._page

    def _minimize_window_in_worker(self) -> int:
        if self._context is None or self._page is None or self._page.is_closed():
            return 0
        title = ""
        try:
            title = str(self._page.title() or "")
        except Exception:
            pass
        cdp_done = False
        if self._cdp is not None:
            try:
                info = self._cdp.send("Browser.getWindowForTarget")
                wid = info.get("windowId")
                if wid is not None:
                    self._cdp.send(
                        "Browser.setWindowBounds",
                        {"windowId": wid, "bounds": {"windowState": "minimized"}},
                    )
                    cdp_done = True
            except Exception:
                pass
        win_done = _win32_minimize_browser_window(title)
        return 1 if (cdp_done or win_done) else 0

    def _move_window_cdp_in_worker(self, left: int, top: int, width: int = 1280, height: int = 840) -> None:
        if self._cdp is None or self._page is None or self._page.is_closed():
            return
        try:
            info = self._cdp.send("Browser.getWindowForTarget")
            wid = info.get("windowId")
            if wid is not None:
                self._cdp.send(
                    "Browser.setWindowBounds",
                    {"windowId": wid, "bounds": {"windowState": "normal"}},
                )
                self._cdp.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": wid,
                        "bounds": {
                            "left": int(left),
                            "top": int(top),
                            "width": int(width),
                            "height": int(height),
                            "windowState": "normal",
                        },
                    },
                )
        except Exception:
            pass

    def _bring_to_front_in_worker(self, *, topmost: bool = True, open_url: str = "", proxy_url: str = "") -> int:
        page = self._ensure_page_in_worker(proxy_url=proxy_url, start_minimized=False)
        if open_url:
            try:
                page.goto(open_url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
        sw, sh = 1920, 1080
        if os.name == "nt":
            try:
                import ctypes
                sw = max(800, int(ctypes.windll.user32.GetSystemMetrics(0) or 1920))
                sh = max(600, int(ctypes.windll.user32.GetSystemMetrics(1) or 1080))
            except Exception:
                pass
        left = max(30, (sw - 1280) // 2)
        top = max(24, (sh - 840) // 2)
        self._move_window_cdp_in_worker(left, top, 1280, 840)
        try:
            page.bring_to_front()
        except Exception:
            pass
        title = ""
        try:
            title = str(page.title() or "")
        except Exception:
            pass
        focused = _win32_raise_browser_window(title, topmost=topmost)
        return max(1, focused)

    def _hide_window_in_worker(self) -> int:
        return self._minimize_window_in_worker()

    # ── Public engine controls ────────────────────────────────────────
    def get_capabilities(self) -> Dict[str, Any]:
        with self._state_lock:
            return {
                "available": True,
                "status": "online",
                "engine_mode": "native-playwright",
                "browser_channel": self._channel_used or _detect_available_browser_channel(),
                "browser_ready": self._context is not None,
                "age_seconds": 0.0,
                "active_platform": self._active_platform,
                "verification_required": self._verification_required,
                "busy": self._busy,
                "keyword_progress": dict(self._keyword_progress),
                "supports": {
                    "homepage": ["douyin"],
                    "keyword": ["douyin", "xiaohongshu"],
                    "xiaohongshu_homepage": False,
                },
            }

    def start_engine(self, platform: str = "douyin", proxy_url: str = "") -> Dict[str, Any]:
        plat = "xiaohongshu" if str(platform).lower() in {"xiaohongshu", "xhs", "小红书"} else "douyin"
        with self._state_lock:
            self._active_platform = plat
            self._verification_required = False
        self._call_browser(lambda: self._ensure_page_in_worker(proxy_url=proxy_url), timeout=35.0)
        ch = self._channel_used or _detect_available_browser_channel()
        ch_name = "Edge" if ch == "msedge" else ("Chrome" if ch == "chrome" else "Chromium")
        return {
            "status": "ok",
            "platform": plat,
            "engine_mode": "native-playwright",
            "browser_channel": ch,
            "message": f"内置 {ch_name} 浏览器采集核心已在线就绪",
        }

    def open_platform_login(self, platform: str = "douyin", proxy_url: str = "", topmost: bool = False) -> Dict[str, Any]:
        raw = str(platform or "douyin").strip().lower()
        plat = raw if raw in self.PLATFORM_LOGIN_URLS else "douyin"
        url = self.PLATFORM_LOGIN_URLS[plat]
        with self._state_lock:
            if plat in {"douyin", "xiaohongshu"}:
                self._active_platform = plat
            self._verification_required = False
        focused = self._call_browser(
            lambda: self._bring_to_front_in_worker(topmost=topmost, open_url=url, proxy_url=proxy_url),
            timeout=35.0,
        )
        plat_cn = {"douyin": "抖音", "xiaohongshu": "小红书", "bilibili": "B站"}.get(plat, plat)
        return {
            "status": "ok",
            "platform": plat,
            "windows_focused": focused,
            "message": f"已在屏幕中央打开 {plat_cn} 持久化登录浏览器，扫码/登录后点击“收起浏览器”即可永久保存会话",
        }

    def bring_verify_browser(
        self,
        platform: str = "douyin",
        topmost: bool = True,
        open_login: bool = False,
        proxy_url: str = "",
    ) -> int:
        if open_login:
            res = self.open_platform_login(platform=platform, proxy_url=proxy_url, topmost=topmost)
            return int(res.get("windows_focused") or 1)
        target_url = ""
        try:
            cur_url = self._call_browser(
                lambda: str(self._page.url) if (self._page and not self._page.is_closed()) else "",
                timeout=5.0,
            )
        except Exception:
            cur_url = ""
        if not cur_url or cur_url.startswith("about:"):
            target_url = self.PLATFORM_LOGIN_URLS.get(platform or "douyin", "https://www.douyin.com/")
        return int(
            self._call_browser(
                lambda: self._bring_to_front_in_worker(topmost=topmost, open_url=target_url, proxy_url=proxy_url),
                timeout=35.0,
            )
        )

    def hide_browser(self) -> Dict[str, Any]:
        try:
            n = self._call_browser(self._hide_window_in_worker, timeout=10.0)
        except Exception:
            n = 0
        return {"status": "ok", "windows_hidden": n, "message": "已将内置采集浏览器静默收起到后台"}

    def stop_collection(self) -> Dict[str, Any]:
        self._cancel_event.set()
        return {"status": "ok", "message": "已向当前采集任务发送停止信号"}

    def consume_paused_job(self) -> Optional[Dict[str, Any]]:
        with self._state_lock:
            job = self._paused_job
            self._paused_job = None
            self._verification_required = False
            return dict(job) if isinstance(job, dict) else None

    def close(self) -> None:
        if not self._worker_started:
            return
        try:
            self._call_browser(self._close_browser_in_worker, timeout=10.0)
        except Exception:
            pass

    # ── Core Douyin keyword collection ────────────────────────────────
    def _set_progress(self, **patch: Any) -> None:
        with self._state_lock:
            self._keyword_progress.update(patch)
            self._keyword_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def collect_douyin_keyword(
        self,
        keyword: str,
        *,
        count: int = 20,
        min_images: int = 4,
        max_images: int = 20,
        allow_video: bool = False,
        media_type: str = "",
        no_filter: bool = False,
        all_results: bool = False,
        direct_download: bool = True,
        web_sort: str = "综合排序",
        web_publish_time: str = "不限",
        skip_ids: Optional[Iterable[str]] = None,
        output_dir: str = "",
        image_format: str = "jpg",
        title_template: str = DEFAULT_TITLE_TEMPLATE,
        set_file_time: bool = True,
        proxy_url: str = "",
        on_gate_cb: Optional[Callable[[str, str], None]] = None,
        job_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        kw = str(keyword or "").strip()
        if not kw:
            return {"status": "error", "success": False, "message": "关键词不能为空"}
        eff_media_type = str(media_type or "").strip().lower()
        if eff_media_type not in {"image", "video", "all"}:
            eff_media_type = "all" if allow_video else "image"
        skip_set = {str(x).strip() for x in (skip_ids or []) if str(x).strip()}
        target = MAX_SEARCH_CANDIDATES if all_results or int(count) == 0 else max(1, min(MAX_SEARCH_CANDIDATES, int(count)))

        self._cancel_event.clear()
        with self._state_lock:
            self._active_platform = "douyin"
            self._busy = True
            self._verification_required = False
            self._keyword_progress = {
                "phase": "starting",
                "status": "running",
                "keyword": kw,
                "target": 0 if all_results else target,
                "total": 0,
                "qualified": 0,
                "crawled": 0,
                "downloaded": 0,
                "keywords_done": 0,
                "keywords_total": 1,
                "message": f"正在打开抖音搜索列表：【{kw}】",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        search_url = _build_douyin_search_url(
            kw,
            web_sort=web_sort,
            web_publish_time=web_publish_time,
            media_type=eff_media_type,
        )
        try:
            def _open_and_wait():
                page = self._ensure_page_in_worker(proxy_url=proxy_url)
                cur = ""
                try:
                    cur = str(page.url or "")
                except Exception:
                    cur = ""
                # Reuse page if user just solved verification on the exact search URL
                same_search = quote(kw, safe="") in cur and "douyin.com/search" in cur
                if not same_search:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                else:
                    snap_now = page.evaluate(_DOUYIN_SEARCH_SNAPSHOT_SCRIPT)
                    if not (isinstance(snap_now, dict) and (snap_now.get("cards") or [])):
                        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                deadline = time.monotonic() + 25.0
                latest: Dict[str, Any] = {}
                while time.monotonic() < deadline:
                    if self._cancel_event.is_set():
                        return {"cancelled": True, "snapshot": latest}
                    snap = page.evaluate(_DOUYIN_SEARCH_SNAPSHOT_SCRIPT)
                    if isinstance(snap, dict):
                        latest = snap
                        if snap.get("verification") or snap.get("login_required") or (snap.get("cards") or []):
                            return {"cancelled": False, "snapshot": snap}
                    time.sleep(0.6)
                return {"cancelled": False, "snapshot": latest}

            open_res = self._call_browser(_open_and_wait, timeout=45.0)
            if open_res.get("cancelled"):
                self._set_progress(phase="cancelled", status="cancelled", message="关键词采集已停止")
                return {"status": "cancelled", "success": False, "stage": "browser", "message": "关键词采集已停止"}

            snap = open_res.get("snapshot") if isinstance(open_res.get("snapshot"), dict) else {}
            if snap.get("verification") or snap.get("login_required"):
                gate_status = "verification_required" if snap.get("verification") else "login_required"
                gate_msg = (
                    "抖音弹出人机验证，已自动弹窗并置顶浏览器，请人工完成验证后点击「已完成验证，继续采集」"
                    if gate_status == "verification_required"
                    else "抖音提示需要登录，已自动弹出浏览器，请扫码登录后点击「已完成验证，继续采集」"
                )
                with self._state_lock:
                    self._verification_required = True
                    self._paused_job = dict(job_request or {"kind": "keyword", "platform": "douyin", "keyword": kw})
                try:
                    self._call_browser(lambda: self._bring_to_front_in_worker(topmost=True), timeout=10.0)
                except Exception:
                    pass
                self._set_progress(phase="verification", status=gate_status, message=gate_msg)
                if callable(on_gate_cb):
                    try:
                        on_gate_cb(gate_status, gate_msg)
                    except Exception:
                        pass
                return {
                    "status": gate_status,
                    "success": False,
                    "stage": "browser",
                    "completion_confirmed": False,
                    "message": gate_msg,
                }

            all_cards: Dict[str, Dict[str, Any]] = {}
            crawled_ids: Set[str] = set()

            def _absorb(s: Dict[str, Any]) -> None:
                for card in (s.get("cards") or []):
                    if not isinstance(card, dict):
                        continue
                    cid = str(card.get("id") or f"idx:{card.get('index')}")
                    crawled_ids.add(cid)
                    if card.get("id"):
                        prev = all_cards.get(str(card["id"]), {})
                        merged = dict(prev)
                        for k, v in card.items():
                            if v not in (None, "", [], {}):
                                merged[k] = v
                        all_cards[str(card["id"])] = merged

            _absorb(snap)
            idle_rounds = 0
            seen_count = len(crawled_ids)
            for _ in range(MAX_SEARCH_SCROLL_ROUNDS):
                if self._cancel_event.is_set():
                    break
                cur_list = _candidate_records(
                    {"cards": list(all_cards.values())},
                    MAX_SEARCH_CANDIDATES,
                    min_images=min_images,
                    max_images=max_images,
                    allow_video=allow_video,
                    media_type=eff_media_type,
                    no_filter=no_filter,
                )
                fresh_list = [c for c in cur_list if str(c.get("id") or "") not in skip_set]
                dup_skipped = len(cur_list) - len(fresh_list)
                self._set_progress(
                    phase="crawling",
                    crawled=len(crawled_ids),
                    qualified=len(fresh_list),
                    total=len(crawled_ids),
                    message=f"正在滚动读取抖音搜索列表；已抓到 {len(fresh_list)} 条新合格作品（已扫描 {len(crawled_ids)}，去重 {dup_skipped}）",
                )
                if len(fresh_list) >= target:
                    break

                def _scroll_and_snap():
                    page = self._ensure_page_in_worker(proxy_url=proxy_url)
                    sc = page.evaluate(_DOUYIN_SCROLL_SCRIPT)
                    time.sleep(SEARCH_SCROLL_SETTLE_SECONDS)
                    nxt = page.evaluate(_DOUYIN_SEARCH_SNAPSHOT_SCRIPT)
                    return sc, nxt

                sc, nxt = self._call_browser(_scroll_and_snap, timeout=25.0)
                if isinstance(nxt, dict):
                    if nxt.get("verification") or nxt.get("login_required"):
                        gate_status = "verification_required" if nxt.get("verification") else "login_required"
                        gate_msg = "抖音滚动过程中弹出人机验证，已置顶浏览器等待人工验证"
                        with self._state_lock:
                            self._verification_required = True
                            self._paused_job = dict(job_request or {"kind": "keyword", "platform": "douyin", "keyword": kw})
                        try:
                            self._call_browser(lambda: self._bring_to_front_in_worker(topmost=True), timeout=10.0)
                        except Exception:
                            pass
                        self._set_progress(phase="verification", status=gate_status, message=gate_msg)
                        if callable(on_gate_cb):
                            try:
                                on_gate_cb(gate_status, gate_msg)
                            except Exception:
                                pass
                        return {
                            "status": gate_status,
                            "success": False,
                            "stage": "browser",
                            "completion_confirmed": False,
                            "message": gate_msg,
                        }
                    _absorb(nxt)

                if len(crawled_ids) > seen_count:
                    seen_count = len(crawled_ids)
                    idle_rounds = 0
                else:
                    idle_rounds += 1
                    at_bottom = isinstance(sc, dict) and sc.get("at_bottom") is True
                    if idle_rounds >= (3 if at_bottom else 5):
                        break

            qualified_all = _candidate_records(
                {"cards": list(all_cards.values())},
                MAX_SEARCH_CANDIDATES,
                min_images=min_images,
                max_images=max_images,
                allow_video=allow_video,
                media_type=eff_media_type,
                no_filter=no_filter,
            )
            fresh = [c for c in qualified_all if str(c.get("id") or "") not in skip_set][:target]
            skipped_dup_count = max(0, len(qualified_all) - len([c for c in qualified_all if str(c.get("id") or "") not in skip_set]))

            candidates_out: List[Dict[str, Any]] = []
            for idx, item in enumerate(fresh, 1):
                row = dict(item)
                row["keyword"] = kw
                row["index"] = idx
                row["artwork_type"] = "视频" if row.get("is_video") else "图文"
                row["likes"] = int(str(item.get("like_count") or "0") or 0) if str(item.get("like_count") or "0").isdigit() else 0
                row["comments"] = int(str(item.get("comment_count") or "0") or 0) if str(item.get("comment_count") or "0").isdigit() else 0
                row["favorites"] = int(str(item.get("collect_count") or "0") or 0) if str(item.get("collect_count") or "0").isdigit() else 0
                row["shares"] = int(str(item.get("share_count") or "0") or 0) if str(item.get("share_count") or "0").isdigit() else 0
                candidates_out.append(row)

            links = [str(c.get("url") or "") for c in candidates_out if c.get("url")]

            if not candidates_out:
                if skipped_dup_count:
                    zero_msg = f"共发现 {skipped_dup_count} 条合格作品，均已历史采集过，本次自动去重跳过"
                elif eff_media_type == "video":
                    zero_msg = "未发现符合条件的视频作品"
                elif eff_media_type == "all":
                    zero_msg = "未发现符合条件（图文/视频）的作品"
                else:
                    zero_msg = f"未发现符合条件（{min_images}-{max_images} 张无水印图文）的作品"
                self._set_progress(phase="completed", status="completed_zero", crawled=len(crawled_ids), qualified=0, message=zero_msg)
                return {
                    "status": "completed_zero",
                    "success": True,
                    "stage": "completed",
                    "candidates": [],
                    "discovered_links": [],
                    "skipped_duplicate_count": skipped_dup_count,
                    "completion_confirmed": True,
                    "message": zero_msg,
                }

            download_items: List[Dict[str, Any]] = []
            total_media = 0
            if direct_download:
                from xhs_dl.web import toolbox_store

                dl_cfg = {
                    "image_format": image_format or "jpg",
                    "title_template": title_template or DEFAULT_TITLE_TEMPLATE,
                    "set_file_time_to_publish": bool(set_file_time),
                }
                base_out = output_dir or str(Path.home() / "Downloads")
                for pos, row in enumerate(candidates_out, 1):
                    if self._cancel_event.is_set():
                        break
                    self._set_progress(
                        phase="downloading",
                        downloaded=len(download_items),
                        qualified=len(candidates_out),
                        message=f"正在高清无水印下载第 {pos}/{len(candidates_out)} 套：{str(row.get('title') or '')[:24]}",
                    )
                    try:
                        if row.get("image_urls"):
                            info, _fb = toolbox_store._download_single_artwork_row(row, base_out, download_settings=dl_cfg)
                            if info:
                                dl_item = dict(row)
                                dl_item["downloaded"] = True
                                dl_item["completion_confirmed"] = True
                                dl_item["save_directory"] = info["save_path"]
                                dl_item["image_count"] = info["image_count"]
                                dl_item["media_file_count"] = info["image_count"]
                                dl_item["download_status"] = f"已下载 {info['image_count']} 张图"
                                download_items.append(dl_item)
                                total_media += int(info["image_count"] or 0)
                        elif row.get("is_video") and row.get("url"):
                            from xhs_dl.unified import UnifiedDownloader

                            vdl = UnifiedDownloader(output_dir=base_out, image_format=image_format or "jpg")
                            vres = vdl.download([str(row["url"])])
                            vitem = (getattr(vres, "items", None) or [None])[0]
                            save_dir = str(getattr(vitem, "save_dir", "") or "").strip() if vitem else ""
                            if vitem and getattr(vitem, "success", False) and save_dir:
                                dl_item = dict(row)
                                dl_item["downloaded"] = True
                                dl_item["completion_confirmed"] = True
                                dl_item["save_directory"] = save_dir
                                dl_item["download_status"] = "已下载视频"
                                download_items.append(dl_item)
                    except Exception:
                        continue

            done_cnt = len(download_items) if direct_download else len(candidates_out)
            done_msg = (
                f"已完成，采集并下载 {len(download_items)} 套（{total_media} 张无水印图）"
                if direct_download
                else f"已回填 {len(candidates_out)} 条合格作品到作品列表"
            )
            self._set_progress(
                phase="completed",
                status="completed",
                crawled=len(crawled_ids),
                qualified=len(candidates_out),
                downloaded=len(download_items),
                keywords_done=1,
                message=done_msg,
            )
            return {
                "status": "completed",
                "success": True,
                "stage": "completed",
                "candidates": candidates_out,
                "discovered_links": links,
                "download": {
                    "items": download_items,
                    "success_count": len(download_items),
                } if direct_download else {},
                "media_file_count": total_media,
                "skipped_duplicate_count": skipped_dup_count,
                "completion_confirmed": done_cnt > 0,
                "message": done_msg,
            }
        finally:
            with self._state_lock:
                self._busy = False

    def collect_douyin_homepage(
        self,
        profile_url: str,
        *,
        max_works: int = 10,
        min_images: int = 4,
        max_images: int = 20,
        direct_download: bool = True,
        skip_ids: Optional[Iterable[str]] = None,
        output_dir: str = "",
        image_format: str = "jpg",
        title_template: str = DEFAULT_TITLE_TEMPLATE,
        set_file_time: bool = True,
        proxy_url: str = "",
        on_gate_cb: Optional[Callable[[str, str], None]] = None,
        job_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        target_url = str(profile_url or "").strip()
        skip_set = {str(x).strip() for x in (skip_ids or []) if str(x).strip()}
        limit = max(1, min(50, int(max_works or 10)))
        self._cancel_event.clear()
        with self._state_lock:
            self._active_platform = "douyin"
            self._busy = True
            self._verification_required = False

        try:
            def _open_author():
                page = self._ensure_page_in_worker(proxy_url=proxy_url)
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                deadline = time.monotonic() + 20.0
                latest: Dict[str, Any] = {}
                while time.monotonic() < deadline:
                    snap = page.evaluate(_DOUYIN_AUTHOR_SNAPSHOT_SCRIPT)
                    if isinstance(snap, dict):
                        latest = snap
                        if snap.get("verification") or snap.get("login_required") or (snap.get("items") or []):
                            return snap
                    time.sleep(0.7)
                return latest

            snap = self._call_browser(_open_author, timeout=40.0)
            if isinstance(snap, dict) and (snap.get("verification") or snap.get("login_required")):
                gate_status = "verification_required" if snap.get("verification") else "login_required"
                gate_msg = "抖音主页触发人机验证或登录提示，已置顶弹出浏览器"
                with self._state_lock:
                    self._verification_required = True
                    self._paused_job = dict(job_request or {"kind": "homepage", "platform": "douyin", "profile_url": target_url})
                try:
                    self._call_browser(lambda: self._bring_to_front_in_worker(topmost=True), timeout=10.0)
                except Exception:
                    pass
                if callable(on_gate_cb):
                    try:
                        on_gate_cb(gate_status, gate_msg)
                    except Exception:
                        pass
                return {"status": gate_status, "success": False, "stage": "browser", "message": gate_msg}

            items_by_id: Dict[str, Dict[str, Any]] = {}
            for _ in range(10):
                if isinstance(snap, dict):
                    for it in (snap.get("items") or []):
                        if isinstance(it, dict) and it.get("id"):
                            items_by_id[str(it["id"])] = it
                filtered = [
                    it for it in items_by_id.values()
                    if min_images <= int(it.get("image_count") or 0) <= max_images
                ]
                fresh = [it for it in filtered if str(it.get("id") or "") not in skip_set]
                if len(fresh) >= limit or self._cancel_event.is_set():
                    break

                def _scroll_author():
                    page = self._ensure_page_in_worker(proxy_url=proxy_url)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.1)
                    return page.evaluate(_DOUYIN_AUTHOR_SNAPSHOT_SCRIPT)

                snap = self._call_browser(_scroll_author, timeout=20.0)

            filtered_all = [
                it for it in items_by_id.values()
                if min_images <= int(it.get("image_count") or 0) <= max_images
            ]
            fresh_all = [it for it in filtered_all if str(it.get("id") or "") not in skip_set]
            skipped_dup = max(0, len(filtered_all) - len(fresh_all))
            chosen = fresh_all[:limit]
            for it in chosen:
                it["keyword"] = "作者主页"

            links = [str(it.get("url") or "") for it in chosen if it.get("url")]
            download_items: List[Dict[str, Any]] = []
            total_media = 0
            if direct_download and chosen:
                from xhs_dl.web import toolbox_store
                dl_cfg = {
                    "image_format": image_format or "jpg",
                    "title_template": title_template or DEFAULT_TITLE_TEMPLATE,
                    "set_file_time_to_publish": bool(set_file_time),
                }
                base_out = output_dir or str(Path.home() / "Downloads")
                for row in chosen:
                    try:
                        info, _ = toolbox_store._download_single_artwork_row(row, base_out, download_settings=dl_cfg)
                        if info:
                            dl_item = dict(row)
                            dl_item["downloaded"] = True
                            dl_item["completion_confirmed"] = True
                            dl_item["save_directory"] = info["save_path"]
                            dl_item["image_count"] = info["image_count"]
                            dl_item["media_file_count"] = info["image_count"]
                            download_items.append(dl_item)
                            total_media += int(info["image_count"] or 0)
                    except Exception:
                        continue

            return {
                "status": "completed" if chosen else "completed_zero",
                "success": True,
                "stage": "completed",
                "candidates": chosen,
                "discovered_links": links,
                "download": {"items": download_items, "success_count": len(download_items)} if direct_download else {},
                "media_file_count": total_media,
                "skipped_duplicate_count": skipped_dup,
                "completion_confirmed": bool(chosen),
                "message": f"主页采集完成：发现 {len(chosen)} 套图文" + (f"，已下载 {len(download_items)} 套" if direct_download else ""),
            }
        finally:
            with self._state_lock:
                self._busy = False

    def collect_xhs_keyword(
        self,
        keyword: str,
        *,
        count: int = 20,
        allow_video: bool = False,
        media_type: str = "",
        skip_ids: Optional[Iterable[str]] = None,
        proxy_url: str = "",
        on_gate_cb: Optional[Callable[[str, str], None]] = None,
        job_request: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        kw = str(keyword or "").strip()
        if not kw:
            return {"status": "error", "success": False, "message": "关键词不能为空"}
        eff_media_type = str(media_type or "").strip().lower()
        if eff_media_type not in {"image", "video", "all"}:
            eff_media_type = "all" if allow_video else "image"
        skip_set = {str(x).strip() for x in (skip_ids or []) if str(x).strip()}
        target = max(1, min(200, int(count or 20)))
        self._cancel_event.clear()
        with self._state_lock:
            self._active_platform = "xiaohongshu"
            self._busy = True
            self._verification_required = False
            self._keyword_progress = {
                "phase": "starting",
                "status": "running",
                "keyword": kw,
                "target": target,
                "total": 0,
                "qualified": 0,
                "crawled": 0,
                "downloaded": 0,
                "message": f"正在打开小红书搜索：{kw}",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(kw, safe='')}&source=web_search_result_notes"
        try:
            def _open_xhs():
                page = self._ensure_page_in_worker(proxy_url=proxy_url)
                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                deadline = time.monotonic() + 20.0
                latest: Dict[str, Any] = {}
                while time.monotonic() < deadline:
                    snap = page.evaluate(_XHS_SEARCH_SNAPSHOT_SCRIPT)
                    if isinstance(snap, dict):
                        latest = snap
                        if snap.get("verification") or snap.get("login_required") or (snap.get("cards") or []):
                            return snap
                    time.sleep(0.7)
                return latest

            snap = self._call_browser(_open_xhs, timeout=35.0)
            if isinstance(snap, dict) and (snap.get("verification") or snap.get("login_required")):
                gate_status = "verification_required" if snap.get("verification") else "login_required"
                gate_msg = "小红书提示登录或安全验证，已置顶弹出浏览器，请完成后点击「继续采集」"
                with self._state_lock:
                    self._verification_required = True
                    self._paused_job = dict(job_request or {"kind": "keyword", "platform": "xiaohongshu", "keyword": kw})
                try:
                    self._call_browser(lambda: self._bring_to_front_in_worker(topmost=True), timeout=10.0)
                except Exception:
                    pass
                if callable(on_gate_cb):
                    try:
                        on_gate_cb(gate_status, gate_msg)
                    except Exception:
                        pass
                return {"status": gate_status, "success": False, "stage": "browser", "message": gate_msg}

            items_by_id: Dict[str, Dict[str, Any]] = {}
            for _ in range(18):
                if isinstance(snap, dict):
                    for it in (snap.get("cards") or []):
                        if isinstance(it, dict) and it.get("id"):
                            it["keyword"] = kw
                            it["artwork_type"] = "视频" if it.get("is_video") else "图文"
                            items_by_id[str(it["id"])] = it
                typed_items = [
                    it for it in items_by_id.values()
                    if (
                        eff_media_type == "all"
                        or (eff_media_type == "video" and it.get("is_video"))
                        or (eff_media_type == "image" and not it.get("is_video"))
                    )
                ]
                fresh = [it for it in typed_items if str(it.get("id") or "") not in skip_set]
                self._set_progress(
                    phase="crawling",
                    crawled=len(items_by_id),
                    qualified=len(fresh),
                    message=f"小红书已抓取 {len(fresh)} 条新笔记",
                )
                if len(fresh) >= target or self._cancel_event.is_set():
                    break

                def _scroll_xhs():
                    page = self._ensure_page_in_worker(proxy_url=proxy_url)
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.1)
                    return page.evaluate(_XHS_SEARCH_SNAPSHOT_SCRIPT)

                snap = self._call_browser(_scroll_xhs, timeout=20.0)

            all_items = [
                it for it in items_by_id.values()
                if (
                    eff_media_type == "all"
                    or (eff_media_type == "video" and it.get("is_video"))
                    or (eff_media_type == "image" and not it.get("is_video"))
                )
            ]
            fresh_all = [it for it in all_items if str(it.get("id") or "") not in skip_set]
            skipped_dup = max(0, len(all_items) - len(fresh_all))
            chosen = fresh_all[:target]
            links = [str(it.get("url") or "") for it in chosen if it.get("url")]
            self._set_progress(
                phase="completed",
                status="completed" if chosen else "completed_zero",
                crawled=len(all_items),
                qualified=len(chosen),
                message=f"小红书采集完成：发现 {len(chosen)} 条笔记",
            )
            return {
                "status": "completed" if chosen else "completed_zero",
                "success": True,
                "stage": "completed",
                "candidates": chosen,
                "discovered_links": links,
                "skipped_duplicate_count": skipped_dup,
                "completion_confirmed": bool(chosen),
                "message": f"小红书发现 {len(chosen)} 条笔记",
            }
        finally:
            with self._state_lock:
                self._busy = False


_ENGINE_LOCK = threading.Lock()
_ENGINE_SINGLETON: Optional[NativeBrowserCollector] = None


def get_engine() -> NativeBrowserCollector:
    global _ENGINE_SINGLETON
    with _ENGINE_LOCK:
        if _ENGINE_SINGLETON is None:
            _ENGINE_SINGLETON = NativeBrowserCollector()
        return _ENGINE_SINGLETON
