# Weekly Brief Quality Gate

This quality gate defines the acceptance criteria for the final weekly AI investment brief.

The brief is not considered complete unless every checklist item below is explicitly checked.

Canonical report structure and handoff standard:

- Use [Research Report Output Standard](research-report-output-standard.md) for the three approved final report versions, public-format constraints, hard publishing limits, and per-agent handoff contracts.
- Full weekly briefs must use Version A: `老板决策页 + 证据包`.
- Fundamental deep dives may use Version B; moat/uncertainty reviews may use Version C.

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
| Agent Visible Trace | one per executed agent when UI/streaming is used | public thinking summary, data nodes used/needed, findings, judgment, next step; raw section Markdown folded away |
| Top 5 Research Action Pool | <= 5 | action rating, confidence, estimated upside range, estimated holding range, exit/trim rule, hard evidence, invalidation, next-week check |
| Conclusion Pool | >= 0 selected entries | selected_by_user, expected Monday entry, Friday review date, status |
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
- Research action rating: Research Buy / Hold-Watch / Take-Profit / Trim Bias / Avoid-Sell Bias / No Rating.
- Confidence score from 0-100.
- Top 5 Research Action Pool when eligible candidates exist.
- Estimated upside range and estimated holding range for each Top 5 candidate.
- Exit / trim rule for each Top 5 candidate.
- First-tier, second-tier, observation-layer, and excluded/deferred candidates.
- The 3-5 highest-conviction judgments.
- The hardest 2-3 evidence summaries for each high-conviction judgment.
- An `Evidence Pack` link for each Top 5 / core candidate, pointing to a separate evidence subfile.
- The largest falsification risk.
- The most important next-week validation item.

The final brief must not begin with:

- Intent Route Plan.
- Agent Visible Trace.
- Run boundaries.
- Data-node status.
- Tool failure tables.
- Quality gate checklists.
- Long raw candidate tables.
- Full evidence tables and long source lists.
- Generic methodology.

Those items are required for auditability, but they must appear after the Boss Decision Page and core evidence chain.

The final brief must also avoid the hard limits from `docs/research-report-output-standard.md`:

- No unsupported target price, certainty language, or performance guarantee.
- No real order, broker, account, position-sizing, allocation, or rebalancing instruction.
- No social heat, KOL view, podcast, GitHub star count, paper, or chart strength treated as proof of revenue or investment merit.
- No hidden missing data, failed tool, stale date, broken link, or unverified source claim.
- No mixing facts, inferences, hypotheses, opinions, market signals, and data gaps.
- No Top 5 padding when fewer candidates clear the evidence threshold.

## Two-Hop Evidence Linking Checks

The brief must separate decision readability from evidence auditability.

For every published report at:

```text
reports/{report_slug}.md
```

there must be a sibling evidence subfile:

```text
reports/{report_slug}.evidence.md
```

The main report must link each Top 5 / core candidate to an anchor in the evidence subfile:

```markdown
[证据包](./{report_slug}.evidence.md#ticker-or-theme)
```

The evidence subfile must then link to original sources.

Required evidence subfile structure:

```markdown
# 证据包：{report_title}

[返回主报告](./{report_slug}.md)

## Evidence Index
| Ticker / Theme | Main Claim | Evidence Anchor |
|---|---|---|

## {ticker_or_theme}
| Evidence ID | Source Type | Date | Supports Which Claim | Fact / Inference / Hypothesis | Link | Notes |
|---|---|---|---|---|---|---|

## Data Node Status
| Input Node | Status | Notes |
|---|---|---|
```

Quality rules:

- The Boss Decision Page may include short evidence summaries, but not full citation tables.
- Long news, paper, GitHub, sentiment, transcript, SEC/IR, and technical evidence tables belong in the evidence subfile.
- Every high-conviction claim in the main report must be traceable by two hops: main report -> evidence subfile -> original source.
- If an evidence subfile is missing, mark format completeness as failed.

## Research Action Rating Checks

Final conclusions may include research action ratings, but they must obey these gates:

