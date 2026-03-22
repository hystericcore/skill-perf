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

### Step 1: Estimate token footprint

Run `skill-perf estimate <path-to-SKILL.md>` to check token counts, progressive disclosure levels, size warnings, and cost per call. No API needed.

### Step 2: Diagnose captured traces

Run `skill-perf diagnose <trace-directory>` to find waste patterns. Shows step-by-step breakdown, token distribution, severity-ranked issues, and think/act ratio.

### Step 3: Get static suggestions

Run `skill-perf suggest <trace-directory>` for template-based fixes. Use as a starting point.

### Step 4: Generate context-aware SKILL.md fixes

For each diagnosed issue, write a specific SKILL.md patch:
1. Find the step index in the diagnose output
2. Identify file paths, tool names, and token counts
3. Write a directive instruction addressing the behavior
4. Calculate estimated savings from impact_tokens

See `references/patterns/` for fix strategies per pattern.
See `references/fix-guidelines.md` for guidelines on writing effective fixes.

### Step 5: Verify improvements

Run `skill-perf verify --baseline <old-traces> --current <new-traces>` to confirm fixes reduced tokens.

## CLI reference

See `references/cli-reference.md` for complete command documentation.
