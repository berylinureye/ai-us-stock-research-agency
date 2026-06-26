# 发散式 AI 美股选股实验

日期：2026-06-26  
市场范围：美股上市公司与 ADR；研究用途；不涉及真实账户、下单、仓位或目标价。  
价格数据口径：`yfinance` 日线，最近可得美股收盘为 2026-06-25。  
研究边界：不预设主题、不使用固定初始股票池；从 AI 信息流、播客、GitHub/arXiv、官方披露、市场强度和舆情反向发现候选。

# Intent Route Plan

## 用户意图判断

- Task Type：`full_weekly_brief`，以发散式 `Stock Discovery` 为核心。
- 路由置信度：高。
- 判断依据：用户要求“直接开始选股/不给限定主题”，且文档要求先跑 Intent Router，再进入候选发现和完整研究链路。

## 执行路径

| Step | Agent / Section | 是否运行 | 运行原因 | 上游输入 | 预期输出 |
|---:|---|---|---|---|---|
| 1 | Intent Router | 运行 | 新版 runbook 强制要求 | 用户请求、AGENCY、quality gate | Route Plan |
| 2 | Stock Discovery | 运行 | 不设主题，从信号入口发现候选 | 播客、新闻、GitHub/arXiv、行情、官方披露 | Raw / active / watch / reject |
| 3 | AI Information & Sentiment | 运行 | 质量门槛要求 10 新闻、5 论文、5 项目、5 舆情 | discovery candidates | 信息与趋势故事 |
| 4 | Fundamental | 运行 | 验证叙事能否落到收入、订单、现金流、capex | active candidates | 财务传导链 |
| 5 | Technical | 运行 | 检查市场价格是否支持 | active candidates OHLCV | 趋势、支撑阻力、情景 |
| 6 | Reflection | 运行 | 审查闭环，运行 Wood vs Buffett | 上游 sections | 保留/降级裁决 |
| 7 | Final Trend | 运行 | 产出老板结论页和最终排序 | 上游 sections | 结论先行研究简报 |
| 8 | Paper Portfolio | 运行 | 建立 shadow ledger，不连接 broker | final candidates | open observation ledger |
| 9 | Quality Gate / Skill Scout | 运行 | 审计与系统维护 | 全部 sections | 质量检查与维护建议 |

## 跳过的 Agent

| Agent / Section | 跳过原因 | 何时需要补跑 |
|---|---|---|
| 单点 fundamental / technical deep dive | 本次是发散式完整实验，不是单 ticker 深挖 | 用户指定单一 ticker 时 |
| live broker / paper API | 项目禁止交易与账户动作 | 未来用户明确批准 sandbox-only 时 |

## Skill / Data Node Plan

| Skill / Data Node | 用途 | 配置状态 | 本次状态 | 降级 |
|---|---|---|---|---|
| `youtube-full` / TranscriptAPI | No Priors、All-In 最新节目和 transcript | `.env` 已配置 | success | 无 |
| GitHub API | AI agent / inference / serving 项目 | public | success | 无 |
| arXiv API | AI agent / inference / reasoning 论文 | public | success | 无 |
| RSS/news/web | 官方披露、科技新闻、机构研究 | public | success | 无 |
| `yfinance` | 历史价格、技术面、benchmark | 已安装 | success | Nasdaq/Finnhub 辅助 |
| Finnhub | quote 交叉验证 | 已配置 | success | 只用免费端点 |
| Alpha Vantage | 辅助 | `.env` 变量名未按 `ALPHA_VANTAGE_API_KEY` 暴露 | partial | 未使用 |
| Longbridge | read-only 行情/研究 | CLI 缺失 | failed | yfinance/Finnhub/官方披露 |
| Wood / Buffett skills | Reflection reasoning lens | 本地可读 | success | 不作事实来源 |

## 缺失输入与默认假设

- 时间范围：默认本周与近 30 天；价格数据截至 2026-06-25 收盘。
- 主题：用户未限定；默认“AI public-market universe”。
- 股票池 / ticker：无初始池；候选由信号产生。
- API / 配置：Longbridge CLI 缺失；Alpha Vantage 变量名未按文档暴露。
- 默认假设：只研究美股/ADR、流动性较好的公开上市公司；低流动性或单源小票默认 watch/defer。

## 安全边界检查

- 是否涉及交易/账户/仓位：否。
- 处理方式：只做研究排序与 shadow ledger。
- 禁止输出：买卖建议、目标价、仓位、下单、账户动作。

## 质量门槛

- 新闻 10 条、论文 5 篇、开源项目 5 个、舆情证据 5 条。
- Active research candidates 默认不超过 8。
- 必须区分 fact / inference / hypothesis。
- 必须通过 `docs/weekly-brief-quality-gate.md`。

# AI 趋势投资研究结论

## 老板结论页

- 一句话主结论：本周发散发现后，最硬的 AI 研究链条不是“泛 AI 应用”，而是 **inference/custom silicon -> AI connectivity/HBM -> enterprise agents**，其中第一梯队集中在 `AVGO/MU/ALAB/CRDO`。
- 整体置信度：中高。硬件与连接层强于软件层；软件层最好的新增信号来自 `SNOW`，而 `PLTR/APP` 基本面强但技术面冲突明显。
- 本周研究裁决：第一梯队强确认；第二梯队保留；应用层和 neocloud 高分歧，降级观察。
- 第一梯队：`AVGO`、`MU`、`ALAB`、`CRDO`。
- 第二梯队：`NVDA`、`MRVL`、`VRT`、`SNOW`。
- 观察层：`PLTR`、`APP`、`CRWV`、`TSM`、`ANET`、`AMD`、`GEV`、`ETN`、`WDC`、`STX`、`BLZE`。
- 暂不纳入主线：`ORCL`、`META`、`MSFT`、`GOOGL`、`AMZN` 作为需求源保留背景，不作为本轮主动候选。
- 最大证伪风险：AI capex 由现金流融资转向债务融资，若 2027-2028 capex 增速放缓，供应链估值可能先受冲击。
- 下周最重要验证：OpenAI/Broadcom Jalapeno 之后，是否出现更多客户/供应链订单确认，尤其是 Celestica、Broadcom、HBM、AI fabric 和 optical connectivity 环节。

