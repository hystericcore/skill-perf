"""Diagnose command — find underperforming steps and waste patterns.

Parses captured LLI session directories, runs waste-pattern detectors,
and prints a Rich terminal report (or JSON).
"""

from __future__ import annotations

import json
import tempfile

from rich.console import Console
from rich.table import Table
from rich.text import Text

from skill_perf.diagnosis.engine import diagnose
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.parser.trace_reader import parse_session
from skill_perf.report import generate_html_report, serve_report

console = Console()

_SEVERITY_ICONS: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "warning": "\U0001f7e1",   # yellow circle
    "info": "\U0001f7e2",      # green circle
}

_BAR_COLORS: dict[str, str] = {
    "system_prompt": "bright_blue",
    "user_message": "cyan",
    "tool_call": "yellow",
    "tool_result": "magenta",
    "skill_load": "green",
    "assistant_response": "bright_red",
}


def _print_session_report(
    session_dir: str,
    skill_dir: str | None,
) -> tuple[dict[str, object], SessionAnalysis, list[Issue]] | None:
    """Analyse one session and print Rich output.

    Returns a tuple of (serialisable dict, session, issues) or ``None``
    if the session directory contains no steps.
    """
    session = parse_session(session_dir)

    if not session.steps:
        console.print(f"[bold red]No steps found in {session_dir}[/bold red]")
        return None

    # Run diagnosis
    issues = diagnose(session, skill_dir=skill_dir)
    session.issues = issues

    # --- Header ---
    console.print()
    console.rule(f"[bold]Session: {session.session_id}[/bold]")
    console.print(f"  Model: {session.model or '?'}")
    console.print(
        f"  API reported: in={session.api_input_tokens:,} "
        f"out={session.api_output_tokens:,}"
    )
    console.print(f"  Steps: {len(session.steps)}")

    # --- Step breakdown ---
    console.print()
    console.print("[bold]Step-by-step breakdown:[/bold]")
    for i, step in enumerate(session.steps):
        has_issue = any(iss.step_index == i for iss in issues)
        flag = " [bold red]!!![/bold red]" if has_issue else ""
        console.print(
            f"  [{i + 1:>3}] {step.step_type:<22} "
            f"{step.token_count:>8,} tokens{flag}"
        )
        console.print(f"        {step.description}")

    # --- Token distribution bar chart ---
    total = session.total_estimated_tokens or 1
    by_type = session.tokens_by_type

    console.print()
    console.print("[bold]Token distribution:[/bold]")

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Category", style="cyan", min_width=22)
    table.add_column("Tokens", justify="right", min_width=10)
    table.add_column("%", justify="right", min_width=7)
    table.add_column("Bar", min_width=30)

    for cat, tokens in sorted(by_type.items(), key=lambda x: -x[1]):
        pct = (tokens / total) * 100
        bar_len = int(pct / 2)
        color = _BAR_COLORS.get(cat, "white")
        bar_text = Text()
        bar_text.append("\u2588" * bar_len, style=color)
        bar_text.append("\u2591" * (25 - bar_len), style="dim")
        table.add_row(cat, f"{tokens:,}", f"{pct:.1f}%", bar_text)

    console.print(table)
    console.print(
        "  [dim]system_prompt = LLM instructions | "
        "user_message = conversation context[/dim]"
    )
    console.print(
        "  [dim]tool_call = model actions (Bash, Edit, Grep) | "
        "tool_result = data returned to model[/dim]"
    )
    console.print(
        "  [dim]skill_load = SKILL.md & references loaded | "
        "assistant_response = model output text[/dim]"
    )

    # --- Think/act ratio ---
    console.print(f"\n  Think/act ratio: {session.think_act_ratio:.2f}x")

    # --- Diagnosed issues ---
    if issues:
        waste_tokens = session.waste_tokens
        waste_pct = session.waste_percentage
        console.print(
            f"\n[bold]Diagnosed issues: {len(issues)} "
            f"(~{waste_tokens:,} waste tokens, {waste_pct:.1f}%)[/bold]"
        )
        for iss in issues:
            icon = _SEVERITY_ICONS.get(iss.severity, "?")
            console.print(
                f"  {icon} [{iss.severity}] {iss.pattern} "
                f"(step {iss.step_index + 1}, ~{iss.impact_tokens:,} tokens)"
            )
            console.print(f"      {iss.description}")
            console.print(f"      [dim]{iss.suggestion}[/dim]")
    else:
        console.print("\n  [green]No waste patterns detected.[/green]")

    # --- Total ---
    console.print(f"\n  Estimated total: {session.total_estimated_tokens:,} tokens")
    console.print()

    # Return serialisable dict alongside the parsed objects
    result_dict: dict[str, object] = {
        "session_id": session.session_id,
        "model": session.model,
        "api_input_tokens": session.api_input_tokens,
        "api_output_tokens": session.api_output_tokens,
        "total_estimated_tokens": session.total_estimated_tokens,
        "tokens_by_type": session.tokens_by_type,
        "tokens_by_tool": session.tokens_by_tool,
        "think_act_ratio": round(session.think_act_ratio, 4),
        "waste_tokens": session.waste_tokens,
        "waste_percentage": round(session.waste_percentage, 2),
        "issues": [iss.model_dump() for iss in issues],
        "steps": [
            {
                "turn": s.turn,
                "step_type": s.step_type,
                "description": s.description,
                "token_count": s.token_count,
                "tool_name": s.tool_name,
                "file_path": s.file_path,
            }
            for s in session.steps
        ],
    }
    return (result_dict, session, issues)


def run_diagnose(
    paths: list[str],
    skill_dir: str | None = None,
    json_output: bool = False,
    open_browser: bool = False,
    static: bool = False,
    report: str | None = None,
) -> None:
    """High-level entry point invoked by the Typer diagnose command."""
    results: list[dict[str, object]] = []
    sessions: list[tuple[SessionAnalysis, list[Issue]]] = []

    for path in paths:
        outcome = _print_session_report(path, skill_dir=skill_dir)
        if outcome is not None:
            result_dict, session, issues = outcome
            results.append(result_dict)
            sessions.append((session, issues))

    if not results:
        console.print("[bold red]No sessions found or parsed.[/bold red]")
        raise SystemExit(1)

    if json_output:
        console.print_json(json.dumps(results, indent=2))

    # --- HTML report generation ---
    # Use the last parsed session for the report (multi-session reports
    # could be extended later; for now one treemap per invocation).
    if report or static or open_browser:
        last_session, last_issues = sessions[-1]
        model = last_session.model or "claude-sonnet-4"

        if report:
            generate_html_report(
                last_session, last_issues, output_path=report, model=model,
            )
            console.print(f"[green]HTML report saved to {report}[/green]")

        if static:
            static_path = "./skill-perf-report.html"
            generate_html_report(
                last_session, last_issues, output_path=static_path, model=model,
            )
            console.print(f"[green]Static HTML report saved to {static_path}[/green]")

        if open_browser:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".html", prefix="skill-perf-", delete=False,
            )
            tmp.close()
            generate_html_report(
                last_session, last_issues, output_path=tmp.name, model=model,
            )
            console.print(f"[green]HTML report generated at {tmp.name}[/green]")
            serve_report(tmp.name)
