# 万能采集器桥接 API

`collector_bridge_api.py` 是兼容层，给需要采集队列和回执的本机其他 AI 使用。普通任务调用剪切板采集归档逻辑；模板库任务用隔离下载引擎落盘到桥接器暂存区，绕过通用素材分流。XHS 引擎只读取 XHS-Downloader 本地设置中已保存的 Cookie，不读取浏览器 Cookie，也不上传远端解析站。默认只绑定 `127.0.0.1`；日常下载不需要启动它。

## 启动

在仓库目录运行：

```powershell
python .\collector_bridge_api.py
```

默认地址为 `http://127.0.0.1:8766`。如需让同一局域网内的另一个进程访问，必须明确传入 `--host`；默认不暴露到局域网。8765 由江湖团建转化助手使用，采集桥使用独立的 8766，避免互相抢占端口。

启动后可打开 `http://127.0.0.1:8766/`，在兼容控制台里提交任务、查看队列/暂停原因、轮询任务进度，并点击已落盘的图片或视频。

日常使用的原版万能下载器 Web 和 API 在 `http://127.0.0.1:5678/`。5678 页面已经包含等待任务、正在进行、排队任务、历史下载和“保持原格式”设置。统一启动脚本默认只启动 5678；只有显式传入 `-StartBridge` 才会额外启动 8766。

## 入口关系

```text
5678 原版 Web + API ──> xhs_dl 统一下载引擎 ─> 本地文件

剪切板守护（可选） ────┘
8766 兼容桥（可选） ────┘
```

因此“万能采集器”不是日常必需品。用户只需要 5678；剪切板守护和 8766 只是需要时调用同一个下载引擎的可选入口。

控制台的图片格式默认是“保持原格式”；顶部四个指标卡可以点击，分别展开队列、历史记录、任务表和运行状态。

队列明细中的 URL 是可点击链接，服务通过 `/api/v1/queue/{queue_id}/open` 按队列记录跳转到原始地址，不把签名参数写进页面文本。

## 能力与状态

```powershell
curl.exe http://127.0.0.1:8766/api/v1/capabilities
curl.exe http://127.0.0.1:8766/api/v1/status
curl.exe http://127.0.0.1:8766/api/v1/jobs
```

能力声明会标明：

- 是否使用 Cookie 或浏览器登录态（当前为 `false`）；
- XHS、抖音和通用引擎的实际状态；
- 任务状态查询和落盘文件读取地址。

`/api/v1/status` 同时回报剪切板队列、历史数、暂停标记和心跳新鲜度。心跳没有 PID 时会返回 `process_alive: "unknown"`，不会把旧心跳伪报成在线。

## 提交任务

既可以传 `links`，也可以把整段剪切板内容放入 `text`：

```powershell
$body = @{
  text = '上海胡闹厨房 https://xhslink.cn/o/example'
  conversation_id = 'other-ai-demo-001'
  client = @{ name = 'other-ai'; version = '1.0' }
  options = @{ dry_run = $false; image_format = 'keep' }
} | ConvertTo-Json -Depth 5

curl.exe -X POST http://127.0.0.1:8766/api/v1/jobs `
  -H 'Content-Type: application/json; charset=utf-8' -d $body
```

响应会带 `message_id`、`conversation_id`、`task_id` 和 `job_id`。`202` 只表示已经接收并入队，必须继续轮询：

```powershell
curl.exe http://127.0.0.1:8766/api/v1/jobs/<job_id>
```

最终任务会报告每条链接的 `status`、`success`、`error`、`retryable`、`metadata` 和 `assets`。`assets` 里的 `download_url` 指向已核实存在的本地文件：

```powershell
curl.exe -o .\result.jpg http://127.0.0.1:8766/api/v1/jobs/<job_id>/files/0
```

也可以使用 `POST /api/v1/parse`，它与 `/api/v1/jobs` 相同。

## 状态含义

| 状态 | 含义 |
| --- | --- |
| `accepted` | 已收到请求的回执状态，只出现在 `receipt` 中 |
| `queued` | 已进入本地串行队列 |
| `running` | 正在调用本地引擎 |
| `validated` | `dry_run` 只完成链接/平台校验，没有下载 |
| `completed` | 所有实际链接均有已核实的落盘媒体 |
| `partial` | 至少一条成功，其他条目失败或阻塞 |
| `blocked` | 机器状态码；全部被暂停标记或登录页挡住时，界面显示为“平台等待” |
| `failed` | 没有形成可交付的落盘媒体 |

### 无登录边界

XHS 和抖音路径都不注入 Cookie。公开链接能被当前平台匿名返回时，现有本地引擎可以直接保存；如果平台把短链或长链重定向到登录页，桥接 API 返回 `blocked`/`failed` 和可重试原因，保留原任务信息，不绕过验证码、登录或风控。控制访问频率只能降低请求压力，不能改变平台当前的访问授权结果。

如果本次请求是用户明确提供的、带 `xsec_token` 的公开链接，可以在 `options` 中加 `manual_override: true` 做一次手动尝试；这不会恢复剪切板后台队列，也不会替无鉴权链接生成登录态。

### 安全边界

- 请求正文不会写入桥接任务文件；回执中的 `xsec_token` 等查询参数会脱敏。
- 文件读取只允许读取采集器配置的素材库、下载目录和桥接暂存目录中的已存在文件。
- 任务使用单一工作线程，避免全局暂存目录并发覆盖。
- 服务重启不会自动重放未完成任务；旧任务会标记为可重试的 `failed`，避免重复下载。
