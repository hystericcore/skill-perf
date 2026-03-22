"""Tests for skill_perf.core.pricing."""

from skill_perf.core.pricing import PRICING, estimate_cost, get_all_costs


def test_estimate_cost_known_model():
    """estimate_cost returns correct value for a known model (input)."""
    # claude-sonnet-4: $3 per 1M input tokens
    cost = estimate_cost(1_000_000, "claude-sonnet-4", "input")
    assert cost == 3.00


def test_estimate_cost_unknown_model():
    """estimate_cost returns 0.0 for an unknown model."""
    assert estimate_cost(1_000_000, "unknown-model") == 0.0


def test_estimate_cost_input_direction():
    """estimate_cost works for input direction."""
    cost = estimate_cost(500_000, "gpt-4o", "input")
    assert abs(cost - 1.25) < 1e-9


def test_estimate_cost_output_direction():
    """estimate_cost works for output direction."""
    # claude-opus-4: $75 per 1M output tokens
    cost = estimate_cost(1_000_000, "claude-opus-4", "output")
    assert cost == 75.00


def test_get_all_costs_returns_all_models():
    """get_all_costs returns a dict with all known models."""
    costs = get_all_costs(1_000_000)
    assert set(costs.keys()) == set(PRICING.keys())


def test_all_pricing_non_negative():
    """All pricing entries have non-negative values."""
    for name, pricing in PRICING.items():
        assert pricing.input_cost_per_m >= 0, f"{name} input cost is negative"
        assert pricing.output_cost_per_m >= 0, f"{name} output cost is negative"


def test_ollama_pricing_is_zero():
    """Ollama (local) pricing is $0 for both input and output."""
    ollama = PRICING["ollama-any"]
    assert ollama.input_cost_per_m == 0.0
    assert ollama.output_cost_per_m == 0.0


def test_estimate_cost_zero_tokens():
    """estimate_cost returns 0 for zero tokens."""
    assert estimate_cost(0, "claude-sonnet-4") == 0.0


def test_bedrock_matches_anthropic():
    """AWS Bedrock pricing matches Anthropic direct pricing."""
    for suffix in ("claude-opus-4", "claude-sonnet-4", "claude-haiku-4.5"):
        direct = PRICING[suffix]
        bedrock = PRICING[f"bedrock-{suffix}"]
        assert direct.input_cost_per_m == bedrock.input_cost_per_m
        assert direct.output_cost_per_m == bedrock.output_cost_per_m
