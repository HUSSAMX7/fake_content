"""DOCX integration via the bundled docx skill: unpack → edit XML → pack."""

from __future__ import annotations

import copy
import re
import sys
import tempfile
from lxml import etree
from difflib import SequenceMatcher
from pathlib import Path

from schemas import ContentBlock, InstructionItem

DOCX_OFFICE_DIR = Path(__file__).resolve().parent / "docx" / "scripts" / "office"
if str(DOCX_OFFICE_DIR) not in sys.path:
    sys.path.insert(0, str(DOCX_OFFICE_DIR))

from pack import pack as skill_pack  # noqa: E402
from unpack import unpack as skill_unpack  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET = etree

_BULLET_PREFIX = re.compile(r"^[\s•●○▪▫\-–—*]+")
_NUMBER_PREFIX = re.compile(r"^[\s\d]+[\.\)\-–—:]+[\s]*")


def _tag(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lstrip("@").strip())


def _normalize_block_text(block: ContentBlock) -> str:
    text = block.text.strip()
    if block.type == "bullet_item":
        return _BULLET_PREFIX.sub("", text).strip()
    if block.type == "numbered_item":
        return _NUMBER_PREFIX.sub("", text).strip()
    return text


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter(_tag("t")):
        if node.text:
            parts.append(node.text)
    return "".join(parts)


