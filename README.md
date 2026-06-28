# AI 美股投资研究 Agency

> **一句话介绍**
>
> 这个项目不是一个“AI 自动选股工具”，而是一套由 9 个 agent 组成的 AI 美股投研工作流，专门研究 AI 产业趋势如何传导到美股公司。它会把新闻、论文、GitHub 开源项目、YouTube/播客、社区舆情、财报、SEC 文件和技术面数据，分别交给 Intent Router、Stock Discovery、AI Information & Sentiment、Fundamental、Technical、Reflection、Final Trend Narrative、Paper Portfolio & Attribution、Skill Scout 这 9 个 agent 处理，最后汇总成一份中文投资研究周报。它和普通投研笔记不一样的地方在于，不是追热点喊买卖，而是强制每个结论都有证据链、反证条件和下周复盘；主报告先给一页老板能看懂的 Top 5 决策页，长证据放到独立 evidence 文件里。比较巧的是，它把“AI 叙事”拆成一条可审查的流水线：先控噪筛候选，再验证信息、基本面和技术面，最后用 Cathie Wood vs Buffett 两种视角做反方审查，并用模拟观察账本记录下周结果，反过来校准自己的信号质量。它更像一个会复盘、会自我质疑的 AI 投研团队，而不是一个喊买卖的黑盒。

## 产品架构图：把 AI 投研从“生成答案”变成“可审计流水线”

```mermaid
flowchart TD
    U["研究意图 / 前端输入"] --> H["Harness Graph Orchestrator<br/>StateGraph 优先，本地图执行器兜底"]

    H --> P["模型网关预检<br/>API key / model / base URL"]
    P --> D["Data Node Evidence Bundle<br/>先采集事实，再让 agent 判断"]

    D --> N1["AI 新闻<br/>10 条目标"]
    D --> N2["论文 / arXiv<br/>5 篇目标"]
    D --> N3["GitHub 开源项目<br/>5 个目标"]
    D --> N4["舆情 / 信息强度<br/>5 条目标"]
    D --> N5["行情 / 技术面<br/>Yahoo / quotes"]
    D --> N6["基本面 / SEC / 宏观<br/>Finnhub / EDGAR / FRED"]

    D --> R["Intent Router<br/>决定本次跑全链路还是窄任务"]
    R --> S["Stock Discovery<br/>控噪筛候选，默认最多 8 个"]
    S --> I["AI Info & Sentiment<br/>验证 AI 叙事是否真实升温"]
    I --> F["Fundamental<br/>检查收入、利润率、现金流、capex、估值传导"]
    I --> T["Technical<br/>只看价格、量能、相对强弱和关键位"]
    F --> X["Reflection<br/>Cathie Wood vs Buffett 双视角反方审查"]
    T --> X
    X --> C["Final Narrative<br/>收束成 Version A 老板决策页"]
    C --> A["Paper Portfolio & Attribution<br/>只做 shadow ledger 复盘，不连实盘"]

    C --> O1["老板决策页<br/>一句话结论 / Top 5 / 最大反证 / 下周只看"]
    C --> O2["Evidence Pack<br/>主报告 -> evidence 子文件 -> 原始来源"]
    C --> O3["Agent Visible Trace<br/>每个 agent 的公开判断、数据节点、缺口和下一步"]
    A --> O4["反馈闭环<br/>下周复盘 thesis 是否成立，校准信号质量"]

    D -.节点失败或数据不足.-> G["质量闸门<br/>partial / No Rating / 不硬凑 Top 5"]
    G --> C

    classDef input fill:#182232,stroke:#7dd3fc,color:#f8fafc;
    classDef graph fill:#1e293b,stroke:#a78bfa,color:#f8fafc;
    classDef data fill:#123524,stroke:#86efac,color:#f8fafc;
    classDef agent fill:#312e81,stroke:#c4b5fd,color:#f8fafc;
    classDef output fill:#3b2414,stroke:#fdba74,color:#f8fafc;
    classDef gate fill:#3f1d2e,stroke:#f9a8d4,color:#f8fafc;

    class U input;
    class H,P graph;
    class D,N1,N2,N3,N4,N5,N6 data;
    class R,S,I,F,T,X,C,A agent;
    class O1,O2,O3,O4 output;
    class G gate;
```

