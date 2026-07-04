from pydantic import BaseModel, Field


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
