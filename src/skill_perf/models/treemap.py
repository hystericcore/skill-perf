from __future__ import annotations

from pydantic import BaseModel

from skill_perf.models.diagnosis import Issue


class TreemapNode(BaseModel):
    """Node in the treemap visualization."""

    name: str
    token_count: int
    effective_tokens: int
    cost_usd: float
    category: str
    children: list[TreemapNode] = []
    issues: list[Issue] = []
    is_wasteful: bool = False
