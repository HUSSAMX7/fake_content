from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(model="gpt-5.4-mini")


def invoke_structured(schema, messages):
    """Structured LLM call via function calling (avoids fragile JSON content parsing)."""
    return llm.with_structured_output(schema, method="function_calling").invoke(messages)
