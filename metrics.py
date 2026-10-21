# ============================================================
# metrics.py — FinSight Metrics Engine
# ============================================================
import pandas as pd
import numpy as np
from logger import get_logger
from config import RISK_FREE_RATE

log = get_logger(__name__)

def calculate_beta(stock_returns, market_returns):
    try:
        combined = pd.DataFrame({"stock": stock_returns, "market": market_returns}).dropna()
        if len(combined) < 10:
            return None
        cov = combined["stock"].cov(combined["market"])
        var = combined["market"].var()
        if var == 0:
            return None
        beta = round(float(cov / var), 4)
        log.debug(f"Beta: {beta}")
        return beta
    except Exception as e:
        log.error(f"Beta calculation failed: {e}")
        return None

def calculate_volatility(log_returns):
    try:
        if log_returns.empty or len(log_returns) < 10:
            return None
        window  = min(30, len(log_returns))
        vol     = log_returns.tail(window).std() * np.sqrt(252) * 100
        log.debug(f"Volatility: {vol:.2f}%")
        return round(float(vol), 4)
    except Exception as e:
        log.error(f"Volatility calculation failed: {e}")
        return None

def calculate_sharpe_ratio(daily_returns):
    try:
        if daily_returns.empty or len(daily_returns) < 10:
            return None
        daily_rf  = RISK_FREE_RATE / 252
        ann_vol   = daily_returns.std() * np.sqrt(252)
        if ann_vol == 0:
            return None
        sharpe = ((daily_returns.mean() - daily_rf) / daily_returns.std()) * np.sqrt(252)
        log.debug(f"Sharpe: {sharpe:.4f}")
        return round(float(sharpe), 4)
    except Exception as e:
        log.error(f"Sharpe calculation failed: {e}")
        return None

def calculate_debt_to_equity(balance_data):
    """
    Returns the Debt-to-Equity ratio, or a sentinel float('inf') when
    stockholders' equity is zero or negative.

    Negative equity means liabilities exceed assets — a serious solvency
    red flag, not a "low D/E" reading. Returning None here (as the old
    code did) let the scorer normalize it to the *lowest*-risk end of
    the range, which is backwards. float('inf') forces it to the
    highest-risk end instead, and the raw value stays visible to the
    user rather than being silently hidden.
    """
    try:
        debt   = balance_data.get("total_debt")
        equity = balance_data.get("stockholders_equity")
        if debt is None or equity is None:
            return None
        if equity <= 0:
            log.warning(f"Negative/zero stockholders' equity ({equity}) — "
                        f"flagging D/E as maximum risk instead of computing a ratio")
            return float("inf")
        de = round(float(debt / equity), 4)
        log.debug(f"D/E: {de}")
        return de
    except Exception as e:
        log.error(f"D/E calculation failed: {e}")
        return None

def calculate_pe_ratio(stock_info):
    try:
        pe = stock_info.get("trailingPE") or stock_info.get("forwardPE")
        if pe is None:
            return None
        log.debug(f"P/E: {pe}")
        return round(float(pe), 4)
    except Exception as e:
        log.error(f"P/E calculation failed: {e}")
        return None

def rsi_series(close_prices, period=14):
    """
    Returns the full rolling RSI series for close_prices.
    Shared by metrics.calculate_rsi() and app.py's rsi_chart(),
    so the formula only lives in one place.
    """
    delta = close_prices.diff()
    gain  = delta.clip(lower=0).rolling(window=period).mean()
    loss  = (-delta.clip(upper=0)).rolling(window=period).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_rsi(close_prices, period=14):
    try:
        if close_prices.empty or len(close_prices) < period + 1:
            return None
        rsi    = rsi_series(close_prices, period).dropna()
        if rsi.empty:
            return None
        latest = round(float(rsi.iloc[-1]), 4)
        log.debug(f"RSI: {latest}")
        return latest
    except Exception as e:
        log.error(f"RSI calculation failed: {e}")
        return None

def compute_all_metrics(clean_df, balance_data, stock_info, market_index):
    log.info("Computing all risk metrics")
    stock_returns  = clean_df.get("daily_return", pd.Series()) if isinstance(clean_df, pd.DataFrame) else pd.Series()
    log_returns    = clean_df.get("log_return",   pd.Series()) if isinstance(clean_df, pd.DataFrame) else pd.Series()
    close          = clean_df.get("close",         pd.Series()) if isinstance(clean_df, pd.DataFrame) else pd.Series()
    market_returns = market_index.pct_change().dropna() if not market_index.empty else pd.Series()

    metrics = {
        "beta":           calculate_beta(stock_returns, market_returns),
        "volatility":     calculate_volatility(log_returns),
        "sharpe_ratio":   calculate_sharpe_ratio(stock_returns),
        "debt_to_equity": calculate_debt_to_equity(balance_data),
        "pe_ratio":       calculate_pe_ratio(stock_info),
        "rsi":            calculate_rsi(close),
    }
    computed = sum(1 for v in metrics.values() if v is not None)
    log.info(f"Metrics computed: {computed}/6 — {metrics}")
    return metrics
