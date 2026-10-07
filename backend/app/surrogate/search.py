"""Gaussian-process stand-in for the clinic day, then Bayesian optimization.

The simulator is the source of truth. The Gaussian process only proposes the
next screening policy so the search does not call the simulator for every
candidate.
"""

from __future__ import annotations

import numpy as np
from numpy.random import default_rng
from scipy.stats import norm
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, Matern, WhiteKernel

from app.schemas.scenario import ScenarioConfig
from app.simulation.engine import run_simulation

# screening on/off, referral threshold, social workers, nurses
GRID = [
    (screen, threshold, social, nurses)
    for screen in (0, 1)
    for threshold in (1, 2, 3, 4, 5, 6, 7, 8, 9)
    for social in (1, 2, 3, 4)
    for nurses in (2, 3, 4, 5, 6)
]


def utility(metrics: dict, social: int, nurses: int) -> float:
    need = max(1, int(metrics["families_with_need"]))
    return (
        float(metrics["supported"]) / need
        - 1.25 * float(metrics["missed"]) / need
        - float(metrics["mean_psych_wait"]) / 80.0
        - 0.04 * social
        - 0.02 * nurses
    )


def _evaluate(scenario: ScenarioConfig, point: tuple[int, int, int, int], seed: int, n_patients: int, replicates: int) -> float:
    screen, threshold, social, nurses = point
    values = []
    for rep in range(replicates):
        probe = scenario.model_copy(
            update={
                "seed": seed + rep * 10007,
                "n_patients": n_patients,
                "use_llm": False,
                "screening_enabled": bool(screen),
                "referral_threshold": threshold,
                "n_social_workers": social,
                "n_nurses": nurses,
                "referral_mode": "automatic",
                "predictive_mode": "off",
            }
        )
        result = run_simulation(probe, trace=False)
        values.append(utility(result["metrics"], social, nurses))
    return float(sum(values) / len(values))


def _encode(points: list[tuple[int, int, int, int]]) -> np.ndarray:
    raw = np.asarray(points, dtype=float)
    lo = np.array([0, 1, 1, 2], dtype=float)
    hi = np.array([1, 9, 4, 6], dtype=float)
    return (raw - lo) / (hi - lo)


def _improvement(mu: np.ndarray, sigma: np.ndarray, best: float) -> np.ndarray:
    sigma = np.maximum(sigma, 1e-6)
    gap = mu - best
    z = gap / sigma
    return gap * norm.cdf(z) + sigma * norm.pdf(z)


def search(
    scenario: ScenarioConfig,
    initial: int = 24,
    steps: int = 16,
    n_patients: int = 20,
    seed: int = 17,
    replicates: int = 2,
) -> dict:
    rng = default_rng(seed)
    order = list(range(len(GRID)))
    rng.shuffle(order)
    chosen = [GRID[index] for index in order[:initial]]
    observed = [
        _evaluate(scenario, point, seed + index * 17, n_patients, replicates) for index, point in enumerate(chosen)
    ]
    trace = [{"point": _label(point), "utility": round(value, 3), "source": "initial"} for point, value in zip(chosen, observed)]

    kernel = ConstantKernel(1.0, (0.1, 10.0)) * Matern(length_scale=0.4, nu=2.5) + WhiteKernel(1e-3)
    for step in range(steps):
        model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=seed)
        model.fit(_encode(chosen), np.asarray(observed))
        remaining = [point for point in GRID if point not in chosen]
        mu, sigma = model.predict(_encode(remaining), return_std=True)
        scores = _improvement(mu, sigma, max(observed))
        pick = remaining[int(np.argmax(scores))]
        value = _evaluate(scenario, pick, seed + 100 + step * 17, n_patients, replicates)
        chosen.append(pick)
        observed.append(value)
        trace.append({"point": _label(pick), "utility": round(float(value), 3), "source": "expected improvement"})

    best_index = int(np.argmax(observed))
    best = chosen[best_index]
    return {
        "method": (
            f"Gaussian process with a Matern kernel. Expected improvement picks the next policy "
            f"from {len(GRID)} candidates. Each reported utility is the mean of {replicates} seeded days."
        ),
        "evaluations": len(chosen),
        "candidates": len(GRID),
        "n_patients": n_patients,
        "replicates": replicates,
        "objective": "Supported families, minus missed families, psychosocial wait, and extra nurses or social workers.",
        "best": {
            "screening_enabled": bool(best[0]),
            "referral_threshold": best[1],
            "n_social_workers": best[2],
            "n_nurses": best[3],
            "utility": round(float(observed[best_index]), 3),
        },
        "trace": trace,
        "disclaimer": "The Gaussian process only picks the next policy. The utility shown is from the simulator.",
    }


def _label(point: tuple[int, int, int, int]) -> str:
    screen, threshold, social, nurses = point
    mode = "screening on" if screen else "screening off"
    return f"{mode}, cutoff {threshold}, {social} social workers, {nurses} nurses"
