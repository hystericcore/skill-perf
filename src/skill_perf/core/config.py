"""Configuration for skill-perf thresholds and settings."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel

CONFIG_FILENAME = ".skill-perf.toml"


class ThresholdConfig(BaseModel):
    """Configurable thresholds for waste pattern detection."""

    # large_file_read: tool result token count above this triggers the pattern
    large_file_read_tokens: int = 2000

    # excessive_exploration: consecutive search calls before action
    excessive_exploration_count: int = 5

    # excessive_exploration: minimum total tokens to flag (skip cheap runs)
    excessive_exploration_min_tokens: int = 500

    # oversized_skill: skill file token count above this triggers the pattern
    oversized_skill_tokens: int = 3000

    # cat_on_large_file: bash cat token count above this triggers the pattern
    cat_on_large_file_tokens: int = 500

    # high_think_ratio: assistant/tool ratio above this triggers the pattern
    high_think_ratio: float = 3.0

    # low_cache_rate: api_input/estimated ratio above this triggers the pattern
    low_cache_rate_ratio: float = 2.0


def load_config(config_path: str | None = None) -> ThresholdConfig:
    """Load configuration from a TOML file.

    Search order:
    1. Explicit ``config_path`` if provided
    2. ``.skill-perf.toml`` in the current directory
    3. Fall back to defaults
    """
    if config_path and os.path.isfile(config_path):
        return _parse_toml(config_path)

    default_path = os.path.join(os.getcwd(), CONFIG_FILENAME)
    if os.path.isfile(default_path):
        return _parse_toml(default_path)

    return ThresholdConfig()


def _parse_toml(path: str) -> ThresholdConfig:
    """Parse a TOML file into ThresholdConfig."""
    import tomllib

    with open(path, "rb") as f:
        data = f.read()

    parsed: dict[str, Any] = tomllib.loads(data.decode())

    # Look for [thresholds] section
    thresholds = parsed.get("thresholds", {})
    return ThresholdConfig(**thresholds)


def generate_default_config() -> str:
    """Generate a default .skill-perf.toml config file content."""
    defaults = ThresholdConfig()
    return f"""# skill-perf configuration
# Place this file as .skill-perf.toml in your project root

[thresholds]
# large_file_read: flag tool results above this token count
large_file_read_tokens = {defaults.large_file_read_tokens}

# excessive_exploration: flag after this many consecutive search calls
excessive_exploration_count = {defaults.excessive_exploration_count}

# excessive_exploration: skip if total tokens below this
excessive_exploration_min_tokens = {defaults.excessive_exploration_min_tokens}

# oversized_skill: flag skill files above this token count
oversized_skill_tokens = {defaults.oversized_skill_tokens}

# cat_on_large_file: flag bash cat above this token count
cat_on_large_file_tokens = {defaults.cat_on_large_file_tokens}

# high_think_ratio: flag when assistant/tool ratio exceeds this
high_think_ratio = {defaults.high_think_ratio}

# low_cache_rate: flag when api_input/estimated ratio exceeds this
low_cache_rate_ratio = {defaults.low_cache_rate_ratio}
"""
