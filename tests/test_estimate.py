"""Tests for the estimate command."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from typer.testing import CliRunner

from skill_perf.cli import app
from skill_perf.commands.estimate import (
    analyze_skill_dir,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_SKILL = FIXTURES_DIR / "sample-skill"

runner = CliRunner()


# ---------------------------------------------------------------------------
# Unit tests for analyze_skill_dir
# ---------------------------------------------------------------------------


class TestAnalyzeSkillDir:
    def test_analyze_skill_dir(self) -> None:
        """Analyzes fixture skill, checks name, token counts, levels."""
        est = analyze_skill_dir(str(SAMPLE_SKILL))

        assert est.name == "sample-skill"
        assert est.total_tokens > 0
        # Should have at least: description (L1), body (L2), guide.md (L3), process.py (L3)
        assert len(est.files) >= 4

        levels = {f.level for f in est.files}
        assert levels == {1, 2, 3}

    def test_analyze_skill_discovers_references(self) -> None:
        """Finds files in references/ and scripts/ directories."""
        est = analyze_skill_dir(str(SAMPLE_SKILL))

        level3_labels = [f.label for f in est.files if f.level == 3]
        # Should discover guide.md in references/
        ref_labels = [lb for lb in level3_labels if "guide.md" in lb]
        assert len(ref_labels) == 1
        assert "references/guide.md" in ref_labels[0]

        # Should discover process.py in scripts/
        script_labels = [lb for lb in level3_labels if "process.py" in lb]
        assert len(script_labels) == 1
        assert "(exec only)" in script_labels[0]

    def test_analyze_skill_warnings_large(self) -> None:
        """Create a tmp skill with huge content, check warnings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Path(tmpdir) / "SKILL.md"
            # Create a description > 50 tokens, body > 2000 tokens
            big_desc = "word " * 100  # ~100 tokens
            big_body = "content word " * 3000  # ~3000+ tokens
            skill.write_text(
                f"---\nname: big-skill\ndescription: {big_desc}\n---\n{big_body}\n"
            )
            est = analyze_skill_dir(str(skill))

            assert len(est.warnings) >= 2
            desc_warnings = [w for w in est.warnings if "description" in w]
            body_warnings = [w for w in est.warnings if "body" in w]
            assert len(desc_warnings) >= 1
            assert len(body_warnings) >= 1

    def test_analyze_skill_frontmatter_parsing(self) -> None:
        """Checks name/description extraction from frontmatter."""
        est = analyze_skill_dir(str(SAMPLE_SKILL))

        assert est.name == "sample-skill"

        # description file info should exist at level 1
        desc_files = [f for f in est.files if f.level == 1 and f.label == "description"]
        assert len(desc_files) == 1
        assert desc_files[0].token_count > 0

    def test_analyze_skill_by_file_path(self) -> None:
        """Can pass the SKILL.md file path directly instead of directory."""
        est = analyze_skill_dir(str(SAMPLE_SKILL / "SKILL.md"))
        assert est.name == "sample-skill"
        assert est.total_tokens > 0

    def test_analyze_skill_costs(self) -> None:
        """Costs dict is populated for known models."""
        est = analyze_skill_dir(str(SAMPLE_SKILL))
        assert "claude-sonnet-4" in est.costs
        assert "gpt-4o" in est.costs
        assert "ollama-any" in est.costs
        assert est.costs["ollama-any"] == 0.0


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestEstimateCLI:
    def test_estimate_cli_runs(self) -> None:
        """Use CliRunner to invoke `skill-perf estimate` on fixture."""
        result = runner.invoke(app, ["estimate", str(SAMPLE_SKILL)])
        assert result.exit_code == 0
        assert "sample-skill" in result.output

    def test_estimate_compare_mode(self) -> None:
        """Compare two fixture skills (same skill twice for simplicity)."""
        result = runner.invoke(
            app,
            ["estimate", str(SAMPLE_SKILL), str(SAMPLE_SKILL), "--compare"],
        )
        assert result.exit_code == 0
        assert "Comparison" in result.output

    def test_estimate_json_output(self) -> None:
        """Check --json flag produces valid JSON."""
        result = runner.invoke(app, ["estimate", str(SAMPLE_SKILL), "--json"])
        assert result.exit_code == 0
        # Strip ANSI codes and parse JSON from the output
        # Rich's print_json outputs with formatting; extract the JSON portion
        output = result.output.strip()
        data = json.loads(output)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "sample-skill"
        assert "total_tokens" in data[0]
        assert "costs" in data[0]
        assert "files" in data[0]
        assert "warnings" in data[0]

    def test_estimate_not_found(self) -> None:
        """Non-existent path shows error."""
        result = runner.invoke(app, ["estimate", "/nonexistent/path"])
        assert result.exit_code != 0
