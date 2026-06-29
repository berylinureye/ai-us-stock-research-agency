from __future__ import annotations

from datetime import date

from ..core.config import normalize_ticker

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None


def yahoo_symbol(ticker: str) -> str:
    return normalize_ticker(ticker).replace(".", "-")


def fetch_daily_closes(ticker: str, *, timeout_seconds: float | None = None) -> list[tuple[str, float]]:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    symbol = yahoo_symbol(ticker)
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = requests.get(
        url,
        params={"range": "6mo", "interval": "1d", "events": "history"},
        headers={"Accept": "application/json", "User-Agent": "weekly-brief-market-data/0.1"},
        timeout=timeout_seconds if timeout_seconds is not None else 12,
    )
    response.raise_for_status()
    data = response.json()
    result = ((data.get("chart") or {}).get("result") or [None])[0]
    if not isinstance(result, dict):
        raise RuntimeError(f"No price result for {ticker}")
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote.get("close") or []
    prices: list[tuple[str, float]] = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        prices.append((date.fromtimestamp(int(timestamp)).isoformat(), float(close)))
    if not prices:
        raise RuntimeError(f"No regular-session close data for {ticker}")
    return prices
