# FinSight — Project Documentation

**AI-Assisted Stock Risk Analysis and Financial Intelligence Dashboard**

This document explains what FinSight does, how it's built, the methodology behind every
calculation, and how to run and extend it. Read this alongside the code — file paths and
function names below match the actual project files exactly.

---

## 1. What FinSight Does

FinSight takes a stock ticker (e.g. `RELIANCE.NS`, `AAPL`) and produces a structured risk
profile:

1. Fetches historical price data and financial statements from Yahoo Finance
2. Cleans and derives return series from the raw price history
3. Computes six quantitative risk indicators (Beta, Volatility, Sharpe Ratio,
   Debt-to-Equity, P/E Ratio, RSI)
4. Aggregates those six indicators into a single weighted **risk score from 1–10**,
   with a Low / Medium / High category
5. Generates a plain-English summary of the risk profile, either via an LLM (Groq /
   LLaMA-3) or a deterministic rule-based fallback
6. Renders everything as an interactive dashboard, with an optional two-stock comparison
   mode

It is a **decision-support tool**, not an investment recommendation engine — every number
it produces is traceable back to a specific, inspectable calculation.

---

## 2. System Architecture

FinSight is a linear, modular pipeline. Each stage is a separate file with a single
responsibility, so a failure or change in one stage doesn't ripple through the others.

```
User Input (Streamlit Sidebar)
         │
         ▼
validator.py     — validates ticker format, time range, API key, comparison pair
         │
         ▼
fetcher.py       — pulls OHLCV history + balance sheet + income statement via yfinance
         │            (checks cache.py first — 5-minute TTL — before hitting the network)
         ▼
cleaner.py       — normalizes columns, fills gaps, computes daily/log returns,
         │            aligns the market index to the stock's trading calendar
         ▼
metrics.py       — computes Beta, Volatility, Sharpe Ratio, Debt-to-Equity,
         │            P/E Ratio, RSI — each in its own function with independent
         │            error handling, so one missing metric doesn't break the rest
         ▼
scorer.py        — normalizes each metric to a 0–1 risk contribution, applies
         │            configured weights, produces the final 1–10 score + category
         ▼
ai_summary.py    — sends metrics + score to Groq's LLaMA-3 API for a plain-English
         │            summary, or falls back to a rule-based summary if no API key
         │            is set or the call fails
         ▼
app.py           — Streamlit dashboard: gauge chart, metric table, AI summary card,
                     price/RSI/volatility charts, single or side-by-side comparison view

Cross-cutting:
  logger.py  — structured logging to console + finsight.log, used by every module
  config.py  — single source of truth for weights, thresholds, theme, API settings
```

### File-by-file responsibility

| File | Responsibility |
|---|---|
| `run.py` | Pre-flight checks (Python version, dependencies, files, config) then launches Streamlit |
| `app.py` | Streamlit UI: layout, charts, orchestrates the pipeline call per ticker |
| `config.py` | All tunable settings — weights, thresholds, cache TTL, theme colors, Groq settings |
| `validator.py` | Validates every user input before the pipeline runs; never raises, returns structured results |
| `fetcher.py` | Wraps `yfinance`; fetches price history, balance sheet, income statement, market index |
| `cache.py` | Disk-based cache (pickle + JSON metadata) to avoid redundant Yahoo Finance calls |
| `cleaner.py` | Turns raw yfinance output into clean, analysis-ready pandas structures |
| `metrics.py` | The six risk-metric calculations, plus the shared RSI series helper |
| `scorer.py` | Normalization + weighted aggregation into the final risk score |
| `ai_summary.py` | Groq API call + rule-based fallback summary generator |
| `logger.py` | Centralized logger factory used by every module |

---

## 3. Methodology — The Six Risk Metrics

Each metric captures a different dimension of investment risk. All are standard,
well-established financial indicators — FinSight's contribution is aggregating them into
one explainable composite score, not inventing new metrics.

### 3.1 Beta (market sensitivity)
**What it measures:** how much a stock's returns move relative to the overall market.

**Formula:** `Beta = Cov(stock_returns, market_returns) / Var(market_returns)`

- Computed in `metrics.calculate_beta()` using daily returns aligned by date
- Market benchmark: Nifty 50 (`^NSEI`), with S&P 500 (`^GSPC`) as fallback (`config.py`)
- Beta ≈ 1 → moves with the market · > 1 → more volatile than market · < 1 → less volatile

### 3.2 Volatility (price instability)
**What it measures:** how much the stock's price swings, annualized.

**Formula:** `Volatility = std(log_returns over last 30 days) × √252 × 100`

- Computed in `metrics.calculate_volatility()`
- √252 annualizes daily volatility (252 trading days/year) — a standard convention
- Log returns are used instead of simple returns because they're time-additive, which
  makes the standard-deviation math theoretically cleaner over multi-day windows

### 3.3 Sharpe Ratio (risk-adjusted return)
**What it measures:** return earned per unit of risk taken, relative to a risk-free
baseline.

**Formula:** `Sharpe = ((mean(daily_returns) − daily_risk_free) / std(daily_returns)) × √252`

