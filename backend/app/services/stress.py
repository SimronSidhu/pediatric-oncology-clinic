"""Dynamic stress for families and staff. Values are clamped to 0–100."""

from __future__ import annotations

from app.agents.base import CaregiverAgent, PatientAgent, StaffAgent, clamp


def initial_patient_stress(patient: PatientAgent) -> float:
    return clamp(
        18
        + patient.baseline_distress * 6.2
        + patient.symptom_burden * 14
        + patient.treatment_intensity * 8
        + (6 if patient.visit_type == "new" else 0)
    )


def initial_caregiver_stress(caregiver: CaregiverAgent, travel: float, child_distress: float) -> float:
    return clamp(caregiver.distress)


def apply_wait(patient: PatientAgent, caregiver: CaregiverAgent, minutes: float) -> None:
    """Waiting raises stress. Longer waits and higher complexity weigh more."""
    if minutes <= 0:
        return
    wait_factor = minutes * (0.22 + 0.18 * patient.complexity)
    patient.stress = clamp(patient.stress + wait_factor + 2.5 * patient.fatigue)
    patient.current_distress = clamp(
        patient.current_distress + minutes * 0.012, 0, 10
    )
    caregiver.stress = clamp(caregiver.stress + wait_factor * 0.85 + (3 if caregiver.travel_category != "local" else 0))
    caregiver.distress = caregiver.stress


def apply_complexity(patient: PatientAgent) -> None:
    patient.stress = clamp(
        patient.stress
        + 6 * patient.treatment_intensity
        + 5 * patient.symptom_burden
        + (4 if patient.urgent else 0)
    )


def apply_support(patient: PatientAgent, caregiver: CaregiverAgent, kind: str) -> None:
    relief = {"social_work": 16, "psychology": 18, "child_life": 14}.get(kind, 12)
    patient.stress = clamp(patient.stress - relief)
    patient.current_distress = clamp(patient.current_distress - relief / 12, 0, 10)
    caregiver.stress = clamp(caregiver.stress - relief * 0.9)
    caregiver.distress = caregiver.stress


def apply_supportive_interaction(patient: PatientAgent, caregiver: CaregiverAgent) -> None:
    patient.stress = clamp(patient.stress - 4)
    caregiver.stress = clamp(caregiver.stress - 3)


def apply_unresolved(patient: PatientAgent, caregiver: CaregiverAgent) -> None:
    if not patient.high_need or patient.received_support:
        return
    patient.stress = clamp(patient.stress + 8 + 4 * patient.anxiety)
    caregiver.stress = clamp(caregiver.stress + 7)


def staff_stress(
    staff: StaffAgent,
    queue: int,
    urgent: bool,
    interruption: bool,
    overtime: float,
) -> None:
    """Queue, urgency, interruptions, and overtime push staff stress up."""
    workload_factor = min(40, queue * 7 + staff.patients_seen * 0.6)
    change = (
        workload_factor * 0.18
        + (8 if urgent else 0)
        + (4 if interruption else 0)
        + min(12, overtime * 0.15)
        - 3.5
    )
    staff.workload = clamp(queue * 18 + staff.patients_seen * 2.2)
    staff.stress = clamp(staff.stress + change)
    if staff.workload >= 78 or queue >= 4:
        staff.availability = "overloaded"
    elif staff.availability != "absent":
        staff.availability = "busy" if staff.state not in {"AVAILABLE", "BREAK"} else "available"
