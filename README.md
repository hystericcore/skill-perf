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
# 0. Scaffold a new skill
skill-perf create my-skill -d "Does something useful"

# 1. Estimate token footprint and validate format (no API call needed)
skill-perf estimate ./my-skill/

# 2. Snapshot before measuring so you can diff changes later
skill-perf measure --prompt "Create a CSV parser" \
    --skill ./my-skill/ --snapshot --diagnose

# 3. Diagnose captured traces for waste patterns
skill-perf diagnose ./bench_results/bench_20260325_010838/traces/

# 4. Get actionable fix suggestions
skill-perf suggest ./bench_results/bench_20260325_010838/traces/

# 5. Edit SKILL.md, then diff what changed
skill-perf diff ./my-skill/

# 6. Verify improvements against baseline
skill-perf verify --baseline ./v1/traces/ --current ./v2/traces/
```

## The Improvement Cycle

```
  Create/         Measure          Diagnose          Suggest          Verify
  Estimate
+-----------+   +-----------+    +-----------+    +-----------+    +-----------+
| Scaffold  |   | Capture   |--->| Find waste|--->| Get fixes |--->| Compare   |
| validate  |   | real token|    | patterns  |    | with token|    | before &  |
| & format  |   | usage     |    | & hotspots|    | savings   |    | after     |
+-----------+   +-----------+    +-----------+    +-----------+    +-----------+
                      ^           snapshot/diff                          |
                      +------------------------------------------------->+
                                       Iterate until lean
```

## Commands

### `skill-perf create`

Scaffold a new SKILL.md directory with valid structure and correct frontmatter.

```bash
skill-perf create my-skill -d "Analyze stocks and produce BUY/WAIT/AVOID recommendations"
```

Output:

```
Created skill directory: ./my-skill/
  my-skill/SKILL.md
  my-skill/references/.gitkeep
  my-skill/scripts/.gitkeep

Next: run `skill-perf estimate ./my-skill/` to validate.
```

---

### `skill-perf estimate`

Offline analysis. Validates format against the Anthropic skill spec (frontmatter,
required fields, name/description length limits), counts tokens at each
progressive-disclosure level, and estimates cost across providers.

```bash
# Analyze a skill directory
skill-perf estimate ./my-skill/

# Compare two versions side by side
skill-perf estimate ./v1/ ./v2/ --compare

# JSON output for CI
skill-perf estimate ./my-skill/ --json
```

Output:

```
──────────────────────────── Skill: analyze-stocks ─────────────────────────────

Level 1 -- Metadata (always loaded)
  description: 36 tokens  [under 100]

Level 2 -- SKILL.md body (on trigger)
  SKILL.md body: 2367 tokens (201 lines)  [under 5000]

  Total if fully loaded: 2,403 tokens
────────────────── Cost per call (skill loaded into context) ───────────────────
  claude-sonnet-4              $0.007209
  gpt-4o                       $0.006008
  gemini-2.0-flash             $0.000240
  ollama-any                   FREE
```

If validation errors exist they appear as red `ERROR:` lines before proceeding.

---

### `skill-perf measure`

Run a skill against one or more prompts and capture real token usage through a
local proxy. Defaults to `haiku` for fast, cheap iteration cycles.

```bash
# Single prompt with skill dir and auto-snapshot
skill-perf measure --prompt "Analyze AAPL" \
    --skill ./.agents/skills/analyze-stocks --snapshot

# Use a different CLI or model
skill-perf measure --prompt "Analyze AAPL" --cli gemini --model gemini-2.5-flash

# Run a test suite
skill-perf measure --suite ./examples/test-suite.json --skill ./my-skill/

# Capture and immediately diagnose
skill-perf measure --prompt "Analyze AAPL" --skill ./my-skill/ --diagnose

# A/B comparison of two skill versions
skill-perf measure --compare --skill-a ./v1/ --skill-b ./v2/ \
    --prompt "Analyze AAPL" --snapshot
```

Output:

```
Snapshot saved: ./.agents/skills/analyze-stocks/.snapshots/SKILL_20260325_010838.md
Run skill-perf diff ./.agents/skills/analyze-stocks after editing to see what changed.

skill-perf measure  output=./bench_results/bench_20260325_010838  model=haiku
Proxy started on port 9090
  Running: Analyze AAPL and give me a BUY/WAIT/AVOID recommendation...
Proxy stopped

                Measure Results
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Label  ┃ Exit Code ┃ Duration (ms) ┃ Status ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ single │         0 │         16726 │ OK     │
└────────┴───────────┴───────────────┴────────┘

single
  stdout: Here is my analysis of AAPL...

Traces saved to: ./bench_results/bench_20260325_010838/traces
Trace files:     2 (1.1 MB)
Runs completed:  1
Skill loaded:    yes
```

---

### `skill-perf diagnose`

Parse captured trace sessions and detect waste patterns.

```bash
skill-perf diagnose ./bench_results/bench_20260325_010838/traces/

