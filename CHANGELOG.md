# 变更记录

## 4.2.0 抖音原画秒解 · 8 大国内/AI 视频平台 · 小红书主页解锁 · 白屏修复与全屏重构 — 2026-11-26

- **抖音免 Cookie 原画极速通道（`douyin_downloader.py`）**：
  - 吸收 `api.amemv.com` + `aweme.snssdk.com` 302 原画解析能力作为前置极速通道（视频/图集/实况 LivePhoto），遇风控或接口异常自动降级内置 Edge 浏览器兜底。
- **8 大国内与 AI 视频平台直解（`cn_short_video_downloader.py`, `platforms.py`, `unified_downloader.py`）**：
  - 新增支持快手、微博视频、今日头条、豆包 AI 视频、即梦 AI 视频、皮皮虾、皮皮搞笑、最右，统一落盘格式、文案输出与历史去重。
- **桌面壳白屏修复（`desktop_shell/UniversalCollectorShell.cs`, `app.py`）**：
  - 过滤 `about:blank` 预加载触发的 `NavigationCompleted`，仅在真正加载 `http://127.0.0.1:5678/` 成功后再隐藏启动遮罩，失败时提供清晰提示与重试按钮；`code_stamp` 同步覆盖 `xhs_dl/core/*.py`。
- **手机端同步升级（Android V1.4.0 · iOS V0.4.0）与 Cloudflare Workers 云端兜底（`cloudflare_workers/`）**：
  - Android & iOS 同步接入抖音免 Cookie 原画秒解（三层链路：本地直解 → Cloudflare Worker 兜底 → 内置 WebView 兜底）、8 大国内与 AI 视频平台解析、403 防盗链 Worker 自动转发重试及设置页可配置入口。
  - 新增 `cloudflare_workers/`（`wanneng-douyin-api` + 带域白名单的 `wanneng-media-proxy`）及 `deploy.cmd` 一键部署脚本；桌面端同步支持 `CF_SV_PROXY_URL` 403 自动转发兜底。
- **界面重构与减法瘦身（`ui_template.py`, `toolbox_store.py`）**：
  - 全屏自适应布局吃满视口高度；左侧导航底部收敛唯一「打开作品保存目录」入口；单作品页移除多余平台切换按钮，展示全部支持平台徽章并支持整段带废话分享文本自动提取。
  - 解锁主页采集的 **小红书** 平台入口；排队抽屉默认折叠且全面替换为可读中文任务标题，消灭 32 位哈希乱码；作品列表拆清「来源」列与「关键词 / 采集方式」列，默认隐藏纯调度空壳行并严谨区分 `0` 与未返回字段。

## [Unreleased] 作品历史元数据与 AI 任务状态准确性 — 2026-11-27

- Workbench reads author, interaction counts, image count, media type and canonical note ID from an existing local `metadata.json`; missing values stay blank, and publish time is never replaced with collection time.
- Duplicate share URLs for the same canonical note ID collapse to one history row.
- Clipboard pending/failure records now join the artwork history, with staging folder names and files supplying only verifiable author, like/comment counts and image counts; incomplete assets and rule blocks get explicit status labels.
- AI task rows distinguish partial failures and unknown outcomes from active work instead of labeling every unrecognized state as “进行中”.

## 4.1.0 反检测内核与接口直听升级 · 小红书实况/主页 · 多账号档案 · 全站 DIY — 2026-11-26

- **反检测浏览器底座升级（`native_collector.py`, `pyproject.toml`）**：
  - 支持优先使用 `Patchright` 驱动本机 Edge / Chrome / Chromium（`[project.optional-dependencies] stealth`），底层消除 `Runtime.enable` 等 CDP 自动化泄漏特征，保留 Playwright 自动兜底。
  - 将机械的瞬间触底滚动升级为 `_human_scroll_page` 拟人化鼠标移动 + 多段随机滚轮滑动 + 随机停顿节流，降低触发滑块风控概率。
- **真实网络 JSON 响应监听与小红书全链路打通（`native_collector.py`, `toolbox_store.py`, `app.py`）**：
  - 抖音关键词与作者主页接入 `page.on("response")` 真实接口 JSON 监听（`/aweme/v1/web/...`）为主、DOM 扒取为兜底，无水印原图与统计参数直取，抗前端改版能力大幅增强。
  - 小红书升级支持接口直听（`/api/sns/web/v1/search/notes`、`/api/sns/web/v1/feed`、`/api/sns/web/v1/user_posted`）与 `__INITIAL_STATE__` 兜底，**完整透传 `xsec_token`**、自动读取笔记详情全套高清多图与 **LivePhoto 实况视频（`实况1.mp4`…）** 并写入 `metadata.json`（自动匹配 `xhscdn` Referer）。
  - 正式上线 **小红书作者主页批量采集**（支持 `/user/profile/...`，能力声明 `xiaohongshu_homepage: true`）。
