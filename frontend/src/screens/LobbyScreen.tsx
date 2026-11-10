import { useState } from 'react';
import type { ReactElement } from 'react';
import type { Command, Difficulty, GameView } from '../api/types';
import { Button } from '../design';

const MIN_PLAYERS = 2;
const MAX_PLAYERS = 5;
const DIFFICULTIES: Difficulty[] = ['easy', 'medium', 'hard'];

interface LobbyProps {
  view: GameView;
  send: (command: Command) => void;
  onLeave: () => void;
}

/** The waiting room: the game code to share, who has joined, and the host's start button. */
export function LobbyScreen({ view, send, onLeave }: LobbyProps): ReactElement {
  const [copied, setCopied] = useState(false);
  const isHost = view.you === 0;
  const enough = view.players.length >= MIN_PLAYERS;
  const full = view.players.length >= MAX_PLAYERS;
  const link = `${window.location.origin}/?game=${view.game_id}`;

  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  return (
    <main className="app-page">
      <section className="mi-panel app-form">
        <h2 className="mi-panel-h">
          Waiting for players
          <span className="mi-label">
            {view.players.length} of {MAX_PLAYERS} seats
          </span>
        </h2>
        <div className="app-row">
          <span className="mi-label">Game code</span>
          <span className="app-code">{view.game_id}</span>
          <Button icon="swap" onClick={() => void copy()}>
            {copied ? 'Link copied' : 'Copy invite link'}
          </Button>
        </div>
        <ol className="app-seats">
          {view.players.map((player) => (
            <li key={player.seat}>
              <span
                className={['app-presence', player.connected && 'is-on'].filter(Boolean).join(' ')}
                title={player.connected ? 'Connected' : 'Not connected'}
              />
              {player.name}
              {player.seat === view.you ? <span className="mi-you">(you)</span> : null}
              {player.seat === 0 ? <span className="mi-label">host</span> : null}
              {player.bot ? <span className="mi-label">bot</span> : null}
            </li>
          ))}
        </ol>
        {isHost ? (
          <div className="app-row">
            <span className="mi-label">Add a bot</span>
            {DIFFICULTIES.map((difficulty) => (
              <Button key={difficulty} disabled={full} onClick={() => send({ type: 'add_bot', difficulty })}>
                {difficulty[0].toUpperCase() + difficulty.slice(1)}
              </Button>
            ))}
          </div>
        ) : null}
        <p className="app-text">
          {isHost
            ? enough
              ? 'Everyone in? Start when the table is complete.'
              : 'Share the code or add a bot; at least one more player is needed.'
            : `Waiting for ${view.players[0]?.name ?? 'the host'} to start the game.`}
        </p>
        <div className="app-row">
          {isHost ? (
            <Button variant="primary" icon="portal" disabled={!enough} onClick={() => send({ type: 'start' })}>
              Start game
            </Button>
          ) : null}
          <Button onClick={onLeave}>Leave</Button>
        </div>
      </section>
    </main>
  );
}
