# large_file_read (warning)

**What:** A tool result exceeded 2,000 tokens -- the model loaded an entire file into context.

**Detection:** Any step with `step_type == "tool_result"` and `token_count > 2000`.

**How to fix:** Identify the file path from the step. Add:

```markdown
## Reading [filename]
Before reading [filepath]:
1. Run `grep -n '[relevant pattern]' [filepath]` to find the section you need
2. Read only the matching line range
Never read the entire file -- it is [N] lines / [M] tokens.
```

**Estimated savings:** `impact_tokens - 200` (grep + targeted read costs ~200 tokens).
