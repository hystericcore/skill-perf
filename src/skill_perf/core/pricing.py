"""Model pricing engine for LLM cost estimation.

Pricing data ported from reference script skill_estimator.py and
expanded with output pricing for full cost modelling.
"""

from __future__ import annotations

from pydantic import BaseModel


class ModelPricing(BaseModel):
    """Pricing information for a single LLM model."""

    model: str
    provider: str
    input_cost_per_m: float  # USD per 1 M input tokens
    output_cost_per_m: float  # USD per 1 M output tokens


# ---------------------------------------------------------------------------
# Pricing table  (model_name -> ModelPricing)
# ---------------------------------------------------------------------------

PRICING: dict[str, ModelPricing] = {
    # Anthropic Direct
    "claude-opus-4": ModelPricing(
        model="claude-opus-4",
        provider="anthropic",
        input_cost_per_m=15.00,
        output_cost_per_m=75.00,
    ),
    "claude-sonnet-4": ModelPricing(
        model="claude-sonnet-4",
        provider="anthropic",
        input_cost_per_m=3.00,
        output_cost_per_m=15.00,
    ),
    "claude-haiku-4.5": ModelPricing(
        model="claude-haiku-4.5",
        provider="anthropic",
        input_cost_per_m=0.80,
        output_cost_per_m=4.00,
    ),
    # AWS Bedrock (same Anthropic models, same pricing)
    "bedrock-claude-opus-4": ModelPricing(
        model="bedrock-claude-opus-4",
        provider="aws-bedrock",
        input_cost_per_m=15.00,
        output_cost_per_m=75.00,
    ),
    "bedrock-claude-sonnet-4": ModelPricing(
        model="bedrock-claude-sonnet-4",
        provider="aws-bedrock",
        input_cost_per_m=3.00,
        output_cost_per_m=15.00,
    ),
    "bedrock-claude-haiku-4.5": ModelPricing(
        model="bedrock-claude-haiku-4.5",
        provider="aws-bedrock",
        input_cost_per_m=0.80,
        output_cost_per_m=4.00,
    ),
    # OpenAI
    "gpt-4o": ModelPricing(
        model="gpt-4o",
        provider="openai",
        input_cost_per_m=2.50,
        output_cost_per_m=10.00,
    ),
    "gpt-4o-mini": ModelPricing(
        model="gpt-4o-mini",
        provider="openai",
        input_cost_per_m=0.15,
        output_cost_per_m=0.60,
    ),
    # Google
    "gemini-2.0-flash": ModelPricing(
        model="gemini-2.0-flash",
        provider="google",
        input_cost_per_m=0.10,
        output_cost_per_m=0.40,
    ),
    "gemini-2.5-pro": ModelPricing(
        model="gemini-2.5-pro",
        provider="google",
        input_cost_per_m=1.25,
        output_cost_per_m=10.00,
    ),
    # DeepSeek
    "deepseek-chat": ModelPricing(
        model="deepseek-chat",
        provider="deepseek",
        input_cost_per_m=0.27,
        output_cost_per_m=1.10,
    ),
    # Local (free)
    "ollama-any": ModelPricing(
        model="ollama-any",
        provider="local",
        input_cost_per_m=0.00,
        output_cost_per_m=0.00,
    ),
}


def estimate_cost(tokens: int, model: str, direction: str = "input") -> float:
    """Estimate cost in USD for a given token count and model.

    Args:
        tokens: Number of tokens.
        model: Model name (must match a key in ``PRICING``).
        direction: ``"input"`` or ``"output"``.

    Returns:
        Estimated cost in USD.  Returns ``0.0`` if the model is unknown.
    """
    pricing = PRICING.get(model)
    if pricing is None:
        return 0.0

    rate = pricing.input_cost_per_m if direction == "input" else pricing.output_cost_per_m
    return (tokens / 1_000_000) * rate


def get_all_costs(tokens: int) -> dict[str, float]:
    """Return input-direction cost estimate for every known model.

    Args:
        tokens: Number of input tokens.

    Returns:
        Mapping of model name to estimated cost in USD.
    """
    return {name: estimate_cost(tokens, name, "input") for name in PRICING}
