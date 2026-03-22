from __future__ import annotations

from pydantic import BaseModel

from skill_perf.models.benchmark import BenchmarkResult
from skill_perf.models.diagnosis import Issue


class Comparison(BaseModel):
    """Before/after comparison."""

    baseline: BenchmarkResult
    current: BenchmarkResult
    token_delta: int
    cost_delta: float
    issues_resolved: list[Issue]
    issues_remaining: list[Issue]
