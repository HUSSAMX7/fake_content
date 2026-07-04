from langchain_core.messages import HumanMessage, SystemMessage

from graph_state import GraphState
from llm_config import llm
from schemas import TemplatePlannerOutput

SYSTEM_PROMPT = """\
You are the Template Planner agent.

Your job: find every @ ... @@ marker pair in the template, extract the instruction inside each pair, \
assign tag IDs, build the silent template, and generate retrieval questions per tag.

Marker format:
- @ opens an instruction; @@ closes it.
- Instruction text may be on the same line as the markers or on following lines.
- Text may be directly adjacent to @ or @@ with no space.
- Everything from @ until the matching @@ is ONE single instruction (keep internal line breaks).
- Do NOT split one @...@@ block into multiple tags because the text is long or spans lines.

CRITICAL — do NOT hallucinate tags:
- A tag exists ONLY where the template contains a literal @ ... @@ pair.
- Count the @ ... @@ pairs in the template. marker_count MUST equal that exact count.
- instructions MUST have exactly marker_count entries (or fewer only if deduplicating identical blocks).
- If there is ONE @ ... @@ block, that is ONE tag — even when the instruction text mentions \
"المرحلة الثانية" or describes how to write multiple future phases. That wording is part of the \
instruction, NOT separate tags.
- NEVER invent TAG_07, TAG_08, etc. for phases or sections that have no @ ... @@ markers in the template.
- Static body text (paragraphs, table cells, headings) WITHOUT @ ... @@ is NOT a tag. \
For example, "خطة نقل المعرفة والتدريب" in a table is static content unless wrapped in @ ... @@.

Extraction rules:
1. Assign IDs in order of first appearance: TAG_01, TAG_02, ...
2. Copy instruction text verbatim from inside @ ... @@ — do not paraphrase or shorten.
3. If the exact same instruction appears in multiple @ ... @@ pairs, reuse the same tag_id \
in the silent template for all of them; list each surrounding section in contexts.
4. Build silent_template: identical to the original except each @ ... @@ block becomes @TAG_XX@@.
5. Do not change any text outside the markers.

Questions (per unique tag):
- 3-7 questions whose answers come from tender docs, scope of work, BOQ, or project info.
- Questions seek facts (who, what, when, deliverables), not writing instructions.
- Prefer Arabic when the template is Arabic.
"""


def plan_template(state: GraphState) -> dict:
    result = llm.with_structured_output(TemplatePlannerOutput).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Template:\n\n{state['template_text']}"),
        ]
    )

    instruction_map: dict[str, str] = {}
    questions_map: dict[str, list[str]] = {}
    contexts_map: dict[str, list[str]] = {}
    for item in result.instructions:
        instruction_map[item.tag_id] = item.instruction
        questions_map[item.tag_id] = item.questions
        contexts_map[item.tag_id] = item.contexts

    return {
        "instruction_map": instruction_map,
        "questions_map": questions_map,
        "contexts_map": contexts_map,
        "silent_template": result.silent_template,
        "marker_count": result.marker_count,
    }
