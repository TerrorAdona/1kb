import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  CalendarDays,
  LogOut,
  MapPinned,
  Pencil,
  Trophy,
  UserRound,
  BarChart2,
  Target,
  Gamepad2,
  Users,
} from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { useAuthStore } from "../auth/authStore";
import { getGameHistory, getPlayerStats } from "../games/gameApi";
import type { GameHistory, PlayerStats } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";
import { PageTitle } from "../../shared/components/PageTitle";

export function ProfilePage() {
  const user = useAuthStore((state) => state.user);
  const updateDisplayName = useAuthStore((state) => state.updateDisplayName);
  const signOut = useAuthStore((state) => state.signOut);
  const navigate = useNavigate();
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const [history, setHistory] = useState<GameHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([getPlayerStats(), getGameHistory()])
      .then(([nextStats, nextHistory]) => {
        if (!active) return;
        setStats(nextStats);
        setHistory(nextHistory);
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, "Impossible de charger vos statistiques."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await updateDisplayName(displayName);
      setEditing(false);
      setSuccess("Votre profil a été mis à jour.");
    } catch (cause) {
      setError(apiErrorMessage(cause, "Impossible de modifier votre profil."));
    } finally {
      setSaving(false);
    }
  }

  async function handleSignOut() {
    try {
      await signOut();
    } finally {
      navigate("/", { replace: true });
    }
  }

  const joinedAt = user?.date_joined
    ? new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" }).format(new Date(user.date_joined))
    : "—";

  const winRate = stats?.win_rate ?? 0;

  return (
    <div className="page-enter">
      <PageTitle
        eyebrow="Votre carnet de route"
        title="Mon profil"
        description="Votre identité de joueur, votre historique et vos kilomètres."
        action={
          <Button variant="outline" onClick={() => void handleSignOut()}>
            <LogOut size={16} /> Déconnexion
          </Button>
        }
      />
      {error && <div className="mb-5"><Notice tone="error">{error}</Notice></div>}
      {success && <div className="mb-5"><Notice tone="success">{success}</Notice></div>}

      <div className="grid gap-6 lg:grid-cols-[.8fr_1.2fr]">
        <section className="profile-card">
          <div className="profile-identity">
            <span className="profile-large-avatar">{user?.display_name.slice(0, 1).toUpperCase() ?? "?"}</span>
            <span className="profile-identity-copy">
              <span className="eyebrow text-cream/55">Joueur</span>
              <strong>{user?.display_name}</strong>
              <small>{user?.email}</small>
            </span>
          </div>
          <div className="mt-6 flex items-center gap-2 border-t border-white/10 pt-5 text-xs text-cream/60">
            <CalendarDays size={15} className="text-orange-300" />
            Sur la route depuis {joinedAt}
          </div>
          {editing ? (
            <form className="mt-6 space-y-3" onSubmit={saveProfile}>
              <label className="field-label text-cream/80">
                Nom de joueur
                <input
                  className="form-input"
                  value={displayName}
                  maxLength={40}
                  onChange={(event) => setDisplayName(event.target.value)}
                  required
                />
              </label>
              <div className="flex gap-2">
                <Button type="submit" size="sm" loading={saving}>Enregistrer</Button>
                <Button type="button" variant="quiet" size="sm" className="text-cream hover:bg-white/10" onClick={() => setEditing(false)}>
                  Annuler
                </Button>
              </div>
            </form>
          ) : (
            <Button variant="quiet" size="sm" className="mt-5 text-cream hover:bg-white/10" onClick={() => setEditing(true)}>
              <Pencil size={15} /> Modifier le profil
            </Button>
          )}
        </section>

        <section>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="eyebrow">Vos statistiques</p>
              <h2 className="mt-1 font-display text-xl font-black text-forest">Au compteur</h2>
            </div>
            <span className="grid size-10 place-items-center rounded-2xl bg-orange-100 text-orange-700"><Trophy size={18} /></span>
          </div>
          {loading ? (
            <div className="grid min-h-36 place-items-center rounded-3xl bg-white"><span className="loading-dot" /></div>
          ) : (
            <>
              <div className="stats-grid">
                <Stat label="Parties jouées" value={stats?.games_played ?? 0} icon={<Gamepad2 size={18} />} />
                <Stat label="Victoires" value={stats?.wins ?? 0} accent icon={<Trophy size={18} />} />
                <Stat label="Défaites" value={stats?.losses ?? 0} icon={<Target size={18} />} />
                <Stat label="Taux de victoire" value={`${winRate}%`} icon={<BarChart2 size={18} />} />
                <Stat label="Kilomètres cumulés" value={formatKm(stats?.total_kilometers ?? 0)} icon={<MapPinned size={18} />} />
                <Stat label="Meilleur score" value={formatKm(stats?.best_kilometers ?? 0)} icon={<Target size={18} />} />
                <Stat label="Moyenne / partie" value={formatKm(stats?.average_kilometers ?? 0)} icon={<BarChart2 size={18} />} />
                <Stat label="Parties solo" value={stats?.solo_games_played ?? 0} icon={<Gamepad2 size={18} />} />
                <Stat label="Parties multi" value={stats?.multiplayer_games_played ?? 0} icon={<Users size={18} />} />
              </div>

              <div className="mt-6">
                <h3 className="font-display text-lg font-extrabold text-cream mb-4">Répartition des résultats</h3>
                <div className="chart-container">
                  <WinRateChart winRate={winRate} />
                </div>
              </div>

              <div className="mt-6">
                <h3 className="font-display text-lg font-extrabold text-cream mb-4">Types de parties</h3>
                <div className="chart-container">
                  <GameTypeChart solo={stats?.solo_games_played ?? 0} multiplayer={stats?.multiplayer_games_played ?? 0} />
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      <section className="mt-9">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Vos dernières courses</p>
            <h2 className="mt-1 font-display text-xl font-black text-forest">Historique</h2>
          </div>
          <span className="text-xs font-semibold text-stone-500">{history.length} résultat(s)</span>
        </div>
        {loading ? (
          <div className="grid min-h-32 place-items-center rounded-3xl bg-white"><span className="loading-dot" /></div>
        ) : history.length ? (
          <div className="space-y-3">
            {history.map((item) => (
              <article key={item.id} className="history-row">
                <span className="history-icon"><MapPinned size={17} /></span>
                <div className="min-w-0 flex-1">
                  <strong className="block truncate text-sm text-forest">
                    {item.mode === "solo" ? "Course en solo" : "Course multijoueur"}
                  </strong>
                  <span className="mt-1 block text-xs text-stone-500">
                    {new Intl.DateTimeFormat("fr-FR", { dateStyle: "medium" }).format(new Date(item.completed_at))}
                    {" · "}{item.participants.length} participants
                  </span>
                </div>
                <span className="hidden text-right sm:block">
                  <small className="block text-[9px] font-bold uppercase tracking-wider text-stone-400">Vainqueur</small>
                  <strong className="text-sm text-forest">{item.winner_display_name}</strong>
                </span>
                <Link to={`/result/${item.id}`} className="grid size-9 place-items-center rounded-full text-forest hover:bg-forest/8" aria-label="Voir le résultat">
                  <ArrowRight size={16} />
                </Link>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <UserRound size={22} />
            <strong>Votre première course vous attend</strong>
            <span>Une fois une partie terminée côté serveur, son résultat apparaîtra ici.</span>
            <Link to="/solo" className="mt-1 text-xs font-bold text-orange-700">Configurer une partie solo →</Link>
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value, accent = false, icon }: { label: string; value: string | number; accent?: boolean; icon?: React.ReactNode }) {
  return (
    <div className="stat-tile">
      <div className="flex items-center gap-2 mb-1">
        {icon && <span className={accent ? "text-orange-600" : "text-forest/60"}>{icon}</span>}
        <span className="text-xs font-semibold text-stone-500">{label}</span>
      </div>
      <strong className={accent ? "text-orange-700" : "text-forest"}>{value}</strong>
    </div>
  );
}

function formatKm(value: number) {
  return `${new Intl.NumberFormat("fr-FR").format(value)} km`;
}

function WinRateChart({ winRate }: { winRate: number }) {
  const lossRate = 100 - winRate;
  return (
    <div className="w-full max-w-xs mx-auto">
      <div className="relative h-32 mb-4">
        <div className="absolute inset-0 flex items-center justify-center">
          <svg viewBox="0 0 100 100" className="w-28 h-28 -rotate-90">
            <circle
              cx="50"
              cy="50"
              r="45"
              stroke="#e5e7eb"
              strokeWidth="8"
              fill="none"
            />
            <circle
              cx="50"
              cy="50"
              r="45"
              stroke="#22c55e"
              strokeWidth="8"
              fill="none"
              strokeDasharray={282.743}
              strokeDashoffset={282.743 * (1 - winRate / 100)}
              strokeLinecap="round"
              className="transition-all duration-1000"
              style={{ transformOrigin: "center" }}
            />
            {lossRate > 0 && (
              <circle
                cx="50"
                cy="50"
                r="45"
                stroke="#ef4444"
                strokeWidth="8"
                fill="none"
                strokeDasharray={282.743}
                strokeDashoffset={282.743 * (winRate / 100)}
                strokeLinecap="round"
                className="transition-all duration-1000"
              />
            )}
          </svg>
          <div className="text-center">
            <strong className="text-2xl font-black text-forest">{winRate}%</strong>
            <span className="block text-xs text-stone-500">Taux de victoire</span>
          </div>
        </div>
      </div>
      <div className="flex justify-center gap-6 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-emerald-500" />
          <span className="text-stone-600">Victoires</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-stone-600">Défaites</span>
        </div>
      </div>
    </div>
  );
}

function GameTypeChart({ solo, multiplayer }: { solo: number; multiplayer: number }) {
  const total = solo + multiplayer;
  if (total === 0) {
    return (
      <div className="w-full max-w-xs mx-auto text-center text-stone-500 py-8">
        Aucune partie jouée
      </div>
    );
  }
  const soloPercent = (solo / total) * 100;
  const multiPercent = (multiplayer / total) * 100;
  return (
    <div className="w-full max-w-xs mx-auto">
      <div className="relative h-32 mb-4">
        <div className="absolute inset-0 flex items-center justify-center">
          <svg viewBox="0 0 100 100" className="w-28 h-28 -rotate-90">
            <circle
              cx="50"
              cy="50"
              r="45"
              stroke="#e5e7eb"
              strokeWidth="8"
              fill="none"
            />
            {solo > 0 && (
              <circle
                cx="50"
                cy="50"
                r="45"
                stroke="#3b82f6"
                strokeWidth="8"
                fill="none"
                strokeDasharray={282.743}
                strokeDashoffset={282.743 * (1 - soloPercent / 100)}
                strokeLinecap="round"
                className="transition-all duration-1000"
              />
            )}
            {multiplayer > 0 && (
              <circle
                cx="50"
                cy="50"
                r="45"
                stroke="#f59e0b"
                strokeWidth="8"
                fill="none"
                strokeDasharray={282.743}
                strokeDashoffset={solo > 0 ? 282.743 * (1 - multiPercent / 100) : 282.743 * (1 - multiPercent / 100)}
                strokeLinecap="round"
                className="transition-all duration-1000"
              />
            )}
          </svg>
          <div className="text-center">
            <strong className="text-2xl font-black text-forest">{total}</strong>
            <span className="block text-xs text-stone-500">Parties totales</span>
          </div>
        </div>
      </div>
      <div className="flex justify-center gap-6 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-blue-500" />
          <span className="text-stone-600">Solo ({solo})</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-amber-500" />
          <span className="text-stone-600">Multijoueur ({multiplayer})</span>
        </div>
      </div>
    </div>
  );
}
