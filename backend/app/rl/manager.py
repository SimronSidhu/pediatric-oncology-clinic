"""Episodic Q-learning for the referral decision, compared with a fixed cutoff.

State is the distress band and the social-work queue. The action is refer or
watch. Each decision is updated from that family's outcome, not from one shared
day score. The comparison with the cutoff uses held-out seeds.
"""

from __future__ import annotations

import numpy as np
from numpy.random import default_rng

from app.schemas.scenario import ScenarioConfig
from app.simulation.engine import run_simulation
from app.surrogate.search import utility

_POLICY: "LearnedManager | None" = None


def active_policy() -> "LearnedManager | None":
    return _POLICY


def _band(score: int) -> int:
    if score >= 9:
        return 3
    if score >= 6:
        return 2
    if score >= 3:
        return 1
    return 0


def _queue_band(queue: int) -> int:
    if queue >= 3:
        return 2
    if queue >= 1:
        return 1
    return 0


def _family_reward(patient: dict) -> float:
    referred = bool(patient.get("referral_target"))
    if patient.get("high_need"):
        if patient.get("received_support"):
            return 1.0
        if referred and patient.get("left_before_psych"):
            return -0.7
        if not referred:
            return -1.2
        return -0.25
    if referred:
        return -0.35
    return 0.05


class LearnedManager:
    def __init__(self, seed: int = 17):
        self.rng = default_rng(seed)
        self.q = np.zeros((4, 3, 2))
        self.q[:, :, 1] = 0.15
        self.episode: list[tuple[int, int, int, str]] = []
        self.explore = 0.3
        self.returns: list[float] = []

    def choose(self, score: int, queue: int) -> str:
        state = (_band(score), _queue_band(queue))
        if self.rng.random() < self.explore:
            action = int(self.rng.integers(0, 2))
        else:
            action = int(self.q[state].argmax())
        return "refer" if action == 1 else "monitor"

    def note(self, score: int, queue: int, action: str, patient_id: str) -> None:
        self.episode.append((_band(score), _queue_band(queue), 1 if action == "refer" else 0, patient_id))

    def finish(self, patients: list[dict]) -> None:
        by_id = {item["id"]: item for item in patients}
        rewards = []
        for band, queue, action, patient_id in self.episode:
            reward = _family_reward(by_id[patient_id]) if patient_id in by_id else 0.0
            rewards.append(reward)
            current = self.q[band, queue, action]
            self.q[band, queue, action] = current + 0.35 * (reward - current)
        self.returns.append(round(sum(rewards) / len(rewards), 3) if rewards else 0.0)
        self.episode = []
        self.explore = max(0.05, self.explore * 0.97)

    def table(self) -> list[dict]:
        bands = ["0–2", "3–5", "6–8", "9–10"]
        queues = ["empty", "1–2 waiting", "3 or more"]
        rows = []
        for band in range(4):
            for queue in range(3):
                action = "refer" if int(self.q[band, queue].argmax()) == 1 else "watch"
                rows.append({"score": bands[band], "queue": queues[queue], "action": action})
        return rows


def train_and_compare(scenario: ScenarioConfig, episodes: int = 48, eval_runs: int = 8, n_patients: int = 20, seed: int = 17) -> dict:
    global _POLICY
    manager = LearnedManager(seed)
    base = scenario.model_copy(update={"use_llm": False, "screening_enabled": True, "n_patients": n_patients, "predictive_mode": "off"})
    for index in range(episodes):
        manager.episode = []
        day = base.model_copy(update={"seed": seed + index * 17, "referral_mode": "learned"})
        result = run_simulation(day, trace=False, policy=manager)
        manager.finish(result["patients"])
    manager.explore = 0.0
    _POLICY = manager

    learned_utils = []
    threshold_utils = []
    for index in range(eval_runs):
        shared = {"seed": seed + 500 + index * 17, "n_patients": n_patients, "use_llm": False, "screening_enabled": True}
        learned = run_simulation(base.model_copy(update={**shared, "referral_mode": "learned"}), trace=False, policy=manager)
        threshold = run_simulation(base.model_copy(update={**shared, "referral_mode": "automatic", "referral_threshold": scenario.referral_threshold}), trace=False)
        learned_utils.append(utility(learned["metrics"], base.n_social_workers, base.n_nurses))
        threshold_utils.append(utility(threshold["metrics"], base.n_social_workers, base.n_nurses))
    return {
        "method": (
            "Episodic Q-learning. Each referral or watch is updated from that family's outcome. "
            f"Trained for {episodes} days and compared with the fixed cutoff on {eval_runs} held-out seeds."
        ),
        "episodes": episodes,
        "n_patients": n_patients,
        "learning_curve": manager.returns,
        "policy": manager.table(),
        "evaluation": {
            "runs": eval_runs,
            "learned_utility": round(sum(learned_utils) / len(learned_utils), 3),
            "threshold_utility": round(sum(threshold_utils) / len(threshold_utils), 3),
            "learned_wins": sum(left > right for left, right in zip(learned_utils, threshold_utils)),
        },
        "disclaimer": "Learned on this synthetic day. Refer or watch only. No schedule is learned.",
    }
