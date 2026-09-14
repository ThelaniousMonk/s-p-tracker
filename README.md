# S&P 500 Winner Tracker

A small Streamlit web app that ranks the biggest S&P 500 stock winners over a selected period and compares them with:

- the S&P 500 index return (`^GSPC`)
- the simple average return of the analyzed constituents

## Files

- `streamlit_app.py` — web interface
- `sp500_tracker.py` — market-data and ranking logic
- `requirements.txt` — Python dependencies for Streamlit Community Cloud

## Deploy on Streamlit Community Cloud

1. Create a new GitHub repository (for example, `sp500-winner-tracker`).
2. Upload the three application files in this folder to the root of the repository.
3. In Streamlit Community Cloud, create a new app from that repository.
4. Select your `main` branch.
5. Set the app entry point / main file to:

   `streamlit_app.py`

6. Deploy.

No secrets or API keys are required for this version.

## Current features

- Quarter-to-date analysis
- Last completed quarter
- Year-to-date
- Specific quarter
- Custom date range
- Top 2 through top 30 winners
- S&P 500 benchmark comparison
- Simple constituent-average comparison
- Download top-winner CSV
- Download full S&P 500 result CSV

## Important historical-data note

The live tracker uses the **current** S&P 500 constituent list at runtime. That is appropriate for current/future tracking. A rigorous historical backtest should reconstruct S&P 500 membership for each historical quarter so stocks are only eligible when they were actually index members.

## Backlog

The next planned feature is a backtest tab where you enter an amount such as `$500 per quarter` and compare buying the top two quarter-end winners with investing the same amount in the S&P 500.
