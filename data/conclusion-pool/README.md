# Conclusion Pool

This folder stores the daily and weekly conclusion-pool records produced by the final AI Trend Narrative Analyst.

The conclusion pool is not a brokerage account and does not place orders. It records research decisions, user selections, hypothetical next-Monday entries, next-Friday reviews, expected upside ranges, and exit/trim rules for later attribution.

Default weekly schedule:

1. **Friday analysis**: run the full research workflow and generate the Top 5 Research Action Pool.
2. **User selection**: record which candidates the user chose to observe in the conclusion pool.
3. **Next Monday entry**: use the next regular-session close as the hypothetical entry price.
4. **Next Friday review**: compare actual price action against expected upside range, invalidation, and benchmark.
5. **Attribution**: update signal quality, action-rating thresholds, and sell/trim rules.

If Monday or Friday is a market holiday, use the next regular trading session close.

Recommended naming:

```text
conclusion-pool-YYYY-MM-DD.csv
```

Do not store API keys, account IDs, broker credentials, or live order information in this folder.
