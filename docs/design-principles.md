# Design Principles: Lessons from webpack-bundle-analyzer

## Why webpack-bundle-analyzer works

It's the most popular webpack plugin (26M+ downloads/month) because of 5 design choices
that we should adopt for skill-perf:

---

## 1. VISUAL FIRST — "See it, don't read it"

**webpack:** Interactive zoomable treemap. You open a browser and immediately SEE which
module is eating your bundle. No reading logs. No parsing numbers. The biggest rectangle
IS the problem.

**skill-perf should adopt:**

Instead of terminal tables, generate an **interactive HTML treemap** of context consumption:

```
┌──────────────────────────────────────────────────────────┐
│ system_prompt (12,450 tokens)                            │
│ ┌────────────────────────┐┌─────────────────────────────┐│
│ │ tool_results           ││ skill_load                  ││
│ │ (8,500 tokens)         ││ (3,200 tokens)              ││
│ │ ┌──────────┐┌────────┐││ ┌───────────┐┌────────────┐ ││
│ │ │src/main  ││config  │││ │SKILL.md   ││references/ │ ││
│ │ │.py       ││.json   │││ │           ││project.md  │ ││
│ │ │(6,200)   ││(2,300) │││ │(2,100)    ││(1,100)     │ ││
│ │ └──────────┘└────────┘││ └───────────┘└────────────┘ ││
│ └────────────────────────┘└─────────────────────────────┘│
│ ┌─────────────┐┌──────┐                                  │
│ │ assistant   ││ user │                                  │
│ │ (2,100)     ││ (85) │                                  │
│ └─────────────┘└──────┘                                  │
└──────────────────────────────────────────────────────────┘
```

Open browser → biggest rectangle is the problem → click to zoom → see details.

