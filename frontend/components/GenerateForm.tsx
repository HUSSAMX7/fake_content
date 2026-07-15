"use client";

import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ContinueAction } from "@/components/ContinueAction";
import { ResourcesUploader } from "@/components/ResourcesUploader";
import { TemplateHelp } from "@/components/TemplateHelp";
import { TemplateUploader } from "@/components/TemplateUploader";
import { generateProposal } from "@/lib/api";
import type { AppSection } from "@/lib/sections";

const SECTION_HEADING_IDS: Record<AppSection, string> = {
  resources: "resources-heading",
  template: "template-heading",
  generate: "generate-heading",
};

export function GenerateForm() {
  const [activeSection, setActiveSection] = useState<AppSection>("resources");
  const [resources, setResources] = useState<File[]>([]);
  const [template, setTemplate] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const resourcesComplete = resources.length > 0;
  const canGenerate = resourcesComplete && !loading;
  const usingDefaultTemplate = template === null;
  const readinessHint = resourcesComplete ? "جاهز" : "ينقص موارد";

  function goToSection(section: AppSection) {
    setActiveSection(section);
    queueMicrotask(() => {
      document.getElementById(SECTION_HEADING_IDS[section])?.focus();
    });
  }

  async function handleGenerate() {
    if (!canGenerate) return;

    setError(null);
    setSuccess(false);
    setLoading(true);
    goToSection("generate");

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
      onSectionChange={goToSection}
      resourceCount={resources.length}
      usingDefaultTemplate={usingDefaultTemplate}
      customTemplateName={template?.name ?? null}
      readinessHint={readinessHint}
      resourcesComplete={resourcesComplete}
      generateComplete={success}
      canGenerate={canGenerate}
      loading={loading}
      error={error}
      success={success}
      onGenerate={handleGenerate}
    >
      {activeSection === "resources" ? (
        <div className="space-y-6">
          <ResourcesUploader
            files={resources}
            onChange={setResources}
            disabled={loading}
          />
          <ContinueAction
            ready={resourcesComplete}
            label="الموارد جاهزة — راجع التمبلت"
            onContinue={() => goToSection("template")}
            disabled={loading}
            idleHint="ارفع ملفًا واحدًا على الأقل للمتابعة."
          />
        </div>
      ) : null}

      {activeSection === "template" ? (
        <div className="space-y-10">
          <TemplateUploader
            template={template}
            onChange={setTemplate}
            disabled={loading}
          />
          <TemplateHelp />
          <ContinueAction
            ready
            label="التمبلت مناسب — انتقل للتوليد"
            onContinue={() => goToSection("generate")}
            disabled={loading}
            backLabel="العودة للموارد"
            onBack={() => goToSection("resources")}
          />
        </div>
      ) : null}

      {activeSection === "generate" ? (
        <section className="space-y-6" aria-labelledby="generate-heading">
          <div className="space-y-1">
            <h2
              id="generate-heading"
              tabIndex={-1}
              className="text-lg font-semibold text-foreground outline-none"
            >
              توليد العرض
            </h2>
            <p className="text-sm leading-relaxed text-muted-foreground">
              راجع الجاهزية ثم ولّد العرض. التمبلت الافتراضي موصى به إن لم
              تستبدله.
            </p>
          </div>

          <ul className="space-y-3 rounded-xl border border-border bg-secondary/30 p-4 text-sm">
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">الموارد</span>
              <span className="font-medium text-foreground">
                {resourcesComplete
                  ? `${resources.length} ملف`
                  : "لم تُرفع بعد"}
              </span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">التمبلت</span>
              <span className="max-w-[60%] truncate font-medium text-foreground">
                {usingDefaultTemplate
                  ? "افتراضي (موصى به)"
                  : (template?.name ?? "مخصص")}
              </span>
            </li>
            <li className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground">الحالة</span>
              <span
                className={
                  resourcesComplete
                    ? "font-medium text-brand"
                    : "font-medium text-destructive"
                }
              >
                {readinessHint}
              </span>
            </li>
          </ul>

          <ContinueAction
            ready={resourcesComplete}
            label="ولّد العرض الفني"
            onContinue={handleGenerate}
            disabled={!canGenerate}
            loading={loading}
            backLabel="العودة للتمبلت"
            onBack={() => goToSection("template")}
            idleHint="ارفع موارد من قسم الموارد قبل التوليد."
          />
        </section>
      ) : null}
    </AppShell>
  );
}
