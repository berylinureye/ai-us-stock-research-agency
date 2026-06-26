# Weekly Brief Quality Gate

This quality gate defines the acceptance criteria for the final weekly AI investment brief.

The brief is not considered complete unless every checklist item below is explicitly checked.

## Required Modules

The final brief must include all core source modules:

1. Intent Route Plan.
2. Stock discovery candidate funnel.
3. AI technology news.
4. AI academic papers.
5. AI open-source projects.
6. AI information and sentiment evidence.
7. Paper portfolio and attribution status when prior observations exist.

Minimum quantity:

| Module | Required Count | Minimum Source Requirement |
|---|---:|---|
| Intent Route Plan | 1 | task type, selected agents, skipped agents, skill plan, missing inputs, safety boundary |
| Top 5 Research Action Pool | <= 5 | action rating, confidence, hard evidence, invalidation, next-week check |
| AI technology news | 10 | title, source, date, link |
| AI academic papers | 5 | title, authors or institution if available, date, link |
| AI open-source projects | 5 | repo name, link, stars or benchmark evidence |
| AI information and sentiment evidence | 5 | source/platform, topic, date or range, link |
| Active research candidates | <= 8 | ticker, signal families, score, missing proof |

If a module cannot reach the required count, the brief must say so and explain which input node failed or returned insufficient data. Do not invent replacement items.

## Executive Output Boundary

The final brief is an internal investment research brief, not a process audit or evidence dump.

The Intent Router must run first internally, but the published brief must start with the Boss Decision Page. The Intent Route Plan belongs in an appendix, not above the conclusion.

The first visible page must contain:

- One-sentence main conclusion.
- Research treatment: strong confirm / keep / downgrade / defer / exclude.
- Research action rating: Research Buy / Hold-Watch / Avoid-Sell Bias / No Rating.
- Confidence score from 0-100.
- Top 5 Research Action Pool when eligible candidates exist.
- First-tier, second-tier, observation-layer, and excluded/deferred candidates.
- The 3-5 highest-conviction judgments.
- The hardest 2-3 evidence points for each high-conviction judgment.
- The largest falsification risk.
- The most important next-week validation item.

The final brief must not begin with:

- Intent Route Plan.
- Run boundaries.
- Data-node status.
- Tool failure tables.
- Quality gate checklists.
- Long raw candidate tables.
- Generic methodology.

Those items are required for auditability, but they must appear after the Boss Decision Page and core evidence chain.

## Research Action Rating Checks

Final conclusions may include research action ratings, but they must obey these gates:

| Rating | Required Gate |
|---|---|
| `Research Buy` | Confidence >=75, no major Reflection break, at least three of information/sentiment, fundamental, technical, and Reflection support the thesis |
| `Hold-Watch` | Confidence 60-74 or one major confirmation missing |
| `Avoid-Sell Bias` | Confidence <60, thesis broken, technical invalidation, weak fundamental link, or overextended expectations |
| `No Rating` | Missing data, failed critical node, or insufficient evidence |

Top 5 Research Action Pool rules:

- Maximum 5 entries.
- Do not fill all 5 slots if fewer candidates clear the threshold.
- Every entry must include hard evidence, invalidation condition, and next-week check.
- The pool is for shadow ledger and attribution only. It must not include order instructions, target prices, position sizing, or broker/account actions.

## Accuracy Checks

Before publishing the final brief, verify:

- The Intent Route Plan matches the user's request and does not run unrelated agents.
- Skipped agents have clear reasons and re-run triggers.
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

- Boss Decision Page at the very start of the published report, before any Intent Route Plan, run status, or data-node status.
- Research action rating and confidence score for core candidates.
- Top 5 Research Action Pool when one or more candidates clear the threshold.
- Core judgment table with hard evidence and falsification risk.
- Research tiering by evidence strength: first tier, second tier, observation layer, excluded/deferred.
- Intent Route Plan.
- AI technology news section with 10 items.
- AI academic papers section with 5 items.
- AI open-source projects section with 5 items.
- AI information and sentiment section with 5 high-signal evidence items.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- AI value-chain expansion map.
- Stock Discovery candidate funnel.
- Trend synthesis.
- Information, sentiment, and market narrative synthesis.
- Investment impact map.
- Fundamental validation handoff.
- Technical analysis handoff.
- Reflection / closed-loop review.
- Wood vs Buffett perspective debate summary.
- Paper Portfolio & Attribution section when prior observations exist.
- Suggested add-on features from Skill Scout when available.

