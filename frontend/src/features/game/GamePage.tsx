import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Clock3,
  Flag,
  Gauge,
  History,
  Info,
  Radio,
  ShieldCheck,
  Sparkles,
  Trash2,
  Trophy,
} from "lucide-react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { getGame } from "../games/gameApi";
import type { Game } from "../../shared/types/api";
import type { CardType } from "../../shared/types/game";
import { apiErrorMessage } from "../../shared/api/errors";
import { useAuthStore } from "../auth/authStore";
import { Button, ButtonLink } from "../../shared/components/Button";
import { GameCard } from "../../shared/components/GameCard";
import { Notice } from "../../shared/components/Notice";

const previewCards: CardType[] = [
  "km_25",
  "km_50",
  "km_75",
  "km_100",
  "red_light",
  "repairs",
];

const previewOpponents = [
  { name: "Camille", distance: 450, danger: "Limite de vitesse" },
  { name: "Alex", distance: 275, danger: "Feu vert" },
];

const previewHistory = [
  { who: "Vous", what: "avez posé une borne", when: "À l’instant" },
  { who: "Camille", what: "a reçu une limitation", when: "Il y a 1 min" },
  { who: "Alex", what: "a parcouru 50 km", when: "Il y a 2 min" },
];

export function GamePage() {
  const { gameId = "" } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const [game, setGame] = useState<Game | null>(
    (location.state as { game?: Game } | null)?.game ?? null,
  );
  const [loading, setLoading] = useState(gameId !== "demo");
  const [error, setError] = useState("");
  const [selectedCard, setSelectedCard] = useState<CardType | null>(null);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (gameId === "demo") {
      setLoading(false);
      return;
    }
    let active = true;
    getGame(gameId)
      .then((data) => {
        if (active) setGame(data);
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, "Impossible de charger la partie."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [gameId]);

  if (loading) return <div className="grid min-h-[55vh] place-items-center"><span className="loading-dot" /></div>;
  if (error && !game) {
    return (
      <div className="mx-auto max-w-2xl py-8">
        <Notice tone="error">{error}</Notice>
        <ButtonLink to="/lobby" variant="outline" className="mt-5">Retour aux salons</ButtonLink>
      </div>
    );
  }

  const gameTitle = game?.mode === "solo" ? "Course en solo" : "Course multijoueur";
  const playerName = user?.display_name ?? "Vous";
  const apiOpponents = game?.participants.filter(
    (participant) => participant.kind === "human" && participant.display_name !== playerName,
  ) ?? [];

  return (
    <div className="page-enter">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <Link to="/lobby" className="inline-flex items-center gap-2 text-sm font-bold text-stone-600 hover:text-forest">
          <ArrowLeft size={16} /> Quitter le plateau
        </Link>
        <span className="flex items-center gap-2 rounded-full border border-orange-200 bg-orange-50 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[.12em] text-orange-800">
          <Radio size={13} /> Aperçu du plateau
        </span>
      </div>

      <div className="game-preview-warning">
        <Info size={17} className="shrink-0" />
        <p>
          <strong>Les commandes de partie ne sont pas encore exposées par l’API.</strong>{" "}
          Les cartes, kilomètres et événements ci-dessous sont illustratifs. Aucun coup n’est joué ni règle calculée dans le navigateur.
        </p>
      </div>
      {error && <div className="mt-4"><Notice tone="error">{error}</Notice></div>}
      {notice && <div className="mt-4"><Notice>{notice}</Notice></div>}

      <div className="game-table">
        <header className="game-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-2xl bg-white/10 text-orange-300"><Flag size={18} /></span>
            <span className="min-w-0">
              <strong className="block truncate font-display text-lg font-extrabold text-cream">{gameTitle}</strong>
              <small className="text-xs text-cream/50">{game?.id ? `Salle ${game.id.slice(0, 8)}` : "Course de démonstration"}</small>
            </span>
          </div>
          <div className="game-turn-pill"><span className="turn-pulse" /> Votre tour <span className="hidden sm:inline">· Aperçu</span></div>
          <span className="hidden items-center gap-2 text-xs text-cream/55 sm:flex"><Clock3 size={14} /> 00:42</span>
        </header>

        <section className="opponent-board" aria-label="État illustratif des adversaires">
          {previewOpponents.slice(0, Math.max(1, game?.participants.length ?? 2) - 1).map((opponent, index) => (
            <article className="opponent-board-card" key={opponent.name}>
              <div className="flex items-center gap-3">
                <span className={`opponent-avatar opponent-avatar-${index}`}>{opponent.name.slice(0, 1)}</span>
                <span className="min-w-0">
                  <strong className="block truncate text-sm text-cream">{apiOpponents[index]?.display_name ?? opponent.name}</strong>
                  <small className="text-[10px] text-cream/45">{opponent.danger}</small>
                </span>
              </div>
              <div className="opponent-km"><strong>{opponent.distance}</strong><span>km</span></div>
              <div className="mt-3 flex items-center justify-between gap-2">
                <div className="flex -space-x-5">
                  {[0, 1, 2, 3].map((index) => (
                    <GameCard key={index} back size="small" className="scale-[.62] origin-top-left -mr-7" />
                  ))}
                </div>
                <span className="text-[9px] font-bold uppercase tracking-wider text-cream/40">Main cachée</span>
              </div>
            </article>
          ))}
          <div className="opponent-note">
            <span className="grid size-8 place-items-center rounded-xl bg-white/8 text-orange-300"><Sparkles size={15} /></span>
            <span><strong>Le peloton</strong><small>Illustration uniquement</small></span>
          </div>
        </section>

        <section className="road-board" aria-label="Piste de course illustrative">
          <div className="road-board-top">
            <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-[.14em] text-cream/55"><Gauge size={15} /> La route</span>
            <span className="text-xs font-semibold text-cream/45">Objectif illustratif · 1 000 km</span>
          </div>
          <div className="road-progress-wrap">
            <div className="road-progress-label">
              <span>{playerName}</span>
              <strong>325 <small>km</small></strong>
            </div>
            <div className="road-track">
              <span className="road-track-fill" style={{ width: "32.5%" }} />
              <span className="road-car-marker" style={{ left: "32.5%" }}>🚙</span>
              <span className="road-finish-marker"><Flag size={13} /> 1 000</span>
            </div>
            <div className="road-ticks"><span>0 km</span><span>500 km</span><span>1 000 km</span></div>
          </div>
          <div className="road-boards">
            <BattleBoard title="Votre route" icon={<ShieldCheck size={15} />} status="Feu vert" tone="good" />
            <BattleBoard title="Limitation" icon={<Gauge size={15} />} status="Libre" tone="neutral" />
            <BattleBoard title="Bottes actives" icon={<Sparkles size={15} />} status="Aucune" tone="neutral" />
          </div>
        </section>

        <section className="game-bottom">
          <div className="game-hand-panel">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="eyebrow text-cream/45">Votre main</p>
                <h2 className="mt-1 font-display text-lg font-extrabold text-cream">Choisissez votre carte</h2>
              </div>
              <span className="rounded-full bg-white/8 px-3 py-1 text-[10px] font-bold text-cream/55">6 cartes · exemple</span>
            </div>
            <div className="game-hand">
              {previewCards.map((type, index) => (
                <GameCard
                  key={`${type}-${index}`}
                  type={type}
                  selected={selectedCard === type}
                  onClick={() => {
                    setSelectedCard(type);
                    setNotice("Sélection visuelle uniquement : l’API de jeu ne permet pas encore de jouer une carte.");
                  }}
                />
              ))}
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button
                onClick={() => setNotice("L’action « jouer » sera activée lorsque l’API de commandes de jeu sera disponible.")}
                disabled={!selectedCard}
              >
                Jouer la carte <ArrowRight size={16} />
              </Button>
              <Button
                variant="outline"
                className="border-white/15 bg-white/5 text-cream hover:bg-white/10"
                onClick={() => setNotice("La défausse est désactivée en aperçu : le moteur serveur doit valider cette action.")}
              >
                <Trash2 size={15} /> Défausser
              </Button>
            </div>
          </div>
          <aside className="game-log-panel">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm font-extrabold text-cream"><History size={16} /> Actions récentes</span>
              <span className="text-[9px] font-bold uppercase tracking-wider text-cream/35">Aperçu</span>
            </div>
            <ol className="mt-4 space-y-4">
              {previewHistory.map((item, index) => (
                <li className="game-log-item" key={`${item.who}-${index}`}>
                  <span className={`game-log-dot ${index === 0 ? "active" : ""}`} />
                  <span><strong>{item.who}</strong> {item.what}<small>{item.when}</small></span>
                </li>
              ))}
            </ol>
            <div className="mt-5 border-t border-white/10 pt-4">
              <ButtonLink to="/profile" variant="quiet" size="sm" className="text-cream/70 hover:bg-white/8 hover:text-cream">
                <Trophy size={14} /> Voir mon parcours
              </ButtonLink>
            </div>
          </aside>
        </section>
      </div>
      {game?.status === "finished" && (
        <div className="mt-6 text-center">
          <Button onClick={() => navigate(`/result/${game.id}`)}>Voir le résultat</Button>
        </div>
      )}
      <p className="mt-4 text-center text-[10px] text-stone-500">
        Données de plateau temporaires utilisées uniquement parce que l’API de jeu n’est pas encore disponible.
      </p>
    </div>
  );
}

function BattleBoard({
  title,
  icon,
  status,
  tone,
}: {
  title: string;
  icon: ReactNode;
  status: string;
  tone: "good" | "neutral";
}) {
  return (
    <div className="battle-board">
      <span className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wider text-cream/40">{icon}{title}</span>
      <strong className={tone === "good" ? "text-emerald-300" : "text-cream"}>{status}</strong>
    </div>
  );
}
