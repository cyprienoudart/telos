"""Image generation via OpenRouter API (Gemini 3 Pro Image).

Standalone CLI tool that Claude Code subagents invoke via bash.
Saves generated images to disk so the agent can visually inspect them.

Usage:
    uv run python -m telos_agent.tools.image_gen "A sunset over mountains" -o sunset.png
    uv run python -m telos_agent.tools.image_gen "Logo for a tech startup" -o logo.png --aspect-ratio 1:1 --size 2K
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_MODEL = "google/gemini-3-pro-image-preview"
API_URL = "https://openrouter.ai/api/v1/chat/completions"


def generate_image(
    prompt: str,
    output_path: str,
    model: str = DEFAULT_MODEL,
    aspect_ratio: str | None = None,
    size: str | None = None,
    input_image: str | None = None,
) -> dict:
    """Generate an image via OpenRouter and save to disk.

    Args:
        prompt: Text description of the image to generate.
        output_path: Where to save the PNG file.
        model: OpenRouter model slug.
        aspect_ratio: e.g. "1:1", "16:9", "4:3".
        size: "1K", "2K", or "4K".
        input_image: Optional path to an input image for editing.

    Returns:
        Dict with keys: path, text_response, model.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. Add it to agent/.env or export it."
        )

    # Build message content
    content: list | str
    if input_image:
        img_path = Path(input_image)
        if not img_path.exists():
            raise FileNotFoundError(f"Input image not found: {input_image}")
        b64 = base64.b64encode(img_path.read_bytes()).decode()
        mime = "image/png" if img_path.suffix == ".png" else "image/jpeg"
        content = [
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    body: dict = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "modalities": ["image", "text"],
    }

    image_config: dict = {}
    if aspect_ratio:
        image_config["aspect_ratio"] = aspect_ratio
    if size:
        image_config["image_size"] = size
    if image_config:
        body["image_config"] = image_config

    response = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=180.0,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter API error {response.status_code}: {response.text}"
        )

    result = response.json()
    message = result["choices"][0]["message"]

    images = message.get("images", [])
    if not images:
        raise ValueError(
            f"No image in response. Text response: {message.get('content', '')}"
        )

    # Decode and save the first image
    img_url = images[0]["image_url"]["url"]
    b64_data = img_url.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_data)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(img_bytes)

    return {
        "path": str(out.resolve()),
        "text_response": message.get("content", ""),
        "model": model,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate images via OpenRouter (Gemini 3 Pro Image)",
    )
    parser.add_argument("prompt", help="Text description of the image to generate")
    parser.add_argument(
        "-o", "--output", required=True, help="Output file path (PNG)"
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help=f"Model slug (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--aspect-ratio",
        choices=["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
        help="Aspect ratio for the generated image",
    )
    parser.add_argument(
        "--size", choices=["1K", "2K", "4K"], help="Image resolution (default: 1K)"
    )
    parser.add_argument(
        "--input-image", help="Path to input image for editing/transformation"
    )

    args = parser.parse_args()

    try:
        result = generate_image(
            prompt=args.prompt,
            output_path=args.output,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            size=args.size,
            input_image=args.input_image,
        )
        print(f"Image saved: {result['path']}")
        if result["text_response"]:
            print(f"Model response: {result['text_response']}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
