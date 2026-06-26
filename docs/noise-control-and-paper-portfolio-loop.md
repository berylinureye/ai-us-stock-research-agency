# 噪音控制与模拟观察闭环设计

## 1. 为什么需要这个闭环

随着 skills 和数据入口增加，系统会遇到两个问题：

- **信息噪音增加**：新闻、播客、GitHub、技术面、财报、机构持仓都能产生候选，但并非每个候选都值得深挖。
- **缺少真实反馈**：如果每周只写报告，不记录后来股价和 thesis 是否匹配，系统会越来越会讲故事，但不一定越来越会筛选。

解决方式：

```text
更多数据入口
  -> Stock Discovery 控噪筛选
  -> 深度研究
  -> Final Conclusion
  -> Paper Observation Ledger
  -> Attribution 归因
  -> 下周调整 signal 权重
```

核心思想：不是让信息越多越好，而是让每个入口接受下周市场反馈。

## 2. 噪音控制机制

### 2.1 候选池上限

默认每周最多 8 个 active research candidates。

超过 8 个时，只保留 Signal Quality Score 最高的候选，其余进入 watchlist。

### 2.2 双信号家庭要求

Active candidate 至少需要 2 个独立 signal family：

- 高管/大佬发言。
- 财报电话会。
- 客户 capex。
- GitHub/developer adoption。
- 产业链外推。
- 催化剂。
- 技术面强度。
- 机构/insider/short interest。

单一来源只进 watchlist。

### 2.3 分层输出

| 层级 | 含义 | 进入下游吗 |
|---|---|---|
| Active | 多信号支持，值得深挖 | 是 |
| Watchlist | 有趣但证据不足 | 只做轻量跟踪 |
| Reject/Defer | 噪音、过热、证据薄弱 | 否 |

### 2.4 入口权重动态调整

每周 Attribution Agent 会更新入口质量：

- 工作的入口：提高权重。
- 经常误导的入口：降低权重。
- 只能产出故事但不能转成财务/价格反馈的入口：限制进入 active。
- 经常只在特定市场环境有效的入口：加上 regime 条件。

## 3. 模拟观察账本

### 3.1 为什么先不用真实 paper API

官方 paper/sandbox trading 是可行的，但第一阶段不建议立刻接入：

- 研究系统还在调 signal quality。
- 接 broker/sandbox 会引入订单、账户、权限、fill assumption 等复杂度。
- 你现在真正要验证的是“候选生成和 thesis 质量”，不是交易执行质量。

第一阶段用 `shadow_ledger`：

- 不连接 broker。
- 不下单。
- 只按规则记录假设买入价、卖出价和 benchmark-relative return。

### 3.2 默认观察规则

| 项目 | 默认规则 |
|---|---|
| 方向 | long-only observation |
| Entry | 报告发布日 close；若收盘后发布，则下一交易日 close |
| Exit | 第 5 个交易日 close |
| Holding window | 5 trading days |
| Benchmark | `QQQ`, `SPY`, 相关 sector ETF |
| Sizing | equal notional observation，仅用于比较，不做仓位 |
| Metrics | absolute return, benchmark return, excess return, max adverse move, max favorable move |

### 3.3 Paper API 未来路线

后续如果要接入真实 paper/sandbox：

- Alpaca Paper Trading：官方支持 paper-only account 和 API。
- Longbridge Sandbox：官方开发者页显示支持 paper trading sandbox。
- IBKR Paper：IBKR API 可用于 paper accounts。
- Futu/Moomoo Paper：支持模拟交易环境。

接入前必须新增权限边界：

- 只允许 paper/sandbox。
- 禁止 live trading。
- 禁止自动执行最终报告建议。
- 每一笔 paper order 必须由用户确认。

## 4. Attribution 归因框架

每个 closed observation 都必须归因，不允许只写涨跌。

| 归因 | 说明 | 对系统的影响 |
|---|---|---|
| thesis_worked | thesis 对，价格也对 | 提高对应入口权重 |
| right_thesis_wrong_timing | thesis 可能对，但一周窗口/技术位不对 | 调整 entry/technical rule |
| market_regime_drag | 大盘/利率/VIX 主导 | 不惩罚 thesis，记录 regime 条件 |
| sector_factor_drag | 行业整体拖累 | 加 sector benchmark |
| already_priced_in | 叙事对但已定价 | 提高预期差门槛 |
| catalyst_misread | 催化剂时间/强度/方向误判 | 改 catalyst scoring |
| wrong_exposure_mapping | 产业链映射错公司 | 降低该映射规则权重 |
| weak_fundamental_link | 舆情强但财务链弱 | 强化 Fundamental gate |
| technical_invalidation | 技术位先破坏 | 强化 Technical gate |
| data_quality_issue | 数据错链、过时、缺失 | 降低数据源信任 |
| unexpected_event | 突发新闻/宏观/监管 | 记录但不简单惩罚 |
| noise_random | 无法解释 | 降低置信度，不强行归因 |

## 5. 最小可行版本

第一阶段只需要三件事：

1. Stock Discovery Agent 每周产出最多 8 个 active candidates。
2. Final Report 从 active candidates 中选择进入 paper observation ledger 的标的。
3. 下周 Paper Portfolio & Attribution Agent 用 close-to-close 回看表现并更新规则。

这个闭环比直接接模拟盘更重要。等它稳定后，再接 paper API 才有意义。