- **多账号浏览器档案与规则健康自检（`native_collector.py`, `toolbox_store.py`, `ui_template.py`）**：
  - 「平台登录」新增 **多账号浏览器档案**（新建 / 切换 / 删除独立隔离会话目录，保留默认主账号 Cookie）与 **反检测内核 / 双平台规则自检看板**，区分正常捕获、DOM 兜底、人机验证拦截与疑似改版告警。
- **全站 DIY 与交互精简（`toolbox_store.py`, `ui_template.py`）**：
  - 关键词与作者主页新增 **分组完整 CRUD**（支持新建 0 条记录空分组、原地改名、`仅删组` 迁回默认分组、`删组含词` 二次确认级联删除）与 **单条行内编辑**（名称 / 网址 / 分组 / 备注）。
  - 作品列表补充 **清空勾选**、**重置筛选** 与每行 **原链** 跳转；设置面板补充原生目录选择器（`浏览选择…`）、`config.json` 直开编辑、命名模板占位符可点拼接 + 实时预览、代理地址与北京时间昼夜主题规则配置。
  - 移除顶部冗余「快速设置」弹窗，将右上角主题按钮改为 **直接点击循环切换 5 种模式**（`自动切换 / 浅色拟态 / 深色拟态 / 浅色玻璃 / 深色玻璃`）；「AI 接入」精简为一段可直接发给 AI Agent 的完整指令提示词。

## 4.0.0 统一智能采集工作台（内置多浏览器内核 · 统一历史记录 · 通用飞书 · AI 接入） — 2026-11-25

- **内置持久化浏览器内核（`native_collector.py`）**：
  - 彻底替代外部闭源 `.exe`，支持 `msedge -> chrome -> chromium` 自动探测与回落，默认启用系统沙盒。
  - 修复离屏坐标隐藏问题，改为正规任务栏最小化，支持随时从任务栏或前端「查看采集浏览器」唤出，并在触发验证码/登录时自动居中置顶与断点续采。
- **桌面外壳与热升级（`desktop_shell/UniversalCollectorShell.cs`）**：
  - 基于 WebView2 的独立桌面壳，启动时通过 `/api/v1/health` 的 `code_stamp` 自动检测更新并平滑重启旧后端进程；移除硬编码本机路径以便开源通用部署。
- **工作台交互与筛选重构（`ui_template.py`, `toolbox_store.py`, `app.py`）**：
  - 移除冗余右侧栏，将关键词/主页发起卡片置顶，默认进入关键词采集并记住上次标签页。
  - 顶部新增 7 模式主题下拉菜单（默认跟随北京时间昼夜自动切换，按日轮换拟态/玻璃质感），移除设置页重复主题区。
  - 关键词与主页新增 **重命名分组**（`op="rename_group"`）及皮肤化输入弹窗；修复「更多 ▾」下拉交互。
  - 关键词区接入真实 **作品类型筛选（`仅图文`/`仅视频`/`全部`）** 与抖音真实排序/发布时间透传；作品列表补充 **收藏量** 过滤与排序。
- **统一作品列表、元数据开关与 AI / 飞书开放化**：
  - 合并原「AI 与任务中心」进入「作品列表」，统一汇总当前采集、剪贴板、单作品、关键词、主页及 AI 任务，顶部内嵌可折叠实时排队抽屉。
  - 严格区分 **发布时间** 与新增的 **读取时间（`collected_at`）**，清晰展示 **`已读取未下载`** / **`已下载 N 张图`** / **`已入库·月份`** 状态。
  - 支持在设置中独立开关 **`metadata.json` 元数据自动生成与更新**；新增可折叠飞书机器人配置（兼容群自定义 Webhook 免建应用、OpenAPI App ID/Secret 与本地配置）；新增设置 **「AI 接入」** 子页，内置一键复制 AI 提示词与 HTTP API 示例。
  - 新增脱敏配置模板 `config.example.json` 并重写 `README.md`、`使用手册.md` 与 `docs/RELEASE-NOTES-4.0.0.md`。

## [Unreleased collector pause safety] - 2026-11-18

