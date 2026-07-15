import json

from langchain_core.messages import HumanMessage, SystemMessage

from graph_state import GraphState
from llm_config import invoke_structured
from schemas import InstructionItem, TemplatePlannerOutput

SYSTEM_PROMPT = """\
You are the Template Planner agent.

Your job: find every @ ... @@ marker pair in the template, extract the instruction inside each pair, \
assign tag IDs, and generate retrieval questions per tag.

Marker format:
- @ opens an instruction; @@ closes it.
- Instruction text may be on the same line as the markers or on following lines.
- Text may be directly adjacent to @ or @@ with no space.
- Everything from @ until the matching @@ is ONE single instruction (keep internal line breaks).
- Do NOT split one @...@@ block into multiple tags because the text is long or spans lines.

CRITICAL — do NOT hallucinate tags:
- A tag exists ONLY where the template contains a literal @ ... @@ pair.
- If there is ONE @ ... @@ block, that is ONE tag — even when the instruction text mentions \
"المرحلة الثانية" or describes how to write multiple future phases. That wording is part of the \
instruction, NOT separate tags.
- NEVER invent tags for phases or sections that have no @ ... @@ markers in the template.
- Static body text (paragraphs, table cells, headings) WITHOUT @ ... @@ is NOT a tag. \
For example, "خطة نقل المعرفة والتدريب" in a table is static content unless wrapped in @ ... @@.

Extraction rules:
1. Assign IDs in order of first appearance: TAG_01, TAG_02, ...
2. Copy instruction text verbatim from inside @ ... @@ — do not paraphrase or shorten.
3. If the exact same instruction appears in multiple @ ... @@ pairs, reuse the same tag_id \
and list each surrounding section in contexts.
4. Return one instructions entry per unique tag.

Questions (per unique tag):
- Read the instruction inside @ ... @@ first — questions must gather the facts needed to fulfill \
that specific instruction.
- 3-7 questions whose answers supply what the instruction asks for (scope, entities, deliverables, \
timelines, requirements, etc.).
- Questions seek facts, not writing instructions — but must align with what the instruction requires.
- Match the language of the template (Arabic or English).
"""


def _canonical_inventory(spans: list[dict]) -> list[InstructionItem]:
    """Assign stable IDs from the OOXML inventory, never from model output."""

    by_instruction: dict[str, InstructionItem] = {}
    for span in spans:
        instruction = span["inner"].strip()
        key = " ".join(instruction.split())
        if key not in by_instruction:
            by_instruction[key] = InstructionItem(
                tag_id=f"TAG_{len(by_instruction) + 1:02d}",
                instruction=instruction,
                contexts=[],
                questions=[],
            )
        by_instruction[key].contexts.append(f"{span['part']}:{span['start']}")
    return list(by_instruction.values())


def plan_template(state: GraphState) -> dict:
    spans = state.get("marker_spans")
    if not spans:
        # Compatibility for callers outside the production pipeline.
        result = invoke_structured(
            TemplatePlannerOutput,
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"Template:\n\n{state['template_text']}"),
            ],
        )
        return {"instructions": result.instructions}

    inventory = _canonical_inventory(spans)
    inventory_json = json.dumps(
        [
            {
                "tag_id": item.tag_id,
                "instruction": item.instruction,
                "contexts": item.contexts,
            }
            for item in inventory
        ],
        ensure_ascii=False,
        indent=2,
    )
    result = invoke_structured(
        TemplatePlannerOutput,
        [
            SystemMessage(
                content=(
                    "You are given the complete, deterministic marker inventory. "
                    "Do not discover, omit, merge, rename, paraphrase, or invent tags. "
                    "Return exactly one entry for every supplied instruction and only "
                    "generate its retrieval questions.\n\n" + SYSTEM_PROMPT
                )
            ),
            HumanMessage(content=f"Marker inventory:\n{inventory_json}"),
        ],
    )
    returned = {" ".join(item.instruction.split()): item for item in result.instructions}
    expected = {" ".join(item.instruction.split()) for item in inventory}
    if set(returned) != expected or len(returned) != len(result.instructions):
        missing = sorted(expected - set(returned))
        extra = sorted(set(returned) - expected)
        duplicates = len(result.instructions) - len(returned)
        raise RuntimeError(
            f"Template planner coverage failure; missing={missing}, extra={extra}, duplicates={duplicates}"
        )

    # Keep IDs, instruction text, and locations from the XML inventory even if a
    # model changes whitespace or IDs in its structured response.
    instructions = [
        item.model_copy(
            update={"questions": returned[" ".join(item.instruction.split())].questions}
        )
        for item in inventory
    ]
    return {"instructions": instructions}
