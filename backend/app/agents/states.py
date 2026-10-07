"""Explicit state machines for patients and staff."""

from __future__ import annotations

from enum import Enum


class PatientState(str, Enum):
    SCHEDULED = "SCHEDULED"
    ARRIVING = "ARRIVING"
    CHECK_IN = "CHECK_IN"
    WAITING_FOR_NURSE = "WAITING_FOR_NURSE"
    NURSE_VISIT = "NURSE_VISIT"
    WAITING_FOR_ONCOLOGIST = "WAITING_FOR_ONCOLOGIST"
    ONCOLOGY_VISIT = "ONCOLOGY_VISIT"
    TREATMENT = "TREATMENT"
    WAITING_FOR_PSYCHOSOCIAL = "WAITING_FOR_PSYCHOSOCIAL"
    PSYCHOSOCIAL_VISIT = "PSYCHOSOCIAL_VISIT"
    DISCHARGED = "DISCHARGED"


class StaffState(str, Enum):
    AVAILABLE = "AVAILABLE"
    REVIEWING = "REVIEWING"
    WITH_PATIENT = "WITH_PATIENT"
    DOCUMENTING = "DOCUMENTING"
    BREAK = "BREAK"
    OVERLOADED = "OVERLOADED"
    URGENT_CASE = "URGENT_CASE"


class CaregiverState(str, Enum):
    SCHEDULED = "SCHEDULED"
    ARRIVING = "ARRIVING"
    CHECK_IN = "CHECK_IN"
    WAITING = "WAITING"
    IN_VISIT = "IN_VISIT"
    PSYCHOSOCIAL = "PSYCHOSOCIAL"
    DISCHARGED = "DISCHARGED"


PATIENT_TRANSITIONS: dict[PatientState, set[PatientState]] = {
    PatientState.SCHEDULED: {PatientState.ARRIVING},
    PatientState.ARRIVING: {PatientState.CHECK_IN},
    PatientState.CHECK_IN: {PatientState.WAITING_FOR_NURSE},
    PatientState.WAITING_FOR_NURSE: {PatientState.NURSE_VISIT, PatientState.DISCHARGED},
    PatientState.NURSE_VISIT: {PatientState.WAITING_FOR_ONCOLOGIST},
    PatientState.WAITING_FOR_ONCOLOGIST: {PatientState.ONCOLOGY_VISIT, PatientState.DISCHARGED},
    PatientState.ONCOLOGY_VISIT: {
        PatientState.TREATMENT,
        PatientState.WAITING_FOR_PSYCHOSOCIAL,
        PatientState.DISCHARGED,
    },
    PatientState.TREATMENT: {
        PatientState.WAITING_FOR_PSYCHOSOCIAL,
        PatientState.DISCHARGED,
    },
    PatientState.WAITING_FOR_PSYCHOSOCIAL: {
        PatientState.PSYCHOSOCIAL_VISIT,
        PatientState.DISCHARGED,
    },
    PatientState.PSYCHOSOCIAL_VISIT: {PatientState.DISCHARGED},
    PatientState.DISCHARGED: set(),
}

CAREGIVER_TRANSITIONS: dict[CaregiverState, set[CaregiverState]] = {
    CaregiverState.SCHEDULED: {CaregiverState.ARRIVING},
    CaregiverState.ARRIVING: {CaregiverState.CHECK_IN},
    CaregiverState.CHECK_IN: {CaregiverState.WAITING, CaregiverState.IN_VISIT},
    CaregiverState.WAITING: {
        CaregiverState.IN_VISIT,
        CaregiverState.PSYCHOSOCIAL,
        CaregiverState.DISCHARGED,
        CaregiverState.CHECK_IN,
    },
    CaregiverState.IN_VISIT: {
        CaregiverState.WAITING,
        CaregiverState.PSYCHOSOCIAL,
        CaregiverState.DISCHARGED,
    },
    CaregiverState.PSYCHOSOCIAL: {CaregiverState.DISCHARGED, CaregiverState.WAITING},
    CaregiverState.DISCHARGED: set(),
}

STAFF_TRANSITIONS: dict[StaffState, set[StaffState]] = {
    StaffState.AVAILABLE: {
        StaffState.REVIEWING,
        StaffState.WITH_PATIENT,
        StaffState.BREAK,
        StaffState.OVERLOADED,
        StaffState.URGENT_CASE,
        StaffState.DOCUMENTING,
    },
    StaffState.REVIEWING: {
        StaffState.WITH_PATIENT,
        StaffState.AVAILABLE,
        StaffState.DOCUMENTING,
        StaffState.OVERLOADED,
        StaffState.URGENT_CASE,
    },
    StaffState.WITH_PATIENT: {
        StaffState.DOCUMENTING,
        StaffState.AVAILABLE,
        StaffState.URGENT_CASE,
        StaffState.OVERLOADED,
    },
    StaffState.DOCUMENTING: {StaffState.AVAILABLE, StaffState.OVERLOADED, StaffState.BREAK},
    StaffState.BREAK: {StaffState.AVAILABLE, StaffState.WITH_PATIENT, StaffState.URGENT_CASE},
    StaffState.OVERLOADED: {
        StaffState.WITH_PATIENT,
        StaffState.REVIEWING,
        StaffState.DOCUMENTING,
        StaffState.AVAILABLE,
        StaffState.URGENT_CASE,
    },
    StaffState.URGENT_CASE: {
        StaffState.WITH_PATIENT,
        StaffState.DOCUMENTING,
        StaffState.AVAILABLE,
        StaffState.OVERLOADED,
    },
}


class StateMachine:
    """Guards transitions so illegal clinic flow fails loudly in tests."""

    def __init__(self, initial: Enum, transitions: dict):
        self.state = initial
        self._transitions = transitions
        self.history: list[str] = [initial.value]

    def can(self, new: Enum) -> bool:
        return new in self._transitions.get(self.state, set())

    def transition(self, new: Enum) -> None:
        if not self.can(new):
            raise ValueError(f"Illegal transition {self.state.value} -> {new.value}")
        self.state = new
        self.history.append(new.value)
