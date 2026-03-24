"""Tests for the create command."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from skill_perf.cli import app
from skill_perf.commands.create import run_create
from skill_perf.commands.estimate import analyze_skill_dir

runner = CliRunner()


class TestRunCreate:
    def test_creates_directory_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_create(name="my-skill", description="A test skill", output_dir=tmpdir)
            skill_dir = Path(tmpdir) / "my-skill"
            assert (skill_dir / "SKILL.md").exists()
            assert (skill_dir / "references").is_dir()
            assert (skill_dir / "scripts").is_dir()
            assert (skill_dir / "references" / ".gitkeep").exists()
            assert (skill_dir / "scripts" / ".gitkeep").exists()

    def test_generated_skill_has_valid_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_create(name="test-skill", description="Test description", output_dir=tmpdir)
            skill_dir = Path(tmpdir) / "test-skill"
            content = (skill_dir / "SKILL.md").read_text()
            assert "---" in content
            assert "name: test-skill" in content
            assert "description: Test description" in content

    def test_generated_skill_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_create(name="valid-skill", description="A valid skill", output_dir=tmpdir)
            est = analyze_skill_dir(str(Path(tmpdir) / "valid-skill"))
            invalid = [w for w in est.warnings if w.startswith("INVALID:")]
            assert invalid == []

    def test_name_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            long_name = "a" * 100
            run_create(name=long_name, description="Test", output_dir=tmpdir)
            # Directory name should be truncated
            skill_dir = Path(tmpdir) / ("a" * 64)
            assert skill_dir.exists()

    def test_empty_description_still_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_create(name="minimal", description="", output_dir=tmpdir)
            skill_dir = Path(tmpdir) / "minimal"
            assert (skill_dir / "SKILL.md").exists()


class TestCreateCLI:
    def test_create_cli_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(app, ["create", "cli-test", "--output", tmpdir])
            assert result.exit_code == 0
            assert "Created skill" in result.output

    def test_create_cli_with_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(
                app,
                ["create", "described-skill", "-d", "My skill description", "--output", tmpdir],
            )
            assert result.exit_code == 0
            content = (Path(tmpdir) / "described-skill" / "SKILL.md").read_text()
            assert "My skill description" in content