| Rating | Required Gate |
|---|---|
| `Research Buy` | Confidence >=75, no major Reflection break, at least three of information/sentiment, fundamental, technical, and Reflection support the thesis |
| `Hold-Watch` | Confidence 60-74 or one major confirmation missing |
| `Take-Profit / Trim Bias` | Actual price reaches or exceeds estimated upside high end, or risk/reward deteriorates after catalyst realization or technical momentum decay |
| `Avoid-Sell Bias` | Confidence <60, thesis broken, technical invalidation, weak fundamental link, or overextended expectations |
| `No Rating` | Missing data, failed critical node, or insufficient evidence |

Top 5 Research Action Pool rules:

- Maximum 5 entries.
- Do not fill all 5 slots if fewer candidates clear the threshold.
- Every entry must include estimated upside range, estimated holding range in days, exit/trim rule, hard evidence, invalidation condition, and next-week check.
- The pool is for shadow ledger and attribution only. It must not include order instructions, target prices, position sizing, or broker/account actions.

Conclusion Pool rules:

- Record user-selected candidates separately from the model's Top 5 suggestions.
- Default cycle is Friday analysis -> next Monday hypothetical entry -> next Friday review.
- If the user selects no candidates, record `selected_by_user=no` rather than assuming a selection.
- If the user overrides the Top 5 and chooses another ticker, mark it as `user_override`.
- Next-Friday attribution must compare actual return against the estimated upside range.

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

- Use of one approved report version from `docs/research-report-output-standard.md`, with Version A required for full weekly briefs.
- Boss Decision Page at the very start of the published report, before any Intent Route Plan, run status, or data-node status.
- Research action rating and confidence score for core candidates.
- Top 5 Research Action Pool when one or more candidates clear the threshold.
- Evidence Pack link for every Top 5 / core candidate.
- Separate sibling evidence subfile for long evidence tables and source citations.
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
- Conclusion Pool section or status when Top 5 candidates exist.
- Suggested add-on features from Skill Scout when available.

## Downstream Handoff Checks

Every executed agent must include a `Downstream Handoff` block unless the route is explicitly final-only and no downstream consumer exists.

Required fields:

| Field | Required Check |
|---|---|
| Handoff ID | Identifies agent/date/theme or ticker |
| Input Status | complete / partial / failed |
| Decision Needed From Next Agent | The next validation or decision is explicit |
| Must-Carry Evidence | Only evidence strong enough for downstream use |
| Key Assumptions | Fact / inference / hypothesis separated |
| Missing Proof | Specific gaps are listed |
| Downgrade Triggers | Conditions that demote the story or candidate |
| Do-Not-Carry | Noise, weak evidence, and forbidden claims are excluded |
| Evidence Anchors | Links, section anchors, or evidence subfile anchors are present |

If a section lacks a handoff block, the Harness must mark the run partial or add a short generated handoff before passing the section downstream.

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
  - UI/stream 是否展示 Agent Visible Trace，而不是默认展示原始 Markdown/参数表：有 / 无 / 不适用
  - 是否为每个 Top 5 / 核心候选提供 Evidence Pack 链接：有 / 无
  - 是否存在同名证据子文件 `{report_slug}.evidence.md`：有 / 无
  - 长证据表是否没有塞进老板决策页：有 / 无
  - 是否使用 `docs/research-report-output-standard.md` 中批准的报告版本：有 / 无
  - 完整周报是否使用 Version A 老板决策页 + 证据包：有 / 无 / 不适用
  - 高置信度判断是否有 2-3 条硬证据：有 / 无
  - 是否包含 action rating 和 confidence：有 / 无
  - Top 5 池是否不超过 5 个：有 / 无 / 不适用
  - 入池候选是否 confidence >=75：有 / 无 / 不适用
  - Top 5 是否包含预估涨幅区间：有 / 无 / 不适用
  - Top 5 是否包含预计观察/持有周期：有 / 无 / 不适用
  - Top 5 是否包含卖出/止盈规则：有 / 无 / 不适用
  - 结论池是否记录用户选择状态：有 / 无 / 不适用
  - 是否使用周五分析 -> 下周一假设买入 -> 下周五复盘：有 / 无 / 不适用
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
- Downstream Handoff：通过 / 部分通过 / 未通过
  - 每个执行 agent 是否有 handoff block：
  - 是否列出 Do-Not-Carry：
  - 是否列出 Missing Proof 和 Downgrade Triggers：
```
