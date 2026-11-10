import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { useEffect, useRef, useState } from 'react';
import type { ReactElement } from 'react';
import type { ActivationView, Catalog, Command, GameView, MoveKind, MoveView, PlayerView } from '../api/types';
import { ActionBar, Button, GameLog, Hand, Market, PearlCard, PlayerArea } from '../design';
import type { ActionId, CharacterCardProps } from '../design';
import { characterName, characterProps } from '../game/characters';
import { indicesForValues, matchingPlans } from '../game/payment';
import { EndDialog } from './EndDialog';
import { DecisionPanel, PayPanel } from './panels';

const LOG_LINES = 80;

interface TableScreenProps {
  view: GameView;
  catalog: Catalog;
  send: (command: Command) => void;
  onLeave: () => void;
}

interface MenuState {
  anchor: HTMLElement;
  items: Array<{ key: number; text: string; run: () => void }>;
}

/** The game table: opponents on top, the market, the action bar, and the local player's portal and hand. */
export function TableScreen({ view, catalog, send, onLeave }: TableScreenProps): ReactElement | null {
  const table = view.table;
  const [payingAction, setPayingAction] = useState<number | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [planChoice, setPlanChoice] = useState<number | null>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [replaceOptions, setReplaceOptions] = useState<MoveView[] | null>(null);
  const [endOpen, setEndOpen] = useState(true);
  const chronicle = useRef<HTMLElement>(null);

  // Any change on the table invalidates a half-made selection.
  const signature = `${view.log.length}:${table?.current_player}:${table?.prompt?.kind}`;
  useEffect(() => {
    setPayingAction(null);
    setSelected([]);
    setPlanChoice(null);
    setReplaceOptions(null);
  }, [signature]);
  useEffect(() => {
    chronicle.current?.scrollTo({ top: chronicle.current.scrollHeight });
  }, [view.log.length]);

  if (!table) {
    return null;
  }
  const me = view.players[view.you];
  const names = view.players.map((player) => player.name);
  const prompt = table.prompt;
  const myTurn = table.current_player === view.you;
  const paying = table.activations.find((activation) => activation.action === payingAction) ?? null;
  const canAct = myTurn && prompt?.kind === 'turn' && !paying;
  const selecting = Boolean(paying) || prompt?.kind === 'discard';
  const movesOf = (kind: MoveKind): MoveView[] => table.moves.filter((move) => move.kind === kind);
  const play = (action: number): void => send({ type: 'play', action });
  const selectedValues = selected.map((index) => table.hand[index]);

  const startPaying = (activation: ActivationView): void => {
    setPayingAction(activation.action);
    setSelected([]);
    setPlanChoice(null);
  };
  const toggle = (index: number): void => {
    setPlanChoice(null);
    setSelected((current) => (current.includes(index) ? current.filter((item) => item !== index) : [...current, index]));
  };

  const activationText = (activation: ActivationView): string =>
    `Activate ${characterName(catalog, activation.character)}` +
    (activation.owner === view.you ? '' : ` on ${names[activation.owner]}'s portal`);

  const portalCards = (player: PlayerView): CharacterCardProps[] =>
    player.portal.map((id, slot) => {
      const activation = canAct
        ? table.activations.find((option) => option.owner === player.seat && option.slot === slot)
        : undefined;
      return {
        ...characterProps(catalog, id),
        activatable: Boolean(activation) || (paying?.owner === player.seat && paying.slot === slot),
        selected: paying?.owner === player.seat && paying.slot === slot,
        onClick: activation ? () => startPaying(activation) : undefined,
      };
    });

  const takeCharacter = (slot: number | 'deck'): void => {
    const options = movesOf('take_character').filter((move) => move.slot === (slot === 'deck' ? null : slot));
    if (options.length === 1) {
      play(options[0].action);
    } else if (options.length > 1) {
      setReplaceOptions(options);
    }
  };
  const takePearl = (slot: number | 'deck'): void => {
    const move = movesOf('take_pearl').find((option) => option.slot === (slot === 'deck' ? null : slot));
    if (move) {
      play(move.action);
    }
  };
  const openMenu = (anchor: HTMLElement, moves: MoveView[]): void =>
    setMenu({ anchor, items: moves.map((move) => ({ key: move.action, text: move.text, run: () => play(move.action) })) });
  const onAction = (id: ActionId, anchor: HTMLElement): void => {
    if (id === 'replace_display') {
      const refresh = movesOf('refresh_pearls')[0];
      if (refresh) {
        play(refresh.action);
      }
    } else if (id === 'take_pearl') {
      openMenu(anchor, movesOf('take_pearl'));
    } else if (id === 'take_character') {
      openMenu(anchor, movesOf('take_character'));
    } else if (table.activations.length === 1) {
      startPaying(table.activations[0]);
    } else {
      setMenu({
        anchor,
        items: table.activations.map((activation) => ({
          key: activation.action,
          text: activationText(activation),
          run: () => startPaying(activation),
        })),
      });
    }
  };

  const matches = paying ? matchingPlans(paying.plans, selectedValues) : [];
  const plan = matches.length === 1 ? matches[0] : (matches.find((option) => option.index === planChoice) ?? null);
  const turnPlayer = table.current_player === null ? null : view.players[table.current_player];
  const opponents = view.players
    .map((_, offset) => view.players[(view.you + 1 + offset) % view.players.length])
    .filter((player) => player.seat !== view.you);

  let controls: ReactElement;
  if (paying) {
    controls = (
      <PayPanel
        activation={paying}
        character={characterProps(catalog, paying.character)}
        owner={paying.owner === view.you ? null : names[paying.owner]}
        selected={selected}
        matches={matches}
        plan={plan}
        onChoosePlan={setPlanChoice}
        onSuggest={(cards) => {
          setPlanChoice(null);
          setSelected(indicesForValues(table.hand, cards));
        }}
        onConfirm={() => plan && send({ type: 'activate', action: paying.action, plan: plan.index })}
        onCancel={() => {
          setPayingAction(null);
          setSelected([]);
        }}
      />
    );
  } else if (myTurn && prompt && prompt.kind !== 'turn') {
    controls = (
      <DecisionPanel
        prompt={prompt}
        moves={table.moves}
        target={prompt.target === null ? '' : names[prompt.target]}
        selectedCount={selected.length}
        onPlay={play}
        onDiscard={() => send({ type: 'discard', values: selectedValues })}
      />
    );
  } else {
    const none = !canAct;
    controls = (
      <>
        <ActionBar
          player={turnPlayer?.name ?? ''}
          isYou={myTurn}
          remaining={table.actions_left}
          total={Math.max(table.actions_left + view.actions_taken, 1)}
          endgame={table.final_turns !== null}
          finalTurns={table.final_turns}
          primary={canAct && table.activations.length ? 'activate' : undefined}
          disabled={{
            take_pearl: none || !movesOf('take_pearl').length,
            replace_display: none || !movesOf('refresh_pearls').length,
            take_character: none || !movesOf('take_character').length,
            activate: none || !table.activations.length,
          }}
          onAction={onAction}
        />
        {canAct && movesOf('convert').length ? (
          <div className="app-row">
            {movesOf('convert').map((move) => (
              <Button key={move.action} icon="diamond" cost={0} onClick={() => play(move.action)}>
                {move.text}
              </Button>
            ))}
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="table-grid">
      <div className="table-main">
        <div className="table-opponents">
          {opponents.map((player) => (
            <PlayerArea
              key={player.seat}
              name={player.name}
              active={table.current_player === player.seat}
              away={!player.connected}
              points={player.points}
              diamonds={player.diamonds}
              handCount={player.hand.length}
              portal={portalCards(player)}
              activated={player.activated.map((id) => characterProps(catalog, id))}
            >
              <div className="table-hand-row" aria-label={`${player.name}'s hand`}>
                {player.hand.map((value, index) => (
                  <PearlCard key={index} value={value} size="sm" />
                ))}
              </div>
            </PlayerArea>
          ))}
        </div>
        <Market
          pearls={table.pearl_display.map((value) => ({ value }))}
          characters={table.character_display.map((id) => characterProps(catalog, id))}
          pearlDeck={table.pearl_deck}
          characterDeck={table.character_deck}
          onTakePearl={canAct && movesOf('take_pearl').length ? takePearl : undefined}
          onTakeCharacter={canAct && movesOf('take_character').length ? takeCharacter : undefined}
        >
          {table.peeked ? (
            <p className="mi-label table-peek">Top of the deck: {characterName(catalog, table.peeked)}</p>
          ) : null}
        </Market>
        {controls}
        <PlayerArea
          name={me.name}
          isYou
          active={myTurn}
          points={me.points}
          diamonds={me.diamonds}
          handCount={me.hand.length}
          portal={portalCards(me)}
          activated={me.activated.map((id) => characterProps(catalog, id))}
        >
          <Hand
            cards={table.hand.map((value, index) => ({ value, selected: selected.includes(index) }))}
            limit={me.hand_limit}
            onToggle={selecting ? toggle : undefined}
          />
        </PlayerArea>
      </div>
      <aside className="table-chronicle" ref={chronicle}>
        <GameLog entries={view.log.slice(-LOG_LINES)} round={view.round} />
      </aside>

      <Menu open={menu !== null} anchorEl={menu?.anchor} onClose={() => setMenu(null)}>
        {menu?.items.map((item) => (
          <MenuItem
            key={item.key}
            onClick={() => {
              setMenu(null);
              item.run();
            }}
          >
            {item.text}
          </MenuItem>
        ))}
      </Menu>
      <Dialog open={replaceOptions !== null} onClose={() => setReplaceOptions(null)}>
        <DialogTitle>Your portal is full</DialogTitle>
        <DialogContent>
          <p className="app-text">Choose the character to discard for the new one.</p>
        </DialogContent>
        <DialogActions>
          {replaceOptions?.map((move) => (
            <Button key={move.action} onClick={() => play(move.action)}>
              {move.text}
            </Button>
          ))}
          <Button onClick={() => setReplaceOptions(null)}>Cancel</Button>
        </DialogActions>
      </Dialog>
      {view.status === 'finished' ? (
        <EndDialog view={view} open={endOpen} onClose={() => setEndOpen(false)} onLeave={onLeave} />
      ) : null}
    </div>
  );
}
