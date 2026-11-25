import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  Gauge,
  ShieldCheck,
  Sparkles,
  UsersRound,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { createGame, startGame } from "../games/gameApi";
import type { BotDifficulty } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";
import { PageTitle } from "../../shared/components/PageTitle";

const difficultyChoices: Array<{
  id: BotDifficulty;
  name: string;
  tagline: string;
  description: string;
  icon: typeof Gauge;
}> = [
  {
    id: "easy",
    name: "Détente",
    tagline: "Facile",
    description: "Une course tranquille pour retrouver les sensations.",
    icon: Sparkles,
  },
  {
    id: "normal",
    name: "Équilibrée",
    tagline: "Normale",
    description: "Des bots qui avancent, réparent et mettent la pression.",
    icon: Gauge,
  },
  {
    id: "hard",
    name: "Compétitive",
    tagline: "Difficile",
    description: "Une stratégie plus attentive à la course et aux risques.",
    icon: ShieldCheck,
  },
];

export function SoloSetupPage() {
  const navigate = useNavigate();
  const [opponents, setOpponents] = useState(2);
  const [difficulty, setDifficulty] = useState<BotDifficulty>("normal");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startSoloGame() {
    setLoading(true);
    setError("");
    try {
      const created = await createGame({
        mode: "solo",
        visibility: "private",
        max_players: opponents + 1,
        bot_difficulty: difficulty,
      });
      const started = await startGame(created.id);
      navigate(`/game/${started.id}`, { state: { game: started } });
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de préparer la partie solo."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-enter">
      <Link to="/" className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-stone-600 hover:text-forest">
        <ArrowLeft size={16} /> Retour à l’accueil
      </Link>
      <PageTitle
        eyebrow="Configuration de course"
        title="Votre course, vos réglages."
        description="Choisissez vos adversaires et leur niveau. Les bots appliquent leurs décisions via le moteur serveur."
      />
      {error && <div className="mb-5"><Notice tone="error">{error}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <section className="panel-card">
            <div className="section-heading">
              <span className="section-icon"><UsersRound size={18} /></span>
              <div>
                <h2>Vos adversaires</h2>
                <p>Choisissez le nombre de bots autour de la table.</p>
              </div>
            </div>
            <div className="mt-6 grid grid-cols-3 gap-3">
              {[1, 2, 3].map((count) => (
                <button
                  type="button"
                  key={count}
                  onClick={() => setOpponents(count)}
                  className={`opponent-option ${opponents === count ? "is-active" : ""}`}
                  aria-pressed={opponents === count}
                >
                  <span className="font-display text-3xl font-black">{count}</span>
                  <span className="mt-1 text-xs font-bold">{count === 1 ? "adversaire" : "adversaires"}</span>
                  <span className="mt-3 flex items-center justify-center -space-x-2">
                    {Array.from({ length: count }).map((_, index) => (
                      <span key={index} className="grid size-7 place-items-center rounded-full border-2 border-white bg-forest text-cream">
                        <Bot size={13} />
                      </span>
                    ))}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel-card">
            <div className="section-heading">
              <span className="section-icon section-icon-orange"><Gauge size={18} /></span>
              <div>
                <h2>Niveau de stratégie</h2>
                <p>Vous pourrez changer la difficulté avant une prochaine partie.</p>
              </div>
            </div>
            <div className="mt-6 grid gap-3 md:grid-cols-3">
              {difficultyChoices.map(({ id, name, tagline, description, icon: Icon }) => (
                <button
                  type="button"
                  key={id}
                  onClick={() => setDifficulty(id)}
                  className={`difficulty-card ${difficulty === id ? "is-active" : ""}`}
                  aria-pressed={difficulty === id}
                >
                  <span className="flex items-center justify-between">
                    <span className="difficulty-icon"><Icon size={17} /></span>
                    {difficulty === id && <span className="difficulty-check">✓</span>}
                  </span>
                  <span className="mt-4 block text-[10px] font-extrabold uppercase tracking-[.18em] text-orange-700">{tagline}</span>
                  <strong className="mt-1 block font-display text-lg font-extrabold text-forest">{name}</strong>
                  <span className="mt-2 block text-xs leading-5 text-stone-500">{description}</span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <aside className="solo-summary">
          <div className="summary-road-mark" aria-hidden="true">1000</div>
          <p className="eyebrow text-cream/55">Prêt au départ</p>
          <h2 className="mt-2 font-display text-2xl font-black text-cream">Votre table est prête.</h2>
          <div className="mt-6 space-y-3">
            <div className="summary-line">
              <span><UsersRound size={15} /> Participants</span>
              <strong>{opponents + 1} joueurs</strong>
            </div>
            <div className="summary-line">
              <span><Bot size={15} /> Adversaires IA</span>
              <strong>{opponents}</strong>
            </div>
            <div className="summary-line">
              <span><Gauge size={15} /> Niveau</span>
              <strong>{difficultyChoices.find((choice) => choice.id === difficulty)?.name}</strong>
            </div>
          </div>
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4 text-xs leading-5 text-cream/65">
            <span className="flex items-center gap-2 font-bold text-cream"><ShieldCheck size={15} className="text-orange-300" /> Règles côté serveur</span>
            Les cartes et les actions restent validées par le moteur du jeu.
          </div>
          <Button
            size="lg"
            loading={loading}
            onClick={() => void startSoloGame()}
            className="mt-6 w-full"
          >
            Commencer <ArrowRight size={17} />
          </Button>
          <p className="mt-3 text-center text-[10px] leading-4 text-cream/45">
            La partie sera créée dans votre historique après sa finalisation par le serveur.
          </p>
        </aside>
      </div>
    </div>
  );
}
