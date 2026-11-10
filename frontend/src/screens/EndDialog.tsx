import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import type { ReactElement } from 'react';
import type { GameView } from '../api/types';
import { Button, Stat } from '../design';

interface EndDialogProps {
  view: GameView;
  open: boolean;
  onClose: () => void;
  onLeave: () => void;
}

/** Final standings: most power points wins, diamonds break ties. */
export function EndDialog({ view, open, onClose, onLeave }: EndDialogProps): ReactElement {
  const winners = view.result?.winners ?? [];
  const names = winners.map((seat) => (seat === view.you ? 'You' : view.players[seat].name));
  const headline =
    winners.length === view.players.length
      ? 'Nobody wins'
      : names.length === 1
        ? `${names[0]} ${winners[0] === view.you ? 'win' : 'wins'}`
        : `${names.join(' and ')} share the win`;
  const standings = [...view.players].sort(
    (left, right) => right.points - left.points || right.diamonds - left.diamonds,
  );
  return (
    <Dialog open={open} onClose={onClose} aria-labelledby="end-title">
      <DialogContent className="app-form">
        <p className="app-display" id="end-title">
          {headline}
        </p>
        <ol className="app-seats">
          {standings.map((player) => (
            <li key={player.seat}>
              {player.name}
              {player.seat === view.you ? <span className="mi-you">(you)</span> : null}
              <span style={{ marginLeft: 'auto' }} />
              <Stat kind="power" value={player.points} goal={12} />
              <Stat kind="diamond" value={player.diamonds} />
            </li>
          ))}
        </ol>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Look at the table</Button>
        <Button variant="primary" onClick={onLeave}>
          New game
        </Button>
      </DialogActions>
    </Dialog>
  );
}
