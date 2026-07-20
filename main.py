import sys
from pathlib import Path

from dotenv import load_dotenv

from backend.pipeline import run_pipeline

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEMPLATE_PATH = str(
    Path(__file__).resolve().parent / "backend" / "defaults" / "good_template.docx"
)
OUTPUT_PATH = r"C:\Users\hosam\OneDrive\سطح المكتب\good_temp\output_draft.docx"

TENDER_PATHS = [
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\إعداد خطط استمرارية الأعمال للخدمات الحكومية\إعداد خطط استمرارية الأعمال للخدمات الحكومية\دراسة مشروع (16).docx",
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\إعداد خطط استمرارية الأعمال للخدمات الحكومية\إعداد خطط استمرارية الأعمال للخدمات الحكومية\كراسة الشروط والمواصفات.pdf"
    ]

print(f"Loading {len(TENDER_PATHS)} resource document(s)")
output = run_pipeline(TEMPLATE_PATH, TENDER_PATHS, OUTPUT_PATH)
print(f"Saved: {output}")
