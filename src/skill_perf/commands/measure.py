"""Implementation of the `skill-perf measure` command."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table

from skill_perf.capture.proxy import ProxyManager
from skill_perf.capture.runner import CLIRunner, RunResult
from skill_perf.capture.suite import load_suite

console = Console()


def _make_run_dir(output_dir: str) -> str:
    """Create a timestamped run directory and return its path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(output_dir, f"bench_{timestamp}")
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def _print_summary(results: list[tuple[str, RunResult]], trace_dir: str) -> None:
    """Print a Rich summary table of run results."""
    table = Table(title="Measure Results")
    table.add_column("Label", style="cyan")
    table.add_column("Exit Code", justify="right")
    table.add_column("Duration (ms)", justify="right")
    table.add_column("Status", style="bold")

    for label, result in results:
        status = "[green]OK[/green]" if result.exit_code == 0 else "[red]FAIL[/red]"
        if result.exit_code == -1:
            status = "[yellow]TIMEOUT[/yellow]"
        table.add_row(
            label,
            str(result.exit_code),
            str(result.duration_ms),
            status,
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]Traces saved to:[/dim] {trace_dir}")
    console.print(f"[dim]Runs completed:[/dim]  {len(results)}")


def run_measure(
    prompt: Optional[str],
    suite_path: Optional[str],
    cli: str,
    port: int,
    output_dir: str,
    max_turns: int,
    timeout: int,
    do_diagnose: bool,
    open_browser: bool,
    compare: bool,
    skill_a: Optional[str],
    skill_b: Optional[str],
) -> None:
    """Orchestrate: start proxy -> run CLI -> capture traces -> optionally diagnose."""
    # --- Validate inputs ---
    if not prompt and not suite_path:
        console.print("[red]Error:[/red] Provide --prompt or --suite")
        raise SystemExit(1)

    if compare and (not skill_a or not skill_b):
        console.print("[red]Error:[/red] --compare requires both --skill-a and --skill-b")
        raise SystemExit(1)

    # --- Create output directory ---
    run_dir = _make_run_dir(output_dir)
    trace_dir = os.path.join(run_dir, "traces")
    os.makedirs(trace_dir, exist_ok=True)

    results: list[tuple[str, RunResult]] = []
    runner = CLIRunner(proxy_port=port)

    console.print(f"[bold]skill-perf measure[/bold]  output={run_dir}")

    # --- Start proxy, run workloads, stop proxy ---
    proxy = ProxyManager(port=port, trace_dir=trace_dir)
    try:
        proxy.start()
        console.print(f"[green]Proxy started[/green] on port {port}")

        if compare:
            # A/B comparison mode
            assert prompt is not None  # validated above
            console.print(f"[cyan]A/B compare:[/cyan] skill_a={skill_a}  skill_b={skill_b}")

            result_a = runner.run(
                prompt, cli=cli, max_turns=max_turns, timeout=timeout, skill_dir=skill_a
            )
            results.append(("skill_a", result_a))

            result_b = runner.run(
                prompt, cli=cli, max_turns=max_turns, timeout=timeout, skill_dir=skill_b
            )
            results.append(("skill_b", result_b))

        elif suite_path:
            # Suite mode
            test_cases = load_suite(suite_path)
            console.print(f"[cyan]Suite:[/cyan] {len(test_cases)} test cases from {suite_path}")

            for tc in test_cases:
                console.print(f"  Running: {tc.label}")
                result = runner.run(
                    tc.prompt, cli=cli, max_turns=max_turns, timeout=timeout
                )
                results.append((tc.label, result))

        else:
            # Single prompt mode
            assert prompt is not None
            console.print(f"  Running: {prompt[:80]}...")
            result = runner.run(
                prompt, cli=cli, max_turns=max_turns, timeout=timeout
            )
            results.append(("single", result))

    finally:
        proxy.stop()
        console.print("[green]Proxy stopped[/green]")

    # --- Check if any traces were captured ---
    trace_files = [
        f for f in os.listdir(trace_dir)
        if f.endswith(".jsonl") and os.path.getsize(os.path.join(trace_dir, f)) > 0
    ] if os.path.isdir(trace_dir) else []
    if not trace_files:
        console.print(
            "[yellow]Warning:[/yellow] No trace files captured. "
            "Check that the proxy was running and the CLI sent requests through it."
        )

    # --- Optional diagnosis ---
    if do_diagnose:
        console.print("[cyan]Running diagnosis on captured traces...[/cyan]")
        _run_diagnosis(trace_dir, open_browser)

    # --- Summary ---
    _print_summary(results, trace_dir)


def _run_diagnosis(trace_dir: str, open_browser: bool) -> None:
    """Parse captured traces and run diagnosis."""
    from skill_perf.diagnosis.engine import diagnose
    from skill_perf.parser.trace_reader import parse_session

    sessions_found = 0

    # Try the trace_dir itself first (lli puts split_output/ and merged.jsonl here)
    dirs_to_try = [trace_dir]
    # Also try subdirectories (for multi-session captures)
    for entry in os.listdir(trace_dir):
        entry_path = os.path.join(trace_dir, entry)
        if os.path.isdir(entry_path) and entry != "split_output":
            dirs_to_try.append(entry_path)

    for session_path in dirs_to_try:
        try:
            session = parse_session(session_path)
            if not session.steps:
                continue
            sessions_found += 1
            issues = diagnose(session)
            session.issues = issues
            console.print(
                f"  Session {session.session_id}: "
                f"input={session.api_input_tokens:,} "
                f"output={session.api_output_tokens:,} "
                f"model={session.model} "
                f"issues={len(issues)}"
            )
            for issue in issues:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}[issue.severity]
                console.print(f"    {icon} {issue.pattern}: {issue.description}")
        except Exception as exc:
            console.print(f"  [yellow]Skipped {session_path}: {exc}[/yellow]")

    if sessions_found == 0:
        console.print("  [dim]No session traces found to diagnose.[/dim]")
