# ============================================================
# config.py — FinSight Central Configuration
# All project settings live here. Change here, affects all.
# ============================================================
import os

# ─────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────
# Key is read from the environment (or a local .env file) rather than
# hardcoded here, so it never ends up committed to source control.
# Set it before running:
#   Windows (PowerShell):  $env:GROQ_API_KEY = "gsk_..."
#   macOS/Linux:            export GROQ_API_KEY="gsk_..."
# Or create a ".env" file (see .env.example) — python-dotenv loads it
# automatically if present.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; env vars set another way still work

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")   # empty → fallback summary mode
GROQ_MODEL   = "llama3-8b-8192"
GROQ_TOKENS  = 350
GROQ_TEMP    = 0.5

# ─────────────────────────────────────────────
# DATA SETTINGS
# ─────────────────────────────────────────────
DEFAULT_TIME_RANGE_DAYS = 365
RISK_FREE_RATE          = 0.06      # 6% — Indian 10-yr G-Sec baseline
MARKET_INDEX_PRIMARY    = "^NSEI"   # Nifty 50
MARKET_INDEX_FALLBACK   = "^GSPC"  # S&P 500

# ─────────────────────────────────────────────
# CACHE SETTINGS
# ─────────────────────────────────────────────
CACHE_ENABLED    = True
CACHE_TTL_SECS   = 300             # 5 minutes — how long cached data stays valid
CACHE_DIR        = ".finsight_cache"

# ─────────────────────────────────────────────
# RISK METRIC WEIGHTS  (must sum to 1.0)
# ─────────────────────────────────────────────
METRIC_WEIGHTS = {
    "volatility":     0.25,
    "beta":           0.20,
    "debt_to_equity": 0.20,
    "sharpe_ratio":   0.15,
    "pe_ratio":       0.10,
    "rsi":            0.10,
}

# ─────────────────────────────────────────────
# RISK SCORE THRESHOLDS
# ─────────────────────────────────────────────
RISK_THRESHOLDS = {
    "low":    3.5,   # score <= 3.5 → Low
    "medium": 6.5,   # score <= 6.5 → Medium
                     # score >  6.5 → High
}

# ─────────────────────────────────────────────
# METRIC NORMALIZATION RANGES
# 0 = lowest risk contribution, 1 = highest
# ─────────────────────────────────────────────
NORM_RANGES = {
    "volatility":     {"min": 0,   "max": 80,  "invert": False},
    "beta":           {"min": 0,   "max": 3,   "invert": False},
    "debt_to_equity": {"min": 0,   "max": 5,   "invert": False},
    "sharpe_ratio":   {"min": -1,  "max": 3,   "invert": True},
    "pe_ratio":       {"min": 0,   "max": 50,  "invert": False},
    "rsi":            {"min": 0,   "max": 100, "invert": False},
}

# ─────────────────────────────────────────────
# SIGNAL THRESHOLDS (for metric table labels)
# ─────────────────────────────────────────────
SIGNAL_THRESHOLDS = {
    "beta": [
        (0.8,         "✅ Low"),
        (1.2,         "🟡 Moderate"),
        (1.8,         "🟠 High"),
        (float("inf"),"🔴 Very High"),
    ],
    "volatility": [
        (15,          "✅ Stable"),
        (25,          "🟡 Moderate"),
        (40,          "🟠 High"),
        (float("inf"),"🔴 Very High"),
    ],
    "sharpe_ratio": [
        (0,           "🔴 Poor"),
        (1,           "🟠 Below Avg"),
        (2,           "🟡 Good"),
        (float("inf"),"✅ Excellent"),
    ],
    "debt_to_equity": [
        (0.5,         "✅ Low"),
        (1.0,         "🟡 Moderate"),
        (2.0,         "🟠 High"),
        (float("inf"),"🔴 Very High"),
    ],
    "pe_ratio": [
        (0,           "🔴 Negative"),
        (15,          "✅ Undervalued"),
        (25,          "🟡 Fair"),
        (40,          "🟠 High"),
        (float("inf"),"🔴 Overvalued"),
    ],
    "rsi": [
        (30,          "🟡 Oversold"),
        (70,          "✅ Neutral"),
        (float("inf"),"🔴 Overbought"),
    ],
}

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_ENABLED  = True
LOG_FILE     = "finsight.log"
LOG_LEVEL    = "INFO"            # DEBUG / INFO / WARNING / ERROR

# ─────────────────────────────────────────────
# UI SETTINGS
# ─────────────────────────────────────────────
APP_TITLE    = "FinSight — Stock Risk Analyzer"
APP_ICON     = "📊"
APP_LAYOUT   = "wide"

THEME = {
    "bg":          "#111827",
    "card_bg":     "#1e293b",
    "border":      "#334155",
    "text":        "#e2e8f0",
    "muted":       "#64748b",
    "blue":        "#3b82f6",
    "green":       "#22c55e",
    "yellow":      "#f59e0b",
    "red":         "#ef4444",
    "purple":      "#a855f7",
}
