import { useCallback, useEffect, useRef, useState } from 'react';
import type { Catalog, Command, GameView, JoinResult, ServerMessage } from './types';

const SESSION_KEY = 'molthar.session';
const RECONNECT_MS = 1000;
const POLICY_VIOLATION = 1008;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === 'string' ? body.detail : 'the server could not do that';
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function createGame(name: string): Promise<JoinResult> {
  return request('/api/games', { method: 'POST', body: JSON.stringify({ name }) });
}

export function joinGame(gameId: string, name: string): Promise<JoinResult> {
  return request(`/api/games/${encodeURIComponent(gameId.trim().toUpperCase())}/players`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export function fetchCatalog(): Promise<Catalog> {
  return request('/api/catalog');
}

/** The seat this browser plays, remembered so a reload rejoins the game. */
export function loadSession(): JoinResult | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? (JSON.parse(raw) as JoinResult) : null;
  } catch {
    return null;
  }
}

export function saveSession(session: JoinResult | null): void {
  try {
    if (session) {
      localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    // Storage may be blocked; the session then lasts until the tab closes.
  }
}

export interface GameConnection {
  view: GameView | null;
  connected: boolean;
  /** The server refused the token: the game is gone (server restart) or the seat is unknown. */
  rejected: boolean;
  error: string | null;
  clearError: () => void;
  send: (command: Command) => void;
}

/** Keep a WebSocket to the game open, reconnecting after drops, and expose the latest view. */
export function useGameConnection(session: JoinResult): GameConnection {
  const [view, setView] = useState<GameView | null>(null);
  const [connected, setConnected] = useState(false);
  const [rejected, setRejected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let closed = false;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${protocol}://${window.location.host}/ws/${session.game_id}?token=${encodeURIComponent(session.token)}`;

    const open = (): void => {
      const socket = new WebSocket(url);
      socketRef.current = socket;
      socket.onopen = () => setConnected(true);
      socket.onmessage = (event: MessageEvent<string>) => {
        const message = JSON.parse(event.data) as ServerMessage;
        if (message.type === 'view') {
          setView(message.view);
        } else {
          setError(message.message);
        }
      };
      socket.onclose = (event) => {
        setConnected(false);
        if (event.code === POLICY_VIOLATION) {
          setRejected(true);
        } else if (!closed) {
          retry = setTimeout(open, RECONNECT_MS);
        }
      };
    };
    open();
    return () => {
      closed = true;
      clearTimeout(retry);
      socketRef.current?.close();
    };
  }, [session.game_id, session.token]);

  const send = useCallback((command: Command) => {
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(command));
    } else {
      setError('not connected to the game, reconnecting');
    }
  }, []);
  const clearError = useCallback(() => setError(null), []);

  return { view, connected, rejected, error, clearError, send };
}
