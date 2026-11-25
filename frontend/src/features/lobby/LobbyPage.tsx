import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  DoorOpen,
  LockKeyhole,
  Plus,
  RefreshCw,
  UsersRound,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import {
  createGame,
  joinGame,
  listAvailableGames,
} from "../games/gameApi";
import type { CreatedGame, Game, GameVisibility } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";
import { PageTitle } from "../../shared/components/PageTitle";

export function LobbyPage() {
  const navigate = useNavigate();
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [joining, setJoining] = useState(false);
  const [visibility, setVisibility] = useState<GameVisibility>("private");
  const [maxPlayers, setMaxPlayers] = useState(4);
  const [gameId, setGameId] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [error, setError] = useState("");

  async function loadGames(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      setGames(await listAvailableGames());
      setError("");
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de charger les salons disponibles."));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadGames();
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setError("");
    try {
      const created: CreatedGame = await createGame({
        mode: "multiplayer",
        visibility,
        max_players: maxPlayers,
      });
      navigate(`/lobby/${created.id}`, {
        state: { inviteCode: created.invite_code ?? "" },
      });
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de créer ce salon."));
    } finally {
      setCreating(false);
    }
  }

  async function handleJoinByCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setJoining(true);
    setError("");
    try {
      const game = await joinGame(gameId.trim(), inviteCode.trim());
      navigate(`/lobby/${game.id}`);
    } catch (cause) {
      setError(apiErrorMessage(cause, "Vérifiez l’identifiant du salon et son code d’invitation."));
    } finally {
      setJoining(false);
    }
  }

  async function handleJoinPublic(targetGame: Game) {
    setJoining(true);
    setError("");
    try {
      await joinGame(targetGame.id);
      navigate(`/lobby/${targetGame.id}`);
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de rejoindre ce salon."));
    } finally {
      setJoining(false);
    }
  }

  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="Le départ se prépare ici"
        title="Salon multijoueur"
        description="Créez une table privée ou trouvez une partie publique prête à vous accueillir."
        action={
          <Button variant="outline" onClick={() => void loadGames(true)} loading={refreshing}>
            <RefreshCw size={16} /> Actualiser
          </Button>
        }
      />

      {error && <div className="mb-6"><Notice tone="error">{error}</Notice></div>}
      <div className="grid gap-6 lg:grid-cols-[.9fr_1.1fr]">
        <section className="panel-card">
          <div className="section-heading">
            <span className="section-icon"><Plus size={18} /></span>
            <div>
              <h2>Créer une partie</h2>
              <p>Choisissez votre salon et invitez les autres joueurs.</p>
            </div>
          </div>
          <form className="mt-7 space-y-5" onSubmit={handleCreate}>
            <fieldset>
              <legend className="field-label mb-2">Type de salon</legend>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  className={`choice-tile ${visibility === "private" ? "is-active" : ""}`}
                  onClick={() => setVisibility("private")}
                >
                  <LockKeyhole size={17} />
                  <span><strong>Privé</strong><small>Sur invitation</small></span>
                </button>
                <button
                  type="button"
                  className={`choice-tile ${visibility === "public" ? "is-active" : ""}`}
                  onClick={() => setVisibility("public")}
                >
                  <UsersRound size={17} />
                  <span><strong>Public</strong><small>Ouvert à tous</small></span>
                </button>
              </div>
            </fieldset>
            <label className="field-label">
              Nombre de places
              <select
                className="form-input"
                value={maxPlayers}
                onChange={(event) => setMaxPlayers(Number(event.target.value))}
              >
                {[2, 3, 4].map((count) => (
                  <option key={count} value={count}>{count} joueurs maximum</option>
                ))}
              </select>
            </label>
            <Button type="submit" size="lg" loading={creating} className="w-full">
              Créer le salon <ArrowRight size={17} />
            </Button>
          </form>
          <div className="mt-5 flex items-start gap-2 rounded-xl bg-paper-strong p-3 text-xs leading-5 text-stone-600">
            <LockKeyhole size={14} className="mt-0.5 shrink-0 text-forest" />
            {visibility === "private"
              ? "Le code privé n’est affiché qu’à la création. Gardez-le pour le partager."
              : "Les salons publics apparaissent dans la liste à droite."}
          </div>
        </section>

        <section className="panel-card">
          <div className="section-heading">
            <span className="section-icon section-icon-orange"><DoorOpen size={18} /></span>
            <div>
              <h2>Rejoindre une partie</h2>
              <p>Entrez les informations reçues de votre hôte.</p>
            </div>
          </div>
          <form className="mt-6 grid gap-3 sm:grid-cols-[1fr_.8fr_auto]" onSubmit={handleJoinByCode}>
            <label className="field-label">
              Identifiant du salon
              <input
                className="form-input"
                value={gameId}
                onChange={(event) => setGameId(event.target.value)}
                placeholder="UUID du salon"
                required
              />
            </label>
            <label className="field-label">
              Code d’invitation
              <input
                className="form-input font-mono uppercase tracking-widest"
                value={inviteCode}
                onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                placeholder="ABCD…"
                required
              />
            </label>
            <Button type="submit" loading={joining} className="self-end">
              Entrer
            </Button>
          </form>
          <div className="my-6 flex items-center gap-3 text-[10px] font-bold uppercase tracking-[.18em] text-stone-400">
            <span className="h-px flex-1 bg-stone-200" /> Ou rejoindre un salon public <span className="h-px flex-1 bg-stone-200" />
          </div>
          {loading ? (
            <div className="grid min-h-32 place-items-center"><span className="loading-dot" /></div>
          ) : games.length ? (
            <div className="space-y-3">
              {games.map((game) => (
                <PublicGameRow
                  key={game.id}
                  game={game}
                  disabled={joining}
                  onJoin={() => void handleJoinPublic(game)}
                />
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <UsersRound size={23} />
              <strong>Pas de salon public pour le moment</strong>
              <span>Créez une table publique ou invitez vos amis.</span>
            </div>
          )}
        </section>
      </div>
      <p className="mt-6 text-center text-xs leading-5 text-stone-500">
        Pour une invitation privée, l’API demande l’identifiant du salon et son code. Un code seul ne permet pas encore de retrouver une partie.
      </p>
    </div>
  );
}

function PublicGameRow({
  game,
  disabled,
  onJoin,
}: {
  game: Game;
  disabled: boolean;
  onJoin: () => void;
}) {
  return (
    <article className="public-game-row">
      <div className="grid size-11 place-items-center rounded-2xl bg-forest/7 text-forest">
        <UsersRound size={18} />
      </div>
      <div className="min-w-0 flex-1">
        <strong className="block truncate text-sm text-forest">{game.host_display_name} vous attend</strong>
        <span className="mt-1 block text-xs text-stone-500">
          {game.seats_taken}/{game.max_players} joueurs · {game.available_seats} places libres
        </span>
      </div>
      <Button size="sm" variant="outline" disabled={disabled} onClick={onJoin}>
        Rejoindre
      </Button>
    </article>
  );
}
