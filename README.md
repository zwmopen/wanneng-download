# 万能下载器 (Universal Downloader)

一款本地优先的公开社交媒体素材下载工具：**小红书/抖音双平台直解 · 多平台公开媒体下载 · 原格式保存 · 待下载防风控阶梯冷却 · 0 侵入 0 依赖登录**。Windows/CLI/AI Skill 已全面支持小红书、抖音及公开主流媒体平台。

当前正式版本：**v3.6.0** · [下载与发布说明](https://github.com/zwmopen/xhs-dl/releases/tag/v3.6.0) · [源码仓库](https://github.com/zwmopen/xhs-dl)

> 💡 **本地优先核心原则**：这是面向个人工作流的本地自愈工具，不是在线解析站，绝不上传私有数据。下载目录、历史记录与元数据 100% 留存在当前设备。

---

## 🌟 v3.6.0 核心入口：一个万能下载器

日常使用只需要打开原版 Web 页面 `http://127.0.0.1:5678/`，粘贴一条或多条公开链接即可。保存位置、下载节奏、视觉主题和图片格式会记在本机；图片格式默认是 **保持原格式**。

剪贴板采集器仍作为独立的可选后台组件保留，适合需要“复制即入队”的工作流，但它不是下载器的必需入口，也不会改变 5678 页面。需要时再单独启动 `XHS-Clipboard-Collector.vbs`。

---

## 平台与客户端状态

| 客户端 | 当前版本 | 能力 | 状态 |
| --- | --- | --- | --- |
| Windows 桌面/CLI/守护 | **v3.6.0** | 小红书、抖音、剪贴板无感捕获、防风控队列、X/B站/YouTube等公开平台 | 正式可用 |
| Android | V1.3.2 | 小红书、抖音；支持手动粘贴、系统分享、下载目录选择 | Release APK，可内测安装 |
| iPhone | V0.3.2 | 小红书、抖音；支持 Files 目录选择 | 源码和未签名 IPA；需 Apple 签名 |
| AI Skill | **v3.6.0** | 自动提取链接并调用统一路由 | `universal-downloader` 正式入口 |

Windows 和 AI Skill 的“多平台”表示会尝试处理公开媒体，不代表每个平台或每条内容永久可下载；遇到登录、验证码、地区限制或平台风控时会明确失败。Android/iPhone 不宣称已经同步 Windows 的全部平台能力。

### 给其他 AI 的本地 API

5678 页面本身就是本地 JSON API：`POST /api/jobs` 提交任务，`GET /api/jobs/<job_id>` 读取真实进度，`GET /api/jobs` 读取等待/进行中/历史，`GET /api/capabilities` 读取能力和默认格式。接口只绑定回环地址，不接收 Cookie，也不读取浏览器登录态。

旧的 `collector_bridge_api.py`（8765）保留给需要兼容采集队列的其他 AI，默认不启动、不作为日常页面。使用方法见 [`docs/collector-bridge-api.md`](docs/collector-bridge-api.md)。

### 入口关系

日常入口只有原版“万能下载器” Web。剪切板守护和旧桥接控制台是可选组件；需要时它们仍可调用同一个 `xhs_dl` 下载引擎：

| 入口 | 端口/方式 | 作用 |
| --- | --- | --- |
| 原版万能下载器 Web + API | `127.0.0.1:5678` | 日常粘贴、下载、队列、进度、历史和 AI 调用 |
| 剪切板守护（可选） | 后台进程 | 复制公开分享文本后入队；不影响 5678 页面 |
| 旧采集桥接（可选） | `127.0.0.1:8765` | 兼容需要采集队列/回执的其他 AI |

正常启动只会打开 5678。只有明确传入 `-StartBridge` 时才会额外启动 8765，避免两个用户界面造成混淆。

## V2.8.2 多平台范围

Windows 和 AI Skill 首批识别：小红书、抖音、X/Twitter、B站、YouTube、TikTok、Instagram、Facebook、Pinterest、Reddit、Vimeo、Bluesky。小红书与抖音继续走原专用引擎，其他平台由本地 yt-dlp 和随包 FFmpeg 处理。

“支持”表示可尝试下载公开媒体，不代表每条链接永久可用。平台可能临时限流或强制登录；软件不会读取浏览器 Cookie，也不会绕过私密、年龄、地区或访问控制。本机实测 X 与 B站公开链接成功；YouTube 在当前网络触发匿名机器人确认，因此会原样报告失败。

## 核心功能

- 默认下载无平台覆盖水印的原始媒体，保持原尺寸和原格式；设置中可选 JPG 或 PNG
- 图片按 `封面-标题`、`内页1-标题` 命名，视频按 `视频-标题` 命名
- 支持抖音公开视频和图文作品；无需登录，也不读取浏览器 Cookie
- 支持 `xhslink.com`、`xhslink.cn` 短链接与带 `xsec_token` 的小红书长链接
- 整段粘贴、批量去重、慢速执行、逐条回报
- 每篇笔记生成 `文案.txt`，包含标题、正文和话题
- 成功历史集中写入应用数据目录的一个 `history.json`，下载目录不散落 JSON
- 文件夹按 `评数-赞数-标题-作者` 命名，便于快速筛选
- 拟态悬浮 / 克制玻璃双主题界面，主题、保存位置与下载节奏会在本机记住
- Web 任务改为后台执行，可实时查看逐条进度，界面不会在下载时卡死
- Web 版默认保存到当前 Windows 用户的“下载”文件夹，高级设置默认收起；右上角“设置”可直接打开保存位置、下载节奏和格式
- V1 仍保留为显式备用，但不会静默降级到水印图

V2 通过独立的 [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader) CLI 工作。该引擎使用 GPL-3.0，本仓库只做进程适配，不复制其源码。

## 无水印原理

软件不会把水印区域模糊或涂掉。它解析公开分享链接，读取笔记公开媒体信息，并优先下载平台叠加账号水印之前的原始媒体地址。因此画质不会因为“修图去水印”而损失；如果作者把署名、Logo 或文字直接做进原图，这些内容会原样保留。

## 快速下载

### 直接下载

打开 [v3.6.0 Release](https://github.com/zwmopen/xhs-dl/releases/tag/v3.6.0)：

- Windows：`universal-downloader-v3.6.0-windows-portable.zip`
- 校验：`SHA256SUMS-v3.6.0.txt`
- 说明：[v3.6.0 正式稳定版发布说明](docs/RELEASE-NOTES-3.6.0.md)

### Windows 首次安装与使用

推荐使用 **v3.6.0 便携桌面版**：解压 `universal-downloader-v3.6.0-windows-portable.zip`：
1. **图形界面**：双击 `万能下载器.exe`，粘贴链接即可开始下载；
2. **可选剪贴板后台守护**：需要复制即入队时再运行项目根目录的 `XHS-Clipboard-Collector.vbs`；
3. 通用平台组件与本地解析引擎已经随包完整提供，电脑端采集抖音需要系统已安装 Microsoft Edge（不会读取 Edge 的个人资料或登录态）。

直接运行源码时，先设置 `MATERIAL_HUB_CONFIG` 指向本机的 `config.json`；正式自启入口通过 `XHS-Clipboard-Collector.vbs` 设置该变量。配置、素材、队列和日志不进入 Git。

在 PowerShell 中运行：

```powershell
cd D:\AICode\工具开发\projects\xhs-dl
.\setup-v2.ps1
python -m pip install -e .
```

安装器会把引擎放在 `D:\AICode\工具开发\projects\XHS_Downloader`，并为它单独准备 Python 3.12 环境，不影响系统 Python。

## 直接使用

双击 `启动无水印版.bat`，也可以从命令行运行：

```powershell
# 单条或整段分享文本
xhs-dl "http://xhslink.com/o/70dt8TsFJon"
xhs-dl "https://v.douyin.com/VFppn9c-lds/"

# 一段文本里混合多个平台链接，程序自动提取、识别和分流
xhs-dl "小红书 http://xhslink.cn/o/97Pz4siAYx4；抖音 https://v.douyin.com/example/；X https://x.com/example/status/123"

# 多条链接或文件，指定保存目录
xhs-dl -f links.txt -o D:\Download\小红书 --mode slow

# 明确指定本地引擎
xhs-dl "链接" --engine-home D:\AICode\工具开发\projects\XHS_Downloader

# 仅在确实需要旧版网页解析时使用（可能有水印）
xhs-dl "链接" --engine v1
```

桌面版默认自动判断：1 条直接采集，2–20 条随机等待 35–55 秒，21–50 条 55–85 秒，超过 50 条 110–160 秒；设置中可以手动覆盖。命令行可选 `fast`、`normal`、`cautious`、`slow`、`very-slow`。

## 桌面界面

桌面版提供独立窗口、设置按钮、系统文件夹选择、实时进度和更新检测。默认保存到 `C:\Users\你的用户名\Downloads`，设置会在本机记住。

旧 Web 界面仍可使用：

```powershell
xhs-dl-web
```

浏览器会打开 `http://127.0.0.1:5678`。Web 版同样使用 V2 本地无水印引擎，并提供实时进度、结果清单与持久化视觉主题。默认保存到 `C:\Users\你的用户名\Downloads`。

## Android 应用

Android V1.3.2 显示名为“万能下载器”，当前仍只支持小红书和抖音。可以手动粘贴或通过系统分享进入；新安装默认保存到 `Download/万能下载器`，升级用户会保留此前自选目录。

安卓端与电脑端使用同名的“拟态悬浮 / 克制玻璃”双主题，并记住主题、下载子目录、自动频率和更新检测设置。Android 10 及以上使用系统 MediaStore 保存，不需要索取全部文件权限。

## iPhone 应用

`ios/` 提供“万能下载器”iOS V0.3.2 客户端，当前仍只支持小红书和抖音，发布目标兼容 iOS 12 / iPhone 6。默认保存到“文件”App 可见的 `万能下载器` 目录，也可以改到用户授权的“我的 iPhone”或 iCloud Drive 文件夹。

iPhone 版与另外两端相互独立，不上传下载历史。仓库使用 GitHub macOS 构建机做无签名模拟器编译；安装到真机仍需用户自己的 Apple 开发签名，详见 `ios/README.md`。

## 本地输出

```text
xhs_downloads/
└── 评128-赞3560-标题-作者/
    ├── 封面-标题.jpg
    ├── 内页1-标题.jpg
    └── 文案.txt
```

所有成功历史集中保存在 `%LOCALAPPDATA%\xhs-dl\history.json`。源码运行要求 Python 3.9 及以上；Windows 便携版无需自行配置 Python。

历史 JSON 只记录下载网址、笔记 ID、标题等索引字段；作品目录不保存单帖 JSON。下载目录、历史数据库和设置均为本地文件，不会自动上传到云端。

模板配置保存在 `templates/local-cli.json`。可用环境变量 `XHS_DOWNLOADER_HOME` 覆盖引擎位置。

## 使用边界

仅下载你有权访问和保存的公开内容；请尊重创作者版权、平台规则与隐私。链接解析受平台接口和风控变化影响，失败时可降低频率或更新本地引擎。

详细说明见 `使用手册.md` 与 `安全与注意事项.md`。正式 AI/OpenClaw Skill 位于 `skills/universal-downloader`；`skills/xhs-download` 仅保留旧调用兼容。

## AI / OpenClaw 调用

正式技能名是 `universal-downloader`。调用时可以直接把一段包含多个平台链接的文字交给 Skill；它会复用项目核心提取 URL、识别平台、按输入顺序下载并返回每条结果。旧名称 `xhs-download` 只做兼容转发，不是第二套实现。

```text
输入：一段分享文案或链接
输出：成功数、失败数、保存目录、标题和错误原因
```

Skill 不读取浏览器登录态，不保存 Cookie、Token 或密码；需要账号、验证码或私密权限的内容会按限制返回失败。

## 开发与验证

- Python：`pytest -q`（v3.6.0：56 passed 100%）
- 静态检查：`ruff check xhs_dl tests`、`python -m compileall -q xhs_dl tests`
- Android：`assembleRelease`、`lintVitalRelease`、APK v2 签名检查通过
- Windows：v3.6.0 便携版打包 ZIP 构建完毕，剪贴板后台极速守护端到端验收通过

完整开发交接见 `开发手册.md`，产品使用见 `使用手册.md`，发布说明见 [docs/RELEASE-NOTES-3.6.0.md](docs/RELEASE-NOTES-3.6.0.md)，版本变化见 `CHANGELOG.md`。

## License

本适配项目为 MIT；独立下载引擎为 GPL-3.0，以其仓库许可证为准。

---

## 📝 变更记录

| 日期 (时间) | 执行者 | 记录 |
|---|---|---|
| 2026-10-01 09:30 | 反重力 | 全面升级发布 v3.6.0 官方稳定版：实装极速无感剪贴板守护、待下载防风控队列、双平台解析与原生硬链接归档 |
| 2026-09-17 23:11 | 💻 本地 PC / 反重力 | 初始化创建文档并补齐变更记录历史 |
