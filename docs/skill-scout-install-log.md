# Skill Scout Install Log

返回：[README](../README.md) · [Skill Registry](skill-registry.md)

本日志记录 Skill Scout 自动安装或拒绝候选 skill 的证据。Skill Scout 的自动安装只适用于低风险 read-only 数据输入或 reasoning-lens skills，不适用于 broker、order execution、account access、position sizing、portfolio rebalancing 或 opaque installer。

## 2026-06-26

### Installed

| Candidate | Repo | Benchmark Hit | Installed Path | Why Added | Risk Review |
|---|---|---|---|---|---|
| `global-stock-data` | https://github.com/simonlin1212/global-stock-data | 932 stars, 157 forks, 0 open issues; README/SKILL clear | `/Users/chenzhuoxin/.codex/skills/global-stock-data` | Adds zero-auth backup for US/HK quote, K-line, technical indicators, fundamentals, SEC filing, and market-list checks | Low risk: read-only data source; no broker/order/account action found in reviewed README/SKILL |

Usage boundary:
- Use as cross-check for Longbridge, Yahoo, Nasdaq, TradingView, Finviz, and SEC nodes.
- Do not use as the sole source for material financial claims.
- Do not convert its market data into order execution, account action, or position sizing.
- Restart Codex to pick up new skills.

### Watch / Reject

| Candidate | Benchmark Evidence | Decision | Reason |
|---|---:|---|---|
| `himself65/finance-skills` | 2886 stars, 320 forks | Watch | Strong heat, but broad finance collection needs path-level review before adding to avoid duplicated or overbroad capabilities |
| `tradermonty/claude-trading-skills` | 2051 stars, 494 forks | Reject for core chain | Trading and strategy focus increases risk of order/position/action drift |
| `OctagonAI/skills` | 124 stars, 12 forks | Watch | Relevant to financial research, but likely depends on Octagon-specific services/API; review only if a concrete gap appears |
| `yennanliu/InvestSkill` | 95 stars, 27 forks | Watch | Useful analysis framework, but default BUY/HOLD/SELL style needs adaptation to research action ratings and stricter output boundaries |
| `tellmefrankie/ai-investment-skills` | 8 stars, 5 forks | Reject | Below benchmark and not enough adoption evidence |
