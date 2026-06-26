# Weekly Brief Quality Gate

This quality gate defines the acceptance criteria for the final weekly AI investment brief.

The brief is not considered complete unless every checklist item below is explicitly checked.

## Required Modules

The final brief must include all core source modules:

1. AI technology news.
2. AI academic papers.
3. AI open-source projects.
4. AI information and sentiment evidence.

Minimum quantity:

| Module | Required Count | Minimum Source Requirement |
|---|---:|---|
| AI technology news | 10 | title, source, date, link |
| AI academic papers | 5 | title, authors or institution if available, date, link |
| AI open-source projects | 5 | repo name, link, stars or benchmark evidence |
| AI information and sentiment evidence | 5 | source/platform, topic, date or range, link |

If a module cannot reach the required count, the brief must say so and explain which input node failed or returned insufficient data. Do not invent replacement items.

## Accuracy Checks

Before publishing the final brief, verify:

- No fabricated article, paper, project, company, ticker, quote, or link.
- No broken or missing links for items used as evidence.
- No stale information presented as current.
- Dates are explicit when recency matters.
- Inferences are labeled as inferences, not facts.
- Current observed stories are grounded in dated evidence.
- Long-horizon projections are labeled as fact, inference, or hypothesis.
- Value-chain expansion includes the missing middle mechanism instead of jumping directly from AI news to stock impact.

## Format Checks

The final brief must include:

- AI technology news section with 10 items.
- AI academic papers section with 5 items.
- AI open-source projects section with 5 items.
- AI information and sentiment section with 5 high-signal evidence items.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- AI value-chain expansion map.
- Trend synthesis.
- Information, sentiment, and market narrative synthesis.
- Investment impact map.
- Fundamental validation handoff.
- Technical analysis handoff.
- Reflection / closed-loop review.
- Wood vs Buffett perspective debate summary.
- Suggested add-on features from Skill Scout when available.

## Language Style

Write in Chinese by default.

Style requirements:

- Professional.
- Concise.
- Dense with signal.
- Similar to a technology intelligence brief.
- Avoid casual chat, filler, generic motivation, and vague optimism.

## Tool/Data Return Checks

For every data-input node used, record whether it successfully returned data:

| Input Node | Expected Output | Status | Notes |
|---|---|---|---|
| RSS/news | AI technology news | success / partial / failed |  |
| arXiv/papers | AI academic papers | success / partial / failed |  |
| GitHub | AI open-source projects | success / partial / failed |  |
| Podcasts/videos | transcript or notes | success / partial / failed |  |
| last30days | community sentiment | success / partial / failed |  |
| Finance data | fundamentals / market data | success / partial / failed |  |
| Chart data | K-line / technical data | success / partial / failed |  |
| Longbridge data | quote / kline / fundamentals / earnings / research | success / partial / failed |  |
| Cross-check data | SEC / Nasdaq / Yahoo / TradingView / Finviz / CBOE / FRED | success / partial / failed |  |
| Perspective skills | Wood / Buffett debate | success / partial / failed |  |

If a node fails, do not silently continue as if data exists. Mark the affected conclusion as lower confidence.

## Final Checklist

```markdown
## 质量检查

- 内容准确性：通过 / 部分通过 / 未通过
  - 是否有编造：
  - 是否有错链：
  - 是否有过时信息：
- 格式完整性：通过 / 部分通过 / 未通过
  - AI 技术新闻：{count}/10
  - AI 学术论文：{count}/5
  - AI 开源项目：{count}/5
  - AI 舆情证据：{count}/5
  - 当前观察版趋势故事：有 / 无
  - 长期远演版趋势故事：有 / 无
  - AI 产业链外推图：有 / 无
- 叙事纪律：通过 / 部分通过 / 未通过
  - 当前故事是否有证据：
  - 远期展望是否标注事实/推断/假设：
  - 产业链外推是否说明中间机制：
- 语言风格：通过 / 部分通过 / 未通过
  - 是否专业：
  - 是否精炼：
  - 是否像科技简报：
- 数量要求：通过 / 部分通过 / 未通过
  - 新闻：
  - 论文：
  - 项目：
- 工具调用：通过 / 部分通过 / 未通过
  - RSS/news：
  - arXiv：
  - GitHub：
  - Podcasts/videos：
  - last30days：
  - Finance：
  - Chart：
  - Longbridge data：
  - Cross-check data：
  - Perspective skills：
```
