"""Diagnosis engine — runs all waste-pattern detectors on a session."""

from __future__ import annotations

from collections.abc import Callable

from skill_perf.diagnosis.patterns import (
    detect_cat_on_large_file,
    detect_duplicate_reads,
    detect_excessive_exploration,
    detect_high_think_ratio,
    detect_large_file_read,
    detect_low_cache_rate,
    detect_oversized_skill,
    detect_script_not_executed,
    detect_skill_not_triggered,
)
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis
from skill_perf.models.step import ConversationStep

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "warning": 1, "info": 2}

StepDetector = Callable[[list[ConversationStep]], list[Issue]]
SessionDetector = Callable[[SessionAnalysis], list[Issue]]

# Detectors that operate on steps only
_STEP_DETECTORS: list[StepDetector] = [
    detect_large_file_read,
    detect_duplicate_reads,
    detect_excessive_exploration,
    detect_oversized_skill,
    detect_cat_on_large_file,
]

# Detectors that require the full session object
_SESSION_DETECTORS: list[SessionDetector] = [
    detect_low_cache_rate,
    detect_high_think_ratio,
]


def diagnose(
    session: SessionAnalysis,
    skill_dir: str | None = None,
) -> list[Issue]:
    """Run all pattern detectors and return issues sorted by severity then impact_tokens."""
    issues: list[Issue] = []

    # Detectors that need both steps and skill_dir
    issues.extend(detect_script_not_executed(session.steps, skill_dir=skill_dir))
    issues.extend(detect_skill_not_triggered(session.steps, skill_dir=skill_dir))

    # Step-level detectors
    for detector in _STEP_DETECTORS:
        issues.extend(detector(session.steps))

    # Session-level detectors
    for session_detector in _SESSION_DETECTORS:
        issues.extend(session_detector(session))

    # Sort: severity first (critical < warning < info), then by impact_tokens descending
    issues.sort(key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), -i.impact_tokens))

    return issues
