"""Discrete-event clinic day. SimPy owns time, queues, and resources."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import simpy
from numpy.random import Generator, default_rng

from app.agents.base import CaregiverAgent, PatientAgent, StaffAgent, clamp
from app.agents.states import CaregiverState, PatientState, StaffState
from app.analytics.metrics import compute_metrics, detect_bottleneck, referral_funnel, sankey_from_paths
from app.schemas.scenario import ScenarioConfig
from app.services.decisions import RuleBasedDecisionEngine, engine_for, screening_decline_probability
from app.services.stress import apply_complexity, apply_support, apply_supportive_interaction, apply_unresolved, apply_wait, staff_stress
from app.simulation.distributions import band_for_score
from app.synthetic_data.generator import build_population

SELECTIVE_CUTOFF = 0.48
PSYCH_ROLES = {"social_work": "social_worker", "psychology": "psychologist", "child_life": "child_life"}
POOL_OF = {v: k for k, v in PSYCH_ROLES.items()}
POOL_OF.update(
    {
        "nurse": "nurse",
        "oncologist": "oncologist",
        "admin": "admin",
        "coordinator": "coordinator",
        "social_worker": "social_work",
        "psychologist": "psychology",
        "child_life": "child_life",
    }
)


class StaffPool:
    def __init__(self, env: simpy.Environment, people: list[StaffAgent]):
        self.all = people
        self.staff = [person for person in people if person.on_duty]
        self.free = list(self.staff)
        self.disabled = len(self.staff) == 0
        self.resource = simpy.PriorityResource(env, capacity=max(1, len(self.staff)))

    def take(self) -> StaffAgent:
        return self.free.pop(0)

    def give(self, person: StaffAgent) -> None:
        if person.machine.can(StaffState.AVAILABLE):
            person.set_state(StaffState.AVAILABLE)
        person.availability = "available"
        person.location = person.room
        person.current_task = "Available"
        person.next_task = "Take the next patient"
        if person not in self.free:
            self.free.append(person)


class ClinicSimulation:
    def __init__(self, scenario: ScenarioConfig, trace: bool = True, policy: Any | None = None):
        self.scenario = scenario
        self.trace = trace
        self.policy = policy
        self.env = simpy.Environment()
        self.rng: Generator = default_rng(scenario.seed)
        self.patients, self.caregivers, self.staff = build_population(scenario, self.rng)
        self.engine = engine_for(scenario.use_llm)
        self.rules = RuleBasedDecisionEngine()
        self.events: list[dict] = []
        self.frames: list[dict] = []
        self.peaks: dict[str, int] = defaultdict(int)
        self.role_waits: dict[str, list[float]] = defaultdict(list)
        self.alerts = 0
        self.above_80_minutes = 0.0
        self.close = scenario.close_minutes()
        self.horizon = self.close + 240
        self.pools = self._make_pools()
        self._assign_risks()

    def _make_pools(self) -> dict[str, StaffPool]:
        grouped: dict[str, list[StaffAgent]] = defaultdict(list)
        for person in self.staff:
            grouped[person.role].append(person)
        return {
            "nurse": StaffPool(self.env, grouped.get("nurse", [])),
            "oncologist": StaffPool(self.env, grouped.get("oncologist", [])),
            "social_work": StaffPool(self.env, grouped.get("social_worker", [])),
            "psychology": StaffPool(self.env, grouped.get("psychologist", [])),
            "child_life": StaffPool(self.env, grouped.get("child_life", [])),
            "admin": StaffPool(self.env, grouped.get("admin", [])),
            "coordinator": StaffPool(self.env, grouped.get("coordinator", [])),
        }

    def _assign_risks(self) -> None:
        risk_from_patient = None
        if self.scenario.predictive_mode != "off":
            try:
                from app.ml.model import risk_from_patient as predict
            except Exception:
                predict = None
            risk_from_patient = predict
        for patient in self.patients:
            caregiver = self.caregivers[patient.id]
            if risk_from_patient is not None:
                predicted = risk_from_patient(patient, caregiver)
            else:
                predicted = None
            patient.predicted_risk = round(
                predicted if predicted is not None else _heuristic_risk(patient, caregiver),
                3,
            )
            if self.scenario.predictive_mode == "prioritize" and patient.predicted_risk >= 0.7:
                patient.priority = min(patient.priority, 1)
            elif self.scenario.predictive_mode == "prioritize" and patient.predicted_risk >= 0.45:
                patient.priority = min(patient.priority, 2)

    def run(self) -> dict:
        self._log(
            0,
            "clinic_open",
            "system",
            None,
            f"Clinic open. {self.scenario.name}.",
            "The day starts with the selected staffing and workflow.",
        )
        self.env.process(self._monitor())
        if self.scenario.late_provider_min > 0 and self.pools["oncologist"].staff:
            self.env.process(self._provider_delay(self.pools["oncologist"], self.scenario.late_provider_min))
        for patient in self.patients:
            self.env.process(self._journey(patient))
        self.env.run()
        for patient in self.patients:
            if patient.discharge_time is None:
                self._discharge(patient, self.caregivers[patient.id], forced=True)
        return self._result()

    def clock(self, t: float) -> str:
        minutes = int(self.scenario.open_hour * 60 + t)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _log(
        self,
        t: float,
        event_type: str,
        category: str,
        agent_id: str | None,
        message: str,
        reason: str,
        data: dict | None = None,
    ) -> None:
        if not self.trace and category != "system":
            return
        self.events.append(
            {
                "t": round(t, 2),
                "clock": self.clock(t),
                "type": event_type,
                "category": category,
                "agent_id": agent_id,
                "message": f"{self.clock(t)} — {message}",
                "reason": reason,
                "data": data or {},
            }
        )

    def _queues(self) -> dict[str, int]:
        counts = {}
        for name, pool in self.pools.items():
            counts[name] = 0 if pool.disabled else len(pool.resource.queue)
            self.peaks[name] = max(self.peaks[name], counts[name])
        return counts

    def _journey(self, patient: PatientAgent):
        caregiver = self.caregivers[patient.id]
        if patient.arrival_time > 0:
            yield self.env.timeout(patient.arrival_time)
        self._arrive(patient, caregiver)
        if self._should_offer(patient, "portal"):
            self._offer_screen(patient, caregiver)
        yield from self._check_in(patient, caregiver)
        if patient.pending_review == "triage":
            yield from self._central_triage(patient, caregiver)
        if self._should_offer(patient, "waiting_room"):
            yield from self._self_screen(patient, caregiver)
            if patient.pending_review == "triage":
                yield from self._central_triage(patient, caregiver)
        yield from self._nurse_stage(patient, caregiver)
        if patient.machine.state == PatientState.DISCHARGED:
            return
        yield from self._oncology_stage(patient, caregiver)
        if patient.machine.state == PatientState.DISCHARGED:
            return
        if patient.needs_treatment and patient.machine.can(PatientState.TREATMENT):
            yield from self._treatment(patient, caregiver)
        if patient.referral_target and patient.machine.state != PatientState.DISCHARGED:
            yield from self._psychosocial(patient, caregiver)
        if patient.machine.state != PatientState.DISCHARGED:
            self._discharge(patient, caregiver)
            yield self.env.timeout(6)
            patient.location = "departed"
            caregiver.location = "departed"

    def _arrive(self, patient: PatientAgent, caregiver: CaregiverAgent) -> None:
        patient.set_state(PatientState.ARRIVING)
        patient.location = "entrance"
        patient.current_task = "Arriving"
        patient.next_task = "Check in"
        patient.start_segment(self.env.now, "Arrival")
        patient.path = ["Arrival"]
        self._cg(caregiver, CaregiverState.ARRIVING, "entrance", "Arriving with the patient", "Check in")
        late = patient.arrival_time > patient.appointment_time + 10
        reason = (
            f"Arrived {patient.arrival_time - patient.appointment_time:.0f} min after the appointment."
            if late
            else "Arrived for the scheduled oncology visit."
        )
        self._log(self.env.now, "arrival", "delay" if late else "patient", patient.id, f"{patient.name} ({patient.id}) arrived", reason)
        if late:
            patient.stress = clamp(patient.stress + 6)
            caregiver.stress = clamp(caregiver.stress + 5)
            patient.remember(self.env.now, "arrived_late", minutes=round(patient.arrival_time - patient.appointment_time, 1))
        self._obvious_distress(patient, caregiver)

    def _obvious_distress(self, patient: PatientAgent, caregiver: CaregiverAgent) -> None:
        if patient.baseline_distress < 9.2 or patient.referral_target:
            return
        if patient.draws["obvious_roll"] >= 0.34:  # type: ignore[attr-defined]
            return
        target = self._route(patient, 9)
        self._create_referral(
            patient,
            caregiver,
            target,
            "Obvious distress noticed on arrival",
            route_name="obvious_distress",
        )

    def _check_in(self, patient: PatientAgent, caregiver: CaregiverAgent):
        patient.set_state(PatientState.CHECK_IN)
        patient.location = "reception"
        patient.current_task = "Checking in"
        patient.next_task = "Waiting room"
        patient.path.append("Check-in")
        self._cg(caregiver, CaregiverState.CHECK_IN, "reception", "Checking the family in", "Waiting room")
        extra = 0.0
        if self._should_offer(patient, "check_in"):
            extra = self._offer_screen(patient, caregiver)
        clinical = patient.draws["checkin"] + extra  # type: ignore[attr-defined]
        wait, _staff = yield from self._serve(
            "admin",
            patient,
            clinical,
            0.4,
            "reception",
            f"Checking in {patient.id}",
        )
        patient.admin_wait = wait
        self.role_waits["admin"].append(wait)
        if wait >= 8:
            apply_wait(patient, caregiver, wait)
            self._log(self.env.now, "checkin_delay", "delay", patient.id, f"{patient.id} waited {wait:.0f} min to check in", "Front desk queue.")
        patient.interact(self.env.now, "admin", "check_in")

    def _self_screen(self, patient: PatientAgent, caregiver: CaregiverAgent):
        patient.location = "waiting_room"
        patient.current_task = "Distress screening in the waiting room"
        duration = self._offer_screen(patient, caregiver)
        if duration > 0:
            yield self.env.timeout(duration)

    def _nurse_stage(self, patient: PatientAgent, caregiver: CaregiverAgent):
        patient.set_state(PatientState.WAITING_FOR_NURSE)
        patient.location = "waiting_room"
        patient.current_task = "Waiting for nurse assessment"
        patient.next_task = "Nurse assessment"
        self._cg(caregiver, CaregiverState.WAITING, "waiting_room", "Waiting with the patient", "Nurse assessment")
        if self.pools["nurse"].disabled:
            self._discharge(patient, caregiver, forced=True)
            return
        screen_extra = 0.0
        review_extra = 3.0 if patient.pending_review == "nurse" else 0.0
        if self._should_offer(patient, "nurse"):
            screen_extra = patient.draws["screen"]  # type: ignore[attr-defined]
        alert_extra = 2.5 if (patient.screen_score or 0) >= self.scenario.alert_score() else 0.0
        clinical = patient.draws["nurse"] + screen_extra + review_extra + alert_extra  # type: ignore[attr-defined]
        if patient.urgent:
            clinical += 6
        wait, staff = yield from self._serve(
            "nurse",
            patient,
            clinical,
            patient.draws["doc"],  # type: ignore[attr-defined]
            "triage",
            f"Assessing {patient.id}",
            on_start=lambda: self._begin_nurse(patient, caregiver, staff_name="nurse"),
        )
        patient.nurse_wait = wait
        self.role_waits["nurse"].append(wait)
        apply_wait(patient, caregiver, wait)
        if wait >= 20:
            self._log(
                self.env.now - clinical,
                "nurse_delay",
                "delay",
                patient.id,
                f"{patient.id} waited {wait:.0f} min for a nurse",
                "Nurse capacity was below arrival pressure.",
            )
        if staff is not None:
            patient.interact(self.env.now, staff.name, "nurse_assessment")
            staff.interact(self.env.now, patient.id, "nurse_assessment")
            apply_supportive_interaction(patient, caregiver)

    def _begin_nurse(self, patient: PatientAgent, caregiver: CaregiverAgent, staff_name: str) -> None:
        if patient.machine.state != PatientState.NURSE_VISIT:
            patient.set_state(PatientState.NURSE_VISIT)
        patient.location = "triage"
        patient.current_task = "Nurse assessment"
        patient.next_task = "Oncology visit"
        patient.path.append("Nurse")
        patient.start_segment(self.env.now, "Nurse")
        self._cg(caregiver, CaregiverState.IN_VISIT, "triage", "In the nurse assessment", "Oncology visit")
        apply_complexity(patient)
        if self._should_offer(patient, "nurse"):
            self._offer_screen(patient, caregiver)
        if patient.pending_review == "nurse":
            self._resolve_review(patient, caregiver, "nurse")
        if (patient.screen_score or 0) >= self.scenario.alert_score():
            patient.current_task = "Nurse review of distress alert"

    def _oncology_stage(self, patient: PatientAgent, caregiver: CaregiverAgent):
        patient.set_state(PatientState.WAITING_FOR_ONCOLOGIST)
        patient.location = "waiting_room"
        patient.current_task = "Waiting for the oncologist"
        patient.next_task = "Oncology visit"
        self._cg(caregiver, CaregiverState.WAITING, "waiting_room", "Waiting for the oncologist", "Oncology visit")
        review_extra = 3.0 if patient.pending_review == "oncologist" else 0.0
        clinical = patient.draws["onc"] + review_extra + (8 if patient.urgent else 0)  # type: ignore[attr-defined]
        if clinical > self.scenario.mean_onc_visit_min * 1.65:
            self._log(
                self.env.now,
                "long_visit",
                "delay",
                patient.id,
                f"{patient.id} is booked for a long oncology visit ({clinical:.0f} min)",
                "Visit length was drawn from the upper tail of the log-normal distribution.",
            )
        wait, staff = yield from self._serve(
            "oncologist",
            patient,
            clinical,
            patient.draws["doc"],  # type: ignore[attr-defined]
            "oncology",
            f"Oncology visit with {patient.id}",
            on_start=lambda: self._begin_onc(patient, caregiver),
        )
        patient.onc_wait = wait
        self.role_waits["oncologist"].append(wait)
        apply_wait(patient, caregiver, wait * 0.8)
        if staff is not None:
            patient.interact(self.env.now, staff.name, "oncology_visit")
            apply_supportive_interaction(patient, caregiver)

    def _begin_onc(self, patient: PatientAgent, caregiver: CaregiverAgent) -> None:
        patient.set_state(PatientState.ONCOLOGY_VISIT)
        patient.location = "oncology"
        patient.current_task = "Oncology visit"
        patient.next_task = "Treatment" if patient.needs_treatment else "Discharge or psychosocial care"
        patient.path.append("Oncology")
        patient.start_segment(self.env.now, "Oncology")
        self._cg(caregiver, CaregiverState.IN_VISIT, "oncology", "In the oncology visit", "Next step")
        if patient.pending_review == "oncologist":
            self._resolve_review(patient, caregiver, "oncologist")
        self._clinician_recognition(patient, caregiver, "onc")

    def _treatment(self, patient: PatientAgent, caregiver: CaregiverAgent):
        patient.set_state(PatientState.TREATMENT)
        patient.location = "treatment"
        patient.current_task = "Treatment / procedure"
        patient.next_task = "Psychosocial care" if patient.referral_target else "Discharge"
        patient.path.append("Treatment")
        patient.start_segment(self.env.now, "Treatment")
        self._cg(caregiver, CaregiverState.WAITING, "waiting_room", "Waiting during treatment", "Rejoin the patient")
        duration = patient.draws["treatment"]  # type: ignore[attr-defined]
        self._log(self.env.now, "treatment_start", "clinical", patient.id, f"{patient.id} started treatment", "The visit plan includes a procedure today.")
        yield self.env.timeout(duration)
        patient.stress = clamp(patient.stress + 5 * patient.treatment_intensity - 3)
        self._log(self.env.now, "treatment_end", "clinical", patient.id, f"{patient.id} finished treatment", "Procedure time was sampled from a gamma distribution.")

    def _psychosocial(self, patient: PatientAgent, caregiver: CaregiverAgent):
        target = patient.referral_target
        pool_name = target if target in self.pools else "social_work"
        pool = self.pools[pool_name]
        patient.set_state(PatientState.WAITING_FOR_PSYCHOSOCIAL)
        zone = "child_life" if target == "child_life" else "psychosocial"
        patient.location = zone
        patient.current_task = f"Waiting for {target.replace('_', ' ')}"
        patient.next_task = "Psychosocial assessment"
        patient.goal = f"Be seen by {target.replace('_', ' ')} today"
        self._cg(caregiver, CaregiverState.PSYCHOSOCIAL, zone, "Waiting for psychosocial care", "Assessment")
        if pool.disabled:
            patient.left_before_psych = True
            patient.referral_deferred = True
            patient.remember(self.env.now, "no_psychosocial_capacity", target=target)
            self._log(
                self.env.now,
                "referral_deferred",
                "psychosocial",
                patient.id,
                f"No {target.replace('_', ' ')} on duty for {patient.id}",
                "The referral could not be staffed.",
            )
            return
        priority = 0 if patient.urgent else patient.priority
        if (patient.screen_score or 0) >= 8:
            priority = min(priority, 1)
        req = pool.resource.request(priority=priority)
        t0 = self.env.now
        patience = patient.draws["patience"]  # type: ignore[attr-defined]
        result = yield req | self.env.timeout(patience)
        wait = self.env.now - t0
        patient.psych_wait = wait
        self.role_waits[pool_name].append(wait)
        apply_wait(patient, caregiver, wait)
        if req not in result:
            req.cancel()
            patient.left_before_psych = True
            patient.referral_deferred = True
            patient.remember(self.env.now, "left_before_psychosocial", wait=round(wait, 1), target=target)
            caregiver.remember(self.env.now, "left_before_psychosocial", wait=round(wait, 1))
            self._log(
                self.env.now,
                "left_before_assessment",
                "psychosocial",
                patient.id,
                f"{patient.id} left before {target.replace('_', ' ')} assessment",
                f"Waited {wait:.0f} min, beyond the family's patience of {patience:.0f} min.",
            )
            return
        staff = pool.take()
        patient.set_state(PatientState.PSYCHOSOCIAL_VISIT)
        patient.path.append("Psychosocial")
        patient.start_segment(self.env.now, "Psychosocial")
        patient.current_task = f"{target.replace('_', ' ').title()} assessment"
        patient.location = zone
        if staff.machine.can(StaffState.WITH_PATIENT):
            staff.set_state(StaffState.WITH_PATIENT)
        staff.location = zone
        staff.current_task = f"Seeing {patient.id}"
        staff.patients_seen += 1
        self._bump_staff(staff, pool_name)
        service = patient.draws[target if target in patient.draws else "social_work"]  # type: ignore[attr-defined]
        self._log(
            self.env.now,
            "psych_start",
            "psychosocial",
            patient.id,
            f"{staff.name} started an assessment with {patient.id}",
            patient.referral_reason or "Referral reached the front of the queue.",
        )
        started = self.env.now
        yield self.env.timeout(service)
        patient.referral_completed = True
        patient.received_support = True
        apply_support(patient, caregiver, target)
        patient.interact(self.env.now, staff.name, target)
        staff.interact(self.env.now, patient.id, target)
        patient.remember(self.env.now, "psychosocial_support", target=target)
        caregiver.remember(self.env.now, "psychosocial_support", target=target)
        self._log(
            self.env.now,
            "psych_end",
            "psychosocial",
            patient.id,
            f"Assessment completed for {patient.id}",
            f"{target.replace('_', ' ').title()} visit lasted {service:.0f} min.",
        )
        self.env.process(self._finish(pool, staff, req, patient.draws["doc"], started))  # type: ignore[attr-defined]

    def _serve(self, pool_name: str, patient: PatientAgent, clinical: float, doc: float, location: str, task: str, on_start=None):
        pool = self.pools[pool_name]
        priority = 0 if patient.urgent else patient.priority
        req = pool.resource.request(priority=priority)
        t0 = self.env.now
        yield req
        wait = self.env.now - t0
        staff = pool.take()
        if patient.urgent and staff.machine.can(StaffState.URGENT_CASE):
            staff.set_state(StaffState.URGENT_CASE)
        elif staff.machine.can(StaffState.WITH_PATIENT):
            staff.set_state(StaffState.WITH_PATIENT)
        staff.location = location
        staff.current_task = task
        staff.next_task = "Document"
        staff.availability = "busy"
        staff.patients_seen += 1
        self._bump_staff(staff, pool_name)
        if on_start:
            on_start()
        started = self.env.now
        yield self.env.timeout(max(0.5, clinical))
        self.env.process(self._finish(pool, staff, req, doc, started))
        return wait, staff

    def _finish(self, pool: StaffPool, staff: StaffAgent, req, doc: float, started: float):
        try:
            if staff.machine.can(StaffState.DOCUMENTING):
                staff.set_state(StaffState.DOCUMENTING)
            staff.location = "staff"
            staff.current_task = "Documenting"
            staff.next_task = "Next patient"
            if doc > 0:
                yield self.env.timeout(doc)
        finally:
            end = self.env.now
            staff.busy_minutes += max(0.0, end - started)
            if getattr(staff, "first_busy", None) is None:
                staff.first_busy = started
            staff.last_busy = end
            if end > self.close:
                staff.overtime_minutes += end - max(started, self.close)
            pool.give(staff)
            if req in pool.resource.users:
                pool.resource.release(req)

    def _provider_delay(self, pool: StaffPool, minutes: float):
        person = next((s for s in pool.staff if s.id == "O1"), None)
        if person is None:
            return
        req = pool.resource.request(priority=-1)
        yield req
        if person not in pool.free:
            pool.resource.release(req)
            return
        pool.free.remove(person)
        if person.machine.can(StaffState.BREAK):
            person.set_state(StaffState.BREAK)
        person.current_task = "Running late from inpatient rounds"
        person.next_task = "Start clinic"
        person.availability = "busy"
        self._log(
            0,
            "provider_late",
            "staff",
            person.id,
            f"{person.name} is {minutes:.0f} min late",
            "Inpatient rounds ran long before clinic.",
        )
        yield self.env.timeout(minutes)
        person.busy_minutes += minutes
        pool.give(person)
        pool.resource.release(req)

    def _should_offer(self, patient: PatientAgent, where: str) -> bool:
        if patient.screen_offered or patient.screen_completed or patient.screen_declined:
            return False
        selective = self.scenario.predictive_mode == "selective" and not self.scenario.screening_enabled
        if selective:
            return where == "check_in" and patient.predicted_risk >= SELECTIVE_CUTOFF
        if not self.scenario.screening_enabled:
            return False
        return where == self.scenario.screening_location

    def _offer_screen(self, patient: PatientAgent, caregiver: CaregiverAgent) -> float:
        """Return minutes to add to the current stage. Portal screens add none."""
        patient.screen_offered = True
        decline_p = screening_decline_probability(
            base=self.scenario.decline_rate,
            language_support=patient.language_support,
            stress=caregiver.stress,
            privacy_concern=caregiver.privacy_concern,
            prior_experience=caregiver.prior_screening_experience,
        )
        environment = {"wait_so_far": patient.admin_wait + patient.nurse_wait, "queues": self._queues()}
        agent_state = {
            "decision": "screening",
            "decline_probability": decline_p,
            "decline_roll": patient.draws["decline_roll"],  # type: ignore[attr-defined]
            "stress": caregiver.stress,
            "language_support": patient.language_support,
            "prior_screening_experience": caregiver.prior_screening_experience,
            "memory": caregiver.memory_dicts(),
        }
        choice = self._decision(agent_state, environment)
        duration = 0.0 if self.scenario.screening_location == "portal" else float(patient.draws["screen"])  # type: ignore[attr-defined]
        if not choice.get("accept", False):
            patient.screen_declined = True
            caregiver.remember(self.env.now, "caregiver_declined_screening", reason=choice.get("reason", "privacy_concern"))
            patient.remember(self.env.now, "caregiver_declined_screening", reason=choice.get("reason", "privacy_concern"))
            self._log(
                self.env.now,
                "screening_declined",
                "psychosocial",
                patient.id,
                f"{caregiver.name} declined distress screening for {patient.id}",
                choice.get("explanation", "The caregiver declined screening."),
            )
            return 0.0
        if patient.draws["incomplete_roll"] > self.scenario.screening_completion_rate:  # type: ignore[attr-defined]
            patient.screen_incomplete = True
            self._log(
                self.env.now,
                "screening_incomplete",
                "psychosocial",
                patient.id,
                f"Distress screen for {patient.id} was not finished",
                "The form was started but not completed.",
            )
            return duration * 0.45
        raw = clamp(patient.baseline_distress + patient.draws["screen_noise"], 0, 10)  # type: ignore[attr-defined]
        disclosed = self._decision(
            {
                "decision": "disclosure",
                "disclosure_roll": patient.draws.get("disclosure_roll", 0.9),  # type: ignore[attr-defined]
                "language_support": patient.language_support,
                "privacy_concern": caregiver.privacy_concern,
                "stress": caregiver.stress,
                "latent_distress": round(patient.baseline_distress, 1),
            },
            environment,
        )
        withheld = {"full": 0.0, "partial": 1.0, "minimal": 2.2}.get(str(disclosed.get("level")), 0.0)
        score = int(round(clamp(raw - withheld, 0, 10)))
        patient.screen_completed = True
        patient.screen_score = score
        patient.disclosure = str(disclosed.get("level") or "full")
        patient.screen_minutes = float(patient.draws["screen"])  # type: ignore[attr-defined]
        patient.screen_category = band_for_score(score)
        patient.current_distress = float(score)
        where = "before arrival on the portal" if self.scenario.screening_location == "portal" and not self.scenario.screening_enabled is False else self.scenario.screening_location.replace("_", " ")
        if self.scenario.predictive_mode == "selective" and not self.scenario.screening_enabled:
            where = "check-in after a risk flag"
        self._log(
            self.env.now,
            "screening_completed",
            "psychosocial",
            patient.id,
            f"{patient.id} completed distress screening ({where})",
            "A short distress screen was offered at the configured point in the visit.",
            {"score": score},
        )
        self._log(
            self.env.now,
            "distress_score",
            "psychosocial",
            patient.id,
            f"Distress score {score}/10 for {patient.id} ({patient.screen_category})",
            f"Latent distress {patient.baseline_distress:.1f}, measurement noise, and {patient.disclosure} disclosure.",
            {"score": score, "category": patient.screen_category},
        )
        if score >= self.scenario.alert_score():
            self.alerts += 1
            patient.detected = True
            self._log(
                self.env.now,
                "alert",
                "alert",
                patient.id,
                f"Distress alert for {patient.id}",
                f"Score {score}/10 reached the {self.scenario.alert_threshold} alert threshold.",
                {"score": score},
            )
            patient.remember(self.env.now, "distress_alert", score=score)
        if score >= self.scenario.referral_threshold:
            mode = self.scenario.referral_mode
            if mode in {"automatic", "learned"}:
                if mode == "learned" and self.policy is not None:
                    queue = len(self.pools["social_work"].resource.queue)
                    action = self.policy.choose(score, queue)
                    self.policy.note(score, queue, action, patient.id)
                    if action != "refer":
                        self._log(
                            self.env.now,
                            "monitor",
                            "clinical",
                            patient.id,
                            f"Learned policy kept {patient.id} on watch",
                            f"Score {score}/10 with a social-work queue of {queue} was not referred.",
                        )
                        return duration
                if float(patient.draws.get("uptake_roll", 0.0)) > self.scenario.referral_uptake:  # type: ignore[attr-defined]
                    self._log(
                        self.env.now,
                        "referral_deferred",
                        "psychosocial",
                        patient.id,
                        f"A positive screen for {patient.id} was not taken up",
                        "The score met the threshold, but the referral was not opened.",
                    )
                    return duration
                target = self._route(patient, score)
                self._create_referral(
                    patient,
                    caregiver,
                    target,
                    f"Distress score {score}/10 met the referral threshold of {self.scenario.referral_threshold}. Pathway: automatic psychosocial referral.",
                    route_name="screening",
                )
            else:
                patient.pending_review = {
                    "nurse_review": "nurse",
                    "oncologist_review": "oncologist",
                    "central_triage": "triage",
                }[mode]
                self._log(
                    self.env.now,
                    "review_pending",
                    "alert",
                    patient.id,
                    f"{patient.id} score {score}/10 is waiting for {patient.pending_review.replace('_', ' ')}",
                    f"Referral mode is {mode.replace('_', ' ')}, so the score is not routed automatically.",
                )
        return duration

    def _resolve_review(self, patient: PatientAgent, caregiver: CaregiverAgent, reviewer: str) -> None:
        if patient.referral_target or patient.pending_review != reviewer:
            return
        score = int(patient.screen_score or 0)
        queues = self._queues()
        agent_state = {
            "decision": "nurse" if reviewer != "triage" else "triage",
            "score": score,
            "age": patient.age,
            "anxiety": patient.anxiety,
            "threshold": self.scenario.referral_threshold,
            "monitor_roll": patient.draws["monitor_roll"],  # type: ignore[attr-defined]
            "memory": patient.memory_dicts(),
            "patient_id": patient.id,
        }
        environment = {"queues": queues, "reviewer": reviewer}
        if reviewer == "triage":
            decision = self._decision({**agent_state, "decision": "triage"}, environment)
            target = decision.get("target", "defer")
            explanation = decision.get("explanation", "Central triage reviewed the score.")
            if target == "defer":
                patient.pending_review = ""
                self._log(self.env.now, "triage_deferred", "psychosocial", patient.id, f"Triage deferred a referral for {patient.id}", explanation)
                return
            self._create_referral(patient, caregiver, target, explanation, route_name="central_triage")
            return
        decision = self._decision(agent_state, environment)
        action = decision.get("action", "monitor")
        explanation = decision.get("explanation", "The clinician reviewed the distress alert.")
        patient.pending_review = ""
        if action == "monitor":
            self._log(self.env.now, "monitor", "clinical", patient.id, f"{reviewer.title()} chose to monitor {patient.id}", explanation)
            patient.remember(self.env.now, "monitored", reviewer=reviewer, score=score)
            return
        target = {
            "refer_social_work": "social_work",
            "refer_psychology": "psychology",
            "refer_child_life": "child_life",
            "urgent_review": "psychology" if self.scenario.n_psychologists else "social_work",
        }.get(action, "social_work")
        if action == "urgent_review":
            patient.priority = 0
        self._create_referral(patient, caregiver, target, explanation, route_name=f"{reviewer}_review")

    def _central_triage(self, patient: PatientAgent, caregiver: CaregiverAgent):
        pool = self.pools["coordinator"]
        patient.location = "staff"
        caregiver.location = "staff"
        patient.current_task = "Waiting for psychosocial triage"
        req = pool.resource.request(priority=patient.priority)
        yield req
        staff = pool.take()
        if staff.machine.can(StaffState.REVIEWING):
            staff.set_state(StaffState.REVIEWING)
        staff.current_task = f"Triaging {patient.id}"
        started = self.env.now
        yield self.env.timeout(patient.draws["triage_admin"])  # type: ignore[attr-defined]
        self._resolve_review(patient, caregiver, "triage")
        staff.busy_minutes += self.env.now - started
        pool.give(staff)
        pool.resource.release(req)
        patient.location = "waiting_room"
        caregiver.location = "waiting_room"

    def _clinician_recognition(self, patient: PatientAgent, caregiver: CaregiverAgent, who: str) -> None:
        if patient.referral_target:
            return
        roll_key = "detect_nurse" if who == "nurse" else "detect_onc"
        roll = patient.draws[roll_key]  # type: ignore[attr-defined]
        if roll < _detection_probability(patient):
            target = self._route(patient, max(6, int(round(patient.baseline_distress))))
            self._create_referral(
                patient,
                caregiver,
                target,
                f"The {who if who != 'onc' else 'oncologist'} recognized distress that screening had not already referred.",
                route_name=f"clinician_{who}",
            )
            return
        request_p = 0.02 + (0.16 if caregiver.stress >= 82 else 0.0)
        if patient.draws["request_roll"] < request_p:  # type: ignore[attr-defined]
            target = self._route(patient, max(5, int(round(patient.baseline_distress))))
            self._create_referral(
                patient,
                caregiver,
                target,
                "The caregiver asked for psychosocial support during the visit.",
                route_name="caregiver_request",
            )
            return
        if patient.prior_psychosocial and patient.draws["existing_roll"] < 0.18:  # type: ignore[attr-defined]
            target = self._route(patient, max(4, int(round(patient.baseline_distress))))
            self._create_referral(
                patient,
                caregiver,
                target,
                "An existing psychosocial referral was already on the chart.",
                route_name="existing_referral",
            )

    def _route(self, patient: PatientAgent, score: int) -> str:
        if score >= 9 and self.scenario.n_psychologists and patient.draws["psych_route"] < 0.55:  # type: ignore[attr-defined]
            return "psychology"
        if patient.age <= 6 and score >= 5 and self.scenario.n_child_life and patient.draws["child_life_route"] < 0.4:  # type: ignore[attr-defined]
            return "child_life"
        if score >= 8 and patient.anxiety >= 0.75 and self.scenario.n_psychologists and patient.draws["psych_route"] < 0.45:  # type: ignore[attr-defined]
            return "psychology"
        if self.scenario.n_social_workers:
            return "social_work"
        if self.scenario.n_psychologists:
            return "psychology"
        if self.scenario.n_child_life:
            return "child_life"
        return ""

    def _create_referral(self, patient: PatientAgent, caregiver: CaregiverAgent, target: str, reason: str, route_name: str) -> None:
        if patient.referral_target or not target:
            if not target and not patient.referral_target:
                patient.referral_deferred = True
            return
        if target == "social_work" and self.pools["social_work"].disabled:
            target = "psychology" if not self.pools["psychology"].disabled else target
        if target == "psychology" and self.pools["psychology"].disabled:
            target = "social_work" if not self.pools["social_work"].disabled else target
        pool = self.pools.get(target)
        if pool is None or pool.disabled:
            patient.referral_deferred = True
            self._log(self.env.now, "referral_deferred", "psychosocial", patient.id, f"Referral for {patient.id} could not be placed", "No staffed psychosocial service was available.")
            return
        patient.referral_target = target
        patient.referral_reason = reason
        patient.identified = True
        patient.detected = True
        patient.identification_route = patient.identification_route or route_name
        patient.false_positive_referral = not patient.high_need
        patient.pending_review = ""
        if self.scenario.predictive_mode == "prioritize":
            patient.priority = min(patient.priority, 1 if patient.predicted_risk >= 0.55 else 3)
        label = target.replace("_", " ")
        self._log(
            self.env.now,
            "referral_created",
            "psychosocial",
            patient.id,
            f"{label.title()} referral created for {patient.id}",
            reason,
            {"target": target, "route": route_name},
        )
        patient.remember(self.env.now, "referral_created", target=target, route=route_name)
        patient.next_task = f"See {label}"

    def _decision(self, agent_state: dict, environment: dict) -> dict:
        try:
            return self.engine.decide(agent_state, environment)
        except Exception:
            return self.rules.decide(agent_state, environment)

    def _bump_staff(self, staff: StaffAgent, pool_name: str) -> None:
        queue = len(self.pools[pool_name].resource.queue)
        staff_stress(
            staff,
            queue=queue,
            urgent=staff.state == StaffState.URGENT_CASE.value,
            interruption=queue >= 3,
            overtime=max(0.0, self.env.now - self.close),
        )
        if queue >= 4 and staff.machine.can(StaffState.OVERLOADED):
            staff.set_state(StaffState.OVERLOADED)
        staff.queue_seen_peak = max(staff.queue_seen_peak, queue)

    def _discharge(self, patient: PatientAgent, caregiver: CaregiverAgent, forced: bool = False) -> None:
        if patient.discharge_time is not None:
            return
        if not hasattr(patient, "path"):
            patient.path = ["Arrival"]
        if patient.machine.state != PatientState.DISCHARGED:
            if patient.machine.can(PatientState.DISCHARGED):
                patient.set_state(PatientState.DISCHARGED)
            else:
                # A forced close can interrupt a wait. Step through only if legal; otherwise mark fields.
                patient.machine.state = PatientState.DISCHARGED
                patient.machine.history.append(PatientState.DISCHARGED.value)
        patient.close_segment(self.env.now)
        if patient.left_before_psych:
            patient.path.append("Left early")
        else:
            patient.path.append("Exit")
        patient.location = "exit"
        patient.current_task = "Discharged"
        patient.next_task = "Leave the clinic"
        patient.discharge_time = round(self.env.now, 2)
        patient.cycle_time = max(0.0, self.env.now - patient.arrival_time)
        if caregiver.machine.can(CaregiverState.DISCHARGED):
            caregiver.set_state(CaregiverState.DISCHARGED)
        else:
            caregiver.machine.state = CaregiverState.DISCHARGED
        caregiver.location = "exit"
        caregiver.current_task = "Leaving with the patient"
        caregiver.next_task = "Travel home"
        patient.identified = bool(patient.referral_target) or patient.received_support
        if patient.high_need and not patient.received_support and not patient.referral_target:
            patient.missed = True
            patient.missed_reason = _missed_reason(patient, self.scenario)
        elif patient.high_need and not patient.received_support:
            patient.unserved = True
            apply_unresolved(patient, caregiver)
        if patient.missed:
            self._log(
                self.env.now,
                "need_missed",
                "psychosocial",
                patient.id,
                f"Psychosocial need missed for {patient.id}",
                patient.missed_reason,
            )
        reason = "Forced close at the end of the simulated horizon." if forced else "Clinical steps for today are finished."
        if patient.left_before_psych:
            reason = "The family left before psychosocial care, then finished the clinical visit pathway."
        self._log(self.env.now, "discharged", "patient", patient.id, f"{patient.id} discharged", reason, {"missed": patient.missed, "high_need": patient.high_need})

    def _cg(self, caregiver: CaregiverAgent, state: CaregiverState, location: str, task: str, nxt: str) -> None:
        if caregiver.machine.state != state:
            if caregiver.machine.can(state):
                caregiver.set_state(state)
            else:
                caregiver.machine.state = state
        caregiver.location = location
        caregiver.current_task = task
        caregiver.next_task = nxt

    def _monitor(self):
        while self.env.now < self.horizon:
            self._capture()
            if self._done():
                break
            yield self.env.timeout(1)
        self._capture()

    def _done(self) -> bool:
        return all(p.location == "departed" for p in self.patients)

    def _capture(self) -> None:
        queues = self._queues()
        elapsed = max(1.0, self.env.now)
        occupancy = {}
        utilization = {}
        saturated = False
        for name, pool in self.pools.items():
            cap = max(1, len(pool.staff))
            busy = 0 if pool.disabled else cap - len(pool.free)
            occupancy[name] = round(busy / cap, 3) if pool.staff else 0.0
            role_staff = pool.staff
            busy_min = sum(s.busy_minutes for s in role_staff)
            utilization[name] = round(busy_min / (elapsed * cap), 3) if role_staff else 0.0
            if pool.staff and occupancy[name] >= 0.8 and name in {"nurse", "oncologist", "social_work", "psychology", "child_life"}:
                saturated = True
        if saturated and self.env.now <= self.close:
            self.above_80_minutes += 1
        if not self.trace:
            return
        discharged = [p for p in self.patients if p.discharge_time is not None]
        need_discharged = [p for p in discharged if p.high_need]
        waits = [p.admin_wait + p.nurse_wait + p.onc_wait for p in self.patients if p.onc_wait > 0 or p.discharge_time is not None]
        self.frames.append(
            {
                "t": round(self.env.now, 2),
                "queues": queues,
                "occupancy": occupancy,
                "utilization": utilization,
                "live": {
                    "arrived": sum(1 for p in self.patients if p.arrival_time <= self.env.now),
                    "discharged": len(discharged),
                    "in_clinic": sum(1 for p in self.patients if p.arrival_time <= self.env.now and p.location != "departed"),
                    "screened": sum(1 for p in self.patients if p.screen_completed),
                    "declined": sum(1 for p in self.patients if p.screen_declined),
                    "referrals": sum(1 for p in self.patients if p.referral_target),
                    "with_need": sum(1 for p in self.patients if p.high_need),
                    "identified": sum(1 for p in need_discharged if p.identified) if False else sum(1 for p in self.patients if p.high_need and p.identified),
                    "missed": sum(1 for p in need_discharged if p.missed),
                    "supported": sum(1 for p in self.patients if p.received_support),
                    "mean_wait": round(sum(waits) / len(waits), 1) if waits else 0.0,
                    "alerts": self.alerts,
                    "psych_queue": queues.get("social_work", 0) + queues.get("psychology", 0) + queues.get("child_life", 0),
                },
                "agents": [_compact(agent) for agent in self._agents()],
            }
        )

    def _agents(self):
        yield from self.patients
        yield from self.caregivers.values()
        yield from self.staff

    def _result(self) -> dict:
        metrics = compute_metrics(
            self.patients,
            self.staff,
            self.scenario,
            self.peaks,
            self.role_waits,
            self.alerts,
            self.above_80_minutes,
            max(1.0, self.env.now),
        )
        bottleneck = detect_bottleneck(metrics, self.scenario)
        self._log(self.env.now, "clinic_close", "system", None, "Clinic day complete", bottleneck["interpretation"])
        roster = [_patient_public(p, self.caregivers[p.id]) for p in self.patients]
        staff_public = [_staff_public(s) for s in self.staff]
        return {
            "scenario": self.scenario.model_dump(),
            "seed": self.scenario.seed,
            "horizon": round(self.frames[-1]["t"] if self.frames else self.env.now, 2),
            "open_hour": self.scenario.open_hour,
            "frames": self.frames,
            "events": self.events,
            "metrics": metrics,
            "bottleneck": bottleneck,
            "funnel": referral_funnel(self.patients),
            "sankey": sankey_from_paths([getattr(p, "path", []) for p in self.patients]),
            "patients": roster,
            "staff": staff_public,
            "gantt": [
                {"id": p.id, "name": p.name, "segments": p.segments}
                for p in self.patients
            ],
        }


def run_simulation(scenario: ScenarioConfig, trace: bool = True, policy: Any | None = None) -> dict:
    if policy is None and scenario.referral_mode == "learned":
        from app.rl.manager import active_policy

        policy = active_policy()
    return ClinicSimulation(scenario, trace=trace, policy=policy).run()


def _heuristic_risk(patient: PatientAgent, caregiver: CaregiverAgent) -> float:
    import math

    z = (
        -3.55
        + 0.47 * patient.chart_distress
        + 1.15 * patient.symptom_burden
        + 0.75 * patient.treatment_intensity
        + 0.017 * caregiver.stress
        + 0.5 * patient.travel_burden
        + (0.62 if patient.visit_type == "new" else 0.0)
        + (0.35 if patient.prior_psychosocial else 0.0)
        + 0.012 * patient.previous_wait_min
        + 0.35 * patient.complexity
    )
    return 1.0 / (1.0 + math.exp(-z))


def _detection_probability(patient: PatientAgent) -> float:
    """Observation is real, but much less sensitive than a structured screen."""
    distress = patient.baseline_distress
    if distress >= 9.2:
        base = 0.22
    elif distress >= 6.4:
        base = 0.12
    elif distress >= 4:
        base = 0.04
    else:
        base = 0.01
    if patient.urgent:
        base += 0.05
    return min(0.4, base)


def _missed_reason(patient: PatientAgent, scenario: ScenarioConfig) -> str:
    parts = ["High underlying psychosocial need."]
    if patient.screen_declined:
        parts.append("Screening was declined.")
    elif patient.screen_incomplete:
        parts.append("The screening form was incomplete, so no score was recorded.")
    elif patient.screen_completed and patient.screen_score is not None and patient.screen_score < scenario.referral_threshold:
        parts.append(
            f"Distress score {patient.screen_score}/10 was below the referral threshold of {scenario.referral_threshold}."
        )
    elif not patient.screen_completed and not scenario.screening_enabled and scenario.predictive_mode != "selective":
        parts.append("No systematic screening was in place.")
    elif not patient.screen_completed:
        parts.append("Screening was not completed.")
    if any(item.event == "monitored" for item in patient.memory):
        parts.append("A clinician reviewed the concern and chose to monitor.")
    else:
        parts.append("Clinician recognition did not create a referral.")
    parts.append("The family left without a psychosocial referral or assessment.")
    return " ".join(parts)


def _compact(agent) -> dict:
    payload = {
        "id": agent.id,
        "role": agent.role,
        "loc": agent.location,
        "state": agent.state,
        "stress": round(float(agent.stress), 1),
        "workload": round(float(getattr(agent, "workload", 0.0)), 1),
        "task": agent.current_task,
        "next": agent.next_task,
        "availability": agent.availability,
    }
    if isinstance(agent, PatientAgent):
        payload["distress"] = round(float(agent.current_distress), 1)
        payload["score"] = agent.screen_score
    if isinstance(agent, CaregiverAgent):
        payload["distress"] = round(float(agent.distress), 1)
        payload["patient_id"] = agent.patient_id
    return payload


def _patient_public(patient: PatientAgent, caregiver: CaregiverAgent) -> dict:
    return {
        "id": patient.id,
        "name": patient.name,
        "role": "patient",
        "age": patient.age,
        "sex": patient.sex,
        "visit_type": patient.visit_type,
        "cancer_category": patient.cancer_category,
        "treatment_phase": patient.treatment_phase,
        "treatment_intensity": patient.treatment_intensity,
        "symptom_burden": patient.symptom_burden,
        "baseline_distress": patient.baseline_distress,
        "chart_distress": patient.chart_distress,
        "psychosocial_need": patient.psychosocial_need,
        "high_need": patient.high_need,
        "complexity": patient.complexity,
        "travel_category": patient.travel_category,
        "language_support": patient.language_support,
        "appointment_time": patient.appointment_time,
        "arrival_time": patient.arrival_time,
        "discharge_time": patient.discharge_time,
        "urgent": patient.urgent,
        "predicted_risk": patient.predicted_risk,
        "goal": patient.goal,
        "screen_score": patient.screen_score,
        "screen_category": patient.screen_category,
        "screen_minutes": patient.screen_minutes,
        "disclosure": patient.disclosure,
        "screen_completed": patient.screen_completed,
        "screen_declined": patient.screen_declined,
        "screen_incomplete": patient.screen_incomplete,
        "identified": patient.identified,
        "identification_route": patient.identification_route,
        "referral_target": patient.referral_target,
        "referral_reason": patient.referral_reason,
        "referral_completed": patient.referral_completed,
        "left_before_psych": patient.left_before_psych,
        "missed": patient.missed,
        "missed_reason": patient.missed_reason,
        "received_support": patient.received_support,
        "false_positive_referral": patient.false_positive_referral,
        "waits": {
            "admin": round(patient.admin_wait, 1),
            "nurse": round(patient.nurse_wait, 1),
            "oncologist": round(patient.onc_wait, 1),
            "psychosocial": round(patient.psych_wait, 1),
        },
        "cycle_time": round(patient.cycle_time, 1),
        "interactions": patient.interactions,
        "memory": patient.memory_dicts(),
        "schedule": patient.schedule,
        "caregiver": {
            "id": caregiver.id,
            "name": caregiver.name,
            "relationship": caregiver.relationship,
            "stress": round(caregiver.stress, 1),
            "distress": round(caregiver.distress, 1),
            "travel_category": caregiver.travel_category,
            "goal": caregiver.goal,
            "memory": caregiver.memory_dicts(),
            "privacy_concern": caregiver.privacy_concern,
        },
    }


def _staff_public(staff: StaffAgent) -> dict:
    return {
        "id": staff.id,
        "name": staff.name,
        "role": staff.role,
        "goal": staff.goal,
        "on_duty": staff.on_duty,
        "patients_seen": staff.patients_seen,
        "busy_minutes": round(staff.busy_minutes, 1),
        "overtime_minutes": round(staff.overtime_minutes, 1),
        "stress": round(staff.stress, 1),
        "workload": round(staff.workload, 1),
        "interactions": staff.interactions,
        "memory": staff.memory_dicts(),
        "final_task": staff.current_task,
        "final_state": staff.state,
    }


def _detection_export_probability(patient: PatientAgent) -> float:
    return _detection_probability(patient)
