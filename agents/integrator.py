import json
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from docx_integrator import apply_replacements_to_docx, match_tag, prepare_template
from graph_state import GraphState
from llm_config import llm
from schemas import ContentBlock, IntegratorOutput, SpanWritingPlan, TagAnswerOutput

SYSTEM_PROMPT = """\
You are the Integrator agent — the final writer for formal technical proposals (عروض فنية).

You receive marker spans from a Word template and factual research notes (question_answers) for \
each matched tag. Your output is rendered into the Word file — only the @ ... @@ block is replaced; \
surrounding text, tables, headers, and template design stay unchanged.

## How to read inputs

Each span provides:
- `marker_instruction`: the section writing specification from the template author.
- `contexts`, `text_before`, `text_after`: where this block sits in the document.
- `inline`: true = replace with a short phrase/sentence inside existing text; false = full section.
- `question_answers`: exhaustive research facts extracted from tender/source documents.
- `current_item` (optional): when present, write ONLY this one phase/section at full depth; \
other items in the same span are written in separate passes.

## marker_instruction (HIGHEST PRIORITY — overrides everything below)

`marker_instruction` defines WHAT to write, HOW to structure it, and HOW DEEP to go. \
Follow its depth exactly — do not write more detail than requested, and do not write less.

Depth signals in marker_instruction (follow literally):
- "ملخص"، "قائمة"، "شرح بسيط"، "سطر"، "فقرة أو فقرتين"، "جملة واحدة" → concise output
- "تفصيل"، "غني بالتفاصيل"، "لكل مرحلة: عنوان/هدف/من خلال/إنجازات" → rich output

- Write final proposal prose — never copy instruction wording, author notes, or placeholder syntax \
into the output.
- Placeholders like [رقم], [اسم], مثلا، ... describe the intended FORMAT — follow the format, \
not the placeholder text.
- Author shorthand (تحط، هنا، بسيط، سطر كذا) is guidance for you, not text for the document.
- Use `contexts` and surrounding text to match the section type (overview, scope, phases, etc.).

## Universal quality standard (all proposals, all sectors)

Write at the level of a winning Saudi government technical proposal:
- Formal, confident, professional tone in the template language.
- Include every useful fact from question_answers that fits the requested depth.
- Match length and detail to marker_instruction — summarize when asked, expand when asked.
- Include concrete details when depth allows: names, deliverables, timelines, standards.
- Use full sentences appropriate to the requested depth.
- Do not repeat the same sentence in different parts of one section.
- If an answer is "غير متوفر", omit that point silently.

## Structure patterns (apply ONLY when marker_instruction implies that depth)

| Instruction signals | Block pattern |
|---------------------|---------------|
| 2–3 فقرات، نبذة | 2–3 `paragraph` blocks per instruction limits |
| فقرة أو فقرتين، ملخص نطاق | 1–2 `paragraph` blocks |
| قائمة أهداف، جملة واحدة لكل هدف | `bullet_item` per objective — one sentence each |
| قائمة + شرح بسيط عن كل مرحلة | `numbered_item` per phase — name + 1–2 sentence explanation |
| inline field (مدة، اسم) | one short `paragraph` when inline=true |
| تفصيل كل مرحلة + لكل مرحلة: هدف/من خلال/إنجازات | full phase pattern below |

Full phase pattern (ONLY when marker_instruction requires per-phase detail):
- `heading`: المرحلة [رقم]: [الاسم الرسمي]
- `paragraph`: الهدف من هذه المرحلة هو... (3–5 sentences)
- `paragraph`: من خلال:
- `bullet_item` per major activity — each 2–4 sentences with (مثال: ...) when facts allow
- `paragraph`: إنجازات المرحلة:
- `bullet_item` per BOQ deliverable

When `current_item` is set: write ONLY that one phase/section at the depth marker_instruction \
requires for a single item.

## Output format — structured blocks

Return a `blocks` list per span. Each block has `type` and `text`:

| type | when to use |
|------|-------------|
| paragraph | Body text, formal prose, detailed explanations |
| numbered_item | Ordered steps or sequential items |
| bullet_item | Unordered lists, sub-points, activities, deliverables |
| heading | Phase title or sub-section title |

Block rules:
- Use multiple blocks when structure, phases, or lists are implied.
- For `numbered_item` and `bullet_item`: do NOT prefix with numbers, bullets (•), or dashes — \
Word handles list formatting.
- For inline=true: one short `paragraph` only.
- Do NOT include @ or @@ in any block text.

## Voice

- Never use meta-phrases: "تنص المستندات", "مذكور في", "وفق ما ورد", "كما ذكر في", \
"according to", "as stated in", "referenced in".
- State each official name or term once in its most complete form.
- Content reads as if written directly for the proposal — not extracted from elsewhere.

## Content fidelity

1. Use ONLY facts from question_answers. Do NOT invent information.
2. Transforming style and weaving facts into prose is required; losing facts is forbidden.
3. Match the language of the template (Arabic or English).
4. Return one replacement per span_index in the request.
"""

