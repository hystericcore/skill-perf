# skill_not_triggered (warning)

**What:** The user's prompt matches the skill's description, but the skill was never loaded during the session. This suggests the skill's trigger conditions or description need improvement.

**Detection:** No `skill_load` step exists in the session, but the user prompt keywords overlap with the skill's `description` frontmatter field. Requires `--skill` flag pointing to the skill directory.

**How to fix:** Improve the skill's description to better match user language:

1. Review how users phrase requests for this skill's functionality
2. Add those keywords to the `description` field in SKILL.md frontmatter
3. Make the description specific — avoid vague terms like "helps with code"

```yaml
# Bad: too vague
---
name: my-skill
description: Helps with code tasks
---

# Good: specific keywords that match user prompts
---
name: csv-processor
description: Processes CSV files with summary statistics, data analysis, and column aggregation
---
```

**Estimated savings:** If the skill provides scripts or targeted instructions, triggering it avoids manual work — typically 1,000-5,000 tokens saved per session.
