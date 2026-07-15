"use client";

import { useState } from "react";

import { AppShell, type AppSection } from "@/components/AppShell";
import { ResourcesUploader } from "@/components/ResourcesUploader";
import { TemplateHelp } from "@/components/TemplateHelp";
import { TemplateUploader } from "@/components/TemplateUploader";
import { Button } from "@/components/ui/button";
import { generateProposal } from "@/lib/api";

export function GenerateForm() {
  const [activeSection, setActiveSection] = useState<AppSection>("resources");
  const [resources, setResources] = useState<File[]>([]);
  const [template, setTemplate] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const canGenerate = resources.length > 0 && !loading;
  const templateHint = template ? template.name : "افتراضي";
  const readinessHint = resources.length > 0 ? "جاهز" : "ينقص موارد";

  async function handleGenerate() {
    if (!canGenerate) return;

    setError(null);
    setSuccess(false);
    setLoading(true);
    setActiveSection("generate");

    try {
      await generateProposal(resources, template);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "تعذر توليد العرض");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell
      activeSection={activeSection}
      onSectionChange={setActiveSection}
      resourceCount={resources.length}
      templateHint={templateHint}
      readinessHint={readinessHint}
      canGenerate={canGenerate}
      loading={loading}
      error={error}
      success={success}
      onGenerate={handleGenerate}
    >
      {activeSection === "resources" ? (
        <ResourcesUploader
          files={resources}
          onChange={setResources}
          disabled={loading}
        />
      ) : null}

      {activeSection === "template" ? (
        <div className="space-y-10">
          <TemplateUploader
            template={template}
            onChange={setTemplate}
            disabled={loading}
          />
          <TemplateHelp />
        </div>
      ) : null}

      {activeSection === "generate" ? (
        <section className="space-y-4" aria-labelledby="generate-heading">
          <div className="space-y-1">
            <h2
              id="generate-heading"
              className="text-lg font-semibold text-foreground"
            >
              توليد العرض
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              راجع جاهزية الملفات ثم اضغط التوليد من الشريط الجانبي أو أسفل
              الشاشة.
            </p>
          </div>

          <ul className="space-y-3 rounded-xl border border-border bg-secondary/30 p-4 text-sm">
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">الموارد</span>
              <span className="font-medium text-foreground">
                {resources.length > 0
                  ? `${resources.length} ملف`
                  : "لم تُرفع بعد"}
              </span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">التمبلت</span>
              <span className="max-w-[60%] truncate font-medium text-foreground">
                {templateHint}
              </span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">الحالة</span>
              <span
                className={
                  resources.length > 0
                    ? "font-medium text-brand"
                    : "font-medium text-destructive"
                }
              >
                {readinessHint}
              </span>
            </li>
          </ul>

          {resources.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              انتقل إلى قسم الموارد وارفع ملفًا واحدًا على الأقل قبل التوليد.
            </p>
          ) : (
            <p className="text-sm text-muted-foreground">
              كل شيء جاهز. اضغط «توليد العرض الفني» لبدء المعالجة وتنزيل{" "}
              <span dir="ltr" className="font-medium text-foreground">
                proposal.docx
              </span>
              .
            </p>
          )}

          <Button
            type="button"
            size="lg"
            disabled={!canGenerate}
            onClick={handleGenerate}
            className="w-full sm:w-auto"
          >
            {loading ? "جارٍ التوليد..." : "توليد العرض الفني"}
          </Button>
        </section>
      ) : null}
    </AppShell>
  );
}
