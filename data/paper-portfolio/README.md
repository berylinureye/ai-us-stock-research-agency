# Paper Portfolio Ledger

This folder stores the shadow-ledger files used by `Paper Portfolio & Attribution Agent`.

The ledger is not a brokerage account and does not place orders. It records hypothetical observation entries and exits for research feedback.

Default workflow:

1. After the Friday final report, copy Top 5 Research Action Pool candidates or user-selected conclusion-pool entries into `paper-observation-template.csv`.
2. Use the next Monday regular-session close as the hypothetical entry price. If Monday is a market holiday, use the next regular trading session close.
3. Fill expected upside range, estimated holding range in days, invalidation condition, and exit/trim bias from the final report.
4. On the next Friday close, fill review price, return, benchmark-relative return, and expected-vs-actual result.
5. Run `agents/07-paper-portfolio-attribution-agent.md` to attribute outcomes and update signal rules.

Recommended naming:

```text
paper-observations-YYYY-MM-DD.csv
```

Do not store API keys, account IDs, or broker credentials in this folder.

Do not store real trades. This folder is for shadow-ledger observations only.
