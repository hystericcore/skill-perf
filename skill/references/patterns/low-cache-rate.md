# low_cache_rate (info)

**What:** API input tokens significantly exceed estimated content tokens, suggesting poor prompt cache utilization.

**Detection:** `api_input_tokens > 2 * total_estimated_tokens`.

**How to fix:** This is about prompt structure, not SKILL.md content:

1. Keep the system prompt stable across calls (don't inject timestamps or random IDs)
2. Place frequently-changing content at the END of messages
3. Use consistent ordering for skill files and references
4. If using multiple skills, load them in the same order each time

**Note:** Cache rate depends on the provider and model. Some providers don't support prompt caching.
