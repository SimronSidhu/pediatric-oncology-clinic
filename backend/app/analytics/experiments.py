"""Monte Carlo summaries and side-by-side scenario runs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.scenario import ScenarioConfig
from app.simulation.engine import run_simulation

SUMMARY_KEYS = [
    "mean_wait",
    "median_wait",
    "max_wait",
    "mean_psych_wait",
    "mean_cycle",
    "families_with_need",
    "identified",
    "missed",
    "supported",
    "unserved",
    "referrals",
    "referrals_completed",
    "left_before_psych",
    "screened",
    "declined",
    "false_positive_referrals",
    "detection_rate",
    "missed_rate",
    "support_rate",
    "alerts",
    "overtime",
    "mean_staff_stress",
    "throughput",
]


def compare_scenarios(scenarios: list[ScenarioConfig], trace: bool = False) -> list[dict]:
    results = []
    for scenario in scenarios:
        result = run_simulation(scenario.model_copy(update={"use_llm": False}), trace=trace)
        results.append(
            {
                "name": scenario.name,
                "seed": scenario.seed,
                "metrics": result["metrics"],
                "bottleneck": result["bottleneck"],
                "funnel": result["funnel"],
                "scenario": scenario.model_dump(),
            }
        )
    return results


def _summarize(series: pd.Series) -> dict:
    values = series.astype(float)
    n = int(values.shape[0])
    mu = float(values.mean()) if n else 0.0
    sd = float(values.std(ddof=1)) if n > 1 else 0.0
    half = 1.96 * sd / np.sqrt(n) if n > 1 else 0.0
    return {
        "n": n,
        "mean": round(mu, 3),
        "median": round(float(values.median()) if n else 0.0, 3),
        "std": round(sd, 3),
        "ci95": [round(mu - half, 3), round(mu + half, 3)],
    }


def monte_carlo(scenario: ScenarioConfig, runs: int, seed: int | None = None) -> dict:
    runs = max(2, min(500, int(runs)))
    origin = scenario.seed if seed is None else seed
    rows = []
    for i in range(runs):
        day = scenario.model_copy(update={"seed": origin + i * 17, "use_llm": False})
        metrics = run_simulation(day, trace=False)["metrics"]
        row = {key: metrics.get(key, 0) for key in SUMMARY_KEYS}
        row["sw_utilization"] = metrics["utilization"].get("social_work", 0)
        row["nurse_utilization"] = metrics["utilization"].get("nurse", 0)
        row["onc_utilization"] = metrics["utilization"].get("oncologist", 0)
        row["psych_utilization"] = metrics["utilization"].get("psychology", 0)
        rows.append(row)
    frame = pd.DataFrame(rows)
    summary = {column: _summarize(frame[column]) for column in frame.columns}
    histograms = {}
    for column in ("mean_wait", "missed", "mean_psych_wait", "sw_utilization", "detection_rate"):
        counts, edges = np.histogram(frame[column].astype(float), bins=min(12, max(4, runs // 3)))
        histograms[column] = {
            "counts": [int(c) for c in counts],
            "edges": [round(float(e), 3) for e in edges],
        }
    return {
        "scenario": scenario.model_dump(),
        "runs": runs,
        "origin_seed": origin,
        "summary": summary,
        "histograms": histograms,
    }
