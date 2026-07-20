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
    tag_id: str = Field(description="Exact tag id from the instructions list, e.g. TAG_01")
    question_answers: list[QuestionAnswerItem] = Field(
        description=(
            "Nested list only — one {question, answer} per question for THIS tag. "
            "Do not place these objects at the top-level answers array."
        )
    )


class AllTagsAnswerOutput(BaseModel):
    answers: list[TagAnswerOutput] = Field(
        description=(
            "One TagAnswerOutput object per tag, same order as instructions. "
            "Each element must include tag_id and question_answers. "
            "Do not insert bare question/answer dicts into this list."
        )
    )


class ContentBlock(BaseModel):
    type: Literal[
        "paragraph",
        "numbered_item",
        "bullet_item",
        "heading",
        "image",
        "chart",
    ] = Field(
        description=(
            "paragraph: body text. numbered_item: ordered list entry. "
            "bullet_item: bullet list entry. heading: section sub-heading. "
            "image: AI-generated illustrative figure (not for data charts). "
            "chart: smart native Word chart from structured data "
            "(bar/barh/pie/line/flow) — editable and resizable in Word; never invent numbers."
        )
    )
    text: str = Field(
        description=(
            "Block text at the depth required by marker_instruction. "
            "For image/chart blocks: formal Arabic caption under the figure."
        )
    )
    image_prompt: str | None = Field(
        default=None,
        description=(
            "Required for AI image blocks. Precise visual prompt for image generation. "
            "Unused for chart blocks."
        ),
    )
    image_path: str | None = Field(
        default=None,
        description="Filled after image/chart rendering with a local PNG path. Never emit this field.",
    )
    chart_kind: Literal["bar", "barh", "pie", "line", "flow"] | None = Field(
        default=None,
        description=(
            "Required for chart blocks. bar/barh/pie/line for numeric series; "
            "flow for ordered process/phase steps as a programmatic flowchart."
        ),
    )
    chart_title: str | None = Field(
        default=None,
        description="Optional Arabic chart title drawn above the chart.",
    )
    chart_labels: list[str] | None = Field(
        default=None,
        description="Category/phase labels from sources only. Required for chart blocks.",
    )
    chart_values: list[float] | None = Field(
        default=None,
        description=(
            "Numeric values aligned with chart_labels. Required for bar/barh/pie/line. "
            "Empty/omitted for flow charts."
        ),
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
    mode: Literal[
        "single_pass",
        "sequential_full_depth",
        "figure_only",
        "chart",
    ] = Field(
        description=(
            "single_pass: one writing call; follow marker_instruction depth exactly. "
            "figure_only: AI illustrative figure as main deliverable (not quantitative charts). "
            "chart: smart native Word chart/flowchart from source data — editable in Word, "
            "not AI image generation. "
            "sequential_full_depth: rich per-item writing only when explicitly required. "
            "Judge intent from meaning, not fixed keywords."
        )
    )
    items: list[str] = Field(
        description=(
            "Ordered official phase/section names. Required for sequential_full_depth. "
            "Empty for single_pass, figure_only, and chart."
        )
    )
