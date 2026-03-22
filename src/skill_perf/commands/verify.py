"""Verify command — compare baseline vs current trace sessions.

Loads two trace directories, computes token/cost deltas, and shows
which issues were resolved or remain.
"""

from __future__ import annotations

import os
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from rich.console import Console

from skill_perf.core.pricing import estimate_cost
from skill_perf.diagnosis.engine import diagnose
from skill_perf.models.benchmark import BenchmarkResult
from skill_perf.models.comparison import Comparison
from skill_perf.models.diagnosis import Issue
from skill_perf.parser.trace_reader import parse_session
from skill_perf.report.html import generate_html_report

console = Console()

_SEVERITY_ICONS: dict[str, str] = {
    "critical": "\U0001f534",
    "warning": "\U0001f7e1",
    "info": "\U0001f7e2",
}


def _load_benchmark(trace_dir: str, label: str) -> BenchmarkResult:
    """Load a trace directory into a BenchmarkResult.

    Parse the session, run diagnosis, compute totals.
    """
    if not os.path.isdir(trace_dir):
        raise FileNotFoundError(f"Trace directory not found: {trace_dir}")

    session = parse_session(trace_dir)
    issues = diagnose(session)
    session.issues = issues

    model = session.model or "claude-sonnet-4"
    total_tokens = session.total_estimated_tokens
    total_cost = estimate_cost(
        session.api_input_tokens, model, "input"
    ) + estimate_cost(session.api_output_tokens, model, "output")

    # Fall back to token-based estimate if API tokens are zero
    if total_cost == 0.0 and total_tokens > 0:
        total_cost = estimate_cost(total_tokens, model, "input")

    return BenchmarkResult(
        run_id=str(uuid4())[:8],
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        skill_name=label,
        sessions=[session],
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
        total_issues=len(issues),
    )


def _compare(baseline: BenchmarkResult, current: BenchmarkResult) -> Comparison:
    """Compute comparison between baseline and current."""
    token_delta = current.total_tokens - baseline.total_tokens
    cost_delta = current.total_cost_usd - baseline.total_cost_usd

    # Collect all issues from both sides
    baseline_issues: list[Issue] = []
    for s in baseline.sessions:
        baseline_issues.extend(s.issues)

    current_issues: list[Issue] = []
    for s in current.sessions:
        current_issues.extend(s.issues)

    # An issue is "resolved" if its pattern+step_index combo from baseline
    # is not found in current.
    current_keys = {(i.pattern, i.step_index) for i in current_issues}

    issues_resolved = [
        i for i in baseline_issues
        if (i.pattern, i.step_index) not in current_keys
    ]
    issues_remaining = [
        i for i in current_issues
        if (i.pattern, i.step_index) in current_keys
    ]

    return Comparison(
        baseline=baseline,
        current=current,
        token_delta=token_delta,
        cost_delta=round(cost_delta, 6),
        issues_resolved=issues_resolved,
        issues_remaining=issues_remaining,
    )


def _print_verification(comp: Comparison) -> None:
    """Print Rich terminal output for verification results."""
    b = comp.baseline
    c = comp.current

    # Percentage calculations (guard against zero baseline)
    token_pct = (
        (comp.token_delta / b.total_tokens * 100) if b.total_tokens else 0.0
    )
    cost_pct = (
        (comp.cost_delta / b.total_cost_usd * 100) if b.total_cost_usd else 0.0
    )

    # Delta sign formatting
    def _fmt_delta(val: int | float, prefix: str = "", suffix: str = "") -> str:
        sign = "+" if val > 0 else ""
        if isinstance(val, float):
            return f"{sign}{prefix}{val:,.3f}{suffix}"
        return f"{sign}{prefix}{val:,}{suffix}"

    def _fmt_pct(val: float) -> str:
        sign = "+" if val > 0 else ""
        return f"{sign}{val:.1f}%"

    console.print()
    console.print("  [bold]VERIFICATION[/bold]")
    console.print("  " + "\u2550" * 43)

    console.print(
        f"  Baseline ({b.skill_name}):  "
        f"{b.total_tokens:>8,} tokens  |  "
        f"${b.total_cost_usd:.3f}"
    )
    console.print(
        f"  Current  ({c.skill_name}):  "
        f"{c.total_tokens:>8,} tokens  |  "
        f"${c.total_cost_usd:.3f}"
    )
    console.print("  " + " " * 18 + "\u2500" * 25)

    # Color the delta line based on improvement vs regression
    delta_color = "green" if comp.token_delta <= 0 else "red"
    delta_line = (
        f"  Improvement:   "
        f"{_fmt_delta(comp.token_delta)} tokens  | "
        f"{_fmt_delta(comp.cost_delta, prefix='$')}"
    )
    pct_line = (
        f"                     "
        f"{_fmt_pct(token_pct)}      |  "
        f"{_fmt_pct(cost_pct)}"
    )
    console.print(f"  [{delta_color}]{delta_line.strip()}[/{delta_color}]")
    console.print(f"  [{delta_color}]{pct_line.strip()}[/{delta_color}]")

    console.print()

    # Issues summary
    n_resolved = len(comp.issues_resolved)
    n_remaining = len(comp.issues_remaining)
    b_total = sum(len(s.issues) for s in b.sessions)

    console.print(
        f"  Issues resolved:  \U0001f534{b_total} -> "
        f"\u2705{b_total - n_resolved}"
    )
    if n_remaining:
        console.print(f"  Issues remaining: \U0001f7e2{n_remaining}")
    else:
        console.print("  Issues remaining: none")

    console.print("  " + "\u2550" * 43)
    console.print()


def run_verify(
    baseline_path: str,
    current_path: str | None = None,
    json_output: bool = False,
    open_browser: bool = False,
    report_path: str | None = None,
) -> None:
    """Run verification comparing baseline vs current."""
    # Load baseline
    baseline = _load_benchmark(baseline_path, "baseline")

    # If no current provided, just show baseline stats
    if current_path is None:
        console.print(
            f"[bold]Baseline loaded:[/bold] "
            f"{baseline.total_tokens:,} tokens, "
            f"${baseline.total_cost_usd:.3f}, "
            f"{baseline.total_issues} issues"
        )
        if json_output:
            console.print_json(baseline.model_dump_json(indent=2))
        return

    # Load current
    current = _load_benchmark(current_path, "current")

    # Compare
    comp = _compare(baseline, current)

    if json_output:
        console.print_json(comp.model_dump_json(indent=2))
        return

    # Print terminal report
    _print_verification(comp)

    # HTML reports
    if open_browser or report_path:
        out_dir = report_path or "."
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        baseline_html = os.path.join(out_dir, "baseline.html")
        current_html = os.path.join(out_dir, "current.html")

        b_session = baseline.sessions[0]
        b_issues = list(b_session.issues)
        generate_html_report(
            b_session, b_issues, output_path=baseline_html,
            model=b_session.model or "claude-sonnet-4",
        )

        c_session = current.sessions[0]
        c_issues = list(c_session.issues)
        generate_html_report(
            c_session, c_issues, output_path=current_html,
            model=c_session.model or "claude-sonnet-4",
        )

        console.print(f"  Reports written to: {baseline_html}, {current_html}")

        if open_browser:
            webbrowser.open(f"file://{os.path.abspath(baseline_html)}")
            webbrowser.open(f"file://{os.path.abspath(current_html)}")
