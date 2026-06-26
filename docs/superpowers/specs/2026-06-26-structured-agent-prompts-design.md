# Structured Agent Prompt Design

## Context

This repository already has nine agent prompt files under `agents/`. Each file has a long-lived `System Prompt` and a per-run `Weekly User Prompt Template`, which matches the core project rule. The current prompts are usable, but their internal structure is uneven: some emphasize data-node status, some emphasize safety, some emphasize output schema, and some mix workflow, filtering, and hard limits in prose.

The goal is to standardize prompt structure without rewriting the whole agency in one pass.

## Decision

Use a two-step rollout:

1. Add a shared structured prompt standard document.
2. Apply the standard to two representative agents as examples:
   - `agents/08-intent-router.md`
   - `agents/02-ai-information-sentiment-analyst.md`

The standard will not include an `Initialization` section.

## Prompt Standard

Every agent prompt should use this structure:

```markdown
# {Agent Name}

## Role

## Profile

## Mission

## Input Sources

## Skills / Data Nodes

## Filtering Rules

## Workflow

## Output Schema

## Hard Limits

## Per-Run User Prompt Template
```

### Section Meanings

| Section | Purpose |
|---|---|
| `Role` | One-sentence identity and system position. |
| `Profile` | Language, tone, domain posture, and what kind of agent it should feel like. |
| `Mission` | The concrete job this agent owns and the questions it answers. |
| `Input Sources` | Allowed upstream artifacts, raw data, user inputs, and forbidden substitutions. |
| `Skills / Data Nodes` | Skills and tools treated as data-input nodes or reasoning lenses, with status expectations. |
| `Filtering Rules` | Inclusion, exclusion, ranking, dedupe, evidence, and noise-control rules. |
| `Workflow` | Ordered reasoning and execution steps for this agent. |
| `Output Schema` | The fixed markdown schema the agent must emit. |
| `Hard Limits` | Safety boundaries, forbidden behavior, evidence boundaries, and no-invention rules. |
| `Per-Run User Prompt Template` | Runtime variables and instructions for a concrete run. |

## Scope

### In Scope

- Create a durable prompt standard document.
- Refactor two agent files as examples.
- Preserve existing investment-safety boundaries:
  - no auto-trading;
  - no account actions;
  - no position sizing;
  - no order instructions;
  - research ratings only.
- Preserve required evidence discipline:
  - skills/plugins are data-input nodes, not reasoning authorities;
  - separate facts, inferences, and assumptions;
  - mark failed or insufficient data nodes explicitly;
  - keep Boss Decision Page first for published reports;
  - preserve two-hop evidence linking.

### Out of Scope

- Bulk rewrite of all nine agents in this step.
- Changing the core directed pipeline.
- Changing required weekly brief counts.
- Adding or installing new skills/plugins.
- Connecting to broker or paper-trading APIs.

## Agent Examples

### Intent Router

`agents/08-intent-router.md` should become the canonical example for routing agents.

Key emphasis:

- task type classification;
- selected and skipped agents;
- skill/data-node plan;
- missing inputs and defaults;
- safety boundary check;
- quality gate requirements;
- no investment judgment.

Its `Workflow` should be explicit:

1. Read the user request.
2. Classify task type.
3. Select agent path.
4. Select skill/data-node plan.
5. Identify missing inputs and defaults.
6. Check investment safety boundary.
7. Emit Intent Route Plan.

### AI Information & Sentiment Analyst

`agents/02-ai-information-sentiment-analyst.md` should become the canonical example for research input agents.

Key emphasis:

- data-node status first;
- dedupe and classify evidence by source type;
- separate fact, opinion, sentiment, developer signal, paper signal, and market narrative;
- produce required counts:
  - 10 AI technology news items;
  - 5 AI academic papers;
  - 5 AI open-source projects;
  - 5 high-signal sentiment evidence items;
- generate current observed story and long-horizon story, with fact/inference/hypothesis labels;
- hand off questions to Fundamental, Technical, Reflection, and Final Trend agents.

Its `Workflow` should be explicit:

1. Record data-node status.
2. Collect and normalize evidence.
3. Deduplicate and filter for AI/public-market relevance.
4. Classify evidence by source type and signal type.
5. Cluster narrative themes.
6. Build current observed story.
7. Build long-horizon projection with labels.
8. Produce downstream questions.

## Alternative Approaches Considered

### Standard Only

This is safest and avoids touching existing prompts, but it leaves the standard abstract. Future migration would still require interpretation.

### Bulk Rewrite

This completes the migration quickly, but the repository already has multiple uncommitted changes. Rewriting every agent at once would make review noisy and increase the risk of changing behavior unintentionally.

### Standard Plus Two Examples

This is the recommended path. It creates a concrete pattern while keeping the change small enough to review. After the examples are accepted, the remaining agents can be migrated mechanically.

## Migration Notes

The two example refactors should preserve all existing content that matters, especially:

- supported task types in the Intent Router;
- required output tables;
- safety boundaries;
- required source counts;
- data-node failure handling;
- two-level current-vs-long-horizon story distinction;
- no trading/account/position instructions.

The refactor may rename `Weekly User Prompt Template` to `Per-Run User Prompt Template` for consistency. If consistency with existing repo language is preferred, both names can appear as:

```markdown
## Per-Run User Prompt Template

Formerly: Weekly User Prompt Template.
```

## Verification

After implementation:

- Check the two modified agent files still contain:
  - `Role`;
  - `Profile`;
  - `Mission`;
  - `Input Sources`;
  - `Skills / Data Nodes`;
  - `Filtering Rules`;
  - `Workflow`;
  - `Output Schema`;
  - `Hard Limits`;
  - `Per-Run User Prompt Template`.
- Confirm no `Initialization` section was added.
- Confirm `agents/README.md` still points to the same prompt files.
- Confirm the quality gate and safety boundaries are not weakened.
- Run `rg -n "^## .*Initialization|^## .*初始化" agents docs/structured-agent-prompt-standard.md` and ensure no structured prompt section was added for it.
- Run `git diff -- agents/08-intent-router.md agents/02-ai-information-sentiment-analyst.md docs/structured-agent-prompt-standard.md` after implementation to review scope.

## Acceptance Criteria

- A shared prompt standard exists in `docs/structured-agent-prompt-standard.md`.
- `agents/08-intent-router.md` follows the standard.
- `agents/02-ai-information-sentiment-analyst.md` follows the standard.
- The two example prompts remain functionally equivalent or stricter than before.
- No live trading, account access, position sizing, order execution, or broker instructions are introduced.
- No required weekly brief counts or evidence-linking requirements are removed.
- No `Initialization` section appears in the new standard or example prompts.
