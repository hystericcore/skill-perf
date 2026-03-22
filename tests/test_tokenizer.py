"""Tests for skill_perf.core.tokenizer."""

from skill_perf.core.tokenizer import content_to_text, count_tokens

# --- count_tokens ---------------------------------------------------------


def test_count_tokens_nonempty():
    """count_tokens returns > 0 for non-empty text."""
    assert count_tokens("Hello, world!") > 0


def test_count_tokens_empty():
    """count_tokens returns 0 for empty string."""
    assert count_tokens("") == 0


# --- content_to_text ------------------------------------------------------


def test_content_to_text_string():
    """content_to_text handles plain string input."""
    assert content_to_text("hello") == "hello"


def test_content_to_text_list_of_text_blocks():
    """content_to_text handles a list of text blocks."""
    blocks = [
        {"type": "text", "text": "first"},
        {"type": "text", "text": "second"},
    ]
    result = content_to_text(blocks)
    assert "first" in result
    assert "second" in result


def test_content_to_text_tool_use_blocks():
    """content_to_text handles list with tool_use blocks."""
    blocks = [
        {"type": "tool_use", "id": "tu_1", "name": "Read", "input": {"file_path": "/a.py"}},
    ]
    result = content_to_text(blocks)
    assert "/a.py" in result


def test_content_to_text_tool_result_blocks():
    """content_to_text handles list with tool_result blocks."""
    blocks = [
        {
            "type": "tool_result",
            "tool_use_id": "tu_1",
            "content": "file contents here",
        },
    ]
    result = content_to_text(blocks)
    assert "file contents here" in result


def test_content_to_text_dict_input():
    """content_to_text handles a dict by converting to str."""
    result = content_to_text({"key": "value"})
    assert "key" in result
    assert "value" in result


def test_content_to_text_mixed_list():
    """content_to_text handles a list mixing strings and dicts."""
    blocks = [
        "plain string",
        {"type": "text", "text": "block text"},
    ]
    result = content_to_text(blocks)
    assert "plain string" in result
    assert "block text" in result


def test_content_to_text_nested_tool_result():
    """content_to_text recursively handles nested tool_result content."""
    blocks = [
        {
            "type": "tool_result",
            "tool_use_id": "tu_2",
            "content": [{"type": "text", "text": "nested"}],
        },
    ]
    result = content_to_text(blocks)
    assert "nested" in result
