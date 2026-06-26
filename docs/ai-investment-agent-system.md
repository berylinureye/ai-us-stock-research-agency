# AI Investment Agent System

## Core Principle

Plugins and skills are data-input nodes. Their job is to fetch the right data with explicit parameters.

The workflow decides how data moves.

The model layer decides what to filter, classify, summarize, challenge, and turn into a structured investment brief.

Do not configure a plugin as "click a button and hope." Configure it as:

```text
source + parameters + limits + sorting + output schema
  -> data input
  -> cleaning / dedupe
  -> model filtering, classification, summary
  -> structured AI investment brief
```

Final weekly briefs must pass the [Weekly Brief Quality Gate](weekly-brief-quality-gate.md).

The hard minimum source modules in the AI Information & Sentiment Section are:
- 10 AI technology news items.
- 5 AI academic papers.
- 5 AI open-source projects.
- 5 high-signal sentiment evidence items.

If any module cannot meet the minimum count, the report must explain which input node failed or returned insufficient data. Missing data must not be replaced with invented items.

## Agent Roles

Detailed prompts live in:
- [AI Information & Sentiment Analyst](../agents/02-ai-information-sentiment-analyst.md)
- [Fundamental Analyst](../agents/03-fundamental-analyst.md)
- [Technical Analyst](../agents/04-technical-analyst.md)
- [Reflection Judge](../agents/05-reflection-judge.md)
- [AI Trend Narrative Analyst](../agents/01-ai-trend-narrative-analyst.md)
- [Skill Scout](../agents/06-skill-scout.md)

## Installed US Equity Skill Stack

The current stack is research-only and focused on US-listed equities.

| Layer | Skills | Use |
|---|---|---|
| AI information and sentiment | `last30days`, `youtube-full`, `bibi`, `ak-rss-digest`, `transcript-polisher` | Podcast, video, RSS, community sentiment, transcript cleanup |
| Market data and catalysts | `longbridge`, `longbridge-market-data`, `longbridge-intel`, `nasdaq-data`, `finviz`, `tradingview`, `yahoo-finance` | Quotes, K-line, market attention, screener, news/catalyst context |
| Fundamentals | `financial-data-collector`, `longbridge-fundamentals`, `longbridge-earnings`, `longbridge-research`, `longbridge-value-investing`, `sec-data`, `nasdaq-data`, `earningswhispers`, `yahoo-finance`, `finviz`, `alpha-vantage`, `finnhub` | Financial statements, SEC filings, earnings, estimates, valuation, company research |
| Technicals and market regime | `technical-analyst`, `longbridge-technical`, `longbridge-market-data`, `tradingview`, `yahoo-finance`, `cboe-data`, `fred-macro`, `finviz` | Chart-first technical analysis, volatility context, rates/macro context |
| Reflection | `cathie-wood-perspective`, `buffett-perspective` | Perspective debate over upstream evidence |

Out of scope: broker trading, account actions, portfolio rebalancing, position sizing, order execution, and auto-trading.

Each agent is constrained by:
- A persistent System Prompt for identity, rules, boundaries, output format, and forbidden behavior.
- A per-run User Prompt template for the concrete weekly task, input sources, filters, and required result.

This is a directed section pipeline, not a five-agent roundtable. The final conclusion is produced after the information/sentiment, fundamental, technical, and reflection sections are complete.

### 1. AI Information & Sentiment Analyst

Purpose: collect and organize the AI information and sentiment section, including RSS/news, YouTube/podcasts, last30days, GitHub, arXiv, and related skills.

Inputs:
- RSS/news and `ak-rss-digest`.
- YouTube/podcasts through `youtube-full`, `bibi`, and `transcript-polisher`.
- last30days across Reddit, X, YouTube, Hacker News, Polymarket, GitHub, and web.
- GitHub project signals.
- arXiv and research feeds.

