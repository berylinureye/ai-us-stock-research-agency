from __future__ import annotations

import csv
import os
import re
from pathlib import Path
from typing import Any

from ..clients.market_data import fetch_daily_closes
from ..core.config import (
    ROOT,
    compact_percent,
    expected_entry_for_decision,
    parse_float,
    parse_iso_date,
    parse_upside_range,
    planned_review_for_entry,
    review_week_for_date,
    safe_text,
    snake_from_camel,
    today_iso,
)

POND_DIR = ROOT / "data" / "conclusion-pool"
REPORT_HISTORY_DIR = Path(os.environ.get("REPORT_HISTORY_DIR") or ROOT / "data" / "report-history")
POND_STATUSES = {"candidate", "open", "closed", "archived", "price_data_failed"}
POND_COLUMNS = [
    "run_id",
    "decision_date",
    "review_week",
    "thesis_id",
    "rank",
    "ticker",
    "company",
    "action_rating",
    "confidence",
    "selected_by_user",
    "selected_date",
    "selection_notes",
    "expected_entry_date",
    "entry_rule",
    "expected_entry_price",
    "actual_entry_date",
    "actual_entry_price",
    "planned_review_date",
    "actual_review_date",
    "review_exit_price",
    "estimated_upside_low_pct",
    "estimated_upside_base_pct",
    "estimated_upside_high_pct",
    "estimated_holding_min_days",
    "estimated_holding_max_days",
    "exit_or_trim_bias",
    "trim_take_profit_range_pct",
    "invalidation_condition",
    "benchmark_primary",
    "benchmark_entry_price",
    "benchmark_review_price",
    "actual_return_pct",
    "benchmark_return_pct",
    "excess_return_pct",
    "expected_vs_actual",
    "primary_attribution",
    "next_week_action",
    "thesis_summary",
    "hard_evidence",
    "why_now",
    "next_week_check",
    "evidence_pack_href",
    "status",
    "notes",
]

def pond_file_for_date(decision_date: str) -> Path:
    return POND_DIR / f"conclusion-pool-{decision_date[:10] or today_iso()}.csv"


def pond_files() -> list[Path]:
    if not POND_DIR.exists():
        return []
    return sorted(
        path
        for path in POND_DIR.glob("conclusion-pool-*.csv")
        if path.name != "conclusion-pool-template.csv"
    )


def read_pond_file(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for raw in reader:
            row = {column: safe_text(raw.get(column, "")) for column in POND_COLUMNS}
            for key, value in raw.items():
                if key and key not in row:
                    row[key] = safe_text(value)
            rows.append(row)
        return rows


def write_pond_file(path: Path, rows: list[dict[str, str]]) -> None:
    POND_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=POND_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: safe_text(row.get(column, "")) for column in POND_COLUMNS})


def load_pond_entries() -> list[tuple[Path, dict[str, str]]]:
    entries: list[tuple[Path, dict[str, str]]] = []
    for path in pond_files():
        entries.extend((path, row) for row in read_pond_file(path))
    return entries


def pond_row_id(row: dict[str, str]) -> str:
    return "|".join(
        [
            safe_text(row.get("run_id")),
            safe_text(row.get("thesis_id")),
            safe_text(row.get("ticker")).upper(),
        ]
    )


def canonical_status(value: str, fallback: str = "open") -> str:
    status = safe_text(value).lower()
    return status if status in POND_STATUSES else fallback


