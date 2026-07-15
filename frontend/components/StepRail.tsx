"use client";

import { Check } from "lucide-react";

import type { AppSection } from "@/lib/sections";
import { cn } from "@/lib/utils";

const STEPS: Array<{ id: AppSection; label: string }> = [
  { id: "resources", label: "الموارد" },
  { id: "template", label: "التمبلت" },
  { id: "generate", label: "التوليد" },
];

type StepRailProps = {
  activeSection: AppSection;
  resourcesComplete: boolean;
  generateComplete: boolean;
  onSectionChange: (section: AppSection) => void;
};

export function StepRail({
  activeSection,
  resourcesComplete,
  generateComplete,
  onSectionChange,
}: StepRailProps) {
  function isComplete(id: AppSection): boolean {
    if (id === "resources") return resourcesComplete;
    if (id === "template") return true;
    return generateComplete;
  }

  return (
    <nav aria-label="مسار الإعداد" className="w-full">
      <ol className="flex items-center gap-2">
        {STEPS.map((step, index) => {
          const active = activeSection === step.id;
          const complete = isComplete(step.id);

          return (
            <li key={step.id} className="flex min-w-0 flex-1 items-center gap-2">
              <button
                type="button"
                onClick={() => onSectionChange(step.id)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-start text-sm transition-colors",
                  active
                    ? "bg-brand text-white"
                    : "bg-secondary/50 text-muted-foreground hover:bg-secondary hover:text-foreground",
                )}
                aria-current={active ? "true" : undefined}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-md text-xs font-semibold",
                    active
                      ? "bg-white/20 text-white"
                      : complete
                        ? "bg-brand/20 text-brand"
                        : "bg-white/10 text-muted-foreground",
                  )}
                >
                  {complete && !active ? (
                    <Check className="size-3.5" aria-hidden />
                  ) : (
                    index + 1
                  )}
                </span>
                <span className="truncate font-medium">{step.label}</span>
              </button>
              {index < STEPS.length - 1 ? (
                <span
                  className="hidden h-px w-3 shrink-0 bg-border sm:block"
                  aria-hidden
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
