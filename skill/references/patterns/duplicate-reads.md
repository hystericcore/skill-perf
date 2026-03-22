# duplicate_reads (warning)

**What:** The same file was read multiple times across turns.

**Detection:** Two or more steps with the same `file_path` and `step_type` in `("tool_call", "tool_result", "skill_load")`.

**How to fix:** Identify which file was re-read. Add:

```markdown
## File context retention
After reading [filepath], retain its contents.
Do NOT re-read it in subsequent turns -- use your memory of the content.
If you need to verify a specific line, use grep instead of re-reading.
```

**Estimated savings:** Full token count of the duplicated read.
