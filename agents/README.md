# Agent Prompt Index

Each agent has two layers:

1. System Prompt: persistent role, rules, boundaries, output format, forbidden behavior.
2. Weekly User Prompt Template: the concrete task for the current run, including date range, input nodes, filters, and required outputs.

Files:
- [01-ai-trend-narrative-analyst.md](01-ai-trend-narrative-analyst.md)
- [02-ai-information-sentiment-analyst.md](02-ai-information-sentiment-analyst.md)
- [03-fundamental-analyst.md](03-fundamental-analyst.md)
- [04-technical-analyst.md](04-technical-analyst.md)
- [05-reflection-judge.md](05-reflection-judge.md)
- [06-skill-scout.md](06-skill-scout.md)

Core investment research agents:
- AI Information & Sentiment Analyst
- Fundamental Analyst
- Technical Analyst
- Reflection Judge
- AI Trend Narrative Analyst

Maintenance agent:
- Skill Scout

Agent scope summary:

| Agent | Primary scopes |
|---|---|
| AI Information & Sentiment | RSS/news, YouTube/podcasts, `last30days`, GitHub, arXiv, market intel, current observed story, long-horizon story, AI value-chain expansion |
| Fundamental | `financial-data-collector`, Longbridge fundamentals/earnings/research/value, SEC, Nasdaq, Yahoo, Finviz, Alpha Vantage, Finnhub, earnings data |
| Technical | `technical-analyst`, Longbridge market/technical, TradingView, Yahoo, CBOE, FRED, Finviz; first pass chart-only |
| Reflection | Closed-loop audit, trend story audit, value-chain jump audit, Cathie Wood vs Buffett perspective debate |
| Final Trend Narrative | Current story, long-horizon projection, kept/downgraded stories, investment impact map, falsification checks |
| Skill Scout | GitHub skill discovery, benchmark review, safety review, suggested add-on features |

Default weekly flow:

```text
data inputs
  -> AI Information & Sentiment Section
  -> Fundamental Section
  -> Technical Section
  -> Reflection Section
  -> Final AI Trend Narrative Conclusion
  -> Skill Scout add-on recommendations as a separate appendix
```

This is a directed section pipeline, not a roundtable discussion. The Skill Scout section improves the research system and is separate from investment conclusions.

Final weekly briefs must pass [Weekly Brief Quality Gate](../docs/weekly-brief-quality-gate.md):
- 10 AI technology news items.
- 5 AI academic papers.
- 5 AI open-source projects.
- 5 high-signal sentiment evidence items with explicit source/tool status.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- AI value-chain expansion map.
- No fabricated items, broken links, or stale recency claims.
- Professional, concise Chinese style.
- Explicit data-input status for each tool/node used.
