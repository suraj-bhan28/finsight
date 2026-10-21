# ============================================================
# scorer.py — FinSight Risk Scorer
# ============================================================
import numpy as np
from logger import get_logger
from config import METRIC_WEIGHTS, NORM_RANGES, RISK_THRESHOLDS, SIGNAL_THRESHOLDS

log = get_logger(__name__)

def normalize_metric(value, metric_name):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        log.debug(f"Metric {metric_name} missing — neutral score 0.5")
        return 0.5
    cfg    = NORM_RANGES[metric_name]
    low, high, invert = cfg["min"], cfg["max"], cfg["invert"]
    clamped    = max(low, min(high, value))
    normalized = (clamped - low) / (high - low)
    if metric_name == "rsi":
        if value >= 70:
            normalized = min(1.0, (value - 70) / 30) * 0.8 + 0.2
        elif value <= 30:
            normalized = min(1.0, (30 - value) / 30) * 0.5
        else:
            normalized = 0.1
    if invert:
        normalized = 1 - normalized
    return round(normalized, 4)

def compute_risk_score(metrics):
    log.info("Computing composite risk score")
    breakdown      = {}
    weighted_sum   = 0.0
    total_weight   = 0.0

    for metric, weight in METRIC_WEIGHTS.items():
        raw        = metrics.get(metric)
        norm       = normalize_metric(raw, metric)
        contrib    = norm * weight
        breakdown[metric] = {
            "raw": raw, "normalized": norm,
            "weight": weight, "contribution": round(contrib, 4)
        }
        weighted_sum += contrib
        total_weight += weight

    raw_score   = weighted_sum / total_weight if total_weight > 0 else 0.5
    final_score = round(max(1.0, min(10.0, 1 + raw_score * 9)), 2)

    if final_score <= RISK_THRESHOLDS["low"]:
        category, color = "Low",    "#22c55e"
    elif final_score <= RISK_THRESHOLDS["medium"]:
        category, color = "Medium", "#f59e0b"
    else:
        category, color = "High",   "#ef4444"

    available = sum(1 for v in metrics.values() if v is not None)
    log.info(f"Risk score: {final_score}/10 — {category} ({available}/6 metrics)")
    return {
        "score": final_score, "category": category, "color": color,
        "breakdown": breakdown, "available_metrics": available, "total_metrics": len(METRIC_WEIGHTS)
    }

def get_metric_signal(metric_name, raw_value):
    if raw_value is None:
        return "N/A"
    thresholds = SIGNAL_THRESHOLDS.get(metric_name, [])
    for threshold, label in thresholds:
        if raw_value <= threshold:
            return label
    return "N/A"
