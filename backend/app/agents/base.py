"""Shared agent state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.states import (
    CAREGIVER_TRANSITIONS,
    PATIENT_TRANSITIONS,
    STAFF_TRANSITIONS,
    CaregiverState,
    PatientState,
    StaffState,
    StateMachine,
)


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


@dataclass
class MemoryEntry:
    time: float
    event: str
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"time": round(self.time, 1), "event": self.event, **self.detail}


@dataclass
class Agent:
    id: str
    name: str
    role: str
    location: str = "entrance"
    stress: float = 20.0
    workload: float = 0.0
    availability: str = "available"
    current_task: str = "Scheduled"
    next_task: str = "Arrive at clinic"
    goal: str = ""
    schedule: list[dict[str, Any]] = field(default_factory=list)
    interactions: list[dict[str, Any]] = field(default_factory=list)
    memory: list[MemoryEntry] = field(default_factory=list)

    def remember(self, time: float, event: str, **detail: Any) -> None:
        self.memory.append(MemoryEntry(time, event, detail))
        if len(self.memory) > 12:
            self.memory = self.memory[-12:]

    def interact(self, time: float, with_role: str, kind: str) -> None:
        self.interactions.append(
            {"time": round(time, 1), "with": with_role, "kind": kind}
        )

    def memory_dicts(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in self.memory]


@dataclass
class PatientAgent(Agent):
    age: float = 8.0
    sex: str = "F"
    visit_type: str = "follow_up"
    cancer_category: str = "leukemia"
    treatment_phase: str = "active_treatment"
    treatment_intensity: float = 0.4
    symptom_burden: float = 0.3
    baseline_distress: float = 2.0
    current_distress: float = 2.0
    chart_distress: float = 2.0
    fatigue: float = 0.3
    anxiety: float = 0.3
    caregiver_support: float = 0.7
    travel_burden: float = 0.2
    travel_category: str = "local"
    language_support: bool = False
    psychosocial_need: float = 2.0
    high_need: bool = False
    complexity: float = 0.3
    prior_psychosocial: bool = False
    previous_wait_min: float = 15.0
    appointment_time: float = 0.0
    arrival_time: float = 0.0
    urgent: bool = False
    needs_treatment: bool = False
    priority: int = 5
    predicted_risk: float = 0.2

    identified: bool = False
    identification_route: str = ""
    screen_offered: bool = False
    screen_completed: bool = False
    screen_declined: bool = False
    screen_incomplete: bool = False
    screen_score: int | None = None
    screen_category: str = ""
    screen_minutes: float = 0.0
    disclosure: str = ""
    referral_target: str = ""
    referral_reason: str = ""
    referral_completed: bool = False
    referral_deferred: bool = False
    left_before_psych: bool = False
    missed: bool = False
    missed_reason: str = ""
    received_support: bool = False
    false_positive_referral: bool = False

    nurse_wait: float = 0.0
    onc_wait: float = 0.0
    psych_wait: float = 0.0
    admin_wait: float = 0.0
    cycle_time: float = 0.0
    discharge_time: float | None = None

    segments: list[dict[str, Any]] = field(default_factory=list)
    _segment_start: float | None = None
    _segment_phase: str | None = None

    machine: StateMachine = field(init=False)

    def __post_init__(self) -> None:
        self.machine = StateMachine(PatientState.SCHEDULED, PATIENT_TRANSITIONS)
        self.role = "patient"
        self.goal = "Complete today's oncology visit and get home"
        self.location = "offsite"

    @property
    def state(self) -> str:
        return self.machine.state.value

    def set_state(self, new: PatientState) -> None:
        self.machine.transition(new)

    def start_segment(self, now: float, phase: str) -> None:
        self.close_segment(now)
        self._segment_start = now
        self._segment_phase = phase

    def close_segment(self, now: float) -> None:
        if self._segment_start is None or self._segment_phase is None:
            return
        if now > self._segment_start:
            self.segments.append(
                {
                    "phase": self._segment_phase,
                    "start": round(self._segment_start, 2),
                    "end": round(now, 2),
                }
            )
        self._segment_start = None
        self._segment_phase = None


@dataclass
class CaregiverAgent(Agent):
    patient_id: str = ""
    relationship: str = "parent"
    distress: float = 30.0
    privacy_concern: float = 0.3
    prior_screening_experience: str = "none"
    travel_category: str = "local"
    machine: StateMachine = field(init=False)

    def __post_init__(self) -> None:
        self.machine = StateMachine(CaregiverState.SCHEDULED, CAREGIVER_TRANSITIONS)
        self.role = "caregiver"
        self.goal = "Stay with their child and keep the day manageable"
        self.location = "offsite"

    @property
    def state(self) -> str:
        return self.machine.state.value

    def set_state(self, new: CaregiverState) -> None:
        self.machine.transition(new)


@dataclass
class StaffAgent(Agent):
    discipline: str = "nurse"
    room: str = "triage"
    patients_seen: int = 0
    alerts_handled: int = 0
    busy_minutes: float = 0.0
    overtime_minutes: float = 0.0
    queue_seen_peak: int = 0
    on_duty: bool = True
    machine: StateMachine = field(init=False)

    def __post_init__(self) -> None:
        initial = StaffState.AVAILABLE if self.on_duty else StaffState.BREAK
        self.machine = StateMachine(initial, STAFF_TRANSITIONS)
        self.availability = "available" if self.on_duty else "absent"
        self.current_task = "Available" if self.on_duty else "Absent today"
        self.next_task = "Take the next patient" if self.on_duty else "Off duty"
        self.location = self.room

    @property
    def state(self) -> str:
        return self.machine.state.value

    def set_state(self, new: StaffState) -> None:
        if self.machine.state != new:
            self.machine.transition(new)
