import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import { useMemo, useState } from 'react';
import type { ReactElement } from 'react';
import { loadSession, saveSession } from './api/client';
import type { JoinResult } from './api/types';
import { GameScreen } from './screens/GameScreen';
import { HomeScreen } from './screens/HomeScreen';
import { moltharTheme, useThemeChoice } from './theme/theme';
import type { ThemeId } from './theme/tokens';

export function App(): ReactElement {
  const [themeId, setThemeId] = useThemeChoice();
  const theme = useMemo(() => moltharTheme(themeId), [themeId]);
  const [session, setSession] = useState<JoinResult | null>(loadSession);

  const enter = (next: JoinResult | null): void => {
    saveSession(next);
    setSession(next);
    const url = new URL(window.location.href);
    if (next) {
      url.searchParams.set('game', next.game_id);
    } else {
      url.searchParams.delete('game');
    }
    window.history.replaceState(null, '', url);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <header className="app-bar">
        <h1 className="app-title">Die Portale von Molthar</h1>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={themeId}
          onChange={(_, value: ThemeId | null) => value && setThemeId(value)}
          aria-label="Theme"
        >
          <ToggleButton value="parchment">Parchment</ToggleButton>
          <ToggleButton value="leather">Leather</ToggleButton>
        </ToggleButtonGroup>
      </header>
      {session ? (
        <GameScreen key={session.token} session={session} onLeave={() => enter(null)} />
      ) : (
        <HomeScreen onEnter={enter} />
      )}
    </ThemeProvider>
  );
}
