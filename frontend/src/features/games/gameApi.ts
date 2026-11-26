import { api } from "../../shared/api/client";
import type {
  ApiPage,
  BotDifficulty,
  CreatedGame,
  Game,
  GameHistory,
  LeaderboardEntry,
  PlayerStats,
} from "../../shared/types/api";

export interface CreateGamePayload {
  mode: "solo" | "multiplayer";
  visibility: "public" | "private";
  max_players: number;
  bot_difficulty?: BotDifficulty;
  invite_expires_in_hours?: number;
}

export interface WebSocketTicket {
  ticket: string;
  expires_in: number;
  websocket_path: string;
}

export interface SoloActionPayload {
  action: string;
  card_id?: string;
  target_player_id?: string;
  state_version: number;
  request_id: string;
}

export interface SoloActionResponse {
  game: Game;
  state_version: number;
  duplicate: boolean;
}

function unwrapPage<T>(data: T[] | ApiPage<T>) {
  return Array.isArray(data) ? data : data.results;
}

export async function listAvailableGames() {
  const { data } = await api.get<Game[] | ApiPage<Game>>("/games/");
  return unwrapPage(data);
}

export async function listMyGames() {
  const { data } = await api.get<Game[] | ApiPage<Game>>("/games/mine/");
  return unwrapPage(data);
}

export async function getGame(gameId: string) {
  const { data } = await api.get<Game>(`/games/${gameId}/`);
  return data;
}

export async function createGame(payload: CreateGamePayload) {
  const { data } = await api.post<CreatedGame>("/games/", payload);
  return data;
}

export async function joinGame(gameId: string, inviteCode?: string) {
  const { data } = await api.post<Game>(`/games/${gameId}/join/`, inviteCode
    ? { invite_code: inviteCode }
    : {});
  return data;
}

export async function leaveGame(gameId: string) {
  const { data } = await api.post<Game>(`/games/${gameId}/leave/`, {});
  return data;
}

export async function setReady(gameId: string, isReady: boolean) {
  const { data } = await api.patch<Game>(`/games/${gameId}/ready/`, {
    is_ready: isReady,
  });
  return data;
}

export async function startGame(gameId: string) {
  const { data } = await api.post<Game>(`/games/${gameId}/start/`, {});
  return data;
}

export async function getWebSocketTicket(gameId: string) {
  const { data } = await api.post<WebSocketTicket>(
    `/games/${gameId}/ws-ticket/`,
    {},
  );
  return data;
}

export async function getPlayerStats() {
  const { data } = await api.get<PlayerStats>("/stats/me/");
  return data;
}

export async function getGameHistory() {
  const { data } = await api.get<GameHistory[] | ApiPage<GameHistory>>("/history/");
  return unwrapPage(data);
}

export async function playSoloAction(gameId: string, payload: SoloActionPayload) {
  const { data } = await api.post<SoloActionResponse>(`/games/${gameId}/action/`, payload);
  return data;
}

export async function getLeaderboard(limit = 50) {
  const { data } = await api.get<LeaderboardEntry[]>(`/stats/leaderboard/`, {
    params: { limit },
  });
  return data;
}
