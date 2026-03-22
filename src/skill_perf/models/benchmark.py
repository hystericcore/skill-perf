from __future__ import annotations

from pydantic import BaseModel

from skill_perf.models.session import SessionAnalysis


class BenchmarkResult(BaseModel):
    """Result of a benchmark run (one or more sessions)."""

    run_id: str
    timestamp: str
    skill_name: str
    sessions: list[SessionAnalysis]
    total_tokens: int
    total_cost_usd: float
    total_issues: int
