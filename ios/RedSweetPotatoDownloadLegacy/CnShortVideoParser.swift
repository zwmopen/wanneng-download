import Foundation

final class CnShortVideoParser {
    private static let desktopUA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    private static let mobileUA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"

    func fetch(_ sourceURL: URL, subplatform: String, completion: @escaping (NoteData?, Error?) -> Void) {
        switch subplatform {
        case "kuaishou": parseKuaishou(sourceURL, completion: completion)
        case "weibo": parseWeibo(sourceURL, completion: completion)
        case "toutiao": parseToutiao(sourceURL, completion: completion)
        case "pipixia": parsePipixia(sourceURL, completion: completion)
        case "pipigx": parsePipigx(sourceURL, completion: completion)
        case "zuiyou": parseZuiyou(sourceURL, completion: completion)
        case "doubao": parseDoubao(sourceURL, completion: completion)
        case "jimeng": parseJimeng(sourceURL, completion: completion)
        default: completion(nil, AppFailure.invalidURL)
        }
    }

    // MARK: - 1. 快手
    private func parseKuaishou(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        getText(sourceURL, ua: Self.mobileUA, referer: "https://www.kuaishou.com/") { text, _, err in
            if let err = err { completion(nil, err); return }
            guard let html = text else { completion(nil, AppFailure.noteMissing); return }
            var rawJson = self.firstMatch(#"window\.INIT_STATE\s*=\s*(.*?)</script>"#, in: html, dotAll: true)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            while rawJson.hasSuffix(";") { rawJson.removeLast() }
            rawJson = rawJson
                .replacingOccurrences(of: "\"{\"err_msg\":\"launchApplication:fail\"}\"", with: "\"launchApplication:fail\"")
                .replacingOccurrences(of: "\"{\"err_msg\":\"system:access_denied\"}\"", with: "\"system:access_denied\"")
            guard let data = rawJson.data(using: .utf8),
                  let state = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] else {
                completion(nil, AppFailure.pageChanged); return
            }
            var photo: [String: Any]?
            for (_, v) in state {
                if let dict = v as? [String: Any], let p = dict["photo"] as? [String: Any] {
                    photo = p; break
                }
            }
            guard let p = photo else { completion(nil, AppFailure.noteMissing); return }
            let title = self.str(p["caption"], fallback: "快手作品")
            let author = self.str(p["userName"], fallback: "快手作者")
            let id = self.str(p["photoId"], fallback: self.str(p["id"]))
            let likes = self.str(p["likeCount"], fallback: "未知")
            var media: [MediaItem] = []

            let extParams = p["ext_params"] as? [String: Any]
            let atlas = extParams?["atlas"] as? [String: Any]
            if let atlasList = atlas?["list"] as? [String], !atlasList.isEmpty {
                for item in atlasList {
                    let trimmed = item.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                    let full = trimmed.hasPrefix("http") ? trimmed : "https://tx2.a.yximgs.com/\(trimmed)"
                    if let u = URL(string: full) { media.append(MediaItem(url: u, fileExtension: self.guessImgExt(full))) }
                }
            } else if self.str(p["photoType"]) == "SINGLE_PICTURE" || (p["singlePicture"] as? Bool) == true {
                if let first = (p["coverUrls"] as? [[String: Any]])?.first,
                   let u = URL(string: self.toHttps(self.str(first["url"]))) {
                    media.append(MediaItem(url: u, fileExtension: self.guessImgExt(u.absoluteString)))
                }
            } else {
                var vStr = self.toHttps(self.str((p["mainMvUrls"] as? [[String: Any]])?.first?["url"]))
                if vStr.isEmpty,
                   let manifest = p["manifest"] as? [String: Any],
                   let sets = manifest["adaptationSet"] as? [[String: Any]],
                   let reps = sets.first?["representation"] as? [[String: Any]],
                   let raw = reps.first?["url"] as? String {
                    vStr = self.toHttps(raw)
                }
                if let u = URL(string: vStr), !vStr.isEmpty { media.append(MediaItem(url: u, fileExtension: "mp4")) }
            }
            guard !media.isEmpty else { completion(nil, AppFailure.mediaMissing); return }
            completion(NoteData(sourceURL: sourceURL, noteID: id, title: title, body: title, author: author, comments: "未知", likes: likes, topics: [], media: media, customReferer: "https://www.kuaishou.com/"), nil)
        }
    }