- Computed in `metrics.calculate_sharpe_ratio()`
- Risk-free rate defaults to 6% (`config.RISK_FREE_RATE`), calibrated to the Indian
  10-year G-Sec yield — change this for other markets
- Higher is better; negative Sharpe means the stock underperformed the risk-free rate
  after accounting for its volatility

### 3.4 Debt-to-Equity (financial leverage)
**What it measures:** how reliant the company is on debt vs. shareholder capital.

**Formula:** `D/E = Total Debt / Stockholders' Equity`

- Computed in `metrics.calculate_debt_to_equity()`, sourced from `cleaner.clean_balance_sheet()`
- **Edge case handling:** if equity is zero or negative, the ratio is undefined/misleading
  as a plain division. FinSight explicitly flags this as `float('inf')` — treated as
  **maximum risk** by the scorer — because negative equity (liabilities exceeding assets)
  is itself a serious solvency warning sign, not a "low debt" reading.

### 3.5 P/E Ratio (valuation risk)
**What it measures:** how expensive the stock is relative to its earnings.

**Formula:** taken directly from Yahoo Finance's `trailingPE` (falls back to `forwardPE`
if trailing is unavailable)

- Computed in `metrics.calculate_pe_ratio()`
- Not itself a "risk" metric in the volatility sense — included because overvaluation
  relative to earnings is a recognized correction/drawdown risk factor

### 3.6 RSI — Relative Strength Index (momentum extremes)
**What it measures:** whether a stock is in overbought or oversold territory, based on
the magnitude of recent gains vs. losses.

**Formula (Wilder, 1978):**
```
RS  = avg_gain(14-day) / avg_loss(14-day)
RSI = 100 − (100 / (1 + RS))
```

- Implemented once in `metrics.rsi_series()` (returns the full rolling series) and
  `metrics.calculate_rsi()` (returns the latest value) — `app.py`'s RSI chart reuses
  `rsi_series()` rather than recomputing the formula, so there's a single source of truth
- RSI > 70 → overbought · RSI < 30 → oversold · 30–70 → neutral momentum

---

## 4. Methodology — Composite Risk Scoring

This is the core "explainability" mechanism: every metric's contribution to the final
score is individually visible, not hidden inside a black-box model.

### Step 1 — Normalize each metric to a 0–1 risk scale
`scorer.normalize_metric()` maps each raw value into a 0 (lowest risk) to 1 (highest
risk) range, using bounds defined in `config.NORM_RANGES`:

| Metric | Min | Max | Inverted? |
|---|---|---|---|
| Volatility | 0 | 80 | No |
| Beta | 0 | 3 | No |
| Debt-to-Equity | 0 | 5 | No |
| Sharpe Ratio | −1 | 3 | **Yes** (higher Sharpe = lower risk) |
| P/E Ratio | 0 | 50 | No |
| RSI | 0 | 100 | Special-cased (see below) |

- Values are clamped to `[min, max]` before normalizing, so extreme outliers don't blow
  up the score
- **RSI is special-cased**, not linearly normalized: risk rises as RSI moves toward either
  extreme (overbought *or* oversold), not just in one direction, since both extremes
  signal elevated momentum risk
- A missing metric (`None`) is scored as a **neutral 0.5** — it doesn't push the score
  toward Low or High, it just contributes proportionally less certainty
- `float('inf')` (the negative-equity D/E case) clamps to the range maximum, which
  normalizes to exactly 1.0 — maximum risk contribution

### Step 2 — Weighted aggregation
`scorer.compute_risk_score()` combines the six normalized scores using fixed weights
from `config.METRIC_WEIGHTS` (must sum to 1.0 — checked at startup by `run.py`):

| Metric | Weight | Rationale |
|---|---|---|
| Volatility | 25% | Most direct measure of price risk |
| Beta | 20% | Systematic/market risk exposure |
| Debt-to-Equity | 20% | Solvency and leverage risk |
| Sharpe Ratio | 15% | Risk-adjusted performance context |
| P/E Ratio | 10% | Valuation risk (softer signal) |
| RSI | 10% | Short-term momentum risk (softer signal) |

```
weighted_sum = Σ (normalized_metric × weight)
final_score  = clamp(1 + weighted_sum × 9, 1, 10)
```

The `× 9` and `+ 1` rescale the 0–1 weighted sum onto a 1–10 scale.

### Step 3 — Categorization
Thresholds from `config.RISK_THRESHOLDS`:

| Score range | Category |
|---|---|
| ≤ 3.5 | Low |
| 3.5 – 6.5 | Medium |
| > 6.5 | High |

### Explainability output
`compute_risk_score()` returns a full `breakdown` dict per metric — raw value,
normalized value, weight, and weighted contribution — which `app.py` renders directly in
the "Metric Breakdown" table. Nothing about the final score is opaque: a user can trace
exactly why a stock scored the way it did.

---

## 5. AI Summary Generation

`ai_summary.generate_ai_summary()` has two paths:

