"""Classify tool calls into step types for conversation analysis."""


from typing import Literal

StepType = Literal[
    "system_prompt",
    "user_message",
    "tool_call",
    "tool_result",
    "skill_load",
    "assistant_response",
]

# Tool names that represent file reading
_READ_TOOLS = frozenset({"read", "fileread", "filereadtool", "view"})

# Tool names that represent file writing/editing
_WRITE_TOOLS = frozenset({"write", "edit", "create", "str_replace"})

# Tool names that represent search/exploration
_SEARCH_TOOLS = frozenset({"grep", "glob", "search", "listtool"})

# Tool names that represent command execution
_EXEC_TOOLS = frozenset({"bash", "bashtool", "execute"})

# Path patterns that indicate skill/reference loading
_SKILL_PATTERNS = ("SKILL", "skills/", "references/")

# Keywords indicating script execution in bash commands
_SCRIPT_KEYWORDS = ("python ", "node ", "bash ", ".sh", ".py")


def classify_step(tool_name: str, tool_input: dict[str, str]) -> tuple[StepType, str, str]:
    """Classify a tool call into (step_type, description, file_path).

    Rules:
    - Read/View on paths containing "SKILL", "skills/", "references/" -> skill_load
    - Read/View on other source files -> tool_result
    - Bash with python/node/bash/.sh/.py -> tool_call (script exec)
    - Bash with cat on large files -> tool_call (potentially wasteful)
    - Grep/Glob -> tool_call (exploration)
    - Edit/Write/Create -> tool_call
    """
    name_lower = (tool_name or "").lower()

    # Skill tool (Claude Code's built-in skill invocation)
    if name_lower == "skill":
        skill_name = tool_input.get("skill", "")
        args = tool_input.get("args", "")
        desc = f"Skill: {skill_name}"
        if args:
            desc += f" ({args})"
        return "skill_load", desc, ""

    # File reading tools
    if name_lower in _READ_TOOLS:
        path = tool_input.get("path", tool_input.get("file_path", ""))
        # Check if it's a skill/reference load
        if any(pattern in path for pattern in _SKILL_PATTERNS):
            return "skill_load", f"Load skill: {path}", path
        return "tool_result", f"Read file: {path}", path

    # Command execution
    if name_lower in _EXEC_TOOLS:
        cmd = tool_input.get("command", "")
        truncated = cmd[:80]
        return "tool_call", f"Bash: {truncated}", ""

    # File writing/editing
    if name_lower in _WRITE_TOOLS:
        path = tool_input.get("path", tool_input.get("file_path", ""))
        return "tool_call", f"{tool_name}: {path}", path

    # Search/exploration tools
    if name_lower in _SEARCH_TOOLS:
        pattern = tool_input.get("pattern", tool_input.get("query", ""))
        truncated = pattern[:60]
        return "tool_call", f"{tool_name}: {truncated}", ""

    # Fallback
    return "tool_call", f"{tool_name}: {str(tool_input)[:60]}", ""
