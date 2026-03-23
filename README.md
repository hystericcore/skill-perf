# skill-perf

> webpack-bundle-analyzer for LLM context.
> Find where your skill underperforms and fix it.

Every token your skill wastes costs money and slows down the model. **skill-perf**
measures real token usage, diagnoses waste patterns, suggests concrete fixes,
and verifies improvements -- a continuous optimization cycle for LLM skills.

## Install

```bash
pipx install git+https://github.com/hystericcore/skill-perf.git
```

## Quick Start

```bash
# 1. Estimate your skill's token footprint (no API call needed)
skill-perf estimate ./my-skill/SKILL.md

# 2. Measure real token usage via proxy capture
skill-perf measure --prompt "Create a CSV parser" --diagnose --open

# 3. Diagnose captured traces for waste patterns
skill-perf diagnose ./bench_results/session-001/

# 4. Get actionable fix suggestions
skill-perf suggest ./bench_results/session-001/

# 5. Verify improvements between versions
skill-perf verify --baseline ./v1/traces/ --current ./v2/traces/
```

## The Improvement Cycle

```
  Measure          Diagnose          Suggest           Verify
+-----------+    +-----------+    +-----------+    +-----------+
| Capture   |--->| Find waste|--->| Get fixes |--->| Compare   |
| real token|    | patterns  |    | with token|    | before &  |
| usage     |    | & hotspots|    | savings   |    | after     |
+-----------+    +-----------+    +-----------+    +-----------+
      ^                                                  |
      +--------------------------------------------------+
                     Iterate until lean
```

1. **Measure** -- Run your skill against real prompts and capture every API
   request/response through a local proxy.
2. **Diagnose** -- Detect 9 built-in waste patterns (duplicate reads,
   oversized skills, unused scripts, excessive exploration, and more).
3. **Suggest** -- Get specific, actionable fixes with estimated token savings
   and dollar-cost reduction per call.
4. **Verify** -- Re-run after applying fixes and confirm improvements
   against the baseline.

## Commands

### `skill-perf estimate`

Offline analysis of a skill directory. Counts tokens at each progressive-disclosure
level, flags oversized components, and estimates cost across providers.

```bash
# Analyze a single skill
skill-perf estimate ./my-skill/SKILL.md

# Analyze a directory of skills
skill-perf estimate ./skills/

# Compare two skill versions side by side
skill-perf estimate ./v1/ ./v2/ --compare

# Output as JSON for CI pipelines
skill-perf estimate ./my-skill/ --json
```

Sample output:

```
──────────────── Skill: csv-processor ────────────────
Level 1 -- Metadata (always loaded)
  description: 8 tokens  [under 50]

Level 2 -- SKILL.md body (on trigger)
  SKILL.md body: 142 tokens (18 lines)  [under 2000]

Level 3 -- References (on demand)
  references/data-formats.md: 52 tokens
  scripts/process_csv.py (exec only): 89 tokens

  Total if fully loaded: 291 tokens

──────────── Cost per call (full load) ─────────────
  claude-sonnet-4              $0.000873
  gpt-4o                       $0.000728
  gemini-2.0-flash             $0.000022
  ollama-any                   FREE
```

### `skill-perf measure`

Run a skill against one or more prompts and capture real token usage through a
local llm-interceptor (lli) proxy.

```bash
# Single prompt
skill-perf measure --prompt "Create a CSV parser"

# Run a test suite (see examples/test-suite.json for format)
skill-perf measure --suite ./examples/test-suite.json

# Capture and immediately diagnose + open report
skill-perf measure --prompt "Refactor this module" --diagnose --open

# A/B comparison of two skill versions
skill-perf measure --compare --skill-a ./v1/ --skill-b ./v2/ \
    --suite ./examples/test-suite.json

# Custom settings
skill-perf measure --prompt "Parse JSON" --cli claude --port 9090 \
    --output ./results --max-turns 5 --timeout 180
```

### `skill-perf config`

Show or generate threshold configuration.

```bash
# Show current thresholds
skill-perf config

# Generate default .skill-perf.toml in your project
skill-perf config --generate
```

### `skill-perf diagnose`

Parse captured trace sessions and detect waste patterns.

```bash
# Diagnose a single session
skill-perf diagnose ./bench_results/session-001/

# Include skill directory for script detection
skill-perf diagnose ./bench_results/session-001/ --skill ./my-skill/

# Open interactive HTML treemap in browser
skill-perf diagnose ./bench_results/session-001/ --open

# Generate static HTML report
skill-perf diagnose ./bench_results/session-001/ --static
skill-perf diagnose ./bench_results/session-001/ --report ./report.html

# Use custom threshold config
skill-perf diagnose ./bench_results/session-001/ --config custom.toml

# JSON output for programmatic use
skill-perf diagnose ./bench_results/session-001/ --json
```

