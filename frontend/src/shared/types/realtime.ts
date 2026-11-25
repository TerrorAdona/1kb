import type { Game } from "./api";
import type { CardType } from "./game";

export interface EngineCard {
  id: string;
  card_type: CardType;
}

export interface VisiblePlayerState {
  player_id: string;
  display_name: string;
  seat_number: number | null;
  distance: number;
  distance_cards: EngineCard[];
  hand_count: number;
  battle_attack: EngineCard | null;
  speed_attack: EngineCard | null;
  green_light_card: EngineCard | null;
  safeties: CardType[];
}

export interface LegalPlay {
  card_id: string;
  target_player_id: string | null;
  is_coup_fourre: boolean;
}

export interface LiveGameState {
  viewer_player_id: string;
  active_player_id: string;
  pending_response_player_id: string | null;
  phase: "draw" | "action" | "response" | "finished";
  turn_number: number;
  target_distance: number;
  draw_pile_count: number;
  discard_top: EngineCard | null;
  players: VisiblePlayerState[];
  hand: EngineCard[];
  legal_actions: LegalPlay[];
  can_draw: boolean;
  can_discard: boolean;
  can_pass: boolean;
  winner_ids: string[];
  finish_reason: string | null;
}

export interface LiveGameEvent {
  id: string;
  sequence: number;
  event_type: string;
  actor_display_name: string;
  data: Record<string, unknown>;
  private: Record<string, unknown>;
  created_at: string;
}

export interface GameSnapshot {
  game: Game;
  state: LiveGameState | null;
  events: LiveGameEvent[];
  presence: Record<string, boolean>;
}

export interface GameSocketAck {
  request_id: string;
  state_version: number;
  status: Game["status"];
  duplicate: boolean;
}
