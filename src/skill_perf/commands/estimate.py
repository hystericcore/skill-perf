"""Offline skill analysis -- token count, cost estimate, structure check.

Reads a SKILL.md file (with optional YAML frontmatter), discovers referenced
files in ``references/`` and ``scripts/`` directories, counts tokens per file,
classifies content into progressive-disclosure levels, and estimates cost
across all known LLM providers.
"""


import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.text import Text

from skill_perf.core import count_tokens, get_all_costs
from skill_perf.core.config import ThresholdConfig, load_config

console = Console()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class SkillFileInfo:
    """Token/line info for a single component of a skill."""

    path: str
    level: int  # 1, 2, or 3
    label: str  # e.g. "description", "SKILL.md body", "references/api.md"
    token_count: int
    line_count: int


@dataclass
class SkillEstimate:
    """Aggregate estimate for one skill directory."""

    name: str
    path: str
    files: list[SkillFileInfo] = field(default_factory=list)
    total_tokens: int = 0
    costs: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return (metadata_dict, body_after_frontmatter).

    Uses a lightweight regex + manual key:value parsing so we don't depend
    on PyYAML.  Supports simple ``key: value`` pairs only.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw = match.group(1)
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = text[match.end() :]
    return meta, body


# ---------------------------------------------------------------------------
# Directory discovery
# ---------------------------------------------------------------------------

