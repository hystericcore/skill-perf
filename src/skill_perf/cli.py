from typing import Optional

import typer

from skill_perf.commands.estimate import run_estimate
from skill_perf.commands.measure import run_measure

app = typer.Typer(
    name="skill-perf",
    help="webpack-bundle-analyzer for LLM context. "
    "Measure, diagnose, and improve skill performance.",
    no_args_is_help=True,
)


@app.command()
def init(
    output: str = typer.Argument(
        ".", help="Target project directory (default: current directory)"
    ),
    global_install: bool = typer.Option(
        False, "--global", help="Install globally to ~/.claude/agents/"
    ),
    force: bool = typer.Option(
        False, "--force", help="Overwrite existing skill files"
    ),
) -> None:
    """Install the skill-perf skill for AI coding assistants."""
    from skill_perf.commands.init import run_init

    run_init(output_dir=output, global_install=global_install, force=force)


@app.command()
def estimate(
    paths: list[str] = typer.Argument(..., help="Path(s) to SKILL.md file(s) or directories"),
    compare: bool = typer.Option(False, "--compare", help="Compare multiple skill versions"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Offline skill analysis -- token count, cost estimate, structure check."""
    run_estimate(paths, compare=compare, json_output=json_output)


@app.command()
def measure(
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="Single prompt to run"),
    suite: Optional[str] = typer.Option(None, "--suite", help="Test suite JSON file"),
    cli: str = typer.Option("claude", "--cli", help="CLI tool (claude, aider, cursor-cli)"),
    port: int = typer.Option(9090, "--port", help="Proxy port"),
    output: str = typer.Option("./bench_results", "--output", help="Output directory"),
    max_turns: int = typer.Option(3, "--max-turns", help="Max conversation turns"),
    timeout: int = typer.Option(120, "--timeout", help="Timeout per run in seconds"),
    do_diagnose: bool = typer.Option(False, "--diagnose", help="Run diagnosis after capture"),
    open_browser: bool = typer.Option(False, "--open", help="Open HTML report"),
    compare: bool = typer.Option(False, "--compare", help="A/B comparison mode"),
    skill_a: Optional[str] = typer.Option(None, "--skill-a", help="Skill version A directory"),
    skill_b: Optional[str] = typer.Option(None, "--skill-b", help="Skill version B directory"),
) -> None:
    """Run a skill and capture real token usage via proxy + CLI execution."""
    run_measure(
        prompt=prompt,
        suite_path=suite,
        cli=cli,
        port=port,
        output_dir=output,
        max_turns=max_turns,
        timeout=timeout,
        do_diagnose=do_diagnose,
        open_browser=open_browser,
        compare=compare,
        skill_a=skill_a,
        skill_b=skill_b,
    )


@app.command()
def diagnose(
    paths: list[str] = typer.Argument(..., help="Path(s) to trace session directories"),
    skill_dir: Optional[str] = typer.Option(
        None, "--skill", help="Path to skill directory for script detection"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    open_browser: bool = typer.Option(False, "--open", help="Open HTML treemap in browser"),
    static: bool = typer.Option(
        False, "--static", help="Generate static HTML report"
    ),
    report: Optional[str] = typer.Option(None, "--report", help="Output HTML report path"),
) -> None:
    """Find underperforming steps and waste patterns."""
    from skill_perf.commands.diagnose import run_diagnose

    run_diagnose(
        paths,
        skill_dir=skill_dir,
        json_output=json_output,
        open_browser=open_browser,
        static=static,
        report=report,
    )


@app.command()
def suggest(
    paths: list[str] = typer.Argument(..., help="Path(s) to trace session directories"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get actionable fix suggestions for diagnosed issues."""
    from skill_perf.commands.suggest import run_suggest

    run_suggest(paths, json_output=json_output)


@app.command()
def verify(
    baseline: str = typer.Option(..., "--baseline", "-b", help="Path to baseline trace directory"),
    current: Optional[str] = typer.Option(
        None, "--current", "-c", help="Path to current trace directory"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    open_browser: bool = typer.Option(False, "--open", help="Open side-by-side HTML report"),
    report: Optional[str] = typer.Option(None, "--report", help="Output report directory path"),
) -> None:
    """Re-run and confirm improvements against a baseline."""
    from skill_perf.commands.verify import run_verify

    run_verify(
        baseline,
        current_path=current,
        json_output=json_output,
        open_browser=open_browser,
        report_path=report,
    )


if __name__ == "__main__":
    app()
