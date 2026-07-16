from __future__ import annotations

import hashlib
import re
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
                        if "مراحل خطة العمل" in span["inner"]
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
                    if "مراحل خطة العمل" in span["inner"]
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


if __name__ == "__main__":
    unittest.main()
