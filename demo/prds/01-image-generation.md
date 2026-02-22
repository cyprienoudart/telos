# PRD 01 — AI Image Generation

## Overview

Generate three visually consistent PNG assets for the International Women's Day (IWD) campaign. These images are required by all downstream PRDs — no other work should begin until all three files exist and are verified.

## Subagent

`image-generator`

## Dependencies

None. This PRD executes first.

## Tech Stack

- CLI: `uv run python -m telos_agent.tools.image_gen "<prompt>" -o <output-path>`
- Model: `google/gemini-3-pro-image-preview` via OpenRouter (handled internally by the tool)
- Auth: `OPENROUTER_API_KEY` env var

## Acceptance Criteria

- [x] Verify the `OPENROUTER_API_KEY` environment variable is set; exit immediately with a clear error message if it is missing — do not attempt image generation without it
- [x] Create the `demo/site/assets/` directory if it does not already exist
- [x] Generate the IWD hero banner using the image_gen CLI with prompt: *"International Women's Day hero banner, elegant abstract design, 16:9 landscape, deep purple and rich gold color palette on dark background, geometric floral motifs, no text, professional luxury feel"* — save to `demo/site/assets/iwd-hero.png`
- [x] Generate the IWD social media image using the image_gen CLI with prompt: *"International Women's Day social graphic, 1:1 square format, bold purple and gold, celebratory confetti and abstract florals, empowering mood, no text, shareable professional aesthetic"* — save to `demo/site/assets/iwd-social.png`
- [x] Generate the IWD email header using the image_gen CLI with prompt: *"International Women's Day email header banner, wide horizontal format, soft purple gradient fading left to right, warm gold accent line at bottom, abstract floral watercolor details, no text, suitable as email masthead"* — save to `demo/site/assets/iwd-email-header.png`
- [x] Confirm `demo/site/assets/iwd-hero.png` exists and its file size is greater than zero bytes
- [x] Confirm `demo/site/assets/iwd-social.png` exists and its file size is greater than zero bytes
- [x] Confirm `demo/site/assets/iwd-email-header.png` exists and its file size is greater than zero bytes

## Definition of Done

All three PNG files are present in `demo/site/assets/`, each with a non-zero file size. A reviewer opening the files should see visually consistent IWD-themed imagery sharing the purple/gold palette. No placeholder or empty files. The `demo/emails/` directory is not modified by this PRD.