# Include skill directory for script detection
skill-perf diagnose ./bench_results/.../traces/ --skill ./my-skill/

# Save HTML report
skill-perf diagnose ./bench_results/.../traces/ --report ./report.html

# JSON output
skill-perf diagnose ./bench_results/.../traces/ --json
```

Output:

```
─────────────────────────────── Session: traces ────────────────────────────────
  Model: claude-haiku-4-5-20251001
  API reported: in=18 out=599
  Steps: 7

Step-by-step breakdown:
  [  1] system_prompt             5,833 tokens
  [  2] user_message             13,867 tokens
  [  3] system_prompt             5,832 tokens
  [  4] user_message             13,867 tokens
  [  5] skill_load                   15 tokens
        Skill: analyze-stocks (AAPL)
  [  6] user_message                  6 tokens
  [  7] tool_result                   6 tokens

Token distribution:
 Category                    Tokens        %  Bar
 user_message                27,740    70.4%  █████████████████░░░░░░░░
 system_prompt               11,665    29.6%  ███████░░░░░░░░░░░░░░░░░░
 skill_load                      15     0.0%  ░░░░░░░░░░░░░░░░░░░░░░░░░
 tool_result                      6     0.0%  ░░░░░░░░░░░░░░░░░░░░░░░░░

  Think/act ratio: 0.00x

  No waste patterns detected.

  Estimated total: 39,426 tokens
```

When issues are found:

```
Diagnosed issues: 2 (~2,914 waste tokens, 28.1%)
  🟡 [warning] duplicate_read (step 13, +2,457 tokens over threshold)
      Duplicate read: 'src/main.py' read 4 times.
  🟡 [warning] large_file_read (step 11, +457 tokens over threshold)
      Large tool result: 2,457 tokens.
```

---

### `skill-perf suggest`

Generate actionable fix suggestions for every diagnosed issue. When no issues
are found, shows a threshold health table so you know the skill is genuinely clean.

```bash
skill-perf suggest ./bench_results/.../traces/

# JSON output
skill-perf suggest ./bench_results/.../traces/ --json
```

Output (no issues):

```
  ✓ No issues — all metrics within thresholds
  Session: traces (claude-haiku-4-5-20251001)

  Metric               Value    Threshold    Status
  skill body tokens       15        5,000      ✓
  think / act ratio    0.00x         3.0x      ✓
  cache rate ratio     0.00x         2.0x      ✓
```

Output (issues found):

```
  FIX 1 of 2: large_file_read (🟡 warning)
  ──────────────────────────────────────────────
  Step [10]: Large tool result: 2,457 tokens. (+457 tokens over threshold)
  Step [10]: Read on src/main.py (2,457 tokens)
╭──────────────────────────────────────────────────────────────────────────╮
│ File src/main.py loaded 2,457 tokens into context.                       │
│                                                                          │
│   Add to SKILL.md:                                                       │
│                                                                          │
│   ## Reading src/main.py                                                 │
│   Before reading this file:                                              │
│   1. Use `grep -n '<pattern>' src/main.py` to find the relevant section  │
│   2. Read only the matching line range                                   │
│   Never read the entire file.                                            │
╰──────────────────────────────────────────────────────────────────────────╯
  Estimated savings: ~457 tokens/call ($0.0014)
```

---

### `skill-perf snapshot` and `skill-perf diff`

Skill directories often live **outside any git repo** (`~/.claude/agents/`,
`.cursor/skills/`, `.agents/skills/`). These commands give you git-diff-style
version tracking without needing a repo.

```bash
# Save a snapshot before editing
skill-perf snapshot ~/.claude/agents/my-skill

# After editing, see exactly what changed
skill-perf diff ~/.claude/agents/my-skill

# List all saved snapshots
skill-perf diff ~/.claude/agents/my-skill --list

# Diff two specific snapshots
skill-perf diff ~/.claude/agents/my-skill \
    --from .snapshots/SKILL_20260101_120000.md \
    --to   .snapshots/SKILL_20260102_090000.md
```

`measure --snapshot` auto-snapshots before the run so the snapshot is always
tied to the exact SKILL.md version that was measured.

To store snapshots globally instead of inside each skill dir:

```bash
export SKILL_PERF_SNAPSHOT_DIR=~/.skill-perf/snapshots
```

---

### `skill-perf verify`

Re-run and confirm improvements against a baseline.

```bash
skill-perf verify --baseline ./v1/traces/ --current ./v2/traces/
```

Output:

```
  VERIFICATION
  ═══════════════════════════════════════════
  Baseline (v1):    29,149 tokens  |  ~$0.437
  Current  (v2):    25,853 tokens  |  ~$0.388
                ─────────────────────────────
  Improvement:   -3,296 tokens  | ~$-0.049  (-11.3%)

  Category                 Baseline    Current      Delta    Change
  ──────────────────────────────────────────────────────────────────
  system_prompt              17,044     17,057         +13     +0.1%
  user_message               10,238      8,582      -1,656    -16.2%
  tool_result                 1,775         82      -1,693    -95.4%
  skill_load                     92         36         -56    -60.9%

  Issues resolved:  🔴0 -> ✅0
  Issues remaining: none
  ═══════════════════════════════════════════
