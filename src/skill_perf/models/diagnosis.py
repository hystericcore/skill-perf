
from typing import Literal

from pydantic import BaseModel


class Issue(BaseModel):
    """A diagnosed underperformance issue."""

    severity: Literal["critical", "warning", "info"]
    pattern: str
    step_index: int
    description: str
    impact_tokens: int
    suggestion: str
