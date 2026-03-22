# oversized_skill (warning)

**What:** A skill file loaded into context exceeds 3,000 tokens.

**Detection:** Any step with `step_type == "skill_load"` and `token_count > 3000`.

**How to fix:** Split the skill file:

1. Keep SKILL.md body under 2,000 tokens (high-level instructions only)
2. Move detailed content to `references/`:
   - API details -> `references/api-guide.md`
   - Examples -> `references/examples.md`
   - Data formats -> `references/data-formats.md`
3. In SKILL.md, reference them: "See references/api-guide.md for API details"

The model loads references on demand, so they don't cost tokens unless needed.

**Estimated savings:** `token_count - 2000` per call where the reference isn't needed.
