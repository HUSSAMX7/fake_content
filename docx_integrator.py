"""Re-exports for the docx skill integrator."""

from docx_skill_integrator import (
    apply_replacements_to_docx,
    find_marker_spans_xml,
    match_tag,
    prepare_template,
)

find_marker_spans = find_marker_spans_xml

__all__ = [
    "apply_replacements_to_docx",
    "find_marker_spans",
    "find_marker_spans_xml",
    "match_tag",
    "prepare_template",
]
