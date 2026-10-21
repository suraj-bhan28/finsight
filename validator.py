# ============================================================
# validator.py — FinSight Input Validator
# Validates all user inputs before the pipeline runs.
# Returns structured result dicts — never raises directly.
# ============================================================

import re
import yfinance as yf
from logger import get_logger

log = get_logger(__name__)

# Known valid suffix patterns
VALID_SUFFIXES = [
    ".NS",   # NSE India
    ".BO",   # BSE India
    ".L",    # London Stock Exchange
    ".AX",   # Australian Securities Exchange
    ".T",    # Tokyo Stock Exchange
    ".HK",   # Hong Kong Stock Exchange
    ".SI",   # Singapore Exchange
    ".DE",   # Deutsche Börse
    ".PA",   # Euronext Paris
]

# Tickers that are obviously wrong
BLACKLISTED_PATTERNS = [
    r"^[0-9]+$",          # pure numbers
    r"[^A-Z0-9.\-^]",    # invalid characters
    r"^\..*",             # starts with dot
    r".*\.$",             # ends with dot
]


def _ok(data: dict = None) -> dict:
    return {"valid": True, "error": None, "data": data or {}}


def _fail(message: str) -> dict:
    return {"valid": False, "error": message, "data": {}}


def validate_ticker(ticker: str) -> dict:
    """
    Validates a stock ticker symbol.

    Checks:
    - Not empty
    - Reasonable length (1-12 chars)
    - No invalid characters
    - Not a blacklisted pattern
    - Optionally verifies against Yahoo Finance (soft check)

    Returns:
        {"valid": True/False, "error": str|None, "data": {}}
    """
    if not ticker or not ticker.strip():
        log.warning("Empty ticker submitted")
        return _fail("Ticker cannot be empty. Enter a valid stock symbol (e.g. RELIANCE.NS).")

    ticker = ticker.upper().strip()

    if len(ticker) > 15:
        return _fail(f"Ticker '{ticker}' is too long. Stock symbols are typically under 15 characters.")

    if len(ticker) < 1:
        return _fail("Ticker is too short.")

    # Check for blacklisted patterns
    for pattern in BLACKLISTED_PATTERNS:
        if re.search(pattern, ticker):
            log.warning(f"Ticker failed pattern check: {ticker}")
            return _fail(
                f"'{ticker}' does not look like a valid stock symbol. "
                f"Examples: RELIANCE.NS, TCS.NS, AAPL, MSFT"
            )

    log.debug(f"Ticker format valid: {ticker}")
    return _ok({"ticker": ticker})


def validate_ticker_exists(ticker: str) -> dict:
    """
    Soft-checks if ticker exists on Yahoo Finance
    by attempting a minimal data fetch.
    This is a network call — use only when needed.

    Returns:
        {"valid": True/False, "error": str|None, "data": {"name": company_name}}
    """
    try:
        log.debug(f"Verifying ticker existence: {ticker}")
        stock = yf.Ticker(ticker)
        info  = stock.info

        # Yahoo Finance returns empty or minimal dict for invalid tickers
        name = info.get("longName") or info.get("shortName")
        if not name:
            log.warning(f"Ticker not found on Yahoo Finance: {ticker}")
            return _fail(
                f"Could not find '{ticker}' on Yahoo Finance. "
                f"Check the symbol and suffix (e.g. RELIANCE.NS for NSE India)."
            )

        log.info(f"Ticker verified: {ticker} → {name}")
        return _ok({"ticker": ticker, "name": name})

    except Exception as e:
        log.error(f"Ticker verification failed for {ticker}: {e}")
        return _fail(
            f"Could not verify '{ticker}'. "
            f"Check your internet connection or try again."
        )


def validate_time_range(days: int) -> dict:
    """
    Validates the selected time range in days.
    Allowed: 90, 180, 365
    """
    allowed = [90, 180, 365]
    if days not in allowed:
        log.warning(f"Invalid time range submitted: {days}")
        return _fail(f"Invalid time range: {days} days. Choose 90, 180, or 365.")
    return _ok({"days": days})


