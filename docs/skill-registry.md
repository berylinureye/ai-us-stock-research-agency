# Skill Registry

返回：[README](../README.md) · [AGENCY](../AGENCY.md) · [Agent Index](../agents/README.md)

这份 registry 说明当前 agency 里每个 skill / data node 的用途、归属 agent、输入输出、配置要求、失败降级方式和禁止用途。

总规则：

- Skills 是数据输入节点或 reasoning lens，不是最终判断权威。
- 每次使用 skill 都要记录状态：`success / partial / failed / not applicable`。
- 如果 skill 没有返回足够数据，不能编造补齐。
- 如果 API key 缺失，相关节点标为 `partial` 或 `failed`。
- Broker、order、position sizing、auto-trading、account action 类能力禁止进入核心研究链路。
- Skill Scout 可以自动安装低风险候选，但仅限已通过 benchmark、README/SKILL 审查、且无交易/账户/隐私权限的只读数据或 reasoning skills；安装结果必须记录在维护附录。

## 1. 信息与舆情 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `last30days` | Stock Discovery; AI Information & Sentiment | 近 30 天跨平台舆情、社区讨论、市场叙事 | 主题、ticker、公司、关键词 | Reddit/X/YouTube/HN/GitHub/Web 等讨论摘要和链接 | 通常无需单独 key，按 skill 实际配置 | 强推荐 | 标为 `partial`，只使用 RSS/YouTube/GitHub/arXiv/market news | 不能把热度当事实或财务证明 |
| `ak-rss-digest` | AI Information & Sentiment | 中文 AI/科技 RSS 和文章摘要 | RSS 源、主题、数量 | 中文科技信息摘要 | 需要本地 RSS 源配置 | 可选但推荐 | 标为 `partial`，改用 web/RSS/news 其他来源 | 不能替代原始链接核查 |
| RSS/news | AI Information & Sentiment | AI 技术新闻、公司博客、行业新闻 | 媒体源、关键词、日期范围 | 新闻标题、日期、链接、摘要 | 取决于实际抓取方式 | 必需模块 | 新闻数量不足时写明缺口 | 不能无链接计入 10 条新闻 |
| GitHub search | Stock Discovery; AI Information & Sentiment; Skill Scout | 开源项目、developer adoption、skill 候选搜索 | query、排序、数量、stars/forks | repo、stars、README、release、issues | 可用公开搜索；高频可能需要 GitHub token | 必需模块 | 项目数量不足时写明缺口 | GitHub 热度不能直接等同公司收入 |
| arXiv search | AI Information & Sentiment | AI 学术论文方向 | search query、数量、排序 | 论文标题、作者/机构、日期、链接、方向 | 通常无需 key | 必需模块 | 论文数量不足时写明缺口 | 论文不能直接等同商业机会 |

## 2. YouTube / 播客 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `youtube-full` | Stock Discovery; AI Information & Sentiment | TranscriptAPI-backed YouTube 搜索、字幕、频道、playlist、评论上下文 | 视频 URL、频道、playlist、关键词 | transcript、视频元数据、频道/playlist 结果 | 需要 `TRANSCRIPT_API_KEY` | 强推荐 | 标为 `partial`，改用 show notes、新闻稿、其他摘要 | 不要重复安装同功能 `transcriptapi`；不能把嘉宾观点当事实 |
| `bibi` | Stock Discovery; AI Information & Sentiment | 长视频/音频/播客快速摘要 | 视频/音频链接、文件或文本 | 摘要、章节、要点 | 可能需要 `BIBI_API_TOKEN` 或本地配置 | 推荐 | 标为 `partial`，只使用可取得的 transcript 或人工摘要 | 摘要不能替代原文证据 |
| `transcript-polisher` | Stock Discovery; AI Information & Sentiment | 清洗和精修转录稿 | 粗转录文本 | 可读 transcript、段落、要点 | 无固定 key | 可选 | 使用原始 transcript 并标注质量限制 | 不能独立生成没有来源的观点 |

