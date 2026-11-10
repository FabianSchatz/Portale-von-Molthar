// The panels that replace the action bar while the local player pays or decides.
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import type { ReactElement } from 'react';
import type { ActivationView, MoveView, PlanView, PromptKind, PromptView } from '../api/types';
import { Button, CharacterCard } from '../design';
import type { CharacterCardProps } from '../design';
import { suggestedCardSets } from '../game/payment';

interface PayPanelProps {
  activation: ActivationView;
  character: CharacterCardProps;
  owner: string | null;
  selected: number[];
  matches: PlanView[];
  plan: PlanView | null;
  onChoosePlan: (index: number) => void;
  onSuggest: (cards: number[]) => void;
  onConfirm: () => void;
  onCancel: () => void;
}

function planSummary(plan: PlanView): string {
  const diamonds = plan.diamonds ? ` · ${plan.diamonds} diamond${plan.diamonds > 1 ? 's' : ''}` : '';
  return `${plan.labels.join(', ')}${diamonds}`;
}

/** Paying for an activation: select pearls in the hand, pick a variant if several fit, confirm. */
export function PayPanel(props: PayPanelProps): ReactElement {
  const { activation, character, selected, matches, plan } = props;
  let status: ReactElement;
  if (matches.length === 0) {
    status = (
      <p className="app-text">
        {selected.length
          ? 'These pearls do not meet the requirement.'
          : 'Select pearls in your hand, or pick one of the payments below.'}
      </p>
    );
  } else if (matches.length === 1) {
    status = <p className="app-text">Pay with {planSummary(matches[0])}.</p>;
  } else {
    status = (
      <RadioGroup
        value={plan?.index ?? ''}
        onChange={(event) => props.onChoosePlan(Number(event.target.value))}
        aria-label="How to pay"
      >
        {matches.map((option) => (
          <FormControlLabel key={option.index} value={option.index} control={<Radio size="small" />} label={planSummary(option)} />
        ))}
      </RadioGroup>
    );
  }
  return (
    <section className="mi-panel" aria-label="Activate a character">
      <h2 className="mi-panel-h">
        Activate {character.name}
        <span className="mi-label">{props.owner ? `on ${props.owner}'s portal` : '1 action'}</span>
      </h2>
      <div className="table-panel-body">
        <CharacterCard {...character} />
        <div className="table-panel-text">
          {status}
          <div className="app-row">
            <span className="mi-label">Payments</span>
            {suggestedCardSets(activation.plans).map((cards) => (
              <button key={cards.join(',')} type="button" className="table-chip" onClick={() => props.onSuggest(cards)}>
                {cards.length ? cards.join(', ') : 'no pearls'}
              </button>
            ))}
          </div>
          <div className="app-row">
            <Button variant="primary" icon="power" cost={1} disabled={!plan} onClick={props.onConfirm}>
              Activate
            </Button>
            <Button onClick={props.onCancel}>Cancel</Button>
          </div>
        </div>
      </div>
    </section>
  );
}

const PROMPT_TITLES: Record<Exclude<PromptKind, 'turn'>, string> = {
  discard: 'Hand limit',
  keep_pearl: 'Puss in Boots',
  steal_target: 'Tinkerbell',
  steal_pearl: 'Tinkerbell',
  discard_target: 'Medusa',
  discard_portal: 'Medusa',
  redraw_hand: 'Reaper',
  swap_portal: 'Mad Hatter',
};

function promptText(prompt: PromptView, target: string): string {
  const plural = prompt.count === 1 ? '' : 's';
  switch (prompt.kind) {
    case 'discard':
      return `Your hand is over the limit. Select ${prompt.count} pearl${plural} to discard.`;
    case 'keep_pearl':
      return 'You may keep one of the pearls you just paid.';
    case 'steal_target':
      return 'Choose whose hand to take a pearl from.';
    case 'steal_pearl':
      return `Take one pearl from ${target}'s hand.`;
    case 'discard_target':
      return 'Choose whose portal loses a character.';
    case 'discard_portal':
      return `Discard one character from ${target}'s portal.`;
    case 'redraw_hand':
      return 'Discard your whole hand and draw as many new pearls?';
    case 'swap_portal':
      return 'Before your turn, you may swap a character on your portal with a face-up one.';
    default:
      return '';
  }
}

interface DecisionPanelProps {
  prompt: PromptView;
  moves: MoveView[];
  target: string;
  selectedCount: number;
  onPlay: (action: number) => void;
  onDiscard: () => void;
}

/** A decision outside the four turn actions: hand-limit discards and red or blue ability choices. */
export function DecisionPanel({ prompt, moves, target, selectedCount, onPlay, onDiscard }: DecisionPanelProps): ReactElement {
  const kind = prompt.kind === 'turn' ? 'discard' : prompt.kind;
  return (
    <section className="mi-panel" aria-label="Decision">
      <h2 className="mi-panel-h">
        {PROMPT_TITLES[kind]}
        <span className="mi-label">free</span>
      </h2>
      <div className="table-panel-text">
        <p className="app-text">{promptText(prompt, target)}</p>
        <div className="app-row">
          {kind === 'discard' ? (
            <Button variant="danger" disabled={selectedCount !== prompt.count} onClick={onDiscard}>
              Discard {selectedCount} of {prompt.count}
            </Button>
          ) : (
            moves.map((move) => (
              <Button key={move.action} onClick={() => onPlay(move.action)}>
                {move.text}
              </Button>
            ))
          )}
        </div>
      </div>
    </section>
  );
}
