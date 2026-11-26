export interface User {
  id: number | string;
  email: string;
  display_name: string;
  date_joined: string;
}

export type GameMode = "solo" | "multiplayer";
export type GameVisibility = "public" | "private";
export type GameStatus = "waiting" | "active" | "finished" | "cancelled";
export type BotDifficulty = "easy" | "normal" | "hard";

export interface GameParticipant {
  id: string;
  seat_number: number;
  kind: "human" | "bot";
  display_name: string;
  bot_difficulty: BotDifficulty | "";
  is_ready: boolean;
  kilometers: number;
  placement: number | null;
  abandoned_at?: string | null;
  joined_at: string;
}

export interface Game {
  id: string;
  mode: GameMode;
  visibility: GameVisibility;
  status: GameStatus;
  host_display_name: string;
  max_players: number;
  seats_taken: number;
  available_seats: number;
  participants: GameParticipant[];
  winner_display_name: string | null;
  ruleset_version: string;
  state_version: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface CreatedGame extends Game {
  invite_code?: string;
}

export interface ApiPage<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface GameHistory {
  id: string;
  mode: GameMode;
  ruleset_version: string;
  participants: Array<{
    display_name: string;
    kind: "human" | "bot";
    seat_number: number;
    kilometers: number;
    placement: number | null;
  }>;
  winner_display_name: string;
  completed_at: string;
}

export interface PlayerStats {
  games_played: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_kilometers: number;
  best_kilometers: number;
  solo_games_played: number;
  multiplayer_games_played: number;
  average_kilometers: number;
  updated_at: string;
}

export interface LeaderboardEntry {
  rank: number;
  user_id: number;
  display_name: string;
  games_played: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_kilometers: number;
  best_kilometers: number;
  solo_games_played: number;
  multiplayer_games_played: number;
}
