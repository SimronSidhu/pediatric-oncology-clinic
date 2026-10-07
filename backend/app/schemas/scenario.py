"""Scenario configuration for a simulated clinic day."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ScreenLocation = Literal["check_in", "waiting_room", "nurse", "portal"]
ReferralMode = Literal["automatic", "nurse_review", "oncologist_review", "central_triage", "learned"]
AlertLevel = Literal["moderate", "high", "severe"]
PredictiveMode = Literal["off", "selective", "prioritize"]


ALERT_SCORE = {"moderate": 3, "high": 6, "severe": 9}


class ScenarioConfig(BaseModel):
    """User-controlled clinic, population, and workflow parameters."""

    name: str = "Universal Screening"
    seed: int = 17
    n_patients: int = Field(20, ge=4, le=80)
    n_nurses: int = Field(3, ge=1, le=8)
    n_oncologists: int = Field(2, ge=1, le=6)
    n_social_workers: int = Field(1, ge=0, le=5)
    n_psychologists: int = Field(1, ge=0, le=4)
    n_child_life: int = Field(1, ge=0, le=4)
    n_admin: int = Field(2, ge=1, le=4)
    open_hour: float = Field(8, ge=6, le=12)
    close_hour: float = Field(16, ge=12, le=20)
    appointment_spacing_min: float = Field(26, ge=8, le=60)
    mean_onc_visit_min: float = Field(20, ge=10, le=60)

    pct_new_diagnosis: float = Field(0.35, ge=0, le=1)
    distress_prevalence: float = Field(0.62, ge=0.05, le=0.95)
    high_distress_prevalence: float = Field(0.34, ge=0.02, le=0.9)
    mean_treatment_intensity: float = Field(0.55, ge=0.1, le=0.95)
    mean_complexity: float = Field(0.48, ge=0.05, le=0.95)
    language_support_rate: float = Field(0.15, ge=0, le=0.8)
    rural_rate: float = Field(0.28, ge=0, le=0.9)
    mean_caregiver_stress: float = Field(48, ge=5, le=90)

    arrival_delay_mean: float = 1.0
    arrival_delay_sd: float = 7.5

    screening_enabled: bool = True
    screening_location: ScreenLocation = "check_in"
    screening_completion_rate: float = Field(0.94, ge=0.2, le=1)
    screening_duration_mean: float = Field(4.5, ge=1, le=15)
    screening_duration_sd: float = Field(1.1, ge=0.2, le=4)
    referral_threshold: int = Field(3, ge=0, le=10)
    alert_threshold: AlertLevel = "moderate"
    referral_mode: ReferralMode = "automatic"
    decline_rate: float = Field(0.1, ge=0, le=0.7)
    referral_uptake: float = Field(1.0, ge=0.2, le=1)

    predictive_mode: PredictiveMode = "off"
    nurse_absence: int = Field(0, ge=0, le=4)
    use_llm: bool = False

    mean_nurse_min: float = Field(12, ge=5, le=30)
    mean_social_work_min: float = Field(40, ge=15, le=70)
    mean_psychology_min: float = Field(36, ge=15, le=70)
    mean_child_life_min: float = Field(24, ge=10, le=50)
    mean_checkin_min: float = Field(4.0, ge=2, le=12)
    patience_min: float = Field(55, ge=15, le=120)
    late_provider_min: float = Field(0, ge=0, le=45)

    def alert_score(self) -> int:
        return ALERT_SCORE[self.alert_threshold]

    def open_minutes(self) -> float:
        return 0.0

    def close_minutes(self) -> float:
        return (self.close_hour - self.open_hour) * 60.0
