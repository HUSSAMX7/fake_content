from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table
from docx.text.paragraph import Paragraph


def _iter_block_items(parent):
    parent_elm = parent.element.body if hasattr(parent, "element") else parent._tc
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _block_text(block) -> str:
    if isinstance(block, Paragraph):
        return block.text
    lines: list[str] = []
    for row in block.rows:
        cells = [c.text.strip() for c in row.cells]
        if any(cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def load_docx(path: str) -> str:
    doc = Document(path)
    parts: list[str] = []
    for block in _iter_block_items(doc):
        text = _block_text(block).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)
