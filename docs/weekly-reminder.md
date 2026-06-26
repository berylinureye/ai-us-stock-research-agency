# Weekly Reminder

返回：[README](../README.md) · [AGENCY](../AGENCY.md)

本机已配置一个 macOS LaunchAgent，用来每周五提醒运行 AI 美股研究闭环。

## 当前提醒

| 字段 | 值 |
|---|---|
| Label | `com.ai-us-stock-research-agency.friday-reminder` |
| 本机路径 | `/Users/chenzhuoxin/Library/LaunchAgents/com.ai-us-stock-research-agency.friday-reminder.plist` |
| 时间 | 每周五 09:00，本机时区 |
| 动作 | macOS notification |
| 内容 | 运行 AI 美股周五分析：Router -> Top 5 Research Action Pool -> Conclusion Pool；下周一假设买入，下周五复盘 |

## 研究闭环

```text
Friday final report
  -> Top 5 Research Action Pool
  -> Conclusion Pool records user-selected candidates
  -> next Monday close hypothetical entry
  -> next Friday close review
  -> attribution vs estimated upside range
  -> Hold / Take-Profit / Trim / Avoid-Sell review
```

## 核查命令

```bash
launchctl print "gui/$(id -u)/com.ai-us-stock-research-agency.friday-reminder"
```

如果以后迁移机器，需要重新创建并加载本机 LaunchAgent。这个文件不进仓库，因为它是用户环境配置。
