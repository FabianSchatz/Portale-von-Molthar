import Alert from '@mui/material/Alert';
import TextField from '@mui/material/TextField';
import { useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { createGame, joinGame } from '../api/client';
import type { JoinResult } from '../api/types';
import { Button } from '../design';

const NAME_KEY = 'molthar.name';
const MAX_NAME = 20;

function rememberedName(): string {
  try {
    return localStorage.getItem(NAME_KEY) ?? '';
  } catch {
    return '';
  }
}

function rememberName(name: string): void {
  try {
    localStorage.setItem(NAME_KEY, name);
  } catch {
    // Only a convenience for the next visit.
  }
}

/** Create a new game or join one with its code; `?game=CODE` in the URL fills in the code. */
export function HomeScreen({ onEnter }: { onEnter: (session: JoinResult) => void }): ReactElement {
  const invited = new URLSearchParams(window.location.search).get('game') ?? '';
  const [name, setName] = useState(rememberedName);
  const [code, setCode] = useState(invited.toUpperCase());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = (action: () => Promise<JoinResult>) => async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      rememberName(name.trim());
      onEnter(await action());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'the server could not be reached');
    } finally {
      setBusy(false);
    }
  };
  const nameField = (
    <TextField
      label="Your name"
      value={name}
      onChange={(event) => setName(event.target.value)}
      slotProps={{ htmlInput: { maxLength: MAX_NAME } }}
      required
      size="small"
    />
  );
  const named = name.trim().length > 0;

  return (
    <main className="app-page">
      <div>
        <p className="app-display">Die Portale von Molthar</p>
        <p className="app-lede">Collect pearls, open portals and activate characters. The first to 12 power points ends the game.</p>
      </div>
      {error ? <Alert severity="error">{error}</Alert> : null}
      <div className="app-columns">
        <form className="mi-panel app-form" onSubmit={submit(() => createGame(name.trim()))}>
          <h2 className="mi-panel-h">New game</h2>
          <p className="app-text">Open a table and share its code with 1 to 4 friends.</p>
          {invited ? null : nameField}
          <Button type="submit" variant={invited ? 'quiet' : 'primary'} disabled={busy || !named}>
            Create game
          </Button>
        </form>
        <form className="mi-panel app-form" onSubmit={submit(() => joinGame(code, name.trim()))}>
          <h2 className="mi-panel-h">Join a game</h2>
          <TextField
            label="Game code"
            value={code}
            onChange={(event) => setCode(event.target.value.toUpperCase())}
            slotProps={{ htmlInput: { maxLength: 5, autoCapitalize: 'characters' } }}
            required
            size="small"
          />
          {invited ? nameField : null}
          <Button type="submit" variant={invited ? 'primary' : 'quiet'} disabled={busy || !named || code.trim().length < 5}>
            Join game
          </Button>
        </form>
      </div>
    </main>
  );
}
