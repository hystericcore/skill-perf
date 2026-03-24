"""Implementation of the `skill-perf measure` command."""


import json
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


def _truncate_lines(text: str, max_lines: int = 3, max_width: int = 80) -> str:
    """Truncate text to max_lines, each line to max_width chars."""
    lines = text.splitlines()
    preview_lines = []
    for line in lines[:max_lines]:
        if len(line) > max_width:
            preview_lines.append(line[:max_width] + "...")
        else:
            preview_lines.append(line)
    if len(lines) > max_lines:
        preview_lines.append("...")
    return "\n".join(preview_lines)


def _format_stdout_preview(stdout: str) -> str:
    """Return a compact preview of stdout content."""
    if not stdout:
        return "(empty)"
    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and "result" in data:
            result_text = str(data["result"])
            if not result_text:
                return "JSON response (empty result)"
            return _truncate_lines(result_text)
        return f"JSON object ({len(stdout)} chars)"
    except (json.JSONDecodeError, ValueError):
        pass
    return _truncate_lines(stdout)


def _format_stderr_preview(stderr: str) -> str:
    """Return a compact preview of stderr content."""
    if not stderr:
        return ""
    lines = stderr.splitlines()
    preview_lines = []
    for line in lines[:2]:
        if len(line) > 80:
            preview_lines.append(line[:80] + "...")
        else:
            preview_lines.append(line)
    if len(lines) > 2:
        preview_lines.append("...")
    return "\n".join(preview_lines)


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _check_skill_loaded(trace_dir: str) -> bool:
    """Check if any skill was loaded by scanning trace files for Skill tool usage."""
    for fname in os.listdir(trace_dir):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(trace_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    if '"Skill"' in line or '"skill_load"' in line:
                        return True
        except (OSError, UnicodeDecodeError):
            continue
    # Also check split_output/ if it exists
    split_dir = os.path.join(trace_dir, "split_output")
    if os.path.isdir(split_dir):
        for fname in os.listdir(split_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(split_dir, fname)
            try:
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                    if '"Skill"' in content:
                        return True
            except (OSError, UnicodeDecodeError):
                continue
    return False


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

    # Detail section: stdout/stderr previews per result
    for label, result in results:
        console.print(f"\n[bold cyan]{label}[/bold cyan]")
        stdout_preview = _format_stdout_preview(result.stdout)
        console.print(f"  [dim]stdout: {stdout_preview}[/dim]")
        stderr_preview = _format_stderr_preview(result.stderr)
        if stderr_preview:
            console.print(f"  [dim red]stderr: {stderr_preview}[/dim red]")

    # Trace file stats
    trace_files = [
        f for f in os.listdir(trace_dir)
        if f.endswith(".jsonl") and os.path.getsize(os.path.join(trace_dir, f)) > 0
    ] if os.path.isdir(trace_dir) else []

    total_size = sum(
        os.path.getsize(os.path.join(trace_dir, f)) for f in trace_files
    ) if trace_files else 0

    console.print(f"\n[dim]Traces saved to:[/dim] {trace_dir}")
    console.print(f"[dim]Trace files:[/dim]     {len(trace_files)} ({_format_size(total_size)})")
    console.print(f"[dim]Runs completed:[/dim]  {len(results)}")

    if not trace_files:
        console.print(
            "[yellow]Warning:[/yellow] No trace files captured. "
            "Check that the proxy was running and the CLI sent requests through it."
        )
        return

    # Check if any skill was loaded in the captured traces
    skill_loaded = _check_skill_loaded(trace_dir)
    if skill_loaded:
        console.print(f"[dim]Skill loaded:[/dim]    [green]yes[/green]")
    else:
        console.print(f"[dim]Skill loaded:[/dim]    [yellow]no[/yellow]")
        console.print(
            "[yellow]Warning:[/yellow] No skill was loaded during this run. "
            "Diagnosis results may not reflect skill performance."
        )


def _auto_snapshot(skill_dirs: list[str]) -> None:
    """Snapshot each valid skill directory, silently skipping missing ones."""
    from skill_perf.commands.snapshot import run_snapshot

    for d in skill_dirs:
        if d and os.path.isfile(os.path.join(d, "SKILL.md")):
            run_snapshot(d)
        elif d:
            console.print(f"[yellow]Snapshot skipped:[/yellow] no SKILL.md in {d}")


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
    skill_dir: Optional[str] = None,
    skill_a: Optional[str] = None,
    skill_b: Optional[str] = None,
    auto_snapshot: bool = False,
    allowed_tools: str = "*",
    model: Optional[str] = None,
) -> None:
    """Orchestrate: start proxy -> run CLI -> capture traces -> optionally diagnose."""
    # --- Validate inputs ---
    if not prompt and not suite_path:
        console.print("[red]Error:[/red] Provide --prompt or --suite")
        raise SystemExit(1)

    if compare and (not skill_a or not skill_b):
        console.print("[red]Error:[/red] --compare requires both --skill-a and --skill-b")
        raise SystemExit(1)

    # --- Auto-snapshot skill(s) before any changes ---
    if auto_snapshot:
        dirs = [skill_a, skill_b] if compare else [skill_dir]
        _auto_snapshot([d for d in dirs if d])

    # --- Create output directory ---
    run_dir = _make_run_dir(output_dir)
    trace_dir = os.path.join(run_dir, "traces")
    os.makedirs(trace_dir, exist_ok=True)

    results: list[tuple[str, RunResult]] = []
    runner = CLIRunner(proxy_port=port)

    model_label = model or "default"
    console.print(f"[bold]skill-perf measure[/bold]  output={run_dir}  model={model_label}")

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
                prompt, cli=cli, max_turns=max_turns, timeout=timeout,
                skill_dir=skill_a, allowed_tools=allowed_tools, model=model,
            )
            results.append(("skill_a", result_a))

            result_b = runner.run(
                prompt, cli=cli, max_turns=max_turns, timeout=timeout,
                skill_dir=skill_b, allowed_tools=allowed_tools, model=model,
            )
            results.append(("skill_b", result_b))

        elif suite_path:
            # Suite mode
            test_cases = load_suite(suite_path)
            console.print(f"[cyan]Suite:[/cyan] {len(test_cases)} test cases from {suite_path}")

            for tc in test_cases:
                console.print(f"  Running: {tc.label}")
                result = runner.run(
                    tc.prompt, cli=cli, max_turns=max_turns, timeout=timeout,
                    skill_dir=skill_dir, allowed_tools=allowed_tools, model=model,
                )
                results.append((tc.label, result))

        else:
            # Single prompt mode
            assert prompt is not None
            console.print(f"  Running: {prompt[:80]}...")
            result = runner.run(
                prompt, cli=cli, max_turns=max_turns, timeout=timeout,
                skill_dir=skill_dir, allowed_tools=allowed_tools, model=model,
            )
            results.append(("single", result))

    finally:
        proxy.stop()
        console.print("[green]Proxy stopped[/green]")

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