- The manual clipboard restart script and downloader UI now refuse to clear the exact `codex-migration-gate` pause marker; both fail closed if the marker cannot be read. Ordinary pause markers retain the existing recovery flow.

## [Unreleased downloader collection workspace] - 2026-11-15

- Added sidebar tabs for single-work downloading, Douyin homepage discovery, and Douyin keyword discovery in the existing 5678 UI.
- Homepage and keyword results enter the same downloader queue, preserving local deduplication, saved output settings, original media formats, and shared download history.
- Kept the clipboard collector as a separate single-link background entry and documented the supported platform and verification limits.
- Added local collection capability/status APIs and collection task polling on the existing port; no additional UI port is introduced.

## [Unreleased template gallery bridge port] - 2026-11-14

- Moved the optional collector bridge default from port 8765 to 8766 because 8765 is reserved by the Jianghu conversion assistant.
- Kept the bridge loopback-only; the template gallery can start and health-check it without replacing the conversion service.

## [Unreleased Universal collector recovery] - 2026-11-13

- Short-link extraction failures now remain retryable queue work instead of being classified as terminal unsupported content.
- Added a team-building topic keep rule so generic travel and family keywords do not discard relevant `胡闹厨房` and team-building posts.
- Raised the local collector image cap to 30 for the current configured workspace.
- Routed Task Scheduler, HKCU Run, and Startup shortcut through the repository launcher; the local config remains outside Git.
- Restored the eight previously failed links from this batch and queued the additional Hangzhou link. The collector remains paused because XHS resolves to a login page and its local downloader cookie is unset.
- Douyin's Playwright Edge session now receives the existing process HTTP(S) proxy when no Jianghu-scoped proxy is provided; direct navigation was closing the connection.

## [Unreleased Jianghu child proxy] - 2026-11-13

- When launched as a Jianghu child with `JIANGHU_PROXY_URL`, the Douyin Edge session now uses that process-scoped proxy explicitly; standalone downloader behavior is unchanged when the variable is absent.
- The adapter passes the same proxy to HTTP media requests through child-only `HTTP_PROXY`/`HTTPS_PROXY` variables; Windows system proxy settings are not modified.

## [Unreleased collector bridge] - 2026-11-13

- Added `collector_bridge_api.py`, a localhost-only bridge for other AI clients to submit public links, poll correlated jobs, and read only media files verified on disk.
- Added capability/status envelopes and explicit `accepted`/`queued`/`running`/`completed`/`partial`/`blocked`/`failed` states; accepted work is never reported as parsed work.
- The bridge does not accept cookies or browser login state. XHS jobs remain truthfully blocked when the local public-link endpoint redirects to login; Douyin can use the existing separate public browser route when the pause marker is XHS-specific.
- Added a local visual console at `/` for submitting jobs, viewing queue/heartbeat status, polling recent tasks, and opening verified on-disk assets.
- The console now presents the product as “万能下载器 · 万能采集器”, keeps source image formats by default, makes the four status cards clickable, and wraps long pause messages without horizontal overflow.
- Queue detail URLs are now real links backed by a local queue-id redirect endpoint, so clicking a displayed URL opens the recorded source instead of doing nothing.
- Added an idempotent service launcher for the original downloader Web UI (`5678`) and the collector bridge console (`8766`); the dashboard links directly to the original downloader page.

## 3.6.0 剪贴板极速无感守护、待下载防风控队列、双平台解析与原生硬链接归档 — 2026-10-01

- **剪贴板极速无感自动采集（Universal Clipboard Collector）**：
  - 新增后台静默监听守护进程，0.1s 极速侦测小红书（`xhslink.cn` / `xiaohongshu.com`）与抖音（`v.douyin.com`）分享链接；
  - 复制即入库，无需反复切换窗口；非媒体内容 100% 穿透放行，零剪贴板与内存污染。
- **待下载持久化队列与拟人防风控阶梯冷却**：
  - 连续复制多链接自动进 `clipboard_pending_queue.json` 磁盘队列，避免并发爆破平台；
  - 默认 8~15 秒随机拟人间隔；捕获平台限流自动进入阶梯冷却（60s/120s/180s），冷却结束自动无缝续跑。
- **城市智能地名分流与 NTFS 原生硬链接**：
  - 自动识别正文及标题内的流量城市（宁波/杭州/安吉/金华义乌/台州等），自动落盘至对应目录；
  - 同卷自动建立秋季/四季归档的 NTFS 原生硬链接，0 额外存储开销；跨驱动器自动降级保障 100% 留存。
