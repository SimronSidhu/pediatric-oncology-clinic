"""Calibration, persona audit, surrogate search, and the learned referral policy."""

from app.calibration.fit import calibrate, distance, operational_summary
from app.evaluation.audit import persona_audit
from app.rl.manager import train_and_compare
from app.schemas.scenario import ScenarioConfig
from app.services.decisions import RuleBasedDecisionEngine
from app.simulation.engine import run_simulation
from app.surrogate.search import search


def test_full_disclosure_is_the_default_when_nothing_is_guarded():
    choice = RuleBasedDecisionEngine().disclosure_choice(
        {"disclosure_roll": 0.5, "language_support": False, "privacy_concern": 0.2, "stress": 30}
    )
    assert choice.level == "full"


def test_language_alone_does_not_move_the_rule():
    report = persona_audit(use_model=False, pairs=8)
    assert report["n_pairs"] == 8
    assert report["rule_outcomes_differ"] is False
    assert all(row["english_rules"] == row["punjabi_rules"] for row in report["rows"])


def test_calibration_averages_replicates_and_returns_a_posterior():
    scenario = ScenarioConfig(seed=3, n_patients=8, screening_enabled=True)
    report = calibrate(scenario, draws=6, n_patients=8, seed=3, replicates=2)
    assert report["replicates"] == 2
    assert report["kept"] >= 4
    assert report["suggested"]["referral_uptake"] <= 1
    day = run_simulation(scenario, trace=False)
    assert distance(operational_summary(day)) >= 0


def test_surrogate_search_returns_a_simulated_policy():
    report = search(ScenarioConfig(seed=4), initial=4, steps=2, n_patients=8, seed=4, replicates=1)
    assert report["evaluations"] == 6
    assert report["candidates"] > report["evaluations"]
    assert "utility" in report["best"]


def test_learned_policy_compares_against_the_cutoff():
    report = train_and_compare(ScenarioConfig(seed=6), episodes=4, eval_runs=2, n_patients=8, seed=6)
    assert len(report["learning_curve"]) == 4
    assert report["evaluation"]["runs"] == 2
    assert "learned_wins" in report["evaluation"]
    assert any(row["action"] == "refer" for row in report["policy"])


def test_score_check_compares_the_full_distribution():
    from app.evaluation.audit import distress_fit

    report = distress_fit(ScenarioConfig(seed=5, n_patients=30), n_patients=30)
    assert len(report["bins"]) == 11
    assert 0 <= report["total_variation"] <= 1
    assert "share_at_least_4" in report


def test_shifted_cohort_is_scored_separately():
    from app.ml.model import train_model

    report = train_model(n=240, seed=5)
    assert report["shifted"]["n_encounters"] >= 200
    assert report["shifted"]["models"][0]["roc_auc"] >= 0
