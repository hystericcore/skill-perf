import json

from skill_perf.models import (
    BenchmarkResult,
    Comparison,
    ConversationStep,
    Issue,
    SessionAnalysis,
    TreemapNode,
)


def _make_step(**kwargs):
    defaults = {
        "turn": 1,
        "role": "assistant",
        "step_type": "tool_call",
        "description": "test step",
        "token_count": 100,
    }
    defaults.update(kwargs)
    return ConversationStep(**defaults)


def _make_issue(**kwargs):
    defaults = {
        "severity": "warning",
        "pattern": "large_file_read",
        "step_index": 0,
        "description": "test issue",
        "impact_tokens": 500,
        "suggestion": "use grep",
    }
    defaults.update(kwargs)
    return Issue(**defaults)


def test_conversation_step_basic():
    step = _make_step()
    assert step.turn == 1
    assert step.role == "assistant"
    assert step.tool_name is None
    assert step.file_path is None


def test_conversation_step_with_tool():
    step = _make_step(tool_name="Read", file_path="/src/main.py")
    assert step.tool_name == "Read"
    assert step.file_path == "/src/main.py"


def test_issue_basic():
    issue = _make_issue()
    assert issue.severity == "warning"
    assert issue.impact_tokens == 500


def test_session_analysis_computed_fields():
    steps = [
        _make_step(step_type="system_prompt", token_count=200, role="system"),
        _make_step(step_type="assistant_response", token_count=300),
        _make_step(step_type="tool_call", token_count=50, tool_name="Bash"),
        _make_step(step_type="tool_result", token_count=150, role="tool"),
    ]
    issues = [_make_issue(impact_tokens=150)]

    session = SessionAnalysis(
        session_id="test-001",
        model="claude-sonnet-4",
        api_input_tokens=1000,
        api_output_tokens=500,
        steps=steps,
        issues=issues,
    )

    assert session.total_estimated_tokens == 700
    assert session.tokens_by_type["system_prompt"] == 200
    assert session.tokens_by_type["assistant_response"] == 300
    assert session.tokens_by_tool["Bash"] == 50
    assert session.think_act_ratio == 300 / (50 + 150)  # 1.5
    assert session.waste_tokens == 150
    assert abs(session.waste_percentage - (150 / 700 * 100)) < 0.01


def test_session_analysis_zero_tool_tokens():
    steps = [_make_step(step_type="assistant_response", token_count=100)]
    session = SessionAnalysis(
        session_id="test-002",
        model="claude-sonnet-4",
        api_input_tokens=100,
        api_output_tokens=50,
        steps=steps,
    )
    assert session.think_act_ratio == 100.0


def test_treemap_node_recursive():
    child = TreemapNode(
        name="child",
        token_count=50,
        effective_tokens=40,
        cost_usd=0.001,
        category="tool_result",
    )
    parent = TreemapNode(
        name="parent",
        token_count=100,
        effective_tokens=80,
        cost_usd=0.002,
        category="session",
        children=[child],
    )
    assert len(parent.children) == 1
    assert parent.children[0].name == "child"


def test_treemap_node_with_issues():
    issue = _make_issue()
    node = TreemapNode(
        name="wasteful",
        token_count=500,
        effective_tokens=500,
        cost_usd=0.01,
        category="waste",
        issues=[issue],
        is_wasteful=True,
    )
    assert node.is_wasteful
    assert len(node.issues) == 1


def test_benchmark_result():
    session = SessionAnalysis(
        session_id="s1",
        model="claude-sonnet-4",
        api_input_tokens=1000,
        api_output_tokens=200,
        steps=[_make_step()],
    )
    result = BenchmarkResult(
        run_id="run-001",
        timestamp="2026-03-23T00:00:00Z",
        skill_name="my-skill",
        sessions=[session],
        total_tokens=1200,
        total_cost_usd=0.0036,
        total_issues=0,
    )
    assert result.run_id == "run-001"
    assert len(result.sessions) == 1


def test_comparison():
    session = SessionAnalysis(
        session_id="s1",
        model="claude-sonnet-4",
        api_input_tokens=1000,
        api_output_tokens=200,
        steps=[_make_step()],
    )
    baseline = BenchmarkResult(
        run_id="baseline",
        timestamp="2026-03-22T00:00:00Z",
        skill_name="my-skill",
        sessions=[session],
        total_tokens=2000,
        total_cost_usd=0.006,
        total_issues=2,
    )
    current = BenchmarkResult(
        run_id="current",
        timestamp="2026-03-23T00:00:00Z",
        skill_name="my-skill",
        sessions=[session],
        total_tokens=1200,
        total_cost_usd=0.0036,
        total_issues=0,
    )
    resolved = [_make_issue(), _make_issue(pattern="duplicate_reads")]
    comp = Comparison(
        baseline=baseline,
        current=current,
        token_delta=-800,
        cost_delta=-0.0024,
        issues_resolved=resolved,
        issues_remaining=[],
    )
    assert comp.token_delta == -800
    assert len(comp.issues_resolved) == 2


def test_json_serialization_roundtrip():
    step = _make_step(tool_name="Read", file_path="/test.py")
    data = step.model_dump()
    restored = ConversationStep(**data)
    assert restored == step

    json_str = step.model_dump_json()
    restored2 = ConversationStep.model_validate_json(json_str)
    assert restored2 == step


def test_session_json_roundtrip():
    session = SessionAnalysis(
        session_id="test",
        model="claude-sonnet-4",
        api_input_tokens=500,
        api_output_tokens=100,
        steps=[_make_step()],
        issues=[_make_issue()],
    )
    json_str = session.model_dump_json()
    data = json.loads(json_str)
    assert "total_estimated_tokens" in data
    assert "tokens_by_type" in data
    assert "think_act_ratio" in data
