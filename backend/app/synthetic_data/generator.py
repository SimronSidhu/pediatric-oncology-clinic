"""Conditional synthetic population. No real patient records are used."""

from __future__ import annotations

from numpy.random import Generator

from app.agents.base import CaregiverAgent, PatientAgent, StaffAgent
from app.agents.states import StaffState
from app.schemas.scenario import ScenarioConfig
from app.services.stress import initial_patient_stress

PATIENT_NAMES = [
    "Amina", "Leo", "Sofia", "Jonah", "Priya", "Mateo", "Hana", "Eli",
    "Noor", "Caleb", "Iris", "Samir", "Freya", "Owen", "Leila", "Hugo",
    "Maya", "Arlo", "Nadia", "Felix", "Sable", "Idris", "Willa", "Kenji",
    "Aria", "Nico", "Esme", "Ravi", "Thea", "Omar", "Lila", "Casper",
    "Yara", "Benicio", "Anouk", "Soren", "Dalia", "Io", "Farah", "Jules",
]

CAREGIVER_NAMES = [
    "Ruth", "Andre", "Helen", "Camille", "Marcus", "Elena", "Samuel", "Grace",
    "David", "Ines", "Peter", "Aisha", "Thomas", "Mei", "Robert", "Claire",
    "Hassan", "Nora", "Victor", "Jane", "Paul", "Amrita", "Louis", "Eva",
    "Daniel", "Fatima", "Chris", "Helena", "Mark", "Yasmin", "Alan", "Rosa",
    "Ivan", "Beth", "Karim", "Sue", "Neil", "Agnes", "Omar", "Lydia",
]

SURNAMES = [
    "Adeyemi", "Berg", "Cho", "Dalal", "Ellis", "Farouk", "Grant", "Ibarra",
    "Johansen", "Khan", "Laurent", "Mensah", "Nwosu", "Okada", "Petrova",
    "Rahman", "Silva", "Tanaka", "Ueda", "Voss", "Walker", "Young", "Zhou",
]

CANCERS = [
    "leukemia",
    "lymphoma",
    "brain tumor",
    "solid tumor",
    "bone tumor",
    "soft-tissue sarcoma",
]

PHASES_NEW = ["new_diagnosis", "active_treatment"]
PHASES_FOLLOW = ["active_treatment", "maintenance", "follow_up", "survivorship"]


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def distress_band(score: float) -> str:
    if score <= 2:
        return "low"
    if score <= 5:
        return "moderate"
    if score <= 8:
        return "high"
    return "severe"


def sample_distress(
    rng: Generator,
    scenario: ScenarioConfig,
    newly: bool,
    symptom: float,
    intensity: float,
) -> float:
    """Mixture model whose weights shift with clinical covariates."""
    high_p = scenario.high_distress_prevalence + 0.08 * int(newly) + 0.1 * symptom
    high_p += 0.05 if intensity > 0.75 else 0.0
    mod_floor = max(0.0, scenario.distress_prevalence - scenario.high_distress_prevalence)
    mod_p = mod_floor + 0.05 * symptom + (0.04 if newly else 0.0)
    high_p = _clip(high_p, 0.04, 0.88)
    mod_p = _clip(mod_p, 0.04, 0.9)
    low_p = max(0.04, 1.0 - high_p - mod_p)
    total = high_p + mod_p + low_p
    high_p, mod_p = high_p / total, mod_p / total
    roll = float(rng.random())
    if roll < high_p:
        return float(_clip(rng.normal(7.7, 0.95), 6.0, 10.0))
    if roll < high_p + mod_p:
        return float(_clip(rng.normal(4.15, 0.65), 3.0, 5.6))
    return float(_clip(rng.normal(1.25, 0.7), 0.0, 2.7))


