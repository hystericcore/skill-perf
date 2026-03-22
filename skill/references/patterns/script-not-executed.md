# script_not_executed (critical)

**What:** The skill has files in `scripts/` but the model did work manually instead of running them.

**Detection:** A `skill_load` step exists AND the skill directory contains `scripts/`, but no Bash tool call executed any script.

**How to fix:** Find the scripts in the skill directory. For each script, add:

```markdown
## [Task Name]
ALWAYS use the bundled script:
```bash
python scripts/[script_name].py <input>
```
Do NOT implement this manually.
```

**Estimated savings:** 1,000-5,000 tokens per avoided manual implementation.
