from __future__ import annotations

import concurrent.futures
import html
import re
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - surfaced via health/error response
    requests = None

from ..core.config import env, parse_float, redact_url, research_seed_universe, safe_text, today_iso
from .market_data import fetch_daily_closes, yahoo_symbol

DATA_NODE_REQUIRED_COUNTS = {
    "finnhub_news": 10,
    "arxiv_papers": 5,
    "github_projects": 5,
    "finnhub_sentiment": 5,
    "market_quotes": 5,
    "technical_prices": 5,
    "sec_filings": 3,
    "finnhub_fundamentals": 3,
    "fred_macro": 2,
}

SEC_CIK_BY_TICKER = {
    "AAPL": "0000320193",
    "AMD": "0000002488",
    "AMZN": "0001018724",
    "AVGO": "0001730168",
    "BAC": "0000070858",
    "BLK": "0001364742",
    "COST": "0000909832",
    "GOOGL": "0001652044",
    "GS": "0000886982",
    "HD": "0000354950",
    "JPM": "0000019617",
    "KO": "0000021344",
    "LLY": "0000059478",
    "MA": "0001141391",
    "MCD": "0000063908",
    "META": "0001326801",
    "MS": "0000895421",
    "MSFT": "0000789019",
    "NKE": "0000320187",
    "NVDA": "0001045810",
    "PEP": "0000077476",
    "PG": "0000080424",
    "V": "0001403161",
    "WMT": "0000104169",
}


def first_env(*names: str) -> str:
    for name in names:
        value = env(name)
        if value:
            return value
    return ""


def data_node_timeout_seconds() -> float:
    return float(env("WEEKLY_BRIEF_DATA_NODE_TIMEOUT", "8"))


def data_node_enabled() -> bool:
    configured = any(
        first_env(name)
        for name in [
            "FINNHUB_API_KEY",
            "ALPHA_VANTAGE_API_KEY",
            "ALPHA_VANTAGE",
            "FRED_API_KEY",
            "SEC_EDGAR_USER_AGENT",
            "TRANSCRIPT_API_KEY",
            "SCRAPECREATORS_API_KEY",
        ]
    )
    value = env("WEEKLY_BRIEF_ENABLE_DATA_NODES", "auto").lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return configured


def local_data_sections_enabled(bundle: dict[str, Any]) -> bool:
    value = env("WEEKLY_BRIEF_LOCAL_DATA_SECTIONS", "0").lower()
    if value in {"0", "false", "no", "off"}:
        return False
    if value in {"1", "true", "yes", "on"}:
        return True
    return False


def data_node_result(
    key: str,
    label: str,
    source_type: str,
    items: list[dict[str, Any]] | None = None,
    *,
    required: int | None = None,
    status: str | None = None,
    error: str = "",
) -> dict[str, Any]:
    rows = items or []
    required_count = DATA_NODE_REQUIRED_COUNTS.get(key, 0) if required is None else required
    if status is None:
        if rows and (required_count <= 0 or len(rows) >= required_count):
            status = "success"
        elif rows:
            status = "partial"
        else:
            status = "failed" if error else "partial"
    return {
        "key": key,
        "label": label,
        "sourceType": source_type,
        "status": status,
        "required": required_count,
        "count": len(rows),
        "items": rows,
        "error": redact_url(safe_text(error)),
    }