def _predraw(rng: Generator, scenario: ScenarioConfig, language: bool) -> dict[str, float]:
    screen = float(rng.normal(scenario.screening_duration_mean, scenario.screening_duration_sd))
    if language:
        screen *= 1.45
    return {
        "checkin": float(_clip(rng.normal(scenario.mean_checkin_min, 0.9), 2.0, 9.0)),
        "screen": float(_clip(screen, 0.8, 14.0)),
        "nurse": float(_clip(rng.gamma(3.1, scenario.mean_nurse_min / 3.1), 6.0, 30.0)),
        "onc": float(
            _clip(
                rng.lognormal(
                    __import__("math").log(scenario.mean_onc_visit_min) - 0.5 * 0.32**2,
                    0.32,
                ),
                12.0,
                58.0,
            )
        ),
        "treatment": float(_clip(rng.gamma(2.5, 7.5), 8.0, 42.0)),
        "social_work": float(_clip(rng.gamma(3.1, scenario.mean_social_work_min / 3.1), 18.0, 62.0)),
        "psychology": float(_clip(rng.gamma(2.8, scenario.mean_psychology_min / 2.8), 18.0, 68.0)),
        "child_life": float(_clip(rng.gamma(2.5, scenario.mean_child_life_min / 2.5), 12.0, 46.0)),
        "doc": float(_clip(rng.normal(2.6, 0.45), 1.4, 5.5)),
        "triage_admin": float(_clip(rng.normal(6.5, 1.2), 4.0, 12.0)),
        "screen_noise": float(rng.normal(0.0, 0.8)),
        "chart_noise": float(rng.normal(0.0, 1.15)),
        "decline_roll": float(rng.random()),
        "incomplete_roll": float(rng.random()),
        "detect_nurse": float(rng.random()),
        "detect_onc": float(rng.random()),
        "request_roll": float(rng.random()),
        "existing_roll": float(rng.random()),
        "obvious_roll": float(rng.random()),
        "child_life_route": float(rng.random()),
        "psych_route": float(rng.random()),
        "monitor_roll": float(rng.random()),
        "disclosure_roll": float(rng.random()),
        "uptake_roll": float(rng.random()),
        "patience": float(_clip(rng.normal(scenario.patience_min, 7.5), 22.0, 85.0)),
        "arrival_noise": float(rng.normal(scenario.arrival_delay_mean, scenario.arrival_delay_sd)),
        "late_bump": float(abs(rng.normal(14, 5))) if rng.random() < 0.2 else 0.0,
        "provider_delay": 14.0 if rng.random() < 0.5 else 0.0,
    }


