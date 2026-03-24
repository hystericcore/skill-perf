"""Snapshot and diff SKILL.md versions."""

from __future__ import annotations

import difflib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.syntax import Syntax

console = Console()

_SNAPSHOTS_DIR = ".snapshots"
_SKILL_FILE = "SKILL.md"
_ENV_VAR = "SKILL_PERF_SNAPSHOT_DIR"


def _snapshots_dir(skill_dir: str) -> Path:
    """Return the snapshot directory for a skill.

    If ``SKILL_PERF_SNAPSHOT_DIR`` is set, snapshots are stored there under a
    slug derived from the skill path (e.g. ``$SKILL_PERF_SNAPSHOT_DIR/cursor-skills-my-skill/``).
    Otherwise they default to ``<skill-dir>/.snapshots/``.
    """
    base = os.environ.get(_ENV_VAR)
    if base:
        # derive a readable slug from the absolute skill path
        slug = Path(skill_dir).resolve().as_posix().lstrip("/").replace("/", "-")
        return Path(base).expanduser() / slug
    return Path(skill_dir) / _SNAPSHOTS_DIR


def _skill_path(skill_dir: str) -> Path:
    return Path(skill_dir) / _SKILL_FILE


def run_snapshot(skill_dir: str) -> str:
    """Save a timestamped copy of SKILL.md and return the snapshot path."""
    skill_path = _skill_path(skill_dir)
    if not skill_path.exists():
        console.print(f"[red]Error:[/red] No SKILL.md found at {skill_path}")
        raise SystemExit(1)

    snap_dir = _snapshots_dir(skill_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snap_file = snap_dir / f"SKILL_{timestamp}.md"
    snap_file.write_text(skill_path.read_text(encoding="utf-8"), encoding="utf-8")

    console.print(f"[green]Snapshot saved:[/green] {snap_file}")
    console.print(
        f"[dim]Run [bold]skill-perf diff {skill_dir}[/bold] after editing to see what changed.[/dim]"
    )
    if not os.environ.get(_ENV_VAR):
        console.print(
            f"[dim]Tip: set [bold]{_ENV_VAR}=~/.skill-perf/snapshots[/bold] "
            "to store all snapshots in one global location instead.[/dim]"
        )
    return str(snap_file)


def _list_snapshots(skill_dir: str) -> list[Path]:
    snap_dir = _snapshots_dir(skill_dir)
    if not snap_dir.exists():
        return []
    return sorted(snap_dir.glob("SKILL_*.md"))


def run_diff(
    skill_dir: str,
    from_snapshot: Optional[str] = None,
    to_snapshot: Optional[str] = None,
) -> None:
    """Show a unified diff between two SKILL.md versions."""
    snapshots = _list_snapshots(skill_dir)

    # Resolve `from`
    if from_snapshot:
        from_path = Path(from_snapshot)
    elif snapshots:
        from_path = snapshots[-1]  # latest snapshot
    else:
        console.print(
            "[red]Error:[/red] No snapshots found. "
            "Run `skill-perf snapshot <skill-dir>` first."
        )
        raise SystemExit(1)

    # Resolve `to`
    if to_snapshot:
        to_path = Path(to_snapshot)
    else:
        to_path = _skill_path(skill_dir)  # current working copy

    if not from_path.exists():
        console.print(f"[red]Error:[/red] Snapshot not found: {from_path}")
        raise SystemExit(1)
    if not to_path.exists():
        console.print(f"[red]Error:[/red] File not found: {to_path}")
        raise SystemExit(1)

    from_text = from_path.read_text(encoding="utf-8").splitlines(keepends=True)
    to_text = to_path.read_text(encoding="utf-8").splitlines(keepends=True)

    diff = list(
        difflib.unified_diff(
            from_text,
            to_text,
            fromfile=str(from_path),
            tofile=str(to_path),
        )
    )

    if not diff:
        console.print("[dim]No changes between versions.[/dim]")
        return

    console.print(
        f"\n[bold]Diff:[/bold] {from_path.name} → {to_path.name}\n"
    )
    diff_text = "".join(diff)
    console.print(Syntax(diff_text, "diff", theme="monokai", word_wrap=True))

    # Summary: lines added/removed
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    console.print(
        f"\n[green]+{added} lines[/green]  [red]-{removed} lines[/red]"
    )


def run_list_snapshots(skill_dir: str) -> None:
    """List all saved snapshots for a skill directory."""
    snapshots = _list_snapshots(skill_dir)
    if not snapshots:
        console.print("[dim]No snapshots found.[/dim]")
        return
    console.print(f"[bold]Snapshots for[/bold] {skill_dir}:")
    for snap in snapshots:
        size = snap.stat().st_size
        console.print(f"  {snap.name}  ({size} bytes)  {snap}")
