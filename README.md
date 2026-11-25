# 万能下载器 / 万能采集器（Universal Collector & Downloader）

一款**本地优先、开箱即用、全面开放**的多平台内容采集与无水印素材下载工作台，面向个人创作者、运营团队与 AI 自动化工作流：**小红书 / 抖音内置持久化浏览器采集 · 公开媒体无水印直解 · 剪贴板后台无感入队 · 智能月份硬链接归档 · 飞书开放通知 · AI HTTP / OpenAPI 联动**。

当前正式版本：**v4.0.0** · [发布说明](docs/RELEASE-NOTES-4.0.0.md) · [版本历史](CHANGELOG.md) · [使用手册](使用手册.md) · [源码仓库](https://github.com/zwmopen/wanneng-download)

> 💡 **本地闭环原则**：所有解析、下载、查重账本、历史记录、浏览器会话与元数据 100% 保留在用户自己电脑的本机目录中（默认 `~/.xhs-dl/` 与 `Downloads/`），不经过第三方在线解析站，不上传任何账号隐私。

---

## ✨ v4.0.0 核心亮点总览

1. **全新桌面工作台（WebView2 独立桌面窗口 + `http://127.0.0.1:5678`）**
   - 自带独立无地址栏桌面壳 [`desktop_shell/万能采集器.exe`](desktop_shell/UniversalCollectorShell.cs)，启动自动检测代码版本更新并热重启本地后端。
   - 右上角提供 **7 种视觉主题模式**：默认 **跟随北京时间昼夜自动切换（07:00–19:00 浅色 / 夜间深色，并按日轮换玻璃与拟态质感）**，也可手动固定为 **浅色（纯净）/ 深色（纯净）/ 浅色拟态 / 深色拟态 / 浅色玻璃 / 深色玻璃**。
2. **自主可控的多浏览器持久化采集内核（自动适配 `Edge → Chrome → Chromium`）**
   - 彻底摆脱外部闭源 `.exe` 依赖，由内置 Playwright 持久化会话内核（[`xhs_dl/web/native_collector.py`](xhs_dl/web/native_collector.py)）接管关键词、主页与风控兜底提取。
   - 自动探测本机环境：优先使用系统已安装的 **Microsoft Edge**；若用户电脑未安装 Edge，自动无缝切换 **Google Chrome**，或退回 **Playwright 内置 Chromium**。
   - **可随时在任务栏展开观看**：采集启动后正规最小化至 Windows 任务栏（不再隐藏在屏幕外），支持点击任务栏图标或点击界面 **「查看采集浏览器」** 居中打开；遇到滑块/扫码风控时**自动居中置顶弹出**，验证完成后点「已完成验证，继续采集」即可断点续跑。
3. **6 大清晰侧栏入口，流程符合直觉**
   - **单作品采集**：粘贴小红书、抖音、B站或 12+ 公开平台链接，智能去噪提取并下载；遇到需登录或风控页面自动切换内置浏览器兜底提取。
   - **关键词采集**：发起卡片置顶，支持多分组管理与 **「重命名分组」** DIY、**作品类型筛选（仅图文[默认] / 仅视频 / 全部）**、**抖音真实搜索排序（综合排序 / 最多点赞 / 最新发布）**、**发布时间筛选（不限 / 一天内 / 一周内 / 半年内）**、以及 **「提取直接下载」**（自动先采后下）或仅先入库再筛选下载。
   - **主页采集**：按分组管理对标作者库、支持分组重命名、一键提取抖音公开图文作品。
   - **作品列表（统一历史与实时队列中心）**：把「当前采集结果」「历史采集档案」「剪贴板后台抓取」「AI CLI/MCP 任务」全部汇总到同一张 12 列表格；清晰区分 **发布时间** 与 **读取时间**（默认按读取时间倒序排列），明确标注 **`已读取未下载` / `已下载 N 张图` / `已入库·01月~12月`**，支持点赞/收藏/评论/图片数多维筛选与 CSV 导出，可展开顶部「剪贴板与实时排队任务」。
   - **平台登录**：一键弹出抖音 / 小红书 / 通用浏览器登录窗口并永久保存本机登录态，支持一键收起到任务栏。
   - **下载与软件设置**：4 个清晰子分页——**路径、去重与自动入库**（含 `metadata.json` 元数据开关）、**格式、节奏与命名模板**、**窗口、通知与飞书提醒**、**AI 接入**（内置一键复制的 AI 提示词与 HTTP 接口示例）。
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
pip install -e .
```

> 如需内置 Chromium 兜底（当电脑既没有 Edge 也没有 Chrome 时）：
> ```powershell
> python -m playwright install chromium
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
| **关键词采集** | 抖音 / 小红书关键词搜索发现、词表分组管理 | 发起卡片置顶；`仅图文(默认)/仅视频/全部` 下拉；抖音排序/发布时间真实透传；分组可重命名；先采后下或提取直下自由切换 |
| **主页采集** | 抖音博主主页公开图文批量提取、作者档案分组 | 支持分组筛选、分组重命名、备注管理、每主页抓取条数与图数范围控制 |
| **作品列表** | **当前采集列表** + **历史采集列表**（统一视图） | 合并手工/关键词/主页 + 剪贴板抓取 + AI 任务；独立记录`发布时间`与`读取时间`；状态明确区分`已读取未下载`、`已下载 N 张图`、`已入库·月份`；可按点赞/收藏/评论/图数过滤与导出 CSV；顶部可展开剪贴板与实时排队 |
| **平台登录** | 持久化浏览器会话管理 | 自动识别 Edge / Chrome / Chromium；登录态永久保留在 `~/.xhs-dl/browser_profiles/collector`；支持一键拉起置顶 / 收起至任务栏 |
| **下载与软件设置** | 路径/去重/元数据 · 格式/命名 · 窗口/飞书通知 · **AI 接入** | 可开关自动写入 `metadata.json`；可折叠飞书 Webhook / App ID 配置；自带给 Codex / Antigravity / Claude 下指令的一键复制提示词与 `curl` 示例 |

---

## 🤖 给其他 AI / 脚本的本地接入说明

服务默认只监听本机回环地址 **`http://127.0.0.1:5678`**（不对外网暴露、无需额外 Token）。在桌面端「下载与软件设置 → AI 接入」中可直接复制现成提示词与接口地址：

| 方法与路径 | 说明 |
|---|---|
| `GET /api/v1/health` | 健康检查（返回运行状态、`version`、`pid` 与 `code_stamp`） |
| `GET /api/openapi.json` | 完整 OpenAPI 3.1 接口规范文档 |
| `POST /api/v1/jobs` | 提交单条或多条分享文本/链接异步下载 |
| `POST /api/v1/collections/keyword` | 发起关键词采集（支持 `keyword`, `platform`, `count`, `media_type`, `web_sort`, `web_publish_time`, `direct_download`） |
| `POST /api/v1/collections/homepage` | 发起抖音作者主页采集 |
| `GET /api/v1/collections/jobs/<job_id>` | 轮询采集与关联下载实时进度 |
| `GET /api/v1/workbench/artworks?mode=history&sort_by=collected_at&sort_dir=desc` | 按读取时间倒序查询所有历史记录（含剪贴板与 AI 任务） |

---

## 📱 全端生态矩阵

| 端 | 目录 / 版本 | 能力范围 | 说明 |
|---|---|---|---|
| **Windows 桌面 & Web & CLI** | **v4.0.0** | 抖音/小红书搜索与主页发现、12+ 公开平台下载、剪贴板后台守护、自动归档硬链接、飞书通知、AI HTTP API | 正式可用 |
| **Android** | `android/` (V1.3.2) | 小红书、抖音分享解析与公开下载、拟态/玻璃双主题 | 可用源码 & APK 构建配置 |
| **iOS** | `ios/` (V0.3.2) | 小红书、抖音公开下载、兼容 iOS 12+ / Files 目录 | 未签名源码（含 GitHub macOS CI 配置） |
| **AI Skill** | `skills/universal-downloader` | 供 Codex / Claude / Antigravity / OpenClaw 自动调用的标准化技能包 | 正式可用 |

---

## 🛡️ 工程测试与质量保障

项目配备完整自动化测试套件（包含链接解析、媒体自然排序与格式转换、双平台分流、去重与硬链接入库、关键词/作者分组重命名、收藏过滤、读取时间排序、飞书 Webhook/OpenAPI 推送及浏览器通道自动识别）：

```powershell
python -m pytest -v
# v4.0.0 实测：82 passed
```

---

## ⚖️ 使用边界与开源协议

- **合法合规使用**：仅用于下载、整理你有权访问和保存的公开内容，请尊重原作者版权与各平台服务条款。软件不会绕过付费墙或破解私密账号；遇到人机验证或登录要求时，会置顶弹出可见浏览器窗口由人工亲自完成确认。
- **开源协议**：本项目主适配与工作台代码采用 **MIT License**；可选独立底层 CLI 引擎遵循其原仓库 GPL-3.0 协议，两者进程边界清晰隔离。
