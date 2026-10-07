"""Outcome metrics, flow diagrams, and bottleneck rules."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, median

from app.agents.base import PatientAgent, StaffAgent
from app.schemas.scenario import ScenarioConfig

ROLE_LABELS = {
    "nurse": "Nursing",
    "oncologist": "Oncology",
    "social_work": "Social Work",
    "psychology": "Psychology",
    "child_life": "Child Life",
    "admin": "Reception",
    "coordinator": "Coordination",
}

STAFF_TO_POOL = {
    "nurse": "nurse",
    "oncologist": "oncologist",
    "social_worker": "social_work",
    "psychologist": "psychology",
    "child_life": "child_life",
    "admin": "admin",
    "coordinator": "coordinator",
}


def _safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _safe_median(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def compute_metrics(
    patients: list[PatientAgent],
    staff: list[StaffAgent],
    scenario: ScenarioConfig,
    peaks: dict[str, int],
    role_waits: dict[str, list[float]],
    alerts: int,
    above_80_minutes: float,
    observed_until: float,
) -> dict:
    discharged = [p for p in patients if p.discharge_time is not None]
    waits = [p.admin_wait + p.nurse_wait + p.onc_wait for p in discharged]
    psych_waits = [p.psych_wait for p in discharged if p.referral_target]
    cycles = [p.cycle_time for p in discharged]
    with_need = [p for p in patients if p.high_need]
    identified = [p for p in with_need if p.identified]
    missed = [p for p in with_need if p.missed]
    supported = [p for p in with_need if p.received_support]
    unserved = [p for p in with_need if p.identified and not p.received_support]
    screened = [p for p in patients if p.screen_completed]
    high_screened = [p for p in with_need if p.screen_completed]
    true_positive = [
        p for p in high_screened if p.screen_score is not None and p.screen_score >= scenario.referral_threshold
    ]
    referrals = [p for p in patients if p.referral_target]
    false_pos = [p for p in referrals if not p.high_need]
    on_duty = [s for s in staff if s.on_duty and s.role != "coordinator"]
    open_minutes = max(1.0, scenario.close_minutes())
    utilization = {}
    session_utilization = {}
    for staff_role, role in STAFF_TO_POOL.items():
        if role == "coordinator":
            continue
        group = [s for s in staff if s.role == staff_role and s.on_duty]
        if not group:
            utilization[role] = 0.0
            session_utilization[role] = 0.0
            continue
        busy = sum(s.busy_minutes for s in group)
        utilization[role] = round(min(1.5, busy / (open_minutes * len(group))), 3)
        spans = [
            float(s.last_busy) - float(s.first_busy)
            for s in group
            if getattr(s, "first_busy", None) is not None and getattr(s, "last_busy", None)
            and float(s.last_busy) > float(s.first_busy)
        ]
        session_utilization[role] = round(min(1.0, busy / sum(spans)), 3) if spans and busy else 0.0

    stresses = [s.stress for s in staff if s.on_duty]
    overtime = sum(s.overtime_minutes for s in staff)
    last_out = max((p.discharge_time or 0) for p in patients) if patients else 0
    need_n = len(with_need)
    mean_role_wait = {
        role: round(_safe_mean(values), 1) for role, values in role_waits.items()
    }
    return {
        "families_with_need": need_n,
        "identified": len(identified),
        "missed": len(missed),
        "detected": sum(1 for p in with_need if p.detected),
        "supported": len(supported),
        "unserved": len(unserved),
        "screened": len(screened),
        "offered": sum(1 for p in patients if p.screen_offered),
        "declined": sum(1 for p in patients if p.screen_declined),
        "incomplete": sum(1 for p in patients if p.screen_incomplete),
        "referrals": len(referrals),
        "referrals_completed": sum(1 for p in patients if p.referral_completed),
        "referrals_deferred": sum(1 for p in patients if p.referral_deferred or p.left_before_psych),
        "left_before_psych": sum(1 for p in patients if p.left_before_psych),
        "high_distress_supported": len(supported),
        "high_distress_missed": len(missed),
        "false_positive_referrals": len(false_pos),
        "false_positive_share": round(len(false_pos) / len(referrals), 3) if referrals else 0.0,
        "sensitivity": round(len(true_positive) / len(high_screened), 3) if high_screened else 0.0,
        "detection_rate": round(len(identified) / need_n, 3) if need_n else 0.0,
        "missed_rate": round(len(missed) / need_n, 3) if need_n else 0.0,
        "support_rate": round(len(supported) / need_n, 3) if need_n else 0.0,
        "mean_wait": round(_safe_mean(waits), 1),
        "median_wait": round(_safe_median(waits), 1),
        "max_wait": round(max(waits), 1) if waits else 0.0,
        "mean_psych_wait": round(_safe_mean(psych_waits), 1),
        "max_psych_wait": round(max(psych_waits), 1) if psych_waits else 0.0,
        "mean_cycle": round(_safe_mean(cycles), 1),
        "max_cycle": round(max(cycles), 1) if cycles else 0.0,
        "throughput": len(discharged),
        "alerts": alerts,
        "overtime": round(overtime, 1),
        "mean_staff_stress": round(_safe_mean(stresses), 1),
        "max_staff_stress": round(max(stresses), 1) if stresses else 0.0,
        "max_queue": {role: int(peaks.get(role, 0)) for role in ROLE_LABELS},
        "utilization": utilization,
        "session_utilization": session_utilization,
        "mean_role_wait": mean_role_wait,
        "above_80_share": round(above_80_minutes / max(1.0, min(observed_until, open_minutes)), 3),
        "clinic_duration": round(max(last_out, scenario.close_minutes()), 1),
        "waits": [round(w, 1) for w in waits],
        "psych_waits": [round(w, 1) for w in psych_waits],
        "on_duty_staff": len(on_duty),
    }


def sankey_from_paths(paths: list[list[str]]) -> dict:
    nodes = [
        "Arrival",
        "Check-in",
        "Nurse",
        "Oncology",
        "Treatment",
        "Psychosocial",
        "Exit",
        "Left early",
    ]
    index = {name: i for i, name in enumerate(nodes)}
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for path in paths:
        cleaned = [step for step in path if step in index]
        for a, b in zip(cleaned, cleaned[1:]):
            if a != b:
                counts[(a, b)] += 1
    links = [
        {"source": index[a], "target": index[b], "value": value}
        for (a, b), value in counts.items()
        if value > 0
    ]
    return {"nodes": [{"name": name} for name in nodes], "links": links}


def referral_funnel(patients: list[PatientAgent]) -> dict:
    need = [p for p in patients if p.high_need]
    return {
        "arrived": len(patients),
        "underlying_need": len(need),
        "screened": sum(1 for p in patients if p.screen_completed),
        "screen_positive": sum(
            1
            for p in patients
            if p.screen_score is not None and p.screen_completed and p.screen_score >= 3
        ),
        "detected": sum(1 for p in need if p.detected),
        "referred": sum(1 for p in need if p.referral_target),
        "supported": sum(1 for p in need if p.received_support),
        "missed": sum(1 for p in need if p.missed),
        "left_waiting": sum(1 for p in need if p.left_before_psych),
    }


def detect_bottleneck(metrics: dict, scenario: ScenarioConfig) -> dict:
    candidates = []
    for role, label in ROLE_LABELS.items():
        if role == "coordinator":
            continue
        util = float(metrics["utilization"].get(role, 0))
        session = float(metrics.get("session_utilization", {}).get(role, 0))
        wait = float(metrics["mean_role_wait"].get(role, 0))
        peak = int(metrics["max_queue"].get(role, 0))
        pressure = max(util, session if role in {"social_work", "psychology", "child_life"} else util)
        if role in {"social_work", "psychology", "child_life"} and scenario.n_patients:
            weight = pressure * 0.58 + min(1, wait / 50) * 0.3 + min(1, peak / 6) * 0.12
        else:
            weight = util * 0.7 + min(1, wait / 45) * 0.2 + min(1, peak / 8) * 0.1
        candidates.append((weight, role, label, util, wait, peak))
    candidates.sort(reverse=True)
    _, role, label, util, wait, peak = candidates[0]
    session = float(metrics.get("session_utilization", {}).get(role, 0))
    interpretation = _interpret(role, label, util, wait, peak, metrics, scenario, session)
    return {
        "role": role,
        "label": label,
        "utilization": round(util, 3),
        "session_utilization": round(session, 3),
        "mean_wait": round(wait, 1),
        "peak_queue": peak,
        "interpretation": interpretation,
    }


def _interpret(role: str, label: str, util: float, wait: float, peak: int, metrics: dict, scenario: ScenarioConfig, session: float = 0) -> str:
    detection = metrics.get("detection_rate", 0)
    sentences = [
        f"Primary bottleneck: {label}. Day utilization {util:.0%}, in-session utilization {session:.0%}, mean wait {wait:.0f} min, peak queue {peak}."
    ]
    if scenario.screening_enabled and role in {"social_work", "psychology", "child_life"} and (util >= 0.75 or session >= 0.85 or wait >= 25):
        sentences.append(
            "Screening improved detection but referral demand exceeded current psychosocial capacity."
        )
    elif not scenario.screening_enabled and metrics.get("missed_rate", 0) >= 0.3:
        sentences.append(
            "Without systematic screening, recognition stayed dependent on observation, requests, and obvious distress."
        )
    elif scenario.predictive_mode == "selective":
        sentences.append(
            "Predictive triage concentrated screening on higher-risk families instead of screening every arrival."
        )
    if metrics.get("left_before_psych", 0):
        sentences.append(
            f"{metrics['left_before_psych']} families left before psychosocial assessment."
        )
    if detection >= 0.75 and metrics.get("support_rate", 0) + 0.25 < detection:
        sentences.append("Detection ran ahead of same-day support capacity.")
    if util < 0.55 and wait < 15 and role not in {"social_work", "psychology", "child_life"}:
        sentences = [
            f"No resource was saturated. The busiest area was {label} at {util:.0%} utilization."
        ]
    return " ".join(sentences)
