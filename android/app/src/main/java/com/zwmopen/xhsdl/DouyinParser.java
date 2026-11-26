package com.zwmopen.xhsdl;

import android.app.Activity;
import android.graphics.Color;
import android.os.Handler;
import android.os.Looper;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class DouyinParser {
    private static final String DESKTOP_UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36";
    private static final String MOBILE_UA =
            "Mozilla/5.0 (Linux; Android 13; 2210132C Build/TKQ1.220829.002) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36";
    private static final String DETAIL_ENDPOINT = "https://api.amemv.com/aweme/v1/aweme/detail/";
    private static final String ORIGINAL_PLAY_ENDPOINT = "https://aweme.snssdk.com/aweme/v1/play/";

    private static final Pattern ID_PATTERN = Pattern.compile("/(?:note|video|slides)/(\\d+)");
    private static final Pattern AWEME_ID_PATTERN = Pattern.compile("^[1-9][0-9]{15,19}$");
    private static final Pattern TOPIC_PATTERN = Pattern.compile("#([^\\s#]+)");
    private static final String SCRIPT =
            "(function(){"
            + "var main=document.querySelector('main')||document.body;"
            + "var current=location.href,isNote=/\\\\/note\\\\//.test(current);"
            + "var text=main.innerText||'',meta=(document.querySelector('meta[name=\"description\"]')||{}).content||'';"
            + "var title=(document.title||'').replace(/\\\\s*-\\\\s*抖音\\\\s*$/,'').trim(),author='';"
            + "document.querySelectorAll('script[type=\"application/ld+json\"]').forEach(function(n){"
            + "try{var v=JSON.parse(n.textContent||'{}'),a=(v.itemListElement||[]).filter(function(x){return Number(x.position)===2})[0];"
            + "if(!author&&a&&a.name)author=String(a.name)}catch(e){}});"
            + "if(!author&&meta.indexOf(' - ')>=0){var m=meta.split(' - ').slice(1).join(' - ').match(/^(.*?)于\\\\d{8}发布/);author=m?m[1]:''}"
            + "if(author&&meta.indexOf(' - '+author+'于')>=0)title=meta.split(' - '+author+'于',1)[0].trim()||title;"
            + "function read(s){var n=main.querySelector(s);return n?(n.innerText||n.textContent||'').trim():''}"
            + "var media=[],seen={};"
            + "if(isNote){main.querySelectorAll('img').forEach(function(n){var u=n.currentSrc||n.src||'';"
            + "if(u.indexOf('aweme-images')<0||seen[u])return;seen[u]=1;"
            + "media.push({url:u,kind:'image',extension:u.indexOf('.png')>=0?'png':(u.indexOf('.jpeg')>=0||u.indexOf('.jpg')>=0?'jpg':'webp')})})}"
            + "else{main.querySelectorAll('video,video source').forEach(function(n){var u=n.currentSrc||n.src||'';"
            + "if(!/^https?:/.test(u)||seen[u])return;seen[u]=1;media.push({url:u,kind:'video',extension:'mp4'})})}"
            + "var published=(text.match(/发布时间[：:]\\\\s*([^\\\\n]+)/)||[])[1]||'';"
            + "return JSON.stringify({final_url:current,title:title,author:author,"
            + "likes:read('[data-e2e=\"video-player-digg\"]')||'未知',"
            + "comments:read('[data-e2e=\"feed-comment-icon\"]')||(text.match(/评论\\\\(([^)]+)\\\\)/)||[])[1]||'未知',"
            + "favorites:read('[data-e2e=\"video-player-collect\"]')||'未知',"
            + "shares:read('[data-e2e=\"video-player-share\"]')||'未知',"
            + "published_at:published.trim(),media:media});"
            + "})()";

    public NoteData fetch(Activity activity, String sourceUrl) throws Exception {
        return fetch(activity, sourceUrl, "");
    }

    public NoteData fetch(Activity activity, String sourceUrl, String cloudWorkerUrl) throws Exception {
        // Layer 1: Cookie-free fast detail API + 302 original play endpoint
        try {
            NoteData fast = fetchViaFastApi(sourceUrl);
            if (fast != null && !fast.media.isEmpty()) return fast;
        } catch (Exception ignored) {
        }

        // Layer 2: Optional Cloudflare Worker fallback
        if (cloudWorkerUrl != null && !cloudWorkerUrl.trim().isEmpty()) {
            try {
                NoteData cloud = fetchViaCloudWorker(sourceUrl, cloudWorkerUrl.trim());
                if (cloud != null && !cloud.media.isEmpty()) return cloud;
            } catch (Exception ignored) {
            }
        }

        // Layer 3: Built-in WebView fallback
        return fetchViaWebView(activity, sourceUrl);
    }

    private NoteData fetchViaFastApi(String sourceUrl) throws Exception {
        String awemeId = extractAwemeId(sourceUrl);
        if (awemeId.isEmpty()) {
            String resolved = resolveRedirects(sourceUrl, DESKTOP_UA, 6);
            awemeId = extractAwemeId(resolved);
        }
        if (awemeId.isEmpty()) return null;

        String detailUrl = DETAIL_ENDPOINT + "?aweme_id=" + awemeId
                + "&aid=6383&device_platform=web&version_code=190500&version_name=19.5.0";
        String raw = httpGet(detailUrl, MOBILE_UA);
        JSONObject root = new JSONObject(raw);
        if (root.optInt("status_code", -1) != 0) return null;
        JSONObject detail = root.optJSONObject("aweme_detail");
        if (detail == null || !awemeId.equals(detail.optString("aweme_id"))) return null;

        NoteData note = new NoteData();
        note.sourceUrl = sourceUrl;
        note.referer = "https://www.douyin.com/";
        note.noteId = awemeId;
        note.title = detail.optString("desc", "").trim();
        note.description = note.title;
        JSONObject author = detail.optJSONObject("author");
        if (author != null) note.author = author.optString("nickname", "").trim();
        JSONObject stats = detail.optJSONObject("statistics");
        if (stats != null) {
            if (stats.has("digg_count")) note.likes = String.valueOf(stats.optLong("digg_count"));
            if (stats.has("comment_count")) note.comments = String.valueOf(stats.optLong("comment_count"));
        }
        fillTopics(note, note.title);

        JSONArray images = detail.optJSONArray("images");
        if (images == null) images = detail.optJSONArray("image_list");
        if (images != null && images.length() > 0) {
            for (int i = 0; i < images.length(); i++) {
                JSONObject img = images.optJSONObject(i);
                if (img == null) continue;
                JSONArray urlList = img.optJSONArray("urlList");
                if (urlList == null) urlList = img.optJSONArray("url_list");
                String imgUrl = pickFirstString(urlList);
                if (!imgUrl.isEmpty()) {
                    imgUrl = toHttps(imgUrl);
                    String ext = guessImageExt(imgUrl);
                    note.media.add(new NoteData.MediaItem(imgUrl, ext, mimeForImage(ext)));
                }
                JSONObject videoInfo = img.optJSONObject("video");
                if (videoInfo != null) {
                    String vid = extractVid(videoInfo);
                    String liveUrl = !vid.isEmpty() ? resolveOriginalPlayUrl(vid) : "";
                    if (liveUrl.isEmpty()) {
                        JSONObject pa = videoInfo.optJSONObject("play_addr");
                        liveUrl = toHttps(pickFirstString(pa != null ? pa.optJSONArray("url_list") : null))
                                .replace("playwm", "play");
                    }
                    if (!liveUrl.isEmpty()) {
                        note.media.add(new NoteData.MediaItem(ensureVideoMimeType(liveUrl), "mp4", "video/mp4"));
                    }
                }
            }
        } else {
            JSONObject video = detail.optJSONObject("video");
            if (video != null) {
                String vid = extractVid(video);
                String videoUrl = !vid.isEmpty() ? resolveOriginalPlayUrl(vid) : "";
                if (videoUrl.isEmpty()) {
                    videoUrl = pickBestBitRateUrl(video);
                }
                if (videoUrl.isEmpty()) {
                    JSONObject pa = video.optJSONObject("play_addr");
                    videoUrl = toHttps(pickFirstString(pa != null ? pa.optJSONArray("url_list") : null))
                            .replace("playwm", "play");
                }
                if (!videoUrl.isEmpty()) {
                    note.media.add(new NoteData.MediaItem(ensureVideoMimeType(videoUrl), "mp4", "video/mp4"));
                }
            }
        }
        return note.media.isEmpty() ? null : note;
    }

    private NoteData fetchViaCloudWorker(String sourceUrl, String workerUrl) throws Exception {
        String sep = workerUrl.contains("?") ? "&" : "?";
        String endpoint = workerUrl + sep + "url=" + URLEncoder.encode(sourceUrl, "UTF-8");
        String raw = httpGet(endpoint, DESKTOP_UA);
        JSONObject root = new JSONObject(raw);
        if (root.optInt("code", 0) != 200) return null;
        JSONObject data = root.optJSONObject("data");
        if (data == null) return null;

        NoteData note = new NoteData();
        note.sourceUrl = sourceUrl;
        note.referer = "https://www.douyin.com/";
        note.title = data.optString("title", "").trim();
        note.description = data.optString("desc", note.title).trim();
        JSONObject author = data.optJSONObject("author");
        if (author != null) note.author = author.optString("name", "").trim();
        note.noteId = extractAwemeId(sourceUrl);
        if (note.noteId.isEmpty()) note.noteId = data.optString("video_id", "");
        fillTopics(note, note.title);

        String type = data.optString("type", "");
        if ("live".equals(type) || "image".equals(type)) {
            JSONArray imgs = data.optJSONArray("images");
            if (imgs != null) {
                for (int i = 0; i < imgs.length(); i++) {
                    String u = toHttps(imgs.optString(i));
                    if (!u.isEmpty()) {
                        String ext = guessImageExt(u);
                        note.media.add(new NoteData.MediaItem(u, ext, mimeForImage(ext)));
                    }
                }
            }
            JSONArray live = data.optJSONArray("live_photo");
            if (live != null) {
                for (int i = 0; i < live.length(); i++) {
                    JSONObject entry = live.optJSONObject(i);
                    if (entry != null && !entry.optString("video").isEmpty()) {
                        note.media.add(new NoteData.MediaItem(toHttps(entry.optString("video")), "mp4", "video/mp4"));
                    }
                }
            }
        } else {
            String videoUrl = toHttps(data.optString("url"));
            if (!videoUrl.isEmpty()) {
                note.media.add(new NoteData.MediaItem(ensureVideoMimeType(videoUrl), "mp4", "video/mp4"));
            }
        }
        return note.media.isEmpty() ? null : note;
    }

    private NoteData fetchViaWebView(Activity activity, String sourceUrl) throws Exception {
        CountDownLatch latch = new CountDownLatch(1);
        AtomicReference<JSONObject> payload = new AtomicReference<>();
        AtomicReference<Exception> failure = new AtomicReference<>();
        AtomicBoolean finished = new AtomicBoolean(false);
        Handler main = new Handler(Looper.getMainLooper());
        AtomicReference<WebView> webViewRef = new AtomicReference<>();
        AtomicReference<FrameLayout> holderRef = new AtomicReference<>();

        main.post(() -> {
            FrameLayout holder = new FrameLayout(activity);
            holder.setAlpha(0.01f);
            FrameLayout.LayoutParams tiny = new FrameLayout.LayoutParams(2, 2);
            activity.addContentView(holder, tiny);
            holderRef.set(holder);

            WebView webView = new WebView(activity);
            webViewRef.set(webView);
            holder.addView(webView, new FrameLayout.LayoutParams(2, 2));
            WebSettings settings = webView.getSettings();
            settings.setJavaScriptEnabled(true);
            settings.setDomStorageEnabled(true);
            settings.setLoadsImagesAutomatically(true);
            settings.setUserAgentString(DESKTOP_UA);
            webView.setBackgroundColor(Color.TRANSPARENT);
            webView.setWebViewClient(new WebViewClient() {
                @Override
                public void onPageFinished(WebView view, String url) {
                    poll(view, 0, finished, payload, failure, latch);
                }
            });
            webView.loadUrl(sourceUrl);
        });

        if (!latch.await(55, TimeUnit.SECONDS)) {
            failure.compareAndSet(null, new IOException("抖音公开页面加载超时，请稍后重试"));
        }
        finished.set(true);
        main.post(() -> {
            WebView webView = webViewRef.get();
            if (webView != null) {
                webView.stopLoading();
                webView.destroy();
            }
            FrameLayout holder = holderRef.get();
            if (holder != null && holder.getParent() instanceof ViewGroup) {
                ((ViewGroup) holder.getParent()).removeView(holder);
            }
        });
        if (failure.get() != null) throw failure.get();
        if (payload.get() == null) throw new IOException("抖音公开页面没有返回作品数据");
        return parse(sourceUrl, payload.get());
    }

    private void poll(WebView view, int attempt, AtomicBoolean finished,
                      AtomicReference<JSONObject> payload, AtomicReference<Exception> failure,
                      CountDownLatch latch) {
        if (finished.get()) return;
        view.evaluateJavascript(SCRIPT, raw -> {
            try {
                String json = new JSONArray("[" + raw + "]").getString(0);
                JSONObject value = new JSONObject(json);
                if (value.optJSONArray("media") != null
                        && value.optJSONArray("media").length() > 0) {
                    payload.set(value);
                    if (finished.compareAndSet(false, true)) latch.countDown();
                    return;
                }
            } catch (Exception ignored) {
            }
            if (attempt >= 35) {
                failure.set(new IOException("抖音公开页面已打开，但没有取得当前作品媒体"));
                if (finished.compareAndSet(false, true)) latch.countDown();
            } else {
                view.postDelayed(() -> poll(view, attempt + 1, finished, payload, failure, latch), 1000);
            }
        });
    }

    private NoteData parse(String sourceUrl, JSONObject payload) throws Exception {
        NoteData note = new NoteData();
        note.sourceUrl = sourceUrl;
        note.referer = "https://www.douyin.com/";
        note.title = payload.optString("title");
        note.description = note.title;
        note.author = payload.optString("author");
        note.likes = payload.optString("likes", "未知");
        note.comments = payload.optString("comments", "未知");
        Matcher id = ID_PATTERN.matcher(payload.optString("final_url"));
        if (id.find()) note.noteId = id.group(1);
        fillTopics(note, note.title);
        JSONArray media = payload.optJSONArray("media");
        if (media != null) {
            for (int i = 0; i < media.length(); i++) {
                JSONObject item = media.optJSONObject(i);
                if (item == null || item.optString("url").isEmpty()) continue;
                String extension = item.optString("extension", "webp");
                String mime = "mp4".equals(extension) ? "video/mp4" : mimeForImage(extension);
                note.media.add(new NoteData.MediaItem(item.optString("url"), extension, mime));
            }
        }
        if (note.media.isEmpty()) throw new IOException("没有找到抖音原始媒体");
        return note;
    }

    private static void fillTopics(NoteData note, String text) {
        if (text == null) return;
        Matcher topics = TOPIC_PATTERN.matcher(text);
        Set<String> seenTopics = new HashSet<>();
        while (topics.find()) {
            String topic = topics.group(1);
            if (seenTopics.add(topic)) note.topics.add(topic);
        }
    }

    private static String extractAwemeId(String url) {
        if (url == null || url.isEmpty()) return "";
        try {
            URL parsed = new URL(url);
            String query = parsed.getQuery();
            if (query != null) {
                for (String pair : query.split("&")) {
                    int eq = pair.indexOf('=');
                    if (eq <= 0) continue;
                    String k = URLDecoder.decode(pair.substring(0, eq), "UTF-8");
                    String v = URLDecoder.decode(pair.substring(eq + 1), "UTF-8");
                    if (("vid".equals(k) || "id".equals(k) || "modal_id".equals(k)
                            || "v".equals(k) || "s".equals(k) || "pid".equals(k))
                            && AWEME_ID_PATTERN.matcher(v).matches()) {
                        return v;
                    }
                }
            }
            String path = parsed.getPath();
            if (path != null) {
                String[] segs = path.split("/");
                for (int i = segs.length - 1; i >= 0; i--) {
                    String s = segs[i];
                    if (s.isEmpty()) continue;
                    if (s.endsWith(".html")) s = s.substring(0, s.length() - 5);
                    if (AWEME_ID_PATTERN.matcher(s).matches()) return s;
                    break;
                }
            }
        } catch (Exception ignored) {
        }
        Matcher m = ID_PATTERN.matcher(url);
        return m.find() ? m.group(1) : "";
    }

    private static String resolveRedirects(String startUrl, String ua, int maxHops) throws IOException {
        String current = startUrl;
        for (int i = 0; i < maxHops; i++) {
            HttpURLConnection conn = (HttpURLConnection) new URL(current).openConnection();
            conn.setInstanceFollowRedirects(false);
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.setRequestProperty("User-Agent", ua);
            int code = conn.getResponseCode();
            String loc = conn.getHeaderField("Location");
            conn.disconnect();
            if (code >= 300 && code < 400 && loc != null && !loc.isEmpty()) {
                current = new URL(new URL(current), loc).toString();
            } else {
                break;
            }
        }
        return current;
    }

    private static String resolveOriginalPlayUrl(String vid) {
        if (vid == null || vid.isEmpty()) return "";
        try {
            String fallback = ORIGINAL_PLAY_ENDPOINT + "?video_id=" + URLEncoder.encode(vid, "UTF-8") + "&ratio=default&line=0";
            return toHttps(resolveRedirects(fallback, DESKTOP_UA, 3));
        } catch (Exception ignored) {
            return "";
        }
    }

    private static String httpGet(String targetUrl, String ua) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(targetUrl).openConnection();
        conn.setConnectTimeout(12000);
        conn.setReadTimeout(15000);
        conn.setRequestProperty("User-Agent", ua);
        conn.setRequestProperty("Accept", "application/json, text/plain, */*");
        int code = conn.getResponseCode();
        if (code < 200 || code >= 400) {
            conn.disconnect();
            throw new IOException("HTTP " + code);
        }
        StringBuilder sb = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) sb.append(line);
        } finally {
            conn.disconnect();
        }
        return sb.toString();
    }

    private static String extractVid(JSONObject videoObj) {
        JSONObject pa = videoObj.optJSONObject("play_addr");
        if (pa != null && !pa.optString("uri").isEmpty()) return pa.optString("uri");
        return videoObj.optString("uri", "");
    }

    private static String pickBestBitRateUrl(JSONObject video) {
        JSONArray list = video.optJSONArray("bit_rate");
        if (list == null) list = video.optJSONArray("bitRateList");
        if (list == null || list.length() == 0) return "";
        List<JSONObject> items = new ArrayList<>();
        for (int i = 0; i < list.length(); i++) {
            JSONObject obj = list.optJSONObject(i);
            if (obj != null) items.add(obj);
        }
        Collections.sort(items, new Comparator<JSONObject>() {
            @Override
            public int compare(JSONObject a, JSONObject b) {
                long ba = a.optLong("bit_rate", a.optLong("bitRate", 0));
                long bb = b.optLong("bit_rate", b.optLong("bitRate", 0));
                return Long.compare(bb, ba);
            }
        });
        for (JSONObject item : items) {
            JSONObject pa = item.optJSONObject("play_addr");
            String candidate = pickFirstString(pa != null ? pa.optJSONArray("url_list") : null);
            if (!candidate.isEmpty()) return toHttps(candidate).replace("playwm", "play");
        }
        return "";
    }

    private static String pickFirstString(JSONArray arr) {
        if (arr == null) return "";
        for (int i = 0; i < arr.length(); i++) {
            String s = arr.optString(i, "");
            if (!s.isEmpty()) return s;
        }
        return "";
    }

    private static String toHttps(String url) {
        if (url == null) return "";
        String trimmed = url.trim();
        if (trimmed.startsWith("//")) return "https:" + trimmed;
        if (trimmed.startsWith("http://")) return "https://" + trimmed.substring(7);
        return trimmed;
    }

    private static String ensureVideoMimeType(String url) {
        if (url == null || url.isEmpty() || url.contains("mime_type=")) return url;
        return url + (url.contains("?") ? "&" : "?") + "mime_type=video_mp4";
    }

    private static String guessImageExt(String url) {
        String lower = url.toLowerCase();
        if (lower.contains(".png")) return "png";
        if (lower.contains(".jpg") || lower.contains(".jpeg")) return "jpg";
        return "webp";
    }

    private static String mimeForImage(String ext) {
        if ("png".equals(ext)) return "image/png";
        if ("jpg".equals(ext) || "jpeg".equals(ext)) return "image/jpeg";
        return "image/webp";
    }
}
