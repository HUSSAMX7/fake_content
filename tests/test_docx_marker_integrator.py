from __future__ import annotations

import hashlib
import re
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree as ET

from docx_skill_integrator import (
    ContentBlock,
    apply_replacements_to_docx,
    find_marker_spans_xml,
    prepare_template,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "backend" / "defaults" / "good_template.docx"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def paragraph(text: str) -> ContentBlock:
    return ContentBlock(type="paragraph", text=text)


def _write_solid_png(path: Path, width: int = 32, height: int = 20) -> None:
    """Write a tiny valid RGB PNG without extra dependencies."""

    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + (b"\xff\x00\x00" * width) for _ in range(height))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


class MarkerIntegratorTests(unittest.TestCase):
    def test_adjacent_markers_are_all_discovered(self) -> None:
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="{W_NS}"><w:body><w:p><w:r><w:t>قبل @A@@@B@@ بعد</w:t></w:r></w:p></w:body></w:document>'''
        with tempfile.TemporaryDirectory() as directory:
            xml_path = Path(directory) / "document.xml"
            xml_path.write_text(xml, encoding="utf-8")
            spans = find_marker_spans_xml(xml_path)
        self.assertEqual([span["inner"] for span in spans], ["A", "B"])
        self.assertEqual([span["start"] for span in spans], [0, 0])

    def test_template_inventory_preserves_both_compatibility_branches(self) -> None:
        temp_dir, _, spans = prepare_template(str(TEMPLATE))
        try:
            self.assertEqual(len(spans), 19)
            self.assertEqual(sum(span["part"] == "word/header2.xml" for span in spans), 1)
            self.assertEqual(sum(span["inner"] == "اسم المشروع" for span in spans), 5)
        finally:
            temp_dir.cleanup()

    def test_all_template_markers_are_replaced_without_rewriting_other_parts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "filled.docx"
            temp_dir, unpacked_dir, spans = prepare_template(str(TEMPLATE))
            try:
                replacements = {
                    span["span_index"]: (
                        [paragraph("مشروع الاختبار المتكامل")]
                        if span["inner"] == "اسم المشروع"
                        else [paragraph("الجهة التجريبية")]
                        if span["inner"] in {"اسم الجهة الكامل", "اسم الجهة بالكامل"}
                        else [
                            ContentBlock(type="numbered_item", text="المرحلة الأولى: تحليل الوضع الحالي"),
                            ContentBlock(type="numbered_item", text="المرحلة الثانية: تصميم النموذج المستهدف"),
                            ContentBlock(type="numbered_item", text="المرحلة الثالثة: تطوير حالات الاستخدام"),
                            ContentBlock(type="numbered_item", text="المرحلة الرابعة: التنفيذ والتفعيل"),
                        ]
                        if "مراحل تنفيذ المشروع" in span["inner"]
                        else
                        [
                            ContentBlock(type="heading", text="عنوان مرحلة اختبار"),
                            paragraph("الفقرة الأولى للاختبار"),
                            ContentBlock(type="bullet_item", text="بند اختبار"),
                        ]
                        if span["start"] != span["end"]
                        else [paragraph(f"قيمة اختبار {span['span_index']}")]
                    )
                    for span in spans
                }
                result = apply_replacements_to_docx(
                    str(TEMPLATE), str(output), spans, replacements, unpacked_dir=unpacked_dir
                )
            finally:
                temp_dir.cleanup()

            verify_dir, _, remaining = prepare_template(result)
            try:
                self.assertEqual(remaining, [])
            finally:
                verify_dir.cleanup()

            with zipfile.ZipFile(TEMPLATE) as source, zipfile.ZipFile(result) as final:
                changed = {
                    name
                    for name in source.namelist()
                    if hashlib.sha256(source.read(name)).digest()
                    != hashlib.sha256(final.read(name)).digest()
                }
            self.assertEqual(
                changed,
                {
                    "word/document.xml",
                    "word/header2.xml",
                    "docProps/app.xml",
                    "docProps/core.xml",
                },
            )

            with zipfile.ZipFile(result) as final:
                core = ET.fromstring(final.read("docProps/core.xml"))
                app = ET.fromstring(final.read("docProps/app.xml"))
                document_xml = final.read("word/document.xml")
            self.assertEqual(
                core.xpath("string(//dc:title)", namespaces={"dc": "http://purl.org/dc/elements/1.1/"}),
                "مشروع الاختبار المتكامل",
            )
            self.assertEqual(
                app.xpath(
                    "string(//ep:Company)",
                    namespaces={"ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"},
                ),
                "الجهة التجريبية",
            )
            self.assertIsNone(re.search(r"@[^<@]+@@", document_xml.decode("utf-8")))

            root = ET.fromstring(zipfile.ZipFile(result).read("word/document.xml"))
            heading = root.xpath(
                ".//w:p[w:pPr/w:pStyle[@w:val='Heading2']]",
                namespaces={"w": W_NS},
            )
            self.assertTrue(any("الجهة التجريبية" in "".join(node.itertext()) for node in heading))

            ns = {
                "w": W_NS,
                "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
            }
            body = root.find("w:body", namespaces=ns)
            self.assertIsNotNone(body)
            body_children = list(body)
            generated_phase_names = {
                "المرحلة الأولى: تحليل الوضع الحالي",
                "المرحلة الثانية: تصميم النموذج المستهدف",
                "المرحلة الثالثة: تطوير حالات الاستخدام",
                "المرحلة الرابعة: التنفيذ والتفعيل",
            }
            phase_indices = [
                index
                for index, child in enumerate(body_children)
                if "".join(child.xpath("./w:r/w:t/text()", namespaces=ns))
                in generated_phase_names
            ]
            anchor_indices = [
                index
                for index, child in enumerate(body_children)
                if child.xpath(".//wp:anchor", namespaces=ns)
                and "التدريب ونقل المعرفة" in "".join(child.itertext())
            ]
            self.assertGreaterEqual(len(phase_indices), 4)
            self.assertEqual(len(anchor_indices), 1)
            self.assertLess(max(phase_indices), anchor_indices[0])

    def test_conflicting_data_bound_title_updates_do_not_abort(self) -> None:
        temp_dir, unpacked_dir, spans = prepare_template(str(TEMPLATE))
        try:
            title_spans = [span for span in spans if span["inner"] == "اسم المشروع"]
            self.assertGreater(len(title_spans), 1)

            replacements = {
                span["span_index"]: (
                    [paragraph("مشروع الاختبار المتكامل")]
                    if span["inner"] == "اسم المشروع"
                    else [paragraph("الجهة التجريبية")]
                    if span["inner"] in {"اسم الجهة الكامل", "اسم الجهة بالكامل"}
                    else [
                        ContentBlock(type="numbered_item", text="المرحلة الأولى: تحليل الوضع الحالي"),
                        ContentBlock(type="numbered_item", text="المرحلة الثانية: تصميم النموذج المستهدف"),
                    ]
                    if "مراحل تنفيذ المشروع" in span["inner"]
                    else [
                        ContentBlock(type="heading", text="عنوان مرحلة اختبار"),
                        paragraph("الفقرة الأولى للاختبار"),
                        ContentBlock(type="bullet_item", text="بند اختبار"),
                    ]
                    if span["start"] != span["end"]
                    else [paragraph(f"قيمة اختبار {span['span_index']}")]
                )
                for span in spans
            }
            for index, span in enumerate(title_spans):
                replacements[span["span_index"]] = [paragraph(f"عنوان متعارض {index}")]

            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "filled.docx"
                result = apply_replacements_to_docx(
                    str(TEMPLATE),
                    str(output),
                    spans,
                    replacements,
                    unpacked_dir=unpacked_dir,
                )
                self.assertTrue(Path(result).exists())
        finally:
            temp_dir.cleanup()

    def test_image_block_is_packed_into_word_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            png_path = Path(directory) / "figure.png"
            _write_solid_png(png_path)
            output = Path(directory) / "with_image.docx"
            temp_dir, unpacked_dir, spans = prepare_template(str(TEMPLATE))
            try:
                target = next(
                    span
                    for span in spans
                    if not span["inline"] and "أدرج شكلاً" in span["inner"]
                )
                replacements = {
                    span["span_index"]: (
                        [
                            ContentBlock(
                                type="image",
                                text="شكل (1): مخطط اختبار",
                                image_prompt="test diagram",
                                image_path=str(png_path),
                            ),
                            paragraph("شرح مختصر بعد الشكل."),
                        ]
                        if span["span_index"] == target["span_index"]
                        else [paragraph("مشروع الاختبار المتكامل")]
                        if span["inner"] == "اسم المشروع"
                        else [paragraph("الجهة التجريبية")]
                        if span["inner"] in {"اسم الجهة الكامل", "اسم الجهة بالكامل"}
                        else [
                            ContentBlock(type="numbered_item", text="المرحلة الأولى: تحليل الوضع الحالي"),
                            ContentBlock(type="numbered_item", text="المرحلة الثانية: تصميم النموذج المستهدف"),
                            ContentBlock(type="numbered_item", text="المرحلة الثالثة: تطوير حالات الاستخدام"),
                            ContentBlock(type="numbered_item", text="المرحلة الرابعة: التنفيذ والتفعيل"),
                        ]
                        if "مراحل تنفيذ المشروع" in span["inner"]
                        else [
                            ContentBlock(type="heading", text="عنوان مرحلة اختبار"),
                            paragraph("الفقرة الأولى للاختبار"),
                            ContentBlock(type="bullet_item", text="بند اختبار"),
                        ]
                        if span["start"] != span["end"]
                        else [paragraph(f"قيمة اختبار {span['span_index']}")]
                    )
                    for span in spans
                }
                result = apply_replacements_to_docx(
                    str(TEMPLATE),
                    str(output),
                    spans,
                    replacements,
                    unpacked_dir=unpacked_dir,
                )
            finally:
                temp_dir.cleanup()

            with zipfile.ZipFile(result) as archive:
                media = [
                    name
                    for name in archive.namelist()
                    if name.startswith("word/media/generated_")
                ]
                self.assertTrue(media, "generated image missing from package")
                document_xml = archive.read("word/document.xml")
                self.assertIn(b"w:drawing", document_xml)
                self.assertIn("شكل (1): مخطط اختبار".encode("utf-8"), document_xml)
                rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
                self.assertIn("media/" + Path(media[0]).name, rels)


if __name__ == "__main__":
    unittest.main()
