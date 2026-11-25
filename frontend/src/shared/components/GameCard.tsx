import {
  AlertTriangle,
  CircleGauge,
  CircleStop,
  Fuel,
  Gauge,
  Shield,
  Sparkles,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import type { CardType } from "../types/game";

const presentation: Record<
  CardType,
  { title: string; short: string; icon: LucideIcon; family: "distance" | "danger" | "repair" | "safety" }
> = {
  km_25: { title: "25 kilomètres", short: "25", icon: CircleGauge, family: "distance" },
  km_50: { title: "50 kilomètres", short: "50", icon: CircleGauge, family: "distance" },
  km_75: { title: "75 kilomètres", short: "75", icon: CircleGauge, family: "distance" },
  km_100: { title: "100 kilomètres", short: "100", icon: CircleGauge, family: "distance" },
  km_200: { title: "200 kilomètres", short: "200", icon: CircleGauge, family: "distance" },
  speed_limit: { title: "Limitation de vitesse", short: "Limite", icon: Gauge, family: "danger" },
  red_light: { title: "Feu rouge", short: "Stop", icon: CircleStop, family: "danger" },
  out_of_fuel: { title: "Panne d’essence", short: "Panne", icon: Fuel, family: "danger" },
  flat_tire: { title: "Crevaison", short: "Crevaison", icon: CircleGauge, family: "danger" },
  accident: { title: "Accident", short: "Accident", icon: AlertTriangle, family: "danger" },
  green_light: { title: "Feu vert", short: "Feu vert", icon: Sparkles, family: "repair" },
  end_speed_limit: { title: "Fin de limitation", short: "Fin limite", icon: Gauge, family: "repair" },
  fuel: { title: "Essence", short: "Essence", icon: Fuel, family: "repair" },
  spare_tire: { title: "Roue de secours", short: "Roue", icon: Wrench, family: "repair" },
  repairs: { title: "Réparations", short: "Réparation", icon: Wrench, family: "repair" },
  priority_vehicle: { title: "Véhicule prioritaire", short: "Prioritaire", icon: Shield, family: "safety" },
  extra_tank: { title: "Citerne", short: "Citerne", icon: Fuel, family: "safety" },
  puncture_proof: { title: "Increvable", short: "Increvable", icon: Shield, family: "safety" },
  driving_ace: { title: "As du volant", short: "As du volant", icon: Shield, family: "safety" },
};

const familyClass = {
  distance: "card-distance",
  danger: "card-danger",
  repair: "card-repair",
  safety: "card-safety",
};

export function GameCard({
  type,
  size = "normal",
  selected = false,
  disabled = false,
  back = false,
  onClick,
  className = "",
}: {
  type?: CardType;
  size?: "small" | "normal" | "large";
  selected?: boolean;
  disabled?: boolean;
  back?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const dimensions = {
    small: "w-[76px] min-w-[76px] h-[112px]",
    normal: "w-[100px] min-w-[100px] h-[148px] sm:w-[112px] sm:min-w-[112px] sm:h-[164px]",
    large: "w-[128px] min-w-[128px] h-[188px]",
  }[size];

  if (back || !type) {
    return (
      <div className={`card-back ${dimensions} ${className}`} aria-label="Carte cachée">
        <span className="grid size-11 place-items-center rounded-full border border-cream/25 bg-cream/5">
          <span className="font-display text-xs font-black tracking-widest text-cream/85">MB</span>
        </span>
      </div>
    );
  }

  const item = presentation[type];
  const Icon = item.icon;
  const isDistance = item.family === "distance";
  const content = (
    <>
      <span className="absolute left-2.5 top-2.5 max-w-[80%] truncate text-[8px] font-extrabold uppercase tracking-[.14em] opacity-65">
        {isDistance ? "Borne" : item.short}
      </span>
      <span className={`card-center-icon ${isDistance ? "distance-icon" : ""}`}>
        <Icon size={isDistance ? 22 : 27} strokeWidth={1.9} aria-hidden="true" />
      </span>
      {isDistance ? (
        <span className="card-distance-number">{item.short}<small>km</small></span>
      ) : (
        <span className="card-name">{item.title}</span>
      )}
      <span className="absolute bottom-2 left-2.5 text-[7px] font-bold uppercase tracking-[.13em] opacity-50">
        Mille Bornes
      </span>
      {isDistance && <span className="absolute right-2.5 top-2.5 text-[8px] font-black opacity-60">◆</span>}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className={`game-card ${familyClass[item.family]} ${dimensions} ${selected ? "is-selected" : ""} ${className}`}
        onClick={onClick}
        disabled={disabled}
        aria-label={item.title}
        aria-pressed={selected}
      >
        {content}
      </button>
    );
  }

  return (
    <div className={`game-card ${familyClass[item.family]} ${dimensions} ${selected ? "is-selected" : ""} ${className}`} aria-label={item.title}>
      {content}
    </div>
  );
}
