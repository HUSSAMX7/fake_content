export function TemplateHelp() {
  return (
    <section className="space-y-5" aria-labelledby="template-help-heading">
      <div className="space-y-1.5">
        <h2
          id="template-help-heading"
          className="text-lg font-semibold text-foreground"
        >
          كيف يُكتب التمبلت؟
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
          استخدم العلامات التالية داخل ملف Word لتوجيه الوكيل إلى ما يجب تعبئته.
        </p>
      </div>

      <ul className="grid gap-2 text-sm leading-relaxed text-foreground/90 sm:grid-cols-2">
        <li className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
          <code className="rounded bg-secondary px-1.5 py-0.5 text-brand" dir="ltr">
            @
          </code>{" "}
          يفتح منطقة يملؤها الوكيل.
        </li>
        <li className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
          <code className="rounded bg-secondary px-1.5 py-0.5 text-brand" dir="ltr">
            @@
          </code>{" "}
          يغلق تلك المنطقة.
        </li>
        <li className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
          النص بين العلامتين هو ما يكتبه الوكيل.
        </li>
        <li className="rounded-lg border border-border bg-secondary/20 px-3 py-2.5">
          النص خارج العلامتين يبقى كما هو في المستند النهائي.
        </li>
      </ul>

      <div className="space-y-3 rounded-xl border border-border bg-secondary/30 p-4 text-sm sm:p-5">
        <p className="font-medium text-foreground">أمثلة قصيرة:</p>
        <p className="leading-relaxed text-muted-foreground" dir="rtl">
          مقدمة ثابتة{" "}
          <code className="text-brand" dir="ltr">
            @اكتب ملخص المشروع هنا@@
          </code>{" "}
          ثم خاتمة ثابتة.
        </p>
        <p className="leading-relaxed text-muted-foreground" dir="rtl">
          الجدول الزمني:{" "}
          <code className="text-brand" dir="ltr">
            @أدرج مراحل التنفيذ@@
          </code>
        </p>
      </div>
    </section>
  );
}
