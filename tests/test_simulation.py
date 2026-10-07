"""Clinic-day behaviour, screening contrast, and decision validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agents.states import PATIENT_TRANSITIONS, PatientState, StateMachine
from app.presets import preset
from app.schemas.scenario import ScenarioConfig
from app.services.decisions import NurseDecision, RuleBasedDecisionEngine, sanitize_nurse_decision
from app.simulation.engine import run_simulation
from app.synthetic_data.generator import build_population
from numpy.random import default_rng


def test_patient_flow_reaches_discharge():
    result = run_simulation(ScenarioConfig(seed=17, n_patients=12), trace=False)
    assert result["metrics"]["throughput"] == 12
    assert all(patient["discharge_time"] is not None for patient in result["patients"])


def test_same_seed_is_deterministic():
    scenario = ScenarioConfig(seed=17, n_patients=10)
    first = run_simulation(scenario, trace=False)["metrics"]
    second = run_simulation(scenario, trace=False)["metrics"]
    assert first == second


def test_screening_detects_more_and_loads_social_work():
    baseline = run_simulation(preset("baseline"), trace=False)["metrics"]
    screened = run_simulation(preset("universal"), trace=False)["metrics"]
    extra = run_simulation(preset("extra_social_worker"), trace=False)["metrics"]
    assert screened["identified"] > baseline["identified"]
    assert screened["missed"] < baseline["missed"]
    assert screened["referrals"] > baseline["referrals"]
    assert screened["utilization"]["social_work"] > baseline["utilization"]["social_work"]
    assert extra["left_before_psych"] < screened["left_before_psych"]
    assert extra["mean_psych_wait"] < screened["mean_psych_wait"]
    assert extra["supported"] >= screened["supported"]


def test_missed_families_have_a_reason():
    result = run_simulation(preset("baseline"), trace=False)
    missed = [patient for patient in result["patients"] if patient["missed"]]
    assert missed
    assert all(patient["missed_reason"] for patient in missed)
    assert all(patient["high_need"] for patient in missed)


def test_resource_wait_grows_when_nurse_capacity_is_tight():
    tight = ScenarioConfig(seed=4, n_patients=16, n_nurses=1, appointment_spacing_min=12, screening_enabled=False)
    slack = tight.model_copy(update={"n_nurses": 4})
    tight_wait = run_simulation(tight, trace=False)["metrics"]["mean_role_wait"]["nurse"]
    slack_wait = run_simulation(slack, trace=False)["metrics"]["mean_role_wait"]["nurse"]
    assert tight_wait > slack_wait


def test_illegal_patient_transition_is_rejected():
    machine = StateMachine(PatientState.SCHEDULED, PATIENT_TRANSITIONS)
    with pytest.raises(ValueError):
        machine.transition(PatientState.DISCHARGED)


def test_nurse_decision_schema_rejects_unknown_actions():
    with pytest.raises(ValidationError):
        NurseDecision.model_validate({"action": "discharge_home", "priority": 1, "explanation": "no"})


def test_severe_score_cannot_be_monitored():
    with pytest.raises(ValueError):
        sanitize_nurse_decision(
            {"action": "monitor", "priority": 3, "explanation": "Wait and see despite the score."},
            score=9,
        )


def test_rule_engine_refers_high_scores():
    decision = RuleBasedDecisionEngine().nurse_decision(
        {"score": 8, "age": 11, "anxiety": 0.2, "threshold": 3, "monitor_roll": 0.9},
        {"queues": {"social_work": 0}},
    )
    assert decision.action == "refer_social_work"
    assert "8" in decision.explanation


def test_synthetic_population_is_correlated():
    scenario = ScenarioConfig(seed=5, n_patients=80, screening_enabled=False)
    patients, caregivers, _staff = build_population(scenario, default_rng(5))
    new = [p.treatment_intensity for p in patients if p.visit_type == "new"]
    follow = [p.treatment_intensity for p in patients if p.visit_type != "new"]
    rural = [caregivers[p.id].stress for p in patients if p.travel_category == "long_distance"]
    local = [caregivers[p.id].stress for p in patients if p.travel_category == "local"]
    intense = [p.symptom_burden for p in patients if p.treatment_intensity >= 0.7]
    mild = [p.symptom_burden for p in patients if p.treatment_intensity <= 0.4]
    new_distress = [p.baseline_distress for p in patients if p.visit_type == "new"]
    follow_distress = [p.baseline_distress for p in patients if p.visit_type != "new"]
    assert sum(new) / len(new) > sum(follow) / len(follow)
    assert sum(rural) / len(rural) > sum(local) / len(local)
    assert sum(intense) / len(intense) > sum(mild) / len(mild)
    assert sum(new_distress) / len(new_distress) > sum(follow_distress) / len(follow_distress)


def test_fixed_seed_population_is_stable():
    scenario = ScenarioConfig(seed=9, n_patients=8)
    first, _, _ = build_population(scenario, default_rng(9))
    second, _, _ = build_population(scenario, default_rng(9))
    assert [p.baseline_distress for p in first] == [p.baseline_distress for p in second]
    assert [p.name for p in first] == [p.name for p in second]
