import type { ReactElement, ReactNode } from 'react';
import { CharacterCard, PearlCard, Pile, Slot } from './cards';
import type { CharacterCardProps, PearlCardProps } from './cards';
import { Stat } from './hud';
import { Icon } from './Icon';

const ARCH = {
  width: 272,
  height: 72,
  outer: 'M1 72 L1 58 Q1 22 136 1 Q271 22 271 58 L271 72',
  inner: 'M6 72 L6 59 Q6 27 136 8 Q266 27 266 59 L266 72',
};

export interface PortalProps {
  slots: Array<CharacterCardProps | null>;
  owner?: string;
  active?: boolean;
}

/** A player's portal: a pointed Gothic arch with two full-size places, readable by everyone. */
export function Portal({ slots, owner, active }: PortalProps): ReactElement {
  const places = [...slots.slice(0, 2)];
  while (places.length < 2) {
    places.push(null);
  }
  const filled = places.filter(Boolean).length;
  const classes = ['mi-portal', active && 'is-active'].filter(Boolean).join(' ');
  return (
    <section className={classes} aria-label={`${owner ? `${owner}'s portal` : 'Portal'}, ${filled} of 2 places used`}>
      <svg className="mi-portal-arch" viewBox={`0 0 ${ARCH.width} ${ARCH.height}`} aria-hidden>
        <path className="a-fill" d={ARCH.outer} />
        <path className="a-in" d={ARCH.inner} />
      </svg>
      <div className="mi-portal-cap">
        <Icon name="portal" size={14} />
        <span className="mi-label">Portal</span>
        <span className="mi-label">{filled}/2</span>
      </div>
      <div className="mi-portal-body">
        {places.map((card, index) =>
          card ? <CharacterCard key={index} {...card} /> : <Slot key={index} />,
        )}
      </div>
    </section>
  );
}

export interface PlayerAreaProps {
  name: string;
  isYou?: boolean;
  active?: boolean;
  /** No open connection: the name gets "(away)". */
  away?: boolean;
  points?: number;
  diamonds?: number;
  handCount?: number;
  portal?: Array<CharacterCardProps | null>;
  activated?: CharacterCardProps[];
  children?: ReactNode;
}

/** One player's public zone: name, power points out of 12, diamonds, hand count, portal and activated
 * characters as readable rows. */
export function PlayerArea(props: PlayerAreaProps): ReactElement {
  const activated = props.activated ?? [];
  return (
    <section
      className={['mi-panel', 'mi-player', props.active && 'is-active'].filter(Boolean).join(' ')}
      aria-label={props.name + (props.active ? ', active player' : '')}
    >
      <div className="mi-player-h">
        <div className="mi-player-name">
          {props.active ? <span className="mi-turn-dot" title="Active player" /> : null}
          {props.name}
          {props.isYou ? <span className="mi-you">(you)</span> : null}
          {props.away ? <span className="mi-you">(away)</span> : null}
        </div>
        <Stat kind="power" value={props.points ?? 0} goal={12} />
        <Stat kind="diamond" value={props.diamonds ?? 0} />
        <Stat kind="hand" value={props.handCount ?? 0} />
      </div>
      <div className="mi-player-body">
        <Portal slots={props.portal ?? []} owner={props.name} active={props.active} />
        <div className="mi-activated">
          <span className="mi-label">Activated · {activated.length}</span>
          <div className="mi-activated-rows">
            {activated.length ? (
              activated.map((card, index) => <CharacterCard key={index} {...card} size="row" />)
            ) : (
              <div className="mi-activated-none">None yet</div>
            )}
          </div>
        </div>
      </div>
      {props.children}
    </section>
  );
}

export interface MarketProps {
  pearls: Array<PearlCardProps | null>;
  characters: Array<CharacterCardProps | null>;
  pearlDeck: number;
  characterDeck: number;
  onTakePearl?: (slot: number | 'deck') => void;
  onTakeCharacter?: (slot: number | 'deck') => void;
  /** Extra content below the character display, such as a peeked top card. */
  children?: ReactNode;
}

/** The two displays on one ruled panel: four pearls plus the pearl deck, two characters plus the character deck. */
export function Market({
  pearls,
  characters,
  pearlDeck,
  characterDeck,
  onTakePearl,
  onTakeCharacter,
  children,
}: MarketProps): ReactElement {
  return (
    <section className="mi-panel" aria-label="Displays">
      <div className="mi-market">
        <div>
          <h3 className="mi-panel-h">
            Pearl display <span className="mi-label">4 face up</span>
          </h3>
          <div className="mi-market-zone">
            {pearls.slice(0, 4).map((card, index) =>
              card ? (
                <PearlCard key={index} {...card} onClick={onTakePearl ? () => onTakePearl(index) : card.onClick} />
              ) : (
                <Slot key={index} />
              ),
            )}
            <Pile kind="pearl" count={pearlDeck} onClick={onTakePearl ? () => onTakePearl('deck') : undefined} />
          </div>
        </div>
        <div>
          <h3 className="mi-panel-h">
            Character display <span className="mi-label">2 face up</span>
          </h3>
          <div className="mi-market-zone">
            {characters.slice(0, 2).map((card, index) =>
              card ? (
                <CharacterCard
                  key={index}
                  {...card}
                  onClick={onTakeCharacter ? () => onTakeCharacter(index) : card.onClick}
                />
              ) : (
                <Slot key={index} />
              ),
            )}
            <Pile
              kind="character"
              count={characterDeck}
              onClick={onTakeCharacter ? () => onTakeCharacter('deck') : undefined}
            />
          </div>
          {children}
        </div>
      </div>
    </section>
  );
}
