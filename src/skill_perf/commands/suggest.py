"""Run suggestion generator on trace directories."""


import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from skill_perf.core.config import ThresholdConfig
from skill_perf.diagnosis import diagnose
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.parser.trace_reader import parse_session
from skill_perf.suggestion.generator import estimate_savings, generate_suggestion

console = Console()

SEVERITY_ICON: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "warning": "\U0001f7e1",  # yellow circle
    "info": "\U0001f7e2",  # green circle
}


def _print_health_check(session: SessionAnalysis, config: ThresholdConfig) -> None:
    """Print a threshold health table when no issues are detected."""
    skill_tokens = session.tokens_by_type.get("skill_load", 0)
    think_ratio = session.think_act_ratio or 0.0
    cache_ratio = (
        round(session.api_input_tokens / session.total_estimated_tokens, 2)
        if session.total_estimated_tokens > 0
        else 0.0
    )

    rows = [
        (
            "skill body tokens",
            f"{skill_tokens:,}",
            f"{config.oversized_skill_tokens:,}",
            skill_tokens <= config.oversized_skill_tokens,
        ),
        (
            "think / act ratio",
            f"{think_ratio:.2f}x",
            f"{config.high_think_ratio:.1f}x",
            think_ratio <= config.high_think_ratio,
        ),
        (
            "cache rate ratio",
            f"{cache_ratio:.2f}x",
            f"{config.low_cache_rate_ratio:.1f}x",
            cache_ratio <= config.low_cache_rate_ratio,
        ),
    ]

    table = Table(box=None, padding=(0, 2), show_header=True)
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_column("Threshold", justify="right", style="dim")
    table.add_column("Status", justify="center")

    for name, value, threshold, ok in rows:
        status = "[green]✓[/green]" if ok else "[yellow]near[/yellow]"
        table.add_row(name, value, threshold, status)

    console.print(f"\n  [green]✓ No issues — all metrics within thresholds[/green]")
    console.print(f"  [dim]Session:[/dim] {session.session_id} ({session.model or 'unknown'})")
    console.print()
    console.print(table)


def _print_suggestion(
    index: int,
    total: int,
    issue: Issue,
    suggestion_text: str,
    tokens_saved: int,
    cost_saved: float,
    step_tool_name: str | None = None,
    step_file_path: str | None = None,
    step_token_count: int | None = None,
) -> None:
    """Print a single suggestion with Rich formatting."""
    icon = SEVERITY_ICON.get(issue.severity, "")
    header = f"FIX {index} of {total}: {issue.pattern} ({icon} {issue.severity})"
    console.print()
    console.print(f"  [bold]{header}[/bold]")
    console.print(f"  {'─' * 46}")
    console.print(
        f"  Step [{issue.step_index}]: {issue.description} "
        f"([red]+{issue.impact_tokens:,} tokens over threshold[/red])"
    )

    # Show step-specific context if available
    if step_tool_name or step_file_path:
        parts = [f"  Step [{issue.step_index}]:"]
        if step_tool_name:
            parts.append(step_tool_name)
        if step_file_path:
            parts.append(f"on {step_file_path}")
        if step_token_count is not None:
            parts.append(f"({step_token_count:,} tokens)")
        console.print(" ".join(parts), style="dim")

    panel = Panel(
        suggestion_text.strip(),
        expand=False,
        padding=(0, 1),
    )
    console.print(panel)

    console.print(
        f"  Estimated savings: ~{tokens_saved:,} tokens/call (${cost_saved:.4f})"
    )


def run_suggest(
    paths: list[str],
    skill_dir: str | None = None,
    json_output: bool = False,
    config_path: str | None = None,
) -> None:
    """Run suggestion generator on trace directories."""
    from skill_perf.core.config import load_config

    config = load_config(config_path)
    all_suggestions: list[dict[str, object]] = []

    for path in paths:
        session = parse_session(path)
        issues = diagnose(session, skill_dir=skill_dir, config=config)
        session.issues = issues

        total = len(issues)
        if total == 0 and not json_output:
            _print_health_check(session, config)
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
                # Extract step context for display
                step_tool_name = None
                step_file_path = None
                step_token_count = None
                if 0 <= issue.step_index < len(session.steps):
                    step = session.steps[issue.step_index]
                    step_tool_name = step.tool_name
                    step_file_path = step.file_path
                    step_token_count = step.token_count

                _print_suggestion(
                    idx,
                    total,
                    issue,
                    suggestion_text,
                    tokens_saved,
                    cost_saved,
                    step_tool_name=step_tool_name,
                    step_file_path=step_file_path,
                    step_token_count=step_token_count,
                )

    if json_output:
        console.print_json(json.dumps(all_suggestions, indent=2))
