"""Implementation of the `skill-perf create` command."""

import os
from rich.console import Console
from skill_perf.commands.estimate import MAX_NAME_CHARS, MAX_DESCRIPTION_CHARS

console = Console()

_SKILL_TEMPLATE = """---
name: {name}
description: {description}
---

## When to use

<!-- Describe when this skill should be triggered -->

## Workflow

<!-- Step-by-step instructions for the AI assistant -->

## Instructions

<!-- Specific rules and constraints -->
"""


def run_create(name: str, description: str, output_dir: str) -> None:
    """Scaffold a new skill directory with SKILL.md, references/, and scripts/."""
    # Enforce spec limits
    if len(name) > MAX_NAME_CHARS:
        name = name[:MAX_NAME_CHARS]
        console.print(f"[yellow]Warning:[/yellow] name truncated to {MAX_NAME_CHARS} chars")

    if len(description) > MAX_DESCRIPTION_CHARS:
        description = description[:MAX_DESCRIPTION_CHARS]
        console.print(f"[yellow]Warning:[/yellow] description truncated to {MAX_DESCRIPTION_CHARS} chars")

    # Create directory structure
    skill_dir = os.path.join(output_dir, name)
    os.makedirs(skill_dir, exist_ok=True)

    refs_dir = os.path.join(skill_dir, "references")
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(refs_dir, exist_ok=True)
    os.makedirs(scripts_dir, exist_ok=True)

    # Create .gitkeep files
    for d in (refs_dir, scripts_dir):
        gitkeep = os.path.join(d, ".gitkeep")
        if not os.path.exists(gitkeep):
            with open(gitkeep, "w") as f:
                pass

    # Write SKILL.md
    skill_file = os.path.join(skill_dir, "SKILL.md")
    content = _SKILL_TEMPLATE.format(name=name, description=description)
    with open(skill_file, "w", encoding="utf-8") as f:
        f.write(content)

    console.print(f"\n[green]Created skill:[/green] {skill_dir}/")
    console.print(f"  SKILL.md")
    console.print(f"  references/")
    console.print(f"  scripts/")
    console.print(f"\n[dim]Next: run[/dim] skill-perf estimate {skill_dir}/ [dim]to validate[/dim]")