def request_json_value(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    response = requests.get(url, params=params or {}, headers=headers or {"Accept": "application/json"}, timeout=data_node_timeout_seconds())
    response.raise_for_status()
    return response.json()


def request_json(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    value = request_json_value(url, params=params, headers=headers)
    if not isinstance(value, dict):
        raise RuntimeError("JSON response is not an object")
    return value


def request_text(url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
    if requests is None:
        raise RuntimeError("Python package 'requests' is required")
    response = requests.get(url, params=params or {}, headers=headers or {"Accept": "text/plain, application/xml"}, timeout=data_node_timeout_seconds())
    response.raise_for_status()
    return response.text


def recent_date(days: int) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def fetch_finnhub_news(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_news", "Finnhub company news", "news", required=10, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker in tickers[:6]:
        data = request_json_value(
            "https://finnhub.io/api/v1/company-news",
            params={"symbol": ticker, "from": recent_date(14), "to": today_iso(), "token": token},
        )
        rows = data if isinstance(data, list) else []
        if not rows:
            continue
        for row in rows[:3]:
            if not isinstance(row, dict):
                continue
            url = safe_text(row.get("url"))
            key = url or safe_text(row.get("headline"))
            if not key or key in seen:
                continue
            seen.add(key)
            timestamp = row.get("datetime")
            item_date = ""
            if isinstance(timestamp, (int, float)) and timestamp > 0:
                item_date = date.fromtimestamp(int(timestamp)).isoformat()
            items.append(
                {
                    "ticker": ticker,
                    "title": safe_text(row.get("headline")),
                    "source": safe_text(row.get("source")) or "Finnhub",
                    "date": item_date,
                    "url": url,
                    "summary": safe_text(row.get("summary"))[:260],
                }
            )
            if len(items) >= 10:
                break
        if len(items) >= 10:
            break
    return data_node_result("finnhub_news", "Finnhub company news", "news", items, required=10)


def fetch_finnhub_quotes(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("market_quotes", "Finnhub quotes", "market_data", required=5, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:8]:
        row = request_json("https://finnhub.io/api/v1/quote", params={"symbol": ticker, "token": token})
        price = parse_float(row.get("c"))
        previous = parse_float(row.get("pc"))
        if price is None:
            continue
        change_pct = None
        if previous and previous > 0:
            change_pct = ((price - previous) / previous) * 100
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} quote",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/quote?symbol={ticker}",
                "price": price,
                "previousClose": previous,
                "changePct": change_pct,
                "summary": f"latest={price}; previous_close={previous}; change_pct={change_pct:.2f}%" if change_pct is not None else f"latest={price}",
            }
        )
    return data_node_result("market_quotes", "Finnhub quotes", "market_data", items, required=5)


def fetch_finnhub_fundamentals(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", required=3, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:6]:
        profile = request_json("https://finnhub.io/api/v1/stock/profile2", params={"symbol": ticker, "token": token})
        metric = request_json("https://finnhub.io/api/v1/stock/metric", params={"symbol": ticker, "metric": "all", "token": token})
        metrics = metric.get("metric") if isinstance(metric.get("metric"), dict) else {}
        if not profile and not metrics:
            continue
        summary_parts = []
        for key in ["marketCapitalization", "peNormalizedAnnual", "revenueGrowthTTMYoy", "grossMarginTTM", "operatingMarginTTM"]:
            if metrics.get(key) is not None:
                summary_parts.append(f"{key}={metrics.get(key)}")
        items.append(
            {
                "ticker": ticker,
                "title": safe_text(profile.get("name")) or f"{ticker} fundamentals",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/stock/metric?symbol={ticker}",
                "summary": "; ".join(summary_parts[:6]) or "profile / metric returned",
            }
        )
    return data_node_result("finnhub_fundamentals", "Finnhub profile / metrics", "fundamentals", items, required=3)


def fetch_finnhub_sentiment(tickers: list[str]) -> dict[str, Any]:
    token = first_env("FINNHUB_API_KEY")
    if not token:
        return data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", required=5, status="partial", error="FINNHUB_API_KEY missing")
    items: list[dict[str, Any]] = []
    for ticker in tickers[:8]:
        row = request_json("https://finnhub.io/api/v1/news-sentiment", params={"symbol": ticker, "token": token})
        sentiment = row.get("sentiment") if isinstance(row.get("sentiment"), dict) else {}
        buzz = row.get("buzz") if isinstance(row.get("buzz"), dict) else {}
        if not sentiment and not buzz:
            continue
        score = sentiment.get("companyNewsScore")
        articles = buzz.get("articlesInLastWeek")
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} news sentiment",
                "source": "Finnhub",
                "date": today_iso(),
                "url": f"https://finnhub.io/api/v1/news-sentiment?symbol={ticker}",
                "summary": f"companyNewsScore={score}; articlesInLastWeek={articles}; sectorAverageBullishPercent={sentiment.get('sectorAverageBullishPercent')}",
            }
        )
    return data_node_result("finnhub_sentiment", "Finnhub news sentiment", "sentiment", items, required=5)


