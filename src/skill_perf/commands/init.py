"""Implementation of the `skill-perf init` command."""


import importlib.resources
import os
import shutil

from rich.console import Console

console = Console()

SKILL_DIR_NAME = "skill-perf"
GITHUB_URL = "https://github.com/hystericcore/skill-perf"


def _get_skill_source_dir() -> str:
    """Get the path to the bundled skill/ directory in the package."""
    ref = importlib.resources.files("skill_perf")
    # Go up from src/skill_perf/ to project root, then into skill/
    pkg_path = str(ref.joinpath("..", ".."))
    skill_dir = os.path.realpath(os.path.join(pkg_path, "skill"))
    if not os.path.isdir(skill_dir):
        console.print(
            f"[red]Error:[/red] Bundled skill files not found.\n"
            f"Download from: {GITHUB_URL}"
        )
        raise SystemExit(1)
    return skill_dir


def _copy_skill_to(target_dir: str, force: bool = False) -> None:
    """Copy the entire skill directory (SKILL.md + references/) to target.

    Creates target_dir/skill-perf/ with SKILL.md and references/ inside.
    This matches Claude Code's expected layout: skills/{name}/SKILL.md.
    """
    src_dir = _get_skill_source_dir()
    dst_dir = os.path.join(target_dir, SKILL_DIR_NAME)

    if os.path.exists(dst_dir) and not force:
        console.print(
            f"[yellow]Already exists:[/yellow] {dst_dir}/ "
            f"(use --force to overwrite)"
        )
        return

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)

    shutil.copytree(src_dir, dst_dir)
    console.print(f"[green]Created[/green] {dst_dir}/SKILL.md")


def run_init(
    output_dir: str = ".",
    global_install: bool = False,
    force: bool = False,
) -> None:
    """Install the skill-perf skill for AI coding assistants."""
    if global_install:
        # Install to ~/.claude/agents/skill-perf/ (available in all projects)
        target = os.path.expanduser("~/.claude/agents")
        os.makedirs(target, exist_ok=True)
        _copy_skill_to(target, force=force)
        console.print()
        console.print("[bold]skill-perf skill installed globally.[/bold]")
        console.print(
            f"[dim]Location:[/dim] ~/.claude/agents/{SKILL_DIR_NAME}/SKILL.md"
        )
    else:
        # Install to .claude/skills/skill-perf/ in the target directory
        target = os.path.join(output_dir, ".claude", "skills")
        os.makedirs(target, exist_ok=True)
        _copy_skill_to(target, force=force)
        console.print()
        console.print("[bold]skill-perf skill installed to workspace.[/bold]")
        console.print(
            f"[dim]Location:[/dim] "
            f".claude/skills/{SKILL_DIR_NAME}/SKILL.md"
        )

    console.print()
    console.print("[dim]Next steps:[/dim]")
    console.print("  1. Run /reload-plugins in your AI assistant")
    console.print("  2. Run: skill-perf diagnose ./traces/")
    console.print(
        "  3. Ask your assistant to improve your skill based on the output"
    )
