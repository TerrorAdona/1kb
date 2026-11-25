import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  Check,
  Copy,
  DoorOpen,
  Radio,
  RefreshCw,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { useAuthStore } from "../auth/authStore";
import {
  getGame,
  leaveGame,
  setReady,
  startGame,
} from "../games/gameApi";
import { useLobbySocket } from "../games/useLobbySocket";
import type { Game } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button, ButtonLink } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";
import { PageTitle } from "../../shared/components/PageTitle";

export function RoomPage() {
  const { gameId = "" } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const [game, setGame] = useState<Game | null>(null);
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const inviteCode = (location.state as { inviteCode?: string } | null)?.inviteCode;

  const reload = useCallback(async () => {
    if (!gameId) return;
    try {
      setGame(await getGame(gameId));
      setError("");
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de charger les informations du salon."));
    }
  }, [gameId]);

  const socketStatus = useLobbySocket(gameId, reload);

  useEffect(() => {
    void reload();
  }, [reload]);

  const currentParticipant = useMemo(
    () => game?.participants.find((participant) => participant.kind === "human" && participant.display_name === user?.display_name),
    [game?.participants, user?.display_name],
  );
  const isHost = game?.host_display_name === user?.display_name;
  const humans = game?.participants.filter((participant) => participant.kind === "human") ?? [];
  const allReady = humans.length >= 2 && humans.every((participant) => participant.is_ready);

  async function toggleReady() {
    if (!game || !currentParticipant) return;
    setWorking(true);
    try {
      await setReady(game.id, !currentParticipant.is_ready);
      await reload();
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de modifier votre statut."));
    } finally {
      setWorking(false);
    }
  }

  async function beginGame() {
    if (!game) return;
    setWorking(true);
    try {
      const started = await startGame(game.id);
      navigate(`/game/${started.id}`, { state: { game: started } });
    } catch (cause) {
      setError(apiErrorMessage(cause, "La partie ne peut pas encore démarrer."));
    } finally {
      setWorking(false);
    }
  }

  async function exitRoom() {
    if (!game) return;
    setWorking(true);
    try {
      await leaveGame(game.id);
      navigate("/lobby");
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de quitter ce salon."));
      setWorking(false);
    }
  }

  async function copyInvite() {
    if (!inviteCode || !navigator.clipboard) return;
    await navigator.clipboard.writeText(inviteCode);
  }

  if (!game && !error) {
    return <div className="grid min-h-[55vh] place-items-center"><span className="loading-dot" /></div>;
  }

  return (
    <div className="page-enter">
      <Link to="/lobby" className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-stone-600 hover:text-forest">
        <ArrowLeft size={16} /> Tous les salons
      </Link>
      {error && <div className="mb-5"><Notice tone="error">{error}</Notice></div>}
      {game && (
        <>
          <PageTitle
            eyebrow={game.visibility === "private" ? "Salon privé" : "Salon public"}
            title="La ligne de départ"
            description="Vérifiez les places, confirmez votre présence et attendez le signal de l’hôte."
            action={
              <span className={`socket-pill socket-${socketStatus}`}>
                <Radio size={14} />
                {socketStatus === "connected" ? "En direct" : socketStatus === "connecting" ? "Connexion…" : "Hors ligne"}
              </span>
            }
          />
          {inviteCode && (
            <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-orange-200 bg-orange-50 p-4">
              <div>
                <p className="text-[10px] font-extrabold uppercase tracking-[.16em] text-orange-800">Votre code d’invitation</p>
                <strong className="mt-1 block font-mono text-lg tracking-[.2em] text-forest">{inviteCode}</strong>
                <span className="text-xs text-stone-500">Il ne sera plus disponible après avoir quitté cette page.</span>
              </div>
              <Button size="sm" variant="outline" onClick={() => void copyInvite()}><Copy size={15} /> Copier</Button>
            </div>
          )}
          <div className="grid gap-6 lg:grid-cols-[1fr_330px]">
            <section className="panel-card">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-100 pb-5">
                <div className="flex items-center gap-3">
                  <span className="section-icon"><UsersRound size={18} /></span>
                  <div>
                    <h2 className="font-display text-xl font-extrabold text-forest">Joueurs inscrits</h2>
                    <p className="mt-0.5 text-xs text-stone-500">Hôte : {game.host_display_name}</p>
                  </div>
                </div>
                <span className="rounded-full bg-paper-strong px-3 py-1.5 text-xs font-bold text-stone-600">
                  {game.seats_taken} / {game.max_players} places
                </span>
              </div>
              <div className="mt-5 space-y-3">
                {game.participants.map((participant) => {
                  const ready = participant.kind === "bot" || participant.is_ready;
                  return (
                    <div className="participant-row" key={participant.id}>
                      <span className={`participant-avatar ${participant.kind === "bot" ? "bg-orange-100 text-orange-700" : "bg-forest/8 text-forest"}`}>
                        {participant.display_name.slice(0, 1).toUpperCase()}
                      </span>
                      <span className="min-w-0 flex-1">
                        <strong className="block truncate text-sm text-forest">
                          {participant.display_name}
                          {participant.display_name === game.host_display_name && <span className="ml-2 text-[9px] uppercase tracking-wider text-orange-700">Hôte</span>}
                        </strong>
                        <small className="text-xs text-stone-500">
                          {participant.kind === "bot"
                            ? `Adversaire IA · ${difficultyLabel(participant.bot_difficulty)}`
                            : participant.display_name === user?.display_name
                              ? "Vous"
                              : `Siège ${participant.seat_number}`}
                        </small>
                      </span>
                      <span className={`ready-status ${ready ? "ready" : "not-ready"}`}>
                        {ready ? <Check size={13} /> : <span className="size-2 rounded-full bg-current" />}
                        {ready ? "Prêt" : "En attente"}
                      </span>
                    </div>
                  );
                })}
                {Array.from({ length: game.available_seats }).map((_, index) => (
                  <div className="participant-row opacity-55" key={`empty-${index}`}>
                    <span className="participant-avatar bg-paper-strong text-stone-400">·</span>
                    <span className="flex-1 text-sm font-semibold text-stone-500">Place disponible</span>
                    <span className="text-xs text-stone-400">En attente</span>
                  </div>
                ))}
              </div>
              <div className="mt-7 flex flex-wrap gap-3 border-t border-stone-100 pt-5">
                <Button
                  variant={currentParticipant?.is_ready ? "outline" : "secondary"}
                  disabled={!currentParticipant || working || game.status !== "waiting"}
                  loading={working}
                  onClick={() => void toggleReady()}
                >
                  <ShieldCheck size={16} />
                  {currentParticipant?.is_ready ? "Annuler ma présence" : "Je suis prêt"}
                </Button>
                {isHost && (
                  <Button
                    disabled={!allReady || working || game.status !== "waiting"}
                    loading={working}
                    onClick={() => void beginGame()}
                  >
                    Démarrer la partie
                  </Button>
                )}
                <Button variant="quiet" disabled={working} onClick={() => void exitRoom()}>
                  <DoorOpen size={16} /> Quitter
                </Button>
              </div>
              {isHost && !allReady && game.status === "waiting" && (
                <p className="mt-3 text-xs text-stone-500">
                  L’hôte pourra démarrer lorsque tous les joueurs humains seront prêts (2 minimum).
                </p>
              )}
            </section>
            <aside className="space-y-5">
              <div className="side-note-card">
                <div className="flex items-center justify-between">
                  <span className="eyebrow text-cream/55">Identifiant de salle</span>
                  <Button size="sm" variant="quiet" onClick={() => void navigator.clipboard?.writeText(game.id)} className="min-h-8 px-2 text-cream">
                    <Copy size={14} /> Copier
                  </Button>
                </div>
                <code className="mt-3 block break-all text-xs leading-5 text-cream/85">{game.id}</code>
                <p className="mt-3 text-xs leading-5 text-cream/50">Pour un salon privé, partagez aussi le code d’invitation.</p>
              </div>
              <div className="panel-card !p-5">
                <div className="flex items-center gap-3">
                  <span className="section-icon section-icon-orange"><RefreshCw size={16} /></span>
                  <div>
                    <h3 className="text-sm font-extrabold text-forest">Salon synchronisé</h3>
                    <p className="mt-1 text-xs leading-5 text-stone-500">
                      {socketStatus === "connected"
                        ? "Les changements de présence sont reçus en direct."
                        : "La liste reste consultable ; la connexion temps réel est indisponible."}
                    </p>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </>
      )}
      {!game && error && (
        <div className="panel-card text-center">
          <p className="font-bold text-forest">Ce salon n’est pas accessible.</p>
          <ButtonLink to="/lobby" variant="outline" className="mt-4">Retour aux salons</ButtonLink>
        </div>
      )}
    </div>
  );
}

function difficultyLabel(value: string) {
  return value === "hard" ? "difficile" : value === "easy" ? "facile" : "normale";
}
