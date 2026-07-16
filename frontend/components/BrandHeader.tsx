type BrandHeaderProps = {
  compact?: boolean;
};

export function BrandHeader({ compact = false }: BrandHeaderProps) {
  return (
    <div
      className={
        compact ? "space-y-1" : "space-y-4 text-center sm:text-start"
      }
    >
      <div
        className={
          compact
            ? "flex items-center gap-2"
            : "flex flex-col items-center gap-2 sm:items-start"
        }
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/rmg-logo.png"
          alt="RMG — ريناد المجد"
          className={
            compact
              ? "h-7 w-auto shrink-0 object-contain"
              : "h-9 w-auto shrink-0 object-contain sm:h-10"
          }
        />
      </div>
      <div className="space-y-0.5">
        <h1
          className={
            compact
              ? "text-2xl font-bold tracking-tight text-brand"
              : "text-4xl font-bold tracking-tight text-brand sm:text-5xl"
          }
        >
          صياغة
        </h1>
        <p
          className={
            compact
              ? "text-sm text-muted-foreground"
              : "text-base text-foreground/90 sm:text-lg"
          }
        >
          مولّد العروض الفنية
        </p>
      </div>
      {!compact ? (
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          ارفع موارد المشروع وتمبلت Word، ثم ولّد العرض جاهزًا للتحميل
        </p>
      ) : null}
    </div>
  );
}