## 核心判断与硬证据

| 判断 | 处理 | 证据强度 | 最硬的 2-3 条证据 | 风险/证伪 |
|---|---|---|---|---|
| Custom silicon / inference ASIC 从二级叙事变成主线 | 强确认 | 高 | [OpenAI/Broadcom Jalapeno](https://openai.com/index/openai-broadcom-jalapeno-inference-chip/) 明确指向 inference chip、gigawatt scale、Microsoft/partners；[Broadcom Q2 FY26](https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2026-financial) 披露 AI semis 收入 108 亿美元、Q3 指引 160 亿美元；`AVGO` 技术面仍高于 200D | 客户集中、ASIC 订单时点、毛利率和 Nvidia 生态竞合 |
| AI connectivity 是本轮新冒头的“骨架” | 强确认 | 高 | [Astera Q1](https://www.asteralabs.com/news/astera-labs-reports-first-quarter-2026-financial-results/) 收入 3.084 亿美元、同比 +93%，AI fabric/PCIe 6；[Credo FY26 Q4](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Technology-Group-Holding-Ltd-Reports-Fourth-Quarter-and-Fiscal-Year-2026-Financial-Results/default.aspx) 收入 4.37 亿美元、同比 +157%；`ALAB/CRDO` 3 个月分别 +250%/+178% | 极高动量、估值拥挤、客户集中、技术替代 |
| Memory/HBM 仍是最清楚的财务传导层 | 强确认 | 高 | [Micron FY26 Q3](https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-record-results-third-quarter) HBM4 lead customer 高量出货；`MU` 3 个月 +241%，站上全部主要均线；开源和论文都指向 long-context/KV cache 需求 | 过热、周期供给、HBM 价格反转 |
| Enterprise agents 开始有真实采用，但上市公司映射更挑剔 | 保留 | 中 | [OpenAI agents work report](https://openai.com/index/how-agents-are-transforming-work/) 显示 Codex 从工程扩展到 Legal/Finance/Recruiting；[Samsung deployment](https://openai.com/index/samsung-electronics-chatgpt-codex-deployment/) 是大规模企业部署；[Snowflake FY27 Q1](https://www.sec.gov/Archives/edgar/data/1640147/000164014726000027/fy2027q1earnings.htm) 披露 13,600+ accounts 使用 AI capabilities | 代理层受益可能流向私有模型公司而非公开软件股；`PLTR/APP` 技术面冲突 |
| Data center physical infra 仍成立，但本周新鲜度弱于芯片/连接 | 保留 | 中 | [Vertiv Q1](https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-First-Quarter-with-Diluted-EPS-Growth-of-136-Adjusted-Diluted-EPS-Growth-of-83-Raises-Full-Year-Guidance/default.aspx) Americas organic +44% on data center demand；William Blair 认为电力需求会形成多年 physical bottleneck；`VRT` 高于 20D/200D | 订单转收入、项目延迟、估值已反映 |
| AI cloud / neocloud 需求强，但融资与现金流风险更尖锐 | 降级观察 | 中 | [CoreWeave Q1](https://investors.coreweave.com/news/news-details/2026/CoreWeave-Reports-Strong-First-Quarter-2026-Results/) 收入 20.78 亿美元、backlog 994 亿美元，但净亏损 7.40 亿美元、调整后 operating margin 仅 1%；WSJ/Exponential View 指出 AI buildout 中债务融资占比上升；`CRWV` 低于 20/50/200D | 高 capex、债务、客户集中、技术面弱 |

## 本周研究排序

| 层级 | 主题/公司 | 为什么在这一层 | 当前处理 |
|---|---|---|---|
| 第一梯队 | `AVGO` | OpenAI custom inference chip + 官方 AI semis 收入/指引 + 仍高于 200D | 强确认 |
| 第一梯队 | `MU` | HBM4 / cloud memory 财务证据最硬，技术面极强 | 强确认但提示过热 |
| 第一梯队 | `ALAB` | AI fabric / PCIe 6 明确，收入同比 +93%，技术面强 | 强确认但拥挤 |
| 第一梯队 | `CRDO` | AI data-center connectivity 收入同比 +157%，技术面强 | 强确认但拥挤 |
| 第二梯队 | `NVDA` | Vera Rubin / Dynamo / Data Center 收入仍是核心底座，但短线低于 20/50D | 保留 |
| 第二梯队 | `MRVL` | AI bookings、optics、XPU attach，技术面强 | 保留 |
| 第二梯队 | `VRT` | 物理基础设施传导清楚，趋势未破 | 保留 |
| 第二梯队 | `SNOW` | 企业 AI adoption 和 product revenue 指引上调，软件层少数图形较好的候选 | 保留 |
| 观察层 | `PLTR` | 基本面极强，但 3 个月 -27%，跌至 52 周低点 | 降级观察 |
| 观察层 | `APP` | AI advertising / FCF 强，但技术面低于 200D 且争议多 | 降级观察 |
| 观察层 | `CRWV` | AI cloud demand 强，但亏损、债务、技术弱 | 降级观察 |
| 观察层 | `BLZE` | CoreWeave 3.35 亿美元存储合同，单源小票 | watch-only |

## 当前观察到的 AI 趋势故事

| 故事 | 已有证据 | 基本面承接 | 技术面反馈 | Reflection 裁决 | 当前处理 |
|---|---|---|---|---|---|
| AI 从 chat 走向 agentic work，推理需求变成长任务/多 agent/token 密集 | OpenAI Codex report、Samsung rollout、No Priors/All-In 讨论 | 直接承接在 inference ASIC、HBM、connectivity；软件承接在 SNOW/PLTR 等 | 硬件强，软件分化 | 保留，但不能直接等同所有软件股受益 | 强确认硬件，保留软件 |
| Custom silicon 和 Nvidia 生态不是二选一，而是并行扩张 | OpenAI/Broadcom、Broadcom AI semis、Marvell AI bookings、NVIDIA Vera Rubin | AVGO/MRVL/NVDA 都有财务承接 | AVGO/MRVL 强于 NVDA 短线 | 保留 | 强确认 |
| AI data center 价值链从 GPU 扩到 AI fabric、optics、memory、cooling/power | ALAB/CRDO/MU/VRT 官方披露，William Blair | 收入、指引、订单、margin 均有映射 | ALAB/CRDO/MU 最强 | 保留但警惕估值拥挤 | 强确认 |
| AI cloud / neocloud 是需求真强但风险也最大的层 | CRWV revenue/backlog，Backblaze/CoreWeave storage deal | revenue/backlog 强，但亏损/债务/FCF 风险 | CRWV 弱，BLZE 单日事件型 | 降级 | 观察 |

## 长期远演版 AI 趋势展望

| 远期故事 | 时间尺度 | 产业阶段变化 | 可能扩散到的价值链 | 关键假设 | 中间验证指标 | 结论身份 |
|---|---|---|---|---|---|---|
| Agentic work 把 AI 使用单位从“聊天”变为“可委托任务” | 6-18 个月 | 单次请求变长、多 agent 并行、工具调用常态化 | Inference ASIC、HBM、KV cache、observability、security | 成本下降带来更多使用，而非只压低收入 | Codex/enterprise agent 使用量、API token、推理毛利 | 部分验证趋势 |
| AI infrastructure 进入 full-stack 定制时代 | 2-5 年 | OpenAI/Google/AWS/Meta 自研或联合 ASIC，Nvidia 通过网络/软件/生态防守 | AVGO/MRVL/TSM/ALAB/CRDO/NVDA/Celestica | 定制芯片能按时量产且不牺牲生态效率 | tape-out、客户订单、rack deployment、gross margin | 场景推演 |
| 数据中心瓶颈从芯片扩散到电力、散热、存储、土地、劳动力 | 2-5 年 | Capex 从服务器转向 power/cooling/grid/storage | VRT/ETN/GEV/CEG/WDC/STX/BLZE | AI demand 足以消化债务融资和折旧 | 电力 PPA、backlog、capex funding cost、project delay | 部分验证趋势 |
| 企业 AI 的赢家不一定是“AI 应用”，可能是数据/治理/安全控制平面 | 6-18 个月 | 企业从试用 chat 转向 workflow、MCP、governance、secure automation | SNOW/PLTR/CRWD/PANW/NET/ZS 等 | 企业愿意为可信工作流付费，且不被模型厂商吞掉价值 | RPO、AI product usage、NRR、seat expansion | 观察清单 |

## 结论矩阵

| 主题/公司 | AI 信息与舆情 | 基本面 | 技术面 | Wood/Buffett 分歧 | Reflection 结论 | 最终处理 |
|---|---|---|---|---|---|---|
| `AVGO` | 强 | 强 | 中强 | Wood 强化 full-stack；Buffett 关注客户集中 | 闭环较完整 | 强确认 |
| `MU` | 强 | 强 | 强但过热 | Wood 强化 HBM 瓶颈；Buffett 提醒周期品 | 闭环强但拥挤 | 强确认 |
| `ALAB` | 强 | 强 | 强 | Wood 强化 rack-scale AI fabric；Buffett 要求客户/估值纪律 | 闭环强 | 强确认 |
| `CRDO` | 强 | 强 | 强 | Wood 强化 interconnect；Buffett 关注集中和估值 | 闭环强 | 强确认 |
| `NVDA` | 强 | 强 | 中 | Wood 强化平台；Buffett 关注预期过满 | 基本面强，短线技术降温 | 保留 |
| `MRVL` | 强 | 中强 | 强 | Wood 强化 optics/XPU；Buffett 关注并购整合 | 保留 | 保留 |
| `VRT` | 中强 | 强 | 中强 | Wood 看二阶 infra；Buffett 更容易理解现金流 | 保留 | 保留 |
| `SNOW` | 强 | 中强 | 中 | Wood 强化 agentic enterprise；Buffett 关注利润率/竞争 | 软件层少数保留 | 保留 |
| `PLTR` | 强 | 强 | 弱 | Wood 看平台；Buffett 警惕价格/预期 | 技术面断裂 | 降级观察 |
| `CRWV` | 强 | 分歧 | 弱 | Wood 看云扩张；Buffett 看到债务和亏损 | 闭环断裂 | 降级观察 |

## 投资影响地图

| AI 变化 | 可能影响的板块 | 可能受益公司类型 | 可能受损公司类型 | 证据强度 |
|---|---|---|---|---|
| Agent tasks 更长、更多并行 | Inference infra | Custom ASIC、GPU、HBM、serving software | 低效率推理栈 | 高 |
| Hyperscaler / frontier lab full-stack 自研 | Semis / EMS / networking | AVGO、MRVL、TSM、Celestica、optics/connectivity | 泛用硬件供应商 | 中高 |
| Rack-scale AI fabric | Connectivity | ALAB、CRDO、ANET、MRVL | 传统低速互连 | 高 |
| 长上下文和 agent memory | Memory/storage | MU、WDC、STX、LMCache 类技术生态 | 供给过剩 commodity memory | 中高 |
| 企业从 chatbot 转 workflow agent | Data/security/software | SNOW、PLTR、security platform | 传统 seat-based SaaS 若价值被模型层抽走 | 中 |
| Capex 进入债务/融资压力阶段 | AI cloud / neocloud | 有合同和低资金成本者 | 高杠杆云算力出租商 | 中高 |

## 最终风险与反证

- 最大风险：AI infrastructure 收入仍在增长，但估值已经把 2027-2028 的高 capex 延续性提前资本化。
- 最关键反证：hyperscaler 或 neocloud 公开下调 capex / GPU / ASIC 订单；HBM 价格或 utilization 下行；AI agent 使用量无法转化为付费收入。
- 下周必须验证的 3 件事：
  1. OpenAI/Broadcom Jalapeno 是否带来更多供应链订单、客户确认或 analyst revision。
  2. `ALAB/CRDO/MRVL/MU` 的动量是否继续强于 `SOXX/SMH`，还是出现高位放量衰竭。
  3. `PLTR/APP/CRWV` 是否能修复 20D/50D，否则保留在观察层。

## Wood vs Buffett 辩论对结论的影响

- Cathie Wood 视角强化了：agentic work 和 custom silicon 是平台级变迁，市场可能低估推理成本下降后的需求弹性；应往 AI fabric、HBM、security、data-control-plane 等深一层价值链看。
- Buffett 视角削弱了：neocloud、低利润软件叙事和过热小票；如果一个故事不能解释 owner earnings、客户集中、资金成本和护城河，就不能进核心结论。
- 最终平衡判断：保留“AI 基建扩散”主线，但只把已经有收入/订单/技术面三重支持的公司放进第一梯队。

# Stock Discovery Section

## 候选入口状态

| 入口 | 数据节点 | 状态 | 返回数量 | 备注 |
|---|---|---|---:|---|
| 高管/大佬发言 | TranscriptAPI / No Priors / All-In | success | 30 latest items, 2 transcripts | No Priors Intel CEO；All-In AI/Anthropic episode |
| 财报电话会/官方披露 | IR / SEC / company releases | success | 12+ | AVGO、MU、ALAB、CRDO、MRVL、VRT、SNOW 等 |
| 客户 capex | official / institution research | success | 6+ | OpenAI/Broadcom、CoreWeave、hyperscaler capex |
| 开发者采用 | GitHub | success | 11 repos | agents、serving、MCP、inference |
| 学术方向 | arXiv | success | 10 papers | agents、reasoning、inference |
| 催化剂 | web/news/IR | success | 10+ | Jalapeno、HBM4、AI fabric、Q2/Q3 guidance |
| 技术面强度 | yfinance OHLCV | success | 27 tickers + 6 ETFs | 半导体/connectivity 强，software 分化 |
| 机构/insider/short | Longbridge unavailable | partial | limited | 未作为核心评分项 |

## Raw Candidate Funnel

| Rank | Ticker | Company | Signal Families | AI/Industry Chain Position | Score | Why Now | Missing Proof | Next Agent |
|---:|---|---|---|---|---:|---|---|---|
| 1 | AVGO | Broadcom | Official AI semis, OpenAI chip, technical | Custom ASIC / AI networking | 92 | Jalapeno + Q3 AI semis guide | 客户集中与量产节奏 | Fundamental / Technical |
| 2 | MU | Micron | Official HBM4, memory demand, technical | HBM / DRAM / AI memory | 90 | HBM4 high-volume + record results | 周期供给风险 | Fundamental / Technical |
| 3 | ALAB | Astera Labs | Official Q1, AI fabric, technical | AI fabric / PCIe / rack-scale connectivity | 88 | 收入同比 +93%，Scorpio AI fabric | 客户集中、估值 | Fundamental / Technical |
| 4 | CRDO | Credo | Official FY26, AI connectivity, technical | AEC / optical connectivity | 87 | 收入同比 +157%，FY27 指引强 | 客户集中 | Fundamental / Technical |
| 5 | NVDA | NVIDIA | Vera Rubin, Data Center, open-source inference | GPU / networking / AI factory | 86 | Rubin full production + Dynamo | 短线低于 20/50D | Fundamental / Technical |
| 6 | MRVL | Marvell | Official AI bookings, optics/XPU, technical | Optical / XPU attach / custom silicon | 82 | AI bookings raised FY27/FY28 outlook | 并购整合、margin | Fundamental / Technical |
| 7 | VRT | Vertiv | Official data center demand, physical infra, technical | Power / cooling / critical infrastructure | 78 | Americas organic +44% | 项目延迟 | Fundamental / Technical |
| 8 | SNOW | Snowflake | Official AI usage, RPO, technical | Enterprise AI data/control plane | 74 | AI accounts + Cortex Code + AWS/OpenAI partnership | AI product monetization | Fundamental / Technical |
| 9 | PLTR | Palantir | Q1 revenue growth, AIP narrative, weak technical | Enterprise AI operating system | 69 | Revenue growth strong | 技术面破位、估值 | Watch |
| 10 | APP | AppLovin | Official FCF, AI ad platform, weak technical | AI advertising / monetization | 67 | FCF 13 亿美元，AI marketing platform | 技术弱、竞争/short scrutiny | Watch |
| 11 | CRWV | CoreWeave | Revenue/backlog, neocloud demand, weak financials | AI cloud / GPU rental | 63 | Revenue doubled, backlog huge | debt/loss/capex | Watch |
| 12 | TSM | TSMC | AI/HPC capex, foundry bottleneck, technical | Advanced foundry / packaging | 66 | AI capex high | 非本周新 signal | Watch |
| 13 | ANET | Arista | AI networking, technical | Ethernet AI networking | 65 | 稳定强势 | 新鲜度低于 CRDO/ALAB | Watch |
| 14 | WDC/STX | Western Digital / Seagate | AI storage, technical | HDD / storage | 60 | AI logs/object storage需求 | 证据多为二级报道，周期性 | Watch |
| 15 | BLZE | Backblaze | CoreWeave contract, market reaction | AI object storage | 55 | 3.35 亿美元 5 年合同 | 小票、单源、规模 | Watch-only |
| 16 | GEV/ETN | GE Vernova / Eaton | Power infra, technical | Grid / electrical equipment | 60 | AI power theme | 公司级 AI 归因不足 | Watch |

## Active Research Candidates

| Rank | Ticker | Company | Signal Families | AI/Industry Chain Position | Score | Why Now | Missing Proof | Next Agent |
|---:|---|---|---|---|---:|---|---|---|
| 1 | AVGO | Broadcom | Official + OpenAI + price | Custom ASIC / networking | 92 | OpenAI Jalapeno 把 custom inference 推到主线 | 客户集中 | All |
| 2 | MU | Micron | Official + AI memory + price | HBM / DRAM | 90 | HBM4 + 技术面最强 | 周期性 | All |
| 3 | ALAB | Astera | Official + AI fabric + price | Connectivity | 88 | Rack-scale AI fabric 成为新瓶颈 | 估值/集中 | All |
| 4 | CRDO | Credo | Official + connectivity + price | Connectivity / AEC / optics | 87 | 收入/利润/指引三者同步 | 集中 | All |
| 5 | NVDA | NVIDIA | Official + OSS + platform | GPU / AI factory | 86 | Rubin + Dynamo 支撑 agentic inference | 短线技术修复 | All |
| 6 | MRVL | Marvell | Official + AI bookings + price | Optical / XPU / switch | 82 | AI bookings 与 FY outlook 上修 | 并购整合 | All |
| 7 | VRT | Vertiv | Official + infra + price | Power / cooling | 78 | data center demand 传导到业绩 | 项目周期 | All |
| 8 | SNOW | Snowflake | Official + enterprise AI + price | Data / enterprise agents | 74 | 软件层少数有 AI 使用量和技术面支撑 | AI revenue attribution | All |

## Watchlist Candidates

| Ticker | Company | Why Watch | Missing Confirmation | Promotion Trigger |
|---|---|---|---|---|
| PLTR | Palantir | Q1 增长极强，AIP 叙事最明确 | 技术面跌至 52 周低点 | 重回 20D/50D，且新合同/RPO 继续确认 |
| APP | AppLovin | FCF 和 AI ad platform 强 | 技术面低于 200D，争议多 | 站回 200D，self-service launch 数据确认 |
| CRWV | CoreWeave | AI cloud backlog 极大 | 亏损、债务、技术面弱 | 利润率修复或资金成本下降 |
| TSM | TSMC | 全链条 foundry bottleneck | 本周新催化弱于连接层 | AI/HPC capex/CoWoS 新增确认 |
| ANET | Arista | AI networking 稳健 | 新鲜度弱于 ALAB/CRDO | 新 AI networking 订单/突破 |
| WDC/STX | Western Digital / Seagate | AI storage/HDD 需求强 | 周期性、官方 AI attribution 不足 | 官方云/AI backlog 或 capacity sold-out 再确认 |
| BLZE | Backblaze | CoreWeave 3.35 亿美元合同 | 小票、单源、规模 | 合同转收入与毛利率确认 |

## Rejected / Deferred Noise

| Ticker/Theme | Rejection Reason | What Would Change This |
|---|---|---|
| HDD | `yfinance` 无可用价格数据，疑似无效 ticker | 明确上市代码与流动性 |
| Crypto miners / AI pivot | 加密业务邻近，研究边界噪音高 | AI revenue 占比清晰且不依赖 crypto economics |
| Private labs: OpenAI / Anthropic | 非上市公司 | 仅作为需求源或供应链线索 |
| ORCL/META/MSFT/GOOGL/AMZN | 需求源很重要，但本轮技术面/资本效率冲突大 | capex ROI 更清晰或供应链传导更直接 |

# AI 信息与舆情 Section

## AI 技术新闻

| # | 标题 | 来源 | 日期 | 链接 | 为什么重要 |
|---:|---|---|---|---|---|
| 1 | OpenAI and Broadcom unveil LLM-optimized inference chip | OpenAI | 2026-06-24 | [link](https://openai.com/index/openai-broadcom-jalapeno-inference-chip/) | Custom inference ASIC 成为主线 |
| 2 | How agents are transforming work | OpenAI | 2026-06-25 | [link](https://openai.com/index/how-agents-are-transforming-work/) | Agentic work 使用量证据 |
| 3 | Daybreak: Tools for securing every organization | OpenAI | 2026-06-22 | [link](https://openai.com/index/daybreak-securing-the-world/) | AI security 从发现漏洞转向 patch automation |
| 4 | Samsung brings ChatGPT and Codex to employees | OpenAI | 2026-06-21 | [link](https://openai.com/index/samsung-electronics-chatgpt-codex-deployment/) | 企业级 AI adoption 大规模部署 |
| 5 | Vera Rubin full production | NVIDIA | 2026-05-31 | [link](https://nvidianews.nvidia.com/news/vera-rubin-full-production-agentic-ai-factory) | Agentic AI factories supply-chain signal |
| 6 | NVIDIA FY27 Q1 results | NVIDIA IR | 2026-05-20 | [link](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx) | Data Center / networking 收入证据 |
| 7 | Broadcom Q2 FY26 results | Broadcom IR | 2026-06-03 | [link](https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2026-financial) | AI semis 收入与指引硬证据 |
| 8 | Micron FY26 Q3 record results | Micron IR | 2026-06-24 | [link](https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-record-results-third-quarter) | HBM4 / memory bottleneck |
| 9 | Astera Labs Q1 FY26 results | Astera | 2026-05-05 | [link](https://www.asteralabs.com/news/astera-labs-reports-first-quarter-2026-financial-results/) | AI fabric / PCIe connectivity |
| 10 | Credo FY26 Q4 results | Credo IR | 2026-06-01 | [link](https://investors.credosemi.com/news-events/news/news-details/2026/Credo-Technology-Group-Holding-Ltd-Reports-Fourth-Quarter-and-Fiscal-Year-2026-Financial-Results/default.aspx) | AI data-center connectivity |
| 11 | Marvell FY27 Q1 results | Marvell IR | 2026-05 | [link](https://investor.marvell.com/news-events/press-releases/detail/1023/marvell-technology-inc-reports-first-quarter-of-fiscal-year-2027-financial-results) | AI bookings / optics / XPU |
| 12 | Snowflake FY27 Q1 results | SEC / Snowflake | 2026-05-27 | [link](https://www.sec.gov/Archives/edgar/data/1640147/000164014726000027/fy2027q1earnings.htm) | Enterprise AI software adoption |

## AI 学术论文

| # | 论文 | 作者/机构 | 日期 | 链接 | 研究方向 | 可能影响 |
|---:|---|---|---|---|---|---|
| 1 | Empowering GUI Agents via Autonomous Experience Exploration | Tianyi Men, Zhuoran Jin, Pengfei Cao | 2026-06-25 | [arXiv](http://arxiv.org/abs/2606.27330v1) | GUI agents | Agent 工作流自动化 |
| 2 | Multilingual Reasoning Cascades Need More Context | Arnav Mazumder et al. | 2026-06-25 | [arXiv](http://arxiv.org/abs/2606.27306v1) | reasoning/context | 长上下文与 memory demand |
| 3 | When Does Combining Language Models Help? | Josef Chen | 2026-06-25 | [arXiv](http://arxiv.org/abs/2606.27288v1) | routing / mixture-of-agents | 多模型/agent orchestration |
| 4 | Information-Aware KV Cache Compression for Long Reasoning | Jushi Kai, Zhuiri Xiao, Alexandra Birch | 2026-06-25 | [arXiv](http://arxiv.org/abs/2606.26875v1) | KV cache | HBM/serving efficiency |
| 5 | Moebius: Serving Mixture-of-Expert Models with Seamless Runtime Parallelism Switch | Shaoyu Wang et al. | 2026-06-25 | [arXiv](http://arxiv.org/abs/2606.26607v1) | MoE serving | Networking / memory / scheduling |

## AI 开源项目

| # | 项目 | GitHub 链接 | 热度证据 | 方向 | 为什么值得看 |
|---:|---|---|---|---|---|
| 1 | vLLM | [repo](https://github.com/vllm-project/vllm) | 84,369 stars | inference serving | 推理吞吐核心生态 |
| 2 | SGLang | [repo](https://github.com/sgl-project/sglang) | 29,672 stars | serving / agents | Agentic / multimodal serving |
| 3 | llama.cpp | [repo](https://github.com/ggml-org/llama.cpp) | 118,193 stars | local inference | 低成本/边缘推理 |
| 4 | TensorRT-LLM | [repo](https://github.com/NVIDIA/TensorRT-LLM) | 13,969 stars | GPU inference | NVIDIA software moat |
| 5 | LangChain | [repo](https://github.com/langchain-ai/langchain) | 140,237 stars | agent framework | Enterprise agent tooling |
| 6 | AutoGen | [repo](https://github.com/microsoft/autogen) | 59,264 stars | multi-agent | Agent orchestration |
| 7 | MCP servers | [repo](https://github.com/modelcontextprotocol/servers) | 87,718 stars | tool protocol | AI agents 连接企业工具 |

## YouTube / 播客要点

| 节目/视频 | 链接 | 核心观点 | 证据性质 | 后续验证 |
|---|---|---|---|---|
| No Priors：Intel CEO semiconductor supply chain | [YouTube](https://www.youtube.com/watch?v=asCgCv2XB4s) | Transcript 命中 semiconductor、AI、data center、power、Intel、NVIDIA；管理层叙事强调供应链再工程 | 播客/高管观点，不是财务证明 | 与 Intel/TSMC/AVGO/MRVL/ALAB 官方数据交叉 |
| All-In：Anthropic / AI debate | [YouTube](https://www.youtube.com/watch?v=3Amlu4y94Ho) | Transcript 命中 AI、Anthropic、power、chip、data center；舆情侧仍围绕 AI 权力、成本和监管争议 | 市场叙事/观点 | 只作为 sentiment，不计入基本面 |

## 高信号舆情证据

| # | 平台 | 主题 | 链接 | 时间 | 代表观点 | 信号类型 |
|---:|---|---|---|---|---|---|
| 1 | Hacker News | OpenAI/Broadcom inference chip | [HN front](https://news.ycombinator.com/front?day=2026-06-24&p=2) | 2026-06-24 | Jalapeno 进入开发者讨论 | 正向技术关注 |
| 2 | Reddit r/stocks | AI gold rush duration | [thread](https://www.reddit.com/r/stocks/comments/1ua8ukh/how_long_do_you_expect_the_ai_gold_rush_to_last/) | 近 1 周 | 担心 capex 放缓引发估值误读 | 反方/周期风险 |
| 3 | Reddit r/investing | AI bubble pop | [thread](https://www.reddit.com/r/investing/comments/1t9txw5/how_the_ai_bubble_is_going_to_pop/) | 近 1 月 | 讨论 productivity vs GPU capex ROI | 反方/ROI 风险 |
| 4 | Hacker News | AI economics don't make sense | [thread](https://news.ycombinator.com/item?id=47936867) | 近 1 月 | 推理成本下降与 reasoning token 增长之间有争议 | 反方/成本风险 |
| 5 | Reddit r/stocks | Everyone in AI long-term winner? | [thread](https://www.reddit.com/r/stocks/comments/1t8tgfg/the_market_seems_to_think_everyone_in_ai_will_be/) | 近 1 月 | 供应商 FCF 与 hyperscaler FCF 的矛盾 | 结构性分歧 |
| 6 | Hacker News | Corporate America rationing AI costs | [thread](https://news.ycombinator.com/item?id=48335388) | 近 3 周 | 企业 AI 成本控制进入讨论 | 反方/enterprise adoption friction |

# 基本面验证报告

## 核心结论

- 基本面闭环：硬件/连接/内存层成立；enterprise agents 部分成立；neocloud 暂不成立。
- 置信度：中高。
- 最大风险：AI demand 真实但市场已过度提前定价；高 capex 与融资成本使 revenue growth 不等于 owner earnings。

## 公司逐项验证

| 公司 | 叙事暴露 | 财务传导链 | 已有证据 | 缺口 | 结论 |
|---|---|---|---|---|---|
| AVGO | Custom ASIC / AI networking | OpenAI & hyperscaler inference demand -> ASIC/networking -> AI semis revenue -> FCF/EBITDA | AI semis Q2 108 亿美元，Q3 指引 160 亿美元；OpenAI Jalapeno | 客户集中和量产节奏 | 成立 |
| MU | HBM / memory | Long-context/agent demand -> HBM/DRAM -> cloud memory revenue/pricing -> FCF | HBM4 high-volume shipments；技术面强 | 周期性和价格 | 成立但过热 |
| ALAB | AI fabric / PCIe | Rack-scale AI -> switch/retimer/smart cable -> revenue/gross margin | Q1 revenue +93%，AI fabric product shipments | 客户集中 | 成立 |
| CRDO | AEC/optical connectivity | AI cluster links -> high-speed connectivity -> revenue/gross margin | Q4 revenue +157%，gross margin ~68% | customer concentration | 成立 |
| NVDA | AI factory platform | Agentic workloads -> GPU/networking/software -> Data Center revenue | Vera Rubin、Data Center、Dynamo | 预期拥挤、短线技术 | 成立 |
| MRVL | Optics / XPU attach | AI scale-out/scale-up -> optics/switch/XPU attach -> revenue outlook | Record Q1 revenue +28%，AI bookings raised FY outlook | 并购整合 | 部分成立 |
| VRT | Power/cooling | AI data centers -> power/cooling -> sales/margin/backlog | Americas organic +44%，guide raise | 项目转收入 | 成立 |
| SNOW | Enterprise AI data plane | Enterprise agents -> governed data/context -> product revenue/RPO | Product revenue +34%，AI capabilities 13,600+ accounts | AI revenue attribution | 部分成立 |

## 估值与预期差

| 公司 | 当前市场可能定价的内容 | 还没验证的内容 | 需要观察的指标 |
|---|---|---|---|
| AVGO | Custom ASIC 爆发已部分定价 | Jalapeno 多代部署规模 | AI semis guide、客户数、FCF margin |
| MU | HBM 短缺和价格上涨 | 供给扩张后的持续性 | HBM price、bit growth、inventory |
| ALAB/CRDO | AI connectivity 高增长 | 客户集中是否降低 | customer count、design wins、gross margin |
| SNOW | Agentic enterprise 转型 | AI features 是否带动 consumption | product revenue guide、RPO、AI accounts |
| PLTR/APP | 高增长和 AI monetization | 技术面与估值是否修复 | 20/50D reclaim、RPO/FCF |
| CRWV | backlog 大幅增长 | 现金流/融资可持续 | interest expense、capex、margin |

# 技术分析报告

## 图表信息

- 标的：active 8 + watchlist/benchmarks。
- 周期：日线 1 年；周线图像未提供，按日线近似中期结构。
- 数据时间：2026-06-25 regular close。
- 数据源：`yfinance`，Finnhub quote 交叉部分 active/watch。
- 图表质量：足够做日线/均线/相对强度；周线/200 周均线不足。

## Active 技术面摘要

| Ticker | Close | 1W | 1M | 3M | MA20 | MA50 | MA200 | 技术状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| AVGO | 378.91 | -3.6% | -10.2% | +22.5% | 406.77 | 412.60 | 361.17 | 中期仍在 200D 上方，短线修复中 |
| MU | 1213.56 | +16.3% | +35.5% | +241.4% | 1024.97 | 788.62 | 420.85 | 极强但明显过热 |
| ALAB | 398.00 | +6.2% | +24.9% | +250.3% | 366.86 | 278.40 | 190.53 | 强趋势，高位波动风险 |
| CRDO | 268.03 | +7.5% | +20.9% | +177.9% | 244.68 | 209.13 | 156.43 | 强趋势，接近前高区域 |
| NVDA | 195.74 | -4.4% | -8.9% | +14.3% | 208.85 | 210.21 | 190.53 | 200D 上方，20/50D 下方 |
| MRVL | 281.26 | -2.9% | +35.1% | +187.9% | 275.14 | 210.57 | 117.51 | 强趋势，成交量偏轻 |
| VRT | 325.57 | +2.5% | +0.5% | +29.0% | 314.79 | 324.04 | 228.05 | 站上 20D，靠近 50D |
| SNOW | 227.06 | -3.2% | +27.8% | +39.9% | 240.44 | 187.54 | 205.74 | 高于 50/200D，低于 20D，软件层相对较好 |

## 情景分析

| 标的组 | Base | Bull | Bear | 失效/确认 |
|---|---|---|---|---|
| MU/ALAB/CRDO | 50% 高位整理 | 30% 放量突破前高 | 20% 跌回 20D 下方 | 20D 为第一风险位，50D 为中期失效 |
| AVGO/NVDA | 50% 20/50D 修复 | 30% 重回短均线并挑战高点 | 20% 跌破 200D | 200D 是关键风险位 |
| MRVL/VRT/SNOW | 45% 趋势内震荡 | 35% 延续上行 | 20% 跌破 50D | 50D 是主要分水岭 |

Benchmark：`SOXX` 3 个月 +90.1%，`SMH` +67.2%，`QQQ` +24.9%，`IGV` +6.3%。本轮市场强度清楚偏向 semis/connectivity，而不是泛软件。

# Reflection Section

## 总判断

- 闭环状态：部分完整，硬件/连接/内存完整度最高。
- 置信度：中高。
- 最弱一环：应用软件和 neocloud 的“收入增长 -> owner earnings”链条。

## 闭环链条

| 环节 | 结论 | 证据 | 缺口 | 评分 |
|---|---|---|---|---:|
| AI 信息 | Agentic work 和 custom inference 增强 | OpenAI/Broadcom、OpenAI Codex、Samsung | 私有模型公司数据不可完全观察 | 8 |
| 舆情叙事 | 市场关注集中在 capex、ROI、成本 | HN/Reddit/All-In | 社区偏见和噪音 | 7 |
| 产业影响 | HBM、AI fabric、optics、power/cooling 扩散 | MU/ALAB/CRDO/MRVL/VRT | 估值和供需周期 | 8 |
| 公司基本面 | 第一梯队可落到收入/指引 | 官方 IR/SEC | 客户集中 | 8 |
| 技术面定价 | 半导体/连接强，软件弱 | yfinance/ETF | 周线不足 | 7 |
| 可证伪指标 | capex/order/margin/MA levels 可跟踪 | 指标明确 | 等待下周确认 | 8 |

## Perspective Debate：Cathie Wood vs Buffett

| 议题 | Cathie Wood 视角 | Buffett 视角 | Reflection 裁决 |
|---|---|---|---|
| Agentic AI | 成本曲线下降会扩大总需求，Jevons 效应可能推高 compute | 好故事必须变成可预测现金流 | 保留为长期主线，当前偏向卖铲层 |
| AVGO/ALAB/CRDO/MU | 深一层供应链可能比 obvious winner 更有弹性 | 小心客户集中、周期和估值 | 第一梯队保留，但不把强趋势等同低风险 |
| SNOW/PLTR/APP | 企业 agent adoption 可能重估 software stack | 技术复杂，护城河和价格要分开看 | SNOW 保留，PLTR/APP 因图形冲突降级 |
| CRWV/neocloud | 新云平台可能重塑基础设施 | 债务和亏损是硬约束 | 降级观察 |

# Paper Portfolio & Attribution Section

## 本周模式

- Mode：`shadow_ledger`
- 是否连接 broker：否
- 评价窗口：报告后下一个可得常规收盘为 entry，5 个交易日后收盘为 exit。
- 数据源：`yfinance`，必要时 Finnhub/Nasdaq 交叉。

## Open Observation Ledger

| Thesis ID | Ticker | Company | Entry Rule | Planned Exit | Benchmark | Thesis Summary | Status |
|---|---|---|---|---|---|---|---|
| AI-BROAD-2026-06-26-01 | AVGO | Broadcom | 发布后下一个常规收盘 | Entry + 5 trading days | SOXX/SMH/QQQ | Custom inference ASIC + AI semis revenue | open |
| AI-BROAD-2026-06-26-02 | MU | Micron | 同上 | 同上 | SOXX/SMH | HBM / memory bottleneck | open |
| AI-BROAD-2026-06-26-03 | ALAB | Astera | 同上 | 同上 | SOXX/SMH | AI fabric / connectivity | open |
| AI-BROAD-2026-06-26-04 | CRDO | Credo | 同上 | 同上 | SOXX/SMH | AI data-center connectivity | open |
| AI-BROAD-2026-06-26-05 | SNOW | Snowflake | 同上 | 同上 | IGV/QQQ | Enterprise agents / data control plane | open |

已有 prior observation：`weekly-ai-infra-minimal-experiment-2026-06-26.md` 中的 ledger 同日创建，尚未到 5 个交易日评价窗口，因此没有 closed attribution。

# 附录：数据节点状态与质量检查

## 数据节点状态

| Input Node | Status | Notes |
|---|---|---|
| Intent Router | success | 已按新版 runbook 生成 Route Plan |
| RSS/news/web | success | 12 条新闻/官方披露 |
| arXiv | success | 5/5 论文 |
| GitHub | success | 7 个项目计入，11 个返回 |
| Podcasts/videos | success | No Priors / All-In latest + 2 transcripts |
| last30days | partial | 用 web/HN/Reddit 搜索替代 dedicated skill |
| Finance | success/partial | yfinance + Finnhub + official IR；Longbridge 缺失 |
| Chart | success/partial | 日线充足，周线图像不足 |
| Longbridge | failed | CLI missing |
| Cross-check | success/partial | SEC/IR/Finnhub/yfinance |
| Paper ledger | success | shadow ledger open |
| Perspective skills | success | Wood/Buffett 作为 lens |

## 质量检查

- 内容准确性：部分通过
  - 是否有编造：未发现；所有计数项有链接。
  - 是否有错链：未发现。
  - 是否有过时信息：当前性按 2026-06-26 核查。
- Router 路由：通过
  - Task type：`full_weekly_brief` with broad discovery。
  - Selected agents：匹配用户请求。
  - Skipped agents：有理由。
- 格式完整性：通过
  - 老板结论页是否在 Intent Route Plan 之后的正文最前面：有。
  - AI 技术新闻：12/10。
  - AI 学术论文：5/5。
  - AI 开源项目：7/5。
  - AI 舆情证据：6/5。
  - Active research candidates：8/8 max。
  - Paper Portfolio & Attribution：有。
- 叙事纪律：通过
  - 当前故事基于 dated evidence。
  - 远期展望标注为部分验证趋势/场景推演/观察清单。
  - 产业链外推包含中间机制。
- 工具调用：部分通过
  - Longbridge failed，Alpha Vantage var mismatch；已降级并标记。

## Skill Scout / 系统维护建议

| 建议 | 相关 section | Recommendation | 理由 |
|---|---|---|---|
| 增加 `.env` 自动加载 wrapper | All | Install/build | 避免 TranscriptAPI 等配置被误判 missing |
| 安装或配置 Longbridge CLI read-only | Market/Fundamental/Technical | Watch/Install | 当前为唯一持续失败的核心节点 |
| 统一 `ALPHA_VANTAGE_API_KEY` 变量名 | Fundamental/Technical | Fix | `.env` 存在类似变量但不符合 skill 文档 |
| 固化 broad discovery 脚本 | Stock Discovery | Build | 本次临时脚本可产品化为候选漏斗 |
| 把 paper ledger 写入 CSV | Paper Attribution | Build | 便于下周自动回看 |