def build_population(scenario: ScenarioConfig, rng: Generator) -> tuple[list[PatientAgent], dict[str, CaregiverAgent], list[StaffAgent]]:
    patients: list[PatientAgent] = []
    caregivers: dict[str, CaregiverAgent] = {}
    streams = max(1, scenario.n_oncologists)

    for i in range(scenario.n_patients):
        slot = i // streams
        appointment = slot * scenario.appointment_spacing_min
        age_band = float(rng.random())
        if age_band < 0.16:
            age = float(rng.uniform(1.5, 4.5))
        elif age_band < 0.72:
            age = float(rng.uniform(4.5, 12.5))
        else:
            age = float(rng.uniform(12.5, 18.0))

        newly = float(rng.random()) < scenario.pct_new_diagnosis
        intensity = float(
            _clip(
                rng.normal(scenario.mean_treatment_intensity + (0.12 if newly else 0.0), 0.16),
                0.08,
                0.98,
            )
        )
        symptom = float(
            _clip(0.22 + 0.62 * intensity + (0.1 if newly else 0.0) + rng.normal(0, 0.08), 0.02, 0.98)
        )
        distress = sample_distress(rng, scenario, newly, symptom, intensity)
        distress = float(
            _clip(distress + (1.15 if newly else 0.0) + 1.35 * (symptom - 0.45) + 0.45 * (intensity - 0.5), 0, 10)
        )
        rural = float(rng.random()) < scenario.rural_rate
        travel = float(_clip(0.15 + (0.55 if rural else 0.0) + rng.normal(0, 0.08), 0.0, 1.0))
        travel_category = "long_distance" if rural or travel > 0.65 else ("regional" if travel > 0.4 else "local")
        language = float(rng.random()) < scenario.language_support_rate
        complexity = float(
            _clip(0.35 * intensity + 0.25 * symptom + 0.2 * scenario.mean_complexity + rng.normal(0, 0.08), 0.05, 0.98)
        )
        caregiver_stress = float(
            _clip(
                scenario.mean_caregiver_stress
                + 16 * travel
                + 10 * symptom
                + (12 if newly else 0)
                + 0.35 * distress
                + rng.normal(0, 6),
                5,
                98,
            )
        )
        need = 0.64 * distress + 0.36 * (caregiver_stress / 10.0)
        phase_pool = PHASES_NEW if newly else PHASES_FOLLOW
        phase = str(rng.choice(phase_pool))
        visit = "new" if newly else ("treatment" if phase == "active_treatment" and intensity > 0.6 else "follow_up")
        draws = _predraw(rng, scenario, language)
        needs_tx = float(rng.random()) < (0.18 + 0.5 * intensity if phase == "active_treatment" else 0.05)
        urgent = i == max(0, scenario.n_patients // 3)

        pid = f"P{i + 1:02d}"
        surname = SURNAMES[i % len(SURNAMES)]
        patient = PatientAgent(
            id=pid,
            name=f"{PATIENT_NAMES[i % len(PATIENT_NAMES)]} {surname}",
            role="patient",
            age=round(age, 1),
            sex="F" if rng.random() < 0.48 else "M",
            visit_type=visit,
            cancer_category=str(rng.choice(CANCERS)),
            treatment_phase=phase,
            treatment_intensity=round(intensity, 3),
            symptom_burden=round(symptom, 3),
            baseline_distress=round(distress, 2),
            current_distress=round(distress, 2),
            chart_distress=round(_clip(distress + draws["chart_noise"], 0, 10), 2),
            fatigue=round(_clip(0.25 + 0.6 * symptom + rng.normal(0, 0.05), 0, 1), 3),
            anxiety=round(_clip(distress / 10 * 0.7 + (0.15 if newly else 0) + rng.normal(0, 0.05), 0, 1), 3),
            caregiver_support=round(_clip(1 - caregiver_stress / 140, 0.1, 0.95), 3),
            travel_burden=round(travel, 3),
            travel_category=travel_category,
            language_support=language,
            psychosocial_need=round(need, 2),
            high_need=bool(need >= 6.0 or distress >= 6.4),
            complexity=round(complexity, 3),
            prior_psychosocial=bool(rng.random() < (0.18 + 0.2 * (distress / 10))),
            previous_wait_min=round(float(_clip(rng.normal(22, 10), 5, 70)), 1),
            appointment_time=round(appointment, 2),
            urgent=urgent,
            needs_treatment=needs_tx,
            priority=0 if urgent else 5,
        )
        patient.arrival_time = round(max(0.0, appointment + draws["arrival_noise"] + draws["late_bump"]), 2)
        patient.stress = round(initial_patient_stress(patient), 1)
        patient.draws = draws  # type: ignore[attr-defined]
        patient.pending_review = ""  # type: ignore[attr-defined]
        patient.unserved = False  # type: ignore[attr-defined]
        patient.detected = False  # type: ignore[attr-defined]
        patient.current_task = "Scheduled"
        patient.next_task = "Travel to clinic"
        patient.goal = "Get through today's visit"
        patient.schedule = [
            {"label": "Appointment", "time": appointment},
            {"label": "Expected arrival", "time": patient.arrival_time},
        ]
        if patient.arrival_time > appointment + 10:
            patient.remember(patient.arrival_time, "running_late", minutes=round(patient.arrival_time - appointment, 1))

        cg = CaregiverAgent(
            id=f"C{i + 1:02d}",
            name=f"{CAREGIVER_NAMES[i % len(CAREGIVER_NAMES)]} {surname}",
            role="caregiver",
            patient_id=pid,
            relationship="parent",
            distress=round(caregiver_stress, 1),
            stress=round(caregiver_stress, 1),
            privacy_concern=round(float(_clip(rng.normal(0.35, 0.12), 0.05, 0.95)), 3),
            prior_screening_experience="difficult" if rng.random() < 0.18 else "neutral",
            travel_category=travel_category,
        )
        cg.goal = "Stay with their child and keep the day manageable"
        cg.current_task = "Traveling with the patient"
        cg.next_task = "Check in"
        patients.append(patient)
        caregivers[pid] = cg

    staff = build_staff(scenario, rng)
    return patients, caregivers, staff


def build_staff(scenario: ScenarioConfig, rng: Generator) -> list[StaffAgent]:
    people: list[StaffAgent] = []
    absent = min(scenario.nurse_absence, max(0, scenario.n_nurses - 1))
    nurse_names = ["Priya Raman", "Jonah Ellis", "Camille Ortiz", "Helen Brooks", "Luis Ortega", "Amina Shah", "Greta Holm", "Noah Pike"]
    onc_names = ["Dr. Helen Cho", "Dr. Andre Nwosu", "Dr. Maya Rahman", "Dr. Seth Adler", "Dr. Lila Mensah", "Dr. Omar Grant"]
    sw_names = ["Ruth Adelman", "Chris Dalton", "Imani Brooks", "Paul Okonkwo", "Eva Lorca"]
    psych_names = ["Dr. Samuel Iqbal", "Dr. Nora Feldman", "Dr. Leila Haddad", "Dr. Victor Ames"]
    cl_names = ["Maya Chen", "Samir Blake", "Freya Nilsen", "Otto Park"]
    admin_names = ["Elena Voss", "Marcus Hale", "Ines Petrova", "Alan Zhou"]

    for i in range(scenario.n_nurses):
        on = i >= absent
        people.append(
            _staff(
                f"N{i + 1}",
                nurse_names[i % len(nurse_names)],
                "nurse",
                "triage" if on else "staff",
                on,
                "Assess patients and review distress alerts",
            )
        )
    for i in range(scenario.n_oncologists):
        people.append(
            _staff(
                f"O{i + 1}",
                onc_names[i % len(onc_names)],
                "oncologist",
                "oncology",
                True,
                "Complete scheduled oncology visits",
            )
        )
    for i in range(scenario.n_social_workers):
        people.append(
            _staff(
                f"SW{i + 1}",
                sw_names[i % len(sw_names)],
                "social_worker",
                "psychosocial",
                True,
                "Respond to psychosocial referrals",
            )
        )
    for i in range(scenario.n_psychologists):
        people.append(
            _staff(
                f"PS{i + 1}",
                psych_names[i % len(psych_names)],
                "psychologist",
                "psychosocial",
                True,
                "Assess higher-acuity distress",
            )
        )
    for i in range(scenario.n_child_life):
        people.append(
            _staff(
                f"CL{i + 1}",
                cl_names[i % len(cl_names)],
                "child_life",
                "child_life",
                True,
                "Support younger children through the visit",
            )
        )
    for i in range(scenario.n_admin):
        people.append(
            _staff(
                f"AD{i + 1}",
                admin_names[i % len(admin_names)],
                "admin",
                "reception",
                True,
                "Check families in and keep the front desk moving",
            )
        )
    people.append(
        _staff(
            "CO1",
            "Jordan Hale",
            "coordinator",
            "staff",
            True,
            "Keep the day coordinated and triage psychosocial demand",
        )
    )
    # Touch rng so staff construction stays part of the seeded stream without changing order later.
    _ = float(rng.random())
    return people


def _staff(id_: str, name: str, role: str, room: str, on_duty: bool, goal: str) -> StaffAgent:
    person = StaffAgent(
        id=id_,
        name=name,
        role=role,
        discipline=role,
        room=room,
        on_duty=on_duty,
        location=room,
        goal=goal,
    )
    if not on_duty:
        person.set_state(StaffState.BREAK)
        person.availability = "absent"
        person.current_task = "Absent today"
        person.next_task = "Off the schedule"
        person.stress = 0
    return person
