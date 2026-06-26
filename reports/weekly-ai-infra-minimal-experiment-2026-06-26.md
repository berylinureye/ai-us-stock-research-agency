# 每周 AI 投资研究简报 - 最小实验

运行日期：2026-06-26  
研究主题：AI infrastructure、inference demand、hyperscaler capex、semiconductor / data center / power supply chain  
市场范围：美股上市公司与 ADR；排除加密货币、期权、私募公司、低流动性 penny stocks  
约束：不输出买卖建议、目标价、仓位；投资结论仅作为研究观察。

## 0. 运行边界与数据节点状态

本次按 `AGENCY.md` 的 directed section pipeline 执行：

Stock Discovery -> AI Information & Sentiment -> Fundamental -> Technical -> Reflection -> Final AI Trend Narrative Conclusion -> Paper Observation Ledger。

| 数据节点 | 状态 | 说明 |
| --- | --- | --- |
| 项目 runbook | 成功 | 已读取 `AGENCY.md`、`README.md`、`docs/agent-responsibilities.md`、`docs/weekly-brief-quality-gate.md`。 |
| Stock Discovery | 成功 | 未使用固定初始股票池；从新闻、官方披露、机构研究、GitHub/arXiv、市场数据、舆情与视频入口生成候选。 |
| 官方财报/新闻稿/SEC | 成功 | 使用公司 IR、SEC、官方公告作为核心事实来源。 |
| RSS/新闻/机构研究 | 成功 | 使用 William Blair、BloombergNEF、Tom's Hardware、IBD 等作为辅助来源。 |
| GitHub | 成功 | 使用 GitHub API 获取 inference / serving 相关开源项目活跃度。 |
| arXiv | 成功 | 使用 arXiv API 获取近一周推理效率、KV cache、speculative decoding、MoE serving 论文。 |
| 市场价格 | 部分成功 | Yahoo/Stooq 受限；使用 Nasdaq 历史行情 API。最后有效收盘日为 2026-06-25。 |
| YouTube/播客 transcript | 成功/复核修正 | `.env` 已配置 `TRANSCRIPT_API_KEY`；运行时需要显式加载 `.env`。已验证 No Priors 与 All-In Podcast transcript 可读取。 |
| Longbridge | 失败 | 本地未发现 Longbridge CLI；本次改用官方披露、Nasdaq 行情和公开网页。 |
| yfinance / financial-data-collector | 成功/复核修正 | 初始运行时 `yfinance` 缺失；后已安装 `yfinance==1.4.1` 并验证可读取 NVDA 5 日历史数据。原报告技术面仍保留 Nasdaq 数据口径。 |
| 技术分析 | 部分成功 | 有日线 OHLCV、20/50/200 日均线、近 3 月支撑阻力；无周线图像与 200 周均线。 |

质量门槛数量检查：新闻 10/10；论文 5/5；开源项目 5/5；高信号舆情 5/5；active candidates 8/8 上限。

## 1. Stock Discovery Section

### 1.1 候选发现入口

本次没有固定初始股票池。候选来自以下触发源：

| 入口 | 本次可用证据 |
| --- | --- |
| YouTube/播客/视频 | 优先路径：No Priors、All-In Podcast。已通过 TranscriptAPI 验证 transcript 可读取；另记录 NVIDIA Computex 2026 keynote、Vertiv Investor Conference 2026、Arista Q1 2026 earnings call、Microsoft FY26 Q3 earnings call、Micron earnings live。 |
| 高管发言/官方披露 | NVIDIA、Broadcom、AMD、Micron、TSMC、Arista、Vertiv、Microsoft、Alphabet、Amazon、Meta、Oracle、Constellation 官方披露。 |
| RSS/新闻/机构研究 | William Blair AI infrastructure supply chain、BloombergNEF data-center capex、Tom's Hardware data-center labor bottleneck、IBD AI power/data-center articles。 |
| GitHub/arXiv | vLLM、SGLang、TensorRT-LLM、llama.cpp、LMCache、Dynamo；arXiv 推理效率、KV cache、MoE serving 与 speculative decoding 论文。 |
| 市场数据 | Nasdaq 日线价格与成交量；ETF 参照 QQQ、SPY、SOXX、SMH、XLK、IGV。 |
| 美股筛选/流动性 | 排除 penny stocks、私募、加密货币相关主线；优先 US large/mid liquid equities 和 ADR。 |

### 1.2 Raw Candidates

