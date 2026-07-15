"use client";

import { useRef, useState } from "react";
import { Download, FileType, Replace, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { downloadDefaultTemplate } from "@/lib/api";
import { MAX_TEMPLATE_BYTES, formatMb } from "@/lib/limits";

type TemplateUploaderProps = {
  template: File | null;
  onChange: (file: File | null) => void;
  disabled?: boolean;
};

export function TemplateUploader({
  template,
  onChange,
  disabled = false,
}: TemplateUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [warningOpen, setWarningOpen] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  const usingDefault = template === null;

  function requestReplaceDefault() {
    setWarningOpen(true);
  }

  function confirmReplaceDefault() {
    setWarningOpen(false);
    inputRef.current?.click();
  }

  function handleFileChange(selected: FileList | null) {
    const file = selected?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".docx")) {
      setDownloadError("التمبلت يجب أن يكون ملف DOCX.");
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    if (file.size > MAX_TEMPLATE_BYTES) {
      setDownloadError(
        `التمبلت أكبر من الحد المسموح (${formatMb(MAX_TEMPLATE_BYTES)} MB).`,
      );
      if (inputRef.current) inputRef.current.value = "";
      return;
    }

    setDownloadError(null);
    onChange(file);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  async function handleDownloadDefault() {
    setDownloadError(null);
    setDownloading(true);
    try {
      await downloadDefaultTemplate();
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error.message : "تعذر تحميل التمبلت الافتراضي",
      );
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="template-heading">
      <div className="space-y-1.5">
        <h2
          id="template-heading"
          tabIndex={-1}
          className="text-lg font-semibold text-foreground outline-none"
        >
          تمبلت العرض
        </h2>
        <p className="max-w-2xl text-sm font-medium leading-relaxed text-brand sm:text-[15px]">
          يُفضّل الإبقاء على التمبلت الحالي وعدم استبداله.
        </p>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
          التمبلت جاهز ومُختبَر ومناسب لبناء العرض الفني. استبدله فقط إذا كان
          لديك تمبلت خاص مكتوب بنفس أسلوب{" "}
          <span dir="ltr" className="text-brand">
            @…@@
          </span>
          .
        </p>
      </div>

      <div className="rounded-xl border border-brand/35 bg-secondary/30 px-4 py-5 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <FileType className="size-5 shrink-0 text-brand" />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium sm:text-base">
                  {usingDefault ? "التمبلت الافتراضي" : template.name}
                </p>
                {usingDefault ? (
                  <span className="rounded-md bg-brand/20 px-2 py-0.5 text-[11px] font-medium text-brand">
                    موصى به
                  </span>
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground sm:text-sm">
                {usingDefault
                  ? "سيُستخدم تلقائيًا — لا حاجة لرفعه من جديد"
                  : "تمبلت مخصص — سيُرسل مع طلب التوليد"}
              </p>
            </div>
          </div>

          {!usingDefault ? (
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              disabled={disabled}
              onClick={() => onChange(null)}
              aria-label="العودة للتمبلت الافتراضي الموصى به"
            >
              <Trash2 className="size-4" />
            </Button>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="lg"
          disabled={disabled || downloading}
          onClick={handleDownloadDefault}
        >
          <Download className="size-4" />
          {downloading ? "جارٍ التحميل..." : "تحميل للاطلاع"}
        </Button>

        <Button
          type="button"
          variant="ghost"
          size="lg"
          disabled={disabled}
          onClick={() => {
            if (usingDefault) {
              requestReplaceDefault();
            } else {
              inputRef.current?.click();
            }
          }}
          className="text-muted-foreground"
        >
          <Replace className="size-4" />
          استبدال التمبلت
        </Button>
      </div>

      {downloadError ? (
        <p className="text-sm text-destructive" role="alert">
          {downloadError}
        </p>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => handleFileChange(event.target.files)}
      />

      <Dialog open={warningOpen} onOpenChange={setWarningOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>تنبيه قبل استبدال التمبلت الموصى به</DialogTitle>
            <DialogDescription className="leading-relaxed text-muted-foreground">
              يُفضّل الإبقاء على التمبلت الحالي. هذا تمبلت ممتاز ومصمم بعناية —
              اقرأ محتواه أولًا قبل استبداله لتفهم كيف تُكتب تعليمات{" "}
              <span dir="ltr">@…@@</span>.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-start">
            <Button type="button" variant="outline" onClick={() => setWarningOpen(false)}>
              الإبقاء على التمبلت
            </Button>
            <Button type="button" variant="ghost" onClick={confirmReplaceDefault}>
              المتابعة والاستبدال
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
