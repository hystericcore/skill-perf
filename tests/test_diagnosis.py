"""Tests for the diagnosis module — 9 pattern detectors + engine + CLI."""


from pathlib import Path

from skill_perf.diagnosis.engine import diagnose
from skill_perf.diagnosis.patterns import (
    detect_cat_on_large_file,
    detect_duplicate_reads,
    detect_excessive_exploration,
    detect_high_think_ratio,
    detect_large_file_read,
    detect_low_cache_rate,
    detect_oversized_skill,
    detect_script_not_executed,
    detect_skill_not_triggered,
)
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(
    step_type: str = "tool_call",
    token_count: int = 100,
    tool_name: str | None = None,
    file_path: str | None = None,
    description: str = "",
    role: str = "assistant",
    turn: int = 1,
    raw_content_preview: str = "",
) -> ConversationStep:
    return ConversationStep(
        turn=turn,
        role=role,
        step_type=step_type,
        description=description,
        token_count=token_count,
        tool_name=tool_name,
        file_path=file_path,
        raw_content_preview=raw_content_preview,
    )


def _session(
    steps: list[ConversationStep] | None = None,
    api_input_tokens: int = 0,
    api_output_tokens: int = 0,
) -> SessionAnalysis:
    return SessionAnalysis(
        session_id="test-session",
        model="test-model",
        api_input_tokens=api_input_tokens,
        api_output_tokens=api_output_tokens,
        steps=steps or [],
    )


# ===========================================================================
# Pattern 1: script_not_executed
# ===========================================================================

