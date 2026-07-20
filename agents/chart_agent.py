"""Validate chart blocks; native Word embedding happens in docx_skill_integrator."""

from __future__ import annotations

import logging

from schemas import ContentBlock

logger = logging.getLogger(__name__)


def _soft_fail(block: ContentBlock) -> ContentBlock:
    caption = block.text.strip()
    if caption:
        return ContentBlock(type="paragraph", text=caption)
    return ContentBlock(type="paragraph", text="\u00a0")


def _chart_block_is_valid(block: ContentBlock) -> bool:
    if block.type != "chart" or not block.chart_kind or not block.chart_labels:
        return False
    if block.chart_kind == "flow":
        return True
    values = block.chart_values or []
    return bool(values) and len(values) == len(block.chart_labels)


def prepare_charts_for_replacements(
    replacements: dict[int, list[ContentBlock]],
) -> dict[int, list[ContentBlock]]:
    """Keep valid chart blocks for native Word embedding; soft-fail invalid ones.

    Numeric kinds (bar/barh/pie/line) become editable Office charts in the DOCX.
    flow becomes an editable Word table of stage names (not an AI image).
    """

    updated: dict[int, list[ContentBlock]] = {}
    for span_index, blocks in replacements.items():
        new_blocks: list[ContentBlock] = []
        for block in blocks:
            if block.type != "chart":
                new_blocks.append(block)
                continue
            if not _chart_block_is_valid(block):
                logger.warning(
                    "Invalid chart block for span %s; soft-failing to caption",
                    span_index,
                )
                new_blocks.append(_soft_fail(block))
                continue
            new_blocks.append(block)
        if not new_blocks:
            new_blocks = [ContentBlock(type="paragraph", text="\u00a0")]
        updated[span_index] = new_blocks
    return updated