def camelize_row(row: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": pond_row_id(row)}
    for key, value in row.items():
        camel = re.sub(r"_([a-z])", lambda match: match.group(1).upper(), key)
        result[camel] = value

    for key in [
        "confidence",
        "expectedEntryPrice",
        "actualEntryPrice",
        "reviewExitPrice",
        "estimatedUpsideLowPct",
        "estimatedUpsideBasePct",
        "estimatedUpsideHighPct",
        "benchmarkEntryPrice",
        "benchmarkReviewPrice",
        "actualReturnPct",
        "benchmarkReturnPct",
        "excessReturnPct",
    ]:
        number = parse_float(result.get(key))
        result[key] = number if number is not None else None

    result["status"] = canonical_status(safe_text(result.get("status")))
    return result


def pond_payload() -> dict[str, Any]:
    entries = load_pond_entries()
    rows = [row for _path, row in entries]
    active_statuses = {"candidate", "open", "price_data_failed"}
    open_rows = [
        row
        for row in rows
        if row.get("selected_by_user") == "yes" and canonical_status(row.get("status")) in active_statuses
    ]
    history_rows = [
        row
        for row in rows
        if canonical_status(row.get("status")) in {"closed", "archived"}
    ]

    open_rows.sort(key=lambda row: (row.get("selected_date"), row.get("decision_date")), reverse=True)
    history_rows.sort(key=lambda row: (row.get("actual_review_date"), row.get("decision_date")), reverse=True)

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in history_rows:
        key = row.get("decision_date") or "unknown"
        groups.setdefault(key, []).append(camelize_row(row))

    latest_refresh = max(
        [safe_text(row.get("actual_review_date")) for row in rows if safe_text(row.get("actual_review_date"))],
        default="",
    )

    return {
        "summary": {
            "openCount": len(open_rows),
            "historyCount": len(history_rows),
            "recentTickers": [row.get("ticker", "") for row in open_rows[:3] if row.get("ticker")],
            "latestRefreshDate": latest_refresh,
            "storage": "data/conclusion-pool",
        },
        "openItems": [camelize_row(row) for row in open_rows],
        "historyGroups": [
            {"decisionDate": decision_date, "items": items}
            for decision_date, items in sorted(groups.items(), reverse=True)
        ],
    }


def get_candidate_field(candidate: dict[str, Any], *names: str) -> str:
    for name in names:
        value = candidate.get(name)
        if value is not None and safe_text(value):
            return safe_text(value)
        snake = snake_from_camel(name)
        value = candidate.get(snake)
        if value is not None and safe_text(value):
            return safe_text(value)
    return ""


def normalize_ticker(value: Any) -> str:
    text = safe_text(value).upper()
    match = re.search(r"\b[A-Z][A-Z0-9.-]{0,7}\b", text)
    return match.group(0) if match else text[:12]


def normalize_pond_candidate(body: dict[str, Any]) -> dict[str, str]:
    candidate = body.get("candidate") if isinstance(body.get("candidate"), dict) else body
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")

    ticker = normalize_ticker(get_candidate_field(candidate, "ticker", "symbol", "tickerTheme", "tickerOrTheme"))
    if not ticker:
        raise ValueError("candidate.ticker is required")

    decision_date = get_candidate_field(candidate, "decisionDate") or today_iso()
    entry_date = get_candidate_field(candidate, "expectedEntryDate") or expected_entry_for_decision(decision_date)
    review_date = get_candidate_field(candidate, "plannedReviewDate") or planned_review_for_entry(entry_date)
    run_id = (
        get_candidate_field(candidate, "runId")
        or get_candidate_field(body, "runId")
        or f"pond-{decision_date.replace('-', '')}"
    )
    thesis_id = get_candidate_field(candidate, "thesisId") or f"{ticker}-{get_candidate_field(candidate, 'rank') or 'watch'}"

    low = get_candidate_field(candidate, "estimatedUpsideLowPct")
    base = get_candidate_field(candidate, "estimatedUpsideBasePct")
    high = get_candidate_field(candidate, "estimatedUpsideHighPct")
    if not any([low, base, high]):
        low, base, high = parse_upside_range(get_candidate_field(candidate, "estimatedUpsideRange"))

    return {
        "run_id": run_id,
        "decision_date": decision_date[:10],
        "review_week": review_week_for_date(review_date),
        "thesis_id": thesis_id,
        "rank": get_candidate_field(candidate, "rank"),
        "ticker": ticker,
        "company": get_candidate_field(candidate, "company", "name"),
        "action_rating": get_candidate_field(candidate, "actionRating", "rating"),
        "confidence": compact_percent(get_candidate_field(candidate, "confidence")),
        "selected_by_user": "yes",
        "selected_date": today_iso(),
        "selection_notes": get_candidate_field(body, "selectionNotes", "notes"),
        "expected_entry_date": entry_date[:10],
        "entry_rule": get_candidate_field(candidate, "entryRule") or "next_monday_regular_session_close",
        "planned_review_date": review_date[:10],
        "estimated_upside_low_pct": compact_percent(low),
        "estimated_upside_base_pct": compact_percent(base),
        "estimated_upside_high_pct": compact_percent(high),
        "estimated_holding_min_days": compact_percent(get_candidate_field(candidate, "estimatedHoldingMinDays")),
        "estimated_holding_max_days": compact_percent(get_candidate_field(candidate, "estimatedHoldingMaxDays")),
        "exit_or_trim_bias": get_candidate_field(candidate, "exitOrTrimRule", "exitOrTrimBias"),
        "invalidation_condition": get_candidate_field(candidate, "invalidationCondition", "invalidation"),
        "benchmark_primary": get_candidate_field(candidate, "benchmarkPrimary") or "QQQ",
        "thesis_summary": get_candidate_field(candidate, "thesisSummary", "summary"),
        "hard_evidence": get_candidate_field(candidate, "hardEvidence", "hardEvidenceSummary"),
        "why_now": get_candidate_field(candidate, "whyNow"),
        "next_week_check": get_candidate_field(candidate, "nextWeekCheck"),
        "evidence_pack_href": get_candidate_field(candidate, "evidencePackHref", "evidencePack"),
        "status": "open",
    }


def select_pond_candidate(body: dict[str, Any]) -> dict[str, Any]:
    row = normalize_pond_candidate(body)
    path = pond_file_for_date(row["decision_date"])
    rows = read_pond_file(path)
    target_key = pond_row_id(row)
    updated = False

    for index, existing in enumerate(rows):
        if pond_row_id(existing) == target_key:
            merged = {**existing, **{key: value for key, value in row.items() if value != ""}}
            merged["selected_by_user"] = "yes"
            merged["selected_date"] = today_iso()
            merged["status"] = "open"
            rows[index] = merged
            updated = True
            break

    if not updated:
        rows.append(row)

    write_pond_file(path, rows)
    return {"ok": True, "item": camelize_row(row), **pond_payload()}


def close_on_or_after(prices: list[tuple[str, float]], target_date: str) -> tuple[str, float] | None:
    target = parse_iso_date(target_date)
    if target is None:
        return prices[-1] if prices else None
    for price_date, close in prices:
        parsed = parse_iso_date(price_date)
        if parsed and parsed >= target:
            return price_date, close
    return None


def compute_expected_vs_actual(row: dict[str, str], actual_return: float | None) -> str:
    if actual_return is None:
        return "pending_entry"
    low = parse_float(row.get("estimated_upside_low_pct"))
    high = parse_float(row.get("estimated_upside_high_pct"))
    if low is not None and high is not None and low <= actual_return <= high:
        return "in_range"
    if high is not None and actual_return > high:
        return "above_range"
    if low is not None and 0 < actual_return < low:
        return "direction_right_below_range"
    if actual_return >= 0:
        return "interim_on_track"
    return "direction_wrong"


def refresh_pond_prices() -> dict[str, Any]:
    grouped: dict[Path, list[dict[str, str]]] = {}
    for path, row in load_pond_entries():
        grouped.setdefault(path, []).append(row)

    refreshed = 0
    failed = 0
    cache: dict[str, list[tuple[str, float]]] = {}

    for path, rows in grouped.items():
        changed = False
        for row in rows:
            status = canonical_status(row.get("status"))
            if row.get("selected_by_user") != "yes" or status not in {"open", "price_data_failed"}:
                continue

            ticker = normalize_ticker(row.get("ticker"))
            try:
                if ticker not in cache:
                    cache[ticker] = fetch_daily_closes(ticker)
                prices = cache[ticker]
                latest_date, latest_close = prices[-1]
                entry = close_on_or_after(prices, row.get("expected_entry_date") or row.get("decision_date"))

                if entry is None:
                    row["expected_vs_actual"] = "pending_entry"
                    row["status"] = "open"
                    refreshed += 1
                    changed = True
                    continue

                entry_date, entry_close = entry
                row["actual_entry_date"] = row.get("actual_entry_date") or entry_date
                row["actual_entry_price"] = row.get("actual_entry_price") or f"{entry_close:.4f}"
                row["actual_review_date"] = latest_date
                row["review_exit_price"] = f"{latest_close:.4f}"

                entry_price = parse_float(row.get("actual_entry_price"))
                actual_return = None
                if entry_price and entry_price > 0:
                    actual_return = ((latest_close - entry_price) / entry_price) * 100
                    row["actual_return_pct"] = f"{actual_return:.2f}"

                benchmark = normalize_ticker(row.get("benchmark_primary") or "QQQ")
                if benchmark:
                    try:
                        if benchmark not in cache:
                            cache[benchmark] = fetch_daily_closes(benchmark)
                        benchmark_prices = cache[benchmark]
                        benchmark_entry = close_on_or_after(benchmark_prices, row["actual_entry_date"])
                        benchmark_latest = benchmark_prices[-1]
                        if benchmark_entry:
                            row["benchmark_entry_price"] = f"{benchmark_entry[1]:.4f}"
                            row["benchmark_review_price"] = f"{benchmark_latest[1]:.4f}"
                            benchmark_return = ((benchmark_latest[1] - benchmark_entry[1]) / benchmark_entry[1]) * 100
                            row["benchmark_return_pct"] = f"{benchmark_return:.2f}"
                            if actual_return is not None:
                                row["excess_return_pct"] = f"{actual_return - benchmark_return:.2f}"
                    except Exception:
                        pass

                row["expected_vs_actual"] = compute_expected_vs_actual(row, actual_return)
                row["status"] = "open"
                refreshed += 1
                changed = True
            except Exception as exc:  # noqa: BLE001 - surfaced in pond notes
                row["status"] = "price_data_failed"
                row["expected_vs_actual"] = "price_data_failed"
                row["notes"] = f"Price refresh failed: {exc}"
                failed += 1
                changed = True

        if changed:
            write_pond_file(path, rows)

    return {"ok": True, "refreshed": refreshed, "failed": failed, **pond_payload()}
