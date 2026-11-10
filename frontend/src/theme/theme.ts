import { createTheme } from '@mui/material/styles';
import type { Theme } from '@mui/material/styles';
import { useEffect, useState } from 'react';
import { TOKENS } from './tokens';
import type { ThemeId } from './tokens';

/** Card pigments: identical in both themes because the cards are physical objects on the table. */
interface CardPalette {
  face: string;
  shade: string;
  ink: string;
  rubric: string;
  vine: string;
  lapis: string;
  gold: string;
  goldLight: string;
}

declare module '@mui/material/styles' {
  interface Palette {
    portal: Palette['primary'];
    power: Palette['primary'];
    diamond: Palette['primary'];
    card: CardPalette;
  }
  interface PaletteOptions {
    portal?: PaletteOptions['primary'];
    power?: PaletteOptions['primary'];
    diamond?: PaletteOptions['primary'];
    card?: CardPalette;
  }
}

const SERIF = '"Alegreya", "Palatino Linotype", Palatino, Georgia, serif';
const DISPLAY = '"Grenze Gotisch", "Old English Text MT", Georgia, serif';
const THEME_KEY = 'molthar.theme';

/** The MUI theme of one Molthar Illuminated theme (Parchment is light, Leather is dark). */
export function moltharTheme(id: ThemeId): Theme {
  const token = TOKENS[id];
  const gothic = { fontFamily: DISPLAY, fontWeight: 600 };
  return createTheme({
    palette: {
      mode: id === 'parchment' ? 'light' : 'dark',
      background: { default: token.surface, paper: token['surface-raised'] },
      text: { primary: token.ink, secondary: token['ink-muted'] },
      primary: { main: token.accent, contrastText: token['on-accent'] },
      error: { main: token.danger },
      divider: token.line,
      portal: { main: token.portal },
      power: { main: token.power },
      diamond: { main: token.diamond },
      card: {
        face: token['card-face'],
        shade: token['card-shade'],
        ink: token['card-ink'],
        rubric: token['card-rubric'],
        vine: token['card-vine'],
        lapis: token['card-lapis'],
        gold: token['card-gold'],
        goldLight: token['card-gold-light'],
      },
    },
    shape: { borderRadius: 4 },
    typography: {
      fontFamily: SERIF,
      h1: { ...gothic, fontSize: 44, lineHeight: '46px' },
      h2: { ...gothic, fontSize: 26, lineHeight: '30px' },
      h3: { ...gothic, fontSize: 22, lineHeight: '26px' },
      h4: { ...gothic, fontSize: 17, lineHeight: '20px' },
      button: { textTransform: 'none', fontWeight: 700 },
    },
    components: {
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiOutlinedInput: { styleOverrides: { notchedOutline: { borderColor: token['line-strong'] } } },
      MuiTooltip: { styleOverrides: { tooltip: { backgroundColor: token.ink, color: token.surface, fontSize: 13 } } },
    },
  });
}

function initialTheme(): ThemeId {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'parchment' || saved === 'leather') {
      return saved;
    }
  } catch {
    // Storage may be blocked; fall back to the system preference.
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'leather' : 'parchment';
}

/** The chosen theme, defaulting to the system setting, applied as `data-theme` on <html>. */
export function useThemeChoice(): [ThemeId, (id: ThemeId) => void] {
  const [id, setId] = useState<ThemeId>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = id;
  }, [id]);
  const choose = (next: ThemeId): void => {
    setId(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Remembering the choice is a convenience only.
    }
  };
  return [id, choose];
}
