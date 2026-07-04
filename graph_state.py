from typing import TypedDict

from schemas import InstructionItem, TagAnswerOutput


class GraphState(TypedDict, total=False):
    template_text: str
    tender_text: str
    instructions: list[InstructionItem]
    answers: list[TagAnswerOutput]
    output_path: str
