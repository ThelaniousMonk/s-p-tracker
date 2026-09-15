from __future__ import annotations

from datetime import date
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from sp500_tracker import (
    current_quarter_period,
    custom_period,
    download_current_prices,
    last_completed_quarter_period,
    quarter_period,
    run_analysis,
    today_ny,
    year_to_date_period,
)

st.set_page_config(page_title="S&P 500 Winner Tracker", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")


@st.cache_data(ttl=3600, show_spinner=False)
def cached_analysis(start_iso: str, end_iso: str, label: str, top_n: int, cache_version: int):
    from sp500_tracker import AnalysisPeriod

    period = AnalysisPeriod(label=label, start=date.fromisoformat(start_iso), end=date.fromisoformat(end_iso))
    return run_analysis(period, top_n=top_n)


@st.cache_data(ttl=900, show_spinner=False)
def cached_current_prices(symbols: tuple[str, ...], cache_version: int) -> pd.DataFrame:
    yahoo_tickers = [symbol.replace(".", "-") for symbol in symbols]
    prices = download_current_prices(yahoo_tickers)
    if prices.empty:
        return pd.DataFrame(columns=["Symbol", "Current Price", "Price As Of"])
    ticker_to_symbol = dict(zip(yahoo_tickers, symbols))
    prices["Symbol"] = prices["YahooTicker"].map(ticker_to_symbol)
    return prices[["Symbol", "Current Price", "Price As Of"]]


def add_current_prices(stocks: pd.DataFrame, period_ends_today: bool) -> pd.DataFrame:
    stocks = stocks.drop(columns=["Current Price", "Price As Of"], errors="ignore").copy()
    if period_ends_today and "End Adjusted Close" in stocks.columns:
        stocks["Current Price"] = stocks["End Adjusted Close"]
        stocks["Price As Of"] = stocks["End Trading Date"]
        return stocks
    prices = cached_current_prices(tuple(stocks["Symbol"].astype(str)), 1)
    return stocks.merge(prices, on="Symbol", how="left")


def metric_card(label: str, value: str, detail: str, accent: str, icon: str) -> None:
    st.markdown(
        f"""<div class="metric-card {accent}">
        <div class="metric-heading"><span>{escape(label)}</span><span>{icon}</span></div>
        <div class="metric-value">{escape(value)}</div><div class="metric-detail">{escape(detail)}</div></div>""",
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    :root {--bg:#071126;--line:rgba(104,142,230,.28);--text:#f4f7ff;--muted:#9eacd0;--cyan:#2ee7f2;--violet:#b15cff}
    [data-testid="stAppViewContainer"]{background:radial-gradient(circle at 78% 5%,rgba(78,46,180,.20),transparent 28%),radial-gradient(circle at 10% 35%,rgba(0,206,218,.08),transparent 25%),var(--bg);color:var(--text)}
    [data-testid="stHeader"]{background:transparent}.block-container{max-width:1700px;padding:1.5rem 2.5rem 3rem}#MainMenu,footer{visibility:hidden}
    .hero{display:flex;gap:1rem;align-items:center;margin-bottom:.1rem}.hero-icon{width:64px;height:64px;border-radius:15px;display:flex;align-items:center;justify-content:center;font-size:34px;background:linear-gradient(145deg,#143b73,#6f2dd9);border:1px solid #38e5ee;box-shadow:0 0 24px rgba(46,231,242,.18)}
    .hero h1{color:var(--text);font-size:2.55rem;line-height:1.05;margin:0;letter-spacing:-.035em}.hero-copy{color:var(--muted);margin:.55rem 0 1.35rem 5rem;font-size:1rem}
    .stTabs [data-baseweb="tab-list"]{gap:1.6rem;border-bottom:1px solid var(--line)}.stTabs [data-baseweb="tab"]{height:3.2rem;padding:0 .25rem;color:#b9c4e1}.stTabs [aria-selected="true"]{color:var(--cyan)!important}.stTabs [data-baseweb="tab-highlight"]{background-color:var(--cyan)}
    .control-shell{background:linear-gradient(115deg,rgba(16,30,66,.94),rgba(21,32,77,.72));border:1px solid var(--line);border-radius:16px;padding:.8rem 1rem .25rem;box-shadow:0 18px 50px rgba(0,0,0,.18);margin:.7rem 0 1.25rem}
    [data-testid="stWidgetLabel"] p{color:#c7d1ec;font-size:.84rem}[data-baseweb="select"]>div,[data-testid="stDateInput"] input,[data-testid="stNumberInput"] input{background:rgba(8,18,43,.72);border-color:rgba(111,143,218,.35);color:var(--text)}
    .stButton>button[kind="primary"]{border:0;color:#06132f;font-weight:800;min-height:2.85rem;background:linear-gradient(100deg,var(--cyan),#3fbbff 55%,var(--violet));box-shadow:0 0 24px rgba(80,109,255,.25)}.stButton>button[kind="primary"]:hover{color:#06132f;filter:brightness(1.08)}
    .metric-card{min-height:138px;padding:1.15rem 1.35rem;border-radius:16px;background:linear-gradient(145deg,rgba(13,34,63,.95),rgba(11,26,57,.88));border:1px solid var(--line);box-shadow:0 16px 38px rgba(0,0,0,.18)}
    .metric-card.green{border-color:rgba(24,211,167,.62);background:linear-gradient(145deg,rgba(6,54,63,.92),rgba(11,33,59,.88))}.metric-card.violet{border-color:rgba(159,89,255,.62);background:linear-gradient(145deg,rgba(38,29,90,.92),rgba(15,31,67,.88))}.metric-card.blue{border-color:rgba(45,130,255,.65);background:linear-gradient(145deg,rgba(13,47,94,.92),rgba(14,30,65,.88))}.metric-card.purple{border-color:rgba(197,77,248,.65);background:linear-gradient(145deg,rgba(63,25,93,.92),rgba(22,26,67,.88))}
    .metric-heading{display:flex;justify-content:space-between;color:#cbd5f2;font-size:.94rem}.metric-value{margin:.7rem 0 .1rem;font-size:2.15rem;font-weight:800;letter-spacing:-.03em}.green .metric-value{color:#4df1ba}.violet .metric-value{color:#bd83ff}.blue .metric-value{color:#48b8ff}.purple .metric-value{color:#e17bff}.metric-detail{color:var(--muted);font-size:.82rem}
    .section-title{display:flex;align-items:center;gap:.6rem;margin:.25rem 0 .65rem}.section-title h3{margin:0;color:var(--text)}.section-icon{color:var(--cyan);font-size:1.25rem}
    [data-testid="stExpander"],[data-testid="stDataFrame"],[data-testid="stVegaLiteChart"]{background:rgba(12,27,60,.68);border:1px solid var(--line);border-radius:14px}[data-testid="stDataFrame"]{overflow:hidden}[data-testid="stDownloadButton"] button{background:rgba(20,40,84,.8);color:#dbe6ff;border-color:var(--line)}
    .empty-state{min-height:310px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border:1px dashed rgba(104,142,230,.32);border-radius:16px;background:rgba(12,27,60,.38);color:var(--muted);margin-top:.8rem}.empty-state strong{color:var(--text);font-size:1.15rem;margin-bottom:.35rem}.method-note{color:var(--muted);font-size:.83rem;padding:.4rem .1rem}
    @media(max-width:900px){.block-container{padding:1rem}.hero h1{font-size:1.75rem}.hero-icon{width:50px;height:50px}.hero-copy{margin-left:0}.metric-card{min-height:120px}}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("""<div class="hero"><div class="hero-icon">↗</div><h1>S&amp;P 500 Winner Tracker</h1></div>
<div class="hero-copy">Find the biggest S&amp;P 500 stock winners for a quarter, year-to-date, or any custom period — and compare each winner with the market.</div>""", unsafe_allow_html=True)

tracker_tab, planned_tab, about_tab = st.tabs(["Tracker", "Backtest", "About"])

with tracker_tab:
    mode_col, start_col, end_col, count_col, run_col = st.columns([1.25, 1, 1, .9, 1.15])
    today = today_ny()
    with mode_col:
        mode = st.selectbox("Period", ["Quarter to date", "Last completed quarter", "Year to date", "Specific quarter", "Custom dates"])

    if mode == "Quarter to date":
        period = current_quarter_period(today)
    elif mode == "Last completed quarter":
        period = last_completed_quarter_period(today)
    elif mode == "Year to date":
        period = year_to_date_period(today)
    elif mode == "Specific quarter":
        with start_col:
            year = st.number_input("Year", min_value=1990, max_value=today.year, value=today.year, step=1)
        with end_col:
            quarter = st.selectbox("Quarter", [1, 2, 3, 4])
        period = quarter_period(int(year), int(quarter))
    else:
        with start_col:
            start = st.date_input("Start date", value=date(today.year, 1, 1))
        with end_col:
            end = st.date_input("End date", value=today)
        try:
            period = custom_period(start, end)
        except ValueError:
            period = custom_period(end, end)
            st.error("End date must be on or after start date.")

    if mode not in ("Specific quarter", "Custom dates"):
        with start_col:
            st.date_input("Start date", value=period.start, disabled=True)
        with end_col:
            st.date_input("End date", value=min(period.end, today), disabled=True)
    with count_col:
        top_n = st.selectbox("Winners", [5, 10, 15, 20, 25, 30], index=1)
    with run_col:
        st.markdown('<div style="height:1.75rem"></div>', unsafe_allow_html=True)
        run_clicked = st.button("▶  Run analysis", type="primary", width="stretch")
    if run_clicked and period.start <= today:
        try:
            with st.spinner("Downloading market data and ranking the S&P 500…"):
                result = cached_analysis(period.start.isoformat(), min(period.end, today).isoformat(), period.label, int(top_n), 4)
                st.session_state["analysis_result"] = result
                st.session_state["analysis_period"] = period
                st.session_state["analysis_top_n"] = int(top_n)
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
    elif run_clicked:
        st.error("That period starts in the future.")

    result = st.session_state.get("analysis_result")
    result_period = st.session_state.get("analysis_period")
    result_top_n = st.session_state.get("analysis_top_n", top_n)
    if result:
        top, summary, full = result
        winner = top.iloc[0]
        metric_cols = st.columns(4)
        with metric_cols[0]: metric_card("S&P 500 return", f"{summary['sp500_return_pct']:+.2f}%", str(summary["label"]), "green", "⌁")
        with metric_cols[1]: metric_card("Average constituent", f"{summary['constituent_average_pct']:+.2f}%", "Simple arithmetic average", "violet", "⌁")
        with metric_cols[2]: metric_card("Stocks analyzed", f"{summary['constituents_analyzed']}", "Current S&P 500 universe", "blue", "▥")
        with metric_cols[3]: metric_card("Top winner", f"{winner['Quarterly Return %']:+.2f}%", str(winner["Symbol"]), "purple", "♛")

        view_col, sector_col, sector_count_col = st.columns([1, 2, 1])
        with view_col:
            result_view = st.selectbox("Results view", ["Overall leaders", "Top performers by sector"])
        all_sectors = sorted(full["GICS Sector"].dropna().astype(str).unique())
        with sector_col:
            selected_sectors = st.multiselect(
                "Search or filter sectors",
                all_sectors,
                placeholder="All sectors",
            )
        with sector_count_col:
            per_sector_n = st.selectbox("Winners per sector", [1, 2, 3, 5, 10], index=2, disabled=result_view == "Overall leaders")

        filtered = full.copy()
        if selected_sectors:
            filtered = filtered[filtered["GICS Sector"].isin(selected_sectors)].copy()

        if result_view == "Top performers by sector":
            displayed = (
                filtered.sort_values(["GICS Sector", "Quarterly Return %"], ascending=[True, False])
                .groupby("GICS Sector", group_keys=False)
                .head(int(per_sector_n))
                .copy()
            )
            displayed["Sector Rank"] = displayed.groupby("GICS Sector").cumcount() + 1
            displayed = displayed.sort_values(["GICS Sector", "Sector Rank"]).reset_index(drop=True)
            result_title = f"Top {per_sector_n} in each sector"
        else:
            displayed = filtered.sort_values("Quarterly Return %", ascending=False).head(int(result_top_n)).copy()
            result_title = f"Top {len(displayed)} winners"

        period_ends_today = summary["effective_end"] >= today
        if period_ends_today:
            displayed = add_current_prices(displayed, True)
        else:
            with st.spinner("Updating current prices for the displayed winners…"):
                displayed = add_current_prices(displayed, False)

        chart_col, table_col = st.columns([1.35, 1])
        with chart_col:
            st.markdown('<div class="section-title"><span class="section-icon">▥</span><h3>Performance comparison</h3></div>', unsafe_allow_html=True)
            chart_rows = displayed.nlargest(30, "Quarterly Return %")[["Symbol", "Quarterly Return %"]].copy()
            chart_rows.columns = ["Series", "Return"]
            chart_rows = pd.concat([chart_rows, pd.DataFrame({"Series": ["S&P 500", "Average constituent"], "Return": [summary["sp500_return_pct"], summary["constituent_average_pct"]]})], ignore_index=True)
            domain = chart_rows["Series"].tolist()
            colors = ["#2ee7f2"] * (len(chart_rows) - 2) + ["#a85cff", "#8795c5"]
            chart = alt.Chart(chart_rows).mark_bar(cornerRadiusTopRight=5, cornerRadiusBottomRight=5).encode(
                y=alt.Y("Series:N", sort="-x", title=None, axis=alt.Axis(labelColor="#c7d1ec")),
                x=alt.X("Return:Q", title="Return (%)", axis=alt.Axis(labelColor="#9eacd0", titleColor="#9eacd0", gridColor="#263763")),
                color=alt.Color("Series:N", scale=alt.Scale(domain=domain, range=colors), legend=None),
                tooltip=[alt.Tooltip("Series:N"), alt.Tooltip("Return:Q", format="+.2f")],
            ).properties(height=390).configure_view(strokeOpacity=0).configure(background="transparent")
            st.altair_chart(chart, width="stretch")
        with table_col:
            st.markdown(f'<div class="section-title"><span class="section-icon">♜</span><h3>{escape(result_title)}</h3></div>', unsafe_allow_html=True)
            rank_columns = ["Rank"] if result_view == "Overall leaders" else ["Sector Rank", "Rank"]
            leaderboard = displayed[rank_columns + ["Symbol", "Security", "GICS Sector", "Current Price", "Quarterly Return %"]].copy()
            leaderboard["Quarterly Return %"] = pd.to_numeric(leaderboard["Quarterly Return %"], errors="coerce")
            leaderboard["Current Price"] = pd.to_numeric(leaderboard["Current Price"], errors="coerce")
            st.dataframe(leaderboard, width="stretch", hide_index=True, height=438, column_config={
                "Rank": st.column_config.NumberColumn("#", width="small", format="%d"), "Symbol": st.column_config.TextColumn("Ticker", width="small"),
                "Sector Rank": st.column_config.NumberColumn("Sector #", width="small", format="%d"),
                "Security": st.column_config.TextColumn("Company", width="medium"),
                "GICS Sector": st.column_config.TextColumn("Sector", width="medium"),
                "Current Price": st.column_config.NumberColumn("Price", width="small", format="$%.2f"),
                "Quarterly Return %": st.column_config.ProgressColumn("Return", format="%.2f%%", min_value=float(min(0, leaderboard["Quarterly Return %"].min())), max_value=float(max(1, leaderboard["Quarterly Return %"].max())))})

        safe_label = str(result_period.label).replace(" ", "_").replace("/", "-").replace(":", "-")
        download_a, download_b, note_col = st.columns([1, 1, 2])
        view_suffix = "by_sector" if result_view == "Top performers by sector" else f"top_{result_top_n}"
        with download_a: st.download_button("Download displayed winners CSV", displayed.to_csv(index=False).encode("utf-8-sig"), f"{safe_label}_{view_suffix}.csv", "text/csv", width="stretch")
        with download_b: st.download_button("Download all returns CSV", full.to_csv(index=False).encode("utf-8-sig"), f"{safe_label}_all_returns.csv", "text/csv", width="stretch")
        with note_col: st.markdown(f'<div class="method-note">Benchmark dates: {summary["benchmark_base_date"]} → {summary["benchmark_end_date"]} · {escape(summary["membership_basis"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown("""<div class="empty-state"><strong>Ready to find the market leaders</strong><span>Choose a period and run the analysis. The first request can take about a minute.</span></div>""", unsafe_allow_html=True)

    with st.expander("ⓘ  Important methodology note"):
        st.write("This version uses the current S&P 500 constituent list at runtime. Historical index membership must be reconstructed separately for a rigorous backtest. Returns use adjusted closing prices from the last trading close before the period starts through the final available close.")

with planned_tab:
    st.subheader("Backtest — next release")
    st.write("Compare recurring purchases of quarter-end winners with equal investments in the S&P 500.")
    st.markdown("- cumulative portfolio value\n- gains and drawdowns\n- quarter-by-quarter results\n- historical S&P 500 membership")
    st.info("The calculation engine for this section is planned; the current tracker remains fully functional.")

with about_tab:
    st.subheader("How the tracker works")
    st.write("The app pulls the current S&P 500 constituent list, downloads adjusted daily market data, calculates each stock's return for the selected period, and ranks the results.")
    st.write("The constituent comparison is a simple arithmetic average. The S&P 500 index is market-cap weighted, so the two benchmarks answer different questions.")
    st.caption("For research and tracking purposes only; not investment advice.")