Output:
- 10 AI technology news items.
- 5 AI academic papers.
- 5 AI open-source projects.
- YouTube/podcast notes.
- 5 high-signal sentiment evidence items.
- Candidate narratives and questions for downstream sections.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- AI value-chain expansion map.

Rule: this section organizes information and sentiment, then drafts candidate stories for downstream validation. It must not produce final investment conclusions.

Narrative rule:
- Current observed stories must be grounded in dated evidence.
- Long-horizon projections can look far ahead, but every step must be labeled as fact, inference, or long-term hypothesis.
- Value-chain expansion should trace second-order and third-order effects, such as AI capability changes -> compute demand -> chips, networking, cloud, data centers, power, cooling, equipment, software automation, robotics, or other affected layers.

### 2. Fundamental Analyst

Inputs:
- AI Information & Sentiment Section as candidate narrative input.
- Financial statements.
- Earnings calls.
- Segment revenue.
- Capex and demand indicators.
- Analyst estimates and valuation multiples.
- Installed finance skills for US equity data and cross-checking.

Output:
- Financial transmission path.
- Which companies benefit directly vs indirectly.
- What must show up in future financials.
- Key falsification metrics.

Rule: information and sentiment can identify what to test, but cannot serve as financial proof.

Data rule: key financial claims should be checked against at least two independent sources where possible. If sources conflict, the report must mark the section partial and explain the conflict.

### 3. Technical Analyst

Purpose: judge whether price action supports the candidate narratives, while keeping the first pass chart-only.

Inputs:
- Candidate tickers from the AI Information & Sentiment Section or the user.
- K-line charts.
- Volume.
- Moving averages.
- Support and resistance.
- Breakout / rejection / exhaustion patterns.

Output:
- Trend state.
- Key levels.
- Bull/base/bear scenarios.
- Invalidation points.

Rule: this agent should stay chart-first and should not be influenced by narrative or fundamentals during its first pass.

### 4. Reflection Section

Purpose: review the information/sentiment, fundamental, and technical sections for closed-loop consistency.

Required chain:

```text
AI information and sentiment
  -> industry impact
  -> company fundamentals
  -> valuation / expectations
  -> market price action
  -> falsifiable future checks
```

Output:
- What is proven.
- What is assumed.
- Where the chain breaks.
- Which evidence would change the conclusion.
- Which stories should be kept, downgraded, or left undecided.
- Audit of current observed stories.
- Audit of long-horizon projections and value-chain expansion.
- Cathie Wood vs Buffett perspective debate summary.

Required perspective skills:
- `cathie-wood-perspective`: disruptive innovation / AI long-horizon bull lens.
- `buffett-perspective`: value investing / moat / safety margin lens.

Rule: these perspectives are reasoning lenses over upstream evidence, not new evidence sources.

### 5. Final AI Trend Narrative Analyst

Purpose: produce the final AI trend investment research conclusion after all upstream sections are complete.

Inputs:
- AI Information & Sentiment Section.
- Fundamental Section.
- Technical Section.
- Reflection Section.
- Wood vs Buffett debate summary.

Output:
- Final weekly conclusion.
- Current observed AI trend story.
- Long-horizon AI trend projection.
- Kept stories.
- Downgraded stories.
- Investment impact map.
- Risks,反证条件, and next-week checks.

Rule: this is the final synthesis layer. It should not behave like another raw data collector.

### Maintenance Agent: Skill Scout

Purpose: review new GitHub skills weekly and recommend add-on capabilities for this system.

This agent does not install skills automatically. It only recommends.

## Input Node Configuration

### RSS Node

RSS sources must be explicit. Each source needs a concrete feed URL.

Example schema:

```yaml
rss_sources:
  - name: 36Kr
    url: "<rss-url>"
    category: cn_media
    max_items: 20
    lookback_days: 7
  - name: Huxiu
    url: "<rss-url>"
    category: cn_media
    max_items: 20
    lookback_days: 7
  - name: InfoQ
    url: "<rss-url>"
    category: tech_media
    max_items: 20
    lookback_days: 7
```

