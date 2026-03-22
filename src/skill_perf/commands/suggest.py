"""Run suggestion generator on trace directories."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel

from skill_perf.diagnosis import diagnose
from skill_perf.models.diagnosis import Issue
from skill_perf.parser.trace_reader import parse_session
from skill_perf.suggestion.generator import estimate_savings, generate_suggestion

console = Console()

SEVERITY_ICON: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "warning": "\U0001f7e1",  # yellow circle
    "info": "\U0001f7e2",  # green circle
}


def _print_suggestion(
    index: int,
    total: int,
    issue: Issue,
    suggestion_text: str,
    tokens_saved: int,
    cost_saved: float,
) -> None:
    """Print a single suggestion with Rich formatting."""
    icon = SEVERITY_ICON.get(issue.severity, "")
    header = f"FIX {index} of {total}: {issue.pattern} ({icon} {issue.severity})"
    console.print()
    console.print(f"  [bold]{header}[/bold]")
    console.print(f"  {'─' * 46}")
    console.print(
        f"  Step [{issue.step_index}]: {issue.description} "
        f"({issue.impact_tokens:,} tokens)"
    )

    panel = Panel(
        suggestion_text.strip(),
        expand=False,
        padding=(0, 1),
    )
    console.print(panel)

    console.print(
        f"  Estimated savings: ~{tokens_saved:,} tokens/call (${cost_saved:.4f})"
    )


def run_suggest(paths: list[str], json_output: bool = False) -> None:
    """Run suggestion generator on trace directories."""
    all_suggestions: list[dict] = []

    for path in paths:
        session = parse_session(path)
        issues = diagnose(session)
        session.issues = issues

        total = len(issues)
        if total == 0 and not json_output:
            console.print(
                f"\n  [green]No issues found[/green] in session {session.session_id}"
            )
            continue

        if not json_output:
            console.print(
                f"\n  [bold]Session:[/bold] {session.session_id} "
                f"({session.model or 'unknown model'})"
            )

        for idx, issue in enumerate(issues, start=1):
            suggestion_text = generate_suggestion(issue, session)
            tokens_saved, cost_saved = estimate_savings(
                issue, model=session.model or "claude-sonnet-4"
            )

            if json_output:
                all_suggestions.append(
                    {
                        "session_id": session.session_id,
                        "fix_number": idx,
                        "pattern": issue.pattern,
                        "severity": issue.severity,
                        "step_index": issue.step_index,
                        "description": issue.description,
                        "impact_tokens": issue.impact_tokens,
                        "suggestion": suggestion_text.strip(),
                        "estimated_tokens_saved": tokens_saved,
                        "estimated_cost_saved_usd": cost_saved,
                    }
                )
            else:
                _print_suggestion(
                    idx, total, issue, suggestion_text, tokens_saved, cost_saved
                )

    if json_output:
        console.print_json(json.dumps(all_suggestions, indent=2))
