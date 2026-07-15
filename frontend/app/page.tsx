import { GenerateForm } from "@/components/GenerateForm";

export default function HomePage() {
  return (
    <div className="relative min-h-full">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(ellipse_at_top,_#163528_0%,_#111927_55%)]" />
      <GenerateForm />
    </div>
  );
}
