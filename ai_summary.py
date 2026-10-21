# ============================================================
# ai_summary.py — FinSight AI Summary Generator
# Uses Groq API (LLaMA-3). Falls back to rule-based if no key.
# ============================================================
from groq import Groq
from logger import get_logger
from config import GROQ_MODEL, GROQ_TOKENS, GROQ_TEMP

log = get_logger(__name__)

def generate_ai_summary(metrics, score_result, ticker, stock_info, groq_api_key):
    if not groq_api_key or not groq_api_key.strip():
        log.info("No Groq key — using rule-based fallback summary")
        return _fallback_summary(metrics, score_result, ticker)
    try:
        client       = Groq(api_key=groq_api_key.strip())
        company_name = stock_info.get("longName", ticker)
        sector       = stock_info.get("sector", "Unknown Sector")
        score        = score_result.get("score", "N/A")
        category     = score_result.get("category", "Unknown")

        prompt = f"""You are a financial analyst assistant. Based on the following computed financial risk metrics for {company_name} ({ticker}), write a concise 4-5 sentence plain English risk summary for a retail investor with no financial background.

Company: {company_name} | Sector: {sector}
Risk Score: {score}/10 ({category} Risk)

Metrics:
- Beta: {metrics.get('beta', 'N/A')} (>1 = more volatile than market)
- 30-day Volatility: {metrics.get('volatility', 'N/A')}%
- Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')} (higher is better)
- Debt-to-Equity: {metrics.get('debt_to_equity', 'N/A')} (lower is safer)
- P/E Ratio: {metrics.get('pe_ratio', 'N/A')}
- RSI (14-day): {metrics.get('rsi', 'N/A')} (>70 overbought, <30 oversold)

Instructions: Write in simple, clear language. No jargon. No bullet points. No headers. Flowing paragraph only. Mention the risk score meaning, highlight 2-3 key metric observations, end with who this stock suits."""

        log.info(f"Calling Groq API for {ticker}")
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=GROQ_TOKENS,
            temperature=GROQ_TEMP
        )
        summary = response.choices[0].message.content.strip()
        log.info(f"Groq summary generated for {ticker}")
        return summary

    except Exception as e:
        log.error(f"Groq API failed for {ticker}: {e}")
        return _fallback_summary(metrics, score_result, ticker) + f"\n\n*(AI summary unavailable: {e})*"

def _fallback_summary(metrics, score_result, ticker):
    score    = score_result.get("score", 5.0)
    category = score_result.get("category", "Medium")
    beta     = metrics.get("beta")
    vol      = metrics.get("volatility")
    sharpe   = metrics.get("sharpe_ratio")
    de       = metrics.get("debt_to_equity")
    rsi      = metrics.get("rsi")
    lines    = [f"{ticker} has a risk score of {score}/10, placing it in the {category} risk category."]
    if beta is not None:
        lines.append("Beta of {:.2f} indicates {} market sensitivity.".format(beta,
            "low" if beta < 0.8 else "moderate" if beta <= 1.2 else "high"))
    if vol is not None:
        lines.append("Annualized volatility of {:.1f}% is {}.".format(vol,
            "stable" if vol < 15 else "moderate" if vol < 30 else "elevated"))
    if sharpe is not None:
        lines.append("Sharpe Ratio of {:.2f} reflects {} risk-adjusted returns.".format(sharpe,
            "strong" if sharpe >= 1.5 else "modest" if sharpe >= 0 else "poor"))
    if rsi is not None:
        lines.append("RSI of {:.1f} signals {}.".format(rsi,
            "overbought conditions" if rsi > 70 else "oversold conditions" if rsi < 30 else "neutral momentum"))
    lines.append({"Low": "Suitable for conservative, long-term investors.",
                  "Medium": "May suit moderate-risk investors comfortable with some variability.",
                  "High": "Better suited for experienced investors with high risk tolerance."}.get(category, ""))
    return " ".join(lines)