def fetch_github_projects() -> dict[str, Any]:
    queries = [
        "AI agent stars:>500",
        "LLM inference OR vLLM OR SGLang stars:>500",
    ]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "weekly-brief-research/0.1"}
    for query in queries:
        data = request_json(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "updated", "order": "desc", "per_page": 5},
            headers=headers,
        )
        for repo in data.get("items") or []:
            if not isinstance(repo, dict):
                continue
            name = safe_text(repo.get("full_name"))
            if not name or name in seen:
                continue
            seen.add(name)
            items.append(
                {
                    "title": name,
                    "source": "GitHub",
                    "date": safe_text(repo.get("updated_at"))[:10],
                    "url": safe_text(repo.get("html_url")),
                    "summary": f"stars={repo.get('stargazers_count')}; forks={repo.get('forks_count')}; {safe_text(repo.get('description'))[:180]}",
                }
            )
            if len(items) >= 5:
                break
        if len(items) >= 5:
            break
    return data_node_result("github_projects", "GitHub project search", "open_source", items, required=5)


def fetch_arxiv_papers() -> dict[str, Any]:
    text = request_text(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": 'cat:cs.AI AND (agent OR "tool use" OR reasoning OR inference)',
            "start": 0,
            "max_results": 5,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        },
        headers={"Accept": "application/atom+xml", "User-Agent": "weekly-brief-research/0.1"},
    )
    root = ET.fromstring(text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        title = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns)).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
        link = ""
        for link_node in entry.findall("atom:link", ns):
            href = link_node.attrib.get("href", "")
            if href:
                link = href
                break
        summary = re.sub(r"\s+", " ", html.unescape(entry.findtext("atom:summary", default="", namespaces=ns))).strip()
        if title:
            items.append({"title": title, "source": "arXiv", "date": published, "url": link, "summary": summary[:260]})
    return data_node_result("arxiv_papers", "arXiv papers", "papers", items, required=5)


def fetch_sec_filings(tickers: list[str]) -> dict[str, Any]:
    user_agent = first_env("SEC_EDGAR_USER_AGENT")
    if not user_agent:
        return data_node_result("sec_filings", "SEC recent filings", "filings", required=3, status="partial", error="SEC_EDGAR_USER_AGENT missing")
    items: list[dict[str, Any]] = []
    headers = {"Accept": "application/json", "User-Agent": user_agent}
    for ticker in tickers[:6]:
        cik = SEC_CIK_BY_TICKER.get(ticker)
        if not cik:
            continue
        data = request_json(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers)
        recent = (data.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        dates = recent.get("filingDate") or []
        accessions = recent.get("accessionNumber") or []
        for form, filing_date, accession in zip(forms, dates, accessions):
            if form not in {"10-K", "10-Q", "8-K"}:
                continue
            accession_compact = safe_text(accession).replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_compact}/"
            items.append(
                {
                    "ticker": ticker,
                    "title": f"{ticker} {form}",
                    "source": "SEC EDGAR",
                    "date": safe_text(filing_date),
                    "url": url,
                    "summary": f"Recent SEC filing: {form}",
                }
            )
            break
        if len(items) >= 6:
            break
    return data_node_result("sec_filings", "SEC recent filings", "filings", items, required=3)


