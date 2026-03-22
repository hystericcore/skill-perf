"""Implementation of the `skill-perf init` command."""

from __future__ import annotations

import importlib.resources
import os
import shutil

from rich.console import Console

console = Console()


def _get_package_root() -> str:
    """Get the installed package root directory."""
    ref = importlib.resources.files("skill_perf")
    # Go up from src/skill_perf/ to project root
    return str(ref.joinpath("..", "..").resolve())  # type: ignore[arg-type]


def run_init(output_dir: str = ".") -> None:
    """Copy SKILL.md and references/ to the target directory."""
    pkg_root = _get_package_root()
    skill_src = os.path.join(pkg_root, "SKILL.md")
    refs_src = os.path.join(pkg_root, "references")

    if not os.path.exists(skill_src):
        console.print(
            "[red]Error:[/red] SKILL.md not found in package. "
            "Download from: https://github.com/hystericcore/skill-perf"
        )
        raise SystemExit(1)

    skill_dst = os.path.join(output_dir, "SKILL.md")
    refs_dst = os.path.join(output_dir, "references")

    # Copy SKILL.md
    if os.path.exists(skill_dst):
        console.print(f"[yellow]SKILL.md already exists at {skill_dst}, skipping[/yellow]")
    else:
        shutil.copy2(skill_src, skill_dst)
        console.print(f"[green]Created[/green] {skill_dst}")

    # Copy references/
    if os.path.exists(refs_dst):
        console.print(
            f"[yellow]references/ already exists at {refs_dst}, skipping[/yellow]"
        )
    else:
        shutil.copytree(refs_src, refs_dst)
        console.print(f"[green]Created[/green] {refs_dst}/")

    console.print()
    console.print("[bold]skill-perf skill installed.[/bold]")
    console.print(
        "Your AI coding assistant can now use skill-perf to analyze and improve skills."
    )
    console.print()
    console.print("[dim]Quick start:[/dim]")
    console.print("  skill-perf estimate ./SKILL.md")
    console.print("  skill-perf diagnose ./traces/")
