---
name: skill-perf
description: Analyze and improve LLM skill performance using skill-perf CLI
---

# skill-perf

Analyze, diagnose, and improve SKILL.md performance using the skill-perf CLI tool. The tool is the source of truth for pattern detection, suggestions, and fixes.

## When to use

When the user asks to:
- Analyze or optimize a SKILL.md's token footprint
- Debug why a skill is slow or expensive
- Find waste patterns in captured conversation traces
- Improve a skill's instructions based on real usage data

## Workflow

### Step 1: Estimate token footprint

Run `skill-perf estimate <path-to-SKILL.md>` to check token counts, progressive disclosure levels, size warnings, and cost per call.

### Step 2: Diagnose captured traces

Run `skill-perf diagnose <trace-directory>` to detect waste patterns. Read the output — it contains step-by-step breakdowns, severity-ranked issues, and token impact.

### Step 3: Get fix suggestions

Run `skill-perf suggest <trace-directory>` to get actionable fixes from the tool. Each suggestion includes:
- The waste pattern and severity
- Which step triggered it
- A concrete fix with example SKILL.md text
- Estimated token savings

### Step 4: Improve suggestions with trace context

The tool's suggestions are templates. Make them specific by referencing the diagnose output:
- Use actual file paths and tool names from the trace
- Reference specific step numbers and token counts
- Use directive language: "ALWAYS", "NEVER", "FIRST do X before Y"
- Quantify savings to justify the instruction

### Step 5: Verify improvements

Run `skill-perf verify --baseline <old-traces> --current <new-traces>` to confirm fixes reduced tokens.

## CLI reference

Run `skill-perf --help` or `skill-perf <command> --help` for flags and options.
