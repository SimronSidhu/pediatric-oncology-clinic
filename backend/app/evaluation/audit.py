"""Compare simulated scores with a published distribution, and audit paired personas.

The persona contrast holds the clinical facts fixed and changes only language
access. The rule does not use language. A shift, if one appears, is a property
of the model calls. It is not a claim about real families.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from scipy.stats import norm

from app.schemas.scenario import ScenarioConfig
from app.services.decisions import LLMDecisionEngine, RuleBasedDecisionEngine, screening_decline_probability
from app.simulation.engine import run_simulation

REFERENCE_MEAN = 5.07
REFERENCE_SD = 2.78
SHARE_AT_LEAST_4 = 0.679
SHARE_AT_LEAST_8 = 0.169
MEAN_SOURCE = (
    "Parents of children with cancer, Distress Thermometer for Parents: mean 5.07, SD 2.78, "
    "and 67.9% scored 4 or higher."
)
TAIL_SOURCE = "Electronic caregiver screening: 16.9% of caregivers ever scored 8 or higher."

CONTEXTS = (
    {"score": 2, "stress": 30, "privacy_concern": 0.2, "queue": 0, "age": 5, "decline_roll": 0.2, "disclosure_roll": 0.5},
    {"score": 4, "stress": 48, "privacy_concern": 0.3, "queue": 1, "age": 7, "decline_roll": 0.15, "disclosure_roll": 0.4},
    {"score": 5, "stress": 60, "privacy_concern": 0.4, "queue": 2, "age": 9, "decline_roll": 0.12, "disclosure_roll": 0.18},
    {"score": 6, "stress": 70, "privacy_concern": 0.45, "queue": 1, "age": 11, "decline_roll": 0.08, "disclosure_roll": 0.7},
    {"score": 7, "stress": 58, "privacy_concern": 0.35, "queue": 3, "age": 8, "decline_roll": 0.25, "disclosure_roll": 0.12},
    {"score": 8, "stress": 80, "privacy_concern": 0.7, "queue": 4, "age": 14, "decline_roll": 0.05, "disclosure_roll": 0.05},
    {"score": 9, "stress": 42, "privacy_concern": 0.25, "queue": 0, "age": 6, "decline_roll": 0.3, "disclosure_roll": 0.9},
    {"score": 3, "stress": 88, "privacy_concern": 0.55, "queue": 2, "age": 16, "decline_roll": 0.04, "disclosure_roll": 0.15},
)


def _reference_bins() -> list[float]:
    dist = norm(REFERENCE_MEAN, REFERENCE_SD)
    cuts = [-np.inf, *[index + 0.5 for index in range(10)], np.inf]
    return [float(dist.cdf(cuts[index + 1]) - dist.cdf(cuts[index])) for index in range(11)]


def distress_fit(scenario: ScenarioConfig, n_patients: int = 120) -> dict:
    probe = scenario.model_copy(
        update={
            "n_patients": n_patients,
            "seed": scenario.seed,
            "use_llm": False,
            "screening_enabled": True,
            "referral_mode": "automatic",
        }
    )
    result = run_simulation(probe, trace=False)
    scores = [
        int(item["screen_score"])
        for item in result["patients"]
        if item["screen_completed"] and item["screen_score"] is not None
    ]
    reference = _reference_bins()
    counts = [0] * 11
    for score in scores:
        counts[min(10, max(0, score))] += 1
    total = len(scores) or 1
    observed = [count / total for count in counts]
    variation = 0.5 * sum(abs(left - right) for left, right in zip(observed, reference))
    observed_cdf = np.cumsum(observed)
    reference_cdf = np.cumsum(reference)
    ks = float(np.max(np.abs(observed_cdf - reference_cdf))) if scores else 1.0
    mean = float(np.mean(scores)) if scores else 0.0
    sd = float(np.std(scores)) if len(scores) > 1 else 0.0
    share4 = sum(score >= 4 for score in scores) / total if scores else 0.0
    share8 = sum(score >= 8 for score in scores) / total if scores else 0.0
    return {
        "n_completed": len(scores),
        "mean_score": round(mean, 2),
        "sd_score": round(sd, 2),
        "reference_mean": REFERENCE_MEAN,
        "reference_sd": REFERENCE_SD,
        "share_at_least_4": round(share4, 3),
        "benchmark_at_least_4": SHARE_AT_LEAST_4,
        "share_at_least_8": round(share8, 3),
        "benchmark_at_least_8": SHARE_AT_LEAST_8,
        "total_variation": round(variation, 3),
        "ks_statistic": round(ks, 3),
        "bins": [
            {"score": index, "observed": round(observed[index], 3), "reference": round(reference[index], 3)}
            for index in range(11)
        ],
        "mean_source": MEAN_SOURCE,
        "tail_source": TAIL_SOURCE,
        "note": (
            "The reference bins are a 0–10 discretization of the published mean and SD, "
            "plus the published shares at 4 and at 8. The demo day is enriched for distress, so a gap here is expected."
        ),
    }


def _agent(context: dict, language: str, interpreter: bool) -> dict:
    return {
        "language": language,
        "interpreter_needed": interpreter,
        "language_support": interpreter,
        "age": context["age"],
        "score": context["score"],
        "latent_distress": context["score"],
        "stress": context["stress"],
        "privacy_concern": context["privacy_concern"],
        "prior_screening_experience": "none",
        "threshold": 4,
        "anxiety": 0.4,
        "decline_roll": context["decline_roll"],
        "disclosure_roll": context["disclosure_roll"],
        "monitor_roll": 0.5,
    }


def _rule_row(agent: dict, queue: int) -> dict:
    rules = RuleBasedDecisionEngine()
    decline_p = screening_decline_probability(
        base=0.10,
        language_support=bool(agent["language_support"]),
        stress=float(agent["stress"]),
        privacy_concern=float(agent["privacy_concern"]),
        prior_experience=str(agent["prior_screening_experience"]),
    )
    screening = rules.decide(
        {**agent, "decision": "screening", "decline_probability": decline_p},
        {"wait_so_far": 4, "queues": {"social_work": queue}},
    )
    disclosure = rules.decide({**agent, "decision": "disclosure"}, {})
    nurse = rules.decide({**agent, "decision": "nurse"}, {"queues": {"social_work": queue}})
    return {
        "decline_probability": round(decline_p, 3),
        "screening": "accept" if screening["accept"] else "decline",
        "disclosure": disclosure["level"],
        "nurse": nurse["action"],
    }


def _llm_row(agent: dict, queue: int) -> dict | None:
    engine = LLMDecisionEngine()
    visible = {key: value for key, value in agent.items() if not str(key).endswith("_roll") and key != "decline_probability"}
    try:
        screening = engine.decide(
            {**visible, "decision": "screening"},
            {"wait_so_far": 4, "queues": {"social_work": queue}},
        )
        disclosure = engine.decide({**visible, "decision": "disclosure"}, {"queues": {"social_work": queue}})
        nurse = engine.decide({**visible, "decision": "nurse"}, {"queues": {"social_work": queue}})
    except Exception:
        return None
    if "accept" not in screening or "level" not in disclosure or "action" not in nurse:
        return None
    return {
        "screening": "accept" if screening["accept"] else "decline",
        "disclosure": disclosure["level"],
        "nurse": nurse["action"],
    }


def _rate(rows: list[dict], side: str, field: str, value: str) -> float | None:
    picked = [row[side] for row in rows if row[side] is not None]
    if not picked or any(item is None for item in picked):
        return None
    return round(sum(item[field] == value for item in picked) / len(picked), 3)


def persona_audit(use_model: bool = True, pairs: int = 8) -> dict:
    contexts = CONTEXTS[:pairs]
    rows = []
    for index, context in enumerate(contexts):
        english = _agent(context, "English", False)
        punjabi = _agent(context, "Punjabi", True)
        rows.append(
            {
                "id": f"pair-{index + 1}",
                "score": context["score"],
                "queue": context["queue"],
                "english_rules": _rule_row(english, context["queue"]),
                "punjabi_rules": _rule_row(punjabi, context["queue"]),
                "english_model": None,
                "punjabi_model": None,
                "_english_agent": english,
                "_punjabi_agent": punjabi,
            }
        )
    if use_model:
        jobs = []
        for row in rows:
            jobs.append((row, "english_model", row["_english_agent"]))
            jobs.append((row, "punjabi_model", row["_punjabi_agent"]))

        def _run(job):
            row, key, agent = job
            return row, key, _llm_row(agent, row["queue"])

        with ThreadPoolExecutor(max_workers=8) as pool:
            for row, key, result in pool.map(_run, jobs):
                row[key] = result
    for row in rows:
        row.pop("_english_agent", None)
        row.pop("_punjabi_agent", None)

    rule_gap = any(row["english_rules"] != row["punjabi_rules"] for row in rows)
    model_ready = all(row["english_model"] and row["punjabi_model"] for row in rows)
    model_gap = None
    if model_ready:
        model_gap = any(row["english_model"] != row["punjabi_model"] for row in rows)
    screening_shift = None
    if model_ready:
        english_accept = _rate(rows, "english_model", "screening", "accept")
        punjabi_accept = _rate(rows, "punjabi_model", "screening", "accept")
        if english_accept is not None and punjabi_accept is not None:
            screening_shift = round(english_accept - punjabi_accept, 3)
    return {
        "n_pairs": len(rows),
        "design": (
            f"{len(rows)} matched pairs. Age, score, stress, privacy, and queue are copied. "
            "The only changed fields are language and whether a Punjabi interpreter is needed. "
            "The rule does not use those fields."
        ),
        "rows": rows,
        "rule_outcomes_differ": rule_gap,
        "model_outcomes_differ": model_gap,
        "model_screening_gap": screening_shift,
        "english_accept_rate": _rate(rows, "english_model", "screening", "accept") if use_model else None,
        "punjabi_accept_rate": _rate(rows, "punjabi_model", "screening", "accept") if use_model else None,
        "reading": (
            "Any difference is from this procedure. It is not a finding about real parents. "
            "The rules ignore language. If they differ, that is a bug. "
            "A model gap means the structured answer changed when only interpreter need changed."
        ),
    }
