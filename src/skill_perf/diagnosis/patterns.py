"""Waste pattern detectors for skill-perf diagnose.

Each detector function takes a list of ConversationSteps (and optionally
session-level or skill-level information) and returns a list of Issue
objects describing diagnosed problems.

Thresholds are configurable via ThresholdConfig (loaded from .skill-perf.toml).
"""


import os
import re

from skill_perf.core.config import ThresholdConfig
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep

_EXPLORATION_TOOLS = {"glob", "grep", "listtool", "search"}


# ---------------------------------------------------------------------------
# Pattern 1 — Script not executed
# ---------------------------------------------------------------------------

def detect_script_not_executed(
    steps: list[ConversationStep],
    skill_dir: str | None = None,
) -> list[Issue]:
    """Skill has ``scripts/`` but the model did work manually.

    Only fires when we can confirm the skill actually has a ``scripts/``
    directory with files in it.
    """
    has_scripts_dir = False
    if skill_dir:
        scripts_path = os.path.join(skill_dir, "scripts")
        if os.path.isdir(scripts_path) and os.listdir(scripts_path):
            has_scripts_dir = True

    if not has_scripts_dir:
        for step in steps:
            if step.step_type == "skill_load" and step.file_path:
                skill_parent = os.path.dirname(step.file_path)
                scripts_path = os.path.join(skill_parent, "scripts")
                if os.path.isdir(scripts_path) and os.listdir(scripts_path):
                    has_scripts_dir = True
                    break

    if not has_scripts_dir:
        return []

    script_keywords = ("python ", "node ", "bash ", ".sh", ".py", "scripts/")
    for step in steps:
        if step.tool_name and step.tool_name.lower() in ("bash", "bashtool"):
            desc_lower = (step.description + step.raw_content_preview).lower()
            if any(kw in desc_lower for kw in script_keywords):
                return []

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
                "The model may be doing work that pre-built scripts "
                "could handle."
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

