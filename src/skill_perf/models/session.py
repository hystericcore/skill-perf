from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, computed_field

from skill_perf.models.diagnosis import Issue
from skill_perf.models.step import ConversationStep


class SessionAnalysis(BaseModel):
    """Complete analysis of one captured session."""

    session_id: str
    model: str
    api_input_tokens: int
    api_output_tokens: int
    steps: list[ConversationStep]
    issues: list[Issue] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_estimated_tokens(self) -> int:
        return sum(s.token_count for s in self.steps)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tokens_by_type(self) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for s in self.steps:
            result[s.step_type] += s.token_count
        return dict(result)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tokens_by_tool(self) -> dict[str, int]:
        result: dict[str, int] = defaultdict(int)
        for s in self.steps:
            if s.tool_name:
                result[s.tool_name] += s.token_count
        return dict(result)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def think_act_ratio(self) -> float:
        assistant_tokens = sum(
            s.token_count for s in self.steps if s.step_type == "assistant_response"
        )
        tool_tokens = sum(
            s.token_count
            for s in self.steps
            if s.step_type in ("tool_call", "tool_result")
        )
        if tool_tokens == 0:
            return float(assistant_tokens) if assistant_tokens > 0 else 0.0
        return assistant_tokens / tool_tokens

    @computed_field  # type: ignore[prop-decorator]
    @property
    def waste_tokens(self) -> int:
        return sum(i.impact_tokens for i in self.issues)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def waste_percentage(self) -> float:
        total = self.total_estimated_tokens
        if total == 0:
            return 0.0
        return (self.waste_tokens / total) * 100
