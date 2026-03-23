# Development Guide

## Prerequisites

- Python 3.11+
- Git

## Getting Started

```bash
# Clone the repository
git clone https://github.com/hystericcore/skill-perf.git
cd skill-perf

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in development mode with all dev dependencies
pip install -e ".[dev]"

# Verify the installation
skill-perf --help
```

To also work on the proxy capture feature:

```bash
pip install -e ".[dev,capture]"
```

## Running Tests

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run a specific test file
pytest tests/test_models.py

# Run a specific test
pytest tests/test_models.py::test_conversation_step_basic

# Run tests with coverage (install pytest-cov first)
pip install pytest-cov
pytest --cov=skill_perf --cov-report=term-missing
```

## Linting and Type Checking

```bash
# Run the linter
ruff check src/ tests/

# Auto-fix lint issues
ruff check src/ tests/ --fix

# Run type checker
mypy src/
```

## Project Structure

```
src/skill_perf/
├── cli.py              # Typer CLI entry point (thin layer)
├── models/             # Pydantic data models
│   ├── step.py         #   ConversationStep
│   ├── diagnosis.py    #   Issue
│   ├── session.py      #   SessionAnalysis (computed fields)
│   ├── benchmark.py    #   BenchmarkResult
│   ├── comparison.py   #   Comparison
│   └── treemap.py      #   TreemapNode (recursive)
├── core/               # Shared utilities
│   ├── tokenizer.py    #   count_tokens(), content_to_text()
│   └── pricing.py      #   estimate_cost(), PRICING table
├── parser/             # Trace file parsing
│   ├── trace_reader.py #   parse_session() — main entry point
│   ├── providers.py    #   detect_provider() from URL
│   ├── classifier.py   #   classify_step() → step_type
│   ├── messages.py     #   parse_request(), parse_response_usage()
│   └── streaming.py    #   parse_sse_response()
├── diagnosis/          # Waste pattern detection
│   ├── patterns.py     #   8 detector functions
│   └── engine.py       #   diagnose() — runs all detectors
├── commands/           # CLI command implementations
│   ├── estimate.py     #   skill-perf estimate
│   ├── diagnose.py     #   skill-perf diagnose
│   ├── suggest.py      #   skill-perf suggest
│   ├── measure.py      #   skill-perf measure
│   └── verify.py       #   skill-perf verify
├── suggestion/         # Fix suggestion generation
│   ├── templates.py    #   TEMPLATES dict (8 patterns)
│   └── generator.py    #   generate_suggestion()
├── capture/            # Proxy + CLI orchestration
│   ├── proxy.py        #   ProxyManager (lli lifecycle)
│   ├── runner.py       #   CLIRunner (claude, aider, cursor)
│   └── suite.py        #   load_suite() from JSON
└── report/             # HTML treemap visualization
    ├── treemap.py      #   build_treemap()
    ├── html.py         #   generate_html_report()
    └── server.py       #   serve_report()
```

## Test Fixtures

Test fixtures live in `tests/fixtures/` and match the real `llm-interceptor` (lli) output format:

- `session_01/split_output/` — lli split format (after `lli merge` + `lli split`). Contains intentional waste patterns: duplicate reads, large file reads, cat on large files.
- `session_02/` — lli native JSONL format with `response_chunk` streaming entries.
- `session_03/` — lli native JSONL with waste patterns: excessive exploration, oversized skill, high think/act ratio.
- `sample-skill/` — example SKILL.md with references/ and scripts/ for estimate command tests.

## Adding a New Waste Pattern

1. Add the detector function in `src/skill_perf/diagnosis/patterns.py`:
   ```python
   def detect_my_pattern(steps: list[ConversationStep]) -> list[Issue]:
       issues = []
       # detection logic
       return issues
   ```

2. Register it in `src/skill_perf/diagnosis/engine.py`:
   ```python
   ALL_PATTERNS = [..., detect_my_pattern]
   ```

3. Add a suggestion template in `src/skill_perf/suggestion/templates.py`:
   ```python
   TEMPLATES["my_pattern"] = "Add to SKILL.md:\n..."
   ```

4. Add tests in `tests/test_diagnosis.py` (positive and negative cases).

5. Create or update a fixture in `tests/fixtures/` that triggers the pattern.

## Adding a New LLM Provider

1. Add the domain mapping in `src/skill_perf/parser/providers.py`
2. Add pricing in `src/skill_perf/core/pricing.py`
3. If the response format differs, add extraction logic in `src/skill_perf/parser/messages.py`

## Cleanup

```bash
# Remove build artifacts
rm -rf dist/ build/ *.egg-info/

# Remove Python cache files
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete 2>/dev/null

# Remove test/lint caches
rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/

# Remove the virtual environment (to start fresh)
rm -rf .venv/

# Remove benchmark results (captured traces)
rm -rf bench_results/
```

## Building for Distribution

```bash
pip install build
python -m build
```

This creates `dist/skill_perf-0.1.0.tar.gz` and `dist/skill_perf-0.1.0-py3-none-any.whl`.
