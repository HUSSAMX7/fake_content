"""Safe, deterministic replacement of ``@instruction@@`` markers in DOCX files.

The implementation deliberately patches only the XML parts containing markers.  It
does not rebuild a document through python-docx, merge runs, or normalise every XML
part: all of those approaches can silently remove text boxes, content controls, or
unrelated formatting from a rich Word template.
"""

from __future__ import annotations

import copy
import logging
import re
import shutil
import struct
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from lxml import etree as ET

from schemas import ContentBlock, InstructionItem

logger = logging.getLogger(__name__)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
V_NS = "urn:schemas-microsoft-com:vml"
XML_NS = "http://www.w3.org/XML/1998/namespace"
ET.register_namespace("w", W_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("pic", PIC_NS)
ET.register_namespace("r", R_NS)

_EMU_PER_INCH = 914400
_TARGET_IMAGE_WIDTH_EMU = 5486400  # ~6 inches / ~15 cm
_IMAGE_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)

_STORY_PART_RE = re.compile(
    r"^word/(?:document|header\d+|footer\d+|footnotes|endnotes)\.xml$"
)
_MARKER_RE = re.compile(r"@(?P<inner>.+?)@@", re.DOTALL)
_BULLET_PREFIX = re.compile(r"^[\s•◦▪▫\-–—*]+")
_NUMBER_PREFIX = re.compile(r"^[\s\d]+[\.\)\-–—:]+[\s]*")


def _tag(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _normalize_block_text(block: ContentBlock) -> str:
    text = block.text.strip()
    if block.type == "bullet_item":
        return _BULLET_PREFIX.sub("", text).strip()
    if block.type == "numbered_item":
        return _NUMBER_PREFIX.sub("", text).strip()
    return text


def _nearest_paragraph(node: ET.Element) -> ET.Element | None:
    current: ET.Element | None = node
    while current is not None:
        if current.tag == _tag("p"):
            return current
        current = current.getparent()
    return None


def _paragraph_text_nodes(paragraph: ET.Element) -> list[ET.Element]:
    """Return text nodes owned by this paragraph, excluding nested text boxes.

    A drawing can contain another ``w:p``.  ``paragraph.iter(w:t)`` incorrectly
    sees that nested paragraph too, which was the source of duplicate markers and
    accidental deletion of entire text boxes in the previous implementation.
    """

    return [
        node
        for node in paragraph.iter(_tag("t"))
        if _nearest_paragraph(node) is paragraph
    ]


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in _paragraph_text_nodes(paragraph))


def _story_parts(unpacked_dir: Path) -> list[str]:
    return sorted(
        path.relative_to(unpacked_dir).as_posix()
        for path in unpacked_dir.rglob("*.xml")
        if _STORY_PART_RE.fullmatch(path.relative_to(unpacked_dir).as_posix())
    )


def _find_marker_spans_in_root(root: ET.Element, part_name: str) -> list[dict]:
    paragraphs = root.findall(f".//{_tag('p')}")
    texts = [_paragraph_text(paragraph) for paragraph in paragraphs]

    # The newline is only a locator separator; it allows a marker to cross normal
    # paragraphs while making its exact source paragraphs unambiguous.
    starts: list[int] = []
    stream_parts: list[str] = []
    offset = 0
    for index, text in enumerate(texts):
        starts.append(offset)
        stream_parts.append(text)
        offset += len(text)
        if index != len(texts) - 1:
            stream_parts.append("\n")
            offset += 1
    stream = "".join(stream_parts)

    def paragraph_at(position: int) -> tuple[int, int]:
        for index in range(len(texts) - 1, -1, -1):
            if position >= starts[index]:
                local = position - starts[index]
                if local <= len(texts[index]):
                    return index, local
        raise ValueError(f"Marker position {position} is outside {part_name}")

    spans: list[dict] = []
    for match in _MARKER_RE.finditer(stream):
        start, start_offset = paragraph_at(match.start())
        # End is exclusive; locate its final character, then convert back to an
        # exclusive offset inside that paragraph.
        end, final_offset = paragraph_at(match.end() - 1)
        end_offset = final_offset + 1
        before = texts[start][:start_offset]
        after = texts[end][end_offset:]
        spans.append(
            {
                "part": part_name,
                "start": start,
                "end": end,
                "start_offset": start_offset,
                "end_offset": end_offset,
                # ``inner`` is the semantic instruction used for matching; the
                # raw value is retained so a harmless authoring space before @@
                # does not make the surgical patch reject its own marker.
                "inner": match.group("inner").strip(),
                "raw_inner": match.group("inner"),
                "before": before,
                "after": after,
                # A marker sharing text with its paragraph must always be patched
                # in place. Marker-only paragraphs can become blocks if the writer
                # actually returns multiple structured blocks.
                "inline": start == end
                and (
                    bool(before.strip() or after.strip())
                    # A data-bound content control is a field even when it is the
                    # only visible text in its paragraph. Asking the writer for a
                    # multi-paragraph section here caused Word to reject/revert it.
                    or _data_binding_for_paragraph(paragraphs[start]) is not None
                ),
            }
        )
    return spans


