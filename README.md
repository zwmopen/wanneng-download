# 万能下载器 / 万能采集器（Universal Collector & Downloader）

一款**本地优先、开箱即用、全面开放**的多平台内容采集与无水印素材下载工作台，面向个人创作者、运营团队与 AI 自动化工作流：**小红书 / 抖音内置持久化浏览器采集 · 公开媒体无水印直解 · 剪贴板后台无感入队 · 智能月份硬链接归档 · 飞书开放通知 · AI HTTP / OpenAPI 联动**。

当前正式版本：**v4.2.0** · [发布说明](docs/RELEASE-NOTES-4.1.0.md) · [版本历史](CHANGELOG.md) · [使用手册](使用手册.md) · [源码仓库](https://github.com/zwmopen/wanneng-download)

> 💡 **本地闭环原则**：所有解析、下载、查重账本、历史记录、浏览器会话与元数据 100% 保留在用户自己电脑的本机目录中（默认 `~/.xhs-dl/` 与 `Downloads/`），不经过第三方在线解析站，不上传任何账号隐私。

---

## ✨ v4.2.0 核心亮点总览

1. **抖音免 Cookie 原画极速前置通道 + 8 大国内与 AI 视频平台直解**
   - 抖音单作品优先走免 Cookie 移动端详情接口 + 302 原画直链秒解（视频原画、图集原图、实况 LivePhoto），失败自动无缝降级内置 Edge 浏览器兜底（`douyin-fast-api -> douyin-edge`）。
   - 新增支持 **快手、微博视频、今日头条、豆包 AI 视频、即梦 AI 视频、皮皮虾、皮皮搞笑、最右** 无水印解析下载与统一文案归档。
2. **桌面壳白屏根治 + 全屏自适应大屏布局 + 冗余瘦身**
   - 修复 WebView2 初始化加载 `about:blank` 过早隐藏启动提示导致的白屏问题；加入重试按钮，同步监控 `core/*.py` 热更新。
   - 取消表格矮高度写死，大屏全屏自动撑满；左侧导航固定收口「打开作品保存目录」，移除单作品多余平台按钮与全站重复按钮；全面解锁 **小红书作者主页采集**。
   - 修复实时排队区显示 32 位十六进制 `job_id` 乱码问题，默认折叠排队抽屉；作品列表拆清「来源」与「关键词 / 采集方式」，区分 `0` 与缺失字段。

## ✨ v4.1.0 核心亮点总览

1. **全新桌面工作台（WebView2 独立桌面窗口 + `http://127.0.0.1:5678`）**
   - 自带独立无地址栏桌面壳 [`desktop_shell/万能采集器.exe`](desktop_shell/UniversalCollectorShell.cs)，启动自动检测代码版本更新并热重启本地后端。
   - 右上角主题按钮支持 **直接点击循环切换 5 种核心模式**：**自动切换**（可在设置中自定义北京时间昼夜起止时间与轮换/固定质感）→ **浅色拟态** → **深色拟态** → **浅色玻璃** → **深色玻璃**。
2. **Patchright 反检测底座 + 真实接口直听（自动适配 `Edge → Chrome → Chromium`）**
   - 彻底摆脱外部闭源 `.exe` 依赖，内置持久化浏览器内核（[`xhs_dl/web/native_collector.py`](xhs_dl/web/native_collector.py)）优先采用 **`Patchright`** 消除底层 CDP 自动化泄漏特征（Playwright 自动兜底），配合拟人化鼠标滚轮与随机停顿节流。
   - 抖音与小红书采用 **`page.on("response")` 真实网络 JSON 响应监听为主 + DOM 兜底**，抗前端改版；支持 **多账号浏览器档案一键新建/切换/删除** 与 **双平台规则健康自检**。
   - **可随时在任务栏展开观看**：采集启动后正规最小化至 Windows 任务栏，支持点击任务栏图标或点击界面居中打开；遇到滑块/扫码风控时**自动居中置顶弹出**，验证完成后点「已完成验证，继续采集」即可断点续跑。
3. **6 大清晰侧栏入口，全站支持高自由度 DIY**
   - **单作品采集**：粘贴小红书、抖音、B站或 12+ 公开平台链接，智能去噪提取并下载；遇到需登录或风控页面自动切换内置浏览器兜底提取。
   - **关键词采集**：发起卡片置顶，支持分组 **新建（含空分组）/ 改名 / 仅删组 / 删组含词**、**单条行内编辑**、**作品类型筛选（仅图文[默认] / 仅视频 / 全部）**、**抖音排序与发布时间筛选**，以及小红书多图/实况自动详情补全与直下。
   - **主页采集**：同时支持 **抖音（`/user/...`）与小红书（`/user/profile/...`）作者主页** 批量提取，支持分组管理与单条编辑。
   - **作品列表（统一历史与实时队列中心）**：把「当前采集结果」「历史采集档案」「剪贴板后台抓取」「AI 任务」汇总到同一张 12 列表格；区分 **发布时间** 与 **读取时间**，支持多维筛选、一键重置筛选、直跳原链、CSV 导出与 LivePhoto 实况保存。
   - **平台登录**：统一管理抖音 / 小红书登录态、**多账号隔离浏览器档案** 与 **反检测内核/规则自检看板**。
   - **下载与软件设置**：支持原生目录选择器、规则 `config.json` 直开编辑、**命名模板可点击拼接占位符与实时预览**、可选代理地址与北京时间主题规则、`metadata.json` 开关、可折叠飞书通知（Webhook / OpenAPI）以及 **AI Agent 一整段一键接入提示词**。
4. **开放通用型飞书通知（人人可用，无需依赖私人脚本）**
   - 在 **下载与软件设置 → 窗口、通知与飞书提醒** 内置纯 HTTP 飞书推送引擎（[`xhs_dl/web/notifier.py`](xhs_dl/web/notifier.py)），支持两种开箱方式（均收在可折叠配置面板中）：
     - **个人推荐（免建应用）**：在飞书群添加「自定义机器人」，贴入 Webhook 地址即可收到验证码提醒与完成通知；
     - **团队自建应用**：填入机器人 `App ID`、`App Secret（密钥）` 以及 `群名称或群 ID（oc_xxx）` 即可通过飞书开放平台 OpenAPI 直发。

---

## 🚀 快速开始

### 环境要求

- **操作系统**：Windows 10 / 11（推荐使用内置桌面壳，亦支持标准浏览器访问 `http://127.0.0.1:5678`）
- **Python**：3.9 及以上（推荐 Python 3.11+）
- **浏览器**：本机任意 **Microsoft Edge** 或 **Google Chrome**；若均未安装，可执行 `playwright install chromium` 使用内置 Chromium。

### 1. 克隆并安装依赖

```powershell
git clone https://github.com/zwmopen/wanneng-download.git
cd wanneng-download
pip install -e ".[stealth]"
```

> 若暂不安装 `patchright` 反检测扩展，也可直接 `pip install -e .` 使用标准 Playwright 内核；如需内置 Chromium 兜底：
> ```powershell
> python -m patchright install chromium
> ```

### 2. 一键启动

任选以下任意一种方式启动：

- **方式 A（推荐，桌面独立窗口）**：双击根目录 [`启动万能采集器.cmd`](启动万能采集器.cmd) 或直接双击 [`desktop_shell/万能采集器.exe`](desktop_shell/万能采集器.exe)
- **方式 B（命令行启动 Web 工作台）**：
  ```powershell
  python -m xhs_dl.web.app
  # 或已安装 console script 后直接运行：
  xhs-dl-web
  ```
- **方式 C（纯 CLI 命令行单条/批量下载）**：
  ```powershell
  xhs-dl "https://v.douyin.com/example/"
  xhs-dl "http://xhslink.com/o/example" -o D:\Downloads\素材
  xhs-dl -f links.txt --mode slow
  ```

### 3. 可选高级配置（本地规则入库与默认飞书模板）

仓库提供脱敏模板 [`config.example.json`](config.example.json)。如果你需要启用自动按城市/季节/月份（`01月~12月` 平铺硬链接）与主题合集归档、广告过滤规则，可复制为 `config/config.json`（已被 `.gitignore` 忽略，绝不误传密钥到 Git）：

```powershell
mkdir config -Force
copy config.example.json config\config.json
```

---

## 🧩 6 大工作台功能详述

| 入口 | 核心能力 | 关键交互与亮点 |
|---|---|---|
| **单作品采集** | 小红书 / 抖音 / B站 / X / YouTube 等公开链接直解下载 | 自动识别多行混排分享文案；遇到防盗链或需登录自动调用内置浏览器兜底提取 |
| **关键词采集** | 抖音 / 小红书关键词搜索发现、词表分组管理 | 发起卡片置顶；分组完整增删改与单条编辑；`仅图文(默认)/仅视频/全部` 下拉；接口 JSON 直听抗改版；小红书多图/实况详情补全 |
| **主页采集** | **抖音 & 小红书** 博主主页批量提取、作者档案分组 | 支持抖音 `/user/...` 与小红书 `/user/profile/...` 自动识别分流、分组完整管理、单条行内编辑与图数范围过滤 |
| **作品列表** | **当前采集列表** + **历史采集列表**（统一视图） | 合并手工/关键词/主页 + 剪贴板抓取 + AI 任务；独立记录`发布时间`与`读取时间`；支持筛选重置、清空勾选、原链直跳与导出 CSV |
| **平台登录** | 持久化浏览器会话、**多账号档案与规则自检** | 自动识别 Edge / Chrome / Chromium（Patchright 反检测内核）；支持多账号隔离档案一键新建/切换/删除与规则健康诊断 |
| **下载与软件设置** | 路径/去重/元数据 · 格式/命名 · 窗口/飞书通知 · **AI 接入** | 原生目录选框、`config.json` 直开、占位符可点命名预览、代理与昼夜主题自定义、可折叠飞书通知及一段式 AI Agent 总提示词 |

---

## 🤖 给其他 AI / 脚本的本地接入说明

服务默认只监听本机回环地址 **`http://127.0.0.1:5678`**（不对外网暴露、无需额外 Token）。在桌面端「下载与软件设置 → AI 接入」中可直接一键复制给任意 AI Agent 的完整接入提示词：

| 方法与路径 | 说明 |
|---|---|
| `GET /api/v1/health` | 健康检查（返回运行状态、`version`、`pid` 与 `code_stamp`） |
| `GET /api/openapi.json` | 完整 OpenAPI 3.1 接口规范文档 |
| `POST /api/v1/jobs` | 提交单条或多条分享文本/链接异步下载 |
| `POST /api/v1/collections/keyword` | 发起关键词采集（支持 `keyword`, `platform`, `count`, `media_type`, `web_sort`, `web_publish_time`, `direct_download`） |
| `POST /api/v1/collections/homepage` | 发起抖音或小红书作者主页采集 |
| `GET /api/v1/collections/jobs/<job_id>` | 轮询采集与关联下载实时进度 |
| `GET /api/v1/workbench/artworks?mode=history&sort_by=collected_at&sort_dir=desc` | 按读取时间倒序查询所有历史记录（含剪贴板与 AI 任务） |

---

## 📱 全端生态矩阵

| 端 | 目录 / 版本 | 能力范围 | 说明 |
|---|---|---|---|
| **Windows 桌面 & Web & CLI** | **v4.2.0** | Patchright 反检测、抖音免 Cookie 原画秒解、8 大国内/AI 视频平台、双平台接口直听、小红书实况与主页、12+ 公开平台、剪贴板守护、硬链接归档、飞书通知、AI API | 正式可用 |
| **Android** | `android/` (V1.4.0) | 小红书、抖音原画秒解、快手/微博/头条/豆包/即梦等 8 大平台 + Cloudflare Workers 云端兜底/403 转发 | 可用源码 & Release APK |
| **iOS** | `ios/` (V0.4.0) | 小红书、抖音原画秒解、8 大国内/AI 平台 + Cloudflare Workers 云端兜底/403 转发、兼容 iOS 12+ | 未签名源码（含 GitHub macOS CI 配置） |
| **Cloudflare Workers** | `cloudflare_workers/` | 抖音免 Cookie 云端解析（`wanneng-douyin-api`）+ 403 防盗链流式转发（`wanneng-media-proxy`），一键 `deploy.cmd` 部署 | 手机端/公网免费兜底 |
| **AI Skill** | `skills/universal-downloader` | 供 Codex / Claude / Antigravity / OpenClaw 自动调用的标准化技能包 | 正式可用 |

---

## 🛡️ 工程测试与质量保障

项目配备完整自动化测试套件（包含链接解析、媒体自然排序与格式转换、双平台分流、去重与硬链接入库、分组 CRUD 与单条 DIY 编辑、Patchright 驱动与双平台接口 JSON 解析、小红书 LivePhoto 实况保存、多账号档案与规则自检、飞书通知等）：

```powershell
python -m pytest -v
# v4.1.0 实测：85 passed
```

---

## ⚖️ 使用边界与开源协议

- **合法合规使用**：仅用于下载、整理你有权访问和保存的公开内容，请尊重原作者版权与各平台服务条款。软件不会绕过付费墙或破解私密账号；遇到人机验证或登录要求时，会置顶弹出可见浏览器窗口由人工亲自完成确认。
- **开源协议**：本项目主适配与工作台代码采用 **MIT License**；可选独立底层 CLI 引擎遵循其原仓库 GPL-3.0 协议，两者进程边界清晰隔离。
