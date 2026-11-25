import { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Flag,
  Medal,
  RotateCcw,
  Sparkles,
  Trophy,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { getGameHistory } from "../games/gameApi";
import type { GameHistory } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { ButtonLink } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";

const demoResult: GameHistory = {
  id: "demo",
  mode: "solo",
  ruleset_version: "mille-bornes-v1",
  winner_display_name: "Vous",
  completed_at: new Date("2025-06-14T15:30:00Z").toISOString(),
  participants: [
    { display_name: "Vous", kind: "human", seat_number: 1, kilometers: 1000, placement: 1 },
    { display_name: "Camille", kind: "bot", seat_number: 2, kilometers: 825, placement: 2 },
    { display_name: "Alex", kind: "bot", seat_number: 3, kilometers: 650, placement: 3 },
  ],
};

export function ResultPage() {
  const { gameId = "" } = useParams();
  const [result, setResult] = useState<GameHistory | null>(gameId === "demo" ? demoResult : null);
  const [loading, setLoading] = useState(gameId !== "demo");
  const [error, setError] = useState("");

  useEffect(() => {
    if (gameId === "demo") return;
    let active = true;
    getGameHistory()
      .then((history) => {
        if (!active) return;
        const found = history.find((item) => item.id === gameId);
        if (found) setResult(found);
        else setError("Aucun résultat terminé ne correspond à cette partie.");
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, "Impossible de charger le résultat."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [gameId]);

  if (loading) return <div className="grid min-h-[55vh] place-items-center"><span className="loading-dot" /></div>;
  if (!result) {
    return (
      <section className="mx-auto max-w-xl py-8">
        <Link to="/profile" className="inline-flex items-center gap-2 text-sm font-bold text-forest"><ArrowLeft size={16} /> Mon profil</Link>
        <div className="mt-6"><Notice tone={error ? "error" : "info"}>{error || "Résultat indisponible."}</Notice></div>
        <p className="mt-4 text-sm leading-6 text-stone-600">
          L’historique est fourni par le backend après la fin de partie. Une partie encore active n’a pas de résultat à afficher.
        </p>
        <ButtonLink to="/solo" className="mt-5">Configurer une partie</ButtonLink>
      </section>
    );
  }

  const winner = result.participants.find(
    (participant) => participant.display_name === result.winner_display_name,
  );
  const isDemo = result.id === "demo";

  return (
    <section className="mx-auto max-w-4xl py-4 page-enter">
      <div className="result-hero">
        <span className="result-confetti result-confetti-one" />
        <span className="result-confetti result-confetti-two" />
        <span className="result-trophy"><Trophy size={29} /></span>
        <p className="mt-5 text-xs font-extrabold uppercase tracking-[.24em] text-orange-300">
          {isDemo ? "Écran de démonstration" : "Course terminée"}
        </p>
        <h1 className="mt-2 font-display text-4xl font-black text-cream sm:text-5xl">
          {result.winner_display_name} <span className="text-orange-300">l’emporte !</span>
        </h1>
        <p className="mt-3 text-sm text-cream/60">
          {isDemo
            ? "Exemple visuel uniquement — ce résultat n’est pas enregistré."
            : `Partie du ${new Intl.DateTimeFormat("fr-FR", { dateStyle: "long" }).format(new Date(result.completed_at))}`}
        </p>
        <div className="result-distance">
          <strong>{winner?.kilometers ?? 0}</strong>
          <span>kilomètres parcourus</span>
          <Flag size={19} className="ml-2 text-orange-300" />
        </div>
        {isDemo && (
          <div className="mx-auto mt-5 max-w-lg rounded-2xl border border-white/10 bg-white/5 p-3 text-xs leading-5 text-cream/60">
            L’API de résultat existe, mais seul le serveur peut enregistrer et certifier le gagnant et les kilomètres.
          </div>
        )}
      </div>

      <div className="result-leaderboard">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <p className="eyebrow">Classement final</p>
            <h2 className="mt-1 font-display text-xl font-black text-forest">La ligne d’arrivée</h2>
          </div>
          <span className="grid size-10 place-items-center rounded-2xl bg-orange-100 text-orange-700"><Medal size={18} /></span>
        </div>
        <div className="space-y-2">
          {[...result.participants]
            .sort((a, b) => (a.placement ?? 99) - (b.placement ?? 99))
            .map((participant, index) => (
              <div className={`result-row ${index === 0 ? "winner-row" : ""}`} key={`${participant.seat_number}-${participant.display_name}`}>
                <span className={`result-position ${index === 0 ? "first" : ""}`}>{participant.placement ?? index + 1}</span>
                <span className="min-w-0 flex-1">
                  <strong className="block truncate text-sm text-forest">{participant.display_name}</strong>
                  <small className="text-xs text-stone-500">{participant.kind === "bot" ? "Adversaire IA" : "Joueur"}</small>
                </span>
                <strong className="font-display text-lg font-black text-forest">{participant.kilometers}<small className="ml-1 text-[10px] font-bold text-stone-500">km</small></strong>
                {index === 0 && <Sparkles size={16} className="ml-2 text-orange-500" />}
              </div>
            ))}
        </div>
      </div>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <ButtonLink to={result.mode === "solo" ? "/solo" : "/lobby"} size="lg">
          <RotateCcw size={17} /> Rejouer
        </ButtonLink>
        <ButtonLink to="/profile" variant="outline" size="lg">
          Mon profil <ArrowRight size={17} />
        </ButtonLink>
      </div>
    </section>
  );
}
