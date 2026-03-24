# Threshold Rationale

All skill-perf thresholds are configurable via `.skill-perf.toml`. This document explains where the default values come from.

## Official Anthropic guidelines

Sources:
- [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Skills Best Practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Claude Code Skills Docs](https://code.claude.com/docs/en/skills)
- [Equipping Agents for the Real World](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills)

### Skill structure limits

| Constraint | Official value | Source |
|-----------|---------------|--------|
| Skill name | 64 characters max | Skills overview |
| Skill description | 1,024 characters max, non-empty | Skills overview |
| Description budget | 2% of context window (fallback: 16,000 chars) shared across ALL skills | Claude Code docs |
| Level 1 metadata | ~100 tokens per skill | Skills overview |
| Level 2 SKILL.md body | Under 5,000 tokens | Skills overview |
| Level 3 resources | Effectively unlimited | Skills overview |

### Description budget math

The 2% budget means all skill descriptions share a limited pool:

```
Context window: 200K tokens → 2% = ~4,000 characters for all descriptions
Fallback budget: 16,000 characters

With 16,000 char budget:
  10 skills × 1,600 chars each = budget
  50 skills × 320 chars each   = budget
  200 skills × 80 chars each   = budget
```

This is why we warn at 100 tokens (~350 chars) for descriptions — a single large description eats into the shared budget. Run `/context` in Claude Code to check if skills are being excluded.

Override: set `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable.

## Default thresholds

### Format validation (estimate command)

Hard Anthropic spec limits — platform-enforced, not configurable:

| Check | Limit | Source |
|-------|-------|--------|
| YAML frontmatter | Required (`---` delimiters) | [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| `name` field | Required, max 64 chars | [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| `description` field | Required, max 1,024 chars | [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) |
| Body content | Must not be empty | Practical — a skill with no instructions is unusable |

### Skill structure (estimate command)

Configurable token thresholds (soft warnings, tunable via `.skill-perf.toml`):

| Threshold | Default | Reasoning |
|-----------|---------|-----------|
| `LIMIT_DESCRIPTION_TOKENS` | 100 | ~350 chars. Official max is 1,024 chars per skill, but all descriptions share 2% of context. Keeping short leaves room for more skills. |
| `LIMIT_BODY_TOKENS` | 5,000 | Official: "under 5,000 tokens" for Level 2 content. |
| `LIMIT_SINGLE_REF_TOKENS` | 5,000 | No official limit. Matches body limit as a reasonable cap per file. |
| `LIMIT_TOTAL_TOKENS` | 10,000 | No official limit. Heuristic for total skill footprint. |

### Waste patterns (diagnose command)

Each pattern is grounded in official Anthropic guidance or observed real-world usage.

#### `script_not_executed` (critical)

Skill has `scripts/` but the model did work manually instead of running them.

- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — "Deterministic operations (sorting, PDF parsing) should use pre-written Python scripts" for "consistency and repeatability"
- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "Low freedom" tasks should use "specific scripts, few or no parameters"
- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — "When Claude runs scripts, the script's code never loads into the context window. Only the output consumes tokens."
- **Threshold:** No token threshold — fires when scripts exist but none were executed

#### `large_file_read` (warning)

Tool result exceeds threshold — entire file loaded into context.

- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — Progressive disclosure principle: "Claude reads only the files needed for each specific task"
- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "The context window is a public good. Your Skill shares the context window with everything else Claude needs to know"
- **Threshold:** `large_file_read_tokens = 2000` — heuristic from reference implementation

#### `duplicate_read` (warning)

Same file read multiple times across turns.

- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — "Claude loads this metadata at startup" and reads files "only when referenced" — re-reading is redundant context cost
- **Threshold:** No token threshold — fires on any duplicate file path

#### `excessive_exploration` (warning)

5+ consecutive glob/grep calls before taking action.

- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — Skills should provide "context Claude doesn't already have" to avoid exploration
- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — Use references for project structure so Claude doesn't need to explore
- **Threshold:** `excessive_exploration_count = 5`, `excessive_exploration_min_tokens = 500`

#### `oversized_skill` (warning)

Skill file loaded with more than threshold tokens.

- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — Level 2 content should be "Under 5k tokens"
- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — "When SKILL.md becomes unwieldy, split into separate files. Authors should segregate mutually exclusive contexts."
- **Threshold:** `oversized_skill_tokens = 5000` — aligned with official "under 5k"

#### `cat_on_large_file` (warning)

Using `cat` via Bash to read entire files into context.

- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — "Efficient script execution: the script's code never loads into the context window. Only the output consumes tokens."
- **Threshold:** `cat_on_large_file_tokens = 500` — heuristic from reference implementation

#### `low_cache_rate` (info)

API input tokens significantly exceed estimated content.

- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "The context window is a public good" — poor caching means re-processing tokens unnecessarily
- **Threshold:** `low_cache_rate_ratio = 2.0` — if API reports 2x more than estimated, caching is likely underutilized

#### `high_think_ratio` (info)

Model generating 3x+ more text than tool calls.

- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — "Code execution" should handle deterministic operations, not token generation
- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — Concise instructions: "Does this paragraph justify its token cost?"
- **Threshold:** `high_think_ratio = 3.0` — heuristic from reference implementation

#### `skill_not_triggered` (warning)

Prompt matches skill description but skill was never loaded.

- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — "Name/Description Optimization: These metadata fields drive triggering behavior — critical tuning points"
- **Source:** [Best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — "The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills"
- **Source:** [Claude Code docs](https://code.claude.com/docs/en/skills) — "Skill descriptions are loaded into context so Claude knows what's available"
- **Threshold:** Keyword matching between prompt and description (2+ keyword overlap)

#### `inline_code_generation` (info)

Model wrote significant code inline that could be a bundled script.

- **Source:** [Blog post](https://claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills) — "Deterministic operations (sorting, PDF parsing) should use pre-written Python scripts" for "consistency and repeatability"
- **Source:** [Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — "When Claude runs scripts, the script's code never loads into the context window. Only the output consumes tokens."
- **Relationship:** This pattern suggests creating a script. Once created, `script_not_executed` enforces using it. They work as a pipeline: detect opportunity → create script → enforce usage.
- **Threshold:** 1,000+ tokens in an assistant_response with code markers (`def `, `import `, `class `, `` ``` ``, etc.)

## Customizing thresholds

```bash
# Generate default config
skill-perf config --generate

# Edit .skill-perf.toml
# Then run diagnose — it auto-loads from project root
skill-perf diagnose ./traces/

# Or specify explicitly
skill-perf diagnose --config custom.toml ./traces/
```