def find_marker_spans_xml(document_xml: Path) -> list[dict]:
    """Find every marker in one XML story part.

    Kept as a public compatibility function for callers that supply document.xml.
    """

    root = ET.parse(str(document_xml)).getroot()
    spans = _find_marker_spans_in_root(root, "word/document.xml")
    for index, span in enumerate(spans):
        span["span_index"] = index
    return spans


def find_marker_spans_in_unpacked(unpacked_dir: Path) -> list[dict]:
    """Inventory body, headers, footers, notes, tables, and text boxes."""

    spans: list[dict] = []
    for part_name in _story_parts(unpacked_dir):
        root = ET.parse(str(unpacked_dir / part_name)).getroot()
        spans.extend(_find_marker_spans_in_root(root, part_name))
    for index, span in enumerate(spans):
        span["span_index"] = index
    return spans


def match_tag(inner_text: str, instructions: list[InstructionItem]) -> InstructionItem | None:
    """Exact matching only. Fuzzy matching can send content to the wrong slot."""

    expected = _normalize(inner_text)
    for tag in instructions:
        if _normalize(tag.instruction) == expected:
            return tag
    return None


def _inline_text(blocks: list[ContentBlock]) -> str:
    return " ".join(
        _normalize_block_text(block)
        for block in blocks
        if block.type != "image" and block.text.strip()
    )


def _should_render_as_blocks(span: dict, blocks: list[ContentBlock]) -> bool:
    if not blocks:
        raise ValueError(f"Empty replacement for marker {span['span_index']}")
    if span["inline"]:
        return False
    if any(block.type == "image" for block in blocks):
        return True
    return len(blocks) > 1 or blocks[0].type != "paragraph"


def _set_text(node: ET.Element, text: str) -> None:
    node.text = text
    if text.startswith(" ") or text.endswith(" "):
        node.set(f"{{{XML_NS}}}space", "preserve")
    else:
        node.attrib.pop(f"{{{XML_NS}}}space", None)


def _text_position(nodes: list[ET.Element], offset: int) -> tuple[int, int]:
    """Map a paragraph character offset to a text-node index and local offset."""

    consumed = 0
    for index, node in enumerate(nodes):
        length = len(node.text or "")
        node_end = consumed + length
        if offset < node_end:
            return index, offset - consumed
        if offset == node_end:
            # A marker immediately after a normal run can start in a data-bound
            # content control.  Selecting the preceding run would write the
            # replacement beside the control, then Word refreshes the control
            # from its document property and visibly duplicates the value.
            if index + 1 < len(nodes):
                return index + 1, 0
            return index, length
        consumed = node_end
    if nodes and offset == consumed:
        return len(nodes) - 1, len(nodes[-1].text or "")
    raise ValueError("Marker offset cannot be mapped to a Word text node")


def _replace_inline(root: ET.Element, span: dict, blocks: list[ContentBlock]) -> None:
    paragraphs = root.findall(f".//{_tag('p')}")
    if span["start"] != span["end"]:
        raise ValueError("Inline marker cannot cross paragraphs")
    paragraph = paragraphs[span["start"]]
    nodes = _paragraph_text_nodes(paragraph)
    source_text = "".join(node.text or "" for node in nodes)
    token = f"@{span.get('raw_inner', span['inner'])}@@"
    start = span["start_offset"]
    end = span["end_offset"]
    if source_text[start:end] != token:
        raise ValueError(
            f"Marker source changed before replacement: {span['part']}#{span['span_index']}"
        )

    replacement = _inline_text(blocks)
    if not replacement:
        raise ValueError(f"Blank replacement for marker {span['span_index']}")
    first_index, first_local = _text_position(nodes, start)
    last_index, last_local = _text_position(nodes, end)
    first_text = nodes[first_index].text or ""
    last_text = nodes[last_index].text or ""
    if first_index == last_index:
        _set_text(nodes[first_index], first_text[:first_local] + replacement + first_text[last_local:])
        return

    _set_text(nodes[first_index], first_text[:first_local] + replacement)
    for index in range(first_index + 1, last_index):
        _set_text(nodes[index], "")
    _set_text(nodes[last_index], last_text[last_local:])


