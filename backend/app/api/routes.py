"""HTTP and websocket API for the clinic digital twin."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.analytics.experiments import compare_scenarios, monte_carlo
from app.optimization.staffing import optimize_staffing
from app.config import ANTHROPIC_API_KEY
from app.presets import list_presets, preset
from app.schemas.scenario import ScenarioConfig
from app.simulation.engine import run_simulation

router = APIRouter()


class RunRequest(BaseModel):
    scenario: ScenarioConfig | None = None
    preset: str | None = None
    trace: bool = True


class CompareRequest(BaseModel):
    scenarios: list[ScenarioConfig] = Field(min_length=1, max_length=3)


class MonteCarloRequest(BaseModel):
    scenario: ScenarioConfig
    runs: int = Field(30, ge=2, le=500)


class OptimizeRequest(BaseModel):
    scenario: ScenarioConfig
    replicates: int = Field(6, ge=4, le=20)


def _resolve(body: RunRequest) -> ScenarioConfig:
    if body.preset:
        return preset(body.preset)
    if body.scenario:
        return body.scenario
    return ScenarioConfig()


def _prepare(scenario: ScenarioConfig) -> ScenarioConfig:
    if scenario.predictive_mode != "off":
        from app.ml.model import ensure_model

        ensure_model()
    return scenario


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "pediatric-oncology-clinic-digital-twin",
        "llm": "claude" if ANTHROPIC_API_KEY else "rules",
    }


@router.get("/presets")
def presets():
    return {"presets": list_presets()}


@router.post("/simulation/run")
def simulation_run(body: RunRequest):
    scenario = _prepare(_resolve(body))
    return run_simulation(scenario, trace=body.trace)


@router.post("/experiments/compare")
def experiments_compare(body: CompareRequest):
    scenarios = [_prepare(item) for item in body.scenarios]
    return {"results": compare_scenarios(scenarios, trace=False)}


@router.post("/experiments/monte-carlo")
def experiments_monte_carlo(body: MonteCarloRequest):
    return monte_carlo(_prepare(body.scenario), runs=body.runs)


@router.post("/ml/train")
def ml_train():
    from app.ml.model import train_model

    return train_model()


@router.get("/ml/metrics")
def ml_metrics():
    from app.ml.model import load_metrics

    return load_metrics()


@router.post("/optimization/run")
def optimization_run(body: OptimizeRequest):
    return optimize_staffing(_prepare(body.scenario), replicates=body.replicates)


class ResearchRequest(BaseModel):
    scenario: ScenarioConfig
    draws: int = Field(80, ge=8, le=120)
    replicates: int = Field(3, ge=1, le=5)
    initial: int = Field(24, ge=4, le=48)
    steps: int = Field(16, ge=2, le=32)
    episodes: int = Field(48, ge=6, le=80)


def _research_day(scenario: ScenarioConfig) -> ScenarioConfig:
    return scenario.model_copy(update={"use_llm": False})


@router.post("/research/calibrate")
def research_calibrate(body: ResearchRequest):
    from app.calibration.fit import calibrate

    return calibrate(_research_day(body.scenario), draws=body.draws, replicates=body.replicates)


@router.post("/research/distress")
def research_distress(body: ResearchRequest):
    from app.evaluation.audit import distress_fit

    return distress_fit(_research_day(body.scenario))


@router.post("/research/personas")
def research_personas():
    from app.evaluation.audit import persona_audit

    return persona_audit(use_model=bool(ANTHROPIC_API_KEY))


@router.post("/research/surrogate")
def research_surrogate(body: ResearchRequest):
    from app.surrogate.search import search

    return search(_research_day(body.scenario), initial=body.initial, steps=body.steps)


@router.post("/research/manager")
def research_manager(body: ResearchRequest):
    from app.rl.manager import train_and_compare

    return train_and_compare(_research_day(body.scenario), episodes=body.episodes)


@router.websocket("/ws/simulation")
async def simulation_socket(websocket: WebSocket):
    """Stream a completed trace. Playback controls in the UI use the REST trace."""
    await websocket.accept()
    try:
        message = await websocket.receive_json()
        scenario = ScenarioConfig.model_validate(message.get("scenario") or {})
        speed = float(message.get("speed") or 1)
        result = await asyncio.to_thread(run_simulation, _prepare(scenario), True)
        await websocket.send_json(
            {
                "type": "ready",
                "horizon": result["horizon"],
                "metrics": result["metrics"],
                "bottleneck": result["bottleneck"],
                "events": result["events"],
            }
        )
        delay = max(0.02, 0.25 / max(0.25, speed))
        for frame in result["frames"]:
            await websocket.send_json({"type": "frame", "frame": frame})
            await asyncio.sleep(delay)
        await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        return
    except Exception as exc:  # surface a single error frame, then close
        await websocket.send_json({"type": "error", "message": str(exc)})
