# Project Rules

This repository defines a multi-agent AI investment research workflow.

Canonical operating manual:
- Use `AGENCY.md` as the Harness Agent runbook for executing weekly briefs.

When adding or changing agent prompts:
- Treat plugins and skills as data-input nodes, not as final reasoning authorities.
- Every agent must have a long-lived system prompt and a per-run user prompt template.
- Each prompt must define role, input sources, filtering rules, output schema, and hard limits.
- Any weekly brief, experiment, or single-section research run must start with an Intent Route Plan from `agents/08-intent-router.md`.
- Keep investment output research-oriented. Do not add auto-trading, account actions, or order execution.
- The installed finance stack is for US equity research in read-only mode. Do not request trade permissions, place orders, rebalance portfolios, or retrieve private account data.
- Separate evidence from inference. Every investment claim should identify its source type or state that it is an assumption.
- Separate current observed stories from long-horizon projections. Long-horizon projections must label fact, inference, and hypothesis.
- Prefer Chinese output for reports, unless a task explicitly asks for English.
- Final weekly briefs must pass the quality gate in `docs/weekly-brief-quality-gate.md`.
- The required source modules are AI technology news, AI academic papers, AI open-source projects, and high-signal AI information/sentiment evidence.
- The core research flow is a directed section pipeline: Intent Router -> Stock Discovery -> AI Information & Sentiment Section -> Fundamental Section -> Technical Section -> Reflection Section -> Final AI Trend Narrative Conclusion.
- Stock Discovery runs before the main research sections and must cap active candidates at 8 by default.
- Paper Portfolio & Attribution runs after final conclusions as a shadow-ledger feedback loop. It must not connect to live trading or place orders.
- Skill Scout is a maintenance agent for suggested add-on capabilities, not part of the core investment conclusion.
- Reflection Section includes a Cathie Wood vs Buffett perspective debate. These perspective skills are reasoning lenses, not evidence sources.
- The required quantities are 10 news items, 5 papers, 5 open-source projects, and 5 high-signal sentiment evidence items.
- If a data-input node fails or returns too little data, state that explicitly. Do not fill gaps with invented content.
