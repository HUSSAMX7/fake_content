"use client";

import type { ReactNode } from "react";
import { Check, LoaderCircle } from "lucide-react";

import { BrandHeader } from "@/components/BrandHeader";
import { StepRail } from "@/components/StepRail";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { AppSection } from "@/lib/sections";
import { cn } from "@/lib/utils";

export type { AppSection };

type AppShellProps = {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
  resourceCount: number;
  usingDefaultTemplate: boolean;
  customTemplateName: string | null;
  readinessHint: string;
  resourcesComplete: boolean;
  generateComplete: boolean;
  canGenerate: boolean;
  loading: boolean;
  error: string | null;
  success: boolean;
  onGenerate: () => void;
  children: ReactNode;
};

const NAV_ITEMS: Array<{
  id: AppSection;
  label: string;
}> = [
  { id: "resources", label: "الموارد" },
  { id: "template", label: "التمبلت" },
  { id: "generate", label: "التوليد" },
];

export function AppShell({
  activeSection,
  onSectionChange,
  resourceCount,
  usingDefaultTemplate,
  customTemplateName,
  readinessHint,
  resourcesComplete,
  generateComplete,
  canGenerate,
  loading,
  error,
  success,
  onGenerate,
  children,
}: AppShellProps) {
  function sectionHint(id: AppSection): string {
    if (id === "resources") {
      if (resourcesComplete) return "تم";
      return String(resourceCount);
    }
    if (id === "template") {
      return usingDefaultTemplate
        ? "موصى به"
        : (customTemplateName ?? "مخصص");
    }
    if (generateComplete) return "تم";
    return readinessHint;
  }

  const showShellGenerate = activeSection !== "generate";

  function sectionComplete(id: AppSection): boolean {
    if (id === "resources") return resourcesComplete;
    if (id === "template") return true;
    return generateComplete;
  }

  const generateButton = (
    <Button
      type="button"
      size="lg"
      disabled={!canGenerate}
      onClick={onGenerate}
      className="w-full"
    >
      {loading ? (
        <>
          <LoaderCircle className="size-4 animate-spin" />
          جارٍ التوليد...
        </>
      ) : (
        "ولّد العرض الفني"
      )}
    </Button>
  );

  const loadingNote = loading ? (
    <p className="text-xs leading-relaxed text-white/70" role="status">
      قد يستغرق التوليد عدة دقائق. يُرجى عدم إغلاق الصفحة.
    </p>
  ) : null;

  const statusAlerts = (
    <>
      {error ? (
        <Alert variant="destructive" className="border-destructive/40 bg-destructive/10">
          <AlertTitle>فشل التوليد</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {success && !error ? (
        <Alert className="border-brand/40 bg-brand/10">
          <AlertTitle>تم التوليد</AlertTitle>
          <AlertDescription>
            بدأ تنزيل ملف{" "}
            <span dir="ltr" className="font-medium">
              proposal.docx
            </span>
            .
          </AlertDescription>
        </Alert>
      ) : null}
    </>
  );

  return (
    <div className="flex min-h-full flex-col lg:flex-row">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#111927] lg:hidden">
        <div className="px-4 py-4">
          <BrandHeader compact />
        </div>
        <nav
          className="flex gap-1 overflow-x-auto px-3 pb-3"
          aria-label="أقسام التطبيق"
        >
          {NAV_ITEMS.map((item) => {
            const active = activeSection === item.id;
            const complete = sectionComplete(item.id);
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSectionChange(item.id)}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-brand text-white"
                    : "bg-white/5 text-white/80 hover:bg-white/10 hover:text-white",
                )}
                aria-current={active ? "true" : undefined}
              >
                {complete && !active ? (
                  <Check className="size-3.5 text-brand" aria-hidden />
                ) : null}
                <span>{item.label}</span>
                <span
                  className={cn(
                    "max-w-24 truncate rounded-md px-1.5 py-0.5 text-[11px]",
                    active ? "bg-white/20 text-white" : "bg-white/10 text-white/70",
                  )}
                >
                  {sectionHint(item.id)}
                </span>
              </button>
            );
          })}
        </nav>
      </header>

      <aside className="sticky top-0 hidden h-svh w-72 shrink-0 flex-col border-e border-white/10 bg-[#111927] lg:flex">
        <div className="flex h-full flex-col gap-8 overflow-y-auto px-5 py-8">
          <BrandHeader compact />

          <nav className="flex flex-1 flex-col gap-1.5" aria-label="أقسام التطبيق">
            {NAV_ITEMS.map((item) => {
              const active = activeSection === item.id;
              const complete = sectionComplete(item.id);
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSectionChange(item.id)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-start text-sm font-medium transition-colors",
                    active
                      ? "bg-brand text-white"
                      : "text-white/80 hover:bg-white/10 hover:text-white",
                  )}
                  aria-current={active ? "true" : undefined}
                >
                  <span className="flex items-center gap-2">
                    {complete && !active ? (
                      <Check className="size-3.5 text-brand" aria-hidden />
                    ) : null}
                    {item.label}
                  </span>
                  <span
                    className={cn(
                      "max-w-28 truncate rounded-md px-1.5 py-0.5 text-[11px] font-normal",
                      active ? "bg-white/20 text-white" : "bg-white/10 text-white/65",
                    )}
                  >
                    {sectionHint(item.id)}
                  </span>
                </button>
              );
            })}
          </nav>

          {showShellGenerate ? (
            <div className="mt-auto space-y-3 border-t border-white/10 pt-5">
              {generateButton}
              {loadingNote}
            </div>
          ) : (
            <div className="mt-auto border-t border-white/10 pt-5">
              <p className="text-xs leading-relaxed text-white/60">
                أكمل التوليد من لوحة المحتوى.
              </p>
            </div>
          )}
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main
          className={cn(
            "flex-1 px-4 py-6 sm:px-8 sm:py-8 lg:px-10 lg:py-10",
            showShellGenerate ? "pb-28 lg:pb-10" : "pb-10",
          )}
        >
          <div className="mx-auto w-full max-w-3xl space-y-8">
            <div className="space-y-4">
              <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
                ارفع موارد المشروع وتمبلت Word، ثم ولّد العرض جاهزًا للتحميل
              </p>
              <StepRail
                activeSection={activeSection}
                resourcesComplete={resourcesComplete}
                generateComplete={generateComplete}
                onSectionChange={onSectionChange}
              />
            </div>
            {statusAlerts}
            {children}
          </div>
        </main>

        {showShellGenerate ? (
          <div className="sticky bottom-0 z-20 space-y-2 border-t border-white/10 bg-[#111927]/95 px-4 py-4 backdrop-blur lg:hidden">
            {generateButton}
            {loadingNote}
          </div>
        ) : null}
      </div>
    </div>
  );
}
