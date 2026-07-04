from langchain_core.messages import HumanMessage, SystemMessage

from graph_state import GraphState
from llm_config import llm
from schemas import SmartParserOutput

SYSTEM_PROMPT = """\
You are the Smart Parser agent.

Extract every human instruction marked with @ (open) and @@ (close) from the template.

Marker format:
- @ opens an instruction; @@ closes it.
- Instruction text may be on the same line as the markers or on following lines.
- Text may be directly adjacent to @ or @@ with no space (e.g. @كتابة نبذة@@ or @\\nالهدف الأول\\n@@).
- Everything from @ until the matching @@ is ONE single instruction (keep internal line breaks).
- Do NOT split one @...@@ block into multiple tags just because the text spans several lines.
- Ignore any text that is NOT inside a @ ... @@ pair.

Rules:
1. Assign unique IDs in order: TAG_01, TAG_02, TAG_03, ...
2. If the exact same instruction appears more than once, reuse the same ID.
3. Build a silent template: same content as the original, but replace each full @ ... @@ block with @TAG_XX@@ only.
4. Do not change any text outside the markers.
5. Return an empty instructions list if no @ ... @@ placeholders exist.
"""


def parse_template(state: GraphState) -> dict:
    result = llm.with_structured_output(SmartParserOutput).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Template:\n\n{state['template_text']}"),
        ]
    )
    return {
        "instruction_map": {
            item.tag_id: item.instruction for item in result.instructions
        },
        "silent_template": result.silent_template,
    }
