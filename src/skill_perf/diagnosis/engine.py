"""Diagnosis engine — runs all waste-pattern detectors on a session."""


from skill_perf.core.config import ThresholdConfig
from skill_perf.diagnosis.patterns import (
    detect_cat_on_large_file,
    detect_duplicate_reads,
    detect_excessive_exploration,
    detect_high_think_ratio,
    detect_inline_code_generation,
    detect_large_file_read,
    detect_low_cache_rate,
    detect_oversized_skill,
    detect_script_not_executed,
    detect_skill_not_triggered,
)
from skill_perf.models.diagnosis import Issue
from skill_perf.models.session import SessionAnalysis

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "warning": 1, "info": 2}


def diagnose(
    session: SessionAnalysis,
    skill_dir: str | None = None,
    config: ThresholdConfig | None = None,
) -> list[Issue]:
    """Run all pattern detectors and return issues sorted by severity."""
    cfg = config or ThresholdConfig()
    issues: list[Issue] = []

    # Detectors that need skill_dir
    issues.extend(detect_script_not_executed(session.steps, skill_dir=skill_dir))
    issues.extend(detect_skill_not_triggered(session.steps, skill_dir=skill_dir))

    # Step-level detectors (configurable thresholds)
    issues.extend(detect_large_file_read(session.steps, config=cfg))
    issues.extend(detect_duplicate_reads(session.steps))
    issues.extend(detect_excessive_exploration(session.steps, config=cfg))
    issues.extend(detect_oversized_skill(session.steps, config=cfg))
    issues.extend(detect_cat_on_large_file(session.steps, config=cfg))
    issues.extend(detect_inline_code_generation(session.steps, config=cfg))

    # Session-level detectors (configurable thresholds)
    issues.extend(detect_low_cache_rate(session, config=cfg))
    issues.extend(detect_high_think_ratio(session, config=cfg))

    # Sort: severity first, then by impact_tokens descending
    issues.sort(
        key=lambda i: (SEVERITY_ORDER.get(i.severity, 9), -i.impact_tokens)
    )

    return issues