def fetch_yahoo_technicals(tickers: list[str]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for ticker in tickers[:6]:
        try:
            prices = fetch_daily_closes(ticker, timeout_seconds=data_node_timeout_seconds())
        except Exception as exc:  # noqa: BLE001
            items.append({"ticker": ticker, "title": f"{ticker} technical data failed", "source": "Yahoo Finance", "date": today_iso(), "url": "", "summary": f"failed: {exc}"})
            continue
        if len(prices) < 20:
            continue
        latest_date, latest_close = prices[-1]
        closes = [close for _price_date, close in prices]
        sma20 = sum(closes[-20:]) / 20
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        six_month_low = min(closes)
        six_month_high = max(closes)
        trend = "above_20d_sma" if latest_close >= sma20 else "below_20d_sma"
        summary = f"close={latest_close:.2f}; sma20={sma20:.2f}; range_6m={six_month_low:.2f}-{six_month_high:.2f}; trend={trend}"
        if sma50 is not None:
            summary += f"; sma50={sma50:.2f}"
        items.append(
            {
                "ticker": ticker,
                "title": f"{ticker} daily technical snapshot",
                "source": "Yahoo Finance chart",
                "date": latest_date,
                "url": f"https://finance.yahoo.com/quote/{yahoo_symbol(ticker)}",
                "summary": summary,
            }
        )
    valid_items = [item for item in items if not item.get("summary", "").startswith("failed:")]
    status = None if valid_items else "failed"
    return data_node_result("technical_prices", "Yahoo daily technicals", "market_data", valid_items, required=5, status=status)


def fetch_fred_macro() -> dict[str, Any]:
    token = first_env("FRED_API_KEY")
    if not token:
        return data_node_result("fred_macro", "FRED macro", "macro", required=2, status="partial", error="FRED_API_KEY missing")
    series = [("DGS10", "10Y Treasury yield"), ("VIXCLS", "VIX close"), ("FEDFUNDS", "Fed funds")]
    items: list[dict[str, Any]] = []
    for series_id, title in series:
        data = request_json(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": series_id, "api_key": token, "file_type": "json", "sort_order": "desc", "limit": 1},
        )
        observations = data.get("observations") or []
        if not observations:
            continue
        row = observations[0]
        items.append(
            {
                "title": title,
                "source": "FRED",
                "date": safe_text(row.get("date")),
                "url": f"https://fred.stlouisfed.org/series/{series_id}",
                "summary": f"{series_id}={safe_text(row.get('value'))}",
            }
        )
    return data_node_result("fred_macro", "FRED macro", "macro", items, required=2)


def collect_research_data_nodes(user_prompt: str) -> dict[str, Any]:
    tickers = [item["ticker"] for item in research_seed_universe(user_prompt)]
    configured_apis = [
        name
        for name, present in {
            "FINNHUB_API_KEY": bool(first_env("FINNHUB_API_KEY")),
            "ALPHA_VANTAGE": bool(first_env("ALPHA_VANTAGE_API_KEY", "ALPHA_VANTAGE")),
            "FRED_API_KEY": bool(first_env("FRED_API_KEY")),
            "SEC_EDGAR_USER_AGENT": bool(first_env("SEC_EDGAR_USER_AGENT")),
            "TRANSCRIPT_API_KEY": bool(first_env("TRANSCRIPT_API_KEY")),
            "SCRAPECREATORS_API_KEY": bool(first_env("SCRAPECREATORS_API_KEY")),
        }.items()
        if present
    ]
    if not data_node_enabled():
        bundle = {
            "enabled": False,
            "configuredApis": configured_apis,
            "tickers": tickers,
            "nodes": {},
            "markdown": "## Data Node Evidence Bundle\n\n数据节点未启用。",
        }
        return bundle

    task_specs = [
        ("finnhub_news", lambda: fetch_finnhub_news(tickers)),
        ("arxiv_papers", fetch_arxiv_papers),
        ("github_projects", fetch_github_projects),
        ("finnhub_sentiment", lambda: fetch_finnhub_sentiment(tickers)),
        ("market_quotes", lambda: fetch_finnhub_quotes(tickers)),
        ("finnhub_fundamentals", lambda: fetch_finnhub_fundamentals(tickers)),
        ("sec_filings", lambda: fetch_sec_filings(tickers)),
        ("technical_prices", lambda: fetch_yahoo_technicals(tickers)),
        ("fred_macro", fetch_fred_macro),
    ]
    nodes: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(task_specs))) as executor:
        future_to_key = {executor.submit(func): key for key, func in task_specs}
        for future in concurrent.futures.as_completed(future_to_key):
            key = future_to_key[future]
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - node failures become evidence status, not request failure
                result = data_node_result(key, key, "data_node", required=DATA_NODE_REQUIRED_COUNTS.get(key, 0), status="failed", error=str(exc))
            nodes[key] = result

    bundle = {
        "enabled": True,
        "configuredApis": configured_apis,
        "tickers": tickers,
        "nodes": nodes,
    }
    bundle["markdown"] = data_node_bundle_markdown(bundle)
    return bundle


