# Waste Patterns Reference

skill-perf detects 8 waste patterns. Each section below describes the pattern, what triggers it, and how to write a specific SKILL.md fix.

## script_not_executed (critical)

**What:** The skill has files in `scripts/` but the model did work manually instead of running them.

**Detection:** A `skill_load` step exists (model loaded SKILL.md) AND the skill directory contains `scripts/`, but no Bash tool call executed any script (`python`, `node`, `bash`, `.py`, `.sh`).

**How to fix:** Find the scripts in the skill directory. For each script, add an explicit instruction:

```markdown
## [Task Name]
ALWAYS use the bundled script:
```bash
python scripts/[script_name].py <input>
```
Do NOT implement this manually. The script handles edge cases and is faster than generating code.
```

**Estimated savings:** Typically 1,000-5,000 tokens per avoided manual implementation.

## large_file_read (warning)

**What:** A tool result exceeded 2,000 tokens — the model loaded an entire file into context.

**Detection:** Any step with `step_type == "tool_result"` and `token_count > 2000`.

**How to fix:** Identify the file path from the step. Add targeted instructions:

```markdown
## Reading [filename]
Before reading [filepath]:
1. Run `grep -n '[relevant pattern]' [filepath]` to find the section you need
2. Read only the matching line range (e.g., lines 42-60)
Never read the entire file — it is [N] lines / [M] tokens.
```

**Estimated savings:** `impact_tokens - 200` (grep + targeted read costs ~200 tokens).

## duplicate_reads (warning)

**What:** The same file was read multiple times across turns.

**Detection:** Two or more steps with the same `file_path` and `step_type` in `("tool_call", "tool_result", "skill_load")`.

**How to fix:** Identify which file was re-read. Add:

```markdown
## File context retention
After reading [filepath], retain its contents.
Do NOT re-read it in subsequent turns — use your memory of the content.
If you need to verify a specific line, use grep instead of re-reading.
```

**Estimated savings:** Full token count of the duplicated read.

## excessive_exploration (warning)

**What:** 5 or more consecutive Glob/Grep calls before the model took action (Edit, Write, Bash).

**Detection:** 5+ consecutive steps where `tool_name` is in `("Grep", "Glob", "search", "ListTool")` with no Edit/Write/Bash in between.

**How to fix:** The model is browsing the project structure. Create a reference doc and point to it:

1. Create `references/project-structure.md` with the relevant directory layout
2. Add to SKILL.md:

```markdown
## Project navigation
Read references/project-structure.md FIRST before exploring.
Do NOT run more than 3 search commands before taking action.
Key locations:
- Source code: src/
- Tests: tests/
- Config: [config location]
```

**Estimated savings:** ~100 tokens per avoided search call, plus reduced context growth.

## oversized_skill (warning)

**What:** A skill file loaded into context exceeds 3,000 tokens.

**Detection:** Any step with `step_type == "skill_load"` and `token_count > 3000`.

**How to fix:** Split the skill file:

1. Keep SKILL.md body under 2,000 tokens (high-level instructions only)
2. Move detailed content to `references/`:
   - API details → `references/api-guide.md`
   - Examples → `references/examples.md`
   - Data formats → `references/data-formats.md`
3. In SKILL.md, reference them: "See references/api-guide.md for API details"

The model loads references on demand, so they don't cost tokens unless needed.

**Estimated savings:** `token_count - 2000` per call where the reference isn't needed.

## cat_on_large_file (warning)

**What:** The model used `cat` via Bash to read a file, which loads the entire file into context.

**Detection:** A step with `tool_name == "Bash"` where the description contains "cat " and `token_count > 500`.

**How to fix:**

```markdown
## File inspection
Never use `cat` to read files. Instead:
- Use `grep -n '[pattern]' [file]` to find relevant lines
- Use `head -n 20 [file]` for file headers
- Use `sed -n '10,30p' [file]` for specific line ranges
- Use the Read tool with line range parameters
```

**Estimated savings:** `token_count - 200` (targeted read costs ~200 tokens).

## low_cache_rate (info)

**What:** API input tokens significantly exceed the estimated content tokens, suggesting poor prompt cache utilization.

**Detection:** `api_input_tokens > 2 * total_estimated_tokens` (the API is re-processing tokens that could be cached).

**How to fix:** This is about prompt structure, not SKILL.md content:

1. Keep the system prompt stable across calls (don't inject timestamps or random IDs)
2. Place frequently-changing content at the END of messages
3. Use consistent ordering for skill files and references
4. If using multiple skills, load them in the same order each time

**Note:** Cache rate depends on the provider and model. Some providers don't support prompt caching.

## high_think_ratio (info)

**What:** The model is generating 3x more text than it spends on tool calls — lots of explaining, little doing.

**Detection:** `think_act_ratio > 3.0` where ratio = assistant_response_tokens / (tool_call_tokens + tool_result_tokens).

**How to fix:**

```markdown
## Execution style
Be concise. Prefer tool calls over explanations:
- Do NOT explain what you're about to do — just do it
- Do NOT narrate each step — show results instead
- Use scripts and tools directly rather than writing code inline
- Keep responses under 3 sentences between tool calls
```

**Estimated savings:** Depends on output token cost, which varies by model. Reducing output by 50% can save significant cost on models with expensive output tokens.
