from typing import TypedDict


class GraphState(TypedDict, total=False):
    template_text: str
    instruction_map: dict[str, str]
    silent_template: str
