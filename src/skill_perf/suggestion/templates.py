"""Suggestion templates for all 9 diagnosis patterns."""


TEMPLATES: dict[str, str] = {
    "script_not_executed": """Add to SKILL.md:

  ## {task_description}
  ALWAYS use the bundled script:
  ```bash
  python scripts/{script_name} <input>
  ```
  Do NOT implement this manually.""",
    "large_file_read": """File {file_path} loaded {token_count} tokens into context.

  Add to SKILL.md:

  ## Reading {file_path}
  Before reading this file:
  1. Use `grep -n '<pattern>' {file_path}` to find the relevant section
  2. Read only the matching line range
  Never read the entire file.""",
    "duplicate_reads": """File {file_path} was read {read_count} times in this session.

  Add to SKILL.md:

  ## Context retention
  After reading {file_path}, retain its contents in memory.
  Do NOT re-read it in subsequent turns.
  Use grep to verify specific lines if needed.""",
    "excessive_exploration": """{exploration_count} consecutive search calls before taking action.

  Add to SKILL.md:

  ## Project navigation
  Read references/project-structure.md FIRST before exploring.
  Do NOT run more than 3 search commands before taking action.""",
    "oversized_skill": """Skill file {file_path} is {token_count} tokens.

  Split your SKILL.md:
  1. Keep SKILL.md under 2000 tokens (high-level overview only)
  2. Move detailed instructions to references/ files
  3. The model loads references on demand.""",
    "cat_on_large_file": """Step [{step_index}]: cat on {file_path} ({token_count} tokens).

  Add to SKILL.md:

  ## File inspection
  Never use `cat` to read entire files. Instead:
  - Use `grep -n '<pattern>' <file>` to find relevant lines
  - Use `head -n 20 <file>` for file headers
  - Use the Read tool with line range parameters""",
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
    "skill_not_triggered": """Improve the skill's trigger conditions:

  1. Review the skill description in SKILL.md frontmatter
  2. Add keywords that match how users phrase their requests
  3. Make the description more specific about what the skill handles

  The description field determines when the skill is activated.
  If users ask relevant questions but the skill doesn't trigger,
  the description needs to better match their language.""",
}
