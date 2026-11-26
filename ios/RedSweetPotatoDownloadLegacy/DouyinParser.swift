import Foundation
import WebKit

final class DouyinParser: NSObject, WKNavigationDelegate {
    private static let desktopUserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    private static let mobileUserAgent = "Mozilla/5.0 (Linux; Android 13; 2210132C Build/TKQ1.220829.002) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36"

    private weak var hostView: UIView?
    private var webView: WKWebView?
    private var sourceURL: URL?
    private var completion: ((NoteData?, Error?) -> Void)?
    private var attempt = 0
    private var finished = false

    func fetch(_ sourceURL: URL, in hostView: UIView, completion: @escaping (NoteData?, Error?) -> Void) {
        self.sourceURL = sourceURL
        self.hostView = hostView
        self.completion = completion

        // Layer 1: Direct fast detail API + 302 original play endpoint
        fetchViaFastAPI(sourceURL) { [weak self] note in
            guard let self = self else { return }
            if let note = note, !note.media.isEmpty {
                DispatchQueue.main.async { self.finish(note: note, error: nil) }
                return
            }
            // Layer 2: Optional Cloudflare Worker fallback
            let workerURL = (UserDefaults.standard.string(forKey: "cfDouyinWorkerURL") ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
            if !workerURL.isEmpty {
                self.fetchViaCloudWorker(sourceURL, workerURL: workerURL) { cloudNote in
                    if let cloudNote = cloudNote, !cloudNote.media.isEmpty {
                        DispatchQueue.main.async { self.finish(note: cloudNote, error: nil) }
                    } else {
                        DispatchQueue.main.async { self.startWebViewFallback(sourceURL) }
                    }
                }
            } else {
                DispatchQueue.main.async { self.startWebViewFallback(sourceURL) }
            }
        }
    }

    private func startWebViewFallback(_ sourceURL: URL) {
        guard !finished, let hostView = hostView else { return }
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let view = WKWebView(frame: CGRect(x: 0, y: 0, width: 2, height: 2), configuration: configuration)
        view.alpha = 0.01
        view.customUserAgent = Self.desktopUserAgent
        view.navigationDelegate = self
        hostView.addSubview(view)
        webView = view
        view.load(URLRequest(url: sourceURL, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 45))
    }

    // MARK: - Layer 1: Direct Fast Detail API

    private func fetchViaFastAPI(_ sourceURL: URL, done: @escaping (NoteData?) -> Void) {
        resolveAwemeID(sourceURL) { [weak self] awemeID in
            guard let self = self, !awemeID.isEmpty,
                  let detailURL = URL(string: "https://api.amemv.com/aweme/v1/aweme/detail/?aweme_id=\(awemeID)&aid=6383&device_platform=web&version_code=190500&version_name=19.5.0") else {
                done(nil)
                return
            }
            var request = URLRequest(url: detailURL, timeoutInterval: 15)
            request.setValue(Self.mobileUserAgent, forHTTPHeaderField: "User-Agent")
            request.setValue("application/json, text/plain, */*", forHTTPHeaderField: "Accept")
            URLSession.shared.dataTask(with: request) { data, _, _ in
                guard let data = data,
                      let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                      let statusCode = root["status_code"] as? Int, statusCode == 0,
                      let detail = root["aweme_detail"] as? [String: Any],
                      self.string(detail["aweme_id"]) == awemeID else {
                    done(nil)
                    return
                }
                self.buildNoteFromDetail(sourceURL: sourceURL, awemeID: awemeID, detail: detail, done: done)
            }.resume()
        }
    }

    private func buildNoteFromDetail(sourceURL: URL, awemeID: String, detail: [String: Any], done: @escaping (NoteData?) -> Void) {
        let title = string(detail["desc"]).trimmingCharacters(in: .whitespacesAndNewlines)
        let authorName = string((detail["author"] as? [String: Any])?["nickname"]).trimmingCharacters(in: .whitespacesAndNewlines)
        let stats = detail["statistics"] as? [String: Any] ?? [:]
        let likes = string(stats["digg_count"], fallback: "未知")
        let comments = string(stats["comment_count"], fallback: "未知")

        let images = (detail["images"] as? [[String: Any]]) ?? (detail["image_list"] as? [[String: Any]]) ?? []
        if !images.isEmpty {
            var media: [MediaItem] = []
            for img in images {
                let list = (img["urlList"] as? [String]) ?? (img["url_list"] as? [String]) ?? []
                if let first = list.first(where: { !$0.isEmpty }),
                   let imgURL = URL(string: toHttps(first)) {
                    media.append(MediaItem(url: imgURL, fileExtension: guessImageExt(imgURL.absoluteString)))
                }
                if let videoInfo = img["video"] as? [String: Any] {
                    let pa = videoInfo["play_addr"] as? [String: Any]
                    let list = (pa?["url_list"] as? [String]) ?? []
                    if let liveRaw = list.first(where: { !$0.isEmpty }) {
                        let clean = ensureVideoMimeType(toHttps(liveRaw.replacingOccurrences(of: "playwm", with: "play")))
                        if let liveURL = URL(string: clean) {
                            media.append(MediaItem(url: liveURL, fileExtension: "mp4"))
                        }
                    }
                }
            }
            guard !media.isEmpty else { done(nil); return }
            done(NoteData(
                sourceURL: sourceURL,
                noteID: awemeID,
                title: title,
                body: title,
                author: authorName,
                comments: comments,
                likes: likes,
                topics: topicNames(in: title),
                media: media,
                customReferer: "https://www.douyin.com/"
            ))
            return
        }

        let video = detail["video"] as? [String: Any] ?? [:]
        let pa = video["play_addr"] as? [String: Any]
        let vid = string(pa?["uri"]).isEmpty ? string(video["uri"]) : string(pa?["uri"])
        let fallbackRaw = pickBestBitRateURL(video) ?? ((pa?["url_list"] as? [String])?.first ?? "")
        let finishVideo: (String) -> Void = { resolvedRaw in
            let finalStr = self.ensureVideoMimeType(self.toHttps(resolvedRaw.replacingOccurrences(of: "playwm", with: "play")))
            guard let videoURL = URL(string: finalStr), !finalStr.isEmpty else { done(nil); return }
            done(NoteData(
                sourceURL: sourceURL,
                noteID: awemeID,
                title: title,
                body: title,
                author: authorName,
                comments: comments,
                likes: likes,
                topics: self.topicNames(in: title),
                media: [MediaItem(url: videoURL, fileExtension: "mp4")],
                customReferer: "https://www.douyin.com/"
            ))
        }
        if !vid.isEmpty {
            resolveOriginalPlayURL(vid) { resolved in
                if let resolved = resolved, !resolved.isEmpty {
                    finishVideo(resolved)
                } else {
                    finishVideo(fallbackRaw)
                }
            }
        } else {
            finishVideo(fallbackRaw)
        }
    }

    // MARK: - Layer 2: Cloudflare Worker Fallback

    private func fetchViaCloudWorker(_ sourceURL: URL, workerURL: String, done: @escaping (NoteData?) -> Void) {
        let encoded = sourceURL.absoluteString.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let sep = workerURL.contains("?") ? "&" : "?"
        guard let reqURL = URL(string: "\(workerURL)\(sep)url=\(encoded)") else { done(nil); return }
        var request = URLRequest(url: reqURL, timeoutInterval: 20)
        request.setValue(Self.desktopUserAgent, forHTTPHeaderField: "User-Agent")
        URLSession.shared.dataTask(with: request) { data, _, _ in
            guard let data = data,
                  let root = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any],
                  (root["code"] as? Int) == 200,
                  let payload = root["data"] as? [String: Any] else {
                done(nil)
                return
            }
            let title = self.string(payload["title"])
            let authorObj = payload["author"] as? [String: Any]
            let authorName = self.string(authorObj?["name"])
            let type = self.string(payload["type"])
            var media: [MediaItem] = []
            if type == "image" || type == "live" {
                for raw in (payload["images"] as? [String]) ?? [] {
                    let https = self.toHttps(raw)
                    if let u = URL(string: https) {
                        media.append(MediaItem(url: u, fileExtension: self.guessImageExt(https)))
                    }
                }
                for entry in (payload["live_photo"] as? [[String: Any]]) ?? [] {
                    let v = self.toHttps(self.string(entry["video"]))
                    if let u = URL(string: v), !v.isEmpty {
                        media.append(MediaItem(url: u, fileExtension: "mp4"))
                    }
                }
            } else {
                let v = self.ensureVideoMimeType(self.toHttps(self.string(payload["url"])))
                if let u = URL(string: v), !v.isEmpty {
                    media.append(MediaItem(url: u, fileExtension: "mp4"))
                }
            }
            guard !media.isEmpty else { done(nil); return }
            done(NoteData(
                sourceURL: sourceURL,
                noteID: self.string(payload["video_id"]),
                title: title,
                body: self.string(payload["desc"], fallback: title),
                author: authorName,
                comments: "未知",
                likes: "未知",
                topics: self.topicNames(in: title),
                media: media,
                customReferer: "https://www.douyin.com/"
            ))
        }.resume()
    }