## 3. 美股市场与催化剂 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `longbridge` | Stock Discovery; Fundamental; Technical; Paper Attribution | Longbridge read-only 总入口 | ticker、市场、日期范围 | quote、市场数据、公司数据入口 | 需要 Longbridge CLI/MCP read-only 授权 | 推荐 | 用 Yahoo/Finviz/Nasdaq/TradingView 交叉替代 | 不请求交易权限，不下单 |
| `longbridge-market-data` | Stock Discovery; Technical; Paper Attribution | 实时/历史行情、K-line、成交量、entry/exit price | ticker、时间周期 | OHLCV、quote、K-line | Longbridge read-only | 强推荐 | 用 Yahoo/TradingView 交叉验证，标 `partial` | 不能执行订单 |
| `longbridge-intel` | Stock Discovery; AI Information & Sentiment; Paper Attribution | 市场异动、sector rotation、catalyst、market intelligence | ticker、板块、日期范围 | 市场注意力、催化剂、ranking | Longbridge read-only | 推荐 | 改用 Finviz/Nasdaq/news | 不能把市场热度当基本面证明 |
| `longbridge-research` | Stock Discovery; Fundamental | 分析师评级、一致预期、机构、insider、short interest 背景 | ticker | analyst、forecast、holdings、short interest | Longbridge read-only | 推荐 | 改用 Nasdaq/Finviz/Yahoo | 不输出 price target 作为建议 |
| `nasdaq-data` | Stock Discovery; Fundamental; AI Information & Sentiment; Paper Attribution | Nasdaq financials、quotes、short interest、institutional、insider、news | ticker | quotes、financials、news、holdings | 通常公开接口 | 推荐 | 改用 SEC/Yahoo/Finviz | 不把 delayed quote 当实时 |
| `finviz` | Stock Discovery; Fundamental; Technical; Paper Attribution | Screener、估值、技术字段、insider、news 辅助 | ticker 或筛选条件 | screener 表、估值、技术、新闻 | 通常无需 key | 推荐 | 改用 Nasdaq/Yahoo/TradingView | 第一轮技术分析不得用新闻解释走势 |
| `yahoo-finance` | Stock Discovery; Fundamental; Technical; Paper Attribution | 免费行情、历史价格、财务、options、news 交叉验证 | ticker、时间范围 | OHLCV、quote、财务、新闻 | 通常无需 key | 推荐 | 改用 Longbridge/TradingView/Nasdaq | 不作为唯一关键财务来源 |
| `global-stock-data` | Stock Discovery; Fundamental; Technical; Paper Attribution | 零鉴权美股/港股 quote、K-line、技术指标、基本面、SEC filing、全市场列表备份验证 | ticker、市场、date range、indicator、filing type | quote、OHLCV、MA/MACD/RSI/KDJ/布林带、财务指标、SEC filing、market list | 无 key；需要 Python `requests` | 推荐 | 改用 Longbridge/Yahoo/Nasdaq/TradingView；标 `partial` | 不作为重大财务结论唯一来源；不下单、不做账户动作 |
| `tradingview` | Stock Discovery; Technical; Paper Attribution | 技术指标、scanner、图表/行情辅助 | ticker、市场、周期 | 技术指标、scanner、价格 | 取决于 skill 配置 | 推荐 | 改用 Longbridge/Yahoo/Finviz | 不输出交易指令 |

