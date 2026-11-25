import type { ButtonHTMLAttributes, ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { Link, type LinkProps } from "react-router-dom";

type Variant = "primary" | "secondary" | "quiet" | "outline" | "danger";
type Size = "sm" | "md" | "lg";

const base =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-full font-semibold transition duration-200 ease-out focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-orange-300/50 disabled:cursor-not-allowed disabled:opacity-50";
const variants: Record<Variant, string> = {
  primary:
    "bg-orange-500 text-white shadow-[0_8px_20px_-8px_rgba(214,106,44,.7)] hover:-translate-y-0.5 hover:bg-orange-600",
  secondary: "bg-forest text-white hover:-translate-y-0.5 hover:bg-forest-800",
  quiet: "text-forest hover:bg-forest/8",
  outline: "border border-stone-300 bg-white/70 text-forest hover:border-forest/40 hover:bg-white",
  danger: "bg-rose-100 text-rose-800 hover:bg-rose-200",
};
const sizes: Record<Size, string> = {
  sm: "px-4 py-2 text-sm",
  md: "px-5 py-3 text-sm",
  lg: "px-7 py-3.5 text-base",
};

export function buttonClass(
  variant: Variant = "primary",
  size: Size = "md",
  className = "",
) {
  return `${base} ${variants[variant]} ${sizes[size]} ${className}`.trim();
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={buttonClass(variant, size, className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <LoaderCircle size={17} className="animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

interface ButtonLinkProps extends LinkProps {
  variant?: Variant;
  size?: Size;
  children: ReactNode;
  className?: string;
}

export function ButtonLink({
  variant = "primary",
  size = "md",
  className = "",
  children,
  ...props
}: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...props}>
      {children}
    </Link>
  );
}