Output includes a step-by-step breakdown with token counts, a token distribution
chart by category, think/act ratio, and all diagnosed issues with severity and
suggested fixes.

### `skill-perf suggest`

Generate detailed, actionable fix suggestions for every diagnosed issue, with
estimated token savings and cost reduction.

```bash
# Get suggestions for a session
skill-perf suggest ./bench_results/session-001/

# JSON output
skill-perf suggest ./bench_results/session-001/ --json
```

Each suggestion includes:

- The waste pattern and severity
- Which step triggered it
- A concrete fix with example code or SKILL.md changes
- Estimated tokens saved per call and dollar-cost savings

### `skill-perf verify`

Re-run and confirm improvements against a baseline.

```bash
skill-perf verify --baseline ./v1/traces/ --current ./v2/traces/
```

## Waste Patterns

skill-perf detects 9 built-in waste patterns (thresholds are configurable via `.skill-perf.toml`):

| Severity | Pattern | Description |
|----------|---------|-------------|
| critical | `script_not_executed` | Skill has `scripts/` but the model did work manually instead of running them |
| warning | `large_file_read` | Tool result exceeds 2,000 tokens -- consider filtering or extracting relevant sections |
| warning | `duplicate_read` | Same file read more than once across turns |
| warning | `excessive_exploration` | 5+ consecutive glob/grep calls (>500 tokens) before taking action |
| warning | `oversized_skill` | Skill file loaded with more than 3,000 tokens at once |
| warning | `cat_on_large_file` | Using `cat` on a large file instead of grep/head/tail |
| warning | `skill_not_triggered` | Prompt matches skill description but skill was never loaded |
| info | `low_cache_rate` | API input tokens significantly exceed estimated content, suggesting poor cache utilization |
| info | `high_think_ratio` | Model generating 3x+ more text than tool calls -- too much explaining, not enough doing |

## How It Works

1. **Token counting** -- Uses `tiktoken` (cl100k_base) to count tokens in skill
   files, references, scripts, and captured API traffic.

2. **Proxy capture** -- `llm-interceptor` (lli) runs a local proxy that intercepts
   API requests/responses between the CLI tool (Claude, Aider, Cursor) and the LLM
   provider, recording full request/response pairs as structured trace files.

3. **Trace parsing** -- Trace files are parsed into structured conversation
   steps (system prompt, user message, tool calls, tool results, assistant
   responses) with per-step token counts.

4. **Pattern detection** -- Nine detector functions scan the step sequence for
   known waste patterns and emit issues with severity, token impact, and
   suggested fixes. All thresholds are configurable.

5. **Suggestion generation** -- Each issue is expanded into a detailed,
   actionable suggestion with estimated token and cost savings.

## Test Suite Format

You can define reusable prompt suites in JSON for repeatable benchmarking:

```json
[
  {
    "label": "csv-parser",
    "prompt": "Create a Python script that reads a CSV file and outputs summary statistics"
  },
  {
    "label": "rest-client",
    "prompt": "Write a Python REST API client with retry logic and error handling"
  }
]
```

See `examples/test-suite.json` for a complete example.

## Configuration

All pattern detection thresholds are configurable via `.skill-perf.toml`:

```bash
# Generate default config
skill-perf config --generate
```

This creates `.skill-perf.toml` with all thresholds:

```toml
[thresholds]
large_file_read_tokens = 2000
excessive_exploration_count = 5
excessive_exploration_min_tokens = 500
oversized_skill_tokens = 3000
cat_on_large_file_tokens = 500
high_think_ratio = 3.0
low_cache_rate_ratio = 2.0
```

Place this file in your project root. skill-perf auto-loads it, or pass
`--config path/to/config.toml` explicitly.

## Using with AI Coding Assistants

skill-perf includes a skill that teaches AI coding assistants (Claude Code,
Cursor, Aider) how to interpret diagnose/suggest output and generate specific,
context-aware SKILL.md fixes.

### Install the skill

```bash
# Install to your current project (workspace-level)
skill-perf init

# Or install globally for all projects
skill-perf init --global

# Overwrite existing installation
skill-perf init --force
```

**Workspace install** creates `.claude/skills/skill-perf.md` in your project --
the skill is auto-discovered by Claude Code for that project.

**Global install** creates `~/.claude/agents/skill-perf.md` -- available across
all your projects.

### Use the skill

In your AI coding session:

```bash
# 1. Run diagnosis on captured traces
skill-perf diagnose ./traces/

# 2. Ask the assistant to improve your skill based on the output
# The skill teaches it how to interpret results and write targeted fixes
```

The assistant will use actual file paths, step numbers, and token counts from
the trace to generate copy-paste-ready SKILL.md patches -- much more specific
than the static template suggestions.

## Development

```bash
git clone https://github.com/hystericcore/skill-perf.git
cd skill-perf
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [docs/development.md](docs/development.md) for the full development guide
including project structure, testing, adding new patterns, and cleanup.

## License

MIT
