# ============================================================
# app.py — FinSight Main Dashboard
# Entry point for Streamlit. Orchestrates all modules.
# ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from config     import GROQ_API_KEY, APP_TITLE, APP_ICON, APP_LAYOUT, THEME, METRIC_WEIGHTS
from logger     import get_logger, log_session_start
from validator  import run_all_validations
from fetcher    import fetch_stock_data, fetch_market_index
from cleaner    import clean_history, clean_balance_sheet, clean_market_index
from metrics    import compute_all_metrics, rsi_series
from scorer     import compute_risk_score, get_metric_signal
from ai_summary import generate_ai_summary
import cache

log = get_logger(__name__)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout=APP_LAYOUT)

st.markdown(f"""
<style>
html, body, [class*="css"] {{ font-family: 'Segoe UI', sans-serif; }}
section[data-testid="stSidebar"] {{ background-color: #0f1923; }}
.ai-card {{
    background-color: {THEME['card_bg']};
    border-left: 5px solid {THEME['blue']};
    padding: 18px 20px; border-radius: 10px;
    font-size: 15px; line-height: 1.8; color: {THEME['text']};
}}
.welcome-card {{
    background: {THEME['card_bg']}; border-radius: 12px;
    padding: 20px; border: 1px solid {THEME['border']};
    text-align: center;
}}
.welcome-card h3 {{ color:{THEME['muted']}; font-size:13px; text-transform:uppercase; letter-spacing:1px; }}
.welcome-card p  {{ color:{THEME['text']}; font-size:15px; margin:0; }}
.badge-Low    {{ background:#166534; color:#bbf7d0; padding:4px 14px; border-radius:20px; font-weight:700; }}
.badge-Medium {{ background:#854d0e; color:#fef08a; padding:4px 14px; border-radius:20px; font-weight:700; }}
.badge-High   {{ background:#7f1d1d; color:#fecaca; padding:4px 14px; border-radius:20px; font-weight:700; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
for key in ["results", "last_ticker", "last_ticker2", "last_days"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 FinSight")
    st.caption("AI-Assisted Stock Risk Analyzer")
    st.markdown("---")

    st.markdown("### 🔍 Stock Selection")
    ticker = st.text_input("Primary Ticker", value="RELIANCE.NS",
        help="NSE→.NS  |  BSE→.BO  |  US→no suffix").upper().strip()

    time_range = st.selectbox("Time Range", ["3 Months","6 Months","1 Year"], index=2)
    days = {"3 Months":90, "6 Months":180, "1 Year":365}[time_range]

    st.markdown("---")
    compare_mode = st.checkbox("⚖️ Compare Two Stocks")
    ticker2 = None
    if compare_mode:
        ticker2 = st.text_input("Second Ticker", value="TCS.NS").upper().strip()

    # ── Groq key from config.py ──
    groq_key = GROQ_API_KEY
    if groq_key and groq_key not in ("", "your_groq_api_key_here"):
        st.success("🤖 AI Summary: Groq connected")
    else:
        st.warning("🤖 AI Summary: fallback mode\n\nSet GROQ_API_KEY in config.py")

    st.markdown("---")
    analyze = st.button("🚀 Analyze Risk", use_container_width=True, type="primary")

    # ── Cache Controls ──
    st.markdown("---")
    st.markdown("### 🗄️ Cache")
    cs = cache.status()
    st.caption(f"{cs['entries']} entries · {cs['size_kb']} KB · TTL {cs['ttl_secs']}s")
    if st.button("🗑️ Clear Cache", use_container_width=True):
        cache.invalidate()
        st.session_state["results"] = None
        st.success("Cache cleared.")
        log.info("Cache cleared by user")

    st.markdown("---")
    st.caption("NSP 2026-27 | Poornima College of Engineering\nFor educational use only.")

# ─────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────
def get_color(cat):
    return {"Low": THEME["green"], "Medium": THEME["yellow"], "High": THEME["red"]}.get(cat, THEME["muted"])

def badge(cat):
    return f'<span class="badge-{cat}">{cat} Risk</span>'

def gauge(score, category):
    color = get_color(category)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=score,
        gauge={
            "axis": {"range":[1,10], "tickcolor": THEME["muted"]},
            "bar":  {"color": color, "thickness": 0.25},
            "bgcolor": THEME["card_bg"], "bordercolor": THEME["border"],
            "steps": [
                {"range":[1,   3.5], "color":"#052e16"},
                {"range":[3.5, 6.5], "color":"#431407"},
                {"range":[6.5, 10],  "color":"#450a0a"},
            ],
            "threshold": {"line":{"color":color,"width":4}, "value":score}
        },
        number={"font":{"size":52,"color":color},"suffix":"/10"},
    ))
    fig.update_layout(height=265, margin=dict(l=30,r=30,t=10,b=10),
                      paper_bgcolor="rgba(0,0,0,0)", font={"color":THEME["text"]})
    return fig

def price_chart(df, t, df2=None, t2=None):
    fig = go.Figure()
    if df2 is not None and not df2.empty:
        n1 = (df["close"]/df["close"].iloc[0])*100
        n2 = (df2["close"]/df2["close"].iloc[0])*100
        fig.add_trace(go.Scatter(x=df.index,  y=n1, name=t,  line=dict(color=THEME["blue"],   width=2.5)))
        fig.add_trace(go.Scatter(x=df2.index, y=n2, name=t2, line=dict(color=THEME["yellow"], width=2.5)))
        fig.update_layout(title="Normalized Price Performance (Base=100)", yaxis_title="Indexed Price")
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["close"], name=t,
            line=dict(color=THEME["blue"], width=2.5),
            fill="tozeroy", fillcolor="rgba(59,130,246,0.07)"))
        fig.update_layout(title=f"{t} — Closing Price", yaxis_title="Price")
    fig.update_layout(xaxis_title="Date", template="plotly_dark", height=360,
                      margin=dict(l=0,r=0,t=40,b=0),
                      plot_bgcolor=THEME["bg"], paper_bgcolor=THEME["bg"])
    return fig

def rsi_chart(df, t):
    rsi = rsi_series(df["close"], period=14)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=rsi, name="RSI",
                             line=dict(color=THEME["purple"], width=2)))
    fig.add_hline(y=70, line_dash="dash", line_color=THEME["red"],
                  annotation_text="Overbought (70)", annotation_font_color=THEME["red"])
    fig.add_hline(y=30, line_dash="dash", line_color=THEME["green"],
                  annotation_text="Oversold (30)",   annotation_font_color=THEME["green"])
    fig.add_hrect(y0=30, y1=70, fillcolor="rgba(148,163,184,0.04)", line_width=0)
    fig.update_layout(title=f"{t} — RSI (14-day)", template="plotly_dark",
                      height=300, yaxis=dict(range=[0,100]),
                      margin=dict(l=0,r=0,t=40,b=0),
                      plot_bgcolor=THEME["bg"], paper_bgcolor=THEME["bg"])
    return fig

def vol_chart(df, t):
    vol = df["log_return"].rolling(30).std()*(252**0.5)*100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=vol, name="Volatility",
        fill="tozeroy", fillcolor="rgba(239,68,68,0.10)",
        line=dict(color=THEME["red"], width=2)))
    fig.update_layout(title=f"{t} — 30-Day Rolling Volatility (%)",
                      template="plotly_dark", height=300,
                      margin=dict(l=0,r=0,t=40,b=0),
                      plot_bgcolor=THEME["bg"], paper_bgcolor=THEME["bg"])
    return fig

METRIC_LABELS = {
    "beta":           "Beta",
    "volatility":     "Volatility (%)",
    "sharpe_ratio":   "Sharpe Ratio",
    "debt_to_equity": "Debt / Equity",
    "pe_ratio":       "P/E Ratio",
    "rsi":            "RSI (14-day)",
}

# ─────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────
def run_pipeline(t, d, gk):
    log.info(f"Pipeline started: {t} | {d} days")
    with st.spinner(f"Fetching data for **{t}**..."):
        raw        = fetch_stock_data(t, d)
        market_raw = fetch_market_index(d)
    if raw["error"]:
        st.error(f"❌ {raw['error']}")
        log.error(f"Pipeline aborted: {raw['error']}")
        return None
    with st.spinner("Computing risk metrics..."):
        clean_df     = clean_history(raw["history"])
        balance_data = clean_balance_sheet(raw["balance"])
        market_idx   = clean_market_index(market_raw, clean_df)
        metrics      = compute_all_metrics(clean_df, balance_data, raw["info"], market_idx)
        score_result = compute_risk_score(metrics)
    with st.spinner("Generating AI summary..."):
        summary = generate_ai_summary(metrics, score_result, t, raw["info"], gk)
    log.info(f"Pipeline complete: {t} → score {score_result['score']}/10")
    return {"clean_df":clean_df, "info":raw["info"],
            "metrics":metrics, "score_result":score_result, "summary":summary}

# ─────────────────────────────────────────────
# PANEL RENDERER
# ─────────────────────────────────────────────
def render_panel(data, t):
    info = data["info"]; metrics = data["metrics"]
    sr = data["score_result"]; df = data["clean_df"]
    score = sr["score"]; category = sr["category"]

    # Company header
    st.markdown(f"### {info.get('longName', t)}  `{t}`")
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Sector",    info.get("sector", "N/A"))
    mc = info.get("marketCap")
    c2.metric("Market Cap", f"₹{mc/1e9:.1f}B" if mc else "N/A")
    c3.metric("52W High",  info.get("fiftyTwoWeekHigh","N/A"))
    c4.metric("52W Low",   info.get("fiftyTwoWeekLow","N/A"))
    st.markdown("---")

    # Score + breakdown
    g1, g2 = st.columns(2)
    with g1:
        st.markdown("#### Risk Score")
        st.plotly_chart(gauge(score, category), use_container_width=True)
        st.markdown(f"<div style='text-align:center'>{badge(category)}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='text-align:center;color:{THEME['muted']};font-size:13px'>"
            f"{sr['available_metrics']}/{sr['total_metrics']} metrics available</p>",
            unsafe_allow_html=True)
    with g2:
        st.markdown("#### Metric Breakdown")
        rows = []
        for key, label in METRIC_LABELS.items():
            rv = metrics.get(key)
            if rv is None:
                display_val = "N/A"
            elif rv == float("inf"):
                display_val = "Negative Equity"
            else:
                display_val = f"{rv:.2f}"
            rows.append({
                "Metric":  label,
                "Value":   display_val,
                "Signal":  get_metric_signal(key, rv),
                "Weight":  f"{sr['breakdown'][key]['weight']*100:.0f}%",
                "Norm Score": f"{sr['breakdown'][key]['normalized']:.2f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True,
                     hide_index=True, height=250)

    st.markdown("---")

    # AI summary
    st.markdown("#### 🤖 AI Risk Summary")
    st.markdown(f'<div class="ai-card">{data["summary"]}</div>', unsafe_allow_html=True)
    st.markdown("---")

    # Charts
    st.markdown("#### 📈 Price & Technical Charts")
    st.plotly_chart(price_chart(df, t), use_container_width=True)
    ch1, ch2 = st.columns(2)
    with ch1: st.plotly_chart(rsi_chart(df, t), use_container_width=True)
    with ch2: st.plotly_chart(vol_chart(df, t), use_container_width=True)

    # Debug expander
    with st.expander("🔧 Debug — Raw Metric Values"):
        st.json({k: (round(v,4) if v is not None else None) for k,v in metrics.items()})
        st.caption(f"Risk Score: {score}/10 | Category: {category} | "
                   f"Metrics computed: {sr['available_metrics']}/6")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
st.markdown("## 📊 FinSight")
st.markdown("**AI-Assisted Stock Risk Analysis and Financial Intelligence Dashboard**")
st.markdown("---")

if not analyze:
    # Welcome screen
    c1, c2, c3 = st.columns(3)
    for col, step, desc in [
        (c1, "Step 1", "Enter a stock ticker in the sidebar<br><br><code>RELIANCE.NS &nbsp; TCS.NS &nbsp; AAPL</code>"),
        (c2, "Step 2", "Select time range and optionally enable two-stock comparison"),
        (c3, "Step 3", "Click <strong>Analyze Risk</strong> for full risk profile + AI summary"),
    ]:
        col.markdown(f'<div class="welcome-card"><h3>{step}</h3><p>{desc}</p></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Metrics Computed")
    st.markdown("""
| Metric | Measures | High Risk Signal | Weight |
|--------|----------|-----------------|--------|
| **Beta** | Market sensitivity | > 1.5 | 20% |
| **Volatility** | Price instability (annualized) | > 30% | 25% |
| **Sharpe Ratio** | Risk-adjusted return | < 0 | 15% |
| **Debt / Equity** | Financial leverage | > 2.0 | 20% |
| **P/E Ratio** | Valuation risk | > 40 | 10% |
| **RSI (14-day)** | Momentum extremes | > 70 or < 30 | 10% |
    """)
    st.markdown("---")
    st.markdown("### System Pipeline")
    st.code("""
User Input (Sidebar)  →  validator.py  — validates all inputs
         ↓
fetcher.py            — yfinance + cache.py (5-min TTL)
         ↓
cleaner.py            — pandas normalization + return calc
         ↓
metrics.py            — Beta, Volatility, Sharpe, D/E, P/E, RSI
         ↓
scorer.py             — weighted composite score 1-10
         ↓
ai_summary.py         — Groq LLaMA-3 or rule-based fallback
         ↓
app.py                — Streamlit dashboard render
         ↓
logger.py             — structured logs → finsight.log
    """, language="text")

else:
    # ── Validation ──
    validation = run_all_validations(
        ticker=ticker, days=days, groq_key=groq_key,
        compare_mode=compare_mode, ticker2=ticker2 or ""
    )

    if not validation["valid"]:
        for err in validation["errors"]:
            st.error(f"❌ {err}")
        st.stop()

    vdata    = validation["data"]
    t1       = vdata.get("ticker", ticker)
    t2       = vdata.get("ticker2", ticker2)
    gk       = vdata.get("groq_key", groq_key)

    # ── Avoid re-running same query (session state) ──
    inputs_changed = (
        st.session_state["last_ticker"]  != t1 or
        st.session_state["last_ticker2"] != t2 or
        st.session_state["last_days"]    != days or
        st.session_state["results"]      is None
    )

    if inputs_changed:
        log_session_start()
        if compare_mode and t2:
            d1 = run_pipeline(t1, days, gk)
            d2 = run_pipeline(t2, days, gk)
            st.session_state["results"] = {"mode":"compare", "d1":d1, "d2":d2}
        else:
            d1 = run_pipeline(t1, days, gk)
            st.session_state["results"] = {"mode":"single", "d1":d1}

        st.session_state["last_ticker"]  = t1
        st.session_state["last_ticker2"] = t2
        st.session_state["last_days"]    = days

    results = st.session_state["results"]

    # ── Render ──
    if results["mode"] == "single":
        if results["d1"]:
            render_panel(results["d1"], t1)

    else:
        d1 = results["d1"]; d2 = results["d2"]
        tab1, tab2, tab3 = st.tabs([f"📊 {t1}", f"📊 {t2}", "⚖️ Side-by-Side"])

        if d1:
            with tab1: render_panel(d1, t1)
        if d2:
            with tab2: render_panel(d2, t2)

        if d1 and d2:
            with tab3:
                st.markdown("### ⚖️ Side-by-Side Comparison")
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.markdown(f"#### {t1}")
                    st.plotly_chart(gauge(d1["score_result"]["score"],
                                         d1["score_result"]["category"]),
                                    use_container_width=True)
                    st.markdown(f"<div style='text-align:center'>{badge(d1['score_result']['category'])}</div>",
                                unsafe_allow_html=True)
                with sc2:
                    st.markdown(f"#### {t2}")
                    st.plotly_chart(gauge(d2["score_result"]["score"],
                                         d2["score_result"]["category"]),
                                    use_container_width=True)
                    st.markdown(f"<div style='text-align:center'>{badge(d2['score_result']['category'])}</div>",
                                unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("#### Metric Comparison")
                rows = []
                def _fmt(v):
                    if v is None:
                        return "N/A"
                    if v == float("inf"):
                        return "Negative Equity"
                    return f"{v:.2f}"

                for key, label in METRIC_LABELS.items():
                    v1 = d1["metrics"].get(key)
                    v2 = d2["metrics"].get(key)
                    rows.append({
                        "Metric":          label,
                        t1:                _fmt(v1),
                        f"{t1} Signal":    get_metric_signal(key, v1),
                        t2:                _fmt(v2),
                        f"{t2} Signal":    get_metric_signal(key, v2),
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("#### Normalized Price Performance")
                st.plotly_chart(price_chart(d1["clean_df"], t1, d2["clean_df"], t2),
                                use_container_width=True)

# Footer
st.markdown("---")
st.markdown(
    f"<p style='text-align:center;color:{THEME['muted']};font-size:13px'>"
    "FinSight | NSP 2026-27 | Poornima College of Engineering | "
    "Python · yfinance · Streamlit · Groq API | Educational use only.</p>",
    unsafe_allow_html=True
)
