from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
BENCHMARK = "^GSPC"
NY_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class AnalysisPeriod:
    label: str
    start: date
    end: date  # inclusive


def today_ny() -> date:
    return datetime.now(NY_TZ).date()


def current_quarter_start(day: date) -> date:
    month = ((day.month - 1) // 3) * 3 + 1
    return date(day.year, month, 1)


def quarter_period(year: int, quarter: int) -> AnalysisPeriod:
    if quarter not in (1, 2, 3, 4):
        raise ValueError("Quarter must be 1, 2, 3, or 4.")

    start_month = 1 + (quarter - 1) * 3
    start = date(year, start_month, 1)

    if quarter == 4:
        next_start = date(year + 1, 1, 1)
    else:
        next_start = date(year, start_month + 3, 1)

    end = next_start - timedelta(days=1)
    return AnalysisPeriod(f"{year}-Q{quarter}", start, end)


def current_quarter_period(day: date | None = None) -> AnalysisPeriod:
    day = day or today_ny()
    start = current_quarter_start(day)
    q = ((start.month - 1) // 3) + 1
    return AnalysisPeriod(f"{day.year}-Q{q} QTD", start, day)


def year_to_date_period(day: date | None = None) -> AnalysisPeriod:
    day = day or today_ny()
    return AnalysisPeriod(f"{day.year} YTD", date(day.year, 1, 1), day)


def last_completed_quarter_period(day: date | None = None) -> AnalysisPeriod:
    day = day or today_ny()
    this_q_start = current_quarter_start(day)
    previous_day = this_q_start - timedelta(days=1)
    q = ((previous_day.month - 1) // 3) + 1
    return quarter_period(previous_day.year, q)


def custom_period(start: date, end: date) -> AnalysisPeriod:
    if end < start:
        raise ValueError("End date must be on or after start date.")
    return AnalysisPeriod(f"{start.isoformat()} to {end.isoformat()}", start, end)


def get_sp500_constituents() -> pd.DataFrame:
    """Return the current S&P 500 constituent table.

    This is intentionally the current membership at runtime. For historical
    backtests, historical membership snapshots should be used instead.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; SP500Tracker/1.0; +https://streamlit.io)"
    }
    response = requests.get(SP500_URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text), attrs={"id": "constituents"})
    if not tables:
        raise RuntimeError("Could not locate the S&P 500 constituent table.")

    df = tables[0].copy()
    required = ["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Unexpected constituent table format; missing {missing}")

    # Yahoo Finance uses dashes instead of dots for symbols such as BRK.B.
    df["YahooTicker"] = df["Symbol"].astype(str).str.replace(".", "-", regex=False)
    return df


def _extract_close(data: pd.DataFrame, ticker: str, batch_size: int) -> pd.Series | None:
    try:
        if isinstance(data.columns, pd.MultiIndex):
            # With group_by="ticker", first level is ticker.
            if ticker not in data.columns.get_level_values(0):
                return None
            series = data[ticker]["Close"]
        else:
            # Single-ticker response.
            series = data["Close"]

        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]

        series = pd.to_numeric(series, errors="coerce").dropna()
        return series if not series.empty else None
    except (KeyError, TypeError, IndexError):
        return None


def _period_return_from_series(series: pd.Series, start: date, end: date) -> tuple[float, date, float, date, float] | None:
    """Compute return from the last close before start through the last close on/before end.

    This captures the full first trading day's move, unlike comparing the first
    trading day's close with the last trading day's close.
    """
    idx = pd.to_datetime(series.index)
    # Normalize away any timezone to compare with calendar dates safely.
    try:
        idx = idx.tz_localize(None)
    except TypeError:
        pass
    s = pd.Series(series.to_numpy(), index=idx).sort_index().dropna()

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)

    before = s[s.index < start_ts]
    through_end = s[s.index <= end_ts]

    if before.empty or through_end.empty:
        return None

    base_price = float(before.iloc[-1])
    base_date = before.index[-1].date()
    end_price = float(through_end.iloc[-1])
    end_date = through_end.index[-1].date()

    if base_price <= 0:
        return None

    ret = (end_price / base_price - 1.0) * 100.0
    return ret, base_date, base_price, end_date, end_price


def download_period_returns(
    tickers: Iterable[str],
    start: date,
    end: date,
    *,
    batch_size: int = 75,
    progress_callback=None,
) -> pd.DataFrame:
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return pd.DataFrame()

    # Buffer before start is needed to obtain the prior trading day's close.
    fetch_start = start - timedelta(days=14)
    fetch_end = min(end + timedelta(days=2), today_ny() + timedelta(days=1))

    rows: list[dict] = []
    total_batches = (len(tickers) + batch_size - 1) // batch_size

    for batch_index, i in enumerate(range(0, len(tickers), batch_size), start=1):
        batch = tickers[i : i + batch_size]
        if progress_callback:
            progress_callback(batch_index, total_batches)

        data = yf.download(
            batch,
            start=fetch_start.isoformat(),
            end=fetch_end.isoformat(),
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
            group_by="ticker",
            timeout=30,
        )

        for ticker in batch:
            series = _extract_close(data, ticker, len(batch))
            if series is None:
                continue
            result = _period_return_from_series(series, start, end)
            if result is None:
                continue
            ret, base_date, base_price, end_date, end_price = result
            rows.append(
                {
                    "YahooTicker": ticker,
                    "Quarterly Return %": ret,
                    "Base Trading Date": base_date,
                    "Base Adjusted Close": base_price,
                    "End Trading Date": end_date,
                    "End Adjusted Close": end_price,
                }
            )

    return pd.DataFrame(rows)


def benchmark_return(start: date, end: date) -> dict:
    fetch_start = start - timedelta(days=14)
    fetch_end = min(end + timedelta(days=2), today_ny() + timedelta(days=1))

    data = yf.download(
        BENCHMARK,
        start=fetch_start.isoformat(),
        end=fetch_end.isoformat(),
        auto_adjust=True,
        actions=False,
        progress=False,
        timeout=30,
    )
    series = data["Close"]
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    series = pd.to_numeric(series, errors="coerce").dropna()

    result = _period_return_from_series(series, start, end)
    if result is None:
        raise RuntimeError("Could not calculate the S&P 500 benchmark return.")

    ret, base_date, base_price, end_date, end_price = result
    return {
        "return_pct": ret,
        "base_date": base_date,
        "base_price": base_price,
        "end_date": end_date,
        "end_price": end_price,
    }


def download_current_prices(tickers: Iterable[str]) -> pd.DataFrame:
    """Return the latest available unadjusted close for the requested tickers."""
    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return pd.DataFrame(columns=["YahooTicker", "Current Price", "Price As Of"])

    data = yf.download(
        tickers,
        period="5d",
        interval="1d",
        auto_adjust=False,
        actions=False,
        progress=False,
        threads=True,
        group_by="ticker",
        timeout=30,
    )

    rows: list[dict] = []
    for ticker in tickers:
        series = _extract_close(data, ticker, len(tickers))
        if series is None:
            continue
        latest_timestamp = pd.Timestamp(series.index[-1])
        rows.append(
            {
                "YahooTicker": ticker,
                "Current Price": float(series.iloc[-1]),
                "Price As Of": latest_timestamp.date(),
            }
        )
    return pd.DataFrame(rows)


def run_analysis(
    period: AnalysisPeriod,
    *,
    top_n: int = 10,
    progress_callback=None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    today = today_ny()
    if period.start > today:
        raise ValueError("The analysis period starts in the future.")
    effective_end = min(period.end, today)

    constituents = get_sp500_constituents()
    returns = download_period_returns(
        constituents["YahooTicker"].tolist(),
        period.start,
        effective_end,
        progress_callback=progress_callback,
    )
    if returns.empty:
        raise RuntimeError("No stock return data was retrieved for this period.")

    full = constituents.merge(returns, on="YahooTicker", how="inner")
    if full.empty:
        raise RuntimeError("Could not match downloaded prices to S&P 500 constituents.")

    bench = benchmark_return(period.start, effective_end)
    constituent_average = float(full["Quarterly Return %"].mean())

    full["S&P 500 Return %"] = bench["return_pct"]
    full["Constituent Average Return %"] = constituent_average
    full["Beat S&P 500 By (pp)"] = full["Quarterly Return %"] - bench["return_pct"]
    full["Beat Constituent Average By (pp)"] = (
        full["Quarterly Return %"] - constituent_average
    )

    full = full.sort_values("Quarterly Return %", ascending=False).reset_index(drop=True)
    full.insert(0, "Rank", range(1, len(full) + 1))

    display_cols = [
        "Rank",
        "Symbol",
        "Security",
        "GICS Sector",
        "GICS Sub-Industry",
        "Quarterly Return %",
        "S&P 500 Return %",
        "Beat S&P 500 By (pp)",
        "Constituent Average Return %",
        "Beat Constituent Average By (pp)",
        "Base Trading Date",
        "End Trading Date",
        "End Adjusted Close",
    ]

    full_out = full[display_cols].copy()
    top_count = max(1, int(top_n))
    top = full_out.head(top_count).copy()

    summary = {
        "label": period.label,
        "requested_start": period.start,
        "requested_end": period.end,
        "effective_end": effective_end,
        "sp500_return_pct": float(bench["return_pct"]),
        "constituent_average_pct": constituent_average,
        "constituents_analyzed": int(len(full_out)),
        "benchmark_base_date": bench["base_date"],
        "benchmark_end_date": bench["end_date"],
        "membership_basis": "Current S&P 500 constituents at runtime",
    }

    return top, summary, full_out
