"""Tests for the trace parser modules."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_perf.parser.providers import detect_provider
from skill_perf.parser.classifier import classify_step
from skill_perf.parser.messages import parse_request, parse_response_usage
from skill_perf.parser.streaming import parse_sse_response
from skill_perf.parser.trace_reader import parse_session

FIXTURES = Path(__file__).parent / "fixtures"


# ── Provider detection ──────────────────────────────────────────────

class TestDetectProvider:
    def test_detect_provider_anthropic(self):
        assert detect_provider("https://api.anthropic.com/v1/messages") == "anthropic"

    def test_detect_provider_openai(self):
        assert detect_provider("https://api.openai.com/v1/chat/completions") == "openai"

    def test_detect_provider_unknown(self):
        assert detect_provider("https://custom-llm.example.com/api") == "unknown"

    def test_detect_provider_google(self):
        assert detect_provider("https://generativelanguage.googleapis.com/v1/models") == "google"

    def test_detect_provider_bedrock(self):
        assert detect_provider("https://bedrock-runtime.us-east-1.amazonaws.com/invoke") == "aws-bedrock"


# ── Step classification ─────────────────────────────────────────────

class TestClassifyStep:
    def test_classify_step_skill_load(self):
        step_type, desc, path = classify_step("Read", {"file_path": "/project/SKILL.md"})
        assert step_type == "skill_load"
        assert "SKILL.md" in desc
        assert path == "/project/SKILL.md"

    def test_classify_step_skill_load_references(self):
        step_type, _, path = classify_step("Read", {"file_path": "/project/references/api.md"})
        assert step_type == "skill_load"

    def test_classify_step_skill_load_skills_dir(self):
        step_type, _, _ = classify_step("View", {"path": "/repo/skills/coding.md"})
        assert step_type == "skill_load"

    def test_classify_step_tool_call(self):
        step_type, desc, _ = classify_step("Bash", {"command": "python test.py"})
        assert step_type == "tool_call"
        assert "Bash" in desc

    def test_classify_step_tool_call_grep(self):
        step_type, desc, _ = classify_step("Grep", {"pattern": "def main"})
        assert step_type == "tool_call"
        assert "Grep" in desc

    def test_classify_step_tool_call_edit(self):
        step_type, desc, path = classify_step("Edit", {"file_path": "src/main.py"})
        assert step_type == "tool_call"
        assert path == "src/main.py"

    def test_classify_step_tool_result(self):
        step_type, desc, path = classify_step("Read", {"file_path": "src/app.py"})
        assert step_type == "tool_result"
        assert "src/app.py" in desc
        assert path == "src/app.py"


# ── Message parsing ─────────────────────────────────────────────────

class TestParseRequest:
    def test_parse_request_basic(self):
        body = {
            "system": "You are helpful.",
            "messages": [
                {"role": "user", "content": "Hello world"},
                {"role": "assistant", "content": "Hi there!"},
            ],
        }
        steps = parse_request(body)
        assert len(steps) == 3
        assert steps[0].step_type == "system_prompt"
        assert steps[0].role == "system"
        assert steps[1].step_type == "user_message"
        assert steps[1].role == "user"
        assert steps[2].step_type == "assistant_response"
        assert steps[2].role == "assistant"

    def test_parse_request_with_tool_use(self):
        body = {
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "Let me check."},
                        {
                            "type": "tool_use",
                            "id": "t1",
                            "name": "Grep",
                            "input": {"pattern": "TODO"},
                        },
                    ],
                },
            ],
        }
        steps = parse_request(body)
        assert len(steps) == 2
        assert steps[0].step_type == "assistant_response"
        assert steps[1].step_type == "tool_call"
        assert steps[1].tool_name == "Grep"

    def test_parse_request_with_tool_result_blocks(self):
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "t1",
                            "content": "Result data here",
                        }
                    ],
                },
            ],
        }
        steps = parse_request(body)
        # Should produce a user_message step + a tool_result step
        assert any(s.step_type == "tool_result" for s in steps)

    def test_parse_request_system_list(self):
        body = {
            "system": [{"type": "text", "text": "System instructions"}],
            "messages": [],
        }
        steps = parse_request(body)
        assert len(steps) == 1
        assert steps[0].step_type == "system_prompt"


class TestParseResponseUsage:
    def test_parse_response_usage_anthropic(self):
        body = {
            "model": "claude-sonnet-4-20250514",
            "usage": {
                "input_tokens": 1500,
                "output_tokens": 350,
            },
        }
        inp, out, model = parse_response_usage(body, "anthropic")
        assert inp == 1500
        assert out == 350
        assert model == "claude-sonnet-4-20250514"

    def test_parse_response_usage_openai(self):
        body = {
            "model": "gpt-4o",
            "usage": {
                "prompt_tokens": 800,
                "completion_tokens": 200,
            },
        }
        inp, out, model = parse_response_usage(body, "openai")
        assert inp == 800
        assert out == 200
        assert model == "gpt-4o"


# ── SSE streaming ───────────────────────────────────────────────────

class TestParseSSE:
    def test_parse_sse_anthropic(self):
        sse_content = (
            'data: {"type": "message_start", "message": {"id": "msg_01", '
            '"model": "claude-sonnet-4-20250514", "usage": {"input_tokens": 950, '
            '"cache_read_input_tokens": 100, "cache_creation_input_tokens": 25}}}\n'
            "\n"
            'data: {"type": "content_block_delta", "index": 0, '
            '"delta": {"type": "text_delta", "text": "Hello"}}\n'
            "\n"
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, '
            '"usage": {"output_tokens": 180}}\n'
            "\n"
            "data: [DONE]\n"
        )
        result = parse_sse_response(sse_content, "anthropic")
        assert result["model"] == "claude-sonnet-4-20250514"
        assert result["input_tokens"] == 950
        assert result["output_tokens"] == 180
        assert result["cache_read_tokens"] == 100
        assert result["cache_creation_tokens"] == 25

    def test_parse_sse_openai(self):
        sse_content = (
            'data: {"id": "chatcmpl-1", "model": "gpt-4o", '
            '"choices": [{"delta": {"content": "Hi"}}]}\n'
            "\n"
            'data: {"id": "chatcmpl-1", "model": "gpt-4o", '
            '"choices": [], "usage": {"prompt_tokens": 500, '
            '"completion_tokens": 120}}\n'
            "\n"
            "data: [DONE]\n"
        )
        result = parse_sse_response(sse_content, "openai")
        assert result["model"] == "gpt-4o"
        assert result["input_tokens"] == 500
        assert result["output_tokens"] == 120


# ── Session parsing (integration with fixtures) ─────────────────────

class TestParseSession:
    def test_parse_session_split_output(self):
        session = parse_session(str(FIXTURES / "session_01"))
        assert session.session_id == "session_01"
        assert session.model == "claude-sonnet-4-20250514"
        assert session.api_input_tokens == 1500
        assert session.api_output_tokens == 350
        assert len(session.steps) > 0

        # Check we have system prompt
        system_steps = [s for s in session.steps if s.step_type == "system_prompt"]
        assert len(system_steps) == 1

        # Check skill_load for SKILL.md
        skill_steps = [s for s in session.steps if s.step_type == "skill_load"]
        assert len(skill_steps) >= 1
        assert any("SKILL" in (s.file_path or "") for s in skill_steps)

        # Check tool_call steps exist (Bash, Grep)
        tool_calls = [s for s in session.steps if s.step_type == "tool_call"]
        assert len(tool_calls) >= 2

        # Check tool_result steps (from user content blocks)
        tool_results = [s for s in session.steps if s.step_type == "tool_result"]
        assert len(tool_results) >= 1

    def test_parse_session_merged_jsonl(self):
        session = parse_session(str(FIXTURES / "session_02"))
        assert session.session_id == "session_02"
        assert session.model == "gpt-4o"
        assert session.api_input_tokens == 800
        assert session.api_output_tokens == 200
        assert len(session.steps) > 0

        # OpenAI format: system message is in messages array, not top-level
        # The fixture uses "system" role in messages; our parse_request
        # only handles top-level "system" key, so this becomes a user message
        # at turn 1. The response has usage with prompt_tokens.

    def test_parse_session_nonexistent(self):
        session = parse_session("/tmp/nonexistent_session_xyz")
        assert session.session_id == "nonexistent_session_xyz"
        assert len(session.steps) == 0
        assert session.api_input_tokens == 0
