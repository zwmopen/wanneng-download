package com.zwmopen.xhsdl;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public final class PlatformRouterTest {
    @Test
    public void detectsXhsAndDouyinShareLinks() {
        assertEquals("douyin", PlatformRouter.detect("https://v.douyin.com/VFppn9c-lds/"));
        assertEquals("douyin", PlatformRouter.detect("https://www.douyin.com/note/7663398572494336177"));
        assertEquals("xhs", PlatformRouter.detect("https://xhslink.com/o/70dt8TsFJon"));
        assertEquals("xhs", PlatformRouter.detect("http://xhslink.cn/o/97Pz4siAYx4"));
        assertEquals("unknown", PlatformRouter.detect("https://example.com/file"));
    }

    @Test
    public void detectsCnShortVideoAndAiPlatforms() {
        assertEquals("cn_video", PlatformRouter.detect("https://v.kuaishou.com/abc123"));
        assertEquals("kuaishou", PlatformRouter.detectCnSubplatform("https://v.kuaishou.com/abc123"));
        assertEquals("cn_video", PlatformRouter.detect("https://weibo.com/tv/show/1034:123"));
        assertEquals("weibo", PlatformRouter.detectCnSubplatform("https://weibo.com/tv/show/1034:123"));
        assertEquals("cn_video", PlatformRouter.detect("https://www.toutiao.com/video/7123456789012345678/"));
        assertEquals("toutiao", PlatformRouter.detectCnSubplatform("https://www.toutiao.com/video/7123456789012345678/"));
        assertEquals("cn_video", PlatformRouter.detect("https://h5.pipix.com/s/abcdef/"));
        assertEquals("pipixia", PlatformRouter.detectCnSubplatform("https://h5.pipix.com/s/abcdef/"));
        assertEquals("cn_video", PlatformRouter.detect("https://h5.pipigx.com/pp/post/123?pid=1&mid=2"));
        assertEquals("pipigx", PlatformRouter.detectCnSubplatform("https://h5.pipigx.com/pp/post/123?pid=1&mid=2"));
        assertEquals("cn_video", PlatformRouter.detect("https://share.izuiyou.com/hybrid/share/post?pid=999"));
        assertEquals("zuiyou", PlatformRouter.detectCnSubplatform("https://share.izuiyou.com/hybrid/share/post?pid=999"));
        assertEquals("cn_video", PlatformRouter.detect("https://www.doubao.com/video-sharing?share_id=a&video_id=b"));
        assertEquals("doubao", PlatformRouter.detectCnSubplatform("https://www.doubao.com/video-sharing?share_id=a&video_id=b"));
        assertEquals("cn_video", PlatformRouter.detect("https://jimeng.jianying.com/ai-tool/video/7123456789012345678"));
        assertEquals("jimeng", PlatformRouter.detectCnSubplatform("https://jimeng.jianying.com/ai-tool/video/7123456789012345678"));
    }
}
