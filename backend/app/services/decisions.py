"""Rule-based and optional LLM decision engines.

LLM output is validated with Pydantic and discarded if it does not match
an allowed action. The simulation never applies free text to clinic state.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL


class NurseDecision(BaseModel):
    action: Literal[
        "refer_social_work",
        "refer_psychology",
        "refer_child_life",
        "monitor",
        "urgent_review",
    ]
    priority: int = Field(ge=0, le=10)
    explanation: str = Field(min_length=3, max_length=400)


class ScreeningChoice(BaseModel):
    accept: bool
    reason: Literal["agreed", "privacy_concern", "time_pressure", "stress", "prior_experience", "language"]
    explanation: str = Field(min_length=3, max_length=400)


class DisclosureChoice(BaseModel):
    level: Literal["full", "partial", "minimal"]
    explanation: str = Field(min_length=3, max_length=400)


class TriageDecision(BaseModel):
    target: Literal["social_work", "psychology", "child_life", "defer"]
    priority: int = Field(ge=0, le=10)
    explanation: str = Field(min_length=3, max_length=400)


class AgentDecisionEngine(Protocol):
    def decide(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> dict[str, Any]:
        """Return a validated decision for the given agent and clinic context."""


def screening_decline_probability(
    *,
    base: float,
    language_support: bool,
    stress: float,
    privacy_concern: float,
    prior_experience: str,
) -> float:
    """Language access does not change this probability. The persona audit is what measures a shift."""
    del language_support
    probability = base
    if stress >= 75:
        probability += 0.06
    if privacy_concern >= 0.62:
        probability += 0.05
    if prior_experience == "difficult":
        probability += 0.04
    return min(0.8, probability)


def _queue(environment_state: dict[str, Any], key: str) -> int:
    queues = environment_state.get("queues") or {}
    return int(queues.get(key, 0))


class RuleBasedDecisionEngine:
    """Transparent rules used for every run unless an LLM is explicitly enabled."""

    def decide(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> dict[str, Any]:
        kind = agent_state.get("decision")
        if kind == "screening":
            choice = self.screening_choice(agent_state, environment_state)
            return choice.model_dump()
        if kind == "disclosure":
            return self.disclosure_choice(agent_state).model_dump()
        if kind == "triage":
            choice = self.triage_decision(agent_state, environment_state)
            return choice.model_dump()
        choice = self.nurse_decision(agent_state, environment_state)
        return choice.model_dump()

    def screening_choice(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> ScreeningChoice:
        decline_p = float(agent_state.get("decline_probability", 0.12))
        roll = float(agent_state.get("decline_roll", 0.5))
        if roll > decline_p:
            return ScreeningChoice(
                accept=True,
                reason="agreed",
                explanation="The caregiver agreed to complete the distress screen.",
            )
        if float(agent_state.get("stress", 0)) >= 75:
            reason = "stress"
            why = "The caregiver was too stressed to take on another form."
        elif float(environment_state.get("wait_so_far", 0)) >= 15:
            reason = "time_pressure"
            why = "The family had already been waiting and declined the extra step."
        elif agent_state.get("prior_screening_experience") == "difficult":
            reason = "prior_experience"
            why = "A previous screening experience made the caregiver unwilling to repeat it."
        else:
            reason = "privacy_concern"
            why = "The caregiver declined because the desk did not feel private enough."
        return ScreeningChoice(accept=False, reason=reason, explanation=why)

    def disclosure_choice(self, agent_state: dict[str, Any]) -> DisclosureChoice:
        """How much of the latent distress is written on the form."""
        roll = float(agent_state.get("disclosure_roll", 0.9))
        guarded = float(agent_state.get("privacy_concern", 0)) >= 0.62 or float(agent_state.get("stress", 0)) >= 75
        if guarded and roll < 0.08:
            return DisclosureChoice(
                level="minimal",
                explanation="The caregiver marked only the lowest items and left the rest blank.",
            )
        if guarded and roll < 0.22:
            return DisclosureChoice(
                level="partial",
                explanation="The caregiver completed the form but left out the items that felt most exposed.",
            )
        return DisclosureChoice(
            level="full",
            explanation="The caregiver answered the distress items as asked.",
        )

    def nurse_decision(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> NurseDecision:
        score = int(agent_state.get("score") or 0)
        age = float(agent_state.get("age") or 10)
        anxiety = float(agent_state.get("anxiety") or 0)
        threshold = int(agent_state.get("threshold") or 3)
        sw_queue = _queue(environment_state, "social_work")
        monitor_roll = float(agent_state.get("monitor_roll", 0))

        if score >= 9:
            return NurseDecision(
                action="urgent_review",
                priority=1,
                explanation=f"Distress score {score}/10 is in the severe band and needs an urgent psychosocial response.",
            )
        if score >= 7 and anxiety >= 0.65:
            return NurseDecision(
                action="refer_psychology",
                priority=2,
                explanation=f"Score {score}/10 with high anxiety is routed to psychology rather than watchful waiting.",
            )
        if age <= 7 and score >= threshold:
            return NurseDecision(
                action="refer_child_life",
                priority=3,
                explanation=f"A younger child scored {score}/10, so child life is the first psychosocial response.",
            )
        if score >= threshold and sw_queue >= 5 and score < threshold + 2 and monitor_roll < 0.4:
            return NurseDecision(
                action="monitor",
                priority=6,
                explanation=(
                    f"Score {score}/10 meets the threshold, but the social work queue is {sw_queue}. "
                    "The nurse monitors instead of adding another immediate referral."
                ),
            )
        if score >= threshold:
            return NurseDecision(
                action="refer_social_work",
                priority=3,
                explanation=f"Distress score {score}/10 is at or above the referral threshold of {threshold}.",
            )
        return NurseDecision(
            action="monitor",
            priority=7,
            explanation=f"Score {score}/10 is below the referral threshold of {threshold}.",
        )

    def triage_decision(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> TriageDecision:
        score = int(agent_state.get("score") or 0)
        age = float(agent_state.get("age") or 10)
        if score >= 9:
            target: Literal["social_work", "psychology", "child_life", "defer"] = "psychology"
            why = f"Central triage assigns a severe score of {score}/10 to psychology."
        elif age <= 7 and score >= 4:
            target = "child_life"
            why = f"Central triage assigns a younger child with score {score}/10 to child life."
        elif score >= int(agent_state.get("threshold") or 3):
            target = "social_work"
            why = f"Central triage assigns score {score}/10 to social work."
        else:
            target = "defer"
            why = "Central triage does not open a referral below the threshold."
        sw_queue = _queue(environment_state, "social_work")
        if target == "social_work" and sw_queue >= 6 and score < 7:
            target = "defer"
            why = f"Social work already has {sw_queue} families waiting, so a moderate score is deferred."
        return TriageDecision(target=target, priority=2 if score >= 8 else 4, explanation=why)


def sanitize_nurse_decision(raw: dict[str, Any], score: int) -> NurseDecision:
    """Validate an LLM payload. Severe scores cannot be downgraded to monitor."""
    decision = NurseDecision.model_validate(raw)
    if score >= 9 and decision.action == "monitor":
        raise ValueError("Severe distress cannot be monitored without a referral.")
    return decision


class LLMDecisionEngine:
    """Optional structured-output engine. Falls back to rules when unavailable."""

    def __init__(self, fallback: RuleBasedDecisionEngine | None = None):
        self.fallback = fallback or RuleBasedDecisionEngine()

    def decide(self, agent_state: dict[str, Any], environment_state: dict[str, Any]) -> dict[str, Any]:
        kind = agent_state.get("decision", "nurse")
        if not ANTHROPIC_API_KEY and not OPENAI_API_KEY:
            return self.fallback.decide(agent_state, environment_state)
        schema = {
            "nurse": NurseDecision,
            "screening": ScreeningChoice,
            "disclosure": DisclosureChoice,
            "triage": TriageDecision,
        }.get(kind, NurseDecision)
        try:
            payload = self._complete(kind, agent_state, environment_state, schema)
            if kind == "nurse":
                parsed = sanitize_nurse_decision(payload, int(agent_state.get("score") or 0))
            else:
                parsed = schema.model_validate(payload)
            return parsed.model_dump()
        except (ValidationError, ValueError, httpx.HTTPError, KeyError, json.JSONDecodeError):
            return self.fallback.decide(agent_state, environment_state)

    def _complete(self, kind: str, agent_state: dict[str, Any], environment_state: dict[str, Any], schema: type[BaseModel]) -> dict[str, Any]:
        visible = {key: value for key, value in agent_state.items() if not str(key).endswith("_roll")}
        prompt = {
            "task": kind,
            "instruction": (
                "Choose one allowed action for this pediatric oncology clinic moment. "
                "Use the distress score, referral threshold, queues, and caregiver context. "
                "A score at or above the threshold should be referred. "
                "Return only JSON matching the schema. Do not invent clinical orders, "
                "doses, or diagnoses. This is an operations simulation."
            ),
            "schema": schema.model_json_schema(),
            "agent_state": visible,
            "environment_state": environment_state,
        }
        if ANTHROPIC_API_KEY:
            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 400,
                    "temperature": 0.1,
                    "system": "You return compact JSON decisions for a clinic operations simulation. No markdown.",
                    "messages": [{"role": "user", "content": json.dumps(prompt)}],
                },
                timeout=30.0,
            )
            response.raise_for_status()
            content = response.json()["content"][0]["text"]
        else:
            response = httpx.post(
                f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": OPENAI_MODEL,
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": "You return compact JSON decisions for a clinic operations simulation.",
                        },
                        {"role": "user", "content": json.dumps(prompt)},
                    ],
                },
                timeout=20.0,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        return _json_object(content)


def _json_object(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Decision payload must be a JSON object.")
    return parsed


def engine_for(use_llm: bool) -> RuleBasedDecisionEngine | LLMDecisionEngine:
    rules = RuleBasedDecisionEngine()
    if use_llm:
        return LLMDecisionEngine(rules)
    return rules
