"use client";

import { ArrowLeft, CheckCircle2, LoaderCircle } from "lucide-react";

import { Button } from "@/components/ui/button";

type ContinueActionProps = {
  ready: boolean;
  label: string;
  onContinue: () => void;
  disabled?: boolean;
  loading?: boolean;
  backLabel?: string;
  onBack?: () => void;
  idleHint?: string;
};

export function ContinueAction({
  ready,
  label,
  onContinue,
  disabled = false,
  loading = false,
  backLabel,
  onBack,
  idleHint,
}: ContinueActionProps) {
  if (!ready) {
    if (!idleHint) return null;
    return (
      <p className="text-sm text-muted-foreground" role="status">
        {idleHint}
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-brand/30 bg-secondary/40 p-4">
      <div className="flex items-start gap-2 text-sm text-foreground/90">
        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
        <p>جاهز للمتابعة</p>
      </div>

      <Button
        type="button"
        size="lg"
        disabled={disabled || loading}
        onClick={onContinue}
        className="w-full"
      >
        {loading ? (
          <>
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
            جارٍ التوليد...
          </>
        ) : (
          <>
            {label}
            <ArrowLeft className="size-4" aria-hidden />
          </>
        )}
      </Button>

      {backLabel && onBack ? (
        <Button
          type="button"
          variant="link"
          onClick={onBack}
          disabled={disabled || loading}
          className="h-auto px-0 text-sm text-muted-foreground"
        >
          {backLabel}
        </Button>
      ) : null}
    </div>
  );
}
