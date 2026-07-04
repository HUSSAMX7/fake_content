import sys

from dotenv import load_dotenv

from agents.answer_agent import fill_answers
from agents.integrator import integrate
from agents.template_planner import plan_template
from docx_utils import load_docx
from document_loader import load_documents

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEMPLATE_PATH = r"D:\python\fake_content\after edit.docx"
OUTPUT_PATH = r"D:\python\fake_content\output_draft.docx"

TENDER_PATHS = [
    r"D:\python\fake_content1\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\إعداد خطط استمرارية الأعمال للخدمات الحكومية\إعداد خطط استمرارية الأعمال للخدمات الحكومية\كراسة الشروط والمواصفات.pdf",
    r"D:\python\fake_content1\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\إعداد خطط استمرارية الأعمال للخدمات الحكومية\إعداد خطط استمرارية الأعمال للخدمات الحكومية\دراسة مشروع (16).docx",
]

template_text = load_docx(TEMPLATE_PATH)
state = {**plan_template({"template_text": template_text}), "template_text": template_text}

print(f"Tags: {len(state['instructions'])}")
print("\nExtracted instructions and questions:")
for tag in state["instructions"]:
    print(f"\n{tag.tag_id}:")
    print(f"  Instruction: {tag.instruction[:80]}...")
    print("  Questions:")
    for q in tag.questions:
        print(f"    - {q}")

print(f"\nLoading {len(TENDER_PATHS)} tender document(s):")
for path in TENDER_PATHS:
    print(f"  - {path}")

state = {**state, "tender_text": load_documents(TENDER_PATHS)}
print(f"Combined tender length: {len(state['tender_text']):,} characters")

state = {**state, **fill_answers(state)}

print("\n--- Integrating into Word ---")
state = {**state, **integrate(state, TEMPLATE_PATH, OUTPUT_PATH)}
print(f"Saved: {state['output_path']}")

print("\n--- Answers summary ---")
for answer in state["answers"]:
    print(f"\n{answer.tag_id}: {len(answer.question_answers)} answer(s)")
