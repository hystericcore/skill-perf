"""Waste pattern detectors for skill-perf diagnose.

Each detector function takes a list of ConversationSteps (and optionally
session-level or skill-level information) and returns a list of Issue
objects describing diagnosed problems.
"""

from __future__ import annotations

import os

from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep

# ---------------------------------------------------------------------------
# Pattern 1 — Script not executed
# ---------------------------------------------------------------------------

def detect_script_not_executed(
    steps: list[ConversationStep],
    skill_dir: str | None = None,
) -> list[Issue]:
    """Skill has ``scripts/`` but the model did work manually.

    Only fires when we can confirm the skill actually has a ``scripts/``
    directory with files in it.  This requires either:
    - *skill_dir* pointing to a directory containing ``scripts/``
    - Or a ``skill_load`` step whose file_path parent contains ``scripts/``
    """
    # Check if skill_dir has scripts/
    has_scripts_dir = False
    if skill_dir:
        scripts_path = os.path.join(skill_dir, "scripts")
        if os.path.isdir(scripts_path) and os.listdir(scripts_path):
            has_scripts_dir = True

    # If no skill_dir given, try to infer from skill_load steps
    if not has_scripts_dir:
        for step in steps:
            if step.step_type == "skill_load" and step.file_path:
                # Check if the skill's parent directory has scripts/
                skill_parent = os.path.dirname(step.file_path)
                scripts_path = os.path.join(skill_parent, "scripts")
                if os.path.isdir(scripts_path) and os.listdir(scripts_path):
                    has_scripts_dir = True
                    break

    if not has_scripts_dir:
        return []

    script_keywords = (
        "python ", "node ", "bash ", ".sh", ".py", "scripts/",
    )
    for i, step in enumerate(steps):
        if step.tool_name and step.tool_name.lower() in ("bash", "bashtool"):
            desc_lower = (step.description + step.raw_content_preview).lower()
            if any(kw in desc_lower for kw in script_keywords):
                return []  # at least one script was executed

    # Find the first skill_load step as the anchor
    anchor = 0
    for i, step in enumerate(steps):
        if step.step_type == "skill_load":
            anchor = i
            break

    return [
        Issue(
            severity="critical",
            pattern="script_not_executed",
            step_index=anchor,
            description=(
                "Skill was loaded but no scripts were executed. "
                "The model may be doing work that pre-built scripts could handle."
            ),
            impact_tokens=sum(
                s.token_count
                for s in steps
                if s.step_type in ("tool_call", "tool_result")
            ),
            suggestion=(
                "Ensure SKILL.md directs the model to run scripts/ "
                "instead of manually reading and transforming files."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Pattern 2 — Large file read
# ---------------------------------------------------------------------------

_LARGE_FILE_THRESHOLD = 2000  # tokens


def detect_large_file_read(steps: list[ConversationStep]) -> list[Issue]:
    """Flag tool results larger than 2 000 tokens."""
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.step_type == "tool_result" and step.token_count > _LARGE_FILE_THRESHOLD:
            issues.append(
                Issue(
                    severity="warning",
                    pattern="large_file_read",
                    step_index=i,
                    description=(
                        f"Large tool result: {step.token_count:,} tokens. "
                        f"Consider filtering or extracting relevant sections."
                    ),
                    impact_tokens=step.token_count - _LARGE_FILE_THRESHOLD,
                    suggestion=(
                        "Use grep/head/tail or a script to extract only the "
                        "relevant parts instead of loading the entire file."
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Pattern 3 — Duplicate reads
# ---------------------------------------------------------------------------

def detect_duplicate_reads(steps: list[ConversationStep]) -> list[Issue]:
    """Same file read more than once across turns."""
    file_reads: dict[str, list[int]] = {}
    for i, step in enumerate(steps):
        if step.file_path and step.step_type in ("tool_call", "tool_result", "skill_load"):
            file_reads.setdefault(step.file_path, []).append(i)

    issues: list[Issue] = []
    for path, indices in file_reads.items():
        if len(indices) > 1:
            dup_step = indices[-1]  # flag the later read
            step = steps[dup_step]
            issues.append(
                Issue(
                    severity="warning",
                    pattern="duplicate_read",
                    step_index=dup_step,
                    description=(
                        f"Duplicate read: '{path}' read {len(indices)} times. "
                        f"Model should retain content from the first read."
                    ),
                    impact_tokens=step.token_count,
                    suggestion=(
                        "Avoid re-reading files the model has already seen. "
                        "Skill instructions can remind the model to cache results."
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Pattern 4 — Excessive exploration
# ---------------------------------------------------------------------------

_EXPLORATION_TOOLS = {"glob", "grep", "listtool", "search"}
_ACTION_TYPES = {"tool_call"}
_ACTION_TOOLS = {"edit", "write", "create", "str_replace", "bash", "bashtool"}
_EXPLORATION_THRESHOLD = 5


def detect_excessive_exploration(steps: list[ConversationStep]) -> list[Issue]:
    """Five or more consecutive glob/grep calls before an edit/write action."""
    issues: list[Issue] = []
    run_start: int | None = None
    run_length = 0

    for i, step in enumerate(steps):
        tool = (step.tool_name or "").lower()
        if tool in _EXPLORATION_TOOLS:
            if run_start is None:
                run_start = i
            run_length += 1
        else:
            if run_length >= _EXPLORATION_THRESHOLD and run_start is not None:
                total_tokens = sum(
                    steps[j].token_count
                    for j in range(run_start, run_start + run_length)
                )
                issues.append(
                    Issue(
                        severity="warning",
                        pattern="excessive_exploration",
                        step_index=run_start,
                        description=(
                            f"{run_length} consecutive exploration calls "
                            f"(glob/grep) before acting. "
                            f"Total: {total_tokens:,} tokens."
                        ),
                        impact_tokens=total_tokens,
                        suggestion=(
                            "Skill instructions should tell the model exactly "
                            "where to look, reducing exploratory searching."
                        ),
                    )
                )
            run_start = None
            run_length = 0

    # Handle trailing run
    if run_length >= _EXPLORATION_THRESHOLD and run_start is not None:
        total_tokens = sum(
            steps[j].token_count
            for j in range(run_start, run_start + run_length)
        )
        issues.append(
            Issue(
                severity="warning",
                pattern="excessive_exploration",
                step_index=run_start,
                description=(
                    f"{run_length} consecutive exploration calls "
                    f"(glob/grep) before acting. "
                    f"Total: {total_tokens:,} tokens."
                ),
                impact_tokens=total_tokens,
                suggestion=(
                    "Skill instructions should tell the model exactly "
                    "where to look, reducing exploratory searching."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------------
# Pattern 5 — Oversized skill
# ---------------------------------------------------------------------------

_OVERSIZED_SKILL_THRESHOLD = 3000  # tokens


def detect_oversized_skill(steps: list[ConversationStep]) -> list[Issue]:
    """Skill files loaded with more than 3 000 tokens at once."""
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.step_type == "skill_load" and step.token_count > _OVERSIZED_SKILL_THRESHOLD:
            issues.append(
                Issue(
                    severity="warning",
                    pattern="oversized_skill",
                    step_index=i,
                    description=(
                        f"Large skill file loaded: {step.token_count:,} tokens. "
                        f"Consider splitting into SKILL.md + references/ "
                        f"with selective loading."
                    ),
                    impact_tokens=step.token_count - _OVERSIZED_SKILL_THRESHOLD,
                    suggestion=(
                        "Break the skill into a concise SKILL.md (< 2 000 tokens) "
                        "and put detailed references in references/."
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Pattern 6 — cat on large file
# ---------------------------------------------------------------------------

_CAT_TOKEN_THRESHOLD = 500


def detect_cat_on_large_file(steps: list[ConversationStep]) -> list[Issue]:
    """Bash ``cat`` on files that could use grep/head."""
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.tool_name and step.tool_name.lower() in ("bash", "bashtool"):
            desc_lower = step.description.lower()
            if "cat " in desc_lower and step.token_count > _CAT_TOKEN_THRESHOLD:
                issues.append(
                    Issue(
                        severity="warning",
                        pattern="cat_on_large_file",
                        step_index=i,
                        description=(
                            f"Using 'cat' on a large file ({step.token_count:,} tokens). "
                            f"Consider grep/head/tail to extract relevant sections."
                        ),
                        impact_tokens=step.token_count,
                        suggestion=(
                            "Replace 'cat' with targeted commands (grep, head, tail) "
                            "or use a script to extract only what is needed."
                        ),
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Pattern 7 — Low cache rate
# ---------------------------------------------------------------------------

def detect_low_cache_rate(session: SessionAnalysis) -> list[Issue]:
    """Cache hit rate appears low (api_input >> estimated tokens).

    We can only approximate: if the API-reported input tokens are
    significantly more than our step-level estimate, caching may be
    underutilised.  This is inherently imprecise.
    """
    estimated = session.total_estimated_tokens
    if estimated == 0 or session.api_input_tokens == 0:
        return []

    # If API input is more than 2x estimated, caching is likely poor
    ratio = session.api_input_tokens / estimated
    if ratio <= 2.0:
        return []

    return [
        Issue(
            severity="info",
            pattern="low_cache_rate",
            step_index=0,
            description=(
                f"API input tokens ({session.api_input_tokens:,}) are "
                f"{ratio:.1f}x the estimated content ({estimated:,}). "
                f"Cache hit rate may be below 50%."
            ),
            impact_tokens=session.api_input_tokens - estimated,
            suggestion=(
                "Ensure prompt caching is enabled. Structure the system "
                "prompt and skill content to maximise cache hits."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Pattern 8 — High think/act ratio
# ---------------------------------------------------------------------------

_THINK_ACT_THRESHOLD = 3.0


def detect_high_think_ratio(session: SessionAnalysis) -> list[Issue]:
    """Model generating disproportionately more text than tool usage."""
    ratio = session.think_act_ratio
    if ratio <= _THINK_ACT_THRESHOLD:
        return []

    assistant_tokens = sum(
        s.token_count for s in session.steps if s.step_type == "assistant_response"
    )

    return [
        Issue(
            severity="info",
            pattern="high_think_ratio",
            step_index=0,
            description=(
                f"Think/act ratio is {ratio:.1f}x. "
                f"The model is generating significantly more text "
                f"({assistant_tokens:,} tokens) than tool calls."
            ),
            impact_tokens=assistant_tokens,
            suggestion=(
                "Consider making skill instructions more directive so "
                "the model acts rather than explains. Add explicit "
                "'do not explain, just do' directives."
            ),
        )
    ]
