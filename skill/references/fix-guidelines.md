# Writing Effective SKILL.md Fixes

When writing SKILL.md patches from diagnose output:

- **Be specific**: Reference actual file paths from the trace, not generic advice
- **Be directive**: Use "ALWAYS", "NEVER", "FIRST do X before Y"
- **Include examples**: Show the exact command or tool call to use
- **Quantify**: Mention token savings to justify the instruction
- **One fix per issue**: Don't combine unrelated fixes

## Examples

Bad: "Use grep before reading files"

Good: "Before reading src/auth/handler.py, ALWAYS run `grep -n 'def login' src/auth/handler.py` first. Reading the full file costs 2,400 tokens; grep + targeted read costs ~200 tokens."
