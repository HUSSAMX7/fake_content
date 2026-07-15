"""Run the proposal generation pipeline on local file paths."""

from __future__ import annotations

from pathlib import Path

from agents.answer_agent import fill_answers
from agents.integrator import integrate
from agents.template_planner import plan_template
from docx_integrator import prepare_template
from document_loader import load_documents
from docx_utils import load_docx


def run_pipeline(
    template_path: str | Path,
    resource_paths: list[str | Path],
    output_path: str | Path,
) -> Path:
    template_path = str(template_path)
    resource_paths_str = [str(path) for path in resource_paths]
    output_path = str(output_path)

    template_text = load_docx(template_path)
    inventory_dir, _, marker_spans = prepare_template(template_path)
    try:
        if not marker_spans:
            raise ValueError("Template does not contain any valid @...@@ marker spans")
        state: dict = {
            **plan_template({"template_text": template_text, "marker_spans": marker_spans}),
            "template_text": template_text,
            "marker_spans": marker_spans,
        }
    finally:
        inventory_dir.cleanup()
    state["tender_text"] = load_documents(resource_paths_str)
    state = {**state, **fill_answers(state)}
    state = {**state, **integrate(state, template_path, output_path)}
    return Path(state["output_path"])


def template_has_markers(template_path: str | Path) -> bool:
    temp_dir, _, spans = prepare_template(str(template_path))
    try:
        return bool(spans)
    finally:
        temp_dir.cleanup()