**Implementation:**
- `skill-perf diagnose --open` → opens HTML report in browser (like webpack's `server` mode)
- `skill-perf diagnose --static` → generates standalone HTML file (for sharing/CI)
- `skill-perf diagnose --json` → raw data for programmatic use
- `skill-perf diagnose` (default) → rich terminal output for quick checks


## 2. MULTIPLE SIZE VIEWS — "Same data, different perspectives"

**webpack:** Toggle between stat / parsed / gzip sizes. Same module, 3 different
views of "how big is it really?"

**skill-perf should adopt:**

Three token views for context:

| View | webpack equivalent | What it shows |
|------|-------------------|---------------|
| **Raw tokens** | stat size | Token count as sent to API |
| **Effective tokens** | parsed size | Raw minus cache hits (what you actually pay for) |
| **Estimated cost** | gzip size | Dollar amount across different providers |

User toggles between views in the treemap. Same layout, different numbers.
"This skill_load is 3,200 raw tokens, but only 320 effective tokens because
it's cached" — that changes the optimization priority completely.


## 3. ZERO CONFIG TO START — "Just add the plugin"

**webpack:** Add 2 lines to config → run build → browser opens with report.
No configuration, no setup, no account.

**skill-perf should adopt:**

```bash
# Zero config: just point at trace files and see results
skill-perf diagnose ./traces/

# Zero config: just point at a skill and see static analysis
skill-perf estimate ./my-skill/

# One flag: capture + analyze in one command
skill-perf measure --prompt "Create a CSV parser" --open
```

No account. No API key. No config file. The first run should produce a visual
report within 30 seconds. If someone needs to read docs before seeing a result,
we've failed.


## 4. SEARCH & DRILL DOWN — "Find why THIS module is here"

**webpack:** Search bar filters the treemap. Click a module → see where it appears
across chunks. Red highlighting shows duplicates scattered across bundles.

**skill-perf should adopt:**

**Search by file path:** "Where does src/main.py appear in the context?"
→ Highlights all steps where that file was read/referenced
→ Shows: "Read at step 3 (6,200 tokens), referenced again at step 7 (duplicate)"

**Search by tool:** "Show me all Bash calls"
→ Highlights all bash execution steps
→ Summary: "4 bash calls, 2 were scripts (efficient), 2 were cat commands (wasteful)"

**Search by waste pattern:** "Show me all 🔴 critical issues"
→ Filters to only underperforming steps
→ Each one clickable → expands to show raw content + suggestion

**Click to drill down:**
- Click a block → zoom in to see sub-components
- system_prompt → zoom → see CLAUDE.md portion vs tools portion vs skill metadata
- tool_results → zoom → see individual file reads with sizes
- Click a waste marker → see the before/after suggestion inline


## 5. COMPARISON MODE — "Before vs after"

**webpack:** Not built-in, but the common workflow is: run analyzer before optimization,
screenshot, optimize, run again, compare visually. Statoscope (companion tool) adds
explicit diff support.

**skill-perf should adopt this as BUILT-IN:**

```bash
skill-perf verify --baseline ./results/run_v1/ --current ./results/run_v2/ --open
```

Opens a **side-by-side treemap**:

```
┌─── v1 (26,300 tokens) ────────┐  ┌─── v2 (15,500 tokens) ────────┐
│ ┌──────────────────────┐      │  │ ┌──────────────────────┐      │
│ │ system_prompt        │      │  │ │ system_prompt        │      │
│ │ (12,450)             │      │  │ │ (12,450)             │      │
│ ├──────────────────────┤      │  │ ├──────────────────────┤      │
│ │ tool_results ████████│      │  │ │ tool_results ██      │      │
│ │ (8,500) 🔴           │      │  │ │ (1,200) ✅          │      │
│ ├──────────────────────┤      │  │ ├──────────────────────┤      │
│ │ skill_load (3,200)   │      │  │ │ skill_load (800) ✅  │      │
│ ├──────────────────────┤      │  │ ├──────────────────────┤      │
│ │ assistant (2,100)    │      │  │ │ assistant (1,050) ✅ │      │
│ └──────────────────────┘      │  │ └──────────────────────┘      │
│                                │  │                                │
│ Waste: 10,800 (41%)           │  │ Waste: 200 (1.3%)             │
│ Issues: 🔴3 🟡2               │  │ Issues: 🟢1                   │
└────────────────────────────────┘  └────────────────────────────────┘

  Delta: -10,800 tokens (-41.1%) | -$0.032/call | 🔴3→✅0 resolved
```

This is the **verify** step of the improvement cycle, made visual.


---

## How this maps to our CLI

| webpack-bundle-analyzer | skill-perf equivalent |
|------------------------|----------------------|
| `BundleAnalyzerPlugin()` in config | `skill-perf measure --prompt "..."` |
| Treemap opens in browser | `--open` flag on any command |
| stat / parsed / gzip toggle | raw / effective / cost toggle |
| Search modules | Search by file, tool, or waste pattern |
| Click to zoom | Click to drill into step details |
| Statoscope (companion diff tool) | `skill-perf verify --baseline ... --current ...` |
| `--mode static` (HTML file) | `--static` flag for CI/sharing |
| `--mode json` (raw data) | `--json` flag for programmatic use |
| `generateStatsFile` | Trace capture (always saved) |


## Output modes (matching webpack)

```bash
# Server mode (default) — opens browser with interactive report
skill-perf diagnose ./traces/ --open

# Static mode — generates standalone HTML file
skill-perf diagnose ./traces/ --static --report report.html

# JSON mode — raw data for CI/programmatic use
skill-perf diagnose ./traces/ --json --report analysis.json

# Terminal mode — rich terminal output (quick check)
skill-perf diagnose ./traces/
```


## The README Screenshot

webpack-bundle-analyzer's README has ONE screenshot at the top — the treemap.
That's what sells it. Everyone immediately understands what it does.

skill-perf needs the same: ONE screenshot showing:
- Treemap with token blocks (biggest = worst)
- Red-highlighted waste blocks
- Sidebar with diagnosis + suggestion
- That's it. That's the pitch.


## Summary: What to adopt

| Principle | Action for skill-perf |
|-----------|----------------------|
| Visual first | Interactive HTML treemap of context usage |
| Multiple views | Raw / Effective / Cost toggle |
| Zero config | `skill-perf diagnose ./traces/` → browser opens |
| Search & drill | Find files, tools, waste patterns in the map |
| Built-in comparison | Side-by-side treemap for verify step |
| Static export | Standalone HTML for sharing/CI |