- **系统托盘与轻量大盘通知**：
  - 任务栏右键菜单直接查看待下载排队、风控状态、打开素材根目录与日志；
  - 复制瞬间即刻给出桌面拟态感知卡片，彻底消除黑盒等待焦虑；支持飞书大盘纯文本低扰同步。
- **工程治理与基线打包**：
  - 跑通全部 56 项单元与回归测试（100% PASS）；
  - 统一 PyInstaller 便携化构建流水线，产出绿色免安装便携包。

## 2.8.2 - 2026-08-14

- 通用平台多图改用自然数字排序，统一“封面、内页1、内页2……”顺序，避免内页10提前于内页2。
- 抖音已有文件只有在确实是可用媒体（文件大于等于 200 字节）时才跳过；0 字节或残缺文件会自动重下。
- Android 媒体保存增加 HTML/JSON 响应拦截与最小体积校验，避免把错误页面伪装成视频或原图留在下载目录。
- 新增上述桌面、抖音和 Android 边界回归测试。

## 2.8.1 - 2026-08-14

- 修复通用平台分支忽略 JPG / PNG 设置的问题，X、B站、TikTok 等图片现在与桌面、手机保持一致。
- 修复共享 Skill 与桌面端 URL 提取规则不一致的问题，中文分享文案尾部标点不会再污染链接。
- 修复多图上游文件名按字符串排序导致“内页10”排在“内页2”前面的顺序问题。
- 新增上述边界回归测试，并完成真实小红书 `xhslink.cn`、抖音短链与 X 视频复测。

## 2.8.0 - 2026-08-13

- 正式产品名升级为“万能下载器”；Windows 窗口、Web、CLI、EXE、便携包和桌面入口统一使用新品牌。
- 正式共享 Skill 更名为 `universal-downloader`；旧 `xhs-download` 降级为无脚本兼容路由，避免历史自动化失效或形成第二套实现。
- Android 显示版本升至 1.3.2，iPhone 升至 0.3.2；保留既有 applicationId / Bundle ID 和用户设置，确保是原应用升级而非新装平行应用。
- 手机端界面明确说明当前只支持小红书与抖音；“万能”指统一产品与可扩展架构，不虚报三端平台能力相同。

## 2.7.0 - 2026-08-13

- 在原有小红书、抖音专用引擎之外新增本地 yt-dlp 适配层，首批路由 X/Twitter、B站、YouTube、TikTok、Instagram、Facebook、Pinterest、Reddit、Vimeo 与 Bluesky。
- 通用平台继续复用统一文件夹、媒体命名、`文案.txt` 与集中历史，不在作品目录生成 JSON。
- 打包内加入 yt-dlp 与 FFmpeg 运行组件，不读取浏览器 Cookie，不调用第三方在线解析网站。
- 真实匿名验证：X 视频与 B站视频下载成功且 MP4 头有效；YouTube 在当前网络要求机器人确认，按安全边界明确失败而不读取登录态。
- 共享 `xhs-download` Skill 保留兼容名称并升级成多平台自动路由入口。

## 2.6.2 - 2026-08-11

- 支持小红书新分享短链域名 `xhslink.cn`，Windows、Android 与 iPhone 路由保持一致。
- Windows 适配器将 `.cn` 短链规范化为上游兼容的 `.com` 等价入口，保留原始下载网址写入集中历史；不修改或复制第三方引擎源码。
- 修复 AI Skill 在 Windows GBK 控制台输出含 Emoji 的下载结果时触发 `UnicodeEncodeError`，现在稳定输出 UTF-8 JSON。
- 使用真实公开链接 `http://xhslink.cn/o/97Pz4siAYx4` 验证成功：15/15 张 JPG、完整 `文案.txt`、中文与 🍃 文件名，Skill 返回 `success 1 / failed 0`。

## 2.6.1 - 2026-08-10

- 修复 Windows 继承包含裸 IPv6 条目的 `NO_PROXY/no_proxy` 时，上游 `httpx 0.28` 把 `::1` 误解析为非法端口并导致所有小红书链接立即失败的问题。
- 子进程启动前只过滤 `httpx` 无法解析的裸 IPv6 代理绕过项，保留用户现有 HTTP/HTTPS 代理和普通域名/IP 绕过规则。
- 下载失败不再把内部 `__XHS_DL_METADATA__{}` 标记直接显示给用户，改为保留真正的上游错误或明确提示未解析到媒体。
- 新增代理环境与错误提示回归测试；使用真实公开小红书单图、多图、视频和 Emoji 标题笔记完成端到端验证。

