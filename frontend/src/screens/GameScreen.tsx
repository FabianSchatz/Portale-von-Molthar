import Alert from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';
import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { fetchCatalog, useGameConnection } from '../api/client';
import type { Catalog, JoinResult } from '../api/types';
import { Button } from '../design';
import { LobbyScreen } from './LobbyScreen';
import { TableScreen } from './TableScreen';

interface GameScreenProps {
  session: JoinResult;
  onLeave: () => void;
}

/** One seat's connection to a game: the lobby until the host starts, then the table. */
export function GameScreen({ session, onLeave }: GameScreenProps): ReactElement {
  const { view, connected, rejected, error, clearError, send } = useGameConnection(session);
  const [catalog, setCatalog] = useState<Catalog>({});

  useEffect(() => {
    fetchCatalog()
      .then(setCatalog)
      .catch(() => setCatalog({}));
  }, []);

  if (rejected) {
    return (
      <main className="app-page">
        <section className="mi-panel app-form">
          <h2 className="mi-panel-h">This game is gone</h2>
          <p className="app-text">The server no longer knows game {session.game_id}. It may have restarted.</p>
          <Button variant="primary" onClick={onLeave}>
            Back to the start
          </Button>
        </section>
      </main>
    );
  }

  let screen: ReactElement;
  if (!view) {
    screen = (
      <main className="app-page">
        <p className="app-lede">Opening game {session.game_id}…</p>
      </main>
    );
  } else if (view.status === 'lobby') {
    screen = <LobbyScreen view={view} send={send} onLeave={onLeave} />;
  } else {
    screen = <TableScreen view={view} catalog={catalog} send={send} onLeave={onLeave} />;
  }

  return (
    <>
      {view && !connected ? (
        <Alert severity="warning" sx={{ mx: 4, mb: 3 }}>
          Connection lost, reconnecting…
        </Alert>
      ) : null}
      {screen}
      <Snackbar open={error !== null} autoHideDuration={5000} onClose={clearError}>
        <Alert severity="error" onClose={clearError} variant="filled">
          {error}
        </Alert>
      </Snackbar>
    </>
  );
}
