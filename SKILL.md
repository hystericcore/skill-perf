---
name: skill-perf
description: Analyze and improve LLM skill performance using skill-perf CLI
---

# skill-perf

Analyze, diagnose, and improve SKILL.md performance by measuring real token usage and detecting waste patterns.

## When to use

When the user asks to:
- Analyze or optimize a SKILL.md's token footprint
- Debug why a skill is slow or expensive
- Find waste patterns in captured conversation traces
- Improve a skill's instructions based on real usage data

## Workflow

### Step 1: Estimate token footprint (offline, no traces needed)

```bash
skill-perf estimate <path-to-SKILL.md>
```

Check the output for:
- Total tokens if fully loaded
- Per-file token counts at each progressive disclosure level
- Warnings about oversized components (description >50 tokens, body >2000 tokens)
- Cost per call across providers

### Step 2: Diagnose captured traces

```bash
skill-perf diagnose <trace-directory>
skill-perf diagnose --json <trace-directory>   # for structured output
```

Read the output carefully. It shows:
- Step-by-step token breakdown (system prompt, tool calls, tool results, assistant responses)
- Token distribution by category with percentage bars
- Diagnosed issues with severity (critical > warning > info)
- Think/act ratio and total waste percentage

### Step 3: Get static suggestions

```bash
skill-perf suggest <trace-directory>
```

This shows template-based fixes. Use these as a starting point, then improve them with context from the trace.

### Step 4: Generate context-aware SKILL.md fixes

After reviewing the diagnose and suggest output, generate specific SKILL.md patches. For each diagnosed issue:

1. Look at the **step index** and find the actual step in the diagnose output
2. Identify the **file paths**, **tool names**, and **token counts** involved
3. Write a SKILL.md instruction that directly addresses the specific behavior
4. Calculate estimated savings (impact_tokens from the issue)

See `references/waste-patterns.md` for detailed fix strategies per pattern.

### Step 5: Verify improvements

After applying fixes to the SKILL.md, re-capture traces and compare:

```bash
skill-perf verify --baseline <old-traces> --current <new-traces>
```

## Generating effective fixes

When writing SKILL.md patches from diagnose output:

- **Be specific**: Reference actual file paths from the trace, not generic advice
- **Be directive**: Use "ALWAYS", "NEVER", "FIRST do X before Y"
- **Include examples**: Show the exact command or tool call to use
- **Quantify**: Mention token savings to justify the instruction
- **One fix per issue**: Don't combine unrelated fixes

Bad: "Use grep before reading files"
Good: "Before reading src/auth/handler.py, ALWAYS run `grep -n 'def login' src/auth/handler.py` first. Reading the full file costs 2,400 tokens; grep + targeted read costs ~200 tokens."

## CLI reference

See `references/cli-reference.md` for complete command documentation.
