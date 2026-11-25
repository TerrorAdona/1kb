import type { ReactNode } from "react";

export function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-2 font-display text-3xl font-black tracking-tight text-forest sm:text-4xl">
          {title}
        </h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-stone-600">{description}</p>}
      </div>
      {action}
    </div>
  );
}
