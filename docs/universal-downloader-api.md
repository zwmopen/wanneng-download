# 万能下载器本机 API

原版可视化界面和 API 共用一个服务：`http://127.0.0.1:5678`。同一台电脑上的 AI、脚本、桌面程序和本机网页都可以发 HTTP/JSON 请求；浏览器跨端口调用支持 `localhost` 和 `127.0.0.1` 来源。服务只监听回环地址。

接口规范可直接读取 `GET /api/openapi.json`。稳定接口使用 `/api/v1`；已有程序也可以继续使用不带版本号的 `/api` 路径。

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

- `GET /api/v1/jobs?limit=50`：返回等待任务、进行中任务、剪贴板队列、下载成功历史和计数。
- `POST /api/v1/collector`：用 `{"enabled": false}` 暂停、`{"enabled": true}` 恢复已经运行的剪贴板守护进程；不启动第二个采集器。运行中的单条下载会完成后暂停，队列保留。
- `GET /api/v1/jobs/{job_id}`：读取单个任务进度；重启服务后仍可读到已归档的网页任务摘要。
- `GET /api/v1/capabilities`：读取支持的平台、格式、默认节奏和接口列表。
- `GET /api/v1/health`：检查 API 是否在线。
- `GET /api/openapi.json`：机器可读的 OpenAPI 3.1 接口定义。

`GET /api/v1/jobs` 的 `counts.download_history` 是本机真实下载历史总数；`history` 返回最近条目，含 `save_dir` 最终保存目录。旧记录若无法唯一匹配素材库路径，`save_dir` 为空。`collector` 单独报告剪贴板采集器心跳、开关状态、等待数、冷却状态和失败归档数。过期心跳不会作为在线显示。任务结果的 `skipped` 和条目级 `deduplicated` 标记用于报告共用账本命中的重复项。

网页、命令行、桌面版、API 和剪贴板采集共用本机成功下载账本（`%LOCALAPPDATA%/xhs-dl/history.json`）。只有确认成功落盘的项目进入账本；再从任一入口提交相同作品时会显示为“已存在 · 跳过”，不重复下载。进行中的同一链接也会跨进程互斥，避免剪贴板与手动/API任务同时下载。剪贴板旧成功记录会在采集器启动时并入共用账本；失败项和仅登记的链接不会被当作已下载。新剪贴板采集记录会在整理完成后写入素材库最终目录。

## 调速与重试

`mode: "auto"` 为默认值。任务按顺序运行；成功后采用 8–15 秒间隔，识别到明确的临时网络错误或限流错误时最多额外重试一次，并逐步延长等待。错误文本包含 `Retry-After` 时优先采用服务器给出的等待值，最长 15 分钟。需要登录、验证码、404、失效链接和不支持来源不会自动重试。

剪贴板采集器与 API 任务继续串行处理各自队列。剪贴板队列的网络错误用短指数退避，限流错误用更长退避；同一条暂时失败会移到队尾，不会卡住后续链接。

这个 API 供本机应用调用，不接收账号 Cookie，也不会读取浏览器登录态。要从另一台设备调用，需另行设计带身份验证的远程入口；不要把本机端口直接暴露到公网。