## Language Style

Write in Chinese by default.

Style requirements:

- Professional.
- Concise.
- Dense with signal.
- Similar to a technology intelligence brief.
- Conclusion-first.
- Explicit and judgmental when evidence supports it.
- Clear about downgraded, deferred, and excluded stories.
- Avoid casual chat, filler, generic motivation, and vague optimism.

## Tool/Data Return Checks

For every data-input node used, record whether it successfully returned data:

| Input Node | Expected Output | Status | Notes |
|---|---|---|---|
| Intent Router | task type / selected agents / skill plan | success / partial / failed |  |
| RSS/news | AI technology news | success / partial / failed |  |
| arXiv/papers | AI academic papers | success / partial / failed |  |
| GitHub | AI open-source projects | success / partial / failed |  |
| Podcasts/videos | transcript or notes | success / partial / failed |  |
| last30days | community sentiment | success / partial / failed |  |
| Finance data | fundamentals / market data | success / partial / failed |  |
| Chart data | K-line / technical data | success / partial / failed |  |
| Longbridge data | quote / kline / fundamentals / earnings / research | success / partial / failed |  |
| Cross-check data | SEC / Nasdaq / Yahoo / TradingView / Finviz / CBOE / FRED | success / partial / failed |  |
| Paper ledger | simulated entries / exits / attribution | success / partial / failed / not applicable |  |
| Perspective skills | Wood / Buffett debate | success / partial / failed |  |

If a node fails, do not silently continue as if data exists. Mark the affected conclusion as lower confidence.

## Final Checklist

```markdown
## 质量检查

- 内容准确性：通过 / 部分通过 / 未通过
  - 是否有编造：
  - 是否有错链：
  - 是否有过时信息：
- Router 路由：通过 / 部分通过 / 未通过
  - Task type 是否正确：
  - Selected agents 是否匹配用户请求：
  - Skipped agents 是否有理由：
  - Skill plan 是否清楚：
  - 缺失输入/API 是否标明：
- 格式完整性：通过 / 部分通过 / 未通过
  - 老板决策页是否在发布报告最前面：有 / 无
  - 是否先给主结论、分层排序、最大风险和下周验证：有 / 无
  - 是否把 Intent Route Plan、数据节点状态和质量检查后置：有 / 无
  - 高置信度判断是否有 2-3 条硬证据：有 / 无
  - 是否包含 action rating 和 confidence：有 / 无
  - Top 5 池是否不超过 5 个：有 / 无 / 不适用
  - 入池候选是否 confidence >=75：有 / 无 / 不适用
  - 是否没有目标价、仓位、下单或账户动作：有 / 无
  - Intent Route Plan：有 / 无
  - AI 技术新闻：{count}/10
  - AI 学术论文：{count}/5
  - AI 开源项目：{count}/5
  - AI 舆情证据：{count}/5
  - Active research candidates：{count}/8 max
  - 当前观察版趋势故事：有 / 无
  - 长期远演版趋势故事：有 / 无
  - AI 产业链外推图：有 / 无
  - Paper Portfolio & Attribution：有 / 无 / 不适用
- 叙事纪律：通过 / 部分通过 / 未通过
  - 当前故事是否有证据：
  - 远期展望是否标注事实/推断/假设：
  - 产业链外推是否说明中间机制：
- 语言风格：通过 / 部分通过 / 未通过
  - 是否专业：
  - 是否精炼：
  - 是否像科技简报：
  - 是否结论先行：
  - 判断语气是否明确：
- 数量要求：通过 / 部分通过 / 未通过
  - 新闻：
  - 论文：
  - 项目：
- 工具调用：通过 / 部分通过 / 未通过
  - Intent Router：
  - RSS/news：
  - arXiv：
  - GitHub：
  - Podcasts/videos：
  - last30days：
  - Finance：
  - Chart：
  - Longbridge data：
  - Cross-check data：
  - Paper ledger：
  - Perspective skills：
```
