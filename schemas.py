from pydantic import BaseModel, Field


class InstructionItem(BaseModel):
    tag_id: str = Field(description="Placeholder ID, e.g. TAG_01")
    instruction: str = Field(description="Original instruction text from inside @ ... @@")


class SmartParserOutput(BaseModel):
    instructions: list[InstructionItem] = Field(
        description="Extracted instructions in order of first appearance"
    )
    silent_template: str = Field(
        description="Template with @TAG_XX@@ placeholders instead of full instructions"
    )