def _element_xml(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return ET.tostring(element, encoding="unicode")


def _extract_template_snippets(root: ET.Element) -> dict[str, str]:
    p_pr_xml = ""
    r_pr_xml = ""
    num_pr_xml = ""

    for paragraph in root.iter(_tag("p")):
        if not p_pr_xml:
            p_pr = paragraph.find(_tag("pPr"))
            if p_pr is not None:
                p_pr_xml = _element_xml(p_pr)
        if not r_pr_xml:
            for run in paragraph.findall(_tag("r")):
                r_pr = run.find(_tag("rPr"))
                if r_pr is not None:
                    r_pr_xml = _element_xml(r_pr)
                    break
        if not num_pr_xml:
            num_pr = paragraph.find(f".//{_tag('numPr')}")
            if num_pr is not None:
                num_pr_xml = _element_xml(num_pr)
        if p_pr_xml and r_pr_xml and num_pr_xml:
            break

    return {"p_pr": p_pr_xml, "r_pr": r_pr_xml, "num_pr": num_pr_xml}


def _inline_text(blocks: list[ContentBlock]) -> str:
    return " ".join(_normalize_block_text(block) for block in blocks if block.text.strip())


def _should_render_as_blocks(span: dict, blocks: list[ContentBlock]) -> bool:
    if not span["inline"]:
        return True
    if len(blocks) > 1:
        return True
    if blocks and blocks[0].type != "paragraph":
        return True
    return False


def _build_run_xml(text: str, r_pr_xml: str) -> str:
    escaped = _xml_escape(text)
    space = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    if r_pr_xml:
        return f"<w:r>{r_pr_xml}<w:t{space}>{escaped}</w:t></w:r>"
    return f"<w:r><w:t{space}>{escaped}</w:t></w:r>"


def _build_paragraph_xml(
    text: str,
    block: ContentBlock,
    snippets: dict[str, str],
) -> str:
    p_pr_parts: list[str] = []
    if block.type == "heading":
        p_pr_parts.append('<w:pStyle w:val="Heading2"/>')
    elif block.type == "numbered_item" and snippets.get("num_pr"):
        p_pr_parts.append(snippets["num_pr"])

    if p_pr_parts:
        p_pr_xml = "<w:pPr>" + "".join(p_pr_parts) + "</w:pPr>"
    elif snippets["p_pr"]:
        p_pr_xml = snippets["p_pr"]
    else:
        p_pr_xml = ""

    return f"<w:p>{p_pr_xml}{_build_run_xml(text, snippets['r_pr'])}</w:p>"


def _build_blocks_xml(
    span: dict,
    blocks: list[ContentBlock],
    snippets: dict[str, str],
) -> str:
    if not _should_render_as_blocks(span, blocks):
        return _xml_escape(_inline_text(blocks))

    parts: list[str] = []
    if span["before"].strip():
        parts.append(
            _build_paragraph_xml(span["before"], ContentBlock(type="paragraph", text=span["before"]), snippets)
        )

    start_index = 0
    if not span["before"].strip() and blocks:
        parts.append(_build_paragraph_xml(_normalize_block_text(blocks[0]), blocks[0], snippets))
        start_index = 1

    for block in blocks[start_index:]:
        parts.append(_build_paragraph_xml(_normalize_block_text(block), block, snippets))

    if span["after"].strip():
        if parts:
            last = parts[-1]
            if last.endswith("</w:p>"):
                parts[-1] = last[:-6] + _build_run_xml(span["after"], snippets["r_pr"]) + "</w:p>"
            else:
                parts.append(
                    _build_paragraph_xml(span["after"], ContentBlock(type="paragraph", text=span["after"]), snippets)
                )
        else:
            parts.append(
                _build_paragraph_xml(span["after"], ContentBlock(type="paragraph", text=span["after"]), snippets)
            )

    return "".join(parts)


def find_marker_spans_xml(document_xml: Path) -> list[dict]:
    root = ET.parse(document_xml).getroot()
    paragraphs = root.findall(f".//{_tag('p')}")

    spans: list[dict] = []
    index = 0
    while index < len(paragraphs):
        text = _paragraph_text(paragraphs[index])
        if "@" not in text:
            index += 1
            continue

        start = index
        combined = text
        while "@@" not in combined and index + 1 < len(paragraphs):
            index += 1
            combined += "\n" + _paragraph_text(paragraphs[index])

        if "@@" not in combined:
            index += 1
            continue

        match = re.search(r"@(.*?)(@@)", combined, re.DOTALL)
        if not match:
            index += 1
            continue

        spans.append(
            {
                "span_index": len(spans),
                "start": start,
                "end": index,
                "inner": match.group(1).strip(),
                "before": combined[: match.start()],
                "after": combined[match.end() :],
                "inline": bool(combined[: match.start()].strip() or combined[match.end() :].strip()),
            }
        )
        index += 1
    return spans


def match_tag(inner_text: str, instructions: list[InstructionItem]) -> InstructionItem | None:
    norm_inner = _normalize(inner_text)
    best: InstructionItem | None = None
    best_score = 0.0

    for tag in instructions:
        norm_instruction = _normalize(tag.instruction)
        score = SequenceMatcher(None, norm_inner, norm_instruction).ratio()
        if norm_inner in norm_instruction or norm_instruction in norm_inner:
            score = max(score, 0.9)
        if score > best_score:
            best_score = score
            best = tag

    return best if best_score >= 0.5 else None


def _build_parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    parent_map: dict[ET.Element, ET.Element] = {}
    for node in root.iter():
        for child in node:
            parent_map[child] = node
    return parent_map


def _parse_paragraph_elements(fragment: str) -> list[ET.Element]:
    fragment = fragment.strip()
    if not fragment:
        return []
    wrapped = f'<root xmlns:w="{W_NS}">{fragment}</root>'
    return list(ET.fromstring(wrapped))


def _copy_p_pr(source: ET.Element, target: ET.Element) -> None:
    source_ppr = source.find(_tag("pPr"))
    if source_ppr is None:
        return
    target_ppr = target.find(_tag("pPr"))
    if target_ppr is not None:
        target.remove(target_ppr)
    target.insert(0, copy.deepcopy(source_ppr))


def _inline_replacement_text(span: dict, blocks: list[ContentBlock]) -> str:
    parts: list[str] = []
    if span["before"]:
        parts.append(span["before"])
    parts.append(_inline_text(blocks))
    if span["after"]:
        parts.append(span["after"])
    return "".join(parts)


def _replace_span_in_tree(
    root: ET.Element,
    span: dict,
    blocks: list[ContentBlock],
    snippets: dict[str, str],
) -> None:
    paragraphs = root.findall(f".//{_tag('p')}")
    parent_map = _build_parent_map(root)
    start = span["start"]
    end = span["end"]
    if start >= len(paragraphs):
        return

    targets = paragraphs[start : end + 1]
    first = targets[0]
    parent = parent_map.get(first)
    if parent is None:
        return

    children = list(parent)
    try:
        indices = [children.index(paragraph) for paragraph in targets]
    except ValueError:
        return
    if len(indices) != len(targets):
        return

    insert_at = min(indices)

    if _should_render_as_blocks(span, blocks):
        new_elements = _parse_paragraph_elements(_build_blocks_xml(span, blocks, snippets))
    else:
        text = _inline_replacement_text(span, blocks)
        block = ContentBlock(type="paragraph", text=text)
        new_elements = _parse_paragraph_elements(_build_paragraph_xml(text, block, snippets))
        if new_elements:
            _copy_p_pr(first, new_elements[0])

    if not new_elements:
        return

    for paragraph in targets:
        parent.remove(paragraph)
    for offset, element in enumerate(new_elements):
        parent.insert(insert_at + offset, element)


def _write_document_xml(document_xml: Path, tree: etree._ElementTree) -> None:
    tree.write(
        str(document_xml),
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def _repair_broken_relationships(unpacked_dir: Path) -> None:
    rels_path = unpacked_dir / "word" / "_rels" / "document.xml.rels"
    document_xml = unpacked_dir / "word" / "document.xml"
    if not rels_path.exists():
        return

    text = rels_path.read_text(encoding="utf-8")
    removed_ids = re.findall(
        r'<Relationship\s+Id="([^"]+)"[^>]*Target="file:///[^"]*"[^>]*/>',
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r'<Relationship[^>]*Target="file:///[^"]*"[^>]*/>\s*',
        "",
        text,
        flags=re.IGNORECASE,
    )
    if cleaned != text:
        rels_path.write_text(cleaned, encoding="utf-8")

    if not removed_ids or not document_xml.exists():
        return

    doc_text = document_xml.read_text(encoding="utf-8")
    updated = doc_text
    for rel_id in removed_ids:
        updated = re.sub(
            rf'(<w:hyperlink[^>]*)\s+r:id="{re.escape(rel_id)}"',
            r"\1",
            updated,
        )
    if updated != doc_text:
        document_xml.write_text(updated, encoding="utf-8")


def _apply_replacements_to_unpacked(
    unpacked_dir: Path,
    spans: list[dict],
    replacements: dict[int, list[ContentBlock]],
) -> None:
    document_xml = unpacked_dir / "word" / "document.xml"
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(document_xml), parser)
    root = tree.getroot()
    snippets = _extract_template_snippets(root)

    span_lookup = {span["span_index"]: span for span in spans}
    ordered_spans = sorted(
        (span_lookup[index] for index in replacements if index in span_lookup),
        key=lambda item: item["start"],
        reverse=True,
    )
    for span in ordered_spans:
        blocks = replacements[span["span_index"]]
        _replace_span_in_tree(root, span, blocks, snippets)

    _write_document_xml(document_xml, tree)
    _repair_broken_relationships(unpacked_dir)


def _save_docx_with_fallback(output_path: str) -> str:
    target = Path(output_path)
    for index in range(20):
        candidate = target if index == 0 else target.with_name(f"{target.stem}_{index}{target.suffix}")
        if not candidate.exists():
            return str(candidate)
        try:
            candidate.unlink()
            return str(candidate)
        except PermissionError:
            continue
    return str(target.with_name(f"{target.stem}_1{target.suffix}"))


def unpack_template(template_path: str, unpacked_dir: Path) -> None:
    _, message = skill_unpack(template_path, str(unpacked_dir))
    if "Error" in message:
        raise RuntimeError(message)


def pack_document(unpacked_dir: Path, output_path: str, template_path: str) -> str:
    target = _save_docx_with_fallback(output_path)
    _, message = skill_pack(
        str(unpacked_dir),
        target,
        original_file=template_path,
        validate=True,
    )
    if "Error" in message:
        raise RuntimeError(message)
    if target != output_path:
        print(
            f"Warning: could not write to {output_path} (file may be open in Word). "
            f"Saved to: {target}"
        )
    print(message)
    return target


def apply_replacements_to_docx(
    template_path: str,
    output_path: str,
    spans: list[dict],
    replacements: dict[int, list[ContentBlock]],
    unpacked_dir: Path | None = None,
) -> str:
    cleanup = unpacked_dir is None
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if unpacked_dir is None:
        temp_dir = tempfile.TemporaryDirectory()
        unpacked_dir = Path(temp_dir.name) / "unpacked"
        unpack_template(template_path, unpacked_dir)

    try:
        if replacements:
            _apply_replacements_to_unpacked(unpacked_dir, spans, replacements)
        return pack_document(unpacked_dir, output_path, template_path)
    finally:
        if cleanup and temp_dir is not None:
            temp_dir.cleanup()


def prepare_template(template_path: str) -> tuple[tempfile.TemporaryDirectory[str], Path, list[dict]]:
    temp_dir = tempfile.TemporaryDirectory()
    unpacked_dir = Path(temp_dir.name) / "unpacked"
    unpack_template(template_path, unpacked_dir)
    spans = find_marker_spans_xml(unpacked_dir / "word" / "document.xml")
    return temp_dir, unpacked_dir, spans
