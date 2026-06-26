# AI 美股投资研究 Agency 实施报告

生成日期：2026-06-26

## 1. 建设目标

这个 agency 的目标不是自动交易，而是替你每周读取 AI 科技信息、播客、舆情、GitHub、论文和美股数据，然后把它们组织成一份可审查的 AI 趋势投资研究报告。

核心问题：

- AI 正在往哪里发展。
- 哪些产业链环节会被影响。
- 哪些美股公司或板块可能被市场纳入叙事。
- 这个叙事是否能落到收入、利润、现金流、capex、margin、估值或预期差。
- 价格行为是否确认市场正在定价这个故事。
- 哪些部分只是远期场景推演，不能当作当前结论。

最终输出应同时包含：

- 当前观察到的 AI 趋势故事。
- 长期远演版 AI 趋势展望。
- 投资影响地图。
- 基本面验证。
- 技术面验证。
- Reflection 闭环审查。
- Cathie Wood vs Buffett 视角辩论摘要。
- Skill Scout 的建议迭加功能。

## 2. 当前已安装 Skill 栈

安装位置：`/Users/chenzhuoxin/.codex/skills`

安装来源：

- Longbridge skills: https://github.com/longbridge/skills
- Financial Data Collector: https://github.com/daymade/claude-code-skills/tree/main/financial-data-collector
- Gauss market data skills: https://github.com/gauss314/skills
- YouTube / TranscriptAPI: `youtube-full` is already installed and backed by TranscriptAPI.com
- Cathie Wood perspective: local Wood skill from `famous skills/woodSKILL.md`
- Buffett perspective: previously installed Buffett perspective skill

注意：安装新 skills 后需要重启 Codex 或开启新线程，才能让新的 skill 列表被当前会话自动识别。

### 2.1 信息与舆情

| Skill | 作用 |
|---|---|
| `last30days` | 近 30 天 Reddit、X、YouTube、HN、Polymarket、GitHub、Web 舆情 |
| `youtube-full` | TranscriptAPI-backed 主 YouTube skill，覆盖 transcript、search、channel latest、channel videos、playlist videos；配置 `TRANSCRIPT_API_KEY` 即可，不重复安装 ClawHub `transcriptapi` |
| `bibi` | 长视频、音频、播客摘要 |
| `ak-rss-digest` | 中文科技/RSS 辅助信号 |
| `transcript-polisher` | 转录稿清洗和可读化 |

### 2.2 美股市场与催化剂

| Skill | 作用 |
|---|---|
| `longbridge` | Longbridge CLI/MCP foundation，作为行情/研究数据入口 |
| `longbridge-market-data` | 实时/历史行情、K-line、资金流、市场温度、交易时段 |
| `longbridge-intel` | screener、ranking、sector rotation、ETF flow、market intelligence |
| `nasdaq-data` | Nasdaq quotes、short interest、financials、institutional holdings、insider、options、earnings、news |
| `finviz` | 美股 screener、估值、技术字段、insider、news |
| `tradingview` | scanner、技术指标、symbol search、news headline、delayed market data |
| `yahoo-finance` | quotes、historicals、fundamentals、options、news 的免费交叉验证 |

### 2.3 基本面

| Skill | 作用 |
|---|---|
| `financial-data-collector` | 美股结构化财务数据 JSON；缺失值必须标 missing，不允许 fallback |
| `longbridge-fundamentals` | 财务报表、估值、公司信息、DCF/估值数据 |
| `longbridge-earnings` | 财报前后分析、业绩 vs 预期、guidance、新闻、K-line |
| `longbridge-research` | 分析师评级、price target、EPS/revenue forecast、机构持仓、insider、short interest |
| `longbridge-value-investing` | Graham/Buffett 式质量、护城河、安全边际检查 |
| `sec-data` | SEC EDGAR / XBRL 原始财务数据 |
| `earningswhispers` | 财报电话会、earnings metadata 辅助 |
| `alpha-vantage` | API key 可用时补充 fundamentals / technical / market data |
| `finnhub` | API key 可用时补充 quote、profile、peers、earnings、metrics、news |

### 2.4 技术面与市场状态

| Skill | 作用 |
|---|---|
| `technical-analyst` | K 线结构、支撑阻力、情景、失效位 |
| `longbridge-technical` | 技术指标、K 线形态、趋势框架 |
| `longbridge-market-data` | OHLCV、K-line、成交量、价格数据 |
| `tradingview` | scanner 和技术指标 |
| `yahoo-finance` | OHLCV 与历史价格交叉验证 |
| `cboe-data` | VIX、CBOE 指数、期权、波动率上下文 |
| `fred-macro` | 利率、treasury、VIX、宏观时间序列 |

### 2.5 Reflection

| Skill | 角色 |
|---|---|
| `cathie-wood-perspective` | AI / disruptive innovation 长周期牛派视角 |
| `buffett-perspective` | 价值、护城河、所有者收益、安全边际视角 |

