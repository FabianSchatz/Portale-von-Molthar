import type { ButtonHTMLAttributes, ReactElement } from 'react';
import { Icon } from './Icon';
import type { IconName } from './Icon';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** `primary` at most once per view; `danger` only for discarding. */
  variant?: 'primary' | 'quiet' | 'danger';
  icon?: IconName;
  /** Action cost after the label in small capitals: 0 → "free", 1 → "1 action". */
  cost?: number;
}

/** A verb-first label in the book hand, an optional icon, and the action cost. */
export function Button({ variant = 'quiet', icon, cost, className, children, ...rest }: ButtonProps): ReactElement {
  return (
    <button type="button" {...rest} className={['mi-btn', `mi-btn-${variant}`, className].filter(Boolean).join(' ')}>
      {icon ? <Icon name={icon} size={16} /> : null}
      {children}
      {cost !== undefined ? (
        <span className="mi-cost">{cost === 0 ? 'free' : `${cost} action${cost === 1 ? '' : 's'}`}</span>
      ) : null}
    </button>
  );
}

export type StatKind = 'power' | 'diamond' | 'hand' | 'actions';
const STAT_ICON: Record<StatKind, IconName> = { power: 'power', diamond: 'diamond', hand: 'hand', actions: 'action' };
const STAT_WORD: Record<StatKind, string> = {
  power: 'power points',
  diamond: 'diamonds',
  hand: 'pearl cards in hand',
  actions: 'actions left',
};

export interface StatProps {
  kind?: StatKind;
  value: number;
  goal?: number;
  label?: string;
}

/** A near-square counter for one public number. */
export function Stat({ kind = 'power', value, goal, label }: StatProps): ReactElement {
  const reached = goal !== undefined && value >= goal;
  return (
    <span
      className={['mi-stat', `mi-stat-${kind}`, reached && 'mi-stat-goal'].filter(Boolean).join(' ')}
      title={`${value}${goal ? ` / ${goal}` : ''} ${STAT_WORD[kind]}`}
    >
      <Icon name={STAT_ICON[kind]} size={16} />
      <span>{value}</span>
      {goal ? <small>/{goal}</small> : null}
      {label ? <small>{label}</small> : null}
      <span className="mi-sr">{STAT_WORD[kind]}</span>
    </span>
  );
}

function Pips({ remaining, total }: { remaining: number; total: number }): ReactElement {
  return (
    <span className="mi-pips" role="img" aria-label={`${remaining} of ${total} actions left`}>
      {Array.from({ length: total }, (_, index) => (
        <span key={index} className={['mi-pip', index < remaining && 'is-on'].filter(Boolean).join(' ')} />
      ))}
      <span className="mi-pips-cap" aria-hidden>
        {remaining} of {total} actions left
      </span>
    </span>
  );
}

export interface TurnBannerProps {
  player?: string;
  isYou?: boolean;
  remaining?: number;
  total?: number;
  endgame?: boolean;
  finalTurns?: number | null;
}

/** Whose turn it is in the Gothic hand, with actions as vermilion roundels. */
export function TurnBanner({ player, isYou, remaining, total = 3, endgame, finalTurns }: TurnBannerProps): ReactElement {
  const left = remaining ?? total;
  return (
    <div className="mi-turn" role="status">
      <h2 className="mi-turn-title">{isYou ? 'Your turn' : `${player}'s turn`}</h2>
      <Pips remaining={left} total={total} />
      {endgame ? (
        <div className="mi-endgame">
          <Icon name="warning" size={16} />
          End of game triggered
          {finalTurns != null ? ` — ${finalTurns} final turn${finalTurns === 1 ? '' : 's'} left` : ''}
        </div>
      ) : null}
    </div>
  );
}

export type ActionId = 'take_pearl' | 'replace_display' | 'take_character' | 'activate';
const ACTIONS: Array<{ id: ActionId; label: string; icon: IconName }> = [
  { id: 'take_pearl', label: 'Take pearl', icon: 'pearl' },
  { id: 'replace_display', label: 'Replace display', icon: 'swap' },
  { id: 'take_character', label: 'Take character', icon: 'portal' },
  { id: 'activate', label: 'Activate', icon: 'power' },
];

export interface ActionBarProps extends TurnBannerProps {
  primary?: ActionId;
  disabled?: Partial<Record<ActionId, boolean>>;
  onAction?: (id: ActionId, anchor: HTMLElement) => void;
}

/** The turn banner plus the four turn actions, each costing one action. */
export function ActionBar({ primary, disabled = {}, onAction, ...banner }: ActionBarProps): ReactElement {
  const remaining = banner.remaining ?? 3;
  return (
    <div className="mi-panel mi-hud">
      <TurnBanner {...banner} remaining={remaining} />
      <div className="mi-actions" role="group" aria-label="Actions">
        {ACTIONS.map((action) => (
          <Button
            key={action.id}
            icon={action.icon}
            variant={primary === action.id ? 'primary' : 'quiet'}
            disabled={remaining === 0 || Boolean(disabled[action.id])}
            cost={1}
            onClick={onAction ? (event) => onAction(action.id, event.currentTarget) : undefined}
          >
            {action.label}
          </Button>
        ))}
      </div>
    </div>
  );
}

export interface LogEntryProps {
  player: string;
  text: string;
  highlight?: string | null;
  action?: number | string | null;
  tone?: 'power' | 'danger' | null;
}

export interface GameLogProps {
  entries: LogEntryProps[];
  round?: number;
}

/** The Chronicle: numbered moves with rubricated numbers, the player in bold. */
export function GameLog({ entries, round = 1 }: GameLogProps): ReactElement {
  return (
    <section className="mi-panel" aria-label="Game log">
      <h3 className="mi-panel-h">
        Chronicle <span className="mi-label">Round {round}</span>
      </h3>
      <ol className="mi-log">
        {entries.map((entry, index) => (
          <li key={index} className={entry.tone ? `t-${entry.tone}` : undefined}>
            <span className="mi-log-n">{entry.action != null && entry.action !== '' ? entry.action : '¶'}</span>
            <span className="mi-log-who">{entry.player}</span>
            <span className="mi-log-what">
              {entry.text}
              {entry.highlight ? <b> {entry.highlight}</b> : null}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
