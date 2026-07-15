import sys

from dotenv import load_dotenv

from backend.pipeline import run_pipeline

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TEMPLATE_PATH = r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\good templete.docx"
OUTPUT_PATH = r"C:\Users\hosam\OneDrive\سطح المكتب\fake_content\output_draft.docx"

TENDER_PATHS = [
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\ملحقات منافسة.pdf",
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\معايير التقييم.pdf",
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\كراسة الشروط والمواصفات.pdf",
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\دراسة مشروع.docx",
    r"C:\Users\hosam\OneDrive\سطح المكتب\نطاق العمل\_عروض فنية نماذج ناجحة\عروض فنية نماذج ناجحة\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\تطوير مركز ذكاء الأعمال ووحدة دعم اتخاذ القرار\استفسارات.docx",
]

print(f"Loading {len(TENDER_PATHS)} resource document(s)")
output = run_pipeline(TEMPLATE_PATH, TENDER_PATHS, OUTPUT_PATH)
print(f"Saved: {output}")