面试时可以这样讲这个项目的巧思：

- **我没有让 LLM 直接写投资结论，而是把投研拆成可控图工作流**：数据节点先采集事实，agent 再按角色分工判断，最后由 Harness 统一组装报告。
- **每个结论都有降级机制**：如果新闻、论文、GitHub、行情、基本面或舆情节点不足，系统会明确标 `partial / No Rating`，不会为了好看硬凑 Top 5。
- **报告结构服务决策者，而不是服务模型炫技**：第一页永远是老板决策页，长证据放 evidence pack，既能快速读结论，也能追溯每条证据。
- **它有复盘闭环**：研究动作进入 shadow ledger，下周用价格和 thesis 归因回看信号质量，让系统不是一次性生成器，而是会自我校准的投研流程。
- **工程上有稳定交付设计**：LangGraph 可用时走 `StateGraph`，不可用时走本地图执行器；section 超时或数据节点失败不会拖垮整份报告。

## 这个项目解决什么问题

AI 投资信息源很分散：新闻、发布会、YouTube、播客、GitHub、arXiv、财报、SEC 文件、K 线和社区讨论经常同时影响市场叙事。

这个仓库把这些输入拆给不同 agent 处理，并用一个 Harness Agent 串起来：

- 先判断本次任务该跑完整周报，还是只跑选股、基本面、技术面、归因或维护任务。
- 先控噪筛候选，再做信息、基本面、技术面和反思审查。
- 把证据和推断分开，把短期观察和长期假设分开。
- 把核心结论放在报告第一页，把长证据表放到独立 evidence 文件。
- 用 shadow ledger 记录研究结果，方便下周复盘信号是否有效。

## 最终产出

一次完整周报会生成：

- **老板决策页**：第一屏直接给结论、Top 5、研究动作、最大反证和下周验证点。
- **Top 5 Research Action Pool**：最多 5 个研究候选，包含 rating、置信度、预估涨幅区间、观察周期和退出/止盈规则。
- **Evidence Pack**：主报告只放证据摘要；完整证据链写到同名 `*.evidence.md` 子文件。
- **AI 信息模块**：10 条 AI 技术新闻、5 篇论文、5 个开源项目、5 条高信号舆情证据。
- **基本面与技术面验证**：检查叙事是否能落到收入、利润、现金流、capex、margin、估值或预期差。
- **Reflection 审查**：用闭环审查和 Cathie Wood vs Buffett 视角辩论暴露最弱环节。
- **Paper Portfolio & Attribution**：只做模拟观察和信号归因，不连接真实交易账户。

## 核心流程

```mermaid
flowchart TD
    U["User Request"] --> R["Intent Router"]
    R --> D["Stock Discovery"]
    D --> I["AI Information & Sentiment"]
    I --> F["Fundamental"]
    I --> T["Technical"]
    F --> X["Reflection"]
    T --> X
    X --> C["Final Trend Narrative"]
    C --> P["Paper Portfolio & Attribution"]
    P --> Q["Weekly Brief Quality Gate"]
    Q --> S["Skill Scout Appendix"]
```

运行顺序是固定的 directed pipeline，不是 agent 圆桌讨论。任何周报、实验或单 section 研究都必须先跑 `agents/08-intent-router.md`，但发布报告必须从老板决策页开始，Route Plan 放到附录。

## 快速开始

### 1. 配置环境变量

复制示例配置：

```bash
cp .env.example .env
```

然后在 `.env` 中填入你本地可用的 key。常用变量包括：

| 类型 | 变量 |
|---|---|
| LLM 网关 | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| 视频/转录 | `TRANSCRIPT_API_KEY`, `BIBI_API_TOKEN` |
| 市场与基本面 | `ALPHA_VANTAGE_API_KEY`, `FINNHUB_API_KEY`, `FRED_API_KEY`, `SEC_EDGAR_USER_AGENT` |
| 研究搜索 | `PERPLEXITY_API_KEY`, `OPENROUTER_API_KEY`, `SCRAPECREATORS_API_KEY` |

