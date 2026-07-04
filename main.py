import sys

from dotenv import load_dotenv

from agents.smart_parser import parse_template
from docx_utils import load_docx

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

path = r"D:\python\fake_content\after edit.docx"

result = parse_template({"template_text": load_docx(path)})

print("Extracted instructions:")
for tag_id, instruction in result["instruction_map"].items():
    print(f"\n{tag_id}:\n  {instruction}")
