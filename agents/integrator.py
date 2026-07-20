import json
import tempfile
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from agents.chart_agent import prepare_charts_for_replacements
from agents.image_agent import generate_images_for_replacements
from docx_integrator import apply_replacements_to_docx, match_tag, prepare_template
from graph_state import GraphState
from llm_config import invoke_structured
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
| ولد صورة / أدرج شكلاً / رسم توضيحي (غير بياني) | include one `image` block (see Image rules) |
| شارت / مخطط بياني / رسم بياني / كميات / نسب / سمارت شارت | include one `chart` block (see Chart rules) — NOT `image` |
| figure as main deliverable with little/no follow-up text | FIGURE-ONLY mode (see Image rules) |
| smart chart as main deliverable | CHART mode (see Chart rules) |
| inline field (مدة، اسم) | one short `paragraph` when inline=true — never `image`/`chart` |
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

Return a `blocks` list per span. Each block has `type` and `text` \
(plus chart fields when type is `chart`, or `image_prompt` when type is `image`):

| type | when to use |
|------|-------------|
| paragraph | Body text, formal prose, detailed explanations |
| numbered_item | Ordered steps or sequential items |
| bullet_item | Unordered lists, sub-points, activities, deliverables |
| heading | Phase title or sub-section title |
| chart | Smart programmatic chart/flowchart from structured source data |
| image | AI illustrative figure ONLY when not a data chart / smart chart |

### Chart rules (native editable Word charts — NOT AI image generation)

Emit a `chart` block when `marker_instruction` asks for a smart/data chart, e.g. \
شارت، سمارت شارت، مخطط بياني، رسم بياني، أعمدة، دائري، نسب، كميات، \
or a programmatic flowchart of ordered phases/steps from sources.

These charts are inserted as real Office charts (resizable + Edit Data in Word). \
Do not emit an `image` block for the same request.

For a chart block:
- `text`: formal Arabic caption under the chart
- `chart_kind`: one of bar, barh, pie, line, flow
  - bar/barh/pie/line: quantitative series from question_answers
  - flow: ordered phase/step names as a programmatic flowchart (no invented numbers)
- `chart_title`: optional short Arabic title drawn on the chart
- `chart_labels`: official category/phase names from question_answers only
- `chart_values`: numbers aligned with labels (required for bar/barh/pie/line; omit for flow)
- Never invent labels or numbers missing from question_answers.
- Do NOT set `image_path`. Never emit `image` for the same request when a chart fits.
- Never emit `chart` when inline=true.
- At most one `chart` block per span unless the instruction asks for multiple charts.

CHART mode (when the section is mainly the chart):
1. optional: one short intro `paragraph` (one sentence max)
2. one `chart` block
3. NOTHING else

### Image rules (AI figures — not for data charts)

Emit an `image` block ONLY when `marker_instruction` clearly asks for an illustrative \
AI figure (not a smart/data chart), e.g. ولد صورة، أدرج صورة/شكلاً، رسم توضيحي، \
diagram, infographic — AND it is NOT asking for شارت/مخطط بياني/كميات/نسب.

For an image block:
- `text`: formal Arabic caption under the figure ONLY (e.g. «شكل (1): محاور العمل الرئيسية»)
- `image_prompt`: precise visual description grounded in question_answers \
  (real official Arabic names from sources). Describe boxes, arrows, RTL layout. \
  Labels inside the figure must use the official Arabic names from question_answers — \
  do NOT translate stage/axis names into English unless the sources are English. \
  Do not invent phases, entities, or facts missing from question_answers.
- Do NOT set `image_path` — it is filled later by the system.
- Never emit `image` when inline=true.
- At most one `image` block per span unless the instruction explicitly asks for multiple figures.

FIGURE-ONLY mode (when intended for AI figures, not smart charts):
When marker_instruction's intent is that the section is mainly an AI visual figure \
(with at most a short intro and a caption), return EXACTLY:
1. optional: one short intro `paragraph` (one sentence max) ONLY if useful/requested
2. one `image` block
3. NOTHING else — no headings, no lettered lists, no deliverables, no phase summaries
Judge by intent even if wording differs across templates.
If the instruction clearly wants a figure AND substantial explanatory text after it, \
do not use FIGURE-ONLY — emit image plus the requested text.
If the instruction wants a smart/data chart, use a `chart` block instead of `image`.

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
Judge the author's intent from meaning — wording varies across templates.

mode = chart:
- The marker asks for a smart/data chart or programmatic phase flowchart \
(شارت، سمارت شارت، مخطط بياني، رسم بياني، أعمدة، دائري، نسب، كميات، \
or ordered stages rendered as a chart — NOT AI image generation).
- At most one short intro sentence plus the chart (caption on the chart block).
- Prefer chart over figure_only whenever quantitative data or a smart chart is intended.
- items = []

mode = figure_only:
- The marker's primary deliverable is an AI illustrative figure/diagram/infographic \
(NOT a smart/data chart).
- Body prose, lettered lists, phase writeups, or deliverable dumps after the figure are NOT wanted.
- At most one short intro sentence plus the figure (caption belongs on the image block).
- items = []

mode = single_pass (default):
- Summary, list, short paragraphs, inline text, one unified section, OR a figure/chart that is \
explicitly accompanied by requested explanatory text after it.
- items = []

