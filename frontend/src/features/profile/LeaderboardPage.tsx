import { useEffect, useState } from "react";
import { ArrowLeft, Trophy, Gamepad2, Users, ChevronLeft, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuthStore } from "../auth/authStore";
import { getLeaderboard } from "../games/gameApi";
import type { LeaderboardEntry } from "../../shared/types/api";
import { apiErrorMessage } from "../../shared/api/errors";
import { Button } from "../../shared/components/Button";
import { Notice } from "../../shared/components/Notice";
import { PageTitle } from "../../shared/components/PageTitle";

export function LeaderboardPage() {
  const user = useAuthStore((state) => state.user);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  useEffect(() => {
    let active = true;
    getLeaderboard(100)
      .then((data) => {
        if (!active) return;
        setLeaderboard(data);
      })
      .catch((cause: unknown) => {
        if (active) setError(apiErrorMessage(cause, "Impossible de charger le classement."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const totalPages = Math.ceil(leaderboard.length / itemsPerPage);
  const paginatedLeaderboard = leaderboard.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const userEntry = leaderboard.find((entry) => entry.user_id === user?.id);
  const userRank = userEntry ? leaderboard.indexOf(userEntry) + 1 : null;

  return (
    <div className="page-enter">
      <Link to="/profile" className="mb-5 inline-flex items-center gap-2 text-sm font-bold text-stone-600 hover:text-forest">
        <ArrowLeft size={16} /> Retour au profil
      </Link>
      <PageTitle
        eyebrow="Classement général"
        title="Les champions de la route"
        description="Les meilleurs joueurs classés par victoires, puis kilomètres totaux."
      />
      {error && <div className="mb-5"><Notice tone="error">{error}</Notice></div>}

      {userRank && (
        <div className="mb-6 p-4 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-orange-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="grid size-12 place-items-center rounded-xl bg-orange-100 text-orange-700">
                <Trophy size={20} />
              </span>
              <div>
                <p className="text-sm font-semibold text-forest">Votre position</p>
                <p className="font-display text-2xl font-black text-orange-700">#{userRank} sur {leaderboard.length}</p>
              </div>
            </div>
            <div className="text-right text-sm">
              <p className="text-stone-500">{userEntry?.wins} victoires · {userEntry?.win_rate}% taux</p>
              <p className="text-stone-500">{formatKm(userEntry?.total_kilometers ?? 0)} km au total</p>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid min-h-64 place-items-center rounded-3xl bg-white"><span className="loading-dot" /></div>
      ) : leaderboard.length ? (
        <div className="space-y-4">
          {paginatedLeaderboard.map((entry) => (
            <LeaderboardRow key={entry.user_id} entry={entry} rank={entry.rank} isCurrentUser={entry.user_id === user?.id} />
          ))}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={16} />
              </Button>
              <span className="text-sm font-semibold text-forest">
                Page {currentPage} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === totalPages}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              >
                <ChevronRight size={16} />
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="empty-state">
          <Trophy size={22} />
          <strong>Aucun joueur classé</strong>
          <span>Les statistiques apparaîtront une fois des parties terminées.</span>
        </div>
      )}

      <p className="mt-6 text-center text-[10px] text-stone-500">
        Classement basé sur les parties terminées uniquement. Mise à jour automatique.
      </p>
    </div>
  );
}

function LeaderboardRow({ entry, rank, isCurrentUser }: { entry: LeaderboardEntry; rank: number; isCurrentUser: boolean }) {
  const medal = rank === 1 ? "🥇" : rank === 2 ? "🥈" : rank === 3 ? "🥉" : null;
  return (
    <article className={`leaderboard-row ${isCurrentUser ? "current-user" : ""}`}>
      <div className="flex items-center gap-3">
        <span className="rank-badge">
          {medal ?? `#${rank}`}
        </span>
        <span className="leaderboard-avatar">{entry.display_name.slice(0, 1).toUpperCase()}</span>
        <div className="min-w-0">
          <strong className="block truncate text-sm text-forest">
            {entry.display_name} {isCurrentUser && <span className="ml-2 text-[9px] font-bold uppercase tracking-wider text-orange-700">Vous</span>}
          </strong>
          <div className="mt-1 flex flex-wrap gap-4 text-[10px] text-stone-500">
            <span className="flex items-center gap-1"><Gamepad2 size={10} /> {entry.solo_games_played} solo</span>
            <span className="flex items-center gap-1"><Users size={10} /> {entry.multiplayer_games_played} multi</span>
          </div>
        </div>
      </div>
      <div className="hidden sm:flex items-center gap-6 text-sm text-stone-600">
        <span className="w-20 text-right font-semibold text-forest">{entry.wins}</span>
        <span className="w-24 text-right">{entry.losses}</span>
        <span className="w-24 text-right font-bold text-orange-700">{entry.win_rate}%</span>
        <span className="w-28 text-right font-medium text-forest">{formatKm(entry.total_kilometers)}</span>
        <span className="w-24 text-right">{formatKm(entry.best_kilometers)}</span>
      </div>
      <div className="sm:hidden mt-2 grid grid-cols-3 gap-2 text-xs text-stone-500">
        <div><span className="font-semibold text-forest">{entry.wins}</span> V</div>
        <div><span className="font-semibold text-stone-600">{entry.losses}</span> D</div>
        <div><span className="font-bold text-orange-700">{entry.win_rate}%</span> taux</div>
      </div>
    </article>
  );
}

function formatKm(value: number) {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M km`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k km`;
  return `${value} km`;
}