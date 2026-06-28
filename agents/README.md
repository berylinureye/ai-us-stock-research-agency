# Agent Prompt Index

Each agent has two layers:

1. System Prompt: persistent role, rules, boundaries, output format, forbidden behavior.
2. Weekly User Prompt Template: the concrete task for the current run, including date range, input nodes, filters, and required outputs.

Each executable agent also includes a `Downstream Handoff` block. The handoff contract is defined in [Research Report Output Standard](../docs/research-report-output-standard.md) and records what downstream agents may inherit, what proof is missing, what should trigger a downgrade, and what must not be carried forward.

Files:
- [08-intent-router.md](08-intent-router.md)
- [00-stock-discovery-analyst.md](00-stock-discovery-analyst.md)
- [01-ai-trend-narrative-analyst.md](01-ai-trend-narrative-analyst.md)
- [02-ai-information-sentiment-analyst.md](02-ai-information-sentiment-analyst.md)
- [03-fundamental-analyst.md](03-fundamental-analyst.md)
- [04-technical-analyst.md](04-technical-analyst.md)
- [05-reflection-judge.md](05-reflection-judge.md)
- [06-skill-scout.md](06-skill-scout.md)
- [07-paper-portfolio-attribution-agent.md](07-paper-portfolio-attribution-agent.md)

Core investment research agents:
- Intent Router / Harness Router Agent
- Stock Discovery Analyst
- AI Information & Sentiment Analyst
- Fundamental Analyst
- Technical Analyst
- Reflection Judge
- AI Trend Narrative Analyst
- Paper Portfolio & Attribution Agent

Maintenance agent:
- Skill Scout

Agent scope summary:

| Agent | Primary scopes |
|---|---|
| Intent Router | User intent classification, task type selection, agent path, skill/data-node plan, missing configuration, safety boundary check |
| Stock Discovery | Candidate generation, executive signal, earnings-call signal, capex/customer inference, GitHub/developer adoption, catalysts, market/technical screens, active/watch/reject filtering |
| AI Information & Sentiment | RSS/news, YouTube/podcasts, `last30days`, GitHub, arXiv, market intel, current observed story, long-horizon story, AI value-chain expansion |
| Fundamental | `financial-data-collector`, Longbridge fundamentals/earnings/research/value, SEC, Nasdaq, Yahoo, Finviz, Alpha Vantage, Finnhub, earnings data |
| Technical | `technical-analyst`, Longbridge market/technical, TradingView, Yahoo, CBOE, FRED, Finviz; first pass chart-only |
| Reflection | Closed-loop audit, trend story audit, value-chain jump audit, Cathie Wood vs Buffett perspective debate |
| Final Trend Narrative | Boss conclusion page, research action rating, Top 5 Research Action Pool, estimated upside range, estimated holding range, exit/trim rule, hard-evidence judgment table, research tiering, current story, long-horizon projection, kept/downgraded stories, investment impact map, falsification checks |
| Paper Portfolio & Attribution | Conclusion Pool, Monday hypothetical entry, Friday review, shadow ledger, benchmark-relative returns, expected-upside attribution, sell/trim review, signal-weight iteration |
| Skill Scout | GitHub skill discovery, benchmark review, safety review, suggested add-on features, approved low-risk auto-installs |

Default weekly flow:

```text
user request
  -> Intent Router / Route Plan
  -> data inputs selected by route
  -> Stock Discovery Section
  -> AI Information & Sentiment Section
  -> Fundamental Section
  -> Technical Section
  -> Reflection Section
  -> Final AI Trend Narrative Conclusion
  -> Paper Portfolio & Attribution Section
  -> Skill Scout add-on recommendations as a separate appendix
```

This is a directed section pipeline, not a roundtable discussion. The Intent Router selects the path before research begins. The Skill Scout section improves the research system and is separate from investment conclusions.

Final weekly briefs must pass [Weekly Brief Quality Gate](../docs/weekly-brief-quality-gate.md):
- Run Intent Router first internally, but publish the Boss Decision Page first; put Route Plan, data-node status, and quality checks in appendices.
- Research action rating and confidence score for core candidates.
- Top 5 Research Action Pool capped at 5, with confidence >=75 for every entry.
- Estimated upside range, estimated holding range, and exit/trim rule for every Top 5 entry.
- Conclusion Pool records user-selected candidates separately from model recommendations.
- Core judgments backed by 2-3 hard evidence summaries plus `Evidence Pack` links.
- Sibling evidence subfile `reports/{report_slug}.evidence.md` with full source tables and original links.
- Research tiering by evidence strength: first tier, second tier, observation layer, excluded/deferred.
- Intent Route Plan with selected/skipped agents and skill plan.
- 10 AI technology news items.
- 5 AI academic papers.
- 5 AI open-source projects.
- 5 high-signal sentiment evidence items with explicit source/tool status.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- AI value-chain expansion map.
- Stock Discovery candidate funnel and noise-control decisions.
- Conclusion Pool and Paper Portfolio & Attribution shadow ledger / attribution.
- No fabricated items, broken links, or stale recency claims.
- Professional, concise Chinese style.
- Explicit data-input status for each tool/node used.
