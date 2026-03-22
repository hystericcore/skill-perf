# high_think_ratio (info)

**What:** The model is generating 3x more text than it spends on tool calls -- lots of explaining, little doing.

**Detection:** `think_act_ratio > 3.0` where ratio = assistant_response_tokens / (tool_call_tokens + tool_result_tokens).

**How to fix:**

```markdown
## Execution style
Be concise. Prefer tool calls over explanations:
- Do NOT explain what you're about to do -- just do it
- Do NOT narrate each step -- show results instead
- Use scripts and tools directly rather than writing code inline
- Keep responses under 3 sentences between tool calls
```

**Estimated savings:** Depends on output token cost. Reducing output by 50% can save significant cost on models with expensive output tokens.
