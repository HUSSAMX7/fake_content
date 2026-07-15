"use client";

import { useRef, useState } from "react";
import { FileText, Trash2, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  MAX_RESOURCE_BYTES,
  MAX_RESOURCES,
  formatMb,
} from "@/lib/limits";

const ACCEPTED_TYPES =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

type ResourcesUploaderProps = {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
};

function isAllowedResource(file: File): boolean {
  const name = file.name.toLowerCase();
  return name.endsWith(".pdf") || name.endsWith(".docx");
}

export function ResourcesUploader({
  files,
  onChange,
  disabled = false,
}: ResourcesUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  function handleSelect(selected: FileList | null) {
    if (!selected) return;

    setError(null);
    const next = [...files];
    const rejected: string[] = [];

    for (const file of Array.from(selected)) {
      if (!isAllowedResource(file)) {
        rejected.push(`${file.name}: النوع غير مدعوم (PDF أو DOCX فقط)`);
        continue;
      }
      if (file.size > MAX_RESOURCE_BYTES) {
        rejected.push(
          `${file.name}: أكبر من ${formatMb(MAX_RESOURCE_BYTES)} MB`,
        );
        continue;
      }
      if (next.length >= MAX_RESOURCES) {
        rejected.push(`الحد الأقصى ${MAX_RESOURCES} ملفات`);
        break;
      }
      const exists = next.some(
        (item) => item.name === file.name && item.size === file.size,
      );
      if (!exists) next.push(file);
    }

    onChange(next);
    if (rejected.length > 0) {
      setError(rejected[0]);
    }

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function removeFile(index: number) {
    setError(null);
    onChange(files.filter((_, i) => i !== index));
  }

  return (
    <section className="space-y-5" aria-labelledby="resources-heading">
      <div className="space-y-1.5">
        <h2
          id="resources-heading"
          tabIndex={-1}
          className="text-lg font-semibold text-foreground outline-none"
        >
          ملفات الموارد
        </h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-[15px]">
          الموارد هي مستندات ومعلومات عن الجهة أو المشروع (كراسة الشروط، نطاق
          العمل، ملاحق…). النموذج يبني محتوى العرض عليها. الصيغ المدعومة: PDF و
          DOCX.
        </p>
        <p className="text-sm text-muted-foreground">
          عند الانتهاء سيظهر لك إجراء للمتابعة إلى التمبلت.
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES}
        multiple
        className="sr-only"
        disabled={disabled}
        onChange={(event) => handleSelect(event.target.files)}
      />

      <Button
        type="button"
        variant="outline"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        className="h-auto w-full flex-col gap-2 border-dashed border-border bg-secondary/40 px-6 py-12 text-foreground hover:bg-secondary hover:text-foreground"
      >
        <Upload className="size-6 text-brand" />
        <span className="text-base font-medium">اختيار ملفات الموارد</span>
        <span className="text-xs font-normal text-muted-foreground">
          PDF أو DOCX — يمكن اختيار أكثر من ملف
        </span>
      </Button>

      {files.length > 0 ? (
        <ul className="grid gap-2 sm:grid-cols-2" aria-label="الملفات المختارة">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${index}`}
              className="flex items-center justify-between gap-3 rounded-lg border border-border bg-secondary/30 px-3 py-2.5"
            >
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="size-4 shrink-0 text-brand" />
                <span className="truncate text-sm">{file.name}</span>
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                disabled={disabled}
                onClick={() => removeFile(index)}
                aria-label={`إزالة ${file.name}`}
              >
                <Trash2 className="size-4" />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
