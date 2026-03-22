# excessive_exploration (warning)

**What:** 5+ consecutive Glob/Grep calls before the model took action (Edit, Write, Bash).

**Detection:** 5+ consecutive steps where `tool_name` is in `("Grep", "Glob", "search", "ListTool")` with no Edit/Write/Bash in between.

**How to fix:** Create a reference doc and point to it:

1. Create `references/project-structure.md` with the relevant directory layout
2. Add to SKILL.md:

```markdown
## Project navigation
Read references/project-structure.md FIRST before exploring.
Do NOT run more than 3 search commands before taking action.
```

**Estimated savings:** ~100 tokens per avoided search call, plus reduced context growth.
