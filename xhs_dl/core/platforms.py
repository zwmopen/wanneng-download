"""Supported share-link platform detection."""

from urllib.parse import urlparse


XHS_HOSTS = {
    "xhslink.com",
    "www.xhslink.com",
    "xhslink.cn",
    "www.xhslink.cn",
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "xiaohongshu.cn",
    "www.xiaohongshu.cn",
    "rednote.com",
    "www.rednote.com",
}
DOUYIN_HOSTS = {
    "v.douyin.com",
    "douyin.com",
    "www.douyin.com",
    "iesdouyin.com",
    "www.iesdouyin.com",
}
CN_SUBPLATFORM_HOSTS = {
    "kuaishou": {
        "kuaishou.com", "www.kuaishou.com", "v.kuaishou.com",
        "chenzhongtech.com", "kuaishouapp.com", "m.gifshow.com",
    },
    "weibo": {
        "weibo.com", "www.weibo.com", "m.weibo.cn", "video.weibo.com", "t.cn",
    },
    "toutiao": {
        "toutiao.com", "www.toutiao.com", "m.toutiao.com", "m.toutiaocdn.com",
    },
    "pipixia": {
        "pipix.com", "h5.pipix.com", "www.pipix.com",
    },
    "pipigx": {
        "pipigx.com", "h5.pipigx.com", "ippzone.com", "h5.ippzone.com",
    },
    "zuiyou": {
        "izuiyou.com", "share.izuiyou.com", "www.izuiyou.com", "xiaochuankeji.cn",
    },
    "doubao": {
        "doubao.com", "www.doubao.com",
    },
    "jimeng": {
        "jimeng.jianying.com", "v.jimeng.aiseet.atry.com",
    },
}
CN_SHORT_VIDEO_HOSTS = {
    host for hosts in CN_SUBPLATFORM_HOSTS.values() for host in hosts
}
GENERIC_HOSTS = {
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "bilibili.com", "www.bilibili.com", "b23.tv",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "fb.watch",
    "pinterest.com", "www.pinterest.com", "pin.it",
    "reddit.com", "www.reddit.com", "old.reddit.com", "redd.it",
    "vimeo.com", "www.vimeo.com",
    "bsky.app", "www.bsky.app",
}


def detect_cn_subplatform(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for subplatform, hosts in CN_SUBPLATFORM_HOSTS.items():
        if host in hosts or any(host.endswith("." + h) for h in hosts):
            return subplatform
    return ""


def detect_platform(url):
    host = (urlparse(url).hostname or "").lower()
    if host in DOUYIN_HOSTS:
        return "douyin"
    if host in XHS_HOSTS:
        return "xhs"
    if host in CN_SHORT_VIDEO_HOSTS or detect_cn_subplatform(url):
        return "cn_video"
    if host in GENERIC_HOSTS:
        return "generic"
    return "unknown"


def group_urls(urls):
    grouped = {"douyin": [], "xhs": [], "generic": [], "unknown": []}
    for url in urls:
        key = detect_platform(url)
        grouped.setdefault(key, []).append(url)
    return grouped
