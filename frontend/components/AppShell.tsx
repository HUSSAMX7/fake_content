"use client";

import type { ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

import { BrandHeader } from "@/components/BrandHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type AppSection = "resources" | "template" | "generate";

type AppShellProps = {
  activeSection: AppSection;
  onSectionChange: (section: AppSection) => void;
  resourceCount: number;
  templateHint: string;
  readinessHint: string;
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
  templateHint,
  readinessHint,
  canGenerate,
  loading,
  error,
  success,
  onGenerate,
  children,
}: AppShellProps) {
  function sectionHint(id: AppSection): string {
    if (id === "resources") return String(resourceCount);
    if (id === "template") return templateHint;
    return readinessHint;
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
        "توليد العرض الفني"
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
                  <span>{item.label}</span>
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

          <div className="mt-auto space-y-3 border-t border-white/10 pt-5">
            {generateButton}
            {loadingNote}
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="flex-1 px-4 py-6 pb-28 sm:px-8 sm:py-8 lg:px-10 lg:py-10 lg:pb-10">
          <div className="mx-auto w-full max-w-3xl space-y-8">
            <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
              ارفع موارد المشروع وتمبلت Word، ثم ولّد العرض جاهزًا للتحميل
            </p>
            {statusAlerts}
            {children}
          </div>
        </main>

        <div className="sticky bottom-0 z-20 space-y-2 border-t border-white/10 bg-[#111927]/95 px-4 py-4 backdrop-blur lg:hidden">
          {generateButton}
          {loadingNote}
        </div>
      </div>
    </div>
  );
}