What it solves:
- Which media sources to read.
- How many items to fetch.
- How far back to look.

### GitHub Node

GitHub search must define keywords, count, and sorting.

Example schema:

```yaml
github_searches:
  - name: ai_agent_projects
    q: "AI agent stars:>500"
    per_page: 10
    sort: updated
    order: desc
  - name: inference_infra
    q: "LLM inference OR vLLM OR SGLang stars:>500"
    per_page: 10
    sort: updated
    order: desc
  - name: agent_skills
    q: '"SKILL.md" "Codex" OR "Claude Code" stars:>100'
    per_page: 20
    sort: stars
    order: desc
```

What it solves:
- Which projects to inspect.
- How many repositories to pull.
- How to sort results.

### arXiv Node

arXiv search must define query, count, and sorting.

Example schema:

```yaml
arxiv_searches:
  - name: ai_agents
    search_query: 'cat:cs.AI AND ("agent" OR "tool use" OR "reasoning")'
    count: 5
    sort_by: submittedDate
    sort_order: descending
  - name: inference_scaling
    search_query: 'cat:cs.LG AND ("inference" OR "test-time compute" OR "reasoning")'
    count: 5
    sort_by: submittedDate
    sort_order: descending
```

What it solves:
- Which research direction to inspect.
- How many papers to include.
- How fresh the research should be.

## Skill Scout Benchmarks

Heat evidence should use fixed benchmarks, not growth trend.

A candidate skill can enter the weekly "Suggested Add-On Features" section only if:

1. It is not already installed in the local skill collection.
2. It is relevant to at least one agent role above.
3. It reaches at least one benchmark:
   - GitHub stars >= 100 for niche skills.
   - GitHub stars >= 500 for general-purpose skills.
   - Forks >= 10.
   - Issues + PRs + Discussions show meaningful user activity.
   - It appears in a curated list such as awesome-agent-skills, ClawHub, or a well-maintained registry.
4. It passes a basic internal review:
   - Clear `SKILL.md` description and trigger conditions.
   - Scoped tool permissions.
   - No obvious credential harvesting.
   - No suspicious full-disk reads.
   - No hidden install scripts or unexplained `curl | bash`.
   - No automatic trading, posting, purchasing, or account actions.
5. It improves the system more than it increases complexity.

Recommended output:

```markdown
## Suggested Add-On Features

| Candidate | Adds What | Benchmark Hit | Relevant Agent | Risk | Recommendation |
|---|---|---|---|---|---|
| skill-name | RSS / GitHub / arXiv / finance / charting | stars/forks/activity/listing | Agent 1/2/3/4/5 | Low/Medium/High | Install / Watch / Reject |
```

Default recommendation policy:
- Install: clear utility, benchmark hit, low risk.
- Watch: useful but duplicate, immature, or medium risk.
- Reject: irrelevant, unsafe, overbroad, or low signal.

## Weekly Report Flow

```text
RSS / GitHub / arXiv / Podcasts / YouTube / last30days
  -> data input nodes
  -> dedupe and normalization
  -> AI Information & Sentiment Section
  -> Fundamental Section
  -> Technical Section
  -> Reflection Section
  -> Final AI Trend Narrative Conclusion
  -> weekly structured AI investment brief
  -> Skill Scout: Suggested Add-On Features as a separate appendix
```

The "Suggested Add-On Features" section should be separate from the investment thesis. It is about improving the research system, not making a trade.

## Final Acceptance Criteria

Before a final weekly brief is considered complete, it must check:

- Content accuracy: no fabrication, no broken evidence links, no stale information presented as current.
- Format completeness: includes AI technology news, AI academic papers, AI open-source projects, and AI information/sentiment evidence.
- Language style: professional, concise, and similar to a technology intelligence brief.
- Quantity requirements: at least 10 news items, 5 papers, 5 projects, and 5 high-signal sentiment evidence items.
- Tool/data return: every used input node must report success, partial success, or failure.
