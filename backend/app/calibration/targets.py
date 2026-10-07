"""Published operating targets used for simulation-based calibration.

Rates come from implementation studies of psychosocial screening. The screen-time
target is a planning value for a short thermometer: those papers do not report
a time-motion mean, and the tolerance is wide on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    id: str
    label: str
    value: float
    tolerance: float
    source: str


TARGETS: tuple[Target, ...] = (
    Target(
        id="completion",
        label="Completed screens among families offered one",
        value=0.955,
        tolerance=0.05,
        source="Electronic caregiver distress thermometer in pediatric oncology: 1,923 of 2,013 patients had a completed screen (95.5% reach).",
    ),
    Target(
        id="referral_if_high",
        label="Social-work referral when the recorded score is 8 or higher",
        value=0.955,
        tolerance=0.05,
        source="Same electronic-screening program: 471 of 493 high-distress alerts were referred to social work (95.5%).",
    ),
    Target(
        id="screen_minutes",
        label="Minutes added by a completed screen",
        value=2.0,
        tolerance=0.75,
        source=(
            "A thermometer used with childhood cancer survivors and their parents is described as taking less than 2 minutes to complete. "
            "That is a completion-time claim, not a measured nursing time."
        ),
    ),
)

# Reported for context. Not used as a loss term: it describes program penetration
# across a multi-site PAT trial, which is a different quantity from check-in completion.
PENETRATION_NOTE = (
    "A separate multi-site Psychosocial Assessment Tool trial screened 73% of eligible families (529/721). "
    "That is program penetration, not the check-in completion rate calibrated here."
)
