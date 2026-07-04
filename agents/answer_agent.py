import json

from langchain_core.messages import HumanMessage, SystemMessage

from graph_state import GraphState
from llm_config import llm
from schemas import AllTagsAnswerOutput

SYSTEM_PROMPT = """\
You are the Answer Agent.

You receive full source documents (tender, scope of work, BOQ, etc.) and a list of template tags, \
each with its questions.

Rules:
1. Read the entire source documents provided once.
2. For EVERY tag in the instructions list, answer all of its questions using ONLY the source documents.
3. Do NOT summarize, shorten, omit, or paraphrase away details. Include ALL relevant facts, \
numbers, dates, lists, deliverables, requirements, and conditions exactly as they appear or \
with full faithful detail.
4. If information spans multiple sections or files, combine ALL of it in that question's answer.
5. If the documents do not contain the answer, write exactly: "غير مذكور في المستند".
6. Do NOT invent or assume information not present in the documents.
7. Return one answers entry per tag, in the same order as the instructions list.
8. For each tag, return one answer per question in the same order as that tag's questions list.
9. Prefer Arabic when the document and template are Arabic.
"""


def fill_answers(state: GraphState) -> dict:
    tags_json = json.dumps(
        [tag.model_dump() for tag in state["instructions"]],
        ensure_ascii=False,
        indent=2,
    )
    result = llm.with_structured_output(AllTagsAnswerOutput).invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Instructions:\n{tags_json}\n\n"
                    f"--- Source documents ---\n\n{state['tender_text']}"
                )
            ),
        ]
    )
    return {"answers": result.answers}