def _discover_files(base_dir: Path) -> list[Path]:
    """Find all files under ``references/`` and ``scripts/`` relative to *base_dir*."""
    found: list[Path] = []
    for sub in ("references", "scripts"):
        sub_dir = base_dir / sub
        if sub_dir.is_dir():
            for p in sorted(sub_dir.rglob("*")):
                if p.is_file():
                    found.append(p)
    return found


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyze_skill_dir(
    skill_path: str, config: ThresholdConfig | None = None,
) -> SkillEstimate:
    """Analyze a SKILL.md file and its ``references/`` and ``scripts/`` directories.

    Parameters
    ----------
    skill_path:
        Path to a ``SKILL.md`` file **or** a directory containing one.

    Returns
    -------
    SkillEstimate
        Populated estimate with per-file info, total tokens, costs, and warnings.
    """
    cfg = config or ThresholdConfig()
    path = Path(skill_path)
    if path.is_dir():
        skill_file = path / "SKILL.md"
        base_dir = path
    else:
        skill_file = path
        base_dir = path.parent

    if not skill_file.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_file}")

    raw_text = skill_file.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw_text)
    name = meta.get("name", skill_file.stem)
    description = meta.get("description", "")

    files: list[SkillFileInfo] = []
    warnings: list[str] = []

    # -- Level 1: description (metadata) --
    desc_tokens = count_tokens(description)
    files.append(
        SkillFileInfo(
            path=str(skill_file),
            level=1,
            label="description",
            token_count=desc_tokens,
            line_count=1,
        )
    )
    if desc_tokens > cfg.estimate_description_tokens:
        warnings.append(
            f"description is {desc_tokens} tokens (limit {cfg.estimate_description_tokens})"
        )

    # -- Level 2: SKILL.md body --
    body_lines = body.count("\n") + 1 if body.strip() else 0
    body_tokens = count_tokens(body)
    files.append(
        SkillFileInfo(
            path=str(skill_file),
            level=2,
            label="SKILL.md body",
            token_count=body_tokens,
            line_count=body_lines,
        )
    )
    if body_tokens > cfg.estimate_body_tokens:
        warnings.append(
            f"SKILL.md body is {body_tokens} tokens (limit {cfg.estimate_body_tokens})"
        )

    # -- Level 3: references & scripts --
    for ref_path in _discover_files(base_dir):
        try:
            ref_text = ref_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        ref_tokens = count_tokens(ref_text)
        ref_lines = ref_text.count("\n") + 1
        rel = ref_path.relative_to(base_dir)
        label = str(rel)
        # Mark scripts with "(exec only)" hint
        if rel.parts[0] == "scripts":
            label += " (exec only)"
        files.append(
            SkillFileInfo(
                path=str(ref_path),
                level=3,
                label=label,
                token_count=ref_tokens,
                line_count=ref_lines,
            )
        )
        if ref_tokens > cfg.estimate_single_ref_tokens:
            warnings.append(
                f"{rel} is {ref_tokens} tokens (limit {cfg.estimate_single_ref_tokens})"
            )

    total_tokens = sum(f.token_count for f in files)
    if total_tokens > cfg.estimate_total_tokens:
        warnings.append(
            f"Total is {total_tokens} tokens (limit {cfg.estimate_total_tokens})"
        )

    costs = get_all_costs(total_tokens)

    return SkillEstimate(
        name=name,
        path=str(base_dir),
        files=files,
        total_tokens=total_tokens,
        costs=costs,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Rich output helpers
# ---------------------------------------------------------------------------

def _status_badge(tokens: int, limit: int) -> Text:
    if tokens <= limit:
        return Text(f"  [under {limit}]", style="green")
    return Text(f"  [OVER {limit}]", style="bold red")


def print_estimate(
    estimate: SkillEstimate, config: ThresholdConfig | None = None,
) -> None:
    """Print Rich terminal output for a single skill estimate."""
    cfg = config or ThresholdConfig()
    out = console

    out.print()
    out.rule(f"[bold]Skill: {estimate.name}[/bold]")

    # -- Level 1 --
    out.print("\n[bold]Level 1 -- Metadata (always loaded)[/bold]")
    for f in estimate.files:
        if f.level == 1:
            line = Text(f"  {f.label}: {f.token_count} tokens")
            line.append_text(_status_badge(f.token_count, cfg.estimate_description_tokens))
            out.print(line)

    # -- Level 2 --
    out.print("\n[bold]Level 2 -- SKILL.md body (on trigger)[/bold]")
    for f in estimate.files:
        if f.level == 2:
            line = Text(f"  {f.label}: {f.token_count} tokens ({f.line_count} lines)")
            line.append_text(_status_badge(f.token_count, cfg.estimate_body_tokens))
            out.print(line)

    # -- Level 3 --
    level3 = [f for f in estimate.files if f.level == 3]
    if level3:
        out.print("\n[bold]Level 3 -- References (on demand)[/bold]")
        for f in level3:
            out.print(f"  {f.label}: {f.token_count} tokens")

    # -- Totals --
    out.print(f"\n  Total if fully loaded: {estimate.total_tokens:,} tokens")

    # -- Warnings --
    if estimate.warnings:
        out.print()
        for w in estimate.warnings:
            out.print(f"  [bold yellow]WARNING:[/bold yellow] {w}")

    # -- Costs --
    out.rule("Cost per call (skill loaded into context)")
    # Show a curated subset for readability
    display_models = [
        "claude-sonnet-4",
        "gpt-4o",
        "gemini-2.0-flash",
        "ollama-any",
    ]
    for model in display_models:
        cost = estimate.costs.get(model, 0.0)
        if cost == 0.0:
            out.print(f"  {model:<28} FREE")
        else:
            out.print(f"  {model:<28} ${cost:.6f}")
    out.print()


def print_comparison(estimates: list[SkillEstimate]) -> None:
    """Print side-by-side comparison of multiple skill versions."""
    if len(estimates) < 2:
        for e in estimates:
            print_estimate(e)
        return

    # Individual summaries first
    for e in estimates:
        print_estimate(e)

    # Comparison table
    table = Table(title="Comparison", show_header=True, header_style="bold")
    table.add_column("Skill", style="cyan")
    table.add_column("Tokens", justify="right")
    table.add_column("Delta", justify="right")
    table.add_column("Delta %", justify="right")

    base = estimates[0]
    for est in estimates:
        delta = est.total_tokens - base.total_tokens
        pct = (delta / base.total_tokens * 100) if base.total_tokens else 0.0
        delta_str = f"{delta:+,}" if est is not base else "--"
        pct_str = f"{pct:+.1f}%" if est is not base else "--"
        style = ""
        if est is not base:
            style = "green" if delta < 0 else ("red" if delta > 0 else "")
        table.add_row(est.name, f"{est.total_tokens:,}", delta_str, pct_str, style=style)

    console.print()
    console.print(table)

    # Cost impact per 1,000 calls
    console.print("\n[bold]Cost impact per 1,000 calls vs baseline:[/bold]")
    impact_models = ["claude-sonnet-4", "gpt-4o", "gemini-2.0-flash"]
    for other in estimates[1:]:
        console.print(f"\n  {other.name} vs {base.name}:")
        for model in impact_models:
            cost_diff = (other.costs.get(model, 0.0) - base.costs.get(model, 0.0)) * 1000
            console.print(f"    {model:<28} ${cost_diff:+.4f}")
    console.print()


def estimate_to_dict(estimate: SkillEstimate) -> dict[str, object]:
    """Serialize an estimate to a plain dict for JSON output."""
    return {
        "name": estimate.name,
        "path": estimate.path,
        "total_tokens": estimate.total_tokens,
        "files": [
            {
                "path": f.path,
                "level": f.level,
                "label": f.label,
                "token_count": f.token_count,
                "line_count": f.line_count,
            }
            for f in estimate.files
        ],
        "costs": estimate.costs,
        "warnings": estimate.warnings,
    }


# ---------------------------------------------------------------------------
# CLI entry-point helper (called from cli.py)
# ---------------------------------------------------------------------------

def run_estimate(
    paths: list[str],
    compare: bool = False,
    json_output: bool = False,
    config_path: str | None = None,
) -> None:
    """High-level entry point invoked by the Typer command."""
    config = load_config(config_path)
    estimates: list[SkillEstimate] = []

    for p in paths:
        pp = Path(p)
        if pp.is_dir():
            if (pp / "SKILL.md").exists():
                estimates.append(analyze_skill_dir(str(pp), config=config))
            else:
                for child in sorted(pp.rglob("SKILL.md")):
                    estimates.append(analyze_skill_dir(str(child), config=config))
        elif pp.is_file():
            estimates.append(analyze_skill_dir(str(pp), config=config))
        else:
            console.print(f"[bold red]Not found:[/bold red] {p}")

    if not estimates:
        console.print("[bold red]No skill files found.[/bold red]")
        raise SystemExit(1)

    if json_output:
        data = [estimate_to_dict(e) for e in estimates]
        console.print_json(json.dumps(data, indent=2))
        return

    if compare and len(estimates) >= 2:
        print_comparison(estimates)
    else:
        for e in estimates:
            print_estimate(e, config=config)
