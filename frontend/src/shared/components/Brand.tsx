import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="group inline-flex items-center gap-3" aria-label="Mille Bornes, accueil">
      <span className="brand-mark">
        <svg viewBox="0 0 44 44" fill="none" aria-hidden="true">
          <rect x="1" y="1" width="42" height="42" rx="15" fill="currentColor" />
          <path
            d="M8 32C16 28 13 20 19 15C24 11 29 15 36 9"
            stroke="#F6F0DF"
            strokeWidth="5"
            strokeLinecap="round"
          />
          <path
            d="M8 32C16 28 13 20 19 15C24 11 29 15 36 9"
            stroke="#E9A14B"
            strokeWidth="1.5"
            strokeDasharray="3 4"
            strokeLinecap="round"
          />
          <circle cx="9" cy="32" r="3" fill="#E9A14B" />
          <circle cx="36" cy="9" r="3" fill="#E9A14B" />
        </svg>
      </span>
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="font-display text-[1.1rem] font-extrabold tracking-tight text-forest">
            MILLE <span className="text-orange-600">BORNES</span>
          </span>
          <span className="mt-1.5 text-[9px] font-bold uppercase tracking-[.24em] text-stone-500">
            Le jeu de la route
          </span>
        </span>
      )}
      <ArrowUpRight
        size={15}
        className="ml-[-5px] self-start text-orange-500 opacity-0 transition group-hover:opacity-100"
        aria-hidden="true"
      />
    </Link>
  );
}
