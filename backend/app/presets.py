"""Named clinic-day presets for the experiment panel."""

from __future__ import annotations

from app.schemas.scenario import ScenarioConfig


def _demo(**overrides: object) -> ScenarioConfig:
    base = ScenarioConfig(name="Universal Screening", seed=17)
    return base.model_copy(update=overrides)


PRESET_BUILDERS = {
    "baseline": lambda: _demo(
        name="Baseline",
        screening_enabled=False,
        predictive_mode="off",
    ),
    "universal": lambda: _demo(name="Universal Screening"),
    "extra_social_worker": lambda: _demo(
        name="Screening + Extra Social Worker",
        n_social_workers=2,
    ),
    "nurse_triage": lambda: _demo(
        name="Nurse Triage",
        referral_mode="nurse_review",
    ),
    "portal": lambda: _demo(
        name="Portal Screening",
        screening_location="portal",
    ),
    "staff_shortage": lambda: _demo(
        name="Staff Shortage",
        nurse_absence=1,
        late_provider_min=12,
    ),
    "high_volume": lambda: _demo(
        name="High Volume Day",
        n_patients=26,
    ),
    "high_distress": lambda: _demo(
        name="High Distress Day",
        distress_prevalence=0.8,
        high_distress_prevalence=0.5,
        mean_caregiver_stress=62,
    ),
    "predictive": lambda: _demo(
        name="Predictive Triage",
        screening_enabled=False,
        predictive_mode="selective",
    ),
    "predictive_priority": lambda: _demo(
        name="Screening + Predictive Priority",
        predictive_mode="prioritize",
    ),
}


def list_presets() -> list[dict]:
    descriptions = {
        "baseline": "No systematic distress screening. Recognition depends on observation, requests, and obvious distress.",
        "universal": "Every family is offered a short distress screen at check-in. Moderate and higher scores are referred.",
        "extra_social_worker": "Universal screening with a second social worker, to test whether capacity catches the new demand.",
        "nurse_triage": "Positive screens wait for a nurse review before a referral is opened.",
        "portal": "Screening is completed before arrival, so check-in stays short.",
        "staff_shortage": "One nurse is absent and an oncologist starts late.",
        "high_volume": "Scheduled volume is 30% higher than the demo day.",
        "high_distress": "The panel has more newly distressed families than a typical day.",
        "predictive": "A risk model chooses who is screened, instead of screening every arrival.",
        "predictive_priority": "Everyone is screened, and higher predicted risk moves ahead in the psychosocial queue.",
    }
    items = []
    for key, builder in PRESET_BUILDERS.items():
        scenario = builder()
        items.append({"id": key, "description": descriptions[key], "scenario": scenario.model_dump()})
    return items


def preset(key: str) -> ScenarioConfig:
    return PRESET_BUILDERS[key]()
