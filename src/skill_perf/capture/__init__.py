"""Capture module — proxy management, CLI execution, and test suites."""

from skill_perf.capture.proxy import ProxyManager
from skill_perf.capture.runner import CLIRunner, RunResult
from skill_perf.capture.suite import BenchCase, load_suite

__all__ = [
    "CLIRunner",
    "ProxyManager",
    "RunResult",
    "BenchCase",
    "load_suite",
]
