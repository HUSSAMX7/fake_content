from typing import TypedDict


class GraphState(TypedDict, total=False):
    template_text: str
    instruction_map: dict[str, str]
    questions_map: dict[str, list[str]]
    contexts_map: dict[str, list[str]]
    silent_template: str
    marker_count: int