## 4. 基本面 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `financial-data-collector` | Fundamental | 美股结构化财务数据 | ticker | JSON 财务数据、缺失值标记 | 取决于 skill 配置 | 强推荐 | 改用 SEC/Longbridge/Nasdaq/Yahoo | 不允许 silent fallback 或编造 missing |
| `longbridge-fundamentals` | Fundamental | 财务报表、估值、公司信息 | ticker | income statement、balance sheet、cash flow、valuation | Longbridge read-only | 强推荐 | 用 SEC/Nasdaq/Yahoo 交叉替代 | 不请求交易权限 |
| `longbridge-earnings` | Fundamental | 财报前后摘要、guidance、分部、业绩 vs 预期 | ticker、财报期 | earnings summary、guidance、segment commentary | Longbridge read-only | 推荐 | 改用 earningswhispers、公司 IR、SEC | 不能把摘要当原始财报全文 |
| `longbridge-value-investing` | Fundamental; Reflection context | Graham/Buffett 式质量、护城河、安全边际检查框架 | ticker、财务指标 | 价值纪律分析 | Longbridge read-only | 可选 | 仅保留传统基本面检查 | 不能替代财务事实或输出买卖建议 |
| `sec-data` | Fundamental | SEC EDGAR/XBRL 原始财务数据交叉验证 | ticker/CIK、filing type | 10-K/10-Q/8-K、XBRL facts | 需要 `SEC_EDGAR_USER_AGENT` | 强推荐 | 标 `partial`，使用公司 IR/Longbridge/Nasdaq | 不忽略 SEC 与第三方冲突 |
| `earningswhispers` | Fundamental | 财报日期、电话会、earnings metadata 辅助 | ticker | earnings date、call metadata、部分 transcript | 取决于 skill 配置 | 可选 | 用公司 IR / Nasdaq / Longbridge | 不把 whisper 当事实 |
| `alpha-vantage` | Fundamental; Technical context | 行情、技术、基本面 API 补充 | ticker、function | time series、overview、indicators | 需要 `ALPHA_VANTAGE_API_KEY` | 可选 | 标 `partial`，用 Yahoo/Longbridge | 免费额度有限，不强行补齐 |
| `finnhub` | Fundamental; Stock Discovery | company profile、metrics、earnings、news 补充 | ticker | metrics、profile、news、earnings | 需要 `FINNHUB_API_KEY` | 可选 | 标 `partial`，用 SEC/Nasdaq/Yahoo | premium-gated 数据不能假装可用 |

## 5. 技术面与市场状态 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `technical-analyst` | Technical | K 线结构、支撑阻力、情景和失效位 | ticker、图表、OHLCV、周期 | 趋势、关键价位、情景、失效位 | 无固定 key | 强推荐 | 如果没有图表数据，要求补数据或标 `partial` | 不输出买卖指令或仓位 |
| `longbridge-technical` | Technical | 技术指标、K 线形态、趋势框架 | ticker、周期 | indicators、patterns、technical summary | Longbridge read-only | 推荐 | 改用 TradingView/Yahoo | 第一轮不得混入新闻解释 |
| `cboe-data` | Technical; Paper Attribution | VIX、CBOE 指数、期权/波动率背景 | index、date range | volatility、market risk context | 公开/skill 配置 | 可选 | 用 FRED/Yahoo 指数代理 | 不能替代个股图表判断 |
| `fred-macro` | Technical; Paper Attribution | 利率、宏观时间序列、市场 regime 背景 | series、date range | treasury、rates、macro series | 需要 `FRED_API_KEY` 时更稳定 | 可选 | 标 `partial`，只用可得市场 proxy | 宏观不能覆盖公司证据 |

## 6. Reflection Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `cathie-wood-perspective` | Reflection | AI 长周期创新牛派视角，审查市场是否低估非线性扩散 | 上游 section 证据 | Wood 视角质疑/强化点 | 本地 skill | 必需于 Reflection debate | 缺失时标 `partial`，只做普通 bull case | 不能新增事实，不能直接给买入结论 |
| `buffett-perspective` | Reflection | 价值、护城河、现金流、安全边际怀疑视角 | 上游 section 证据 | Buffett 视角质疑/降级点 | 本地 skill | 必需于 Reflection debate | 缺失时标 `partial`，只做普通 value discipline | 不能因为技术复杂就自动否定 |

