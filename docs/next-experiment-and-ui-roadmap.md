# Next Experiment And UI Roadmap

返回：[README](../README.md) · [AGENCY](../AGENCY.md)

## 1. 现在下一步该干嘛

现在 agent 和文档基本配齐，下一步不是继续加 skills，而是跑一个最小实验，看看链路是否真的能产出可用候选。

建议第一次实验主题：

```text
AI inference demand + hyperscaler capex + semiconductor / data center supply chain
```

建议输入：

- 高管/大佬：Jensen Huang、Lisa Su、Intel CEO、Satya Nadella、Sundar Pichai、Andy Jassy、Mark Zuckerberg、Sam Altman。
- 节目/来源：All-In、No Priors、company keynotes、earnings call clips、GTC/Computex/keynote videos。
- 市场范围：美股上市公司和 ADR。
- 可选 anchor / benchmark：NVDA、AMD、AVGO、MU、TSM、ASML、ANET、SMCI、DELL、VRT、ETN、CEG、MSFT、GOOGL、AMZN、META、ORCL。它们只用于行业参照，不默认进入候选池。

第一次运行目标不是预测，而是检查：

- Stock Discovery 能不能把候选压到 8 个以内。
- 每个候选是否有两个以上独立 signal family。
- Fundamental 是否能把叙事落到财务科目。
- Technical 是否能给出清楚失效位。
- Reflection 是否敢降级故事。
- Paper ledger 是否能记录 3-5 个观察对象。

## 2. 最小实验 Prompt

可以在新线程直接说：

```text
请读取本仓库的 AGENCY.md、README.md、docs/agent-responsibilities.md、docs/skill-registry.md、docs/weekly-brief-quality-gate.md。

本周运行一个最小实验：

主题：
- AI inference demand
- hyperscaler capex
- semiconductor / data center supply chain

高管/大佬来源：
- Jensen Huang
- Lisa Su
- Intel CEO
- Satya Nadella
- Sundar Pichai
- Andy Jassy
- Mark Zuckerberg

市场范围：
- 美股上市公司和 ADR
- 优先考虑流动性充足、信息披露充分、与 AI 产业链有明确关系的公司
- 不研究加密货币、期权、私募公司、低流动性 penny stocks

可选 anchor / benchmark：
- NVDA, AMD, AVGO, MU, TSM, ASML, ANET, SMCI, DELL, VRT, ETN, CEG, MSFT, GOOGL, AMZN, META, ORCL
- 这些 ticker 只作为行业参照和 benchmark，不默认进入候选池

要求：
- 先运行 Intent Router，输出 Intent Route Plan。
- Stock Discovery 不使用固定初始股票池，必须自己发现 10-15 个 raw candidates。
- Stock Discovery 最多筛出 8 个 active candidates。
- 再按 Route Plan 跑 AI Information & Sentiment、Fundamental、Technical、Reflection、Final Trend。
- Final Trend 必须输出研究型 action rating、confidence、预估涨幅区间、预计观察/持有周期、卖出/止盈规则和 Top 5 Research Action Pool。
- 只有 confidence >=75 且无重大 Reflection 断裂的 `Research Buy` 可以进入 Top 5。
- 用户实际选择的候选进入 Conclusion Pool。
- Top 5 / 用户选择项进入 Paper Observation Ledger，用于下周归因。
- 默认下周一 close 假设买入，下周五 close 对比实际涨幅与预估涨幅区间。
- 不输出目标价、仓位、下单或账户动作。
```

## 3. Stock Discovery 需要再加 scales 吗

短期不需要马上加。

它现在可用的核心 scales 已经够跑第一版：

- `youtube-full`
- `bibi`
- `transcript-polisher`
- `last30days`
- `longbridge-intel`
- `longbridge-market-data`
- `longbridge-research`
- `finviz`
- `tradingview`
- `nasdaq-data`
- `yahoo-finance`
- `global-stock-data`
- GitHub / arXiv / RSS 输入节点

更重要的是先验证筛选规则，而不是继续加入口。

## 4. 以后可以加的 Stock Discovery 子 agent

第一阶段先不拆子 agent。等跑 2-3 周后，如果发现 Stock Discovery 太拥挤，再拆成这些子 agent：

| 子 Agent | 负责什么 | 需要的数据 |
|---|---|---|
| Executive Signal Scout | 高管/大佬发言、播客、keynote、访谈 | YouTube, bibi, transcript |
| Capex Chain Mapper | hyperscaler capex -> 供应链映射 | filings, earnings, Longbridge, SEC |
| Developer Adoption Scout | GitHub / developer adoption / open-source infra | GitHub, last30days, arXiv |
| Catalyst Calendar Scout | 未来 30-90 天催化剂 | earnings calendar, events, product launches |
| Technical Strength Screener | AI 候选池里的相对强度和形态筛选 | Longbridge, TradingView, Yahoo |

默认不要一开始就拆。先用单一 Stock Discovery 控噪，避免系统过早复杂化。

## 5. 还需要什么 API

必须项：

- `TRANSCRIPT_API_KEY`：让 YouTube / podcast 读取稳定。
- `OPENAI_API_KEY` + `OPENAI_BASE_URL`：模型调用。

建议项：

- Longbridge CLI/MCP read-only setup：行情、K 线、基本面、research。
- `global-stock-data`：已安装，零鉴权；只需要本地 Python `requests`，作为行情/K 线/基本面/SEC filing 备份验证。
- `FINNHUB_API_KEY`：补充 company profile、earnings、news、metrics。
- `ALPHA_VANTAGE_API_KEY`：补充行情/技术/基本面，但免费额度有限。
- `FRED_API_KEY`：宏观和利率背景。
- `SEC_EDGAR_USER_AGENT`：合规访问 SEC 数据时使用。

暂不需要：

- Alpaca paper trading key。
- IBKR paper API。
- Futu/Moomoo paper trading。

这些等 shadow ledger 跑通后再接。

## 6. UI 路线图

UI 可以做，但建议作为第二阶段。

### v0 UI：静态/本地网页

目标：把每周报告、候选池、观察账本可视化。

页面：

- Dashboard：首页流程状态。
- Stock Discovery：active/watch/reject 表。
- Final Report：最终周报 markdown。
- Paper Ledger：entry/exit/return/attribution 表。
- Signal Weights：各入口权重变化。

技术选择：

- 最小版本：静态 HTML + JSON/CSV。
- 进阶版本：Next.js / React + local files。

### v1 UI：可运行实验台

目标：在网页上输入主题、股票池和时间范围，然后生成 run config。

页面：

- Run Builder。
- Source Config。
- Agent Output Viewer。
- Paper Attribution Dashboard。

### v2 UI：自动化和提醒

目标：每周自动生成 run checklist，并提醒复盘。

功能：

- 每周运行提醒。
- 数据节点状态检查。
- paper ledger 自动回看。
- Skill Scout 建议队列。

## 7. 判断 UI 是否值得做

先跑一次 CLI / 文档链路。如果你发现：

- 候选池确实有用。
- Paper Attribution 能指出错因。
- 每周想复盘而不是只读报告。

那 UI 就值得做。

如果第一次实验发现 agent 输出还很散，先优化 prompt 和 quality gate，比做 UI 更重要。