def _data_binding_for_paragraph(paragraph: ET.Element) -> dict[str, str] | None:
    """Return a Word content-control binding inherited by this paragraph."""

    # Word can place the SDT inside a paragraph, as well as around the paragraph.
    # The marker text is then a descendant of the paragraph rather than vice versa.
    nested = paragraph.find(f".//{_tag('dataBinding')}")
    if nested is not None:
        return dict(nested.attrib)
    current: ET.Element | None = paragraph
    while current is not None:
        if current.tag == _tag("sdt"):
            binding = current.find(f"./{_tag('sdtPr')}/{_tag('dataBinding')}")
            if binding is not None:
                return dict(binding.attrib)
        current = current.getparent()
    return None


def _record_data_binding_update(
    paragraph: ET.Element,
    value: str,
    updates: dict[tuple[str, str, str], str],
) -> None:
    """Keep a data-bound content control from reverting when Word opens it.

    Word may refresh a content control from docProps/core.xml or docProps/app.xml
    during export/open. Updating only w:sdtContent therefore looks correct in XML
    but visibly reverts to the original marker in Word.
    """

    binding = _data_binding_for_paragraph(paragraph)
    if binding is None:
        return
    xpath = binding.get(_tag("xpath"))
    prefix_mappings = binding.get(_tag("prefixMappings"), "")
    store_item_id = binding.get(_tag("storeItemID"), "")
    if not xpath:
        raise ValueError("Data-bound content control has no XPath")
    key = (store_item_id, xpath, prefix_mappings)
    existing = updates.get(key)
    if existing is not None and existing != value:
        # Multiple inline markers can bind to the same Word property (e.g. dc:title).
        # Keep the first recorded docProps value; each span still gets its inline XML replacement.
        logger.warning(
            "Skipping conflicting docProps update for %s; keeping %r over %r",
            xpath,
            existing,
            value,
        )
        return
    updates[key] = value


def _binding_namespaces(prefix_mappings: str) -> dict[str, str]:
    return dict(re.findall(r"xmlns:([\w.-]+)='([^']+)'", prefix_mappings))


def _apply_data_binding_updates(
    unpacked_dir: Path,
    updates: dict[tuple[str, str, str], str],
) -> None:
    if not updates:
        return
    property_parts = [unpacked_dir / "docProps" / "core.xml", unpacked_dir / "docProps" / "app.xml"]
    unresolved = set(updates)
    for property_part in property_parts:
        if not property_part.exists():
            continue
        tree = ET.parse(str(property_part))
        root = tree.getroot()
        changed = False
        for key, value in updates.items():
            _, xpath, mappings = key
            try:
                matches = root.xpath(xpath, namespaces=_binding_namespaces(mappings))
            except ET.XPathError as error:
                raise ValueError(f"Invalid content-control binding XPath {xpath!r}") from error
            if not matches:
                continue
            for match in matches:
                if not isinstance(match, ET._Element):
                    raise ValueError(f"Unsupported non-element content-control binding {xpath!r}")
                match.text = value
            unresolved.discard(key)
            changed = True
        if changed:
            tree.write(str(property_part), xml_declaration=True, encoding="UTF-8", standalone=True)
    if unresolved:
        paths = sorted({key[1] for key in unresolved})
        raise ValueError(f"Could not resolve content-control binding(s): {paths}")


def _contains_preserve_only_content(paragraph: ET.Element) -> bool:
    protected = (_tag("drawing"), _tag("pict"), _tag("sdt"), _tag("bookmarkStart"), _tag("bookmarkEnd"))
    return any(paragraph.find(f".//{tag}") is not None for tag in protected)


def _first_run_properties(paragraph: ET.Element) -> ET.Element | None:
    for run in paragraph.iter(_tag("r")):
        if _nearest_paragraph(run) is paragraph:
            properties = run.find(_tag("rPr"))
            return copy.deepcopy(properties) if properties is not None else None
    return None


