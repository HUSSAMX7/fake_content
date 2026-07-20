"""Generate PNG figures for ContentBlock image entries via OpenRouter (Nano Banana)."""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path

import httpx
from PIL import Image

from schemas import ContentBlock

logger = logging.getLogger(__name__)

MAX_IMAGES_PER_DOCUMENT = 8
DEFAULT_IMAGE_MODEL = "google/gemini-3.1-flash-lite-image"
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_RESOLUTION = "1K"
OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"

_STYLE_PREFIX = (
    "Professional technical illustration for a formal Saudi government proposal. "
    "Clean flat diagram style, light background, clear boxes and arrows, "
    "no photorealistic people, no logos, no watermarks, no decorative clutter. "
    "Use official Arabic labels from the prompt for stage/axis names; "
    "do not translate those names into English. "
)


def _image_model() -> str:
    return (
        os.getenv("OPENROUTER_IMAGE_MODEL", DEFAULT_IMAGE_MODEL).strip()
        or DEFAULT_IMAGE_MODEL
    )


def _api_key() -> str:
    key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return key


def _decode_image_payload(raw: str) -> bytes:
    payload = raw.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    return base64.b64decode(payload)


def _write_as_png(image_bytes: bytes, destination: Path) -> None:
    """Normalize JPEG/WebP/etc. from providers into a real PNG file."""

    with Image.open(io.BytesIO(image_bytes)) as image:
        image.load()
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            converted = image.convert("RGBA")
        else:
            converted = image.convert("RGB")
        converted.save(destination, format="PNG")
    if not destination.is_file() or destination.stat().st_size < 32:
        raise RuntimeError("Normalized PNG was empty")
    with destination.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise RuntimeError("Normalized file is not a valid PNG")


def _generate_png(prompt: str, destination: Path) -> None:
    full_prompt = f"{_STYLE_PREFIX}{prompt.strip()}"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _image_model(),
        "prompt": full_prompt,
        "resolution": DEFAULT_RESOLUTION,
        "aspect_ratio": DEFAULT_ASPECT_RATIO,
        "output_format": "png",
        "n": 1,
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(OPENROUTER_IMAGES_URL, headers=headers, json=payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = response.text[:500]
            raise RuntimeError(
                f"OpenRouter image generation failed ({response.status_code}): {detail}"
            ) from exc
        result = response.json()

    data = result.get("data") or []
    if not data:
        raise RuntimeError("OpenRouter image API returned no data")
    item = data[0]
    raw = item.get("b64_json")
    if not raw:
        raise RuntimeError("OpenRouter image API response missing b64_json")
    media_type = (item.get("media_type") or "").lower()
    image_bytes = _decode_image_payload(raw)
    try:
        _write_as_png(image_bytes, destination)
    except Exception as exc:
        raise RuntimeError(
            f"Could not normalize provider image to PNG (media_type={media_type!r})"
        ) from exc


def _materialize_image_block(block: ContentBlock, destination: Path) -> ContentBlock | None:
    prompt = (block.image_prompt or "").strip()
    caption = block.text.strip()
    if not prompt:
        if caption:
            return ContentBlock(type="paragraph", text=caption)
        return None
    try:
        _generate_png(prompt, destination)
    except Exception:
        logger.exception("Image generation failed; keeping caption only if present")
        if caption:
            return ContentBlock(type="paragraph", text=caption)
        return None
    return ContentBlock(
        type="image",
        text=caption or "شكل توضيحي",
        image_prompt=prompt,
        image_path=str(destination),
    )


def generate_images_for_replacements(
    replacements: dict[int, list[ContentBlock]],
    work_dir: Path,
) -> dict[int, list[ContentBlock]]:
    """Generate PNGs for image blocks into ``work_dir``. Soft-fail per image."""

    work_dir.mkdir(parents=True, exist_ok=True)
    generated = 0
    updated: dict[int, list[ContentBlock]] = {}

    for span_index, blocks in replacements.items():
        new_blocks: list[ContentBlock] = []
        for block in blocks:
            if block.type != "image":
                new_blocks.append(block)
                continue
            # Pre-rendered PNGs already have image_path.
            if (block.image_path or "").strip():
                new_blocks.append(block)
                continue
            if generated >= MAX_IMAGES_PER_DOCUMENT:
                logger.warning(
                    "Image limit (%s) reached; demoting remaining image blocks",
                    MAX_IMAGES_PER_DOCUMENT,
                )
                if block.text.strip():
                    new_blocks.append(ContentBlock(type="paragraph", text=block.text.strip()))
                continue
            destination = work_dir / f"generated_{span_index}_{generated}.png"
            materialized = _materialize_image_block(block, destination)
            if materialized is None:
                continue
            if materialized.type == "image":
                generated += 1
            new_blocks.append(materialized)
        if not new_blocks:
            raise RuntimeError(f"All blocks removed after image handling for span {span_index}")
        updated[span_index] = new_blocks
    return updated
