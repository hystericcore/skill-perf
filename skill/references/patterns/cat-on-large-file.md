# cat_on_large_file (warning)

**What:** The model used `cat` via Bash to read a file, loading the entire file into context.

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
