"""Build hierarchical treemap data from a SessionAnalysis."""


from skill_perf.core.pricing import estimate_cost
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.treemap import TreemapNode


def _issues_for_step(issues: list[Issue], step_index: int) -> list[Issue]:
    """Return issues that reference a specific step index."""
    return [i for i in issues if i.step_index == step_index]


def _make_leaf(
    name: str,
    token_count: int,
    category: str,
    model: str,
    issues: list[Issue] | None = None,
) -> TreemapNode:
    """Create a leaf TreemapNode with cost estimation."""
    issues = issues or []
    cost = estimate_cost(token_count, model, "input")
    return TreemapNode(
        name=name,
        token_count=token_count,
        effective_tokens=token_count - sum(i.impact_tokens for i in issues),
        cost_usd=cost,
        category=category,
        issues=issues,
        is_wasteful=len(issues) > 0,
    )


def _make_group(
    name: str,
    category: str,
    children: list[TreemapNode],
) -> TreemapNode:
    """Create a group TreemapNode that aggregates its children."""
    total_tokens = sum(c.token_count for c in children)
    total_effective = sum(c.effective_tokens for c in children)
    total_cost = sum(c.cost_usd for c in children)
    all_issues: list[Issue] = []
    for c in children:
        all_issues.extend(c.issues)
    return TreemapNode(
        name=name,
        token_count=total_tokens,
        effective_tokens=total_effective,
        cost_usd=total_cost,
        category=category,
        children=children,
        issues=all_issues,
        is_wasteful=any(c.is_wasteful for c in children),
    )


def build_treemap(
    session: SessionAnalysis,
    model: str = "claude-sonnet-4",
) -> TreemapNode:
    """Build hierarchical treemap data from session analysis.

    Hierarchy:
    - Root (session)
      - system_prompt
      - user_messages (group)
      - assistant_responses (group)
      - tool_calls (group)
        - individual tool calls by tool_name
      - tool_results (group)
        - individual results
      - skill_loads (group)
        - individual skill files

    Each leaf node = one ConversationStep.
    Mark nodes as wasteful if they have associated issues.
    """
    issues = session.issues

    # Collect steps by category
    system_leaves: list[TreemapNode] = []
    user_leaves: list[TreemapNode] = []
    assistant_leaves: list[TreemapNode] = []
    tool_call_leaves: list[TreemapNode] = []
    tool_result_leaves: list[TreemapNode] = []
    skill_load_leaves: list[TreemapNode] = []

    for idx, step in enumerate(session.steps):
        step_issues = _issues_for_step(issues, idx)
        desc = step.description or f"turn-{step.turn}"

        if step.step_type == "system_prompt":
            leaf = _make_leaf(desc, step.token_count, "system_prompt", model, step_issues)
            system_leaves.append(leaf)
        elif step.step_type == "user_message":
            leaf = _make_leaf(desc, step.token_count, "user_message", model, step_issues)
            user_leaves.append(leaf)
        elif step.step_type == "assistant_response":
            leaf = _make_leaf(
                desc, step.token_count, "assistant_response", model, step_issues
            )
            assistant_leaves.append(leaf)
        elif step.step_type == "tool_call":
            name = step.tool_name or desc
            leaf = _make_leaf(name, step.token_count, "tool_call", model, step_issues)
            tool_call_leaves.append(leaf)
        elif step.step_type == "tool_result":
            name = step.tool_name or desc
            leaf = _make_leaf(name, step.token_count, "tool_result", model, step_issues)
            tool_result_leaves.append(leaf)
        elif step.step_type == "skill_load":
            name = step.file_path or desc
            leaf = _make_leaf(name, step.token_count, "skill_load", model, step_issues)
            skill_load_leaves.append(leaf)

    # Build groups
    groups: list[TreemapNode] = []

    for leaves in system_leaves:
        groups.append(leaves)

    if user_leaves:
        groups.append(_make_group("user_messages", "user_message", user_leaves))
    if assistant_leaves:
        groups.append(
            _make_group("assistant_responses", "assistant_response", assistant_leaves)
        )
    if tool_call_leaves:
        groups.append(_make_group("tool_calls", "tool_call", tool_call_leaves))
    if tool_result_leaves:
        groups.append(_make_group("tool_results", "tool_result", tool_result_leaves))
    if skill_load_leaves:
        groups.append(_make_group("skill_loads", "skill_load", skill_load_leaves))

    # Root node
    total_tokens = sum(g.token_count for g in groups)
    total_effective = sum(g.effective_tokens for g in groups)
    total_cost = sum(g.cost_usd for g in groups)
    all_issues: list[Issue] = []
    for g in groups:
        all_issues.extend(g.issues)

    return TreemapNode(
        name=session.session_id,
        token_count=total_tokens,
        effective_tokens=total_effective,
        cost_usd=total_cost,
        category="session",
        children=groups,
        issues=all_issues,
        is_wasteful=any(g.is_wasteful for g in groups),
    )
