# ============================================================
# cleaner.py — FinSight Data Cleaner
# ============================================================
import pandas as pd
import numpy as np
from logger import get_logger

log = get_logger(__name__)

def clean_history(history: pd.DataFrame) -> pd.DataFrame:
    if history is None or history.empty:
        log.warning("Empty history passed to cleaner")
        return pd.DataFrame()
    df = history.copy()
    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    df = df.dropna(subset=["close"])
    df = df.ffill().bfill()
    df["daily_return"] = df["close"].pct_change()
    df["log_return"]   = np.log(df["close"] / df["close"].shift(1))
    df = df.dropna(subset=["daily_return"])
    df.index = pd.to_datetime(df.index)
    log.debug(f"Cleaned history: {len(df)} rows")
    return df

def clean_balance_sheet(balance: pd.DataFrame) -> dict:
    result = {"total_debt": None, "stockholders_equity": None}
    if balance is None or balance.empty:
        log.warning("Balance sheet unavailable")
        return result
    balance.index = [str(i).strip() for i in balance.index]
    for label in ["Total Debt","Long Term Debt","Total Liabilities Net Minority Interest","Current Debt And Capital Lease Obligation"]:
        if label in balance.index:
            val = balance.loc[label].iloc[0]
            if pd.notna(val):
                result["total_debt"] = float(val)
                break
    for label in ["Stockholders Equity","Total Equity Gross Minority Interest","Common Stock Equity","Total Stockholders Equity"]:
        if label in balance.index:
            val = balance.loc[label].iloc[0]
            if pd.notna(val):
                result["stockholders_equity"] = float(val)
                break
    log.debug(f"Balance sheet: debt={result['total_debt']}, equity={result['stockholders_equity']}")
    return result

def clean_market_index(index_series: pd.Series, stock_history: pd.DataFrame) -> pd.Series:
    if index_series.empty or stock_history.empty:
        return pd.Series(dtype=float)
    try:
        index_series  = index_series.copy()
        stock_history = stock_history.copy()
        index_series.index  = pd.to_datetime(index_series.index)
        stock_history.index = pd.to_datetime(stock_history.index)
        if index_series.index.tz is not None:
            index_series.index = index_series.index.tz_localize(None)
        if stock_history.index.tz is not None:
            stock_history.index = stock_history.index.tz_localize(None)
        aligned = index_series.reindex(stock_history.index, method="ffill").dropna()
        log.debug(f"Market index aligned: {len(aligned)} records")
        return aligned
    except Exception as e:
        log.error(f"Market index alignment failed: {e}")
        return pd.Series(dtype=float)