    // MARK: - Layer 3: WebView Fallback

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        poll()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        finish(note: nil, error: error)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        finish(note: nil, error: error)
    }

    private func poll() {
        guard !finished, let webView = webView else { return }
        webView.evaluateJavaScript(Self.extractionScript) { result, _ in
            guard !self.finished else { return }
            if let raw = result as? String,
               let data = raw.data(using: .utf8),
               let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let media = value["media"] as? [[String: Any]], !media.isEmpty {
                do {
                    self.finish(note: try self.parse(value), error: nil)
                } catch {
                    self.finish(note: nil, error: error)
                }
                return
            }
            self.attempt += 1
            if self.attempt >= 40 {
                self.finish(note: nil, error: AppFailure.mediaMissing)
            } else {
                DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.poll() }
            }
        }
    }

    private func parse(_ payload: [String: Any]) throws -> NoteData {
        guard let sourceURL = sourceURL else { throw AppFailure.invalidURL }
        let title = string(payload["title"])
        let finalURL = string(payload["final_url"])
        let noteID = firstMatch(#"/(?:note|video)/(\d+)"#, in: finalURL)
        let mediaValues = payload["media"] as? [[String: Any]] ?? []
        let media: [MediaItem] = mediaValues.compactMap { value in
            let raw = string(value["url"])
            guard let url = URL(string: raw), !raw.isEmpty else { return nil }
            return MediaItem(url: url, fileExtension: string(value["extension"], fallback: "webp"))
        }
        guard !media.isEmpty else { throw AppFailure.mediaMissing }
        return NoteData(
            sourceURL: sourceURL,
            noteID: noteID,
            title: title,
            body: title,
            author: string(payload["author"]),
            comments: string(payload["comments"], fallback: "未知"),
            likes: string(payload["likes"], fallback: "未知"),
            topics: topicNames(in: title),
            media: media,
            customReferer: "https://www.douyin.com/"
        )
    }

    // MARK: - Helpers

    private func resolveAwemeID(_ url: URL, done: @escaping (String) -> Void) {
        let direct = extractAwemeID(from: url)
        if !direct.isEmpty { done(direct); return }
        followRedirects(url, ua: Self.desktopUserAgent, remaining: 5) { finalURL in
            done(self.extractAwemeID(from: finalURL))
        }
    }

    private func extractAwemeID(from url: URL) -> String {
        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
           let items = components.queryItems {
            for key in ["vid", "id", "modal_id", "v", "s", "pid"] {
                if let val = items.first(where: { $0.name == key })?.value,
                   !firstMatch(#"^([1-9][0-9]{15,19})$"#, in: val).isEmpty {
                    return val
                }
            }
        }
        let segments = url.pathComponents.filter { $0 != "/" }
        if var last = segments.last {
            if last.hasSuffix(".html") { last = String(last.dropLast(5)) }
            if !firstMatch(#"^([1-9][0-9]{15,19})$"#, in: last).isEmpty { return last }
        }
        return firstMatch(#"/(?:note|video|slides)/([1-9][0-9]{15,19})"#, in: url.path)
    }

    private func resolveOriginalPlayURL(_ vid: String, done: @escaping (String?) -> Void) {
        let enc = vid.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? vid
        guard let playURL = URL(string: "https://aweme.snssdk.com/aweme/v1/play/?video_id=\(enc)&ratio=default&line=0") else {
            done(nil); return
        }
        followRedirects(playURL, ua: Self.desktopUserAgent, remaining: 3) { finalURL in
            done(self.toHttps(finalURL.absoluteString))
        }
    }

    private func followRedirects(_ url: URL, ua: String, remaining: Int, done: @escaping (URL) -> Void) {
        guard remaining > 0 else { done(url); return }
        let delegate = ManualRedirectDelegate()
        let session = URLSession(configuration: .ephemeral, delegate: delegate, delegateQueue: nil)
        var req = URLRequest(url: url, timeoutInterval: 10)
        req.setValue(ua, forHTTPHeaderField: "User-Agent")
        session.dataTask(with: req) { _, response, _ in
            session.finishTasksAndInvalidate()
            if let http = response as? HTTPURLResponse,
               (300..<400).contains(http.statusCode),
               let loc = http.allHeaderFields["Location"] as? String ?? http.allHeaderFields["location"] as? String,
               let nextURL = URL(string: loc, relativeTo: url)?.absoluteURL {
                self.followRedirects(nextURL, ua: ua, remaining: remaining - 1, done: done)
            } else {
                done(response?.url ?? url)
            }
        }.resume()
    }

    private func pickBestBitRateURL(_ video: [String: Any]) -> String? {
        let list = (video["bit_rate"] as? [[String: Any]]) ?? (video["bitRateList"] as? [[String: Any]]) ?? []
        let sorted = list.sorted {
            let ba = ($0["bit_rate"] as? Double) ?? ($0["bitRate"] as? Double) ?? 0
            let bb = ($1["bit_rate"] as? Double) ?? ($1["bitRate"] as? Double) ?? 0
            return bb > ba
        }
        for item in sorted {
            let pa = item["play_addr"] as? [String: Any]
            if let cand = (pa?["url_list"] as? [String])?.first(where: { !$0.isEmpty }) {
                return cand
            }
        }
        return nil
    }

    private func toHttps(_ raw: String) -> String {
        let t = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if t.hasPrefix("//") { return "https:" + t }
        if t.hasPrefix("http://") { return "https://" + t.dropFirst(7) }
        return t
    }

    private func ensureVideoMimeType(_ raw: String) -> String {
        if raw.isEmpty || raw.contains("mime_type=") { return raw }
        return raw + (raw.contains("?") ? "&" : "?") + "mime_type=video_mp4"
    }

    private func guessImageExt(_ url: String) -> String {
        let lower = url.lowercased()
        if lower.contains(".png") { return "png" }
        if lower.contains(".jpg") || lower.contains(".jpeg") { return "jpg" }
        return "webp"
    }

    private func topicNames(in text: String) -> [String] {
        guard let expression = try? NSRegularExpression(pattern: #"#([^\s#]+)"#) else { return [] }
        let range = NSRange(text.startIndex..., in: text)
        var seen = Set<String>()
        return expression.matches(in: text, range: range).compactMap { match in
            guard let valueRange = Range(match.range(at: 1), in: text) else { return nil }
            let value = String(text[valueRange])
            return seen.insert(value).inserted ? value : nil
        }
    }

    private func firstMatch(_ pattern: String, in text: String) -> String {
        guard let expression = try? NSRegularExpression(pattern: pattern),
              let match = expression.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)),
              let range = Range(match.range(at: 1), in: text) else { return "" }
        return String(text[range])
    }

    private func string(_ value: Any?, fallback: String = "") -> String {
        guard let value = value, !(value is NSNull) else { return fallback }
        let output = value as? String ?? String(describing: value)
        return output.isEmpty ? fallback : output
    }

    private func finish(note: NoteData?, error: Error?) {
        guard !finished else { return }
        finished = true
        webView?.stopLoading()
        webView?.removeFromSuperview()
        webView = nil
        let callback = completion
        completion = nil
        callback?(note, error)
    }

    private static let extractionScript = """
    (function(){
      var main=document.querySelector('main')||document.body;
      var current=location.href, isNote=/\\/note\\//.test(current);
      var text=main.innerText||'', meta=(document.querySelector('meta[name="description"]')||{}).content||'';
      var title=(document.title||'').replace(/\\s*-\\s*抖音\\s*$/,'').trim(), author='';
      document.querySelectorAll('script[type="application/ld+json"]').forEach(function(n){
        try {
          var v=JSON.parse(n.textContent||'{}');
          var a=(v.itemListElement||[]).filter(function(x){return Number(x.position)===2})[0];
          if(!author&&a&&a.name) author=String(a.name);
        } catch(e) {}
      });
      if(!author&&meta.indexOf(' - ')>=0){
        var m=meta.split(' - ').slice(1).join(' - ').match(/^(.*?)于\\d{8}发布/);
        author=m?m[1]:'';
      }
      if(author&&meta.indexOf(' - '+author+'于')>=0) title=meta.split(' - '+author+'于',1)[0].trim()||title;
      function read(s){var n=main.querySelector(s);return n?(n.innerText||n.textContent||'').trim():''}
      var media=[], seen={};
      if(isNote){
        main.querySelectorAll('img').forEach(function(n){
          var u=n.currentSrc||n.src||'';
          if(u.indexOf('aweme-images')<0||seen[u]) return;
          seen[u]=1;
          media.push({url:u,extension:u.indexOf('.png')>=0?'png':((u.indexOf('.jpeg')>=0||u.indexOf('.jpg')>=0)?'jpg':'webp')});
        });
      } else {
        main.querySelectorAll('video,video source').forEach(function(n){
          var u=n.currentSrc||n.src||'';
          if(!/^https?:/.test(u)||seen[u]) return;
          seen[u]=1; media.push({url:u,extension:'mp4'});
        });
      }
      return JSON.stringify({
        final_url:current,title:title,author:author,
        likes:read('[data-e2e="video-player-digg"]')||'未知',
        comments:read('[data-e2e="feed-comment-icon"]')||(text.match(/评论\\(([^)]+)\\)/)||[])[1]||'未知',
        media:media
      });
    })()
    """
}

private final class ManualRedirectDelegate: NSObject, URLSessionTaskDelegate {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(nil)
    }
}
