# Paper Portfolio Ledger

This folder stores the shadow-ledger files used by `Paper Portfolio & Attribution Agent`.

The ledger is not a brokerage account and does not place orders. It records hypothetical observation entries and exits for research feedback.

Default workflow:

1. After the weekly final report, copy selected candidates into `paper-observation-template.csv`.
2. Fill `entry_date`, `entry_price`, `planned_exit_date`, and benchmark fields using close prices.
3. Next week, fill exit prices and returns.
4. Run `agents/07-paper-portfolio-attribution-agent.md` to attribute outcomes.

Recommended naming:

```text
paper-observations-YYYY-MM-DD.csv
```

Do not store API keys, account IDs, or broker credentials in this folder.
