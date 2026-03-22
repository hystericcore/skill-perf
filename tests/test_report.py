"""Tests for skill_perf.report — treemap builder and HTML generator."""

from __future__ import annotations

from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep
from skill_perf.report.html import generate_html_report
from skill_perf.report.treemap import build_treemap


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(**kwargs) -> ConversationStep:
    defaults = {
        "turn": 1,
        "role": "assistant",
        "step_type": "assistant_response",
        "description": "step",
        "token_count": 100,
    }
    defaults.update(kwargs)
    return ConversationStep(**defaults)


def _issue(**kwargs) -> Issue:
    defaults = {
        "severity": "warning",
        "pattern": "large_file_read",
        "step_index": 0,
        "description": "File too large",
        "impact_tokens": 500,
        "suggestion": "Use grep instead",
    }
    defaults.update(kwargs)
    return Issue(**defaults)


def _sample_session(
    *,
    issues: list[Issue] | None = None,
) -> SessionAnalysis:
    """Build a realistic SessionAnalysis with varied step types."""
    steps = [
        _step(
            turn=0,
            role="system",
            step_type="system_prompt",
            description="System prompt",
            token_count=800,
        ),
        _step(
            turn=1,
            role="user",
            step_type="user_message",
            description="User request",
            token_count=120,
        ),
        _step(
            turn=2,
            role="assistant",
            step_type="assistant_response",
            description="Planning response",
            token_count=300,
        ),
        _step(
            turn=3,
            role="assistant",
            step_type="tool_call",
            description="Read file",
            token_count=50,
            tool_name="Read",
        ),
        _step(
            turn=3,
            role="tool",
            step_type="tool_result",
            description="File contents",
            token_count=2000,
            tool_name="Read",
        ),
        _step(
            turn=4,
            role="assistant",
            step_type="tool_call",
            description="Bash command",
            token_count=40,
            tool_name="Bash",
        ),
        _step(
            turn=4,
            role="tool",
            step_type="tool_result",
            description="Bash output",
            token_count=150,
            tool_name="Bash",
        ),
        _step(
            turn=5,
            role="assistant",
            step_type="assistant_response",
            description="Final answer",
            token_count=250,
        ),
        _step(
            turn=6,
            role="assistant",
            step_type="skill_load",
            description="Load skill file",
            token_count=600,
            file_path="/skills/my_skill.md",
        ),
    ]
    return SessionAnalysis(
        session_id="test-session",
        model="claude-sonnet-4",
        api_input_tokens=5000,
        api_output_tokens=1000,
        steps=steps,
        issues=issues or [],
    )


# ---------------------------------------------------------------------------
# Treemap builder tests
# ---------------------------------------------------------------------------


class TestBuildTreemap:
    def test_build_treemap_basic(self) -> None:
        session = _sample_session()
        root = build_treemap(session)
        assert root.name == "test-session"
        assert root.category == "session"
        assert len(root.children) > 0
        assert root.token_count > 0

    def test_build_treemap_categories(self) -> None:
        session = _sample_session()
        root = build_treemap(session)
        child_categories = {c.category for c in root.children}
        # The sample session has system_prompt, user, assistant, tool_call,
        # tool_result, and skill_load steps.
        assert "system_prompt" in child_categories
        assert "user_message" in child_categories
        assert "assistant_response" in child_categories
        assert "tool_call" in child_categories
        assert "tool_result" in child_categories
        assert "skill_load" in child_categories

    def test_build_treemap_wasteful_nodes(self) -> None:
        issues = [
            _issue(step_index=4, impact_tokens=500),  # tool_result at index 4
        ]
        session = _sample_session(issues=issues)
        root = build_treemap(session)
        assert root.is_wasteful

        # Find the tool_results group and verify it is marked wasteful
        tool_results_group = next(
            c for c in root.children if c.category == "tool_result"
        )
        assert tool_results_group.is_wasteful
        # At least one child should be wasteful
        assert any(c.is_wasteful for c in tool_results_group.children)

    def test_build_treemap_token_totals(self) -> None:
        session = _sample_session()
        root = build_treemap(session)
        assert root.token_count == session.total_estimated_tokens

    def test_build_treemap_cost_positive(self) -> None:
        session = _sample_session()
        root = build_treemap(session, model="claude-sonnet-4")
        assert root.cost_usd > 0


# ---------------------------------------------------------------------------
# HTML report tests
# ---------------------------------------------------------------------------


class TestGenerateHtmlReport:
    def test_generate_html_report(self) -> None:
        session = _sample_session()
        html = generate_html_report(session, issues=[])
        assert "<!DOCTYPE html>" in html
        assert "<title>skill-perf Report</title>" in html
        assert "id=\"treemap\"" in html
        assert "id=\"sidebar\"" in html

    def test_generate_html_report_contains_d3(self) -> None:
        session = _sample_session()
        html = generate_html_report(session, issues=[])
        assert "https://d3js.org/d3.v7.min.js" in html

    def test_generate_html_report_contains_data(self) -> None:
        session = _sample_session()
        issues = [_issue()]
        html = generate_html_report(session, issues=issues)
        assert "const DATA =" in html
        assert "const ISSUES =" in html
        assert "const SESSION =" in html
        # The session id should appear in the embedded data
        assert "test-session" in html

    def test_generate_html_report_file_output(self, tmp_path) -> None:
        session = _sample_session()
        out = tmp_path / "report.html"
        html = generate_html_report(session, issues=[], output_path=str(out))
        assert out.exists()
        contents = out.read_text(encoding="utf-8")
        assert contents == html

    def test_html_file_size_limit(self) -> None:
        session = _sample_session()
        issues = [_issue(step_index=i) for i in range(9)]
        html = generate_html_report(session, issues=issues)
        size_kb = len(html.encode("utf-8")) / 1024
        assert size_kb < 500, f"HTML report is {size_kb:.0f} KB, exceeds 500 KB limit"

    def test_generate_html_report_with_issues(self) -> None:
        session = _sample_session()
        issues = [
            _issue(severity="critical", pattern="bloated_prompt"),
            _issue(severity="info", pattern="minor_issue"),
        ]
        html = generate_html_report(session, issues=issues)
        assert "bloated_prompt" in html
        assert "minor_issue" in html
