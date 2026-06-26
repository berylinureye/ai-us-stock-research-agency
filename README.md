# AI 美股投资研究 Agency

这是一个面向 AI 产业趋势和美股投资研究的多 Agent 工作流。

它不会自动交易，不会下单，不会给仓位建议。它的目标是每周把 AI 科技新闻、播客、舆情、GitHub、论文、美股基本面和技术面数据组织成一份可审查的研究报告。

## 核心链路

```text
RSS / YouTube / Podcasts / last30days / GitHub / arXiv / market intel
  -> AI Information & Sentiment Section
  -> Fundamental Section
  -> Technical Section
  -> Reflection Section
     -> Cathie Wood vs Buffett Perspective Debate
  -> Final AI Trend Narrative Conclusion
  -> Weekly Brief Quality Gate
  -> Skill Scout Appendix
```

## 关键理念

- Skills 是数据输入节点，不是最终判断者。
- 舆情只能识别市场关注和候选叙事，不能证明财务改善。
- 基本面必须把叙事落到收入、利润、现金流、capex、margin、估值或预期差。
- 技术面第一轮只看图表，不能被新闻或叙事污染。
- Reflection 只审查上游证据，不新增事实。
- 长期远演可以大胆，但必须标注事实、推断和长期假设。
- 最终报告不输出买卖建议、目标价、仓位或自动交易动作。

## Agent 文件

| Agent | 文件 | 职责 |
|---|---|---|
| AI Trend Narrative Analyst | [agents/01-ai-trend-narrative-analyst.md](agents/01-ai-trend-narrative-analyst.md) | 最终 AI 趋势投资研究结论 |
| AI Information & Sentiment Analyst | [agents/02-ai-information-sentiment-analyst.md](agents/02-ai-information-sentiment-analyst.md) | 新闻、播客、舆情、GitHub、arXiv、趋势故事草案 |
| Fundamental Analyst | [agents/03-fundamental-analyst.md](agents/03-fundamental-analyst.md) | 美股基本面验证和财务传导链 |
| Technical Analyst | [agents/04-technical-analyst.md](agents/04-technical-analyst.md) | K 线、价格行为、支撑阻力、技术情景 |
| Reflection Judge | [agents/05-reflection-judge.md](agents/05-reflection-judge.md) | 闭环审查、Wood vs Buffett 辩论 |
| Skill Scout | [agents/06-skill-scout.md](agents/06-skill-scout.md) | 每周 GitHub skills / plugins 升级建议 |

## 当前已安装 Skill Scopes

### 信息与舆情

- `last30days`
- `youtube-full`
- `bibi`
- `ak-rss-digest`
- `transcript-polisher`

### 美股市场与催化剂

- `longbridge`
- `longbridge-market-data`
- `longbridge-intel`
- `nasdaq-data`
- `finviz`
- `tradingview`
- `yahoo-finance`

### 基本面

- `financial-data-collector`
- `longbridge-fundamentals`
- `longbridge-earnings`
- `longbridge-research`
- `longbridge-value-investing`
- `sec-data`
- `nasdaq-data`
- `earningswhispers`
- `yahoo-finance`
- `finviz`
- `alpha-vantage`
- `finnhub`

### 技术面与市场状态

- `technical-analyst`
- `longbridge-technical`
- `longbridge-market-data`
- `tradingview`
- `yahoo-finance`
- `cboe-data`
- `fred-macro`
- `finviz`

### Reflection

- `cathie-wood-perspective`
- `buffett-perspective`

## 配置

复制 `.env.example` 到 `.env` 并填入本地密钥。

```bash
cp .env.example .env
```

不要提交 `.env`。仓库已经通过 `.gitignore` 忽略真实密钥文件。

常用可选变量：

- `ALPHA_VANTAGE_API_KEY`
- `FINNHUB_API_KEY`
- `FRED_API_KEY`
- `SEC_EDGAR_USER_AGENT`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENROUTER_API_KEY`
- `PERPLEXITY_API_KEY`

Longbridge 通常通过 CLI/MCP 授权，而不是写入 `.env`。本项目只使用 read-only research mode，不请求交易权限。

安装或更新 skills 后，请重启 Codex 或开启新线程，让新 skills 被会话重新加载。

## 每周运行方式

新聊天中让 Codex 读取：

- [AGENCY.md](AGENCY.md)
- [docs/ai-investment-agent-system.md](docs/ai-investment-agent-system.md)
- [docs/weekly-brief-quality-gate.md](docs/weekly-brief-quality-gate.md)

然后按 Harness Agent 流程依次运行：

1. AI Information & Sentiment Section。
2. Fundamental Section。
3. Technical Section。
4. Reflection Section。
5. Final AI Trend Narrative Conclusion。
6. Weekly Brief Quality Gate。
7. Skill Scout Appendix。

## 质量门槛

最终周报必须包含：

- 10 条 AI 技术新闻。
- 5 篇 AI 学术论文。
- 5 个 AI 开源项目。
- 5 条高信号舆情证据。
- 当前观察到的 AI 趋势故事。
- 长期远演版 AI 趋势展望。
- AI 产业链外推图。
- 基本面传导链。
- 技术面关键价位和情景。
- Reflection 闭环审查。
- Wood vs Buffett 辩论摘要。

任何数据节点失败都必须标记为 `partial` 或 `failed`，不得编造补齐。

## 已交付文档

- [AGENCY.md](AGENCY.md)：主 harness 运行手册。
- [AGENTS.md](AGENTS.md)：项目级规则。
- [docs/ai-investment-agent-system.md](docs/ai-investment-agent-system.md)：系统设计。
- [docs/weekly-brief-quality-gate.md](docs/weekly-brief-quality-gate.md)：质量门槛。
- [docs/agency-implementation-report.md](docs/agency-implementation-report.md)：实施报告与资深研究视角把关。

## 状态

当前版本：`v0.1-draft`

等待人工确认后再推送到 GitHub。
