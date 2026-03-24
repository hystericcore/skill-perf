---
name: skill-perf
description: Analyze and improve LLM skill performance using skill-perf CLI
---

# skill-perf

Analyze, diagnose, and improve SKILL.md performance using the skill-perf CLI tool. The tool is the source of truth for pattern detection, suggestions, and fixes.

## When to use

When the user asks to:
- Create or scaffold a new skill
- Analyze or optimize a SKILL.md's token footprint
- Debug why a skill is slow or expensive
- Find waste patterns in captured conversation traces
- Improve a skill's instructions based on real usage data

## Workflow

### Step 0: Create a new skill (if none exists)

Run `skill-perf create <name> -d "description"` to scaffold a valid SKILL.md directory with references/ and scripts/ subdirectories.

### Step 1: Estimate and validate

Run `skill-perf estimate <path>` to check:
- Format validation (frontmatter, required fields, spec limits)
- Token counts at each progressive disclosure level
- Size warnings and cost per call

Fix any ERROR-level issues before proceeding.

### Step 2: Measure real usage

Run `skill-perf measure -p "prompt" --diagnose` to capture real token usage via proxy.

Key flags:
- `--cli` — which coding assistant to invoke: `claude` (default), `cursor` / `agent`, `gemini`, `aider`
- `--model` — model name passed to the CLI (default: `haiku` for fast/cheap iteration). Use the assistant's model ID, e.g. `claude-haiku-4-5`, `gemini-2.5-flash`, `gpt-4o`.
- `--skill-a` / `--skill-b` + `--compare` — A/B test two skill versions in one run

Reading the output:
- **exit_code 0 + JSON stdout + traces captured** = successful run, proceed to diagnose
- **exit_code -1 + "Timeout" stderr** = skill may be too complex, increase --timeout or simplify
- **exit_code 0 + empty traces** = proxy not configured, check proxy setup
- **exit_code != 0 + stderr errors** = CLI issue, investigate before diagnosing

The stdout preview shows the final model response (`result` field for Claude JSON). If it's empty or the skill-loaded line shows `no`, the trace may not reflect real skill behaviour.

### Step 3: Diagnose captured traces

Run `skill-perf diagnose <trace-directory>` to detect waste patterns. Read the output — it contains step-by-step breakdowns, severity-ranked issues, and token impact.

### Step 4: Get fix suggestions

Run `skill-perf suggest <trace-directory>` to get actionable fixes. Each suggestion includes:
- The waste pattern and severity
- Which step triggered it
- A concrete fix with example SKILL.md text
- Estimated token savings

### Step 5: Apply suggestions to SKILL.md

The tool's suggestions are templates. Apply them to the actual SKILL.md:
- Preserve existing frontmatter fields (name, description)
- Add instructions under relevant workflow sections
- Use directive language: "ALWAYS", "NEVER", "FIRST do X before Y"
- Reference actual file paths and tool names from the trace
- Quantify savings to justify the instruction

### Step 6: Re-estimate after changes

Run `skill-perf estimate <path>` again to confirm:
- No new validation errors introduced
- Token budget is still within limits
- Cost per call is acceptable

### Step 7: Verify improvements

Run `skill-perf verify --baseline <old-traces> --current <new-traces>` to confirm fixes reduced tokens.

## CLI reference

Run `skill-perf --help` or `skill-perf <command> --help` for flags and options.
