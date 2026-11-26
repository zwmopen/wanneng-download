package com.zwmopen.xhsdl;

import java.net.URI;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PlatformRouter {
    private static final Map<String, List<String>> CN_SUBPLATFORMS;

    static {
        Map<String, List<String>> map = new LinkedHashMap<>();
        map.put("kuaishou", Arrays.asList(
                "kuaishou.com", "v.kuaishou.com", "www.kuaishou.com",
                "chenzhongtech.com", "kuaishouapp.com", "m.gifshow.com"
        ));
        map.put("weibo", Arrays.asList(
                "weibo.com", "www.weibo.com", "m.weibo.cn", "video.weibo.com", "t.cn"
        ));
        map.put("toutiao", Arrays.asList(
                "toutiao.com", "www.toutiao.com", "m.toutiao.com", "m.toutiaocdn.com"
        ));
        map.put("pipixia", Arrays.asList(
                "pipix.com", "h5.pipix.com", "www.pipix.com"
        ));
        map.put("pipigx", Arrays.asList(
                "pipigx.com", "h5.pipigx.com", "ippzone.com", "h5.ippzone.com"
        ));
        map.put("zuiyou", Arrays.asList(
                "izuiyou.com", "share.izuiyou.com", "www.izuiyou.com", "xiaochuankeji.cn"
        ));
        map.put("doubao", Arrays.asList(
                "doubao.com", "www.doubao.com"
        ));
        map.put("jimeng", Arrays.asList(
                "jimeng.jianying.com", "v.jimeng.aiseet.atry.com"
        ));
        CN_SUBPLATFORMS = Collections.unmodifiableMap(map);
    }

    private PlatformRouter() {}

    public static String detectCnSubplatform(String value) {
        String host = extractHost(value);
        if (host.isEmpty()) return "";
        for (Map.Entry<String, List<String>> entry : CN_SUBPLATFORMS.entrySet()) {
            for (String candidate : entry.getValue()) {
                if (host.equals(candidate) || host.endsWith("." + candidate)) {
                    return entry.getKey();
                }
            }
        }
        return "";
    }

    public static String detect(String value) {
        String host = extractHost(value);
        if (host.isEmpty()) return "unknown";
        if (host.equals("v.douyin.com") || host.equals("douyin.com")
                || host.equals("www.douyin.com") || host.equals("iesdouyin.com")
                || host.equals("www.iesdouyin.com")) return "douyin";
        if (host.equals("xhslink.com") || host.equals("www.xhslink.com")
                || host.equals("xhslink.cn") || host.equals("www.xhslink.cn")
                || host.equals("xiaohongshu.com") || host.equals("www.xiaohongshu.com")
                || host.equals("xiaohongshu.cn") || host.equals("www.xiaohongshu.cn")
                || host.equals("rednote.com") || host.equals("www.rednote.com")) return "xhs";
        if (!detectCnSubplatform(value).isEmpty()) return "cn_video";
        return "unknown";
    }

    private static String extractHost(String value) {
        if (value == null) return "";
        try {
            String host = URI.create(value.trim()).getHost();
            return host == null ? "" : host.toLowerCase();
        } catch (Exception ignored) {
            return "";
        }
    }
}
