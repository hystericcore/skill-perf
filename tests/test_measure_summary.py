"""Tests for measure summary helpers."""
import json
import os
import tempfile

from skill_perf.commands.measure import (
    _check_skill_loaded,
    _format_stderr_preview,
    _format_stdout_preview,
)


class TestFormatStdoutPreview:
    def test_empty_stdout(self):
        assert _format_stdout_preview("") == "(empty)"

    def test_claude_json_shows_result(self):
        data = {"type": "result", "result": "Here is the code I wrote for you.", "cost_usd": 0.01}
        preview = _format_stdout_preview(json.dumps(data))
        assert "Here is the code I wrote for you." in preview

    def test_claude_json_result_truncated(self):
        data = {"result": "line 1\nline 2\nline 3\nline 4\nline 5"}
        preview = _format_stdout_preview(json.dumps(data))
        assert "line 1" in preview
        assert "line 5" not in preview

    def test_claude_json_empty_result(self):
        data = {"result": ""}
        preview = _format_stdout_preview(json.dumps(data))
        assert "empty result" in preview

    def test_json_without_result_field(self):
        data = {"status": "ok", "data": [1, 2, 3]}
        raw = json.dumps(data)
        preview = _format_stdout_preview(raw)
        assert "JSON object" in preview
        assert str(len(raw)) in preview

    def test_plain_text_stdout(self):
        text = "line 1\nline 2\nline 3\nline 4\nline 5"
        result = _format_stdout_preview(text)
        assert "line 1" in result
        assert "line 5" not in result  # truncated to 3 lines

    def test_plain_text_three_lines_no_ellipsis(self):
        text = "line 1\nline 2\nline 3"
        result = _format_stdout_preview(text)
        assert result.count("...") == 0

    def test_long_line_truncated(self):
        text = "a" * 200
        result = _format_stdout_preview(text)
        assert len(result.split("\n")[0]) <= 83  # 80 + "..."


class TestFormatStderrPreview:
    def test_empty_stderr(self):
        assert _format_stderr_preview("") == ""

    def test_stderr_shown(self):
        result = _format_stderr_preview("error: something failed")
        assert "error: something failed" in result

    def test_stderr_truncated_to_two_lines(self):
        text = "line 1\nline 2\nline 3\nline 4"
        result = _format_stderr_preview(text)
        assert "line 1" in result
        assert "line 2" in result
        assert "line 3" not in result

    def test_stderr_long_line_truncated(self):
        text = "b" * 200
        result = _format_stderr_preview(text)
        assert len(result.split("\n")[0]) <= 83  # 80 + "..."


class TestCheckSkillLoaded:
    def test_skill_found_in_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = os.path.join(tmpdir, "trace.jsonl")
            with open(trace, "w") as f:
                f.write('{"tool": {"name": "Skill"}}\n')
            assert _check_skill_loaded(tmpdir) is True

    def test_no_skill_in_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trace = os.path.join(tmpdir, "trace.jsonl")
            with open(trace, "w") as f:
                f.write('{"tool": {"name": "Read"}}\n')
            assert _check_skill_loaded(tmpdir) is False

    def test_skill_found_in_split_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            split_dir = os.path.join(tmpdir, "split_output")
            os.makedirs(split_dir)
            with open(os.path.join(split_dir, "001.json"), "w") as f:
                f.write('{"content": [{"type": "tool_use", "name": "Skill"}]}')
            assert _check_skill_loaded(tmpdir) is True

    def test_empty_trace_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assert _check_skill_loaded(tmpdir) is False
