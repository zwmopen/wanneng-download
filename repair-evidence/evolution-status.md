# 采集器进化记录

2026-11-12：D盘项目源码同步当前技能实现后增量修改。
- 无产物不再武断归因为超图或平台验证；保留任务进入原退避重试。
- 心跳区分paused、worker_stopped、cooling、downloading、idle，并报告worker_alive/current_url/cooldown_until。
- 保留原连续失败暂停保护。
- AST语法解析通过；尚未切换运行入口，未做真实下载验收。
- 当前运行技能路径受保护，不能直接回写；原队列、历史和冷却未修改。
