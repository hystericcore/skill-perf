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

### Skill structure (estimate command)

| Threshold | Default | Reasoning |
|-----------|---------|-----------|
| `LIMIT_DESCRIPTION_TOKENS` | 100 | ~350 chars. Official max is 1,024 chars per skill, but all descriptions share 2% of context. Keeping short leaves room for more skills. |
| `LIMIT_BODY_TOKENS` | 5,000 | Official: "under 5,000 tokens" for Level 2 content. |
| `LIMIT_SINGLE_REF_TOKENS` | 5,000 | No official limit. Matches body limit as a reasonable cap per file. |
| `LIMIT_TOTAL_TOKENS` | 10,000 | No official limit. Heuristic for total skill footprint. |

### Waste patterns (diagnose command)

These thresholds have no official Anthropic guidance — they're heuristics from observed real-world usage patterns.

| Threshold | Default | Reasoning |
|-----------|---------|-----------|
| `large_file_read_tokens` | 2,000 | From reference implementation. A 2K-token file read is large enough to justify using grep/head first. |
| `excessive_exploration_count` | 5 | Design spec. 5+ consecutive searches suggests the model doesn't know where to look. |
| `excessive_exploration_min_tokens` | 500 | Avoids flagging cheap grep/glob runs (<500 tokens is negligible). |
| `oversized_skill_tokens` | 5,000 | Aligned with official "under 5,000 tokens" for SKILL.md body. |
| `cat_on_large_file_tokens` | 500 | From reference implementation. `cat` on a 500+ token file should use grep instead. |
| `high_think_ratio` | 3.0 | From reference implementation. 3x more assistant text than tool usage suggests over-explaining. |
| `low_cache_rate_ratio` | 2.0 | Design spec. If API reports 2x more input tokens than estimated, caching may be underutilized. |

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