def _detach_floating_runs(paragraph: ET.Element) -> ET.Element | None:
    """Move floating page furniture into a standalone anchor paragraph.

    Some templates put an ``@...@@`` marker and an anchored banner in the same
    paragraph.  Expanding that marker into several paragraphs while leaving the
    anchor on the first paragraph makes the later text flow underneath the
    banner.  Detaching only shape-only runs lets us reinsert the unchanged
    anchor after all generated content; its geometry and Choice/Fallback payload
    stay byte-for-byte equivalent at the element level.
    """

    wp_anchor = f"{{{WP_NS}}}anchor"
    v_shape = f"{{{V_NS}}}shape"
    floating_runs: list[ET.Element] = []
    for child in list(paragraph):
        if child.tag != _tag("r"):
            continue
        has_floating_shape = (
            child.find(f".//{wp_anchor}") is not None
            or child.find(f".//{v_shape}") is not None
        )
        owns_visible_text = any(
            _nearest_paragraph(node) is paragraph and bool((node.text or "").strip())
            for node in child.iter(_tag("t"))
        )
        if has_floating_shape and not owns_visible_text:
            floating_runs.append(child)

    if not floating_runs:
        return None

    anchor_paragraph = ET.Element(_tag("p"))
    p_pr = paragraph.find(_tag("pPr"))
    if p_pr is not None:
        anchor_paragraph.append(copy.deepcopy(p_pr))
    for run in floating_runs:
        paragraph.remove(run)
        anchor_paragraph.append(run)
    return anchor_paragraph


def _set_paragraph_style(p_pr: ET.Element, style_name: str) -> None:
    style = p_pr.find(_tag("pStyle"))
    if style is None:
        style = ET.Element(_tag("pStyle"))
        p_pr.insert(0, style)
    style.set(_tag("val"), style_name)


def _png_pixel_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        signature = handle.read(8)
        if signature == b"\x89PNG\r\n\x1a\n":
            length = struct.unpack(">I", handle.read(4))[0]
            chunk_type = handle.read(4)
            if chunk_type != b"IHDR" or length < 8:
                raise ValueError(f"Invalid PNG IHDR: {path}")
            width, height = struct.unpack(">II", handle.read(8))
            if width <= 0 or height <= 0:
                raise ValueError(f"Invalid PNG dimensions: {path}")
            return width, height

    # Fallback for any still-unnormalized provider format.
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid image dimensions: {path}")
    return width, height


def _image_extent_emu(path: Path) -> tuple[int, int]:
    width_px, height_px = _png_pixel_size(path)
    cx = _TARGET_IMAGE_WIDTH_EMU
    cy = max(1, int(cx * (height_px / width_px)))
    return cx, cy


def _rels_path_for_part(unpacked_dir: Path, part_name: str) -> Path:
    part = Path(part_name)
    return unpacked_dir / part.parent / "_rels" / f"{part.name}.rels"


def _ensure_png_content_type(unpacked_dir: Path) -> None:
    types_path = unpacked_dir / "[Content_Types].xml"
    tree = ET.parse(str(types_path))
    root = tree.getroot()
    for node in root.findall(f"{{{CT_NS}}}Default"):
        if (node.get("Extension") or "").lower() == "png":
            return
    default = ET.SubElement(root, f"{{{CT_NS}}}Default")
    default.set("Extension", "png")
    default.set("ContentType", "image/png")
    tree.write(str(types_path), xml_declaration=True, encoding="UTF-8", standalone=True)


def _next_relationship_id(rels_root: ET.Element) -> str:
    used: set[int] = set()
    for node in rels_root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = node.get("Id") or ""
        match = re.fullmatch(r"rId(\d+)", rel_id)
        if match:
            used.add(int(match.group(1)))
    candidate = 1
    while candidate in used:
        candidate += 1
    return f"rId{candidate}"


def _next_doc_pr_id(unpacked_dir: Path) -> int:
    max_id = 0
    for part_name in _story_parts(unpacked_dir):
        part_path = unpacked_dir / part_name
        root = ET.parse(str(part_path)).getroot()
        for node in root.iter(f"{{{WP_NS}}}docPr"):
            raw = node.get("id")
            if raw and raw.isdigit():
                max_id = max(max_id, int(raw))
    return max_id + 1


