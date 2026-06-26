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
  -> Conclusion Pool 记录用户选择
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

第一阶段用 `Conclusion Pool` + `shadow_ledger`：

- 不连接 broker。
- 不下单。
- 结论池记录用户每天实际选择观察的股票。
- shadow ledger 按规则记录假设买入价、复盘价和 benchmark-relative return。

### 3.2 默认观察规则

| 项目 | 默认规则 |
|---|---|
| 方向 | long-only observation |
| Decision | 每周五 final report |
| Conclusion Pool | 记录用户选择的 Top 5 / override 标的 |
| Entry | 下周一 regular-session close；若休市，则下一交易日 close |
| Review | 下周五 regular-session close；若休市，则最近 regular-session close |
| Holding window | Monday close -> Friday close，或报告指定的 estimated holding range |
| Benchmark | `QQQ`, `SPY`, 相关 sector ETF |
| Sizing | equal notional observation，仅用于比较，不做仓位 |
| Metrics | absolute return, benchmark return, excess return, expected upside vs actual return, max adverse move, max favorable move |
| Exit / Trim | 达到预估涨幅上沿且动能衰减时给 Take-Profit / Trim Bias；跌破失效位或 thesis 断裂时给 Avoid-Sell Bias |

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
| upside_target_met | 实际收益达到或超过预估涨幅上沿 | 检查是否触发止盈/减磅规则 |
| take_profit_triggered | 满足 Take-Profit / Trim Bias | 记录是否需要缩短观察周期或提高追高门槛 |
| catalyst_misread | 催化剂时间/强度/方向误判 | 改 catalyst scoring |
| wrong_exposure_mapping | 产业链映射错公司 | 降低该映射规则权重 |
| weak_fundamental_link | 舆情强但财务链弱 | 强化 Fundamental gate |
| technical_invalidation | 技术位先破坏 | 强化 Technical gate |
| data_quality_issue | 数据错链、过时、缺失 | 降低数据源信任 |
| unexpected_event | 突发新闻/宏观/监管 | 记录但不简单惩罚 |
| user_override | 用户选择了非 Top 5 或非默认候选 | 与模型默认池分开统计 |
| noise_random | 无法解释 | 降低置信度，不强行归因 |

## 5. 最小可行版本

第一阶段只需要三件事：

1. Stock Discovery Agent 每周产出最多 8 个 active candidates。
2. Final Report 生成 Top 5 Research Action Pool，包含预估涨幅区间、预计观察/持有周期和卖出/止盈规则。
3. 用户选择的标的进入 Conclusion Pool。
4. 下周一按 close 做假设买入，下周五 Paper Portfolio & Attribution Agent 用 close-to-close 回看表现并更新规则。

这个闭环比直接接模拟盘更重要。等它稳定后，再接 paper API 才有意义。
