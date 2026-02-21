# PRD 01 — AI Image Generation

## Overview

Generate three visually consistent IWD-themed images using the `telos_agent.tools.image_gen` CLI tool (OpenRouter → Gemini 3 Pro Image). These images are a hard prerequisite for all downstream work: the landing page references `iwd-hero.png` and `iwd-social.png`, and the email tool embeds `iwd-email-header.png`.

**Agent:** `image-generator`
**Phase:** 1 (blocking — must complete before PRDs 02, 03, and 04 can begin)
**Depends on:** nothing

---

## Tech Stack

| Concern | Detail |
|---|---|
| Tool | `uv run python -m telos_agent.tools.image_gen` |
| Model | `google/gemini-3-pro-image-preview` (OpenRouter) |
| Auth | `OPENROUTER_API_KEY` env var (check `agent/.env` or shell) |
| Output dir | `demo/site/assets/` |
| Supported flags | `--aspect-ratio` (`1:1`, `16:9`, etc.), `--size` (`1K`, `2K`, `4K`), `-o` (output path) |

The tool creates parent directories automatically. It saves the response as a PNG at the path given by `-o`.

---

## Shared Style Prefix

**All three prompts must open with this exact string** to guarantee visual consistency:

```
modern flat illustration, purple #7B2D8B and gold #C9A84C palette, white background, clean professional design, International Women's Day 2026,
```

Append image-specific description after the comma.

---

## Image Specifications

| File | Aspect Ratio | Description suffix |
|---|---|---|
| `demo/site/assets/iwd-hero.png` | `16:9` | abstract hero banner celebrating women in business, bold geometric shapes, empowerment theme |
| `demo/site/assets/iwd-social.png` | `1:1` | shareable social media graphic, central female silhouette or symbol, March 8 date detail |
| `demo/site/assets/iwd-email-header.png` | `16:9` | warm congratulatory email header, soft gradient accents, celebratory floral or ribbon motif |

---

## Acceptance Criteria

- [ ] Confirm `OPENROUTER_API_KEY` is available in the environment (check `agent/.env` or run `echo $OPENROUTER_API_KEY`)
- [ ] Run `image_gen` for `iwd-hero.png` with `--aspect-ratio 16:9` and the shared style prefix
- [ ] Run `image_gen` for `iwd-social.png` with `--aspect-ratio 1:1` and the shared style prefix
- [ ] Run `image_gen` for `iwd-email-header.png` with `--aspect-ratio 16:9` and the shared style prefix
- [ ] Confirm `demo/site/assets/iwd-hero.png` exists and is non-zero bytes
- [ ] Confirm `demo/site/assets/iwd-social.png` exists and is non-zero bytes
- [ ] Confirm `demo/site/assets/iwd-email-header.png` exists and is non-zero bytes
- [ ] Visually inspect all three images (open or describe them) and confirm they share the purple/gold palette and professional style — re-generate any that look inconsistent before declaring done

---

## Error Handling

- If OpenRouter returns an error, retry once with a shorter, simpler prompt (remove the detailed description suffix, keep only the style prefix)
- If the API is unreachable after retry, create placeholder PNGs using any available method (e.g., a 1×1 purple pixel) so downstream tasks are not fully blocked — note this clearly in progress output
- Do not proceed to PRD 02/03 with missing image files; they are referenced by `<img>` tags and email embed

---

## Definition of Done

All three PNG files exist at their target paths, are visually consistent in palette and style, and have been visually confirmed before signaling completion to the orchestrator.