最小 `.env` 示例：

```bash
# LLM gateway
OPENAI_API_KEY=your_openai_compatible_key
OPENAI_BASE_URL=https://api.viviai.cc/v1
OPENAI_MODEL=gpt-5.5

# YouTube / podcast transcript
TRANSCRIPT_API_KEY=your_transcriptapi_key_starts_with_sk

# Market and fundamentals data
FINNHUB_API_KEY=your_finnhub_key
FRED_API_KEY=your_fred_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
SEC_EDGAR_USER_AGENT="Your Name your.email@example.com"

# Optional sentiment / search helpers
SCRAPECREATORS_API_KEY=your_scrapecreators_key
PERPLEXITY_API_KEY=your_perplexity_key
OPENROUTER_API_KEY=your_openrouter_key

# Research feedback mode
PAPER_TRADING_MODE=shadow_ledger
```

完整说明见 [docs/api-configuration.md](docs/api-configuration.md)。

### 2. 在 Codex 新线程中运行周报

让 Codex 读取这些文件：

- [AGENCY.md](AGENCY.md)
- [docs/ai-investment-agent-system.md](docs/ai-investment-agent-system.md)
- [docs/weekly-brief-quality-gate.md](docs/weekly-brief-quality-gate.md)
- [docs/research-report-output-standard.md](docs/research-report-output-standard.md)
- [docs/skill-registry.md](docs/skill-registry.md)

然后发起类似任务：

```text
按 AGENCY.md 跑本周 AI 美股投资研究周报。
必须先运行 Intent Router，最终报告从老板决策页开始，证据使用双跳链接。
```

如果只想跑某个模块，也先让 Intent Router 判断路线，例如：

```text
只跑本周 AI infra 股票发现，不生成完整周报。
```

## 关键规则

- Skills 和 plugins 只作为数据输入节点，不是最终推理权威。
- 投资输出保持 research-oriented；可以给研究动作 rating，但不能给下单、仓位、自动交易或券商操作指令。
- 美股金融数据栈只读使用，不请求交易权限，不读取私人账户数据。
- 每个投资判断都要区分事实、推断和假设。
- 长期远演必须和当前观察分开写。
- 数据节点失败或返回不足时必须显式标记 `partial` 或 `failed`，不能编造补齐。
- Published report 使用双跳证据链接：主报告 -> evidence 子文件 -> 原始来源。
- 默认中文输出，除非任务明确要求英文。

## Agent 目录

| Agent | Prompt | 职责 |
|---|---|---|
| Intent Router | [agents/08-intent-router.md](agents/08-intent-router.md) | 判断任务类型、执行路径、skills/data nodes、缺失配置和质量门槛 |
| Stock Discovery | [agents/00-stock-discovery-analyst.md](agents/00-stock-discovery-analyst.md) | 发现候选股票，默认最多 8 个 active candidates |
| AI Information & Sentiment | [agents/02-ai-information-sentiment-analyst.md](agents/02-ai-information-sentiment-analyst.md) | 新闻、论文、GitHub、YouTube、播客和舆情证据 |
| Fundamental | [agents/03-fundamental-analyst.md](agents/03-fundamental-analyst.md) | 财报、SEC、估值、预期差和财务传导链 |
| Technical | [agents/04-technical-analyst.md](agents/04-technical-analyst.md) | 图表优先的价格行为、支撑阻力和技术情景 |
| Reflection | [agents/05-reflection-judge.md](agents/05-reflection-judge.md) | 闭环审查，含 Cathie Wood vs Buffett 视角辩论 |
| Final Trend Narrative | [agents/01-ai-trend-narrative-analyst.md](agents/01-ai-trend-narrative-analyst.md) | 生成最终 AI 趋势投资研究结论 |
| Paper Portfolio & Attribution | [agents/07-paper-portfolio-attribution-agent.md](agents/07-paper-portfolio-attribution-agent.md) | shadow ledger、下周复盘和信号归因 |
| Skill Scout | [agents/06-skill-scout.md](agents/06-skill-scout.md) | 维护型 agent，推荐低风险只读 skills/plugins |