## 7. Paper Attribution Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| `longbridge-market-data` | Paper Portfolio & Attribution | next-Monday entry close、next-Friday review close、K-line、benchmark return | ticker、entry/review dates、benchmark | return、excess return、MFE/MAE、expected-vs-actual 基础数据 | Longbridge read-only | 强推荐 | 用 Yahoo/TradingView 交叉验证 | 不下单、不连 live account |
| `yahoo-finance` | Paper Portfolio & Attribution | 历史价格交叉验证、Monday/Friday close 验证 | ticker、date range | historical close、benchmark price | 通常无需 key | 推荐 | 用 Longbridge/TradingView | 不作为真实成交记录 |
| `tradingview` | Paper Portfolio & Attribution | 技术状态和 delayed price 交叉验证 | ticker、date range | price/technical context | 取决于 skill 配置 | 可选 | 只做价格回看，不做技术解释 | 不输出交易建议 |
| `global-stock-data` | Paper Portfolio & Attribution | next-Monday entry close、next-Friday review close、K-line 和 benchmark price 的零鉴权备份验证 | ticker、date range、benchmark | historical close、indicator context、backup quote | 无 key；需要 Python `requests` | 推荐 | 用 Longbridge/Yahoo/TradingView | 不作为真实成交记录；不连接账户 |
| `cboe-data` | Paper Portfolio & Attribution | VIX/波动率解释 market regime drag | date range | VIX / volatility context | 公开/skill 配置 | 可选 | 标 `partial` | 不把波动率当个股归因唯一原因 |
| `fred-macro` | Paper Portfolio & Attribution | 利率/宏观 regime 归因 | series、date range | macro context | `FRED_API_KEY` 推荐 | 可选 | 标 `partial` | 不做宏观绝对解释 |

## 8. Skill Scout / 维护 Skills

| Skill / Data Node | 归属 Agent | 用途 | 输入 | 输出 | API / 配置 | 必需性 | 失败降级 | 禁止用途 |
|---|---|---|---|---|---|---|---|---|
| GitHub skill search | Skill Scout | 每周检查未安装 skills/plugins/MCP，并在低风险授权范围内自动安装合格候选 | query、stars/forks benchmark、README/SKILL、当前已安装 skill 列表 | Install / Watch / Reject、安装证据、安装路径 | 可公开搜索；高频可能需要 token | 必需于 Skill Scout | 标 `partial`，只用已知 curated lists；不安装 | 不安装 broker/order/account/position-sizing/opaque installer |
| Installed skill inventory | Skill Scout; Intent Router | 判断已有能力和重复项 | 本地 skill 列表 | 当前 capability map | 本地环境 | 必需 | 如果不可读，标 `failed` 并禁止安装建议 | 不把已安装 skill 误报为缺失 |
| Curated lists | Skill Scout | awesome-agent-skills、ClawHub、skills.sh 等候选来源 | list URL、关键词 | 候选 skill 列表 | 取决于网络 | 可选 | 标 `partial` | stars 高不代表安全 |

## 9. Explicitly Forbidden Capability Classes

以下能力不进入核心 agency，除非未来单独做 sandbox/paper-only 系统并重新定义权限：

| Capability Class | 状态 | 原因 |
|---|---|---|
| Broker live trading APIs | Forbidden | 会触发真实账户和订单风险 |
| Auto-trader / order execution skills | Forbidden | 与研究型系统边界冲突 |
| Position sizing / portfolio rebalancing skills | Forbidden | 容易变成投资建议和账户动作 |
| Account data retrieval | Forbidden | 涉及隐私和交易权限 |
| `curl | bash` opaque installer skills | Reject by default | 安全风险不可审查 |

允许的替代方案：

- `shadow_ledger`：只记录假设 entry/exit price。
- `paper_api`：未来只有在用户明确批准后，且仅限 sandbox/paper account。
- read-only finance skills：只取行情、财务、研究和公开市场数据。
