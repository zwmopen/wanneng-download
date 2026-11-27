# 项目对话闭环清单

> 每个项目只保留一份 `TASK_CLOSURE.md`。持续未完成的要求带入后续区段，直到凭证据关闭或明确被取代。

## 对话：2026-11-27 · 赏秋素材统一列表与失败诊断

- 项目 / 仓库：万能下载器 `xhs-dl`
- 路径 / 分支：`D:\AICode\工具开发\projects\xhs-dl` / `master`
- 工作区说明：原有多文件改动已存在；未重置或覆盖。本次相关改动提交 `213fcbc` 并推送到 `origin/master`，其它改动保持未提交。
- 目标：核对用户给出的19条小红书链接；免登录、去重；让历史、剪贴板失败/待补素材和 AI 任务状态在作品列表准确可见。

| ID | 用户要求 | 状态 | 证据 | 遗留 |
|---|---|---|---|---|
| C-001 | 核对19条链接并避免重复采集 | 已完成 | 应用 `GET /api/v1/workbench/artworks?mode=history` 回读命中19/19；8条完整入库、10条待补、1条规则拦截；无新采集任务 | 无 |
| C-002 | 列表读出作者、互动数、图片数、发布时间 | 已完成 | 下载包 `metadata.json` 与待补目录名/文件回填可核字段；本次19条作者及可得赞评数、图片数已回读；缺失发布时间仍为“—” | 无 |
| C-003 | 待补/规则拦截素材也进入统一作品列表 | 已完成 | 合并剪贴板队列记录及待补目录事实；当前 API 读回19条，部分素材不再误标“已下载” | 若队列存档被用户清空，后续应将快照正式持久化到工作台库 |
| C-004 | AI 任务未知/部分失败要正确标记并保留诊断 | 源码和测试已完成 | xhs-dl 显示未知/部分失败；`jianghu-collector-gui` detached worker 已加脱敏输出摘要与退出码，3项专项测试和335项整套测试通过 | MCP worker 长驻进程尚未 reload；未来任务才会有新诊断，旧任务原始 stderr 已丢失，无法追溯原因 |
| C-005 | 保留原工作区改动并验证桌面实际数据 | 已完成本地回读与推送 | `git diff --check` 通过；专项工作台测试26项通过；桌面 HTTP 服务版本4.2.0在线，源码时间戳 `1795761343`，重启后真实配置读取共享队列并显示19条 | 未打包发布；工作区其它既有改动仍保留为未提交 |

### 本次19条清单状态

- **8条完整入库**：7AUCYs1gZY3、1WLbPDllDFt、6xSJ5L6N9P1、9E18joNe8Q5、8PaQkOSVldD、1mSidMGZBvT、7D5CmuRK6NI、7MzeDQy0yZ7。
- **10条待补素材**：1eDSJKE9RtU、3zSxkkZj6De、AMIeO1AFXCG、9yDSzCorvy、9M1MDyiHoSD、4NN6QSmXYkJ、6SFsBjzsxJG、2iccRLqhprv、5DIHgTNdXsb、1Qe1GWDyJ7e。
- **1条规则拦截**：7v5eAYs41ML（“遛娃”词触发营销规则；当前只显示拦截，未把它当作成功素材）。
- 互动数与图片数来自本地作品元数据或采集器生成的素材目录名/文件；发布时间在可读取数据中均缺失，列表保留“—”，没有用读取时间替代。

### 分层验收

- **源码**：`xhs_dl/web/app.py`、`xhs_dl/web/toolbox_store.py`、`xhs_dl/web/ui_template.py` 增加队列历史统一、待补素材事实读取及状态显示；`tests/test_workbench_hub.py` 增加回归覆盖；`CHANGELOG.md` 记录未发布变更。
- **测试**：`python -m pytest -p no:xonsh tests/test_workbench_hub.py -q`：26 passed。工作进程仓库整套测试：335 passed。
- **运行实例**：按正式 `config/config.json` 重启本地 HTTP 服务；API 健康检查通过，列表 API 命中19/19。
- **采集风控**：剪贴板队列为空、后台采集器 idle，万能采集器 busy=false、verification_required=false；本次未使用登录态、未自动重发未知任务。
- **Git 与发布**：提交 `213fcbc`（`Unify clipboard results in artwork history`）已推送到 `origin/master`。只提交本次相关代码、测试、变更记录与闭环清单；素材命名的既有改动和其它未相关工作区内容仍保持未提交。

### 后续注意

- 如果剪贴板失败存档会被定期清理，应将失败/待补记录在队列移除前持久化进 `workbench_hub.json`，否则这些列表项会随源存档消失。
- MCP 长驻 worker 进程尚未重新加载新诊断代码；需要在无任务运行时重启该服务后，未来异常任务才能记录脱敏摘要与退出码。
