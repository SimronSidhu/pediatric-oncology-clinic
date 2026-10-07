"""Grid search for a small staffing plan that meets clinic constraints."""

from __future__ import annotations

from app.analytics.experiments import monte_carlo
from app.schemas.scenario import ScenarioConfig


def _violations(summary: dict) -> list[str]:
    problems = []
    wait = summary["mean_wait"]["mean"]
    if wait > 30:
        problems.append(f"average wait {wait:.1f} min is above 30")
    need = max(0.01, summary["families_with_need"]["mean"])
    missed_rate = summary["missed"]["mean"] / need
    unserved_rate = summary["unserved"]["mean"] / need
    if missed_rate > 0.05 and unserved_rate > 0.05:
        problems.append(
            f"high-need families still unsupported (missed {missed_rate:.0%}, referred-but-not-seen {unserved_rate:.0%})"
        )
    for key, label in (
        ("nurse_utilization", "nursing"),
        ("onc_utilization", "oncology"),
        ("sw_utilization", "social work"),
        ("psych_utilization", "psychology"),
    ):
        util = summary[key]["mean"]
        if util > 0.9:
            problems.append(f"{label} utilization {util:.0%} is above 90%")
    return problems


def optimize_staffing(scenario: ScenarioConfig, replicates: int = 6) -> dict:
    replicates = max(4, min(20, replicates))
    current = {
        "nurses": scenario.n_nurses,
        "social_workers": scenario.n_social_workers,
        "psychologists": scenario.n_psychologists,
        "child_life": scenario.n_child_life,
    }
    trials = []
    feasible = []
    for nurses in (max(2, scenario.n_nurses - 1), scenario.n_nurses, scenario.n_nurses + 1):
        for social_workers in (1, 2, 3):
            for psychologists in (1, 2):
                candidate = scenario.model_copy(
                    update={
                        "n_nurses": nurses,
                        "n_social_workers": social_workers,
                        "n_psychologists": psychologists,
                        "name": f"{nurses}N / {social_workers}SW / {psychologists}PS",
                    }
                )
                report = monte_carlo(candidate, runs=replicates, seed=scenario.seed)
                summary = report["summary"]
                problems = _violations(summary)
                cost = nurses + 2.0 * social_workers + 2.0 * psychologists + scenario.n_child_life
                row = {
                    "nurses": nurses,
                    "social_workers": social_workers,
                    "psychologists": psychologists,
                    "child_life": scenario.n_child_life,
                    "cost": cost,
                    "feasible": not problems,
                    "problems": problems,
                    "mean_wait": summary["mean_wait"]["mean"],
                    "missed": summary["missed"]["mean"],
                    "unserved": summary["unserved"]["mean"],
                    "with_need": summary["families_with_need"]["mean"],
                    "sw_utilization": summary["sw_utilization"]["mean"],
                    "nurse_utilization": summary["nurse_utilization"]["mean"],
                    "mean_psych_wait": summary["mean_psych_wait"]["mean"],
                    "supported": summary["supported"]["mean"],
                }
                trials.append(row)
                if row["feasible"]:
                    feasible.append(row)
    trials.sort(key=lambda item: (not item["feasible"], item["cost"], item["mean_wait"]))
    if feasible:
        recommended = min(feasible, key=lambda item: (item["cost"], item["mean_wait"]))
        note = "Smallest weighted staffing plan that met the wait, support, and utilization constraints on these replicates."
    else:
        recommended = min(trials, key=lambda item: (len(item["problems"]), item["cost"], item["mean_wait"]))
        note = (
            "No configuration met every constraint. The closest plan is shown. "
            "Families who decline screening or are never referred cannot be recovered by staffing alone."
        )
    return {
        "objective": "Minimize nurses + 2·social workers + 2·psychologists, subject to mean wait under 30 min, high-need families either identified and seen or under a 5% gap, and role utilization under 90%.",
        "replicates": replicates,
        "current": current,
        "recommended": recommended,
        "note": note,
        "trials": trials[:12],
        "disclaimer": "Grid search on this synthetic day. Do not use it to staff a real clinic.",
    }
