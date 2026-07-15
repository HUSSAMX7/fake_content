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
        <h2 id="template-heading" className="text-lg font-semibold text-foreground">
          تمبلت العرض
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
          التمبلت الافتراضي محدّد مسبقًا. حمّله واقرأ محتواه قبل استبداله بتمبلت
          خاص.
        </p>
      </div>

      <div className="rounded-xl border border-border bg-secondary/30 px-4 py-5 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <FileType className="size-5 shrink-0 text-brand" />
            <div className="min-w-0">
              <p className="text-sm font-medium sm:text-base">
                {usingDefault ? "التمبلت الافتراضي" : template.name}
              </p>
              <p className="text-xs text-muted-foreground sm:text-sm">
                {usingDefault
                  ? "سيُستخدم تمبلت الخادم إن لم ترفع ملفًا آخر"
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
              aria-label="العودة للتمبلت الافتراضي"
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
          {downloading ? "جارٍ التحميل..." : "تحميل التمبلت الافتراضي"}
        </Button>

        <Button
          type="button"
          variant="outline"
          size="lg"
          disabled={disabled}
          onClick={() => {
            if (usingDefault) {
              requestReplaceDefault();
            } else {
              inputRef.current?.click();
            }
          }}
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
            <DialogTitle>تنبيه قبل استبدال التمبلت الافتراضي</DialogTitle>
            <DialogDescription className="leading-relaxed text-muted-foreground">
              انتبه: هذا تمبلت ممتاز. اقرأ محتواه أولًا لتفهم كيف تُكتب تعليمات
              التمبلت قبل استبداله.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:justify-start">
            <Button type="button" onClick={confirmReplaceDefault}>
              المتابعة والاستبدال
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setWarningOpen(false)}
            >
              إلغاء
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