def node_items(bundle: dict[str, Any], key: str) -> list[dict[str, Any]]:
    node = (bundle.get("nodes") or {}).get(key) or {}
    items = node.get("items") or []
    return [item for item in items if isinstance(item, dict)]


def data_node_status_rows(bundle: dict[str, Any]) -> list[str]:
    rows = ["| Node | Status | Count / Required | Notes |", "|---|---|---:|---|"]
    nodes = bundle.get("nodes") or {}
    for key in [
        "finnhub_news",
        "arxiv_papers",
        "github_projects",
        "finnhub_sentiment",
        "market_quotes",
        "finnhub_fundamentals",
        "sec_filings",
        "technical_prices",
        "fred_macro",
    ]:
        node = nodes.get(key) or data_node_result(key, key, "data_node", status="partial", error="not collected")
        rows.append(
            f"| {node.get('label') or key} | {node.get('status')} | {node.get('count', 0)} / {node.get('required', 0)} | {redact_url(safe_text(node.get('error'))) or node.get('sourceType', '')} |"
        )
    return rows


def evidence_items_table(items: list[dict[str, Any]], *, max_rows: int = 10) -> str:
    rows = ["| Date | Source | Ticker / Topic | Evidence | Link |", "|---|---|---|---|---|"]
    for item in items[:max_rows]:
        ticker = safe_text(item.get("ticker"))
        topic = ticker or safe_text(item.get("title"))[:36]
        title = safe_text(item.get("title"))
        summary = safe_text(item.get("summary"))
        url = safe_text(item.get("url"))
        link = f"[source]({url})" if url else "n/a"
        evidence = title if not summary else f"{title}: {summary}"
        rows.append(f"| {safe_text(item.get('date')) or today_iso()} | {safe_text(item.get('source'))} | {topic} | {evidence[:260]} | {link} |")
    if len(rows) == 2:
        rows.append("| n/a | n/a | n/a | 数据节点没有返回可用条目 | n/a |")
    return "\n".join(rows)


def data_node_bundle_markdown(bundle: dict[str, Any]) -> str:
    lines = [
        "## Data Node Evidence Bundle",
        "",
        f"- Enabled：{bundle.get('enabled')}",
        f"- Configured APIs：{', '.join(bundle.get('configuredApis') or []) or 'none detected'}",
        f"- Seed tickers：{', '.join(bundle.get('tickers') or [])}",
        "",
        "### Data Node Status",
        *data_node_status_rows(bundle),
        "",
        "### News",
        evidence_items_table(node_items(bundle, "finnhub_news"), max_rows=10),
        "",
        "### Papers",
        evidence_items_table(node_items(bundle, "arxiv_papers"), max_rows=5),
        "",
        "### Open Source",
        evidence_items_table(node_items(bundle, "github_projects"), max_rows=5),
        "",
        "### Sentiment / Market Attention",
        evidence_items_table(node_items(bundle, "finnhub_sentiment"), max_rows=5),
        "",
        "### Market / Technical / Fundamentals",
        evidence_items_table(
            node_items(bundle, "market_quotes")
            + node_items(bundle, "technical_prices")
            + node_items(bundle, "finnhub_fundamentals")
            + node_items(bundle, "sec_filings")
            + node_items(bundle, "fred_macro"),
            max_rows=18,
        ),
    ]
    return "\n".join(lines)


def data_node_counts(bundle: dict[str, Any]) -> dict[str, int]:
    return {key: len(node_items(bundle, key)) for key in (bundle.get("nodes") or {})}


def data_node_complete_enough(bundle: dict[str, Any]) -> bool:
    counts = data_node_counts(bundle)
    return (
        counts.get("finnhub_news", 0) >= 10
        and counts.get("arxiv_papers", 0) >= 5
        and counts.get("github_projects", 0) >= 5
        and counts.get("market_quotes", 0) >= 5
        and counts.get("technical_prices", 0) >= 5
    )
