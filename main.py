import sys

from dotenv import load_dotenv

from agents.template_planner import plan_template
from docx_utils import load_docx

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

path = r"D:\python\fake_content\after edit.docx"

result = plan_template({"template_text": load_docx(path)})

print(f"Marker count: {result.get('marker_count', len(result['instruction_map']))}")
print(f"Unique tags: {len(result['instruction_map'])}")
print("\nExtracted instructions and questions:")
for tag_id, instruction in result["instruction_map"].items():
    print(f"\n{tag_id}:")
    print(f"  Instruction: {instruction}")
    contexts = result["contexts_map"].get(tag_id, [])
    if contexts:
        print(f"  Contexts ({len(contexts)}):")
        for ctx in contexts:
            print(f"    - {ctx}")
    print("  Questions:")
    for q in result["questions_map"][tag_id]:
        print(f"    - {q}")
