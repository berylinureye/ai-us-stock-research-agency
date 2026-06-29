# Docs Map

返回：[README](../README.md)

这组文档服务三个目的：运行周报、理解产品架构、维护安全边界。

## 优先阅读

| 文档 | 什么时候看 |
|---|---|
| [../README.md](../README.md) | 第一次了解项目、产品亮点、快速启动 |
| [../AGENCY.md](../AGENCY.md) | 真正运行周报前，作为 Harness Agent runbook |
| [../AGENTS.md](../AGENTS.md) | 查看项目规则、安全边界和报告硬约束 |
| [agent-responsibilities.md](agent-responsibilities.md) | 理解每个 agent 的职责、输入、输出和禁止行为 |
| [research-report-output-standard.md](research-report-output-standard.md) | 写最终报告、证据包和下游 handoff 时 |
| [weekly-brief-quality-gate.md](weekly-brief-quality-gate.md) | 验收完整周报时 |

## 产品与架构

| 文档 | 内容 |
|---|---|
| [ai-investment-agent-system.md](ai-investment-agent-system.md) | 系统原则、Agent pipeline、skill/data node 使用方式 |
| [langgraph-orchestration.md](langgraph-orchestration.md) | LangGraph / StateGraph 如何做意图路由、状态管理和条件编排 |
| [agent-visible-trace.md](agent-visible-trace.md) | 前端展示公开 Agent Trace 的 schema 和边界 |
| [noise-control-and-paper-portfolio-loop.md](noise-control-and-paper-portfolio-loop.md) | 控噪、Conclusion Pool、Paper Portfolio 复盘闭环 |
| [backend-fastapi-refactor-plan.md](backend-fastapi-refactor-plan.md) | 后端 FastAPI 模块化单体重构目标 |
| [next-experiment-and-ui-roadmap.md](next-experiment-and-ui-roadmap.md) | 下一轮实验、后端和 UI 路线图 |

## 配置与维护

| 文档 | 内容 |
|---|---|
| [api-configuration.md](api-configuration.md) | `.env`、模型网关、行情、财务、转录和搜索 API 配置 |
| [skill-registry.md](skill-registry.md) | 已安装 skills / data nodes 的用途、降级和禁止用途 |
| [skill-scout-install-log.md](skill-scout-install-log.md) | Skill Scout 安装/评估记录 |
| [weekly-reminder.md](weekly-reminder.md) | 周报提醒和运行节奏 |

## 输出规范

最终发布报告必须遵守：

- 报告首页是 Boss Decision Page，不从工具状态或 route plan 开始。
- 主报告链接到 evidence 子文件，evidence 子文件再链接原始来源。
- 投资输出保持 research-only，不能写成交易指令、仓位建议或账户操作。
- 数据节点不足必须标 `partial` / `failed`，不能用编造内容补齐数量。
