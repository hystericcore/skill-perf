"""Generate actionable fix suggestions for diagnosed issues."""

from __future__ import annotations

import re

from skill_perf.core.pricing import estimate_cost
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.suggestion.templates import TEMPLATES


def generate_suggestion(issue: Issue, session: SessionAnalysis) -> str:
    """Generate actionable fix text for a diagnosed issue.

    Returns formatted suggestion text with the template filled in using
    context from the issue description and the actual step data.
    """
    template = TEMPLATES.get(issue.pattern, "")
    if not template:
        return issue.suggestion

    # Build context from step data
    context: dict[str, str] = {}

    # Safe access to the step
    if 0 <= issue.step_index < len(session.steps):
        step = session.steps[issue.step_index]
        context["file_path"] = step.file_path or "unknown file"
        context["tool_name"] = step.tool_name or "unknown tool"
        context["token_count"] = f"{step.token_count:,}"
        context["step_index"] = str(issue.step_index)
        context["raw_preview"] = (
            step.raw_content_preview[:100] if step.raw_content_preview else ""
        )

    # Pattern-specific context
    if issue.pattern == "duplicate_reads":
        # Count how many times this file appears
        file_path = context.get("file_path", "")
        if file_path and file_path != "unknown file":
            read_count = sum(
                1
                for s in session.steps
                if s.file_path == file_path
                and s.step_type in ("tool_call", "tool_result", "skill_load")
            )
            context["read_count"] = str(read_count)
        else:
            context["read_count"] = "multiple"

    elif issue.pattern == "excessive_exploration":
        # Extract count from description (e.g., "6 consecutive exploration calls")
        m = re.search(r"(\d+)\s+consecutive", issue.description)
        context["exploration_count"] = m.group(1) if m else "5+"

    elif issue.pattern == "script_not_executed":
        # Try to extract script name from the issue description
        script_match = re.search(r"scripts?/(\S+\.py)", issue.description)
        context["script_name"] = (
            script_match.group(1) if script_match else "run.py"
        )
        # Try to extract task description
        context["task_description"] = _extract_task_description(issue.description)

    try:
        return template.format(**context)
    except KeyError:
        return template


def _extract_task_description(description: str) -> str:
    """Extract a short task description from an issue description string."""
    # Use the first meaningful phrase, or fall back to a generic label
    if "CSV" in description.upper():
        return "CSV Processing"
    if "JSON" in description.upper():
        return "JSON Processing"
    if "parse" in description.lower():
        return "Data Processing"
    # Fall back: use first part of description
    short = description.split(".")[0].strip()
    return short[:60] if short else "Script Execution"


def estimate_savings(
    issue: Issue, model: str = "claude-sonnet-4"
) -> tuple[int, float]:
    """Estimate token and cost savings from fixing this issue.

    Returns (tokens_saved, cost_saved_usd).
    """
    tokens_saved = issue.impact_tokens
    cost_saved = estimate_cost(tokens_saved, model, direction="input")
    return tokens_saved, cost_saved
