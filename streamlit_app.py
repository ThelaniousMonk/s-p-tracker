from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from sp500_tracker import (
    current_quarter_period,
    custom_period,
    last_completed_quarter_period,
    quarter_period,
    run_analysis,
    today_ny,
    year_to_date_period,
)

st.set_page_config(
    page_title="S&P 500 Winner Tracker",
    page_icon="📈",
    layout="wide",
)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_analysis(start_iso: str, end_iso: str, label: str, top_n: int):
    # Import here to reconstruct a simple period object while keeping cache args primitive.
    from sp500_tracker import AnalysisPeriod

    period = AnalysisPeriod(
        label=label,
        start=date.fromisoformat(start_iso),
        end=date.fromisoformat(end_iso),
    )
    return run_analysis(period, top_n=top_n)


st.title("📈 S&P 500 Winner Tracker")
st.caption(
    "Find the biggest S&P 500 stock winners for a quarter, year-to-date, or any custom period — "
    "and compare each winner with the S&P 500 and the average constituent return."
)

tracker_tab, planned_tab, about_tab = st.tabs(["Tracker", "Backtest (planned)", "About"])

with tracker_tab:
    left, right = st.columns([1, 2])

    with left:
        st.subheader("Analysis settings")

        mode = st.selectbox(
            "Period",
            [
                "Quarter to date",
                "Last completed quarter",
                "Year to date",
                "Specific quarter",
                "Custom dates",
            ],
        )

        today = today_ny()

        if mode == "Quarter to date":
            period = current_quarter_period(today)

        elif mode == "Last completed quarter":
            period = last_completed_quarter_period(today)

        elif mode == "Year to date":
            period = year_to_date_period(today)

        elif mode == "Specific quarter":
            year = st.number_input(
                "Year",
                min_value=1990,
                max_value=today.year,
                value=today.year,
                step=1,
            )
            quarter = st.selectbox("Quarter", [1, 2, 3, 4])
            period = quarter_period(int(year), int(quarter))

        else:
            start = st.date_input("Start date", value=date(today.year, 1, 1))
            end = st.date_input("End date", value=today)
            period = custom_period(start, end)

        top_n = st.slider("Number of winners", min_value=2, max_value=30, value=10)

        st.info(
            f"**Selected:** {period.label}\n\n"
            f"{period.start:%b %d, %Y} → {min(period.end, today):%b %d, %Y}"
        )

        run_clicked = st.button("Run analysis", type="primary", use_container_width=True)

        with st.expander("Important methodology note"):
            st.write(
                "This web version uses the **current S&P 500 constituent list at the time you run it**. "
                "That is ideal for current and future tracking. For historical backtests, index membership "
                "changes should be reconstructed separately so a stock is not treated as an S&P 500 member "
                "before it actually joined the index."
            )
            st.write(
                "Returns use adjusted closing prices and measure from the last trading close before the "
                "period starts through the last available close on or before the period end."
            )

    with right:
        st.subheader("Results")

        if run_clicked:
            if period.start > today:
                st.error("That period starts in the future.")
            else:
                try:
                    with st.spinner("Downloading market data and ranking the S&P 500…"):
                        top, summary, full = cached_analysis(
                            period.start.isoformat(),
                            min(period.end, today).isoformat(),
                            period.label,
                            top_n,
                        )

                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("S&P 500 return", f"{summary['sp500_return_pct']:+.2f}%")
                    m2.metric(
                        "Average constituent",
                        f"{summary['constituent_average_pct']:+.2f}%",
                    )
                    m3.metric("Stocks analyzed", f"{summary['constituents_analyzed']}")
                    m4.metric("Top winner", str(top.iloc[0]["Symbol"]))

                    display = top.copy()
                    pct_cols = [
                        "Quarterly Return %",
                        "S&P 500 Return %",
                        "Beat S&P 500 By (pp)",
                        "Constituent Average Return %",
                        "Beat Constituent Average By (pp)",
                    ]
                    for c in pct_cols:
                        display[c] = pd.to_numeric(display[c], errors="coerce").round(2)

                    st.dataframe(
                        display,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Quarterly Return %": st.column_config.NumberColumn(format="%.2f%%"),
                            "S&P 500 Return %": st.column_config.NumberColumn(format="%.2f%%"),
                            "Beat S&P 500 By (pp)": st.column_config.NumberColumn(format="%.2f pp"),
                            "Constituent Average Return %": st.column_config.NumberColumn(format="%.2f%%"),
                            "Beat Constituent Average By (pp)": st.column_config.NumberColumn(format="%.2f pp"),
                        },
                    )

                    chart_data = top.set_index("Symbol")[["Quarterly Return %"]]
                    st.bar_chart(chart_data)

                    safe_label = (
                        period.label.replace(" ", "_")
                        .replace("/", "-")
                        .replace(":", "-")
                    )

                    c1, c2 = st.columns(2)
                    with c1:
                        st.download_button(
                            "Download top winners CSV",
                            data=top.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"{safe_label}_top_{top_n}.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                    with c2:
                        st.download_button(
                            "Download all S&P 500 returns CSV",
                            data=full.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"{safe_label}_all_returns.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

                    st.caption(
                        f"Benchmark trading dates: {summary['benchmark_base_date']} → "
                        f"{summary['benchmark_end_date']}. Membership basis: {summary['membership_basis']}."
                    )

                except Exception as exc:
                    st.error(f"Analysis failed: {exc}")
                    st.exception(exc)
        else:
            st.write(
                "Choose a period and click **Run analysis**. The first run can take a minute because "
                "the app downloads price history for the full S&P 500."
            )

with planned_tab:
    st.subheader("Backtest — backlog")
    st.write(
        "Planned next: enter an investment amount (for example **$500 per quarter**) and compare:"
    )
    st.markdown(
        "- buying the top 2 quarter-end winners after each quarter closes\n"
        "- investing the same amount in the S&P 500\n"
        "- cumulative value, gains, drawdowns, and quarter-by-quarter results\n"
        "- historical S&P 500 membership so the backtest does not use hindsight membership"
    )
    st.info("This tab is intentionally a placeholder for the next project iteration.")

with about_tab:
    st.subheader("How this tracker works")
    st.write(
        "The app pulls the current S&P 500 constituent list, downloads adjusted daily market data, "
        "calculates each stock's return for the selected period, and ranks the results."
    )
    st.write(
        "**Beat S&P 500 By (pp)** is the stock's return minus the S&P 500 index return in percentage points. "
        "The constituent-average comparison is a simple arithmetic average, while the S&P 500 itself is "
        "market-cap weighted."
    )
    st.caption("For research and tracking purposes only; not investment advice.")
