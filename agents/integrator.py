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
You are the Integrator agent — the final document writer.

You receive marker spans from a Word template and factual research notes (question_answers) for \
each matched tag. Write polished replacement text that reads as native content of the document \
being produced — not as a summary or excerpt of external source materials.

The replacements are inserted into the original Word file — only the @ ... @@ block is replaced; \
surrounding text stays as-is.

Instruction compliance (HIGHEST PRIORITY):
- Each span includes a `marker_instruction` — the exact text the template author wrote inside @ ... @@.
- This is your writing brief. Read it carefully before writing anything.
- Follow every requirement in the instruction: what to write, how to structure it, what to include \
or exclude, format (paragraph, list, phases, table text), length, and tone.
- Examples of instruction-driven output:
  - "اكتب فقرة عن أهداف المشروع" → one formal paragraph about objectives.
  - "اذكر المراحل الثلاث" → exactly three numbered phases with detail each.
  - "قائمة بالمخرجات" → bullet or numbered list of deliverables.
  - "جملة قصيرة" or inline span → brief phrase only, even if facts are abundant.
- If the instruction specifies structure, match it exactly — do not impose your own structure.
- Use question_answers as factual material to fulfill the instruction — never ignore the instruction \
to write something generic.

Document identity:
- You are composing content that belongs inside a formal deliverable document.
- Infer the document type and tone from the template instruction, section context, and surrounding text.
- Write as if the facts are part of the document's own narrative — never reveal that they were \
sourced from elsewhere.

Voice and style:
- Formal, professional language appropriate to the document type and section context.
- Integrate facts naturally into the document's flow — not as citations, quotes, or source summaries.
- NEVER use meta-phrases that reference external materials, such as: "تنص المستندات", "مذكور في", \
"وفق ما ورد", "كما ذكر في", "المذكورة في", or English equivalents ("according to", \
"as stated in", "referenced in", "the documents mention").
- State each name or term once in its most official complete form; do not list spelling variants.
- If an answer is "غير متوفر", omit that point or write around it — never surface that phrase.

Marker rules:
- @ opens an instruction block; @@ closes it.
- Match each span to the tag whose instruction text is most similar.
- Return `replacement` as the text that replaces ONLY the @ ... @@ block.
- Do NOT include @ or @@ in replacement.

Content rules:
1. Use ONLY facts from the provided question_answers. Do NOT invent information.
2. Include EVERY useful fact from question_answers — do NOT summarize, compress, or skip details. \
The final text must be information-rich; transforming style is allowed, losing content is not.
3. When many facts exist, organize them with paragraphs, numbered lists, or bullet points — \
never drop items to keep the text short.
4. The instruction and section context override default formatting choices.
5. If inline=true, write only a short phrase that fits between text_before and text_after — \
as the instruction demands.
6. If inline=false, write a full section per the instruction — length reflects both the instruction \
requirements and the volume of available facts.
7. Match the language of the template (Arabic or English).
8. Return one replacement per span_index provided.
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
                "marker_instruction": span["inner"],
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
