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

    def test_image_block_requires_image_prompt(self) -> None:
        result = IntegratorOutput(
            replacements=[
                SpanReplacement(
                    span_index=1,
                    tag_id="TAG_01",
                    blocks=[
                        ContentBlock(type="image", text="شكل (1)", image_prompt=None),
                    ],
                ),
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "missing image_prompt"):
            _normalize_integrator_replacements(result, expected={1})

    def test_image_block_with_prompt_is_accepted(self) -> None:
        result = IntegratorOutput(
            replacements=[
                SpanReplacement(
                    span_index=1,
                    tag_id="TAG_01",
                    blocks=[
                        ContentBlock(
                            type="image",
                            text="شكل (1): المراحل",
                            image_prompt="Horizontal flowchart of four project phases",
                        ),
                    ],
                ),
            ]
        )

        replacements = _normalize_integrator_replacements(result, expected={1})
        self.assertEqual(replacements[1][0].type, "image")
        self.assertTrue(replacements[1][0].image_prompt)


if __name__ == "__main__":
    unittest.main()
