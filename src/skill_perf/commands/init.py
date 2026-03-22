"""Implementation of the `skill-perf init` command."""

from __future__ import annotations

import importlib.resources
import os
import shutil

from rich.console import Console

console = Console()

SKILL_FILENAME = "skill-perf.md"
GITHUB_URL = "https://github.com/hystericcore/skill-perf"


def _get_skill_dir() -> str:
    """Get the path to the bundled skill/ directory in the package."""
    ref = importlib.resources.files("skill_perf")
    # Go up from src/skill_perf/ to project root, then into skill/
    skill_dir = str(ref.joinpath("..", "..", "skill").resolve())  # type: ignore[arg-type]
    if not os.path.isdir(skill_dir):
        console.print(
            f"[red]Error:[/red] Bundled skill files not found.\n"
            f"Download from: {GITHUB_URL}"
        )
        raise SystemExit(1)
    return skill_dir


def _install_skill(
    target_dir: str,
    skill_filename: str,
    force: bool = False,
) -> None:
    """Copy the skill file and references to the target directory."""
    skill_src_dir = _get_skill_dir()
    skill_src = os.path.join(skill_src_dir, SKILL_FILENAME)
    refs_src = os.path.join(skill_src_dir, "references")

    os.makedirs(target_dir, exist_ok=True)

    skill_dst = os.path.join(target_dir, skill_filename)
    refs_dst = os.path.join(target_dir, "references")

    # Copy skill file
    if os.path.exists(skill_dst) and not force:
        console.print(
            f"[yellow]Already exists:[/yellow] {skill_dst} (use --force to overwrite)"
        )
    else:
        shutil.copy2(skill_src, skill_dst)
        console.print(f"[green]Created[/green] {skill_dst}")

    # Copy references/
    if os.path.exists(refs_dst) and not force:
        console.print(
            f"[yellow]Already exists:[/yellow] {refs_dst}/ (use --force to overwrite)"
        )
    else:
        if os.path.exists(refs_dst):
            shutil.rmtree(refs_dst)
        shutil.copytree(refs_src, refs_dst)
        console.print(f"[green]Created[/green] {refs_dst}/")


def run_init(
    output_dir: str = ".",
    global_install: bool = False,
    force: bool = False,
) -> None:
    """Install the skill-perf skill for AI coding assistants."""
    if global_install:
        # Install to ~/.claude/agents/ (available in all projects)
        target = os.path.expanduser("~/.claude/agents")
        _install_skill(target, SKILL_FILENAME, force=force)
        console.print()
        console.print("[bold]skill-perf skill installed globally.[/bold]")
        console.print(
            f"[dim]Location:[/dim] {target}/{SKILL_FILENAME}"
        )
    else:
        # Install to .claude/skills/ in the target directory (workspace-level)
        target = os.path.join(output_dir, ".claude", "skills")
        _install_skill(target, SKILL_FILENAME, force=force)
        console.print()
        console.print("[bold]skill-perf skill installed to workspace.[/bold]")
        console.print(
            f"[dim]Location:[/dim] {target}/{SKILL_FILENAME}"
        )

    console.print()
    console.print("[dim]Next steps:[/dim]")
    console.print("  1. Reload plugins in your AI assistant")
    console.print("  2. Run: skill-perf diagnose ./traces/")
    console.print(
        "  3. Ask your assistant to improve your skill based on the output"
    )
