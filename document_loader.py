from pathlib import Path

import fitz

from docx_utils import load_docx


def load_document(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix == ".docx":
        return load_docx(path)
    raise ValueError(f"Unsupported file type: {suffix}. Use .pdf or .docx")


def load_documents(paths: list[str]) -> str:
    parts: list[str] = []
    for path in paths:
        text = load_document(path)
        parts.append(f"=== {Path(path).name} ===\n\n{text}")
    return "\n\n".join(parts)


def parse_paths(value: str) -> list[str]:
    if not value.strip():
        return []
    for separator in (";", "\n", "|"):
        if separator in value:
            return [part.strip() for part in value.split(separator) if part.strip()]
    return [value.strip()]


def _load_pdf(path: str) -> str:
    doc = fitz.open(path)
    parts: list[str] = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            parts.append(text)
    doc.close()
    return "\n\n".join(parts)