def detect_large_file_read(
    steps: list[ConversationStep],
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Flag tool results larger than the configured threshold."""
    threshold = (config or ThresholdConfig()).large_file_read_tokens
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.step_type == "tool_result" and step.token_count > threshold:
            issues.append(
                Issue(
                    severity="warning",
                    pattern="large_file_read",
                    step_index=i,
                    description=(
                        f"Large tool result: {step.token_count:,} tokens. "
                        f"Consider filtering or extracting relevant sections."
                    ),
                    impact_tokens=step.token_count - threshold,
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
        if step.file_path and step.step_type in (
            "tool_call", "tool_result", "skill_load",
        ):
            file_reads.setdefault(step.file_path, []).append(i)

    issues: list[Issue] = []
    for path, indices in file_reads.items():
        if len(indices) > 1:
            dup_step = indices[-1]
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
                        "Skill instructions can remind the model to cache "
                        "results."
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Pattern 4 — Excessive exploration
# ---------------------------------------------------------------------------

def detect_excessive_exploration(
    steps: list[ConversationStep],
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Consecutive glob/grep tool_call steps before an action."""
    cfg = config or ThresholdConfig()
    count_threshold = cfg.excessive_exploration_count
    min_tokens = cfg.excessive_exploration_min_tokens

    issues: list[Issue] = []
    run_start: int | None = None
    run_length = 0

    for i, step in enumerate(steps):
        tool = (step.tool_name or "").lower()
        if tool in _EXPLORATION_TOOLS and step.step_type == "tool_call":
            if run_start is None:
                run_start = i
            run_length += 1
        else:
            if run_length >= count_threshold and run_start is not None:
                total_tokens = sum(
                    steps[j].token_count
                    for j in range(run_start, run_start + run_length)
                )
                if total_tokens >= min_tokens:
                    issues.append(_exploration_issue(
                        run_start, run_length, total_tokens
                    ))
            run_start = None
            run_length = 0

    # Handle trailing run
    if run_length >= count_threshold and run_start is not None:
        total_tokens = sum(
            steps[j].token_count
            for j in range(run_start, run_start + run_length)
        )
        if total_tokens >= min_tokens:
            issues.append(_exploration_issue(
                run_start, run_length, total_tokens
            ))

    return issues


def _exploration_issue(
    step_index: int, run_length: int, total_tokens: int,
) -> Issue:
    return Issue(
        severity="warning",
        pattern="excessive_exploration",
        step_index=step_index,
        description=(
            f"{run_length} consecutive exploration calls "
            f"(glob/grep) before acting. "
            f"Total: {total_tokens:,} tokens."
        ),
        impact_tokens=total_tokens,
        suggestion=(
            "Skill instructions should tell the model "
            "exactly where to look, reducing exploratory searching."
        ),
    )


# ---------------------------------------------------------------------------
# Pattern 5 — Oversized skill
# ---------------------------------------------------------------------------

def detect_oversized_skill(
    steps: list[ConversationStep],
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Skill files loaded above the configured token threshold."""
    threshold = (config or ThresholdConfig()).oversized_skill_tokens
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.step_type == "skill_load" and step.token_count > threshold:
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
                    impact_tokens=step.token_count - threshold,
                    suggestion=(
                        "Break the skill into a concise SKILL.md "
                        "(< 2 000 tokens) and put detailed references "
                        "in references/."
                    ),
                )
            )
    return issues


# ---------------------------------------------------------------------------
# Pattern 6 — cat on large file
# ---------------------------------------------------------------------------

def detect_cat_on_large_file(
    steps: list[ConversationStep],
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Bash ``cat`` on files above the configured token threshold."""
    threshold = (config or ThresholdConfig()).cat_on_large_file_tokens
    issues: list[Issue] = []
    for i, step in enumerate(steps):
        if step.tool_name and step.tool_name.lower() in ("bash", "bashtool"):
            desc_lower = step.description.lower()
            if "cat " in desc_lower and step.token_count > threshold:
                issues.append(
                    Issue(
                        severity="warning",
                        pattern="cat_on_large_file",
                        step_index=i,
                        description=(
                            f"Using 'cat' on a large file "
                            f"({step.token_count:,} tokens). "
                            f"Consider grep/head/tail to extract "
                            f"relevant sections."
                        ),
                        impact_tokens=step.token_count,
                        suggestion=(
                            "Replace 'cat' with targeted commands "
                            "(grep, head, tail) or use a script to "
                            "extract only what is needed."
                        ),
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Pattern 7 — Low cache rate
# ---------------------------------------------------------------------------

def detect_low_cache_rate(
    session: SessionAnalysis,
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Cache hit rate appears low (api_input >> estimated tokens)."""
    threshold = (config or ThresholdConfig()).low_cache_rate_ratio
    estimated = session.total_estimated_tokens
    if estimated == 0 or session.api_input_tokens == 0:
        return []

    ratio = session.api_input_tokens / estimated
    if ratio <= threshold:
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

def detect_high_think_ratio(
    session: SessionAnalysis,
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Model generating disproportionately more text than tool usage."""
    threshold = (config or ThresholdConfig()).high_think_ratio
    ratio = session.think_act_ratio
    if ratio <= threshold:
        return []

    assistant_tokens = sum(
        s.token_count for s in session.steps
        if s.step_type == "assistant_response"
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


# ---------------------------------------------------------------------------
# Pattern 9 — Skill not triggered
# ---------------------------------------------------------------------------

def _extract_user_prompt(steps: list[ConversationStep]) -> str:
    """Extract the first real user prompt from the steps."""
    for step in steps:
        if step.step_type != "user_message":
            continue
        preview = step.raw_content_preview
        if preview.startswith("<available-deferred-tools>"):
            continue
        if preview.startswith("<system-reminder>"):
            continue
        if len(preview.strip()) < 5:
            continue
        return preview
    return ""


def _load_skill_description(skill_dir: str) -> tuple[str, str]:
    """Load skill name and description from SKILL.md frontmatter."""
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        for name in ("skill.md", "SKILL.MD"):
            candidate = os.path.join(skill_dir, name)
            if os.path.isfile(candidate):
                skill_md = candidate
                break
        else:
            return "", ""

    try:
        with open(skill_md) as f:
            content = f.read()
    except OSError:
        return "", ""

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return "", ""

    frontmatter = match.group(1)
    name = ""
    description = ""
    for line in frontmatter.split("\n"):
        if line.startswith("name:"):
            name = line[5:].strip().strip("'\"")
        elif line.startswith("description:"):
            description = line[12:].strip().strip("'\"")

    return name, description


def _keywords_match(
    prompt: str, description: str, threshold: int = 2,
) -> bool:
    """Check if enough keywords from the description appear in the prompt."""
    if not prompt or not description:
        return False

    stop_words = {
        "a", "an", "the", "and", "or", "to", "in", "on", "for", "of",
        "is", "are", "was", "were", "be", "been", "with", "that", "this",
        "from", "by", "at", "as", "it", "its", "use", "when", "can",
        "do", "does", "new", "will", "how", "what", "which",
    }

    desc_words = {
        w.lower() for w in re.findall(r"\w+", description)
        if len(w) > 2 and w.lower() not in stop_words
    }
    prompt_lower = prompt.lower()

    matches = sum(1 for w in desc_words if w in prompt_lower)
    return matches >= threshold


def detect_skill_not_triggered(
    steps: list[ConversationStep],
    skill_dir: str | None = None,
) -> list[Issue]:
    """Skill exists and prompt matches but was never loaded."""
    if not skill_dir:
        return []

    has_skill_load = any(s.step_type == "skill_load" for s in steps)
    if has_skill_load:
        return []

    name, description = _load_skill_description(skill_dir)
    if not description:
        return []

    prompt = _extract_user_prompt(steps)
    if not prompt:
        return []

    if not _keywords_match(prompt, description):
        return []

    anchor = 0
    for i, step in enumerate(steps):
        if step.step_type == "user_message":
            anchor = i
            break

    return [
        Issue(
            severity="warning",
            pattern="skill_not_triggered",
            step_index=anchor,
            description=(
                f"Skill '{name or 'unknown'}' was not triggered, but the "
                f"prompt appears to match its description. The skill's "
                f"trigger conditions or description may need improvement."
            ),
            impact_tokens=0,
            suggestion=(
                "Review the skill's description and trigger conditions. "
                "The description should contain keywords that match "
                "the types of prompts users will give. Consider making "
                "the description more specific or adding trigger keywords."
            ),
        )
    ]


# ---------------------------------------------------------------------------
# Pattern 10 — Inline code generation
# ---------------------------------------------------------------------------

_CODE_MARKERS = ("def ", "import ", "class ", "function ", "```", "const ", "let ", "var ")
_INLINE_CODE_THRESHOLD = 1000  # tokens


def detect_inline_code_generation(
    steps: list[ConversationStep],
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Model wrote significant code inline that could be a bundled script.

    Detects assistant_response steps with high token counts and code patterns
    in the preview. Suggests creating a reusable script in scripts/.

    Source: Blog post — "Deterministic operations should use pre-written
    Python scripts" for "consistency and repeatability". Scripts execute
    without loading code into context, saving tokens.
    """
    threshold = _INLINE_CODE_THRESHOLD
    issues: list[Issue] = []

    for i, step in enumerate(steps):
        if step.step_type != "assistant_response":
            continue
        if step.token_count < threshold:
            continue

        preview = step.raw_content_preview.lower()
        has_code = any(marker in preview for marker in _CODE_MARKERS)
        if not has_code:
            continue

        issues.append(
            Issue(
                severity="info",
                pattern="inline_code_generation",
                step_index=i,
                description=(
                    f"Model generated {step.token_count:,} tokens of inline "
                    f"code. Consider bundling as a reusable script in scripts/."
                ),
                impact_tokens=step.token_count,
                suggestion=(
                    "Create a script in scripts/ for this operation. "
                    "Scripts execute without loading code into context, "
                    "saving tokens and ensuring consistency. "
                    "Add to SKILL.md: ALWAYS use python scripts/<name>.py"
                ),
            )
        )

    return issues