## 2.6.0 - 2026-07-30

- 修复 Windows 后台下载异常回到界面时错误对象失效，导致提示失败、按钮可能停留在“采集中”的问题。
- 修复混合图片与视频时首张图片被错误命名为“内页”，以及多视频互相覆盖；三端统一按图片、视频各自独立编号。
- 修复 Android / iPhone 更新检测仍等待旧式独立标签，无法识别统一正式 Release 的问题；现在从正式发布资产名读取各端版本。
- 抖音媒体改为分块下载、临时文件校验和成功后原子落盘；拒绝把风控 HTML/JSON 错存为图片，降低大视频内存占用和半文件风险。
- Web 备用界面改用小红书/抖音统一路由，并增加 JPG、PNG、保持原格式选择和输入大小/设置类型校验。
- 本机设置读取增加类型与枚举校验，损坏或旧格式设置自动安全回退，不再导致桌面端启动崩溃。
- 补充项目自带 Gradle Wrapper，固定 Android 构建工具版本，提升换电脑和 CI 的可重复构建能力。
- 清理桌面 Python 静态检查问题，并把源码运行要求更正为 Python 3.9 及以上。

## 2.5.0 - 2026-07-29

- Windows、Android、iPhone 和共享 AI 技能统一加入抖音公开视频、图文作品下载。
- Windows 使用临时、未登录的系统 Edge 会话解析公开页面；真实三条抖音图文回归 3/3 成功。
- CLI 与便携 EXE 增加可供 AI 自动化调用的统一下载入口，支持小红书与抖音混合链接。
- Android 升级 1.2.0，iPhone 升级 0.2.0；两端均使用应用内网页环境，不共享系统浏览器登录态。
- 保持原有文件夹命名、`文案.txt` 和集中历史结构，不在每条作品目录放 JSON。
- 共享 `xhs-download` 技能移除普通下载中的 Cookie 读取路线，改为调用项目统一引擎。
- 产品名统一升级为“小红书抖音下载”，Bundle ID / Android applicationId 保持不变，避免覆盖其他应用。
- 增加图片格式设置：默认高质量 JPG，可选 PNG 或保持原格式；媒体按封面、内页、视频加标题命名。

## 2.4.0 - 2026-07-19

- 产品统一更名为“小红书抖音下载”，Windows、Android、iPhone 采用同一图标与拟态悬浮 / 克制玻璃视觉语言。
- 明确三端为独立客户端，不增加设备互联或云同步。
- Windows 设置页增加使用说明和手动更新检测，便携包增加正式图标并改为中文程序名。
- Android 升级到 1.1.0：增加完整设置与帮助页、系统自选下载目录、设计说明、使用说明和手动更新检测。
- Android 在 Redmi K60 真机完成自选目录授权和真实公开笔记下载，生成 6 张 PNG 与文案。
- 新增 iOS 0.1.0 SwiftUI 工程、自选 Files 目录、本机历史、双主题、说明和更新检测，并接入 GitHub macOS 模拟器编译验收。
- 下载目录继续只放媒体和 `文案.txt`；集中历史保留下载网址、笔记 ID 和标题。

## 2.3.1 - 2026-07-19

- Windows 桌面版恢复“拟态悬浮 / 克制玻璃”双主题切换与持久化。
- 修复高 DPI 或较小屏幕下设置页底部“保存设置”显示不完整。
- 新增项目开发手册、跨端视觉检查和 UI 回归记录。
- 新增原生 Android 1.0.0 应用工程，支持粘贴、分享、自动随机频率、本地保存、集中历史和更新检测。
- Android 使用媒体 token 请求原图 CDN，避免 H5 展示图中的平台账号水印；已在真实小米设备下载 6 张 PNG 与文案验证。

## 2.3.0 - 2026-07-19

- 发布 Windows 独立便携桌面版、剪贴板“粘贴并采集”、自动频率和更新检测。
- 下载目录只保留媒体与文案，历史 JSON 集中保存。

## 2.2.1 - 2026-07-19

- 简化主界面，把保存位置与速度收进设置。
- 默认保存到 Windows 下载文件夹，强化进度与完成过渡。

---

## 📝 变更记录

| 日期 (时间) | 执行者 | 记录 |
|---|---|---|
| 2026-09-17 23:11 | 💻 本地 PC / 反重力 | 初始化创建文档并补齐变更记录历史 |