1. **Groq path (if `GROQ_API_KEY` is set):** sends the computed metrics and score to
   Groq's `llama3-8b-8192` model with a fixed prompt template asking for a 4–5 sentence,
   jargon-free summary for a retail investor. Temperature 0.5, max 350 tokens
   (`config.py`). On any API failure, it falls back automatically and appends the error
   to the output rather than failing silently.
2. **Rule-based fallback (default, no key required):** `_fallback_summary()`
   deterministically constructs sentences from threshold comparisons on Beta, Volatility,
   Sharpe, and RSI, plus a closing suitability line based on risk category. This means
   **FinSight works fully offline from an AI standpoint** — the LLM is an enhancement,
   not a dependency.

---

## 6. Data Pipeline Details

### Fetching (`fetcher.py`)
- `fetch_stock_data(ticker, days)` — OHLCV history, `stock.info`, balance sheet, income
  statement. Each sub-fetch (balance sheet, financials) has independent try/except so a
  missing statement doesn't fail the whole fetch.
- `fetch_market_index(days)` — tries Nifty 50 first, S&P 500 second, for Beta's market
  benchmark.
- Every fetch checks `cache.py` first (5-minute TTL, pickled to `.finsight_cache/`)
  before hitting Yahoo Finance, keeping repeat queries fast and reducing API load.

### Cleaning (`cleaner.py`)
- `clean_history()` — lowercases columns, drops rows with missing close price,
  forward/backward-fills gaps, derives `daily_return` and `log_return`.
- `clean_balance_sheet()` — searches a prioritized list of possible Yahoo Finance
  balance-sheet row labels (label names vary by company/filing) to find total debt and
  stockholders' equity.
- `clean_market_index()` — aligns the market index's dates to the stock's trading
  calendar (handles timezone stripping and forward-fill for non-overlapping trading
  days).

### Validation (`validator.py`)
Runs before any network-heavy work: ticker format (length, character whitelist,
blacklist patterns for obviously-invalid input), optional live existence check against
Yahoo Finance, time range (90/180/365 days only), Groq key format, and — in comparison
mode — that the two tickers aren't identical. `run_all_validations()` aggregates all
checks and returns every error at once rather than stopping at the first failure.

---

## 7. Setup & Running

### Requirements
- Python 3.9+
- Dependencies in `requirements.txt` (yfinance, pandas, numpy, streamlit, plotly, groq,
  python-dotenv)

### Steps
```bash
cd finsight
pip install -r requirements.txt

# Optional — enables AI summaries instead of the rule-based fallback
cp .env.example .env
# then edit .env and paste a real key from console.groq.com

python run.py
```

`run.py` performs pre-flight checks (Python version, installed packages, required files,
config sanity — e.g. weights summing to 1.0) before launching Streamlit at
`http://localhost:8501`.

### Configuration
All tunables live in `config.py`: metric weights, normalization ranges, risk thresholds,
signal labels, cache TTL, risk-free rate, market index tickers, UI theme. Change values
there rather than in the pipeline code — every downstream module reads from this file.

---

## 8. Known Limitations

- **Data freshness/reliability**: entirely dependent on Yahoo Finance's data quality and
  availability. Small-cap and recently-listed stocks frequently have incomplete balance
  sheet data, which causes Debt-to-Equity to fall back to a neutral 0.5 score rather than
  a true reading.
- **No forward-looking signals**: the score is built entirely from historical price
  action and the most recent balance sheet — it does not incorporate earnings guidance,
  analyst estimates, or macroeconomic indicators.
- **LLM hallucination risk**: like any LLM output, the Groq-generated summary should be
  treated as a readable interpretation of the computed numbers, not an independent source
  of truth — the numbers themselves (not the prose) are the ground truth.
- **Fixed weights**: the 25/20/20/15/10/10 metric weighting is a reasonable default, not
  an empirically fitted or validated allocation — treat it as a configurable starting
  point rather than a proven optimum.
- **Single-point-in-time analysis**: FinSight scores a stock as of "now" (or the selected
  window's end) — it isn't a backtesting or historical-scoring tool across many dates.
- **Not investment advice**: FinSight is explicitly a decision-support tool. It surfaces
  and explains quantitative signals; it does not account for portfolio context,
  individual risk tolerance, tax situation, or other factors a real financial advisor
  would consider.

---

## 9. Possible Extensions

- News/sentiment analysis module feeding into the qualitative side of the risk profile
- Portfolio-level aggregation (risk across a basket of holdings, not just one stock)
- Historical backtesting of the scoring model against realized outcomes
- Options-market implied volatility as an additional forward-looking risk signal
- Additional market indices for Beta calculation outside India/US

---

## 10. Quick Reference — Where to Look for What

| I want to change... | Edit this file |
|---|---|
| Metric weights or risk thresholds | `config.py` |
| How a specific metric is calculated | `metrics.py` |
| How the composite score is computed | `scorer.py` |
| The AI summary prompt or fallback wording | `ai_summary.py` |
| What data is fetched from Yahoo Finance | `fetcher.py` |
| Dashboard layout, charts, colors | `app.py` |
| Input validation rules | `validator.py` |
| Cache duration or behavior | `config.py` (`CACHE_*`) / `cache.py` |