| # | 候选 | 触发信号 | AI 链条位置 | 证据来源 | 为什么值得进入下一层 |
| --- | --- | --- | --- | --- | --- |
| 1 | NVDA | FY27 Q1 Data Center 收入 752 亿美元，同比增长 92%；Vera Rubin 进入 full production 叙事 | GPU、AI factory、networking、inference software | [NVIDIA FY27 Q1 results](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx)、[Vera Rubin announcement](https://nvidianews.nvidia.com/news/vera-rubin-full-production-agentic-ai-factory) | 直接收入、供给链、产品路线图三者同时支持，是 AI 基建主线核心锚点。 |
| 2 | AVGO | FY26 Q2 AI semiconductor 收入 108 亿美元，同比增长 143%；预计 Q3 AI semiconductor 160 亿美元，同比增长 200% | Custom ASIC/XPU、AI networking | [Broadcom FY26 Q2 results](https://investors.broadcom.com/news-releases/news-release-details/broadcom-inc-announces-second-quarter-fiscal-year-2026-financial) | 定制芯片从故事变成已披露收入，验证 hyperscaler custom silicon 分支。 |
| 3 | AMD | Data Center 收入 58 亿美元，同比增长 57%；Instinct ramp；Meta 最高 6GW 计划 | 替代 GPU、EPYC CPU、accelerator platform | [AMD Q1 2026 results](https://ir.amd.com/news-events/press-releases/detail/1284/amd-reports-first-quarter-2026-financial-results) | 是 NVDA 之外最重要的公开 accelerator 替代供给观察点。 |
| 4 | TSM | Q1 收入 359 亿美元；Q2 指引 390-402 亿美元；2026 capex 高端 520-560 亿美元；HPC/AI 需求强且供给紧 | 先进制程、先进封装、foundry bottleneck | [TSMC quarterly results](https://investor.tsmc.com/english/quarterly-results/2026/q1)、[TSMC Q1 transcript PDF](https://investor.tsmc.com/chinese/encrypt/files/encrypt_file/reports/2026-04/3cef85204275f94fd111485cfdf4adb3c0263c45/TSMC%201Q26%20Transcript.pdf) | 是 GPU、ASIC、HBM 控制器和先进封装的底层供给瓶颈。 |
| 5 | MU | FY26 Q3 收入 414.56 亿美元；FQ4 指引 500 亿美元；HBM4 lead customer 高量出货 | HBM、DRAM、NAND、long-context memory | [Micron FY26 Q3 results](https://investors.micron.com/news-releases/news-release-details/micron-technology-inc-reports-record-results-third-quarter) | 推理与长上下文需求直接推高内存重要性，财务证据极强但周期性风险也高。 |
| 6 | ANET | Q1 收入 27.09 亿美元，同比增长 35.1%；XPO MSA 指向 AI networking 机架/空间效率 | Ethernet AI networking、data-center spine | [Arista Q1 2026 results](https://investors.arista.com/Communications/Press-Releases-and-Events/Press-Release-Detail/2026/Arista-Networks-Inc--Reports-First-Quarter-2026-Financial-Results/default.aspx) | 大规模推理/训练集群需要网络吞吐，ANET 是非 GPU 链条关键观察点。 |
| 7 | VRT | Q1 销售 26.5 亿美元，同比增长 30%；Americas organic +44%；上调全年指引 | 电力、散热、critical digital infrastructure | [Vertiv Q1 2026 results](https://investors.vertiv.com/news/news-details/2026/Vertiv-Reports-Strong-First-Quarter-with-Diluted-EPS-Growth-of-136-Adjusted-Diluted-EPS-Growth-of-83-Raises-Full-Year-Guidance/default.aspx) | AI data center 物理瓶颈已经反映到订单、收入和利润率。 |
| 8 | CEG | Calpine 组合后强调为 AI 时代数据中心和关键基础设施供电 | 核电、燃气、地热、数据中心电力 | [Constellation FY2025 results](https://investors.constellationenergy.com/news-releases/news-release-details/constellation-reports-fourth-quarter-and-full-year-2025-results/) | 电力是 AI data center 扩张限制条件，但公司级利润归因需要继续验证。 |
| 9 | GEV | 官方 data-center power solutions；二级报道指向 AI data center 电力设备需求 | 燃机、电气化、grid equipment | [GE Vernova data centers](https://www.gevernova.com/consulting/solutions/data-centers)、[IBD AI data-center article](https://www.investors.com/news/ge-vernova-stock-buy-points-ai-data-centers/) | 电力设备是 AI capex 的第二层受益链，但本轮 primary segment 证据不足。 |
| 10 | MSFT | AI business ARR 超 370 亿美元，同比增长 123%；Azure +40%；commercial RPO +99% | Hyperscaler demand source、cloud AI、enterprise inference | [Microsoft FY26 Q3 results](https://www.microsoft.com/en-us/investor/earnings/fy-2026-q3/press-release-webcast) | 是需求端与 AI 应用变现验证点，但 capex ROI 与估值压力要分开看。 |
| 11 | AMZN | 过去 12 个月部署 210 万+ AI chips；2026 起部署 100 万+ NVIDIA GPUs；Bedrock tokens 增速强 | AWS、Trainium/Inferentia、cloud inference | [Amazon Q1 2026 results](https://ir.aboutamazon.com/news-release/news-release-details/2026/Amazon-com-Announces-First-Quarter-Results/default.aspx) | 云端推理需求信号强，但作为 hyperscaler 更偏需求源而非纯供应链受益。 |
| 12 | GOOGL | Google Cloud 收入 200 亿美元，同比增长 63%；Q1 capex 357 亿美元，主要用于 AI 基础设施 | TPU、Google Cloud、AI infrastructure buyer/operator | [Alphabet Q1 2026 call](https://abc.xyz/investor/events/event-details/2026/2026-Q1-Earnings-Call-2026-nW8kCrBAKS/default.aspx)、[SEC exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000043/googexhibit991q12026.htm) | AI cloud 收入和 capex 同时高增，是需求端验证，但资本效率需跟踪。 |
| 13 | META | FY26 capex 指引提高到 1250-1450 亿美元；AI / personal superintelligence 叙事 | Frontier AI demand source、data-center capex | [Meta Q1 2026 results](https://investor.atmeta.com/investor-news/press-release-details/2026/Meta-Reports-First-Quarter-2026-Results/default.aspx) | AI capex 强度极高，但投资回报路径和技术面均需审慎。 |
| 14 | ORCL | RPO 6380 亿美元，同比增长 363%；自由现金流因 OCI 基建投入转负 | AI cloud capacity、OCI、contracted backlog | [Oracle FY2026 results](https://investor.oracle.com/investor-news/news-details/2026/Oracle-Announces-Record-Q4-and-FY-2026-Results-Driven-by-Cloud-Infrastructure--Cloud-Applications/default.aspx) | 合同积压极强，但融资、现金流和交付风险突出。 |
| 15 | QCOM | 二级报道显示进入 AI data-center compute，并提出大额 data-center 收入目标 | 低功耗推理、AI data-center optionality | [IBD Qualcomm article](https://www.investors.com/news/technology/qualcomm-stock-ai-data-center-play/) | 是新增可选项，当前证据偏早期，需等官方收入/客户验证。 |

### 1.3 Active Candidates

本轮筛选标准：证据强度、AI 链条直接性、公司披露质量、流动性、技术面、是否能被后续 sections 验证。最多 8 个。

| Active | 进入原因 | 主要风险/待验证 |
| --- | --- | --- |
| NVDA | AI factory 与 inference/full-stack 最核心；收入和 roadmap 证据最强。 | 预期拥挤、出口限制、毛利率/网络业务节奏、供应链执行。 |
| AVGO | Custom ASIC 与 AI networking 收入爆发，直接验证 hyperscaler custom silicon。 | 客户集中、订单时点、ASIC 周期与替代风险。 |
| MU | HBM/内存瓶颈财务证据强，推理和长上下文直接相关。 | 存储周期性、价格波动、扩产后供需错配。 |
| TSM | AI capex 和先进制程/封装瓶颈明确，是全链条基础设施底座。 | 地缘政治、设备供给、客户集中、capex 折旧压力。 |
| VRT | AI data center 电力和散热瓶颈已进入收入/利润率。 | 产能扩张执行、订单转收入、竞争和项目周期。 |
| ANET | AI Ethernet/networking 是非 GPU bottleneck；收入与产品线均有验证。 | NVIDIA Spectrum-X 等竞争、客户采购节奏。 |
| AMD | 替代 accelerator 和 EPYC 数据中心增长提供第二供给曲线。 | GPU 份额、软件生态、毛利率和客户转化。 |
| CEG | 电力约束是 AI data center 的硬限制；核电/燃气/地热组合具备主题相关性。 | 技术面弱，公司级 AI data-center 利润归因仍不足，监管/项目周期长。 |

Watchlist：MSFT、AMZN、GOOGL、META、ORCL、GEV、QCOM。  
Deferred：CRWV、SMCI、DELL、HPE、ETN、IREN。原因分别包括公开历史较短、财务/治理噪音、差异化不足、primary evidence 不足或加密业务邻近风险。

## 2. AI Information & Sentiment Section

### 2.1 10 条核心信息

| # | 日期 | 信息 | Source type | 对主题的含义 |
| --- | --- | --- | --- | --- |
| 1 | 2026-05-20 | NVIDIA FY27 Q1 Data Center 收入 752 亿美元，同比增长 92%；networking 同比 199%。 | 官方披露 | AI infrastructure 需求仍直接体现为 GPU/networking 收入。 |
| 2 | 2026-05-31 | NVIDIA Vera Rubin 进入 full production，强调 agentic AI factories。 | 官方披露 | 供应链从 Blackwell 向 Rubin 过渡，推理/agentic 被放到中心位置。 |
| 3 | 2026-06-03 | Broadcom AI semiconductor 收入 108 亿美元，预计 Q3 160 亿美元。 | 官方披露 | Custom AI ASIC 和 networking demand 高速增长。 |
| 4 | 2026-06-24 | Micron record quarter，HBM4 high-volume shipments。 | 官方披露 | HBM 和内存成为推理与长上下文扩张的关键瓶颈。 |
| 5 | 2026-05 | AMD Data Center 收入 58 亿美元，Meta 最高 6GW Instinct plan。 | 官方披露 | Hyperscaler 正在寻找第二 accelerator 供给源。 |
| 6 | 2026-05 | Arista Q1 收入 27.09 亿美元，XPO MSA 指向 AI networking efficiency。 | 官方披露 | AI 集群网络层正在成为独立受益层。 |
| 7 | 2026-04-22 | Vertiv Q1 销售 +30%，Americas organic +44%，上调全年指引。 | 官方披露 | 电力/散热/机房基础设施需求正在转化为财务指标。 |
| 8 | 2026-04-29 | Alphabet Google Cloud +63%，Q1 capex 357 亿美元，主要用于 AI infrastructure。 | 官方披露/SEC | Hyperscaler capex 是供应链需求源，但也提高资本效率问题。 |
| 9 | 2026-04-29 | Meta FY26 capex 指引提高至 1250-1450 亿美元。 | 官方披露 | Frontier AI 与社交 AI 推动超大规模资本开支。 |
| 10 | 2026-05 | Amazon 过去 12 个月落地 210 万+ AI chips，Bedrock tokens 强增长。 | 官方披露 | 云端 inference token demand 有直接运营信号。 |

辅助信息：William Blair 估计 2026 hyperscaler capex 接近 7000 亿美元，并把半导体、网络、电力、散热和施工列为 AI infrastructure supply chain；BloombergNEF 估计大型 data-center 相关公司 2026 capex 可能接近 7500 亿美元；Tom's Hardware 指出电力、劳动力、高压电工、HVAC、fiber 与 commissioning 都可能成为部署瓶颈。  
来源：[William Blair](https://im.williamblair.com/insights/articles/the-ai-infrastructure-supply-chain-ai-enablers-growing-alongside-hyperscalers)、[BloombergNEF](https://about.bnef.com/insights/data-centers/ai-data-center-build-advances-at-full-speed-five-things-to-know/)、[Tom's Hardware](https://www.tomshardware.com/tech-industry/data-centers/ai-data-center-boom-hits-a-human-bottleneck-critical-skilled-labor-shortages-could-slow-deployment-despite-billions-in-funding)。

### 2.1.1 播客 transcript 复核

复核原因：初始运行时未加载项目 `.env`，导致 `TRANSCRIPT_API_KEY` 被误判为 missing。加载 `.env` 后，TranscriptAPI 调用成功。

| Source | Episode | Transcript check | Topic signal |
| --- | --- | --- | --- |
| No Priors | [Re-engineering the Semiconductor Supply Chain with Intel CEO Lip Bu Tan](https://www.youtube.com/watch?v=asCgCv2XB4s) | 1193 segments，约 43.9k chars | 命中 AI、semiconductor、data center、power、Intel、NVIDIA 等关键词；适合作为 semiconductor / supply chain 入口。 |
| All-In Podcast | [World's First Trillionaire, Anthropic Fable Banned, The New Oligarchs, Iran Peace Deal](https://www.youtube.com/watch?v=3Amlu4y94Ho) | 2385 segments，约 87.1k chars | 命中 AI、Anthropic、power、chip、Intel、data center 等关键词；适合作为 AI sentiment / capex debate 入口。 |

后续周报应把 `@NoPriorsPodcast` 和 `@allin` 作为播客优先路径：先跑 channel latest，再按主题词筛选 episode，再拉 transcript，不要只依赖通用 YouTube 搜索。

### 2.2 5 篇论文

| # | 论文 | Source type | 主题映射 |
| --- | --- | --- | --- |
| 1 | [SharQ: Bridging Activation Sparsity and FP4 Quantization for LLM Inference](http://arxiv.org/abs/2606.26587v1) | arXiv | 推理量化，降低单位 token 成本。 |
| 2 | [Information-Aware KV Cache Compression for Long Reasoning](http://arxiv.org/abs/2606.26875v1) | arXiv | 长推理 KV cache 压缩，映射 HBM/显存瓶颈。 |
| 3 | [PersistentKV: Page-Aware Decode Scheduling for Long-Context LLM Serving on Commodity GPUs](http://arxiv.org/abs/2606.26666v1) | arXiv | 长上下文 serving 调度，映射 GPU 利用率。 |
| 4 | [Moebius: Serving Mixture-of-Expert Models with Seamless Runtime Parallelism Switch](http://arxiv.org/abs/2606.26607v1) | arXiv | MoE serving，对 networking、memory 和调度有需求。 |
| 5 | [Speculation at a Distance: Where Edge-Cloud Speculative Decoding Actually Pays Off](http://arxiv.org/abs/2606.25091v1) | arXiv | speculative decoding 与 edge-cloud inference tradeoff。 |

解释：这些论文不是投资证据本身，而是技术方向证据。共同指向 inference serving 正在围绕 KV cache、量化、调度、MoE 和 speculative decoding 优化，可能降低单位成本，同时通过更低价格扩大总需求。

### 2.3 5 个开源项目

| # | 项目 | 观察信号 | Source type | 主题映射 |
| --- | --- | --- | --- | --- |
| 1 | [vLLM](https://github.com/vllm-project/vllm) | 84k+ stars，2026-06-26 仍活跃更新 | GitHub | 高吞吐 inference serving。 |
| 2 | [SGLang](https://github.com/sgl-project/sglang) | 29k+ stars，服务 LLM/VLM workloads | GitHub | agentic / multimodal serving framework。 |
| 3 | [TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM) | NVIDIA 推理栈，持续活跃 | GitHub | GPU inference optimization。 |
| 4 | [llama.cpp](https://github.com/ggml-org/llama.cpp) | 118k+ stars，edge/local inference 高关注 | GitHub | 本地/边缘推理，长期可能影响云端需求结构。 |
| 5 | [LMCache](https://github.com/LMCache/LMCache) | KV cache reuse 方向，活跃度高 | GitHub | 长上下文和 agent workloads 的 memory efficiency。 |

补充观察：[Dynamo](https://github.com/ai-dynamo/dynamo) issue/roadmap 指向从 LLM serving 扩展到 agent、RL rollout、diffusion 和 multimodal inference。该信号支持“推理工作负载复杂化”的判断，但仍属技术/社区证据，不是公司收入证据。

### 2.4 高信号舆情证据

| # | 证据 | Source type | 读法 |
| --- | --- | --- | --- |
| 1 | [Hacker News: Is AI Profitable Yet?](https://news.ycombinator.com/item?id=48243863) | 开发者/投资者讨论 | 关注 inference margin、API 价格是否可持续，提供反身性风险。 |
| 2 | [Hacker News: AI is slowing down](https://news.ycombinator.com/item?id=48446893) | 技术社区讨论 | 对模型进步、成本曲线、推理 economics 有分歧。 |
| 3 | [Reddit r/investing: How the AI bubble is going to pop](https://www.reddit.com/r/investing/comments/1t9txw5/how_the_ai_bubble_is_going_to_pop/) | 零售/社区情绪 | 市场担心硬件 moat 和 capex 回收周期。 |
| 4 | [Reddit r/stocks: The market seems to think everyone in AI will be a long-term winner](https://www.reddit.com/r/stocks/comments/1t8tgfg/the_market_seems_to_think_everyone_in_ai_will_be/) | 投资者讨论 | 明确讨论供应商 FCF 与 hyperscaler FCF 的错位。 |
| 5 | [Reddit r/stocks: How long do you expect the AI gold rush to last?](https://www.reddit.com/r/stocks/comments/1ua8ukh/how_long_do_you_expect_the_ai_gold_rush_to_last/) | 投资者讨论 | 担心 2027 后 capex 增速放缓带来估值冲击。 |

### 2.5 当前叙事与长期假设

当前 observed story：

1. AI infrastructure 正从“训练 GPU 短缺”扩展到“agentic inference factories”。
2. 供应链受益层从 GPU 扩散到 custom ASIC、HBM、Ethernet/networking、液冷/电力、数据中心电源。
3. Hyperscalers 是需求源，但不等于一定是最优观察标的；它们同时承担资本开支、折旧和 ROI 风险。
4. 社区舆情的分歧点不在“AI 是否重要”，而在“capex 是否过热、token economics 是否足以支撑投资回报”。

长期 projection，分层标注：

| 时间 | Fact | Inference | Hypothesis |
| --- | --- | --- | --- |
| 6-18 个月 | 多家公司已披露 AI data-center、HBM、networking、cooling、电力相关收入或 capex。 | 推理/agentic workloads 会持续推高 serving、memory 和 network demand。 | 单位 token 成本下降可能通过需求弹性提高总算力消耗。 |
| 2-5 年 | TSMC、NVIDIA、Broadcom、Micron、Vertiv 等正在扩产或提高指引。 | Custom ASIC、GPU、HBM 和 data-center physical infrastructure 将并行受益。 | 电力、许可、劳动力和并网速度可能成为比芯片更慢的瓶颈。 |
| 5 年以上 | 大型云厂商已经将 AI infrastructure 作为长期战略。 | 产业链利润会在不同周期阶段迁移。 | 若 AI 应用收入未覆盖 capex，hyperscaler 端可能成为估值压力源。 |

## 3. Fundamental Section

### 3.1 基本面闭环

| Active | Evidence | Inference | Hypothesis |
| --- | --- | --- | --- |
| NVDA | Data Center 收入、networking 增长、Rubin roadmap。 | AI factory 与 agentic inference 需求仍在推动硬件升级。 | 平台软件和网络绑定会延长竞争优势。 |
| AVGO | AI semiconductor 收入和 Q3 指引。 | Hyperscaler custom ASIC 已进入可计量收入阶段。 | Custom silicon 不会替代 GPU，而是形成第二增长层。 |
| MU | HBM4 出货、Cloud/Core data-center memory 收入、FQ4 指引。 | 内存从周期品变成 AI infrastructure bottleneck 的重要组成。 | 长上下文和 agentic workflows 会提高 HBM/DRAM 消耗强度。 |
| TSM | 高 capex、AI/HPC 需求强、供给 tight。 | Advanced nodes 和封装产能是全链条约束。 | 若 AI demand 可持续，TSMC 的定价和资本回报可能保持强势。 |
| VRT | 收入、利润率、Americas demand、全年指引上调。 | 电源、散热和机房基础设施正在从瓶颈变成财务增长。 | 高密度 rack 与液冷会延长需求周期。 |
| ANET | 收入增长、AI networking 产品与效率叙事。 | AI 集群 scale-out 需要更强 Ethernet/networking。 | Ethernet 生态能在部分 AI workloads 中扩大份额。 |
| AMD | Data Center 增长、Instinct ramp、Meta 计划。 | 第二 accelerator 供给曲线被 hyperscaler 认真采用。 | 软件生态改善后可能获得更高 AI accelerator 份额。 |
| CEG | 官方将 Calpine 组合与 AI age power demand 连接。 | 数据中心电力需求提升 baseload/低碳/灵活发电价值。 | AI data-center 长约可能改善公用事业/发电资产的现金流可见度。 |

### 3.2 横向判断

最强财务证据：NVDA、AVGO、MU、TSM、VRT。  
最强技术/开源趋势映射：NVDA、MU、ANET、AMD、TSM。  
最强 physical bottleneck 映射：VRT、CEG、GEV。  
最弱闭环：CEG 的公司级 AI 收入归因；QCOM 的收入验证；ORCL 的自由现金流与融资风险；hyperscaler 的 capex ROI。

### 3.3 主要证伪条件

| 观察对象 | 证伪条件 |
| --- | --- |
| NVDA | Data Center 指引降温、networking 增速快速回落、出口限制放大、毛利率下行。 |
| AVGO | Custom ASIC 客户订单推迟、单一客户依赖加剧、AI semis 指引回落。 |
| MU | HBM/DRAM 价格转弱、扩产后供需过剩、客户采购节奏反转。 |
| TSM | AI/HPC 客户削减订单、先进封装供给不再紧、capex 回报率下降。 |
| VRT | 订单无法转收入、产能扩张拖累利润率、数据中心项目延迟。 |
| ANET | AI Ethernet 渗透不及预期、NVIDIA 或其他垂直栈压制、云客户采购节奏放缓。 |
| AMD | Instinct 客户转化不及预期、软件生态拖累、与 NVDA 差距扩大。 |
| CEG | 数据中心电力合同缺少经济性、监管限制、技术面继续走弱。 |

## 4. Technical Section

数据源：Nasdaq 日线 OHLCV，最近交易日 2026-06-25。  
限制：未取得周线图像、200 周均线和人工画线图；以下为日线级别技术观察，不构成交易信号。

| Active | Close | 1W | 1M | 3M | 20D MA | 50D MA | 200D MA | 3M support | 3M resistance | 技术读法 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| NVDA | 195.74 | -4.4% | -8.9% | +9.5% | 208.85 | 210.21 | 190.53 | 164.27 | 236.54 | 回调后仍在 200D 上方，需重新站回 20/50D 才算修复。 |
| AVGO | 378.91 | -3.6% | -10.2% | +18.9% | 406.77 | 412.60 | 361.17 | 289.96 | 495.00 | 中期仍强于大盘，但短线低于 20/50D。 |
| MU | 1213.56 | +16.3% | +35.5% | +217.6% | 1024.97 | 788.62 | 420.85 | 311.49 | 1255.00 | 动量极强且接近 52 周高点，短期过热风险高。 |
| TSM | 434.99 | +0.7% | +5.5% | +25.1% | 433.61 | 411.50 | 339.26 | 313.80 | 476.79 | 均线结构健康，靠近短线均线，趋势仍偏建设性。 |
| VRT | 325.57 | +2.5% | +0.5% | +17.9% | 314.80 | 324.04 | 228.05 | 231.70 | 379.94 | 站上 20D，贴近 50D，若守住 315-324 区间趋势可延续。 |
| ANET | 165.45 | +0.3% | +4.7% | +22.5% | 163.55 | 159.82 | 142.68 | 115.42 | 179.80 | 稳定高于主要均线，180 附近为上方确认区。 |
| AMD | 532.57 | +3.9% | +5.7% | +141.8% | 512.22 | 433.85 | 268.64 | 192.87 | 562.99 | 趋势极强但三个月涨幅大，需警惕高位波动。 |
| CEG | 268.69 | +0.6% | -10.9% | -11.4% | 264.91 | 282.99 | 318.60 | 240.51 | 328.80 | 基本面主题强，技术面偏弱，属于修复型观察而非趋势确认。 |

参照 ETF：SOXX 三个月 +81.1%，SMH +59.6%，QQQ +21.9%，SPY +12.4%。半导体相对强度显著高于大盘；software ETF IGV 三个月仅 +5.4%，说明本轮市场偏好更集中在硬件与物理基建。

## 5. Reflection Section

### 5.1 逻辑闭环检查

本轮闭环较强的链条：

1. Agentic / inference demand -> GPU/ASIC/HBM/networking -> NVDA、AVGO、MU、TSM、ANET。
2. Hyperscaler capex -> high-density data centers -> VRT、CEG、GEV。
3. 推理效率提升 -> 单位成本下降 -> 更高 token demand 的可能性。

薄弱链条：

1. Hyperscaler capex 到股东回报之间仍缺少统一答案。
2. 电力链条是结构性瓶颈，但 CEG/GEV 的公司级 AI 收益归因仍不如半导体和 VRT 清晰。
3. 社区舆情对 AI profitability、API margin 和 capex bubble 有明显分歧。

### 5.2 Cathie Wood vs Buffett 视角辩论

Cathie Wood 视角：

AI 推理成本下降和 agentic workloads 可能引发需求弹性，市场低估了从 GPU 到 HBM、networking、cooling、power 的扩散效应。应关注技术学习曲线、开源推理栈和供应链瓶颈，而不是只看当期利润率。

Buffett 视角：

要区分“技术重要性”和“股东回报确定性”。Hyperscaler capex 可能很大，但如果客户付费和现金回收不够清晰，资本开支会削弱自由现金流。半导体和内存仍有周期性；真正值得持续跟踪的是定价权、长期合同、现金流质量和可理解的护城河。

裁决：

保留 AI infrastructure 主线，但把结论拆成两层：供应链收入已验证层和 capex ROI 待验证层。NVDA、AVGO、MU、TSM、VRT 的 evidence-to-revenue 链条最清楚；CEG/GEV 所在 power theme 很关键，但公司级归因和技术确认不足，需要更多合同、监管和现金流证据。

## 6. Final AI Trend Narrative Conclusion

本周最小实验的核心结论：

AI infrastructure 的市场叙事正在从“GPU training shortage”扩展为“agentic inference factories + HBM/networking/power/cooling bottlenecks”。这不是单一股票故事，而是供应链多层扩散故事。

证据最强的方向：

1. GPU/full-stack AI factory：NVDA。
2. Custom ASIC 与 AI networking：AVGO、ANET。
3. HBM/内存：MU。
4. Advanced foundry / packaging：TSM。
5. Data-center power/cooling：VRT。
6. Alternative accelerator：AMD。
7. Power supply：CEG 进入观察，但需要更强公司级归因。

对 long-horizon projection 的谨慎判断：

Fact：多家官方披露已经显示 AI data-center、AI semis、HBM、cloud AI 和 physical infrastructure 的收入或 capex 增长。  
Inference：推理需求正在把瓶颈从单纯 GPU 扩散到内存、网络、电源、散热、场地和电网。  
Hypothesis：如果推理效率提升导致总 token demand 更快增长，则供应链需求可能继续上修；如果 AI 应用收入无法覆盖 capex，则 hyperscaler 与高估值供应商都可能承受回撤。

本报告不包含买卖建议、目标价或仓位建议。

## 7. Paper Observation Ledger

本次选择 5 个进入纸面观察账本。入口价格不使用盘中价；计划使用本报告发布后下一个可获得的美股常规交易日收盘价作为 entry reference，观察 5 个交易日后收盘相对表现。

| Ticker | 观察假设 | 最新参考收盘 | Entry rule | Exit rule | Benchmark |
| --- | --- | ---: | --- | --- | --- |
| NVDA | AI factory/inference 平台收入与 roadmap 是否继续被市场确认。 | 195.74 | 2026-06-26 之后首个可得常规收盘 | Entry 后第 5 个交易日收盘 | SMH、SOXX、QQQ |
| AVGO | Custom ASIC + AI networking 收入爆发是否具备延续性。 | 378.91 | 同上 | 同上 | SMH、SOXX |
| MU | HBM/内存瓶颈是否继续获得相对强度确认。 | 1213.56 | 同上 | 同上 | SOXX、SMH |
| VRT | Data-center power/cooling bottleneck 是否继续从订单传导到价格趋势。 | 325.57 | 同上 | 同上 | XLK、SPY |
| CEG | AI power scarcity 主题能否克服当前技术弱势并获得修复。 | 268.69 | 同上 | 同上 | SPY、XLU、QQQ |

Ledger 禁止事项：不连接券商账户；不下单；不做仓位；不输出目标价；只记录 paper entry/exit、相对基准、事后归因。

事后归因字段模板：

| 字段 | 说明 |
| --- | --- |
| Entry date / price | 报告后下一个常规收盘。 |
| Exit date / price | Entry 后第 5 个交易日收盘。 |
| Absolute return | 纸面观察收益率。 |
| Benchmark relative return | 相对 SMH/SOXX/QQQ/SPY/XLU 的差异。 |
| Attribution | 信息面、基本面、技术面、市场风格、外部风险。 |
| Falsification update | 哪条假设被加强、削弱或证伪。 |

## 8. Quality Gate

| Gate | 状态 |
| --- | --- |
| 10 news items | 通过 |
| 5 papers | 通过 |
| 5 open-source projects | 通过 |
| 5 high-signal sentiment evidence items | 通过 |
| Raw candidates 10-15 | 通过，15 个 |
| Active candidates <= 8 | 通过，8 个 |
| 每个候选说明触发信号、链条位置、证据来源、进入理由 | 通过 |
| 不输出买卖建议、目标价、仓位 | 通过 |
| 数据节点失败时显式说明 | 通过 |
| 区分 evidence / inference / hypothesis | 通过 |
| 区分当前故事与长期 projection | 通过 |

## 9. Skill Scout / Maintenance Notes

本次为最小实验，没有安装新插件或新增技能。建议维护项：

1. 配置 Longbridge CLI 或可调用接口，恢复实时/历史行情、基本面和研究数据节点。
2. 确保周报 runner 自动加载项目 `.env` 中的 `TRANSCRIPT_API_KEY`，避免 transcript 节点被误判为 missing。
3. 将已安装的 `yfinance==1.4.1` 写入项目依赖清单或 runner 检查项，并保留 Nasdaq historical price fallback。
4. 增加一个 Nasdaq historical price fallback 脚本，把本次手动恢复路径产品化。
5. 为 Paper Observation Ledger 添加自动化归因模板，但保持 read-only 与 paper-only。
