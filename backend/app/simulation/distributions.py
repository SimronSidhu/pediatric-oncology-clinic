"""Service-time helpers."""

from __future__ import annotations


def band_for_score(score: int) -> str:
    if score <= 2:
        return "low"
    if score <= 5:
        return "moderate"
    if score <= 8:
        return "high"
    return "severe"