它们不是事实来源，只是审查上游证据的推理镜头。

## 3. 未纳入核心的候选项

| 候选 | 当前处理 | 原因 |
|---|---|---|
| ClawHub `transcriptapi` | Reject / Duplicate | `youtube-full` 已经是 TranscriptAPI-backed YouTube skill，配置 `TRANSCRIPT_API_KEY` 即可；重复安装会增加调用混乱 |
| InvestSkill | Watch | 它是很好的美股分析框架，但默认 BUY/HOLD/SELL 需要二次改造成研究型 action rating，并禁止目标价、仓位、下单和账户动作 |
| OpenClaw `finance-data` | Watch | 和 `financial-data-collector` + `yahoo-finance` + `sec-data` 重复，暂不增加复杂度 |
| `alpha-skills` momentum / breadth / bubble detector | Watch | 有市场状态价值，但交易色彩更重，部分 repo 热度未达到当前 Skill Scout benchmark |
| broker / portfolio / auto-trader skills | Reject | 会引入下单、账户、仓位、自动交易风险 |

## 4. Agent 链路与职责

### 4.1 Harness Agent

Harness Agent 是编排器，不是投资分析师。

职责：

- 加载正确的 agent prompt。
- 按固定顺序运行 section。
- 传递必要上游材料。
- 强制数据节点状态表。
- 强制质量门槛。
- 阻止 unsupported conclusion 进入最终报告。

禁止：

- 编造缺失数据。
- 把舆情当财务证明。
- 把 K 线强势当基本面证明。
- 输出买卖指令、目标价、仓位、下单或账户动作。

### 4.2 AI Information & Sentiment Analyst

职责：

- 读取 RSS/news、YouTube/播客、last30days、GitHub、arXiv、market news/intel。
- 产出 10 条 AI 技术新闻、5 篇论文、5 个开源项目、5 条高信号舆情证据。
- 把零散信息串成“当前观察版趋势故事”。
- 把远期可能性串成“长期远演版趋势故事”。
- 输出 AI 产业链外推图。

关键边界：

- 可以想得远，但必须标注事实、推断、长期假设。
- 可以写上游、上上游、冷却、电力、数据中心、自动化、机器人等二三阶影响。
- 不能把“可能受益”写成“股票会涨”。

### 4.3 Fundamental Analyst

职责：

- 检验候选叙事是否能落到财务科目。
- 每家公司必须给出：叙事 -> 财务科目 -> 估值/预期差。
- 至少用两个独立来源交叉验证关键财务指标。
- 区分直接受益、间接受益、估值叙事受益、潜在受损。

关键数据：

- SEC/公司文件优先。
- Longbridge、Nasdaq、Financial Data Collector、Yahoo/Finviz/Finnhub/Alpha Vantage 做交叉验证。
- 冲突不静默处理，必须写成 partial。

### 4.4 Technical Analyst

职责：

- 第一轮只看图表，不引用新闻、基本面、舆情或趋势叙事。
- 读取 OHLCV、K-line、成交量、均线、支撑阻力、指标。
- 输出 trend state、key levels、volume/MA read、bull/base/bear scenarios、invalidation。

关键边界：

- 图表支持叙事，不证明叙事。
- 第二轮可以解释“市场是否可能在定价某个故事”，但必须把 chart signal 和 narrative explanation 分开。
- 不输出买卖指令，不给仓位建议。

### 4.5 Reflection Judge

职责：

- 审查闭环：AI 信息 -> 舆情叙事 -> 产业影响 -> 公司基本面 -> 估值/预期差 -> 技术面 -> 可证伪指标。
- 单独审查当前观察版故事。
- 单独审查长期远演版故事。
- 检查产业链外推有没有跳过中间机制。
- 运行 Cathie Wood vs Buffett 辩论。

关键边界：

- 不新增事实。
- 不因为多个 agent 都乐观就乐观。
- 最重要任务是找断裂点。

### 4.6 Final AI Trend Narrative Analyst

职责：

- 在上游 section 完成后，输出最终 AI 趋势投资研究结论。
- 分开输出当前观察到的 AI 趋势故事和长期远演版 AI 趋势展望。
- 保留、降级或暂缓每个故事。
- 输出投资影响地图、反证条件、下周验证重点。

关键边界：

- 长期远演可以有想象力，但只能写成场景推演或观察清单。
- 高置信度必须得到信息/舆情、基本面、技术面和 Reflection 共同支持。

### 4.7 Skill Scout

职责：

- 每周检查 GitHub skills、agent skills、MCP/plugin 工具。
- 只推荐尚未安装且达到 benchmark 的候选。
- 审查权限、安装方式、是否会读取密钥、是否会自动交易或修改账户。

输出只进入“建议迭加功能”附录，不进入投资结论。

## 5. 报告产出结构

