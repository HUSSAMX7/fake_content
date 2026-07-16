import { GenerateForm } from "@/components/GenerateForm";

export default function HomePage() {
  return (
    <div className="relative min-h-full bg-white dark:bg-background">
      <div className="pointer-events-none fixed inset-0 -z-10 hidden bg-[radial-gradient(ellipse_at_top,_#163528_0%,_#111927_55%)] dark:block" />
      <GenerateForm />
    </div>
  );
}
