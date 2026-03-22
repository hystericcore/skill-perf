# CLI Reference

## skill-perf estimate

Offline skill analysis. No API calls, no traces needed.

```bash
skill-perf estimate <paths...> [--compare] [--json]
```

| Flag | Description |
|------|-------------|
| `paths` | One or more SKILL.md files or directories |
| `--compare` | Side-by-side comparison of multiple skill versions |
| `--json` | Output as JSON |

**Output includes:** Token counts per file, progressive disclosure levels (L1 metadata, L2 body, L3 references), size warnings, cost per call across providers.

## skill-perf diagnose

Analyze captured traces for waste patterns.

```bash
skill-perf diagnose <paths...> [--skill DIR] [--json] [--open] [--static] [--report PATH]
```

| Flag | Description |
|------|-------------|
| `paths` | One or more trace session directories |
| `--skill DIR` | Path to skill directory (enables script detection) |
| `--json` | Output as JSON |
| `--open` | Open interactive HTML treemap in browser |
| `--static` | Generate static HTML report |
| `--report PATH` | Output HTML report to specific path |

**Output includes:** Step-by-step breakdown, token distribution chart, diagnosed issues with severity, think/act ratio, waste summary.

## skill-perf suggest

Generate fix suggestions for diagnosed issues.

```bash
skill-perf suggest <paths...> [--json]
```

| Flag | Description |
|------|-------------|
| `paths` | One or more trace session directories |
| `--json` | Output as JSON |

**Output includes:** Per-issue fix with severity, step reference, suggestion text, estimated savings.

## skill-perf measure

Capture real token usage via proxy.

```bash
skill-perf measure [--prompt TEXT] [--suite FILE] [--cli TOOL] [--compare] [--diagnose] [--open]
```

| Flag | Description |
|------|-------------|
| `--prompt/-p TEXT` | Single prompt to run |
| `--suite FILE` | Test suite JSON file |
| `--cli TOOL` | CLI tool: claude, aider, cursor-cli (default: claude) |
| `--compare` | A/B comparison mode (requires --skill-a and --skill-b) |
| `--skill-a DIR` | Skill version A directory |
| `--skill-b DIR` | Skill version B directory |
| `--diagnose` | Auto-diagnose after capture |
| `--open` | Open HTML report |
| `--port NUM` | Proxy port (default: 9090) |
| `--output DIR` | Output directory (default: ./bench_results) |
| `--max-turns NUM` | Max conversation turns (default: 3) |
| `--timeout SECS` | Timeout per run (default: 120) |

**Requires:** `pip install skill-perf[capture]` for llm-interceptor proxy.

## skill-perf verify

Compare current run against baseline.

```bash
skill-perf verify --baseline DIR [--current DIR] [--json] [--open] [--report PATH]
```

| Flag | Description |
|------|-------------|
| `--baseline/-b DIR` | Path to baseline trace directory (required) |
| `--current/-c DIR` | Path to current trace directory |
| `--json` | Output as JSON |
| `--open` | Open side-by-side HTML report |
| `--report PATH` | Output report directory |

**Output includes:** Token/cost deltas, percentage improvement, resolved vs remaining issues.
