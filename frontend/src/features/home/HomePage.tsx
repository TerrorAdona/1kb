import {
  ArrowDownRight,
  ArrowRight,
  Flag,
  Gauge,
  Sparkles,
  Trophy,
  UsersRound,
} from "lucide-react";
import { Link } from "react-router-dom";
import { useAuthStore } from "../auth/authStore";
import { ButtonLink } from "../../shared/components/Button";
import { GameCard } from "../../shared/components/GameCard";

export function HomePage() {
  const user = useAuthStore((state) => state.user);

  return (
    <div className="home-page">
      <section className="hero-panel">
        <div className="hero-copy">
          <div className="hero-kicker">
            <span className="hero-kicker-dot" />
            Le grand classique reprend la route
          </div>
          <h1 className="hero-title">
            La route
            <br />
            est <em>à vous.</em>
          </h1>
          <p className="hero-description">
            Feux verts, belles accélérations et quelques embûches. Retrouvez
            l’esprit du Mille Bornes, en solo ou avec vos proches.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <ButtonLink to="/solo" size="lg" className="group">
              <span className="grid size-7 place-items-center rounded-full bg-white/15">
                <ArrowRight size={15} />
              </span>
              Jouer maintenant
            </ButtonLink>
            <ButtonLink to="/lobby" variant="outline" size="lg" className="border-white/20 bg-white/8 text-cream hover:bg-white/15">
              <UsersRound size={17} /> Multijoueur
            </ButtonLink>
          </div>
          <div className="hero-social-proof">
            <div className="flex -space-x-2">
              {["bg-orange-200", "bg-emerald-200", "bg-amber-100"].map((color, index) => (
                <span
                  key={color}
                  className={`grid size-8 place-items-center rounded-full border-2 border-forest text-[10px] font-black text-forest ${color}`}
                >
                  {["A", "M", "J"][index]}
                </span>
              ))}
            </div>
            <span>Une partie se joue mieux à plusieurs.</span>
            <ArrowDownRight size={14} className="text-orange-300" />
          </div>
        </div>

        <div className="hero-visual" aria-label="Illustration d’une route de campagne et de cartes">
          <div className="hero-sun" />
          <div className="hero-horizon">
            <span className="hill hill-back" />
            <span className="hill hill-front" />
          </div>
          <svg className="hero-road" viewBox="0 0 720 620" fill="none" aria-hidden="true">
            <path d="M-50 520C123 466 95 327 249 315C408 302 429 480 572 432C667 400 620 245 779 191" stroke="#182A22" strokeWidth="188" strokeLinecap="round" />
            <path d="M-50 520C123 466 95 327 249 315C408 302 429 480 572 432C667 400 620 245 779 191" stroke="#D8CDAF" strokeWidth="6" strokeDasharray="18 19" strokeLinecap="round" />
          </svg>
          <div className="hero-mileage-card">
            <span className="grid size-9 place-items-center rounded-xl bg-orange-100 text-orange-700"><Flag size={17} /></span>
            <span>
              <small>Destination</small>
              <strong>1 000 km</strong>
            </span>
            <span className="mileage-arrow">↗</span>
          </div>
          <div className="hero-mini-card hero-card-one"><GameCard type="km_100" size="small" /></div>
          <div className="hero-mini-card hero-card-two"><GameCard type="green_light" size="small" /></div>
          <div className="hero-route-chip">
            <span className="route-chip-icon"><Gauge size={16} /></span>
            <span><strong>Prêt à partir ?</strong><small>Votre prochaine belle course</small></span>
            <Sparkles size={15} className="ml-auto text-orange-300" />
          </div>
          <div className="hero-stamp">BON<br />VOYAGE</div>
        </div>
      </section>

      <section className="home-lower">
        <div className="home-intro">
          <p className="eyebrow">Choisissez votre route</p>
          <h2 className="mt-2 max-w-xl font-display text-2xl font-black tracking-tight text-forest sm:text-3xl">
            Le plaisir du jeu. <span className="text-orange-700">À votre façon.</span>
          </h2>
        </div>
        <div className="mode-cards">
          <Link to="/solo" className="mode-card mode-card-solo">
            <span className="mode-icon"><Gauge size={19} /></span>
            <span className="mode-card-copy">
              <strong>En solo</strong>
              <small>Réglez le niveau, prenez le départ face aux bots.</small>
            </span>
            <span className="mode-arrow"><ArrowRight size={16} /></span>
          </Link>
          <Link to="/lobby" className="mode-card mode-card-multi">
            <span className="mode-icon"><UsersRound size={19} /></span>
            <span className="mode-card-copy">
              <strong>Entre amis</strong>
              <small>Ouvrez un salon ou rejoignez une partie en cours.</small>
            </span>
            <span className="mode-arrow"><ArrowRight size={16} /></span>
          </Link>
          <Link to={user ? "/profile" : "/register"} className="mode-card mode-card-stats">
            <span className="mode-icon"><Trophy size={19} /></span>
            <span className="mode-card-copy">
              <strong>Votre parcours</strong>
              <small>Retrouvez votre profil, vos parties et vos statistiques.</small>
            </span>
            <span className="mode-arrow"><ArrowRight size={16} /></span>
          </Link>
        </div>
      </section>
      <div className="home-note">
        <span className="note-line" />
        <span>Une partie de stratégie, un brin de chance, beaucoup de bonne humeur.</span>
        <span className="note-line" />
      </div>
    </div>
  );
}
