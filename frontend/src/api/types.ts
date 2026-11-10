// The server's JSON contract. Mirrors the TypedDicts in
// src/portale_von_molthar/services/{catalog,views,game_service}.py — keep them in sync.
import type { Requirement } from '../design';

export interface CharacterInfo {
  id: string;
  name: string;
  kind: 'green' | 'red' | 'blue';
  requirement: Requirement;
  points: number;
  diamonds: number;
  ability: string | null;
  timing: string | null;
}

export type Catalog = Record<string, CharacterInfo>;

export interface JoinResult {
  game_id: string;
  seat: number;
  token: string;
}

export interface PlayerView {
  seat: number;
  name: string;
  connected: boolean;
  points: number;
  diamonds: number;
  /** Sorted pearl values: every hand is public. */
  hand: number[];
  hand_limit: number;
  portal: string[];
  activated: string[];
}

export type MoveKind = 'take_pearl' | 'refresh_pearls' | 'take_character' | 'discard' | 'convert' | 'choice';

export interface MoveView {
  action: number;
  kind: MoveKind;
  text: string;
  /** Display slot of a take; `null` is the hidden deck card. */
  slot: number | null;
  /** Portal slot discarded to make room for a new character. */
  replace: number | null;
}

export interface PlanView {
  index: number;
  /** Printed values of the hand pearls this plan discards, sorted. */
  cards: number[];
  labels: string[];
  diamonds: number;
}

export interface ActivationView {
  action: number;
  owner: number;
  slot: number;
  character: string;
  plans: PlanView[];
}

export type PromptKind =
  | 'turn'
  | 'discard'
  | 'keep_pearl'
  | 'steal_target'
  | 'steal_pearl'
  | 'discard_target'
  | 'discard_portal'
  | 'redraw_hand'
  | 'swap_portal';

export interface PromptView {
  kind: PromptKind;
  count: number;
  target: number | null;
}

export interface TableView {
  hand: number[];
  pearl_display: number[];
  pearl_deck: number;
  pearl_discard: number;
  character_display: string[];
  character_deck: number;
  character_discard: number;
  current_player: number | null;
  actions_left: number;
  final_turns: number | null;
  peeked: string | null;
  prompt: PromptView | null;
  moves: MoveView[];
  activations: ActivationView[];
}

export interface LogEntry {
  player: string;
  text: string;
  highlight: string | null;
  tone: 'power' | 'danger' | null;
  action: number | null;
}

export interface GameView {
  game_id: string;
  status: 'lobby' | 'playing' | 'finished';
  you: number;
  players: PlayerView[];
  table: TableView | null;
  log: LogEntry[];
  round: number;
  actions_taken: number;
  result: { winners: number[] } | null;
}

export type Command =
  | { type: 'start' }
  | { type: 'play'; action: number }
  | { type: 'activate'; action: number; plan: number }
  | { type: 'discard'; values: number[] };

export type ServerMessage = { type: 'view'; view: GameView } | { type: 'error'; message: string };
