"""Suggestion templates for all 8 diagnosis patterns."""

from __future__ import annotations

TEMPLATES: dict[str, str] = {
    "script_not_executed": """Add to SKILL.md:

  ## {task_description}
  ALWAYS use the bundled script:
  ```bash
  python scripts/{script_name} <input>
  ```
  Do NOT implement this manually.""",
    "large_file_read": """Add to SKILL.md:

  ## Reading source files
  Before reading any file larger than 50 lines:
  1. Use grep to find the relevant section first
  2. Read only the relevant line range with view tool
  Never read an entire file when you only need a section.""",
    "duplicate_reads": """Add to SKILL.md:

  ## Context retention
  After reading a file, retain its contents in context.
  Do NOT re-read the same file in subsequent turns.
  If you need to reference it again, use your memory of the content.""",
    "excessive_exploration": """Add to SKILL.md:

  ## Project structure
  The project structure is documented in references/project-structure.md.
  Read it FIRST before exploring with glob/grep.
  Do NOT run more than 3 search commands before taking action.""",
    "oversized_skill": """Split your SKILL.md:

  Move detailed instructions to references/ files:
  1. Keep SKILL.md under 2000 tokens (high-level overview only)
  2. Move API details to references/api-guide.md
  3. Move examples to references/examples.md
  The model will load references on demand.""",
    "cat_on_large_file": """Add to SKILL.md:

  ## File inspection
  Never use `cat` to read entire files.
  Use `grep` to find relevant lines, then `head`/`tail` or
  line-range reads to view specific sections.""",
    "low_cache_rate": """Improve cache hit rate:

  1. Keep system prompt stable across calls (avoid dynamic content)
  2. Place frequently-changing content at the END of the prompt
  3. Use consistent skill file ordering""",
    "high_think_ratio": """Add to SKILL.md:

  ## Execution style
  Prefer using tools over generating long explanations.
  When a task can be accomplished with a script or tool call,
  use the tool directly instead of writing out the solution.
  Be concise in your responses.""",
}