更完整的职责说明见 [docs/agent-responsibilities.md](docs/agent-responsibilities.md)。

## 仓库结构

```text
.
├── AGENCY.md                         # Harness Agent 主运行手册
├── AGENTS.md                         # 项目级规则
├── agents/                           # 每个 agent 的系统 prompt 和用户 prompt 模板
├── docs/                             # 系统设计、质量门槛、skill registry、配置文档
├── data/
│   ├── conclusion-pool/              # 用户选择观察的结论池模板
│   └── paper-portfolio/              # shadow ledger / 模拟观察模板
└── reports/                          # 已生成的研究报告和 evidence 子文件
```

## 质量门槛

完整周报必须通过 [docs/weekly-brief-quality-gate.md](docs/weekly-brief-quality-gate.md)。最低要求包括：

| 模块 | 要求 |
|---|---|
| Intent Route Plan | 任务类型、选中/跳过 agents、skill plan、缺失输入、安全边界 |
| Stock Discovery | active candidates 默认不超过 8 个 |
| AI 新闻 | 10 条，含标题、来源、日期和链接 |
| AI 论文 | 5 篇，含标题、作者/机构、日期和链接 |
| AI 开源项目 | 5 个，含 repo、链接和 stars/benchmark 证据 |
| 高信号舆情 | 5 条，含平台、主题、日期/范围和链接 |
| Top 5 Pool | 最多 5 个，每个含 rating、置信度、证据、失效条件、预估涨幅区间、观察周期和退出规则 |
| Evidence Pack | 每个核心候选从主报告链接到同名 evidence 子文件，再链接到原始来源 |
| Downstream Handoff | 每个执行 agent 说明下游应继承什么、缺什么、何时降级、哪些内容不能带入下一环 |

如果数据源不足，报告必须说明哪个输入节点失败或不足，不能用想象内容补齐数量。

## 安全边界

允许：

- 研究型 `Research Buy / Hold-Watch / Take-Profit / Trim Bias / Avoid-Sell Bias / No Rating`
- 置信度、反证条件、下周验证点
- 模拟观察池、shadow ledger、benchmark 归因

禁止：

- 真实下单、自动交易、再平衡、券商账户操作
- 个性化仓位比例、资金分配或账户建议
- 把舆情热度当作财务改善证明
- 把 perspective skills 当作事实来源
- 在数据节点失败时编造新闻、论文、项目、财务数据或链接

## 重要文档

- [AGENCY.md](AGENCY.md)：主 Harness Agent 运行手册。
- [AGENTS.md](AGENTS.md)：项目级规则。
- [agents/README.md](agents/README.md)：agent prompt 索引。
- [docs/ai-investment-agent-system.md](docs/ai-investment-agent-system.md)：系统设计。
- [docs/research-report-output-standard.md](docs/research-report-output-standard.md)：最终报告三种结构、公开格式约束和 agent handoff 契约。
- [docs/agent-responsibilities.md](docs/agent-responsibilities.md)：agent 职责、输入、输出和边界。
- [docs/skill-registry.md](docs/skill-registry.md)：skill/data node 用途、降级和禁止用途。
- [docs/weekly-brief-quality-gate.md](docs/weekly-brief-quality-gate.md)：最终周报验收标准。
- [docs/api-configuration.md](docs/api-configuration.md)：API 和模型配置。
- [docs/noise-control-and-paper-portfolio-loop.md](docs/noise-control-and-paper-portfolio-loop.md)：控噪和模拟观察闭环。
- [data/conclusion-pool/README.md](data/conclusion-pool/README.md)：结论池协议。
- [data/paper-portfolio/README.md](data/paper-portfolio/README.md)：paper portfolio / shadow ledger 协议。

## 当前状态

当前版本：`v0.4-research-action-pool`

已具备：

- 完整多 Agent prompt 结构。
- 周报质量门槛。
- 双跳证据链接规范。
- Top 5 Research Action Pool 规则。
- Conclusion Pool 和 Paper Portfolio 复盘闭环。
- Skill Scout 维护机制。

下一步路线见 [docs/next-experiment-and-ui-roadmap.md](docs/next-experiment-and-ui-roadmap.md)。
