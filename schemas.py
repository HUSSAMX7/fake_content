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
    marker_count: int = Field(
        description="Exact number of @ ... @@ pairs found in the template"
    )
    instructions: list[InstructionItem] = Field(
        description="One entry per @ ... @@ block in the template, in order of appearance"
    )
    silent_template: str = Field(
        description="Full template with each @ ... @@ block replaced by @TAG_XX@@ only"
    )