    // MARK: - 2. 微博
    private func parseWeibo(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        let resolveAndFetch: (URL) -> Void = { targetURL in
            var fid = self.queryParam("fid", in: targetURL)
            if fid.isEmpty {
                fid = self.firstMatch(#"weibo\.com/tv/(?:show|v)/([^?&#/]+)"#, in: targetURL.absoluteString)
            }
            guard !fid.isEmpty else { completion(nil, AppFailure.invalidURL); return }
            let pagePath = "/tv/show/\(fid)"
            let encPage = pagePath.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? pagePath
            guard let apiURL = URL(string: "https://weibo.com/tv/api/component?page=\(encPage)"),
                  let payloadData = try? JSONSerialization.data(withJSONObject: ["Component_Play_Playinfo": ["oid": fid]]),
                  let payloadStr = String(data: payloadData, encoding: .utf8),
                  let encPayload = payloadStr.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
                completion(nil, AppFailure.invalidURL); return
            }
            let bodyData = "data=\(encPayload)".data(using: .utf8) ?? Data()
            self.postRaw(apiURL, body: bodyData, contentType: "application/x-www-form-urlencoded", referer: "https://weibo.com\(pagePath)") { data, err in
                if let err = err { completion(nil, err); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let d = root["data"] as? [String: Any],
                      let info = d["Component_Play_Playinfo"] as? [String: Any],
                      let urls = info["urls"] as? [String: String], !urls.isEmpty else {
                    completion(nil, AppFailure.noteMissing); return
                }
                let ranked = urls.sorted { self.qualityRank($0.key) > self.qualityRank($1.key) }
                guard let bestRaw = ranked.first?.value,
                      let videoURL = URL(string: self.toHttps(bestRaw)), !bestRaw.isEmpty else {
                    completion(nil, AppFailure.mediaMissing); return
                }
                let title = self.str(info["title"], fallback: self.str(info["text"], fallback: "微博视频"))
                let author = self.str(info["author"], fallback: self.str(info["nickname"], fallback: "微博作者"))
                completion(NoteData(sourceURL: sourceURL, noteID: fid, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: [MediaItem(url: videoURL, fileExtension: "mp4")], customReferer: "https://weibo.com/"), nil)
            }
        }
        if sourceURL.absoluteString.contains("t.cn/") {
            getText(sourceURL, ua: Self.desktopUA, referer: "https://weibo.com/") { _, finalURL, _ in
                resolveAndFetch(finalURL ?? sourceURL)
            }
        } else {
            resolveAndFetch(sourceURL)
        }
    }

    // MARK: - 3. 今日头条
    private func parseToutiao(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        getText(sourceURL, ua: Self.desktopUA, referer: "https://www.toutiao.com/") { _, finalURL, err in
            if let err = err { completion(nil, err); return }
            let target = (finalURL ?? sourceURL).absoluteString
            var vid = self.firstMatch(#"(?:video/|group/|item/)(\d+)"#, in: target)
            if vid.isEmpty { vid = self.firstMatch(#"(\d{10,})"#, in: target) }
            guard !vid.isEmpty, let pageURL = URL(string: "https://www.toutiao.com/video/\(vid)") else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.getText(pageURL, ua: Self.desktopUA, referer: "https://www.toutiao.com/") { html, _, err2 in
                if let err2 = err2 { completion(nil, err2); return }
                guard let html = html else { completion(nil, AppFailure.noteMissing); return }
                let encoded = self.firstMatch(#"<script id="RENDER_DATA" type="application/json">(.*?)</script>"#, in: html, dotAll: true)
                let decoded = encoded.removingPercentEncoding ?? encoded
                guard let data = decoded.data(using: .utf8),
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let d = root["data"] as? [String: Any],
                      let initVideo = d["initialVideo"] as? [String: Any],
                      let playInfo = initVideo["videoPlayInfo"] as? [String: Any],
                      let list = playInfo["video_list"] as? [[String: Any]],
                      let best = list.reversed().first(where: { !self.str($0["main_url"]).isEmpty }),
                      let videoURL = URL(string: self.toHttps(self.str(best["main_url"]))) else {
                    completion(nil, AppFailure.mediaMissing); return
                }
                let userInfo = (initVideo["itemCell"] as? [String: Any])?["userInfo"] as? [String: Any]
                let title = self.str(initVideo["title"], fallback: "今日头条视频")
                let author = self.str(userInfo?["name"], fallback: "头条作者")
                completion(NoteData(sourceURL: sourceURL, noteID: vid, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: [MediaItem(url: videoURL, fileExtension: "mp4")], customReferer: "https://www.toutiao.com/"), nil)
            }
        }
    }

    // MARK: - 4. 皮皮虾
    private func parsePipixia(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        getText(sourceURL, ua: Self.desktopUA, referer: "https://h5.pipix.com/") { _, finalURL, err in
            if let err = err { completion(nil, err); return }
            let target = (finalURL ?? sourceURL).absoluteString
            let cellID = self.firstMatch(#"item/(\d+)"#, in: target)
            guard !cellID.isEmpty,
                  let apiURL = URL(string: "https://h5.pipix.com/bds/cell/cell_h5_comment/?count=5&aid=1319&app_name=super&cell_id=\(cellID)") else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.getData(apiURL, ua: Self.desktopUA, referer: "https://h5.pipix.com/") { data, err2 in
                if let err2 = err2 { completion(nil, err2); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let comments = (root["data"] as? [String: Any])?["cell_comments"] as? [[String: Any]],
                      let item = comments.compactMap({ ($0["comment_info"] as? [String: Any])?["item"] as? [String: Any] }).first else {
                    completion(nil, AppFailure.noteMissing); return
                }
                var media: [MediaItem] = []
                if let v = (item["video"] as? [String: Any])?["video_high"] as? [String: Any],
                   let ul = v["url_list"] as? [[String: Any]],
                   let u = URL(string: self.toHttps(self.str(ul.first?["url"]))) {
                    media.append(MediaItem(url: u, fileExtension: "mp4"))
                }
                if let multi = (item["note"] as? [String: Any])?["multi_image"] as? [[String: Any]] {
                    for img in multi {
                        if let ul = img["url_list"] as? [[String: Any]],
                           let u = URL(string: self.toHttps(self.str(ul.first?["url"]))) {
                            media.append(MediaItem(url: u, fileExtension: self.guessImgExt(u.absoluteString)))
                        }
                    }
                }
                guard !media.isEmpty else { completion(nil, AppFailure.mediaMissing); return }
                let title = self.str(item["content"], fallback: "皮皮虾作品")
                let author = self.str((item["author"] as? [String: Any])?["name"], fallback: "皮皮虾作者")
                completion(NoteData(sourceURL: sourceURL, noteID: cellID, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: media, customReferer: "https://h5.pipix.com/"), nil)
            }
        }
    }

    // MARK: - 5. 皮皮搞笑
    private func parsePipigx(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        getText(sourceURL, ua: Self.desktopUA, referer: "https://h5.pipigx.com/") { _, finalURL, err in
            if let err = err { completion(nil, err); return }
            let target = finalURL ?? sourceURL
            let pidStr = self.queryParam("pid", in: target)
            let midStr = self.queryParam("mid", in: target)
            guard let pid = Int64(pidStr), let mid = Int64(midStr),
                  let apiURL = URL(string: "https://h5.pipigx.com/ppapi/share/fetch_content"),
                  let body = try? JSONSerialization.data(withJSONObject: ["pid": pid, "mid": mid, "type": "post"]) else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.postRaw(apiURL, body: body, contentType: "application/json", referer: "https://h5.pipigx.com/") { data, err2 in
                if let err2 = err2 { completion(nil, err2); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let post = (root["data"] as? [String: Any])?["post"] as? [String: Any],
                      let vStr = self.extractVideoURL(from: post["videos"]),
                      let videoURL = URL(string: vStr) else {
                completion(nil, AppFailure.mediaMissing); return
                }
                let title = self.str(post["content"], fallback: "皮皮搞笑作品")
                let author = self.str((post["user"] as? [String: Any])?["name"], fallback: "皮皮搞笑作者")
                completion(NoteData(sourceURL: sourceURL, noteID: pidStr, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: [MediaItem(url: videoURL, fileExtension: "mp4")], customReferer: "https://h5.pipigx.com/"), nil)
            }
        }
    }

    // MARK: - 6. 最右
    private func parseZuiyou(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        let proceed: (String) -> Void = { pidStr in
            guard let pid = Int64(pidStr),
                  let apiURL = URL(string: "https://share.izuiyou.com/api/post/detail"),
                  let body = try? JSONSerialization.data(withJSONObject: ["pid": pid]) else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.postRaw(apiURL, body: body, contentType: "application/json", referer: "https://share.izuiyou.com/") { data, err in
                if let err = err { completion(nil, err); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let post = (root["data"] as? [String: Any])?["post"] as? [String: Any] else {
                    completion(nil, AppFailure.noteMissing); return
                }
                var media: [MediaItem] = []
                if let vStr = self.extractVideoURL(from: post["videos"]), let u = URL(string: vStr) {
                    media.append(MediaItem(url: u, fileExtension: "mp4"))
                } else if let imgs = post["imgs"] as? [[String: Any]] {
                    for img in imgs {
                        let urls = img["urls"] as? [String: Any]
                        let bucket = (urls?["origin"] as? [String: Any]) ?? (urls?["540"] as? [String: Any])
                        if let first = (bucket?["urls"] as? [String])?.first, let u = URL(string: self.toHttps(first)) {
                            media.append(MediaItem(url: u, fileExtension: self.guessImgExt(u.absoluteString)))
                        }
                    }
                }
                guard !media.isEmpty else { completion(nil, AppFailure.mediaMissing); return }
                let title = self.str(post["content"], fallback: "最右作品")
                let author = self.str((post["member"] as? [String: Any])?["name"], fallback: "最右作者")
                let likes = self.str(post["likes"], fallback: "未知")
                completion(NoteData(sourceURL: sourceURL, noteID: pidStr, title: title, body: title, author: author, comments: "未知", likes: likes, topics: [], media: media, customReferer: "https://share.izuiyou.com/"), nil)
            }
        }
        let pidDirect = queryParam("pid", in: sourceURL)
        if !pidDirect.isEmpty {
            proceed(pidDirect)
        } else {
            getText(sourceURL, ua: Self.desktopUA, referer: "https://share.izuiyou.com/") { _, finalURL, _ in
                proceed(self.queryParam("pid", in: finalURL ?? sourceURL))
            }
        }
    }

    // MARK: - 7. 豆包 AI
    private func parseDoubao(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        getText(sourceURL, ua: Self.desktopUA, referer: "https://www.doubao.com/") { _, finalURL, err in
            if let err = err { completion(nil, err); return }
            let target = finalURL ?? sourceURL
            let shareID = self.queryParam("share_id", in: target)
            let videoID = self.queryParam("video_id", in: target)
            guard !shareID.isEmpty, !videoID.isEmpty,
                  let apiURL = URL(string: "https://www.doubao.com/creativity/share/get_video_share_info?version_code=20800&language=zh-CN&device_platform=web&aid=497858&real_aid=497858&pkg_type=release_version&pc_version=3.8.3&samantha_web=1"),
                  let body = try? JSONSerialization.data(withJSONObject: ["share_id": shareID, "vid": videoID, "creation_id": ""]) else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.postRaw(apiURL, body: body, contentType: "application/json", referer: target.absoluteString) { data, err2 in
                if let err2 = err2 { completion(nil, err2); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      (root["code"] as? Int) == 0,
                      let d = root["data"] as? [String: Any] else {
                    completion(nil, AppFailure.noteMissing); return
                }
                var vStr = ""
                for key in ["play_url", "video_url", "url", "download_url"] {
                    let cand = self.str(d[key])
                    if cand.hasPrefix("http") { vStr = self.toHttps(cand); break }
                }
                if vStr.isEmpty, let pi = d["play_info"] as? [String: Any] {
                    vStr = self.toHttps(self.str(pi["main"], fallback: self.str(pi["url"])))
                }
                guard let videoURL = URL(string: vStr), !vStr.isEmpty else {
                    completion(nil, AppFailure.mediaMissing); return
                }
                let title = self.str(d["prompt"], fallback: self.str(d["title"], fallback: "豆包AI视频"))
                let author = self.str(d["author_name"], fallback: "豆包AI")
                completion(NoteData(sourceURL: sourceURL, noteID: videoID, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: [MediaItem(url: videoURL, fileExtension: "mp4")], customReferer: "https://www.doubao.com/"), nil)
            }
        }
    }

    // MARK: - 8. 即梦 AI
    private func parseJimeng(_ sourceURL: URL, completion: @escaping (NoteData?, Error?) -> Void) {
        let proceed: (URL) -> Void = { target in
            var itemID = ""
            for k in ["id", "item_id", "published_item_id", "work_id"] {
                itemID = self.queryParam(k, in: target)
                if !itemID.isEmpty { break }
            }
            if itemID.isEmpty { itemID = self.firstMatch(#"(\d{16,})"#, in: target.absoluteString) }
            guard !itemID.isEmpty,
                  let apiURL = URL(string: "https://jimeng.jianying.com/mweb/v1/get_item_info"),
                  let body = try? JSONSerialization.data(withJSONObject: ["published_item_id": itemID]) else {
                completion(nil, AppFailure.invalidURL); return
            }
            self.postRaw(apiURL, body: body, contentType: "application/json", referer: "https://jimeng.jianying.com/") { data, err in
                if let err = err { completion(nil, err); return }
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      self.str(root["ret"], fallback: "0") == "0",
                      let d = root["data"] as? [String: Any] else {
                    completion(nil, AppFailure.noteMissing); return
                }
                let common = d["common_attr"] as? [String: Any]
                let authorObj = d["author"] as? [String: Any]
                let video = d["video"] as? [String: Any]
                let transcoded = video?["transcoded_video"] as? [String: Any]
                let originVideo = video?["origin_video"] as? [String: Any]
                var vStr = self.toHttps(self.str((transcoded?["origin"] as? [String: Any])?["video_url"]))
                if vStr.isEmpty { vStr = self.toHttps(self.str(originVideo?["video_url"])) }
                if vStr.isEmpty, let transcoded = transcoded {
                    for (_, entry) in transcoded {
                        if let dict = entry as? [String: Any], !self.str(dict["video_url"]).isEmpty {
                            vStr = self.toHttps(self.str(dict["video_url"])); break
                        }
                    }
                }
                guard let videoURL = URL(string: vStr), !vStr.isEmpty else {
                    completion(nil, AppFailure.mediaMissing); return
                }
                let title = self.str(common?["description"], fallback: "即梦AI视频")
                let author = self.str(authorObj?["name"], fallback: "即梦AI")
                completion(NoteData(sourceURL: sourceURL, noteID: itemID, title: title, body: title, author: author, comments: "未知", likes: "未知", topics: [], media: [MediaItem(url: videoURL, fileExtension: "mp4")], customReferer: "https://jimeng.jianying.com/"), nil)
            }
        }
        if sourceURL.absoluteString.contains("/s/") {
            getText(sourceURL, ua: Self.desktopUA, referer: "https://jimeng.jianying.com/") { _, finalURL, _ in
                proceed(finalURL ?? sourceURL)
            }
        } else {
            proceed(sourceURL)
        }
    }

    // MARK: - Networking & Utilities (iOS 12+ URLSession)

    private func getText(_ url: URL, ua: String, referer: String, completion: @escaping (String?, URL?, Error?) -> Void) {
        var req = URLRequest(url: url, timeoutInterval: 20)
        req.setValue(ua, forHTTPHeaderField: "User-Agent")
        req.setValue(referer, forHTTPHeaderField: "Referer")
        URLSession.shared.dataTask(with: req) { data, response, error in
            if let error = error { completion(nil, response?.url, error); return }
            let text = data.flatMap { String(data: $0, encoding: .utf8) }
            completion(text, response?.url, nil)
        }.resume()
    }

    private func getData(_ url: URL, ua: String, referer: String, completion: @escaping (Data?, Error?) -> Void) {
        var req = URLRequest(url: url, timeoutInterval: 20)
        req.setValue(ua, forHTTPHeaderField: "User-Agent")
        req.setValue(referer, forHTTPHeaderField: "Referer")
        URLSession.shared.dataTask(with: req) { data, _, error in
            completion(data, error)
        }.resume()
    }

    private func postRaw(_ url: URL, body: Data, contentType: String, referer: String, completion: @escaping (Data?, Error?) -> Void) {
        var req = URLRequest(url: url, timeoutInterval: 20)
        req.httpMethod = "POST"
        req.httpBody = body
        req.setValue(Self.desktopUA, forHTTPHeaderField: "User-Agent")
        req.setValue(referer, forHTTPHeaderField: "Referer")
        req.setValue(contentType, forHTTPHeaderField: "Content-Type")
        URLSession.shared.dataTask(with: req) { data, _, error in
            completion(data, error)
        }.resume()
    }

    private func extractVideoURL(from field: Any?) -> String? {
        if let dict = field as? [String: Any] {
            for (_, v) in dict {
                if let entry = v as? [String: Any], !str(entry["url"]).isEmpty { return toHttps(str(entry["url"])) }
            }
        } else if let arr = field as? [[String: Any]] {
            for entry in arr {
                if !str(entry["url"]).isEmpty { return toHttps(str(entry["url"])) }
            }
        }
        return nil
    }

    private func qualityRank(_ label: String) -> Int {
        let u = label.uppercased()
        if u.contains("4K") { return 6 }
        if u.contains("2K") { return 5 }
        if u.contains("1080P") { return 4 }
        if u.contains("720P") { return 3 }
        if u.contains("480P") { return 2 }
        if u.contains("360P") { return 1 }
        return 0
    }

    private func queryParam(_ key: String, in url: URL) -> String {
        guard let items = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems else { return "" }
        return items.first(where: { $0.name == key })?.value ?? ""
    }

    private func firstMatch(_ pattern: String, in text: String, dotAll: Bool = false) -> String {
        let opts: NSRegularExpression.Options = dotAll ? [.dotMatchesLineSeparators] : []
        guard let exp = try? NSRegularExpression(pattern: pattern, options: opts),
              let match = exp.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let r = Range(match.range(at: 1), in: text) else { return "" }
        return String(text[r])
    }

    private func str(_ value: Any?, fallback: String = "") -> String {
        guard let value = value, !(value is NSNull) else { return fallback }
        let out = value as? String ?? String(describing: value)
        return out.isEmpty ? fallback : out
    }

    private func toHttps(_ raw: String) -> String {
        let t = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.hasPrefix("//") { return "https:" + t }
        if t.hasPrefix("http://") { return "https://" + t.dropFirst(7) }
        return t
    }

    private func guessImgExt(_ url: String) -> String {
        let l = url.lowercased()
        if l.contains(".png") { return "png" }
        if l.contains(".webp") { return "webp" }
        return "jpg"
    }
}
