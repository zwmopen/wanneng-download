# 万能下载器本机 API

原版可视化界面和 API 共用一个服务：`http://127.0.0.1:5678`。同一台电脑上的 AI、脚本、桌面程序和本机网页都可以发 HTTP/JSON 请求；浏览器跨端口调用支持 `localhost` 和 `127.0.0.1` 来源。服务只监听回环地址。

接口规范可直接读取 `GET /api/openapi.json`。稳定接口使用 `/api/v1`；已有程序也可以继续使用不带版本号的 `/api` 路径。

## 主页和关键词入口

5678 页面侧栏的“主页采集”和“关键词采集”使用本机江湖工具箱发现抖音公开图文链接，再把发现的链接提交到同一个万能下载器任务队列。因此保存目录、节奏、图片格式、成功去重和历史都沿用下载器设置。调用前需确认江湖工具箱原生核心在线且当前为抖音；遇到登录或验证时会返回状态，不会自动绕过。主页发现复用工具箱 `extract-author`：导航指定作者主页、只读取公开 `/note/` 链接，遇到验证码或空页面会明确结束，不伪报成功。

桥接目录优先取服务环境变量 `JIANGHU_BRIDGE_DIR`。未设置时，Windows 本机会读取 `%USERPROFILE%\.codex\config.toml` 中 `[mcp_servers.jianghu_toolbox.env]` 的同名值，使下载器心跳门禁和江湖 CLI 共用 MCP 配置的运行目录；没有此配置时才回退到 `D:\Program Files\江湖工具箱\MinApp`。

江湖 CLI 默认使用工具箱 `.venv-agent\Scripts\python.exe`，可用服务环境变量 `JIANGHU_PYTHON` 覆盖；若工具箱环境不存在，则使用下载器当前 Python 环境。

剪贴板后台仍是单链接入口：每次复制只采一条链接。它和主页、关键词、手动下载最终都使用万能下载器成功账本去重。

```powershell
$body = @{
  profile_url = 'https://www.douyin.com/user/example'
  output_dir = "$env:USERPROFILE\Downloads"
  mode = 'auto'
  image_format = 'keep'
} | ConvertTo-Json -Depth 4

$task = Invoke-RestMethod `
  -Uri 'http://127.0.0.1:5678/api/v1/collections/homepage' `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Headers @{ 'Idempotency-Key' = 'homepage-run-001' } `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))

Invoke-RestMethod "http://127.0.0.1:5678/api/v1/collections/jobs/$($task.job_id)"
```

关键词请求为 `POST /api/v1/collections/keyword`，字段为 `keyword`、`count`（1–30）、`min_images`、`max_images`，并可传相同的 `output_dir`、`mode` 和 `image_format`。小红书主页采集未接入此 API；小红书关键词仍需要其原生核心，不会用抖音路径替代。

## 提交任务

请求可以传链接数组，也可以传整段复制的分享文本。省略格式和节奏时，格式保持来源原样，节奏使用自适应策略。

```powershell
$body = @{
  urls = @('https://xhslink.cn/o/example')
  image_format = 'keep'
  mode = 'auto'
} | ConvertTo-Json -Depth 4

$job = Invoke-RestMethod `
  -Uri 'http://127.0.0.1:5678/api/v1/jobs' `
  -Method Post `
  -ContentType 'application/json; charset=utf-8' `
  -Headers @{ 'Idempotency-Key' = 'my-app-request-001' } `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))

$job
```

接口返回 `202 Accepted`、`job_id` 和 `Location`。按 `Retry-After` 指定的间隔轮询任务：

```powershell
Invoke-RestMethod "http://127.0.0.1:5678/api/v1/jobs/$($job.job_id)"
```

相同 `Idempotency-Key` 在本地服务进程内 24 小时有效：同一请求会返回原任务，不同请求内容复用同一键会返回 `409`。不传幂等键也可以正常提交。

## 查询和能力

- `GET /api/v1/jobs?limit=50&history_offset=0`：返回等待任务、进行中任务、剪贴板队列、下载成功历史和计数；历史记录可用 `history_offset` 分页，`history_has_more` 表示是否还有更早记录。
- `POST /api/v1/collector`：用 `{"enabled": false}` 暂停、`{"enabled": true}` 恢复剪贴板守护进程；如果原进程已退出，会启动同一个入口（仍受单实例互斥保护）。运行中的单条下载会完成后暂停，队列保留；响应 `starting` 表示正在启动。
- `GET /api/v1/collections/capabilities`：读取主页/关键词面板能力、江湖工具箱心跳和当前平台。
- `POST /api/v1/collections/homepage`、`POST /api/v1/collections/keyword`：发现抖音链接并送入通用下载队列；`GET /api/v1/collections/jobs/{job_id}`：回读发现阶段和关联下载状态。
- `GET /api/v1/jobs/{job_id}`：读取单个任务进度；重启服务后仍可读到已归档的网页任务摘要。
- `GET /api/v1/capabilities`：读取支持的平台、格式、默认节奏和接口列表。
- `GET /api/v1/health`：检查 API 是否在线。
- `GET /api/openapi.json`：机器可读的 OpenAPI 3.1 接口定义。

`GET /api/v1/jobs` 的 `counts.download_history` 是本机真实下载历史总数；`history` 按 `history_offset` 分页返回共享历史，含 `save_dir` 最终保存目录。旧记录若无法唯一匹配素材库路径，`save_dir` 为空。`collector` 单独报告剪贴板采集器心跳、开关状态、等待数、冷却状态和失败归档数。过期心跳不会作为在线显示。任务结果的 `skipped` 和条目级 `deduplicated` 标记用于报告共用账本命中的重复项。

网页、命令行、桌面版、API 和剪贴板采集共用本机成功下载账本（`%LOCALAPPDATA%/xhs-dl/history.json`）。只有确认成功落盘的项目进入账本；再从任一入口提交相同作品时会显示为“已存在 · 跳过”，不重复下载。进行中的同一链接也会跨进程互斥，避免剪贴板与手动/API任务同时下载。剪贴板旧成功记录会在采集器启动时并入共用账本；失败项和仅登记的链接不会被当作已下载。新剪贴板采集记录会在整理完成后写入素材库最终目录。

## 调速与重试

`mode: "auto"` 为默认值。任务按顺序运行；成功后采用 8–15 秒间隔，识别到明确的临时网络错误或限流错误时最多额外重试一次，并逐步延长等待。错误文本包含 `Retry-After` 时优先采用服务器给出的等待值，最长 15 分钟。需要登录、验证码、404、失效链接和不支持来源不会自动重试。

剪贴板采集器与 API 任务继续串行处理各自队列。剪贴板队列的网络错误用短指数退避，限流错误用更长退避；同一条暂时失败会移到队尾，不会卡住后续链接。

这个 API 供本机应用调用，不接收账号 Cookie，也不会读取浏览器登录态。要从另一台设备调用，需另行设计带身份验证的远程入口；不要把本机端口直接暴露到公网。