```

---

### `skill-perf config`

Show or generate threshold configuration.

```bash
skill-perf config
skill-perf config --generate   # writes .skill-perf.toml
```

Output:

```
Current thresholds:
  estimate_description_tokens: 100
  estimate_body_tokens: 5000
  estimate_single_ref_tokens: 5000
  estimate_total_tokens: 10000
  large_file_read_tokens: 2000
  excessive_exploration_count: 5
  excessive_exploration_min_tokens: 500
  oversized_skill_tokens: 5000
  cat_on_large_file_tokens: 500
  high_think_ratio: 3.0
  low_cache_rate_ratio: 2.0
```

---

## Waste Patterns

skill-perf detects 10 built-in waste patterns (all thresholds configurable via `.skill-perf.toml`):

| Severity | Pattern | Description |
|----------|---------|-------------|
| critical | `script_not_executed` | Skill has `scripts/` but model did work manually instead of running them |
| warning | `large_file_read` | Tool result exceeds 2,000 tokens — consider filtering or extracting relevant sections |
| warning | `duplicate_read` | Same file read more than once across turns |
| warning | `excessive_exploration` | 5+ consecutive glob/grep calls (>500 tokens) before taking action |
| warning | `oversized_skill` | Skill file loaded with more than 5,000 tokens at once |
| warning | `cat_on_large_file` | Using `cat` on a large file instead of grep/head/tail |
| warning | `skill_not_triggered` | Prompt matches skill description but skill was never loaded |
| info | `low_cache_rate` | API input tokens significantly exceed estimated content, suggesting poor cache utilisation |
| info | `high_think_ratio` | Model generating 3x+ more text than tool calls — too much explaining, not enough doing |
| info | `inline_code_generation` | Model wrote 1,000+ tokens of code inline that could be a bundled script |

## Supported CLI Tools

| `--cli` value | Tool | `--model` example |
|---|---|---|
| `claude` (default) | Claude Code | `haiku`, `claude-haiku-4-5`, `claude-sonnet-4-6` |
| `cursor` or `agent` | Cursor headless agent | `claude-sonnet-4-6`, `gpt-4o` |
| `gemini` | Gemini CLI | `gemini-2.5-flash`, `gemini-2.5-pro` |
| `aider` | Aider | n/a (aider manages its own model) |

Default model is `haiku` for fast, cheap iteration. Upgrade to sonnet/opus only for final verification.

## How It Works

1. **Token counting** — Uses `tiktoken` (cl100k_base) to count tokens in skill
   files, references, scripts, and captured API traffic.

2. **Proxy capture** — `llm-interceptor` runs a local proxy that intercepts
   API requests/responses between the CLI and the LLM provider, recording full
   request/response pairs as structured trace files.

3. **Trace parsing** — Trace files are parsed into structured conversation
   steps (system prompt, user message, tool calls, tool results, assistant
   responses) with per-step token counts.

4. **Pattern detection** — Ten detector functions scan the step sequence for
   known waste patterns and emit issues with severity, token impact, and
   suggested fixes. All thresholds are configurable.

5. **Suggestion generation** — Each issue is expanded into a detailed,
   actionable suggestion with estimated token and cost savings.

See [docs/thresholds.md](docs/thresholds.md) for threshold rationale and
official Anthropic guidelines.

## Test Suite Format

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

Pass with `skill-perf measure --suite ./test-suite.json`. See `examples/test-suite.json`.

## Configuration

```bash
skill-perf config --generate   # creates .skill-perf.toml
```

```toml
[thresholds]
estimate_body_tokens = 5000
estimate_total_tokens = 10000
large_file_read_tokens = 2000
excessive_exploration_count = 5
oversized_skill_tokens = 5000
cat_on_large_file_tokens = 500
high_think_ratio = 3.0
low_cache_rate_ratio = 2.0
```

## Using with AI Coding Assistants

skill-perf ships a skill that teaches AI assistants to interpret diagnose/suggest
output and generate targeted SKILL.md fixes.

```bash
skill-perf init           # workspace-level (.agents/skills/skill-perf/)
skill-perf init --global  # global (~/.claude/agents/skill-perf/)
```

Then in your AI session, run `skill-perf suggest` and ask the assistant to apply
the fixes. Use `skill-perf snapshot` before and `skill-perf diff` after to review
every change.

## Development

```bash
git clone https://github.com/hystericcore/skill-perf.git
cd skill-perf
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

See [docs/development.md](docs/development.md) for project structure, testing,
and adding new patterns.

## License

MIT
