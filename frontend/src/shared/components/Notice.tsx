import type { ReactNode } from "react";
import { AlertCircle, CheckCircle2, Info } from "lucide-react";

type Tone = "error" | "success" | "info";

const toneClass: Record<Tone, string> = {
  error: "border-rose-200 bg-rose-50 text-rose-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  info: "border-forest/15 bg-forest/5 text-forest",
};

const icons = {
  error: AlertCircle,
  success: CheckCircle2,
  info: Info,
};

export function Notice({
  tone = "info",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  const Icon = icons[tone];
  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${toneClass[tone]}`} role="status">
      <Icon size={18} className="mt-0.5 shrink-0" aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