```text
RSS / YouTube / Podcasts / last30days / GitHub / arXiv / market intel
  -> AI Information & Sentiment Section
     -> Current observed story
     -> Long-horizon scenario story
     -> AI value-chain expansion map
  -> Fundamental Section
  -> Technical Section
  -> Reflection Section
     -> Cathie Wood vs Buffett debate
  -> Final AI Trend Narrative Conclusion
  -> Weekly Brief Quality Gate
  -> Skill Scout Appendix
```

## 6. 质量门槛

报告必须通过以下检查：

- 10 条 AI 技术新闻。
- 5 篇 AI 学术论文。
- 5 个 AI 开源项目。
- 5 条高信号舆情证据。
- 每条计数证据必须有来源、日期或范围、链接。
- 每个数据节点必须标记 success / partial / failed。
- 当前观察版故事必须有证据。
- 长期远演版故事必须标注事实 / 推断 / 长期假设。
- 基本面关键指标必须尽可能双源验证。
- 技术面必须记录数据源、周期、时间戳、延迟状态。
- Reflection 必须指出最弱一环。
- Wood/Buffett 辩论必须只使用上游事实，不新增事实。
- 最终结论可以输出研究型 action rating、置信度和 Top 5 Research Action Pool；不得输出目标价、仓位、下单或账户动作。

## 7. 资深研究视角把关

### 7.1 股票研究员视角

优点：

- 链路把舆情和基本面拆开，避免“热点即业绩”的常见错误。
- 基本面 agent 明确要求叙事落到财务科目，方向正确。
- SEC/Longbridge/Yahoo/Nasdaq 多源交叉验证能显著减少数据幻觉。

需要注意：

- AI 产业链很长，不能只看 Nvidia/云厂商。要强制覆盖 direct, upstream, second-order, potential losers。
- 需要在每周报告里写“这个故事下一次应该看什么财务指标”，否则报告会停在漂亮叙事。

已迭代：

- 增加了“数据源交叉验证”表。
- 增加了“可证伪指标”作为基本面必填项。

### 7.2 技术分析员视角

优点：

- 技术面第一轮图表隔离，能防止叙事污染读图。
- 强制 key levels、scenario、trigger、invalidation，比简单看多/看空更专业。

需要注意：

- 免费数据常有 15 分钟或更长延迟，必须记录数据时间。
- 周线和日线有时结论冲突，必须分周期。

已迭代：

- 增加数据源状态、时间戳、延迟状态。
- 明确第二轮才允许解释技术面和叙事之间的关系。

### 7.3 量化交易员视角

优点：

- 数据节点状态表和 partial/fail 机制很好，适合未来做自动化。
- Skill Scout 独立于投资结论，可以防止系统随意扩张。

需要注意：

- 目前还不是量化交易系统，不能输出策略和仓位。
- 如果未来要加入因子或回测，必须单独建立 research sandbox，不能和当前 weekly brief 混在一起。

已迭代：

- 明确拒绝 broker / auto-trader / position sizing 类 skills。
- 把 market regime 只作为上下文，不让它替代公司证据。

### 7.4 投资大佬视角

优点：

- Cathie Wood 和 Buffett 的冲突非常适合 AI 主题投资：一个负责逼系统看长期非线性扩散，一个负责逼系统看现金流、护城河和安全边际。
- Reflection 不新增事实，只审上游证据，这个边界很关键。

需要注意：

- 长期远演必须存在，否则 AI 趋势研究会太短视。
- 远期展望也必须有纪律，否则会变成科幻叙事。

已迭代：

- 增加“当前观察版”和“长期远演版”双故事结构。
- 增加 Reflection 对长期远演和产业链外推的审查。

## 8. 最终一次性通过版本

我建议当前版本作为 v0.1 通过，理由：

- Agent 角色清楚。
- 美股数据 skills 已补齐核心读取能力。
- 舆情、基本面、技术面、Reflection 的边界清楚。
- 长期远演能力已经加入，但有证据/推断/假设标签。
- Wood/Buffett 辩论被放在正确位置：Reflection，而不是数据采集层。
- Skill Scout 独立，不会污染投资结论。
- No trade / no account / no target price / no position sizing 的边界明确。

剩余建议：

- 下一阶段再考虑是否安装 `longbridge-content`，用于更系统的新闻/filing/topic 内容抓取。
- 等你确认 API key 后，测试 `alpha-vantage`、`finnhub`、`fred-macro` 是否能正常返回数据。
- 如果未来想要量化模块，单独新建 Quant Research Agent，不要直接放进 Technical Analyst。

## 9. 下一步

如果你回复 `OK`，下一步可以执行：

1. 创建或切换到 GitHub 推送用分支。
2. 检查 `.env` 未被 staged。
3. 将 README、AGENCY、agents、docs、`.env.example` 提交。
4. 推送到你的 GitHub repository。
5. 如果你要新建 GitHub repo 或 GitHub Project，再按你的仓库目标执行。

当前版本已经准备好进入人工审阅。
