"""Approximate Bayesian computation for a few operational parameters.

Each prior draw is the mean of several seeded clinic days. The clock, queues,
and service times stay inside the discrete-event simulator. The language model
is not called. Score prevalence is not in this loss; that comparison is a
separate distribution check.
"""

from __future__ import annotations

from numpy.random import default_rng

from app.calibration.targets import PENETRATION_NOTE, TARGETS
from app.schemas.scenario import ScenarioConfig
from app.simulation.engine import run_simulation

PARAMETERS = (
    ("decline_rate", 0.02, 0.35),
    ("screening_completion_rate", 0.55, 0.99),
    ("referral_uptake", 0.70, 1.0),
    ("screening_duration_mean", 0.8, 6.0),
)


def operational_summary(result: dict) -> dict[str, float]:
    patients = result["patients"]
    offered = [item for item in patients if item["screen_completed"] or item["screen_declined"] or item["screen_incomplete"]]
    completed = [item for item in offered if item["screen_completed"]]
    high = [item for item in completed if (item["screen_score"] or 0) >= 8]
    referred = [item for item in high if item["referral_target"]]
    minutes = [float(item.get("screen_minutes") or 0) for item in completed if item.get("screen_minutes")]
    return {
        "completion": (len(completed) / len(offered)) if offered else 0.0,
        "referral_if_high": (len(referred) / len(high)) if high else 0.0,
        "high_score_share": (len(high) / len(completed)) if completed else 0.0,
        "screen_minutes": (sum(minutes) / len(minutes)) if minutes else 0.0,
    }


def distance(summary: dict[str, float]) -> float:
    total = 0.0
    for target in TARGETS:
        scale = target.tolerance if target.tolerance else 1.0
        total += abs(summary.get(target.id, 0.0) - target.value) / scale
    return total / len(TARGETS)


def _day(scenario: ScenarioConfig, seed: int, n_patients: int) -> dict:
    probe = scenario.model_copy(
        update={
            "seed": seed,
            "n_patients": n_patients,
            "use_llm": False,
            "screening_enabled": True,
            "referral_mode": "automatic",
            "name": "Calibration probe",
        }
    )
    return run_simulation(probe, trace=False)


def _average(summaries: list[dict[str, float]]) -> dict[str, float]:
    keys = summaries[0].keys()
    return {key: sum(item[key] for item in summaries) / len(summaries) for key in keys}


def calibrate(
    scenario: ScenarioConfig,
    draws: int = 80,
    n_patients: int = 20,
    seed: int = 17,
    replicates: int = 3,
) -> dict:
    """Rejection ABC. Each draw is the mean of several days. Keep the closest fifth."""
    rng = default_rng(seed)
    rows = []
    for index in range(draws):
        proposal = {}
        for name, lo, hi in PARAMETERS:
            proposal[name] = float(rng.uniform(lo, hi))
        probe = scenario.model_copy(update=proposal)
        summaries = [
            operational_summary(_day(probe, seed + index * 17 + rep * 10007, n_patients))
            for rep in range(replicates)
        ]
        summary = _average(summaries)
        rows.append({"parameters": proposal, "summary": summary, "distance": distance(summary)})
    rows.sort(key=lambda item: item["distance"])
    kept = rows[: max(4, draws // 5)]
    posterior = {}
    for name, _lo, _hi in PARAMETERS:
        samples = sorted(item["parameters"][name] for item in kept)
        mid = samples[len(samples) // 2]
        posterior[name] = {
            "median": round(mid, 3),
            "low": round(samples[0], 3),
            "high": round(samples[-1], 3),
        }
    suggested = {name: posterior[name]["median"] for name, *_rest in PARAMETERS}
    best = rows[0]
    return {
        "method": (
            f"Rejection ABC. {draws} prior draws, each the mean of {replicates} seeded days "
            f"with {n_patients} families. The closest fifth is the reported posterior."
        ),
        "draws": draws,
        "replicates": replicates,
        "n_patients": n_patients,
        "kept": len(kept),
        "targets": [
            {"id": item.id, "label": item.label, "value": item.value, "tolerance": item.tolerance, "source": item.source}
            for item in TARGETS
        ],
        "penetration_note": PENETRATION_NOTE,
        "best_distance": round(best["distance"], 3),
        "best_summary": {key: round(value, 3) for key, value in best["summary"].items()},
        "posterior": posterior,
        "suggested": suggested,
        "disclaimer": "The loss is completion, referral of high scores, and screen minutes. The score distribution is a separate check.",
    }
