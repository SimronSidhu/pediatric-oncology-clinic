"""Train and score a psychosocial-need model on synthetic encounters.

The model is a demonstration. It is not for clinical decision-making.
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from numpy.random import default_rng
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import DATA_DIR
from app.schemas.scenario import ScenarioConfig
from app.synthetic_data.generator import build_population

FEATURES = [
    "age",
    "new_diagnosis",
    "symptom_burden",
    "chart_distress",
    "caregiver_stress",
    "travel_burden",
    "treatment_intensity",
    "complexity",
    "language_support",
    "prior_psychosocial",
    "previous_wait_min",
]

_MODEL = None
_METRICS: dict | None = None


def generate_encounters(n: int = 3200, seed: int = 21, shifted: bool = False) -> pd.DataFrame:
    rows: list[dict] = []
    remaining = n
    batch_seed = seed
    while remaining > 0:
        take = min(40, remaining)
        draw = default_rng(batch_seed)
        if shifted:
            prevalence = float(draw.uniform(0.22, 0.34))
            high = float(draw.uniform(0.06, 0.12))
        else:
            prevalence = float(draw.uniform(0.4, 0.75))
            high = float(draw.uniform(0.18, 0.42))
        scenario = ScenarioConfig(
            seed=batch_seed,
            n_patients=take,
            screening_enabled=False,
            distress_prevalence=prevalence,
            high_distress_prevalence=high,
            pct_new_diagnosis=float(default_rng(batch_seed + 3).uniform(0.2, 0.5)),
        )
        patients, caregivers, _staff = build_population(scenario, default_rng(batch_seed))
        flip = default_rng(batch_seed + 9)
        for patient in patients:
            caregiver = caregivers[patient.id]
            label = int(patient.high_need)
            if flip.random() < 0.04:
                label = 1 - label
            rows.append(
                {
                    "age": patient.age,
                    "new_diagnosis": int(patient.visit_type == "new"),
                    "symptom_burden": patient.symptom_burden,
                    "chart_distress": patient.chart_distress,
                    "caregiver_stress": caregiver.stress,
                    "travel_burden": patient.travel_burden,
                    "treatment_intensity": patient.treatment_intensity,
                    "complexity": patient.complexity,
                    "language_support": int(patient.language_support),
                    "prior_psychosocial": int(patient.prior_psychosocial),
                    "previous_wait_min": patient.previous_wait_min,
                    "requires_referral": label,
                }
            )
        remaining -= take
        batch_seed += 11
    frame = pd.DataFrame(rows)
    if shifted and len(frame):
        shuffled = frame["chart_distress"].to_numpy().copy()
        default_rng(seed + 99).shuffle(shuffled)
        frame["chart_distress"] = shuffled
    if not shifted:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        frame.to_csv(DATA_DIR / "encounters.csv", index=False)
    return frame


def _score(name: str, model, x_test, y_test, importances: list[float]) -> dict:
    proba = model.predict_proba(x_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    matrix = confusion_matrix(y_test, pred, labels=[0, 1]).tolist()
    auc = float(roc_auc_score(y_test, proba)) if len(set(y_test)) > 1 else 0.5
    return {
        "name": name,
        "roc_auc": round(auc, 3),
        "precision": round(float(precision_score(y_test, pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y_test, pred, zero_division=0)), 3),
        "f1": round(float(f1_score(y_test, pred, zero_division=0)), 3),
        "confusion_matrix": matrix,
        "feature_importance": [
            {"feature": feature, "importance": round(float(value), 4)}
            for feature, value in sorted(zip(FEATURES, importances), key=lambda item: item[1], reverse=True)
        ],
    }


def train_model(n: int = 3200, seed: int = 21) -> dict:
    global _MODEL, _METRICS
    frame = generate_encounters(n=n, seed=seed)
    x = frame[FEATURES]
    y = frame["requires_referral"].astype(int)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, random_state=seed, stratify=y
    )
    logistic = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=400, class_weight="balanced")),
        ]
    )
    logistic.fit(x_train, y_train)
    forest = RandomForestClassifier(
        n_estimators=180,
        max_depth=8,
        min_samples_leaf=8,
        random_state=seed,
        class_weight="balanced_subsample",
        n_jobs=1,
    )
    forest.fit(x_train, y_train)
    logistic_coef = np.abs(logistic.named_steps["model"].coef_[0])
    logistic_coef = logistic_coef / logistic_coef.sum()
    forest_imp = forest.feature_importances_
    metrics = {
        "disclaimer": (
            "Synthetic data. The first metrics are a holdout from the training generator. "
            "The shifted cohort has lower distress and shuffled chart distress. "
            "Do not use these scores for patient care."
        ),
        "n_encounters": int(len(frame)),
        "positive_rate": round(float(y.mean()), 3),
        "features": FEATURES,
        "models": [
            _score("Logistic regression", logistic, x_test, y_test, logistic_coef),
            _score("Random forest", forest, x_test, y_test, forest_imp),
        ],
        "shifted": _shifted_report(logistic, forest, logistic_coef, forest_imp, n=max(400, n // 4), seed=seed + 500),
    }
    _MODEL = forest
    _METRICS = metrics
    joblib.dump(forest, DATA_DIR / "referral_model.joblib")
    (DATA_DIR / "ml_metrics.json").write_text(json.dumps(metrics, indent=2))
    return metrics


def _shifted_report(logistic, forest, logistic_coef, forest_imp, n: int, seed: int) -> dict:
    frame = generate_encounters(n=n, seed=seed, shifted=True)
    x = frame[FEATURES]
    y = frame["requires_referral"].astype(int)
    return {
        "n_encounters": int(len(frame)),
        "positive_rate": round(float(y.mean()), 3),
        "description": (
            "Lower distress prevalence than the training generator, and chart distress shuffled "
            "so it no longer tracks the label."
        ),
        "models": [
            _score("Logistic regression", logistic, x, y, logistic_coef),
            _score("Random forest", forest, x, y, forest_imp),
        ],
    }


def load_metrics() -> dict:
    global _METRICS, _MODEL
    if _METRICS is not None:
        return _METRICS
    path = DATA_DIR / "ml_metrics.json"
    model_path = DATA_DIR / "referral_model.joblib"
    if path.exists() and model_path.exists():
        _METRICS = json.loads(path.read_text())
        _MODEL = joblib.load(model_path)
        return _METRICS
    return train_model()


def risk_from_patient(patient, caregiver) -> float | None:
    """Use a trained model when one is already loaded. Do not train mid-simulation."""
    if _MODEL is None:
        return None
    row = pd.DataFrame(
        [
            {
                "age": patient.age,
                "new_diagnosis": int(patient.visit_type == "new"),
                "symptom_burden": patient.symptom_burden,
                "chart_distress": patient.chart_distress,
                "caregiver_stress": caregiver.stress,
                "travel_burden": patient.travel_burden,
                "treatment_intensity": patient.treatment_intensity,
                "complexity": patient.complexity,
                "language_support": int(patient.language_support),
                "prior_psychosocial": int(patient.prior_psychosocial),
                "previous_wait_min": patient.previous_wait_min,
            }
        ]
    )
    return float(_MODEL.predict_proba(row[FEATURES])[0, 1])


def ensure_model():
    load_metrics()
    return _MODEL
