from pydantic import BaseModel, Field
from typing import Literal


class InstructionItem(BaseModel):
    tag_id: str = Field(description="Placeholder ID, e.g. TAG_01")
    instruction: str = Field(
        description="Verbatim instruction text copied exactly from inside @ ... @@"
    )
    contexts: list[str] = Field(
        description="Surrounding section headings where this @ ... @@ block appears"
    )
    questions: list[str] = Field(
        description="3-7 retrieval questions answerable from tender docs or project info"
    )


class TemplatePlannerOutput(BaseModel):
    instructions: list[InstructionItem] = Field(
        description="One entry per @ ... @@ block in the template, in order of appearance"
    )


class QuestionAnswerItem(BaseModel):
    question: str
    answer: str = Field(
        description="Full detailed answer extracted from the source document. No summarization."
    )


class TagAnswerOutput(BaseModel):
    tag_id: str
    question_answers: list[QuestionAnswerItem] = Field(
        description="Full detailed answer for each question, in the same order as provided"
    )


class AllTagsAnswerOutput(BaseModel):
    answers: list[TagAnswerOutput] = Field(
        description="One entry per tag in the instructions list, same order"
    )


class ContentBlock(BaseModel):
    type: Literal["paragraph", "numbered_item", "bullet_item", "heading"] = Field(
        description=(
            "paragraph: body text. numbered_item: ordered list entry. "
            "bullet_item: bullet list entry. heading: section sub-heading."
        )
    )
    text: str = Field(
        description="Block text at the depth required by marker_instruction."
    )


class SpanReplacement(BaseModel):
    span_index: int
    tag_id: str
    blocks: list[ContentBlock] = Field(
        description=(
            "Structured content replacing the @ ... @@ block. Must follow marker_instruction. "
            "Include every useful fact — use multiple blocks for paragraphs, lists, or phases."
        )
    )


class IntegratorOutput(BaseModel):
    replacements: list[SpanReplacement] = Field(
        description="One replacement per marker span"
    )


class SpanWritingPlan(BaseModel):
    mode: Literal["single_pass", "sequential_full_depth"] = Field(
        description=(
            "single_pass: one writing call; follow marker_instruction depth exactly "
            "(summary list, short paragraphs, inline field, etc.). "
            "sequential_full_depth: write each item in a separate call at maximum depth — "
            "only when marker_instruction explicitly requires rich per-item structure "
            "(e.g. per-phase goal, من خلال, activities, deliverables)."
        )
    )
    items: list[str] = Field(
        description=(
            "Ordered official phase/section names. Required for sequential_full_depth. "
            "Empty for single_pass."
        )
    )
