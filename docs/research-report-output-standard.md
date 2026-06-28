# Research Report Output Standard

返回：[README](../README.md) · [AGENCY](../AGENCY.md) · [Quality Gate](weekly-brief-quality-gate.md)

本文件定义最终投资研究报告的可选结构、默认发布结构、禁止事项，以及各 agent 交给下游的固定交接格式。

调研日期：2026-06-28

## 公开格式对照

| 来源格式 | 公开来源 | 核心结构 | 对本系统的启发 | 本系统改造 |
|---|---|---|---|---|
| Sell-side equity research update | [CFI Equity Research Report](https://corporatefinanceinstitute.com/resources/valuation/equity-research-report/): recommendation/price target、recent updates、investment thesis、valuation、risks | 先给推荐和关键变化，再给 thesis、估值和风险 | 适合忙碌老板快速决策 | 保留“结论先行、thesis、valuation/risk”框架；把 buy/sell/target price 改成 research action rating、confidence、estimated upside range，不给真实交易指令 |
| CFA-style full coverage report | [CFA Institute Equity Research Report Essentials](https://www.cfainstitute.org/sites/default/files/-/media/documents/support/research-challenge/challenge/rc-equity-research-report-essentials.pdf): business description、industry overview、investment summary、valuation、financial analysis、investment risks、ESG | 从公司、行业、估值、财务、风险完整建模 | 适合单票深度研究和证据附录 | 深度内容进入 evidence subfile 或 appendix；主报告只保留最硬证据和结论 |
| Morningstar-style quality and fair value report | [Morningstar Equity Analyst Report Features](https://advisor.morningstar.com/Enterprise/VTC/EquityResearchReportv2.pdf): rating driven by economic moat、fair value estimate、uncertainty、current price；含 Bulls Say、Bears Say、Moat、Risk、Stewardship | 把质量、护城河、估值不确定性和牛熊两面固定化 | 适合长期质量、moat、capital allocation 讨论 | 引入 moat/uncertainty/capital allocation 视角，但不输出星级或个性化建议 |

补充约束来源：

- [CFA Standard V(A)](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-v-a) 要求投资分析有 diligence、independence、thoroughness 和 reasonable basis。
- [FINRA Rule 2210](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2210) 要求 communications fair and balanced，不能 false、exaggerated、promissory 或 misleading。
- [FINRA Rule 2241](https://www.finra.org/rules-guidance/rulebooks/finra-rules/2241) 要求研究报告的事实有可靠信息基础，rating / price target 需要合理依据、估值方法和风险说明，并披露相关冲突。

## 三个最终报告版本

### Version A：老板决策页 + 证据包

默认用于每周周报、广义 AI 趋势 brief、实验报告、Top 5 Research Action Pool。

```markdown
# 老板决策页：{report_title}

## 1. 一句话结论
- 主结论：
- 整体置信度：高 / 中 / 低
- 本周研究裁决：强确认 / 保留 / 降级 / 暂缓 / 剔除

## 2. 本周研究动作
| Rank | Ticker / Theme | Research Rating | Confidence | Est. Upside Range | Est. Holding Range | Exit / Trim Rule | Why Now | Hard Evidence Summary | Evidence Pack | Falsification |
|---:|---|---|---:|---|---|---|---|---|---|---|

## 3. 不进核心池
| Ticker / Theme | Treatment | Reason |
|---|---|---|

## 4. 最大风险与下周验证
- 最大反证：
- 下周只看：
  1.
  2.
  3.

# 证据索引
- 主报告只放 2-3 条证据摘要。
- 完整证据写入 `reports/{report_slug}.evidence.md`。

## 5. 核心判断与硬证据
| 判断 | 处理 | 证据强度 | 最硬证据摘要 | Evidence Pack | 风险/证伪 |
|---|---|---|---|---|---|

# 附录
## A. Intent Route Plan
## B. 上游 Section 状态
## C. 数据节点状态
## D. 质量检查
```

### Version B：单票 / 单链条深度覆盖

用于用户要求 single-name deep dive、fundamental deep dive、行业链条专题。

```markdown
# 深度研究：{ticker_or_theme}

## 1. 投资研究摘要
- 研究动作：
- 置信度：
- Mispricing / expectation gap：
- 最大反证：

## 2. 公司与业务经济性
| 业务/产品 | 收入/利润机制 | AI 暴露 | 证据 |
|---|---|---|---|

## 3. 行业与竞争位置
| 竞争维度 | 现状 | 证据 | 影响 |
|---|---|---|---|

## 4. 财务传导与估值/预期差
| 叙事 | 财务科目 | 已验证 | 未验证 | 估值含义 |
|---|---|---|---|---|

## 5. 技术面与市场定价
| 周期 | 趋势 | 关键位 | 失效 | 解释边界 |
|---|---|---|---|---|

## 6. 风险、反证与下次验证
## 7. Evidence Pack / Appendix
```

### Version C：Moat / Uncertainty / Bull-Bear Scorecard

用于质量公司、长期趋势、估值分歧、Wood vs Buffett 分歧较大的主题。

```markdown
# 质量与不确定性评分卡：{ticker_or_theme}

## 1. 结论卡
| 维度 | 结论 | 置信度 | 证据 |
|---|---|---:|---|
| Research Rating |  |  |  |
| Moat / 竞争优势 | Wide / Narrow / None / Unclear |  |  |
| Fair-value direction | Undervalued / Fair / Overvalued / Unclear |  |  |
| Uncertainty | Low / Medium / High / Extreme |  |  |
| Capital Allocation | Strong / Standard / Weak / Unclear |  |  |

## 2. Bulls Say
| Bull Case | Evidence | What Must Be True |
|---|---|---|

## 3. Bears Say
| Bear Case | Evidence | What Would Break Thesis |
|---|---|---|

## 4. Profit Drivers 与中间验证指标
## 5. 风险与反证
## 6. Evidence Pack / Appendix
```

## 默认选择规则

| 任务 | 默认报告版本 | 备注 |
|---|---|---|
| `full_weekly_brief` | Version A | 必须以老板决策页开头 |
| `stock_discovery_only` | Version A 的候选池子集 | 不输出最终 research action rating |
| `information_sentiment_only` | 中间 section 格式 | 不输出最终投资结论 |
| `fundamental_deep_dive` | Version B | 可以加入 Version C 的 moat/uncertainty 表 |
| `technical_deep_dive` | 技术 section 格式 | 不输出基本面结论 |
| `reflection_only` | Reflection section 格式 | 不新增事实 |
| `paper_attribution_review` | Paper Attribution section 格式 | 不连接 broker |

## 最终报告硬限制

最终报告一定避免：

1. 不以 Intent Route Plan、运行日志、数据节点状态、工具失败、质量检查开头。
2. 不把长证据表、长新闻清单、论文清单、GitHub 清单塞进老板决策页。
3. 不输出真实下单、账户操作、仓位比例、资金分配、再平衡或 broker 指令。
4. 不输出无估值方法和风险说明支撑的 target price。本系统默认使用 `estimated_upside_range_pct`，且标明研究情景。
5. 不承诺收益，不写“必涨/必跌/确定跑赢”，不暗示历史表现会重复。
6. 不把单一新闻、KOL、播客、Reddit/HN/X 热度当作事实或投资结论。
7. 不把 AI 论文、benchmark 或 GitHub stars 直接等同于商业收入。
8. 不把 K 线强势写成基本面改善；不把基本面改善写成市场已经定价。
9. 不混淆事实、推断、假设、长期场景推演。
10. 不使用无日期、无链接、错链、过时或无法复核的证据支撑高置信度判断。
11. 不凑满 Top 5；低于门槛时宁可少于 5 个。
12. 不把 perspective skills、third-party tools 或模型输出当作最终权威。
13. 不隐藏数据节点失败；失败必须降低置信度或降级为 partial。
14. 不把披露、限制、风险只丢到脚注导致读者无法理解主判断。

## 中间 Agent 交接总规

每个中间 agent 必须把输出压缩成一个 `Downstream Handoff`，让下一位 agent 不需要重读所有原始材料也能继续工作。

通用格式：

```markdown
## Downstream Handoff
| Field | Content |
|---|---|
| Handoff ID | {agent}-{date}-{theme_or_ticker} |
| Input Status | complete / partial / failed |
| Decision Needed From Next Agent |  |
| Must-Carry Evidence |  |
| Key Assumptions | fact / inference / hypothesis 分列 |
| Missing Proof |  |
| Downgrade Triggers |  |
| Do-Not-Carry | 下游不能继承的噪音、弱证据或禁区 |
| Evidence Anchors | 源链接、上游 section anchor 或 evidence subfile anchor |
```

## 各 Agent 交接契约

| From -> To | 下游最需要收到什么 | 绝对不能夹带什么 |
|---|---|---|
| Intent Router -> Harness | Task type、selected/skipped agents、data-node plan、missing inputs、安全边界、质量门 | 投资判断、rating、目标价、候选排序 |
| Stock Discovery -> AI Info/Fundamental/Technical | 最多 8 个 active candidates、signal families、AI/industry position、why now、missing proof、next agent | 买卖建议、Research Buy、目标价、单源候选升级为 active |
| AI Info & Sentiment -> Fundamental/Technical/Reflection | 事实/观点/舆情/论文/GitHub 分离后的证据、当前故事、长期远演、候选受益链、反方证据 | 把舆情当事实、把论文/GitHub 当收入、把远期推演当当前结论 |
| Fundamental -> Reflection/Final | 叙事 -> 财务科目 -> 估值/预期差、交叉验证、priced-in 判断、可证伪指标 | 无依据 forecast、目标价、把新闻热度当财务证据 |
| Technical -> Reflection/Final/Paper | 数据时间戳、趋势、关键位、情景概率、失效位、技术面是否支持候选叙事 | 第一轮用新闻解释图表、交易指令、仓位建议 |
| Reflection -> Final | 保留/降级/暂缓、最弱一环、Wood vs Buffett 分歧、质量检查、最大反证 | 新事实、未经上游支持的乐观/悲观判断 |
| Final -> Paper Attribution | Thesis ID、Top 5 / excluded、research rating、confidence、estimated upside、holding range、exit/trim rule、evidence pack、review date | 真实订单、账户动作、仓位比例、保证收益 |
| Paper Attribution -> Next Stock Discovery/Final | expected vs actual、benchmark-relative return、归因分类、signal weight updates、process changes | 事后合理化、把偶然涨幅奖励给原始 thesis、live trading |
| Skill Scout -> Harness Appendix | 候选 skill、benchmark、risk、install/watch/reject、安装路径 | 投资结论、自动交易工具、opaque installer、账户/密钥读取能力 |

## 证据标签

所有 agent 必须使用以下证据身份之一：

- `Fact`: 可复核的一手披露、SEC/IR、公司公告、价格/财务数据、论文/GitHub 原始链接。
- `Inference`: 基于事实的推断，必须写出中间链条。
- `Hypothesis`: 尚未被验证的研究假设或长期远演。
- `Opinion`: KOL、播客、社区、分析师观点。
- `Market Signal`: 价格、量价、资金流、sector rotation 或市场注意力。
- `Data Gap`: 数据失败、数量不足、无法交叉验证或过时。
