from __future__ import annotations

import unittest

from agents.integrator import _normalize_integrator_replacements
from schemas import ContentBlock, IntegratorOutput, SpanReplacement


def _paragraph(text: str) -> ContentBlock:
    return ContentBlock(type="paragraph", text=text)


class IntegratorCoverageTests(unittest.TestCase):
    def test_duplicate_span_index_keeps_first_entry(self) -> None:
        result = IntegratorOutput(
            replacements=[
                SpanReplacement(
                    span_index=17,
                    tag_id="TAG_01",
                    blocks=[_paragraph("المرحلة الأولى")],
                ),
                SpanReplacement(
                    span_index=17,
                    tag_id="TAG_01",
                    blocks=[_paragraph("نسخة مكررة")],
                ),
            ]
        )

        replacements = _normalize_integrator_replacements(result, expected={17})

        self.assertEqual(list(replacements), [17])
        self.assertEqual(replacements[17][0].text, "المرحلة الأولى")

    def test_missing_span_index_still_fails(self) -> None:
        result = IntegratorOutput(
            replacements=[
                SpanReplacement(
                    span_index=1,
                    tag_id="TAG_01",
                    blocks=[_paragraph("قيمة")],
                ),
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "missing=\\[2\\]"):
            _normalize_integrator_replacements(result, expected={1, 2})


if __name__ == "__main__":
    unittest.main()
