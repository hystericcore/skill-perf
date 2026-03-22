"""Tests for the suggestion module."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from skill_perf.cli import app
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep
from skill_perf.suggestion.generator import estimate_savings, generate_suggestion
from skill_perf.suggestion.templates import TEMPLATES

ALL_PATTERNS = [
    "script_not_executed",
    "large_file_read",
    "duplicate_reads",
    "excessive_exploration",
    "oversized_skill",
    "cat_on_large_file",
    "low_cache_rate",
    "high_think_ratio",
    "skill_not_triggered",
]

runner = CliRunner()


def _make_session(model: str = "claude-sonnet-4") -> SessionAnalysis:
    """Create a minimal session for testing."""
    return SessionAnalysis(
        session_id="test-session-001",
        model=model,
        api_input_tokens=5000,
        api_output_tokens=1000,
        steps=[
            ConversationStep(
                turn=1,
                role="user",
                step_type="user_message",
                description="User asked a question",
                token_count=100,
            ),
            ConversationStep(
                turn=2,
                role="assistant",
                step_type="assistant_response",
                description="Model response",
                token_count=500,
            ),
        ],
    )


def _make_issue(
    pattern: str,
    severity: str = "warning",
    step_index: int = 1,
    description: str = "Test issue",
    impact_tokens: int = 500,
    suggestion: str = "Fix this",
) -> Issue:
    return Issue(
        severity=severity,
        pattern=pattern,
        step_index=step_index,
        description=description,
        impact_tokens=impact_tokens,
        suggestion=suggestion,
    )


class TestGenerateSuggestionScriptNotExecuted:
    def test_template_filled_with_script_name(self) -> None:
        issue = _make_issue(
            pattern="script_not_executed",
            severity="critical",
            description="Model manually parsed CSV instead of using scripts/parse_csv.py",
            impact_tokens=2100,
        )
        session = _make_session()
        result = generate_suggestion(issue, session)

        assert "parse_csv.py" in result
        assert "ALWAYS use the bundled script" in result
        assert "Do NOT implement this manually" in result

    def test_template_with_no_script_in_description(self) -> None:
        issue = _make_issue(
            pattern="script_not_executed",
            severity="critical",
            description="Model did not use the available script",
            impact_tokens=1000,
        )
        session = _make_session()
        result = generate_suggestion(issue, session)

        # Should still produce valid output with fallback script name
        assert "ALWAYS use the bundled script" in result
        assert "run.py" in result


class TestGenerateSuggestionLargeFileRead:
    def test_template_content(self) -> None:
        issue = _make_issue(
            pattern="large_file_read",
            description="Read entire 500-line file",
            impact_tokens=1500,
        )
        session = _make_session()
        result = generate_suggestion(issue, session)

        assert "grep" in result.lower()
        assert "relevant section" in result
        assert "larger than 50 lines" in result


class TestGenerateSuggestionDuplicateReads:
    def test_template_content(self) -> None:
        issue = _make_issue(
            pattern="duplicate_reads",
            description="File read 3 times",
            impact_tokens=800,
        )
        session = _make_session()
        result = generate_suggestion(issue, session)

        assert "retain" in result.lower() or "memory" in result.lower()
        assert "re-read" in result.lower() or "Do NOT" in result


class TestGenerateSuggestionAllPatterns:
    def test_every_pattern_returns_nonempty(self) -> None:
        session = _make_session()
        for pattern in ALL_PATTERNS:
            issue = _make_issue(pattern=pattern, description="Test issue")
            result = generate_suggestion(issue, session)
            assert result.strip(), f"Empty suggestion for pattern: {pattern}"

    def test_unknown_pattern_falls_back(self) -> None:
        issue = _make_issue(
            pattern="unknown_pattern",
            suggestion="Fallback suggestion text",
        )
        session = _make_session()
        result = generate_suggestion(issue, session)
        assert result == "Fallback suggestion text"


class TestEstimateSavings:
    def test_returns_positive_values(self) -> None:
        issue = _make_issue(pattern="large_file_read", impact_tokens=2000)
        tokens_saved, cost_saved = estimate_savings(issue, model="claude-sonnet-4")
        assert tokens_saved == 2000
        assert cost_saved > 0

    def test_cost_calculation_correct(self) -> None:
        issue = _make_issue(pattern="large_file_read", impact_tokens=1_000_000)
        tokens_saved, cost_saved = estimate_savings(issue, model="claude-sonnet-4")
        assert tokens_saved == 1_000_000
        # claude-sonnet-4 input cost is $3.00 per 1M tokens
        assert cost_saved == 3.00

    def test_unknown_model_returns_zero_cost(self) -> None:
        issue = _make_issue(pattern="large_file_read", impact_tokens=1000)
        tokens_saved, cost_saved = estimate_savings(issue, model="unknown-model-x")
        assert tokens_saved == 1000
        assert cost_saved == 0.0


class TestTemplatesAllPatternsCovered:
    def test_all_9_patterns_exist(self) -> None:
        for pattern in ALL_PATTERNS:
            assert pattern in TEMPLATES, f"Missing template for pattern: {pattern}"

    def test_exactly_9_templates(self) -> None:
        assert len(TEMPLATES) == 9

    def test_no_empty_templates(self) -> None:
        for pattern, template in TEMPLATES.items():
            assert template.strip(), f"Empty template for pattern: {pattern}"


class TestSuggestCLI:
    def test_suggest_no_args_shows_error(self) -> None:
        result = runner.invoke(app, ["suggest"])
        # Should error because no paths given
        assert result.exit_code != 0

    def test_suggest_nonexistent_path(self) -> None:
        result = runner.invoke(app, ["suggest", "/nonexistent/path/xyz"])
        # Should run without crashing (empty session, no issues)
        assert result.exit_code == 0

    def test_suggest_json_nonexistent_path(self) -> None:
        result = runner.invoke(app, ["suggest", "--json", "/nonexistent/path/xyz"])
        assert result.exit_code == 0
        # Should output valid JSON (empty array)
        output = result.stdout.strip()
        # Parse the JSON from the output
        data = json.loads(output)
        assert isinstance(data, list)