class TestDetectScriptNotExecuted:
    def test_fires_when_skill_has_scripts_but_none_executed(self, tmp_path):
        # Create a skill dir with scripts/
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "process.py").write_text("print('hi')")

        steps = [
            _step(step_type="skill_load", description="Load SKILL.md", token_count=500),
            _step(
                step_type="tool_call", tool_name="Read",
                description="Read file", token_count=200,
            ),
            _step(step_type="tool_result", description="File content", token_count=300),
        ]
        issues = detect_script_not_executed(steps, skill_dir=str(tmp_path))
        assert len(issues) == 1
        assert issues[0].severity == "critical"
        assert issues[0].pattern == "script_not_executed"

    def test_no_issue_when_skill_has_no_scripts_dir(self):
        steps = [
            _step(step_type="skill_load", description="Load SKILL.md", token_count=500),
            _step(
                step_type="tool_call", tool_name="Read",
                description="Read file", token_count=200,
            ),
        ]
        issues = detect_script_not_executed(steps)
        assert len(issues) == 0

    def test_no_issue_when_script_executed(self):
        steps = [
            _step(step_type="skill_load", description="Load SKILL.md", token_count=500),
            _step(
                step_type="tool_call",
                tool_name="Bash",
                description="Bash: python scripts/process.py",
                token_count=50,
                raw_content_preview="python scripts/process.py",
            ),
        ]
        issues = detect_script_not_executed(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 2: large_file_read
# ===========================================================================

class TestDetectLargeFileRead:
    def test_fires_on_large_tool_result(self):
        steps = [
            _step(step_type="tool_result", token_count=3000, description="Large file content"),
        ]
        issues = detect_large_file_read(steps)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].pattern == "large_file_read"
        assert issues[0].impact_tokens == 1000  # 3000 - 2000

    def test_no_issue_on_small_result(self):
        steps = [
            _step(step_type="tool_result", token_count=500, description="Small file"),
        ]
        issues = detect_large_file_read(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 3: duplicate_reads
# ===========================================================================

class TestDetectDuplicateReads:
    def test_fires_on_same_file_read_twice(self):
        steps = [
            _step(
                step_type="tool_call", file_path="/src/main.py",
                token_count=50, tool_name="Read",
            ),
            _step(step_type="tool_result", token_count=200),
            _step(
                step_type="tool_call", file_path="/src/main.py",
                token_count=50, tool_name="Read",
            ),
            _step(step_type="tool_result", token_count=200),
        ]
        issues = detect_duplicate_reads(steps)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].pattern == "duplicate_read"
        assert issues[0].step_index == 2  # the second read

    def test_no_issue_on_unique_reads(self):
        steps = [
            _step(step_type="tool_call", file_path="/src/a.py", token_count=50),
            _step(step_type="tool_call", file_path="/src/b.py", token_count=50),
        ]
        issues = detect_duplicate_reads(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 4: excessive_exploration
# ===========================================================================

class TestDetectExcessiveExploration:
    def test_fires_on_6_consecutive_grep_glob(self):
        steps = [
            _step(tool_name="Grep", token_count=100, description="grep: pattern1"),
            _step(tool_name="Glob", token_count=80, description="glob: *.py"),
            _step(tool_name="Grep", token_count=120, description="grep: pattern2"),
            _step(tool_name="Grep", token_count=90, description="grep: pattern3"),
            _step(tool_name="Glob", token_count=70, description="glob: src/*.ts"),
            _step(tool_name="Grep", token_count=100, description="grep: pattern4"),
            _step(tool_name="Edit", token_count=100, description="Edit file"),
        ]
        issues = detect_excessive_exploration(steps)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].pattern == "excessive_exploration"

    def test_no_issue_on_few_searches(self):
        steps = [
            _step(tool_name="Grep", token_count=30),
            _step(tool_name="Glob", token_count=20),
            _step(tool_name="Edit", token_count=100),
        ]
        issues = detect_excessive_exploration(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 5: oversized_skill
# ===========================================================================

class TestDetectOversizedSkill:
    def test_fires_on_large_skill_load(self):
        steps = [
            _step(step_type="skill_load", token_count=5000, description="Load SKILL.md"),
        ]
        issues = detect_oversized_skill(steps)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].pattern == "oversized_skill"
        assert issues[0].impact_tokens == 2000  # 5000 - 3000

    def test_no_issue_on_small_skill(self):
        steps = [
            _step(step_type="skill_load", token_count=1000, description="Load SKILL.md"),
        ]
        issues = detect_oversized_skill(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 6: cat_on_large_file
# ===========================================================================

class TestDetectCatOnLargeFile:
    def test_fires_on_bash_cat_with_high_tokens(self):
        steps = [
            _step(
                step_type="tool_call",
                tool_name="Bash",
                description="Bash: cat /etc/config.json",
                token_count=800,
            ),
        ]
        issues = detect_cat_on_large_file(steps)
        assert len(issues) == 1
        assert issues[0].severity == "warning"
        assert issues[0].pattern == "cat_on_large_file"

    def test_no_issue_on_small_cat(self):
        steps = [
            _step(
                step_type="tool_call",
                tool_name="Bash",
                description="Bash: cat /etc/hosts",
                token_count=50,
            ),
        ]
        issues = detect_cat_on_large_file(steps)
        assert len(issues) == 0


# ===========================================================================
# Pattern 7: low_cache_rate
# ===========================================================================

class TestDetectLowCacheRate:
    def test_fires_when_api_input_much_higher(self):
        session = _session(
            steps=[
                _step(step_type="system_prompt", token_count=500, role="system"),
                _step(step_type="tool_call", token_count=200),
            ],
            api_input_tokens=5000,  # 5000 / 700 > 2.0
        )
        issues = detect_low_cache_rate(session)
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert issues[0].pattern == "low_cache_rate"

    def test_no_issue_when_ratio_normal(self):
        session = _session(
            steps=[
                _step(step_type="system_prompt", token_count=500, role="system"),
            ],
            api_input_tokens=800,  # 800 / 500 = 1.6 <= 2.0
        )
        issues = detect_low_cache_rate(session)
        assert len(issues) == 0


# ===========================================================================
# Pattern 8: high_think_ratio
# ===========================================================================

class TestDetectHighThinkRatio:
    def test_fires_when_ratio_above_3(self):
        session = _session(
            steps=[
                _step(step_type="assistant_response", token_count=4000),
                _step(step_type="tool_call", token_count=100),
                _step(step_type="tool_result", token_count=100),
            ],
        )
        # think_act_ratio = 4000 / (100 + 100) = 20.0 > 3.0
        issues = detect_high_think_ratio(session)
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert issues[0].pattern == "high_think_ratio"


# ===========================================================================
# Pattern 9: skill_not_triggered
# ===========================================================================

class TestDetectSkillNotTriggered:
    def test_fires_when_prompt_matches_but_no_skill_load(self, tmp_path):
        # Create a skill with description matching the prompt
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: csv-processor\n"
            "description: Processes CSV files with summary statistics\n"
            "---\n\n# CSV Processor\n"
        )
        steps = [
            _step(
                step_type="user_message",
                description="User prompt",
                token_count=20,
                raw_content_preview="Process this CSV file and show statistics",
            ),
            _step(step_type="tool_call", tool_name="Bash", token_count=50),
        ]
        issues = detect_skill_not_triggered(steps, skill_dir=str(tmp_path))
        assert len(issues) == 1
        assert issues[0].pattern == "skill_not_triggered"
        assert "csv-processor" in issues[0].description

    def test_no_issue_when_skill_was_loaded(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: test\ndescription: test skill\n---\n"
        )
        steps = [
            _step(step_type="user_message", token_count=20,
                  raw_content_preview="test something"),
            _step(step_type="skill_load", token_count=100),
        ]
        issues = detect_skill_not_triggered(steps, skill_dir=str(tmp_path))
        assert len(issues) == 0

    def test_no_issue_when_prompt_doesnt_match(self, tmp_path):
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: csv-processor\n"
            "description: Processes CSV files with summary statistics\n"
            "---\n"
        )
        steps = [
            _step(
                step_type="user_message",
                token_count=20,
                raw_content_preview="Deploy the application to production",
            ),
        ]
        issues = detect_skill_not_triggered(steps, skill_dir=str(tmp_path))
        assert len(issues) == 0

    def test_no_issue_without_skill_dir(self):
        steps = [
            _step(step_type="user_message", token_count=20,
                  raw_content_preview="Process CSV"),
        ]
        issues = detect_skill_not_triggered(steps, skill_dir=None)
        assert len(issues) == 0

    def test_no_issue_when_ratio_normal(self):
        session = _session(
            steps=[
                _step(step_type="assistant_response", token_count=200),
                _step(step_type="tool_call", token_count=100),
                _step(step_type="tool_result", token_count=100),
            ],
        )
        # think_act_ratio = 200 / 200 = 1.0 <= 3.0
        issues = detect_high_think_ratio(session)
        assert len(issues) == 0