def validate_groq_key(key: str) -> dict:
    """
    Validates the Groq API key format.
    Does NOT make an API call — just checks format.
    Real errors will surface during AI summary generation.

    Groq keys start with 'gsk_' and are 50+ chars.
    """
    if not key or not key.strip():
        # Empty key is allowed — triggers fallback summary
        return _ok({"groq_key": "", "ai_enabled": False})

    key = key.strip()

    if not key.startswith("gsk_"):
        log.warning("Groq API key has invalid prefix")
        return _fail(
            "Groq API key should start with 'gsk_'. "
            "Get a free key at console.groq.com"
        )

    if len(key) < 40:
        log.warning(f"Groq API key too short: {len(key)} chars")
        return _fail("Groq API key looks incomplete. Please paste the full key.")

    log.debug("Groq API key format valid")
    return _ok({"groq_key": key, "ai_enabled": True})


def validate_comparison_pair(ticker1: str, ticker2: str) -> dict:
    """
    Validates that two tickers submitted for comparison are not identical.
    """
    if ticker1.upper().strip() == ticker2.upper().strip():
        return _fail(
            f"Both tickers are the same ({ticker1}). "
            f"Enter two different stocks to compare."
        )
    return _ok()


def run_all_validations(ticker: str, days: int, groq_key: str,
                         compare_mode: bool = False, ticker2: str = "",
                         check_existence: bool = True) -> dict:
    """
    Master validation function.
    Runs all relevant validators and returns a combined result.

    check_existence: when True (default), also soft-verifies the ticker
    against Yahoo Finance so a well-formatted but nonexistent symbol
    (e.g. "ZZZZ.NS") is caught here with a clear message instead of
    failing later, less clearly, at the data-fetch stage. This costs a
    network call, so callers doing bulk/offline validation can disable it.

    Returns:
        {
            "valid": True/False,
            "errors": [list of error strings],
            "data": {validated inputs}
        }
    """
    errors = []
    data   = {}

    # Validate primary ticker (format, then existence)
    r1 = validate_ticker(ticker)
    if not r1["valid"]:
        errors.append(r1["error"])
    else:
        data["ticker"] = r1["data"]["ticker"]
        if check_existence:
            r1b = validate_ticker_exists(data["ticker"])
            if not r1b["valid"]:
                errors.append(r1b["error"])
            elif r1b["data"].get("name"):
                data["ticker_name"] = r1b["data"]["name"]

    # Validate time range
    r2 = validate_time_range(days)
    if not r2["valid"]:
        errors.append(r2["error"])
    else:
        data["days"] = r2["data"]["days"]

    # Validate Groq key
    r3 = validate_groq_key(groq_key)
    if not r3["valid"]:
        errors.append(r3["error"])
    else:
        data["groq_key"]   = r3["data"]["groq_key"]
        data["ai_enabled"] = r3["data"]["ai_enabled"]

    # Validate second ticker if comparison mode
    if compare_mode:
        r4 = validate_ticker(ticker2)
        if not r4["valid"]:
            errors.append(f"Second ticker: {r4['error']}")
        else:
            data["ticker2"] = r4["data"]["ticker"]
            r5 = validate_comparison_pair(ticker, ticker2)
            if not r5["valid"]:
                errors.append(r5["error"])
            if check_existence:
                r4b = validate_ticker_exists(data["ticker2"])
                if not r4b["valid"]:
                    errors.append(f"Second ticker: {r4b['error']}")
                elif r4b["data"].get("name"):
                    data["ticker2_name"] = r4b["data"]["name"]

    if errors:
        log.warning(f"Validation failed: {errors}")
        return {"valid": False, "errors": errors, "data": data}

    log.info(f"All inputs validated successfully: ticker={ticker}, days={days}")
    return {"valid": True, "errors": [], "data": data}
