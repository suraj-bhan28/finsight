# ============================================================
# fetcher.py — FinSight Data Fetcher
# Fetches stock data from Yahoo Finance via yfinance.
# Uses cache layer to avoid redundant API calls.
# ============================================================

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from logger import get_logger
from config import MARKET_INDEX_PRIMARY, MARKET_INDEX_FALLBACK
import cache

log = get_logger(__name__)


def fetch_stock_data(ticker: str, days: int = 365) -> dict:
    """
    Fetches OHLCV history + financial statements for a ticker.
    Checks cache first. Falls back to Yahoo Finance if cache miss.

    Returns:
        {
            info      : dict — stock metadata
            history   : DataFrame — OHLCV price data
            balance   : DataFrame — balance sheet
            financials: DataFrame — income statement
            error     : None | str
        }
    """
    result = {
        "info": None, "history": None,
        "balance": None, "financials": None, "error": None
    }

    # ── Cache check ──
    cached = cache.load(ticker, days, "stock")
    if cached:
        log.info(f"Loaded from cache: {ticker}")
        return cached

    log.info(f"Fetching from Yahoo Finance: {ticker} | {days} days")

    try:
        end_date   = datetime.today()
        start_date = end_date - timedelta(days=days)
        stock      = yf.Ticker(ticker)

        # Historical OHLCV
        history = stock.history(start=start_date, end=end_date)
        if history.empty:
            result["error"] = (
                f"No price data found for '{ticker}'. "
                f"Check the ticker symbol and suffix "
                f"(e.g. RELIANCE.NS for NSE, AAPL for US)."
            )
            log.warning(f"Empty history returned for {ticker}")
            return result

        result["history"] = history
        log.debug(f"{ticker}: {len(history)} price records fetched")

        # Stock metadata
        result["info"] = stock.info or {}

        # Balance sheet
        try:
            balance = stock.balance_sheet
            result["balance"] = balance if not balance.empty else None
            log.debug(f"{ticker}: balance sheet {'found' if result['balance'] is not None else 'missing'}")
        except Exception as e:
            log.warning(f"{ticker}: balance sheet fetch failed — {e}")
            result["balance"] = None

        # Income statement
        try:
            financials = stock.financials
            result["financials"] = financials if not financials.empty else None
        except Exception as e:
            log.warning(f"{ticker}: financials fetch failed — {e}")
            result["financials"] = None

        # ── Save to cache ──
        cache.save(ticker, days, "stock", result)
        log.info(f"Fetch complete: {ticker}")

    except Exception as e:
        result["error"] = f"Failed to fetch data for '{ticker}': {str(e)}"
        log.error(f"Fetch error for {ticker}: {e}")

    return result


def fetch_market_index(days: int = 365) -> pd.Series:
    """
    Fetches market index closing prices for Beta calculation.
    Primary: Nifty 50 (^NSEI) | Fallback: S&P 500 (^GSPC)
    Uses cache with 'market' key.

    Returns:
        pd.Series of closing prices indexed by date
    """
    # ── Cache check ──
    cached = cache.load("__market__", days, "index")
    if cached is not None:
        log.info("Market index loaded from cache")
        return cached

    for idx_ticker in [MARKET_INDEX_PRIMARY, MARKET_INDEX_FALLBACK]:
        try:
            log.info(f"Fetching market index: {idx_ticker}")
            end_date   = datetime.today()
            start_date = end_date - timedelta(days=days)
            idx        = yf.Ticker(idx_ticker)
            history    = idx.history(start=start_date, end=end_date)

            if not history.empty:
                series = history["Close"]
                cache.save("__market__", days, "index", series)
                log.info(f"Market index fetched: {idx_ticker} ({len(series)} records)")
                return series

        except Exception as e:
            log.warning(f"Market index fetch failed ({idx_ticker}): {e}")

    log.error("All market index sources failed. Beta will be unavailable.")
    return pd.Series(dtype=float)