# ===========================================================================
# Engine tests
# ===========================================================================

class TestDiagnoseEngine:
    def test_sorts_by_severity_then_impact(self):
        steps = [
            # Will trigger large_file_read (warning, impact 1000)
            _step(step_type="tool_result", token_count=3000, description="big file"),
            # Will trigger oversized_skill (warning, impact 2000)
            _step(step_type="skill_load", token_count=5000, description="big skill"),
        ]
        session = _session(steps=steps)
        issues = diagnose(session)

        # All should be warnings in this case (no scripts dir = no critical)
        assert len(issues) >= 2

        # Among warnings, higher impact first
        warnings = [i for i in issues if i.severity == "warning"]
        if len(warnings) >= 2:
            assert warnings[0].impact_tokens >= warnings[1].impact_tokens

    def test_empty_session_returns_no_issues(self):
        session = _session(steps=[])
        issues = diagnose(session)
        assert issues == []


# ===========================================================================
# CLI integration test
# ===========================================================================

class TestDiagnoseCLI:
    def test_diagnose_cli_runs(self):
        """Run diagnose on fixture session_01 and verify it completes."""
        from typer.testing import CliRunner

        from skill_perf.cli import app

        runner = CliRunner()
        session_path = str(FIXTURES_DIR / "session_01")
        result = runner.invoke(app, ["diagnose", session_path])
        assert result.exit_code == 0
        assert "Session:" in result.output

    def test_diagnose_cli_json_output(self):
        """Verify --json flag produces JSON output."""
        from typer.testing import CliRunner

        from skill_perf.cli import app

        runner = CliRunner()
        session_path = str(FIXTURES_DIR / "session_01")
        result = runner.invoke(app, ["diagnose", session_path, "--json"])
        assert result.exit_code == 0
        assert "session_id" in result.output
