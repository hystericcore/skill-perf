"""Trace parsing: read LLI JSONL captures into SessionAnalysis models."""

from skill_perf.parser.providers import detect_provider
from skill_perf.parser.trace_reader import parse_session

__all__ = ["detect_provider", "parse_session"]
