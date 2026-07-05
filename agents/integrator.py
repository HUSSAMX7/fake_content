import json
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from docx_integrator import apply_replacements_to_docx, match_tag, prepare_template
from graph_state import GraphState
from llm_config import llm
from schemas import IntegratorOutput, TagAnswerOutput

SYSTEM_PROMPT = """\
You are the Integrator agent — the final document writer.

You receive marker spans from a Word template and factual research notes (question_answers) for \
each matched tag. Return structured content blocks that will be rendered into the Word file with \
proper formatting — only the @ ... @@ block is replaced; surrounding text and template design stay.

Instruction compliance (HIGHEST PRIORITY):
- Each span includes a `marker_instruction` — the exact text the template author wrote inside @ ... @@.
- This is your writing brief. Read it carefully before writing anything.
- Follow every requirement: what to write, structure, what to include or exclude, length, and tone.
- Examples:
  - "اكتب فقرة عن أهداف المشروع" → one `paragraph` block.
  - "اذكر المراحل الثلاث" → three `numbered_item` blocks (or `heading` + `paragraph` per phase).
  - "قائمة بالمخرجات" → multiple `bullet_item` or `numbered_item` blocks.
  - "جملة قصيرة" or inline=true → one short `paragraph` block.
- Use question_answers as factual material to fulfill the instruction.

Output format — structured blocks (NOT plain text):
Return a `blocks` list per span. Each block has `type` and `text`:

| type | when to use |
|------|-------------|
| paragraph | Body text, formal prose, detailed explanations |
| numbered_item | Ordered steps, phases, sequential deliverables |
| bullet_item | Unordered lists, features, requirements |
| heading | Sub-section title before related paragraphs |

Rules for blocks:
- Use multiple blocks to structure content — never cram everything into one block when a list or \
sections are appropriate.
- Each block's `text` is rich and complete — include every useful fact, never summarize.
- For `numbered_item` and `bullet_item`: do NOT prefix text with numbers, bullets (•), or dashes — \
Word adds list formatting automatically.
- For inline=true spans: return one short `paragraph` block only.
- Do NOT include @ or @@ in any block text.

Document identity:
- Content belongs inside a formal deliverable document.
- Infer document type and tone from instruction, section context, and surrounding text.
- Never reveal that facts were sourced from elsewhere.

Voice and style:
- Formal, professional language appropriate to the document type.
- NEVER use meta-phrases: "تنص المستندات", "مذكور في", "وفق ما ورد", "كما ذكر في", \
"according to", "as stated in", "referenced in".
- State each name or term once in its most official form.
- If an answer is "غير متوفر", omit that point — never surface that phrase.

Content rules:
1. Use ONLY facts from question_answers. Do NOT invent information.
2. Include EVERY useful fact — transforming style is allowed, losing content is not.
3. Match the language of the template (Arabic or English).
4. Return one replacement per span_index provided.
"""


def _build_span_payloads(
    template_path: str,
    instructions,
    answers: list[TagAnswerOutput],
) -> tuple[tempfile.TemporaryDirectory[str], Path, list[dict], list[dict]]:
    temp_dir, unpacked_dir, spans = prepare_template(template_path)
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

    return temp_dir, unpacked_dir, spans, payloads


def integrate(state: GraphState, template_path: str, output_path: str) -> dict:
    temp_dir, unpacked_dir, spans, payloads = _build_span_payloads(
        template_path=template_path,
        instructions=state["instructions"],
        answers=state["answers"],
    )

    try:
        if not payloads:
            path = apply_replacements_to_docx(
                template_path, output_path, spans, {}, unpacked_dir=unpacked_dir
            )
            return {"output_path": path}

        result = llm.with_structured_output(IntegratorOutput).invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Marker spans:\n{json.dumps(payloads, ensure_ascii=False, indent=2)}"
                ),
            ]
        )
        replacements = {item.span_index: item.blocks for item in result.replacements}
        path = apply_replacements_to_docx(
            template_path,
            output_path,
            spans,
            replacements,
            unpacked_dir=unpacked_dir,
        )
        return {"output_path": path}
    finally:
        temp_dir.cleanup()
