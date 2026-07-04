import json

from docx import Document
from langchain_core.messages import HumanMessage, SystemMessage

from docx_integrator import (
    apply_replacements_to_docx,
    find_marker_spans,
    iter_all_paragraphs,
    match_tag,
)
from graph_state import GraphState
from llm_config import llm
from schemas import IntegratorOutput, TagAnswerOutput

SYSTEM_PROMPT = """\
You are the Integrator agent.

You receive marker spans from a Word template and detailed question-answers for each matched tag.
Write the ideal replacement text for each span. The replacements will be inserted into the \
original Word file — only the @ ... @@ block is replaced; surrounding text stays as-is.

Marker rules:
- @ opens an instruction block; @@ closes it.
- Match each span to the tag whose instruction text is most similar.
- Return `replacement` as the text that replaces ONLY the @ ... @@ block.
- Do NOT include @ or @@ in replacement.

Content rules:
1. Use ONLY facts from the provided question_answers. Do NOT invent information.
2. Write detailed, complete content — do not summarize or omit facts.
3. Follow the instruction and section context for format.
4. If inline=true, write a short phrase that fits naturally between text_before and text_after.
5. If inline=false, write the full section using all relevant answers with good structure.
6. Prefer Arabic when the template is Arabic.
7. Return one replacement per span_index provided.
"""


def _build_span_payloads(
    template_path: str,
    instructions,
    answers: list[TagAnswerOutput],
) -> tuple[list[dict], list[dict]]:
    doc = Document(template_path)
    paragraphs = list(iter_all_paragraphs(doc))
    spans = find_marker_spans(paragraphs)
    answers_by_tag = {answer.tag_id: answer for answer in answers}

    payloads: list[dict] = []
    for span in spans:
        tag = match_tag(span["inner"], instructions)
        if tag is None:
            continue

        answer = answers_by_tag.get(tag.tag_id)
        if answer is None:
            continue

        payloads.append(
            {
                "span_index": span["span_index"],
                "tag_id": tag.tag_id,
                "instruction": tag.instruction,
                "contexts": tag.contexts,
                "inline": span["inline"],
                "text_before": span["before"],
                "text_after": span["after"],
                "question_answers": [
                    {"question": qa.question, "answer": qa.answer}
                    for qa in answer.question_answers
                ],
            }
        )

    return spans, payloads


def integrate(state: GraphState, template_path: str, output_path: str) -> dict:
    spans, payloads = _build_span_payloads(
        template_path=template_path,
        instructions=state["instructions"],
        answers=state["answers"],
    )

    if not payloads:
        apply_replacements_to_docx(template_path, output_path, spans, {})
        return {"output_path": output_path}

    result = llm.with_structured_output(IntegratorOutput).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=f"Marker spans:\n{json.dumps(payloads, ensure_ascii=False, indent=2)}"
            ),
        ]
    )
    replacements = {item.span_index: item.replacement for item in result.replacements}
    path = apply_replacements_to_docx(template_path, output_path, spans, replacements)
    return {"output_path": path}
