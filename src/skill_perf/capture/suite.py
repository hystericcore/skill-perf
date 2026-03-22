"""Load test suite definitions from JSON files."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class BenchCase:
    """A single test case in a benchmark suite."""

    label: str
    prompt: str


def load_suite(path: str) -> list[BenchCase]:
    """Load test suite from JSON file.

    Expected format::

        [
            {"label": "csv-parser", "prompt": "Create a Python CSV parser"},
            {"label": "rest-client", "prompt": "Write a REST API client"}
        ]
    """
    with open(path) as f:
        data = json.load(f)
    return [BenchCase(label=item["label"], prompt=item["prompt"]) for item in data]