def _register_image_relationship(
    unpacked_dir: Path,
    part_name: str,
    media_name: str,
) -> str:
    rels_path = _rels_path_for_part(unpacked_dir, part_name)
    rels_path.parent.mkdir(parents=True, exist_ok=True)
    if rels_path.exists():
        tree = ET.parse(str(rels_path))
        root = tree.getroot()
    else:
        root = ET.Element(f"{{{REL_NS}}}Relationships")
        tree = ET.ElementTree(root)

    rel_id = _next_relationship_id(root)
    relationship = ET.SubElement(root, f"{{{REL_NS}}}Relationship")
    relationship.set("Id", rel_id)
    relationship.set("Type", _IMAGE_REL_TYPE)
    relationship.set("Target", f"media/{media_name}")
    tree.write(str(rels_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    return rel_id


def _copy_image_into_package(unpacked_dir: Path, source: Path) -> str:
    media_dir = unpacked_dir / "word" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        name = f"generated_{index}.png"
        destination = media_dir / name
        if not destination.exists():
            shutil.copy2(source, destination)
            return name
        index += 1


def _build_drawing_run(
    rel_id: str,
    media_name: str,
    cx: int,
    cy: int,
    doc_pr_id: int,
) -> ET.Element:
    run = ET.Element(_tag("r"))
    drawing = ET.SubElement(run, _tag("drawing"))
    inline = ET.SubElement(
        drawing,
        f"{{{WP_NS}}}inline",
        {
            "distT": "0",
            "distB": "0",
            "distL": "0",
            "distR": "0",
        },
    )
    ET.SubElement(inline, f"{{{WP_NS}}}extent", {"cx": str(cx), "cy": str(cy)})
    ET.SubElement(
        inline,
        f"{{{WP_NS}}}effectExtent",
        {"l": "0", "t": "0", "r": "0", "b": "0"},
    )
    ET.SubElement(
        inline,
        f"{{{WP_NS}}}docPr",
        {"id": str(doc_pr_id), "name": f"Picture {doc_pr_id}"},
    )
    cnv = ET.SubElement(inline, f"{{{WP_NS}}}cNvGraphicFramePr")
    ET.SubElement(
        cnv,
        f"{{{A_NS}}}graphicFrameLocks",
        {"noChangeAspect": "1"},
    )
    graphic = ET.SubElement(inline, f"{{{A_NS}}}graphic")
    graphic_data = ET.SubElement(
        graphic,
        f"{{{A_NS}}}graphicData",
        {"uri": "http://schemas.openxmlformats.org/drawingml/2006/picture"},
    )
    pic = ET.SubElement(graphic_data, f"{{{PIC_NS}}}pic")
    nv = ET.SubElement(pic, f"{{{PIC_NS}}}nvPicPr")
    ET.SubElement(
        nv,
        f"{{{PIC_NS}}}cNvPr",
        {"id": "0", "name": media_name},
    )
    ET.SubElement(nv, f"{{{PIC_NS}}}cNvPicPr")
    blip_fill = ET.SubElement(pic, f"{{{PIC_NS}}}blipFill")
    ET.SubElement(blip_fill, f"{{{A_NS}}}blip", {f"{{{R_NS}}}embed": rel_id})
    stretch = ET.SubElement(blip_fill, f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")
    sp_pr = ET.SubElement(pic, f"{{{PIC_NS}}}spPr")
    xfrm = ET.SubElement(sp_pr, f"{{{A_NS}}}xfrm")
    ET.SubElement(xfrm, f"{{{A_NS}}}off", {"x": "0", "y": "0"})
    ET.SubElement(xfrm, f"{{{A_NS}}}ext", {"cx": str(cx), "cy": str(cy)})
    prst = ET.SubElement(sp_pr, f"{{{A_NS}}}prstGeom", {"prst": "rect"})
    ET.SubElement(prst, f"{{{A_NS}}}avLst")
    return run


def _generated_image_paragraph(
    source: ET.Element,
    block: ContentBlock,
    unpacked_dir: Path,
    part_name: str,
    doc_pr_id: int,
) -> ET.Element:
    if not block.image_path:
        raise ValueError("Image block is missing image_path")
    source_path = Path(block.image_path)
    if not source_path.is_file():
        raise ValueError(f"Image file not found: {source_path}")

    _ensure_png_content_type(unpacked_dir)
    media_name = _copy_image_into_package(unpacked_dir, source_path)
    rel_id = _register_image_relationship(unpacked_dir, part_name, media_name)
    cx, cy = _image_extent_emu(source_path)

    paragraph = ET.Element(_tag("p"))
    source_ppr = source.find(_tag("pPr"))
    if source_ppr is not None:
        paragraph.append(copy.deepcopy(source_ppr))
    paragraph.append(_build_drawing_run(rel_id, media_name, cx, cy, doc_pr_id))
    return paragraph


def _paragraphs_for_block(
    source: ET.Element,
    block: ContentBlock,
    unpacked_dir: Path | None,
    part_name: str,
    doc_pr_counter: list[int],
) -> list[ET.Element]:
    if block.type != "image":
        return [_generated_paragraph(source, block)]
    if not block.image_path or unpacked_dir is None:
        if block.text.strip():
            return [_generated_paragraph(source, ContentBlock(type="paragraph", text=block.text))]
        raise ValueError("Image block has no generated file and no caption")

    paragraphs = [
        _generated_image_paragraph(
            source,
            block,
            unpacked_dir,
            part_name,
            doc_pr_counter[0],
        )
    ]
    doc_pr_counter[0] += 1
    if block.text.strip():
        paragraphs.append(
            _generated_paragraph(source, ContentBlock(type="paragraph", text=block.text))
        )
    return paragraphs


def _generated_paragraph(source: ET.Element, block: ContentBlock) -> ET.Element:
    paragraph = ET.Element(_tag("p"))
    source_ppr = source.find(_tag("pPr"))
    if source_ppr is not None:
        p_pr = copy.deepcopy(source_ppr)
        # New structural headings need a heading style, but existing heading
        # placeholders are patched inline and therefore keep their exact style.
        if block.type == "heading":
            _set_paragraph_style(p_pr, "Heading2")
        paragraph.append(p_pr)
    elif block.type == "heading":
        p_pr = ET.Element(_tag("pPr"))
        _set_paragraph_style(p_pr, "Heading2")
        paragraph.append(p_pr)

    run = ET.SubElement(paragraph, _tag("r"))
    properties = _first_run_properties(source)
    if properties is not None:
        run.append(properties)
    text = _normalize_block_text(block)
    text_node = ET.SubElement(run, _tag("t"))
    _set_text(text_node, text)
    return paragraph


def _replace_block(
    root: ET.Element,
    span: dict,
    blocks: list[ContentBlock],
    unpacked_dir: Path | None = None,
    doc_pr_counter: list[int] | None = None,
) -> None:
    paragraphs = root.findall(f".//{_tag('p')}")
    targets = paragraphs[span["start"] : span["end"] + 1]
    if not targets:
        raise ValueError("Marker target paragraph is missing")
    if span["start_offset"] != 0 or span["end_offset"] != len(_paragraph_text(targets[-1])):
        raise ValueError("Block marker has surrounding text and must be patched inline")
    parent = targets[0].getparent()
    if parent is None or any(paragraph.getparent() is not parent for paragraph in targets):
        raise ValueError("Block marker crosses Word containers")
    if any(_contains_preserve_only_content(paragraph) for paragraph in targets):
        raise ValueError("Block marker contains drawing, bookmark, or content control")

    children = list(parent)
    indices = [children.index(paragraph) for paragraph in targets]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise ValueError("Block marker paragraphs are not consecutive siblings")
    counter = doc_pr_counter if doc_pr_counter is not None else [1]
    new_paragraphs: list[ET.Element] = []
    for block in blocks:
        new_paragraphs.extend(
            _paragraphs_for_block(targets[0], block, unpacked_dir, span["part"], counter)
        )
    if not new_paragraphs:
        raise ValueError(f"Blank replacement for marker {span['span_index']}")
    for paragraph in targets:
        parent.remove(paragraph)
    for offset, paragraph in enumerate(new_paragraphs):
        parent.insert(indices[0] + offset, paragraph)


def _replace_block_preserving_source_paragraph(
    root: ET.Element,
    span: dict,
    blocks: list[ContentBlock],
    unpacked_dir: Path | None = None,
    doc_pr_counter: list[int] | None = None,
) -> None:
    """Expand a marker without deleting an anchored drawing or bookmark.

    The first block is written into the existing paragraph, retaining its drawing,
    content-control metadata, or bookmark. Remaining blocks are cloned as normal
    sibling paragraphs after it. This is the safe path for a marker-only paragraph
    that contains page furniture or navigation anchors.
    """

    if span["start"] != span["end"]:
        raise ValueError("Protected block marker crosses paragraphs")
    paragraphs = root.findall(f".//{_tag('p')}")
    source = paragraphs[span["start"]]
    if span["start_offset"] != 0 or span["end_offset"] != len(_paragraph_text(source)):
        raise ValueError("Protected block marker has surrounding text")

    counter = doc_pr_counter if doc_pr_counter is not None else [1]
    first, *rest = blocks
    if first.type == "image":
        # Keep protected furniture; clear marker, then insert drawing (+ caption) after.
        _replace_inline(root, span, [ContentBlock(type="paragraph", text="\u00a0")])
        anchor_paragraph = _detach_floating_runs(source)
        parent = source.getparent()
        if parent is None:
            raise ValueError("Protected block marker has no parent container")
        insert_at = list(parent).index(source) + 1
        for block in [first, *rest]:
            for paragraph in _paragraphs_for_block(
                source, block, unpacked_dir, span["part"], counter
            ):
                parent.insert(insert_at, paragraph)
                insert_at += 1
        if anchor_paragraph is not None:
            parent.insert(insert_at, anchor_paragraph)
        return

    _replace_inline(root, span, [first])
    anchor_paragraph = _detach_floating_runs(source)
    parent = source.getparent()
    if parent is None:
        raise ValueError("Protected block marker has no parent container")
    insert_at = list(parent).index(source) + 1
    for offset, block in enumerate(rest):
        extra = _paragraphs_for_block(source, block, unpacked_dir, span["part"], counter)
        for paragraph in extra:
            parent.insert(insert_at, paragraph)
            insert_at += 1
    if anchor_paragraph is not None:
        parent.insert(insert_at, anchor_paragraph)


def _apply_replacements_to_unpacked(
    unpacked_dir: Path,
    spans: list[dict],
    replacements: dict[int, list[ContentBlock]],
) -> None:
    span_lookup = {span["span_index"]: span for span in spans}
    unknown = set(replacements) - set(span_lookup)
    if unknown:
        raise ValueError(f"Replacements reference unknown marker spans: {sorted(unknown)}")

    by_part: dict[str, list[dict]] = defaultdict(list)
    for index in replacements:
        by_part[span_lookup[index]["part"]].append(span_lookup[index])

    doc_pr_counter = [_next_doc_pr_id(unpacked_dir)]
    binding_updates: dict[tuple[str, str, str], str] = {}
    for part_name, part_spans in by_part.items():
        part_path = unpacked_dir / part_name
        parser = ET.XMLParser(remove_blank_text=False)
        tree = ET.parse(str(part_path), parser)
        root = tree.getroot()
        for span in sorted(part_spans, key=lambda item: (item["start"], item["start_offset"]), reverse=True):
            blocks = replacements[span["span_index"]]
            paragraphs = root.findall(f".//{_tag('p')}")
            marker_paragraph = paragraphs[span["start"]]
            binding = _data_binding_for_paragraph(marker_paragraph)
            if _should_render_as_blocks(span, blocks):
                targets = paragraphs[span["start"] : span["end"] + 1]
                if any(_contains_preserve_only_content(paragraph) for paragraph in targets):
                    _replace_block_preserving_source_paragraph(
                        root, span, blocks, unpacked_dir, doc_pr_counter
                    )
                else:
                    _replace_block(root, span, blocks, unpacked_dir, doc_pr_counter)
            else:
                _record_data_binding_update(marker_paragraph, _inline_text(blocks), binding_updates)
                _replace_inline(root, span, blocks)
        tree.write(str(part_path), xml_declaration=True, encoding="UTF-8", standalone=True)
    _apply_data_binding_updates(unpacked_dir, binding_updates)


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
    """Extract without pretty-printing or merging runs in unrelated XML parts."""

    with zipfile.ZipFile(template_path, "r") as archive:
        archive.extractall(unpacked_dir)


def pack_document(unpacked_dir: Path, output_path: str, template_path: str) -> str:
    """Repack unchanged parts byte-for-byte and changed parts only where necessary."""

    del template_path  # retained for the existing public API
    target = _save_docx_with_fallback(output_path)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(unpacked_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(unpacked_dir).as_posix())
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
    spans = find_marker_spans_in_unpacked(unpacked_dir)
    return temp_dir, unpacked_dir, spans
