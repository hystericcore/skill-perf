from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ConversationStep(BaseModel):
    """One turn in the conversation."""

    turn: int
    role: Literal["system", "user", "assistant", "tool"]
    step_type: Literal[
        "system_prompt",
        "user_message",
        "tool_call",
        "tool_result",
        "skill_load",
        "assistant_response",
    ]
    description: str
    token_count: int
    tool_name: str | None = None
    file_path: str | None = None
    raw_content_preview: str = ""
