"""Tests for the verify command — baseline comparison."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_perf.commands.verify import _compare, _load_benchmark
from skill_perf.models.benchmark import BenchmarkResult
from skill_perf.models.diagnosis import Issue
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


def _make_benchmark(
    label: str,
    total_tokens: int,
    total_cost: float,
    issues: list[Issue] | None = None,
) -> BenchmarkResult:
    """Build a BenchmarkResult with a synthetic session."""
    session = SessionAnalysis(
        session_id=f"{label}-session",
        model="claude-sonnet-4",
        api_input_tokens=total_tokens,
        api_output_tokens=0,
        steps=[
            _step(step_type="system_prompt", token_count=total_tokens // 2, role="system"),
            _step(step_type="tool_call", token_count=total_tokens // 2),
        ],
        issues=issues or [],
    )
    return BenchmarkResult(
        run_id=label,
        timestamp="2026-01-01T00:00:00+00:00",
        skill_name=label,
        sessions=[session],
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        total_issues=len(issues or []),
    )


def _make_issue(
    pattern: str = "large_file_read",
    severity: str = "warning",
    step_index: int = 0,
    impact_tokens: int = 500,
) -> Issue:
    return Issue(
        severity=severity,
        pattern=pattern,
        step_index=step_index,
        description="Test issue",
        impact_tokens=impact_tokens,
        suggestion="Fix it",
    )


# ===========================================================================
# test_load_benchmark
# ===========================================================================

class TestLoadBenchmark:
    def test_load_benchmark(self):
        """Load fixture session_01 into BenchmarkResult and check fields."""
        session_path = str(FIXTURES_DIR / "session_01")
        result = _load_benchmark(session_path, "v1")
        assert isinstance(result, BenchmarkResult)
        assert result.skill_name == "v1"
        assert result.total_tokens > 0
        assert len(result.sessions) == 1
        assert result.sessions[0].session_id == "session_01"

    def test_load_benchmark_missing_dir(self):
        """Error handling for non-existent path."""
        with pytest.raises(FileNotFoundError, match="not found"):
            _load_benchmark("/nonexistent/path/to/traces", "missing")


# ===========================================================================
# test_compare_improvement
# ===========================================================================

class TestCompareImprovement:
    def test_compare_improvement(self):
        """Baseline has more tokens/issues than current -- verify negative deltas."""
        baseline = _make_benchmark("v1", total_tokens=26000, total_cost=0.079)
        current = _make_benchmark("v2", total_tokens=15000, total_cost=0.047)
        comp = _compare(baseline, current)

        assert comp.token_delta == -11000
        assert comp.cost_delta < 0
        assert comp.baseline.total_tokens == 26000
        assert comp.current.total_tokens == 15000


# ===========================================================================
# test_compare_regression
# ===========================================================================

class TestCompareRegression:
    def test_compare_regression(self):
        """Current is worse -- verify positive deltas."""
        baseline = _make_benchmark("v1", total_tokens=10000, total_cost=0.030)
        current = _make_benchmark("v2", total_tokens=20000, total_cost=0.060)
        comp = _compare(baseline, current)

        assert comp.token_delta == 10000
        assert comp.cost_delta > 0


# ===========================================================================
# test_compare_issues_resolved
# ===========================================================================

class TestCompareIssuesResolved:
    def test_compare_issues_resolved(self):
        """Baseline issues not in current should be marked as resolved."""
        issue_a = _make_issue(pattern="large_file_read", step_index=0)
        issue_b = _make_issue(pattern="duplicate_read", step_index=2)
        issue_c = _make_issue(pattern="oversized_skill", step_index=1)

        baseline = _make_benchmark(
            "v1", total_tokens=20000, total_cost=0.060,
            issues=[issue_a, issue_b, issue_c],
        )
        # Current only has issue_c remaining
        current = _make_benchmark(
            "v2", total_tokens=15000, total_cost=0.045,
            issues=[issue_c],
        )
        comp = _compare(baseline, current)

        # issue_a and issue_b should be resolved
        resolved_patterns = {i.pattern for i in comp.issues_resolved}
        assert "large_file_read" in resolved_patterns
        assert "duplicate_read" in resolved_patterns

        # issue_c remains
        remaining_patterns = {i.pattern for i in comp.issues_remaining}
        assert "oversized_skill" in remaining_patterns


# ===========================================================================
# CLI integration tests
# ===========================================================================

class TestVerifyCLI:
    def test_verify_cli_runs(self):
        """CLI integration test with --baseline and --current pointing to fixtures."""
        from typer.testing import CliRunner

        from skill_perf.cli import app

        runner = CliRunner()
        session_path = str(FIXTURES_DIR / "session_01")
        result = runner.invoke(
            app,
            ["verify", "--baseline", session_path, "--current", session_path],
        )
        assert result.exit_code == 0
        assert "VERIFICATION" in result.output

    def test_verify_json_output(self):
        """Verify --json produces valid JSON with comparison fields."""
        from typer.testing import CliRunner

        from skill_perf.cli import app

        runner = CliRunner()
        session_path = str(FIXTURES_DIR / "session_01")
        result = runner.invoke(
            app,
            ["verify", "--baseline", session_path, "--current", session_path, "--json"],
        )
        assert result.exit_code == 0
        # Extract JSON from the output (Rich may add formatting)
        output = result.output.strip()
        data = json.loads(output)
        assert "baseline" in data
        assert "current" in data
        assert "token_delta" in data
        assert "cost_delta" in data
        assert "issues_resolved" in data
        assert "issues_remaining" in data

    def test_verify_missing_baseline(self):
        """Error handling for non-existent baseline path."""
        from typer.testing import CliRunner

        from skill_perf.cli import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["verify", "--baseline", "/nonexistent/path"],
        )
        assert result.exit_code != 0