mode = sequential_full_depth (rare):
- ONLY when marker_instruction explicitly requires EACH phase/section at full sub-structure \
(goal, من خلال, activities, deliverables / تفصيل كل مرحلة).
- Never choose this when the marker is mainly asking for a figure or chart.
- items = ordered official phase/section names from question_answers.

Prefer chart over figure_only when the instruction is about smart/data charts. \
Prefer figure_only over single_pass when the instruction centers on an AI figure and \
restricts or omits post-figure writing. Prefer single_pass when both a visual and substantial \
follow-up text are clearly requested.
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


def _normalize_integrator_replacements(
    result: IntegratorOutput,
    expected: set[int],
) -> dict[int, list[ContentBlock]]:
    replacements: dict[int, list[ContentBlock]] = {}
    for item in result.replacements:
        if item.span_index not in expected:
            continue
        # Models sometimes emit the same span_index twice; keep the first usable entry.
        if item.span_index in replacements:
            continue
        replacements[item.span_index] = item.blocks

    missing = sorted(expected - set(replacements))
    if missing:
        raise RuntimeError(f"Integrator coverage failure; missing={missing}")

    empty = [
        index
        for index, blocks in replacements.items()
        if not blocks or not any(_block_has_content(block) for block in blocks)
    ]
    if empty:
        raise RuntimeError(f"Integrator returned blank replacement(s): {empty}")

    invalid_images = [
        index
        for index, blocks in replacements.items()
        for block in blocks
        if block.type == "image"
        and not (block.image_prompt or "").strip()
        and not (block.image_path or "").strip()
    ]
    if invalid_images:
        raise RuntimeError(
            f"Integrator image block(s) missing image_prompt: {sorted(set(invalid_images))}"
        )

    invalid_charts = [
        index
        for index, blocks in replacements.items()
        for block in blocks
        if block.type == "chart" and not _chart_block_is_valid(block)
    ]
    if invalid_charts:
        raise RuntimeError(
            f"Integrator chart block(s) missing chart fields: {sorted(set(invalid_charts))}"
        )
    return replacements


def _chart_block_is_valid(block: ContentBlock) -> bool:
    if not block.chart_kind or not block.chart_labels:
        return False
    if block.chart_kind == "flow":
        return True
    values = block.chart_values or []
    return bool(values) and len(values) == len(block.chart_labels)


def _block_has_content(block: ContentBlock) -> bool:
    if block.type == "image":
        return bool(
            (block.image_prompt or "").strip()
            or (block.image_path or "").strip()
            or block.text.strip()
        )
    if block.type == "chart":
        return _chart_block_is_valid(block) or bool(block.text.strip())
    return bool(block.text.strip())


def _short_intro_paragraph(blocks: list[ContentBlock]) -> ContentBlock | None:
    for block in blocks:
        if block.type != "paragraph":
            continue
        text = block.text.strip()
        if text and len(text) <= 220:
            return ContentBlock(type="paragraph", text=text)
    return None


def _enforce_figure_only_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Keep at most one short intro paragraph + one image; drop everything else."""

    images = [block for block in blocks if block.type == "image"]
    if not images:
        return blocks

    intro = _short_intro_paragraph(blocks)
    enforced = [intro] if intro is not None else []
    enforced.append(images[0])
    return enforced


def _enforce_chart_blocks(blocks: list[ContentBlock]) -> list[ContentBlock]:
    """Keep at most one short intro paragraph + one chart; drop everything else."""

    charts = [block for block in blocks if block.type == "chart"]
    if not charts:
        return blocks

    intro = _short_intro_paragraph(blocks)
    enforced = [intro] if intro is not None else []
    enforced.append(charts[0])
    return enforced


def _invoke_integrator(payloads: list[dict]) -> dict[int, list[ContentBlock]]:
    result = invoke_structured(
        IntegratorOutput,
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Marker spans:\n{json.dumps(payloads, ensure_ascii=False, indent=2)}"),
        ],
    )
    expected = {payload["span_index"] for payload in payloads}
    return _normalize_integrator_replacements(result, expected)


def _writing_plan(payload: dict) -> SpanWritingPlan:
    if payload["inline"]:
        return SpanWritingPlan(mode="single_pass", items=[])

    try:
        plan = invoke_structured(
            SpanWritingPlan,
            [
                SystemMessage(content=WRITING_PLAN_PROMPT),
                HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
            ],
        )
        if plan.mode == "chart":
            return SpanWritingPlan(mode="chart", items=[])
        if plan.mode == "figure_only":
            return SpanWritingPlan(mode="figure_only", items=[])
        if plan.mode == "sequential_full_depth" and plan.items:
            return SpanWritingPlan(mode="sequential_full_depth", items=plan.items)
        return SpanWritingPlan(mode="single_pass", items=[])
    except Exception:
        # Prefer completing generation over failing the whole request on a planning parse error.
        return SpanWritingPlan(mode="single_pass", items=[])


def _generate_blocks_for_payload(payload: dict) -> list[ContentBlock]:
    plan = _writing_plan(payload)
    if plan.mode == "chart":
        blocks = _invoke_integrator([payload]).get(payload["span_index"], [])
        return _enforce_chart_blocks(blocks)
    if plan.mode == "figure_only":
        blocks = _invoke_integrator([payload]).get(payload["span_index"], [])
        return _enforce_figure_only_blocks(blocks)

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

        image_dir = unpacked_dir.parent / "generated_images"
        replacements = prepare_charts_for_replacements(replacements)
        replacements = generate_images_for_replacements(replacements, image_dir)

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
