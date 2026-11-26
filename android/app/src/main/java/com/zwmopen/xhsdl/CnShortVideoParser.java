package com.zwmopen.xhsdl;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class CnShortVideoParser {
    private static final String DESKTOP_UA =
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            + "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36";
    private static final String MOBILE_UA =
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 "
            + "(KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1";

    public NoteData fetch(String sourceUrl) throws Exception {
        String sub = PlatformRouter.detectCnSubplatform(sourceUrl);
        switch (sub) {
            case "kuaishou": return parseKuaishou(sourceUrl);
            case "weibo": return parseWeibo(sourceUrl);
            case "toutiao": return parseToutiao(sourceUrl);
            case "pipixia": return parsePipixia(sourceUrl);
            case "pipigx": return parsePipigx(sourceUrl);
            case "zuiyou": return parseZuiyou(sourceUrl);
            case "doubao": return parseDoubao(sourceUrl);
            case "jimeng": return parseJimeng(sourceUrl);
            default: throw new IOException("暂不支持该平台链接：" + sourceUrl);
        }
    }

    private NoteData parseKuaishou(String sourceUrl) throws Exception {
        String finalUrl = resolveRedirects(sourceUrl, MOBILE_UA);
        String html = httpGet(finalUrl, MOBILE_UA, "https://www.kuaishou.com/");
        Matcher m = Pattern.compile("window\\.INIT_STATE\\s*=\\s*(.*?)</script>", Pattern.DOTALL).matcher(html);
        if (!m.find()) throw new IOException("快手页面未找到作品数据，可能受风控限制");
        String rawJson = m.group(1).trim().replaceAll(";+$", "");
        JSONObject state;
        try {
            state = new JSONObject(rawJson);
        } catch (Exception ignored) {
            rawJson = rawJson.replace("\"{\"err_msg\":\"launchApplication:fail\"}\"", "\"launchApplication:fail\"")
                    .replace("\"{\"err_msg\":\"system:access_denied\"}\"", "\"system:access_denied\"");
            state = new JSONObject(rawJson);
        }
        JSONObject photo = null;
        Iterator<String> keys = state.keys();
        while (keys.hasNext()) {
            JSONObject v = state.optJSONObject(keys.next());
            if (v != null && v.optJSONObject("photo") != null) {
                photo = v.optJSONObject("photo");
                break;
            }
        }
        if (photo == null) throw new IOException("快手页面未解析到作品信息");

        NoteData note = baseNote(sourceUrl, "https://www.kuaishou.com/",
                photo.optString("photoId", photo.optString("id")),
                photo.optString("caption", "快手作品"),
                photo.optString("userName", "快手作者"));
        if (photo.has("likeCount")) note.likes = String.valueOf(photo.optLong("likeCount"));

        JSONObject extParams = photo.optJSONObject("ext_params");
        JSONObject atlas = extParams != null ? extParams.optJSONObject("atlas") : null;
        JSONArray atlasList = atlas != null ? atlas.optJSONArray("list") : null;
        if (atlasList != null && atlasList.length() > 0) {
            for (int i = 0; i < atlasList.length(); i++) {
                String p = atlasList.optString(i, "").replaceFirst("^/+", "");
                if (!p.isEmpty()) {
                    String imgUrl = p.startsWith("http") ? p : "https://tx2.a.yximgs.com/" + p;
                    addImage(note, imgUrl);
                }
            }
        } else if ("SINGLE_PICTURE".equals(photo.optString("photoType")) || photo.optBoolean("singlePicture", false)) {
            JSONArray covers = photo.optJSONArray("coverUrls");
            if (covers != null && covers.length() > 0 && covers.optJSONObject(0) != null) {
                addImage(note, toHttps(covers.optJSONObject(0).optString("url")));
            }
        } else {
            String videoUrl = "";
            JSONArray mv = photo.optJSONArray("mainMvUrls");
            if (mv != null && mv.length() > 0 && mv.optJSONObject(0) != null) {
                videoUrl = toHttps(mv.optJSONObject(0).optString("url"));
            }
            if (videoUrl.isEmpty()) {
                try {
                    videoUrl = toHttps(photo.getJSONObject("manifest").getJSONArray("adaptationSet")
                            .getJSONObject(0).getJSONArray("representation").getJSONObject(0).getString("url"));
                } catch (Exception ignored) {
                }
            }
            if (!videoUrl.isEmpty()) note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        }
        if (note.media.isEmpty()) throw new IOException("快手作品未提取到有效视频或图集直链");
        return note;
    }

    private NoteData parseWeibo(String sourceUrl) throws Exception {
        String target = sourceUrl.contains("t.cn/") ? resolveRedirects(sourceUrl, DESKTOP_UA) : sourceUrl;
        String videoId = queryParam(target, "fid");
        if (videoId.isEmpty()) {
            Matcher m = Pattern.compile("weibo\\.com/tv/(?:show|v)/([^?&#/]+)").matcher(target);
            if (m.find()) videoId = m.group(1);
        }
        if (videoId.isEmpty()) throw new IOException("未能从微博链接提取视频 ID");

        String pagePath = "/tv/show/" + videoId;
        String apiUrl = "https://weibo.com/tv/api/component?page=" + URLEncoder.encode(pagePath, "UTF-8");
        JSONObject payload = new JSONObject();
        payload.put("Component_Play_Playinfo", new JSONObject().put("oid", videoId));
        String body = "data=" + URLEncoder.encode(payload.toString(), "UTF-8");
        String raw = httpPost(apiUrl, body, "application/x-www-form-urlencoded", DESKTOP_UA, "https://weibo.com" + pagePath);
        JSONObject info = new JSONObject(raw).optJSONObject("data");
        JSONObject playInfo = info != null ? info.optJSONObject("Component_Play_Playinfo") : null;
        JSONObject urls = playInfo != null ? playInfo.optJSONObject("urls") : null;
        if (urls == null || urls.length() == 0) throw new IOException("微博接口未返回视频直链");

        String bestUrl = "";
        int bestRank = -1;
        Iterator<String> keys = urls.keys();
        while (keys.hasNext()) {
            String label = keys.next();
            int rank = rankQuality(label);
            String u = toHttps(urls.optString(label));
            if (!u.isEmpty() && rank > bestRank) {
                bestRank = rank;
                bestUrl = u;
            }
        }
        if (bestUrl.isEmpty()) throw new IOException("微博视频直链为空");
        NoteData note = baseNote(sourceUrl, "https://weibo.com/", videoId,
                playInfo.optString("title", playInfo.optString("text", "微博视频")),
                playInfo.optString("author", playInfo.optString("nickname", "微博作者")));
        note.media.add(new NoteData.MediaItem(bestUrl, "mp4", "video/mp4"));
        return note;
    }

    private NoteData parseToutiao(String sourceUrl) throws Exception {
        String finalUrl = resolveRedirects(sourceUrl, DESKTOP_UA);
        Matcher m = Pattern.compile("(?:video/|group/|item/)(\\d+)").matcher(finalUrl);
        if (!m.find()) m = Pattern.compile("(\\d{10,})").matcher(finalUrl);
        if (!m.find()) throw new IOException("无法从今日头条链接提取视频 ID");
        String vid = m.group(1);

        String html = httpGet("https://www.toutiao.com/video/" + vid, DESKTOP_UA, "https://www.toutiao.com/");
        Matcher dm = Pattern.compile("<script id=\"RENDER_DATA\" type=\"application/json\">(.*?)</script>", Pattern.DOTALL).matcher(html);
        if (!dm.find()) throw new IOException("今日头条页面未找到视频数据");
        JSONObject data = new JSONObject(URLDecoder.decode(dm.group(1), "UTF-8")).optJSONObject("data");
        JSONObject initVideo = data != null ? data.optJSONObject("initialVideo") : null;
        JSONObject playInfo = initVideo != null ? initVideo.optJSONObject("videoPlayInfo") : null;
        JSONArray videoList = playInfo != null ? playInfo.optJSONArray("video_list") : null;
        String videoUrl = "";
        if (videoList != null) {
            for (int i = videoList.length() - 1; i >= 0; i--) {
                JSONObject item = videoList.optJSONObject(i);
                if (item != null && !item.optString("main_url").isEmpty()) {
                    videoUrl = toHttps(item.optString("main_url"));
                    break;
                }
            }
        }
        if (videoUrl.isEmpty()) throw new IOException("今日头条未提取到有效视频直链");
        JSONObject itemCell = initVideo.optJSONObject("itemCell");
        JSONObject userInfo = itemCell != null ? itemCell.optJSONObject("userInfo") : null;
        NoteData note = baseNote(sourceUrl, "https://www.toutiao.com/", vid,
                initVideo.optString("title", "今日头条视频"),
                userInfo != null ? userInfo.optString("name", "头条作者") : "头条作者");
        note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        return note;
    }

    private NoteData parsePipixia(String sourceUrl) throws Exception {
        String finalUrl = resolveRedirects(sourceUrl, DESKTOP_UA);
        Matcher m = Pattern.compile("item/(\\d+)").matcher(finalUrl);
        if (!m.find()) throw new IOException("无法从皮皮虾链接提取作品 ID");
        String cellId = m.group(1);

        String apiUrl = "https://h5.pipix.com/bds/cell/cell_h5_comment/?count=5&aid=1319&app_name=super&cell_id=" + cellId;
        JSONObject root = new JSONObject(httpGet(apiUrl, DESKTOP_UA, "https://h5.pipix.com/"));
        JSONArray comments = root.optJSONObject("data") != null ? root.optJSONObject("data").optJSONArray("cell_comments") : null;
        JSONObject item = null;
        if (comments != null) {
            for (int i = 0; i < comments.length(); i++) {
                JSONObject ci = comments.optJSONObject(i) != null ? comments.optJSONObject(i).optJSONObject("comment_info") : null;
                if (ci != null && ci.optJSONObject("item") != null) {
                    item = ci.optJSONObject("item");
                    break;
                }
            }
        }
        if (item == null) throw new IOException("皮皮虾接口未返回作品详情");

        NoteData note = baseNote(sourceUrl, "https://h5.pipix.com/", cellId,
                item.optString("content", "皮皮虾作品"),
                item.optJSONObject("author") != null ? item.optJSONObject("author").optString("name", "皮皮虾作者") : "皮皮虾作者");
        try {
            String vUrl = toHttps(item.getJSONObject("video").getJSONObject("video_high")
                    .getJSONArray("url_list").getJSONObject(0).getString("url"));
            if (!vUrl.isEmpty()) note.media.add(new NoteData.MediaItem(vUrl, "mp4", "video/mp4"));
        } catch (Exception ignored) {
        }
        JSONObject noteObj = item.optJSONObject("note");
        JSONArray multi = noteObj != null ? noteObj.optJSONArray("multi_image") : null;
        if (multi != null) {
            for (int i = 0; i < multi.length(); i++) {
                JSONArray ul = multi.optJSONObject(i) != null ? multi.optJSONObject(i).optJSONArray("url_list") : null;
                if (ul != null && ul.length() > 0 && ul.optJSONObject(0) != null) {
                    addImage(note, toHttps(ul.optJSONObject(0).optString("url")));
                }
            }
        }
        if (note.media.isEmpty()) throw new IOException("皮皮虾作品未提取到媒体");
        return note;
    }

    private NoteData parsePipigx(String sourceUrl) throws Exception {
        String finalUrl = resolveRedirects(sourceUrl, DESKTOP_UA);
        String pid = queryParam(finalUrl, "pid");
        String mid = queryParam(finalUrl, "mid");
        if (pid.isEmpty() || mid.isEmpty()) throw new IOException("无法从皮皮搞笑链接提取 pid/mid");

        JSONObject req = new JSONObject()
                .put("pid", Long.parseLong(pid))
                .put("mid", Long.parseLong(mid))
                .put("type", "post");
        String raw = httpPost("https://h5.pipigx.com/ppapi/share/fetch_content", req.toString(),
                "application/json", DESKTOP_UA, "https://h5.pipigx.com/");
        JSONObject post = new JSONObject(raw).optJSONObject("data") != null
                ? new JSONObject(raw).optJSONObject("data").optJSONObject("post") : null;
        if (post == null) throw new IOException("皮皮搞笑未返回作品数据");

        String videoUrl = extractUrlFromVideosField(post.opt("videos"));
        if (videoUrl.isEmpty()) throw new IOException("皮皮搞笑未提取到视频直链");
        NoteData note = baseNote(sourceUrl, "https://h5.pipigx.com/", pid,
                post.optString("content", "皮皮搞笑作品"),
                post.optJSONObject("user") != null ? post.optJSONObject("user").optString("name", "皮皮搞笑作者") : "皮皮搞笑作者");
        note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        return note;
    }

    private NoteData parseZuiyou(String sourceUrl) throws Exception {
        String pid = queryParam(sourceUrl, "pid");
        if (pid.isEmpty()) pid = queryParam(resolveRedirects(sourceUrl, DESKTOP_UA), "pid");
        if (pid.isEmpty()) throw new IOException("无法从最右链接提取 pid");

        String raw = httpPost("https://share.izuiyou.com/api/post/detail",
                new JSONObject().put("pid", Long.parseLong(pid)).toString(),
                "application/json", DESKTOP_UA, "https://share.izuiyou.com/");
        JSONObject data = new JSONObject(raw).optJSONObject("data");
        JSONObject post = data != null ? data.optJSONObject("post") : null;
        if (post == null) throw new IOException("最右接口未返回作品详情");

        NoteData note = baseNote(sourceUrl, "https://share.izuiyou.com/", pid,
                post.optString("content", "最右作品"),
                post.optJSONObject("member") != null ? post.optJSONObject("member").optString("name", "最右作者") : "最右作者");
        if (post.has("likes")) note.likes = String.valueOf(post.optLong("likes"));
        String videoUrl = extractUrlFromVideosField(post.opt("videos"));
        if (!videoUrl.isEmpty()) {
            note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        } else {
            JSONArray imgs = post.optJSONArray("imgs");
            if (imgs != null) {
                for (int i = 0; i < imgs.length(); i++) {
                    JSONObject urls = imgs.optJSONObject(i) != null ? imgs.optJSONObject(i).optJSONObject("urls") : null;
                    if (urls == null) continue;
                    JSONObject origin = urls.optJSONObject("origin");
                    if (origin == null) origin = urls.optJSONObject("540");
                    JSONArray ul = origin != null ? origin.optJSONArray("urls") : null;
                    if (ul != null && ul.length() > 0) addImage(note, toHttps(ul.optString(0)));
                }
            }
        }
        if (note.media.isEmpty()) throw new IOException("最右作品未提取到媒体");
        return note;
    }

    private NoteData parseDoubao(String sourceUrl) throws Exception {
        String finalUrl = resolveRedirects(sourceUrl, DESKTOP_UA);
        String shareId = queryParam(finalUrl, "share_id");
        String videoId = queryParam(finalUrl, "video_id");
        if (shareId.isEmpty() || videoId.isEmpty()) throw new IOException("无法从豆包链接提取 share_id / video_id");

        String apiUrl = "https://www.doubao.com/creativity/share/get_video_share_info"
                + "?version_code=20800&language=zh-CN&device_platform=web&aid=497858"
                + "&real_aid=497858&pkg_type=release_version&pc_version=3.8.3&samantha_web=1";
        JSONObject body = new JSONObject().put("share_id", shareId).put("vid", videoId).put("creation_id", "");
        String raw = httpPost(apiUrl, body.toString(), "application/json", DESKTOP_UA, finalUrl);
        JSONObject root = new JSONObject(raw);
        if (root.optInt("code", -1) != 0) throw new IOException("豆包视频接口错误：" + root.optString("msg"));
        JSONObject data = root.optJSONObject("data");
        if (data == null) throw new IOException("豆包视频接口返回为空");

        String videoUrl = "";
        for (String key : new String[]{"play_url", "video_url", "url", "download_url"}) {
            String candidate = data.optString(key, "");
            if (candidate.startsWith("http")) {
                videoUrl = toHttps(candidate);
                break;
            }
        }
        if (videoUrl.isEmpty() && data.optJSONObject("play_info") != null) {
            JSONObject pi = data.optJSONObject("play_info");
            videoUrl = toHttps(pi.optString("main", pi.optString("url", "")));
        }
        if (videoUrl.isEmpty()) throw new IOException("豆包视频接口未返回无水印直链");

        NoteData note = baseNote(sourceUrl, "https://www.doubao.com/", videoId,
                data.optString("prompt", data.optString("title", "豆包AI视频")),
                data.optString("author_name", "豆包AI"));
        note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        return note;
    }

    private NoteData parseJimeng(String sourceUrl) throws Exception {
        String target = sourceUrl.contains("/s/") ? resolveRedirects(sourceUrl, DESKTOP_UA) : sourceUrl;
        String itemId = "";
        for (String k : new String[]{"id", "item_id", "published_item_id", "work_id"}) {
            itemId = queryParam(target, k);
            if (!itemId.isEmpty()) break;
        }
        if (itemId.isEmpty()) {
            Matcher m = Pattern.compile("(\\d{16,})").matcher(target);
            if (m.find()) itemId = m.group(1);
        }
        if (itemId.isEmpty()) throw new IOException("无法从即梦 AI 链接提取作品 ID");

        String raw = httpPost("https://jimeng.jianying.com/mweb/v1/get_item_info",
                new JSONObject().put("published_item_id", itemId).toString(),
                "application/json", DESKTOP_UA, "https://jimeng.jianying.com/");
        JSONObject root = new JSONObject(raw);
        if (!"0".equals(root.optString("ret", "0"))) throw new IOException("即梦接口错误：" + root.optString("errmsg"));
        JSONObject data = root.optJSONObject("data");
        if (data == null) throw new IOException("即梦接口未返回数据");
        JSONObject common = data.optJSONObject("common_attr");
        JSONObject author = data.optJSONObject("author");
        JSONObject video = data.optJSONObject("video");

        String videoUrl = "";
        if (video != null) {
            JSONObject transcoded = video.optJSONObject("transcoded_video");
            JSONObject origin = transcoded != null ? transcoded.optJSONObject("origin") : null;
            if (origin != null && !origin.optString("video_url").isEmpty()) {
                videoUrl = toHttps(origin.optString("video_url"));
            } else if (video.optJSONObject("origin_video") != null
                    && !video.optJSONObject("origin_video").optString("video_url").isEmpty()) {
                videoUrl = toHttps(video.optJSONObject("origin_video").optString("video_url"));
            } else if (transcoded != null) {
                Iterator<String> keys = transcoded.keys();
                while (keys.hasNext()) {
                    JSONObject item = transcoded.optJSONObject(keys.next());
                    if (item != null && !item.optString("video_url").isEmpty()) {
                        videoUrl = toHttps(item.optString("video_url"));
                        break;
                    }
                }
            }
        }
        if (videoUrl.isEmpty()) throw new IOException("即梦 AI 作品未提取到有效视频直链");

        NoteData note = baseNote(sourceUrl, "https://jimeng.jianying.com/", itemId,
                common != null ? common.optString("description", "即梦AI视频") : "即梦AI视频",
                author != null ? author.optString("name", "即梦AI") : "即梦AI");
        note.media.add(new NoteData.MediaItem(videoUrl, "mp4", "video/mp4"));
        return note;
    }

    private static NoteData baseNote(String sourceUrl, String referer, String id, String title, String author) {
        NoteData note = new NoteData();
        note.sourceUrl = sourceUrl;
        note.referer = referer;
        note.noteId = id == null ? "" : id;
        note.title = title == null ? "" : title.trim();
        note.description = note.title;
        note.author = author == null ? "" : author.trim();
        return note;
    }

    private static void addImage(NoteData note, String url) {
        if (url == null || url.isEmpty()) return;
        String lower = url.toLowerCase();
        String ext = lower.contains(".png") ? "png" : (lower.contains(".webp") ? "webp" : "jpg");
        String mime = "png".equals(ext) ? "image/png" : ("webp".equals(ext) ? "image/webp" : "image/jpeg");
        note.media.add(new NoteData.MediaItem(url, ext, mime));
    }

    private static String extractUrlFromVideosField(Object videos) {
        if (videos instanceof JSONObject) {
            JSONObject obj = (JSONObject) videos;
            Iterator<String> keys = obj.keys();
            while (keys.hasNext()) {
                JSONObject v = obj.optJSONObject(keys.next());
                if (v != null && !v.optString("url").isEmpty()) return toHttps(v.optString("url"));
            }
        } else if (videos instanceof JSONArray) {
            JSONArray arr = (JSONArray) videos;
            for (int i = 0; i < arr.length(); i++) {
                JSONObject v = arr.optJSONObject(i);
                if (v != null && !v.optString("url").isEmpty()) return toHttps(v.optString("url"));
            }
        }
        return "";
    }

    private static int rankQuality(String label) {
        String upper = label == null ? "" : label.toUpperCase();
        if (upper.contains("4K")) return 6;
        if (upper.contains("2K")) return 5;
        if (upper.contains("1080P")) return 4;
        if (upper.contains("720P")) return 3;
        if (upper.contains("480P")) return 2;
        if (upper.contains("360P")) return 1;
        return 0;
    }

    private static String queryParam(String url, String key) {
        try {
            String query = new URL(url).getQuery();
            if (query == null) return "";
            for (String pair : query.split("&")) {
                int eq = pair.indexOf('=');
                if (eq <= 0) continue;
                if (key.equals(URLDecoder.decode(pair.substring(0, eq), "UTF-8"))) {
                    return URLDecoder.decode(pair.substring(eq + 1), "UTF-8");
                }
            }
        } catch (Exception ignored) {
        }
        return "";
    }

    private static String resolveRedirects(String startUrl, String ua) throws IOException {
        String current = startUrl;
        for (int i = 0; i < 6; i++) {
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

    private static String httpGet(String url, String ua, String referer) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setConnectTimeout(12000);
        conn.setReadTimeout(20000);
        conn.setRequestProperty("User-Agent", ua);
        conn.setRequestProperty("Referer", referer);
        return readResponse(conn);
    }

    private static String httpPost(String url, String body, String contentType, String ua, String referer) throws IOException {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setConnectTimeout(12000);
        conn.setReadTimeout(20000);
        conn.setRequestProperty("User-Agent", ua);
        conn.setRequestProperty("Referer", referer);
        conn.setRequestProperty("Content-Type", contentType);
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        try (OutputStream os = conn.getOutputStream()) {
            os.write(bytes);
        }
        return readResponse(conn);
    }

    private static String readResponse(HttpURLConnection conn) throws IOException {
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

    private static String toHttps(String url) {
        if (url == null) return "";
        String t = url.trim();
        if (t.startsWith("//")) return "https:" + t;
        if (t.startsWith("http://")) return "https://" + t.substring(7);
        return t;
    }
}
