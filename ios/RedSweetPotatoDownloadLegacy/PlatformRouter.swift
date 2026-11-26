import Foundation

enum SupportedPlatform {
    case xiaohongshu
    case douyin
    case cnVideo(String)
}

enum PlatformRouter {
    private static let cnSubplatforms: [(String, [String])] = [
        ("kuaishou", ["kuaishou.com", "v.kuaishou.com", "www.kuaishou.com", "chenzhongtech.com", "kuaishouapp.com", "m.gifshow.com"]),
        ("weibo", ["weibo.com", "www.weibo.com", "m.weibo.cn", "video.weibo.com", "t.cn"]),
        ("toutiao", ["toutiao.com", "www.toutiao.com", "m.toutiao.com", "m.toutiaocdn.com"]),
        ("pipixia", ["pipix.com", "h5.pipix.com", "www.pipix.com"]),
        ("pipigx", ["pipigx.com", "h5.pipigx.com", "ippzone.com", "h5.ippzone.com"]),
        ("zuiyou", ["izuiyou.com", "share.izuiyou.com", "www.izuiyou.com", "xiaochuankeji.cn"]),
        ("doubao", ["doubao.com", "www.doubao.com"]),
        ("jimeng", ["jimeng.jianying.com", "v.jimeng.aiseet.atry.com"]),
    ]

    static func platform(for url: URL) -> SupportedPlatform? {
        let host = url.host?.lowercased() ?? ""
        if host == "douyin.com" || host.hasSuffix(".douyin.com")
            || host == "iesdouyin.com" || host.hasSuffix(".iesdouyin.com") {
            return .douyin
        }
        if host == "xiaohongshu.com" || host.hasSuffix(".xiaohongshu.com")
            || host == "xiaohongshu.cn" || host.hasSuffix(".xiaohongshu.cn")
            || host == "xhslink.com" || host.hasSuffix(".xhslink.com")
            || host == "xhslink.cn" || host.hasSuffix(".xhslink.cn")
            || host == "rednote.com" || host.hasSuffix(".rednote.com") {
            return .xiaohongshu
        }
        for (sub, hosts) in cnSubplatforms {
            if hosts.contains(where: { host == $0 || host.hasSuffix("." + $0) }) {
                return .cnVideo(sub)
            }
        }
        return nil
    }
}