WRITING_PLAN_PROMPT = """\
Read the marker span and decide how the Integrator should write it.

mode = single_pass (default):
- marker_instruction asks for summary, list, simple explanation, short paragraphs, inline text, \
or one unified section — even if it mentions multiple phases.
- Examples: "قائمة + شرح بسيط"، "ملخص"، "فقرة أو فقرتين"، "2-3 فقرات"، "جملة واحدة لكل هدف"
- items = []

mode = sequential_full_depth (rare — only when instruction explicitly demands rich per-item structure):
- marker_instruction requires EACH phase/section written with full sub-structure: goal, من خلال, \
activities, deliverables, or says "تفصيل كل مرحلة" / "غني بالتفاصيل" with per-phase breakdown.
- items = ordered official phase/section names from question_answers (from كراسة/BOQ).

Never use sequential_full_depth for summary or list-style instructions.
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
            raise RuntimeError(
                f"No deterministic instruction match for marker {span['span_index']}: {span['inner']!r}"
            )

        answer = answers_by_tag.get(tag.tag_id)
        if answer is None:
            raise RuntimeError(f"Missing research answer for {tag.tag_id}")

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


def _invoke_integrator(payloads: list[dict]) -> dict[int, list[ContentBlock]]:
    result = llm.with_structured_output(IntegratorOutput).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Marker spans:\n{json.dumps(payloads, ensure_ascii=False, indent=2)}"),
        ]
    )
    expected = {payload["span_index"] for payload in payloads}
    returned = [item.span_index for item in result.replacements]
    duplicate_ids = {index for index in returned if returned.count(index) > 1}
    actual = set(returned)
    if actual != expected or duplicate_ids:
        raise RuntimeError(
            "Integrator coverage failure; "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}, "
            f"duplicates={sorted(duplicate_ids)}"
        )
    replacements = {item.span_index: item.blocks for item in result.replacements}
    empty = [
        index
        for index, blocks in replacements.items()
        if not blocks or not any(block.text.strip() for block in blocks)
    ]
    if empty:
        raise RuntimeError(f"Integrator returned blank replacement(s): {empty}")
    return replacements


def _writing_plan(payload: dict) -> SpanWritingPlan:
    if payload["inline"]:
        return SpanWritingPlan(mode="single_pass", items=[])

    return llm.with_structured_output(SpanWritingPlan).invoke(
        [
            SystemMessage(content=WRITING_PLAN_PROMPT),
            HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
        ]
    )


def _generate_blocks_for_payload(payload: dict) -> list[ContentBlock]:
    plan = _writing_plan(payload)
    if plan.mode != "sequential_full_depth" or len(plan.items) <= 1:
        return _invoke_integrator([payload]).get(payload["span_index"], [])

    blocks: list[ContentBlock] = []
    for item in plan.items:
        focused = {**payload, "current_item": item.strip()}
        item_blocks = _invoke_integrator([focused]).get(payload["span_index"], [])
        blocks.extend(item_blocks)
    return blocks


def integrate(state: GraphState, template_path: str, output_path: str) -> dict:
    temp_dir, unpacked_dir, spans, payloads = _build_span_payloads(
        template_path=template_path,
        instructions=state["instructions"],
        answers=state["answers"],
    )

    try:
        expected_span_ids = {span["span_index"] for span in spans}
        payload_span_ids = {payload["span_index"] for payload in payloads}
        if payload_span_ids != expected_span_ids:
            raise RuntimeError(
                "Marker payload coverage failure; "
                f"missing={sorted(expected_span_ids - payload_span_ids)}, "
                f"extra={sorted(payload_span_ids - expected_span_ids)}"
            )

        inline_payloads = [p for p in payloads if p["inline"]]
        block_payloads = [p for p in payloads if not p["inline"]]

        replacements: dict[int, list[ContentBlock]] = {}
        if inline_payloads:
            replacements.update(_invoke_integrator(inline_payloads))

        for payload in block_payloads:
            replacements[payload["span_index"]] = _generate_blocks_for_payload(payload)

        if set(replacements) != expected_span_ids:
            raise RuntimeError(
                "Replacement coverage failure; "
                f"missing={sorted(expected_span_ids - set(replacements))}"
            )

        path = apply_replacements_to_docx(
            template_path,
            output_path,
            spans,
            replacements,
            unpacked_dir=unpacked_dir,
        )
        verify_dir, _, remaining = prepare_template(path)
        try:
            if remaining:
                raise RuntimeError(
                    f"Output still contains marker spans: {[span['span_index'] for span in remaining]}"
                )
        finally:
            verify_dir.cleanup()
        return {"output_path": path}
    finally:
        temp_dir.cleanup()
