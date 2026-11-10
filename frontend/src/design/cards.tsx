import type { CSSProperties, ReactElement, ReactNode } from 'react';
import { Icon } from './Icon';
import type { IconName } from './Icon';
import { Frame, Lattice, Ornament, TileOrnament, Vine } from './ornament';
import { PORTRAITS } from './portraits';

/** 'row' (252 × 64) lays an activated character out as one readable line. */
export type CardSize = 'sm' | 'md' | 'lg' | 'row';

export interface CardBase {
  size?: CardSize;
  selected?: boolean;
  /** Verdigris ring: this card can be activated now. */
  activatable?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  style?: CSSProperties;
  /** Native hover text, such as a character's ability. */
  title?: string;
}

export interface PearlCardProps extends CardBase {
  value?: number;
  /** Printed character-swap symbol. */
  swap?: boolean;
  /** A diamond raises this pearl by +1 for the current activation. */
  modified?: boolean;
  faceDown?: boolean;
}

/** Exact values as tiles ('or' / 'and' join alternatives, 'diamond' is a paid diamond, other strings are
 * short words such as 'pair') or a sentence. */
export type Requirement = string | Array<number | string>;
export type CardKind = 'green' | 'red' | 'blue';
export type AbilityTiming = 'before_turn' | 'during_turn' | 'after_turn' | 'persistent';

export interface CharacterCardProps extends CardBase {
  /** Card id such as 'golem_1'; picks the portrait. */
  id?: string;
  /** Portrait key, when it differs from the id. */
  portrait?: string;
  /** Never printed: the portrait's tooltip and the card's accessible label. */
  name?: string;
  /** Ring colour and ability box: green = no ability, red = one-time, blue = persistent. */
  kind?: CardKind;
  requirement?: Requirement;
  points?: number;
  diamonds?: number;
  /** One short sentence, about 40 characters at size md. */
  ability?: string | null;
  timing?: AbilityTiming | string | null;
  faceDown?: boolean;
  /** The card's back used as a diamond. */
  diamondSide?: boolean;
}

const KIND: Record<CardKind, { word: string; icon: IconName }> = {
  green: { word: 'No ability', icon: 'leaf' },
  red: { word: 'One-time', icon: 'flame' },
  blue: { word: 'Persistent', icon: 'ring' },
};
const TIMING_WORD: Record<string, string> = {
  before_turn: 'Before your turn',
  during_turn: 'During your turn',
  after_turn: 'After your turn',
  persistent: 'Always',
};

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

/** The card element: a button when clickable, else an image with a label. */
function Shell({
  props,
  className,
  label,
  children,
}: {
  props: CardBase;
  className: string;
  label: string;
  children: ReactNode;
}): ReactElement {
  const classes = cx(
    'mi-card',
    props.size && props.size !== 'md' && `mi-card-${props.size}`,
    className,
    props.selected && 'is-selected',
    props.activatable && 'is-activatable',
    props.disabled && 'is-disabled',
    props.className,
  );
  if (props.onClick) {
    return (
      <button
        type="button"
        className={classes}
        onClick={props.onClick}
        disabled={props.disabled}
        aria-pressed={props.selected === undefined ? undefined : props.selected}
        aria-label={label}
        title={props.title}
        style={props.style}
      >
        {children}
      </button>
    );
  }
  return (
    <div className={classes} role="img" aria-label={label} title={props.title} style={props.style}>
      {children}
    </div>
  );
}

/** A pearl card laid out like an illuminated page; every pearl looks the same apart from its number. */
export function PearlCard(props: PearlCardProps): ReactElement {
  if (props.faceDown) {
    return (
      <Shell props={props} className="mi-back mi-back-red" label="Pearl card, face down">
        <Ornament>
          <Lattice stars={false} />
        </Ornament>
      </Shell>
    );
  }
  const value = props.value ?? 1;
  const shown = props.modified ? value + 1 : value;
  const label =
    `Pearl ${value}` +
    (props.modified ? `, raised to ${shown} by a diamond` : '') +
    (props.swap ? ', character swap symbol' : '') +
    (props.selected ? ', selected' : '');
  return (
    <Shell props={props} className="mi-pearl" label={label}>
      <Ornament>
        <Frame />
        <Vine />
        <Vine rotated />
      </Ornament>
      <span className="mi-pv-corner" aria-hidden>
        {value}
      </span>
      <span className="mi-pv-tile" aria-hidden>
        <TileOrnament />
        <span className="mi-pv-num">{shown}</span>
      </span>
      <span className="mi-pv-corner b" aria-hidden>
        {value}
      </span>
      {props.swap ? (
        <span className="mi-pv-swap">
          <Icon name="swap" size={18} />
        </span>
      ) : null}
      {props.modified ? (
        <span className="mi-pv-mod">
          <Icon name="diamond" size={11} />
          +1
        </span>
      ) : null}
    </Shell>
  );
}

function RequirementTiles({ requirement }: { requirement: Requirement }): ReactElement {
  if (!Array.isArray(requirement)) {
    return <div className="mi-ch-reqtext">{requirement}</div>;
  }
  return (
    <div className={cx('mi-chips', requirement.length > 6 && 'is-dense')}>
      {requirement.map((part, index) => {
        if (part === 'diamond') {
          return (
            <span key={index} className="mi-chip mi-chip-dia" title="one diamond">
              <Icon name="diamond" size={11} />
            </span>
          );
        }
        if (part === 'or' || part === 'and') {
          return (
            <span key={index} className="mi-chip-or">
              {part === 'or' ? 'or' : '+'}
            </span>
          );
        }
        return (
          <span key={index} className={typeof part === 'string' ? 'mi-chip-word' : 'mi-chip'}>
            {part}
          </span>
        );
      })}
    </div>
  );
}

export interface PortraitProps {
  id?: string;
  portrait?: string;
  name?: string;
  /** Only when the picture stands alone; inside a card the card carries the name. */
  title?: string;
  className?: string;
}

function portraitKey({ id = '', portrait }: PortraitProps): string | null {
  if (portrait && PORTRAITS[portrait]) {
    return portrait;
  }
  const base = id.replace(/_(\d+|odd|even)$/, '');
  return [id, base].find((key) => PORTRAITS[key]) ?? null;
}

/** A woodcut picture of one character (viewBox 90 × 60, fills its box); unknown ids fall back to the name. */
export function Portrait(props: PortraitProps): ReactElement {
  const key = portraitKey(props);
  return (
    <svg
      className={cx('mi-pt', props.className)}
      viewBox="0 0 90 60"
      preserveAspectRatio="xMidYMid slice"
      role={props.title ? 'img' : undefined}
      aria-label={props.title}
      aria-hidden={props.title ? undefined : true}
    >
      <rect className="sky" x={0} y={0} width={90} height={60} />
      <path className="ground" d="M0 54 Q45 50 90 54 V60 H0 Z" />
      {key ? (
        // Static markup from the design system, never user input.
        <g dangerouslySetInnerHTML={{ __html: PORTRAITS[key] }} />
      ) : (
        <text className="pt-name" x={45} y={34} textAnchor="middle">
          {props.name ?? '?'}
        </text>
      )}
    </svg>
  );
}

/** A character shown by its portrait, ringed in its type colour, with requirement and ability always readable. */
export function CharacterCard(props: CharacterCardProps): ReactElement {
  if (props.faceDown) {
    return (
      <Shell props={props} className="mi-back mi-back-blue" label="Character card, face down">
        <Ornament>
          <Lattice stars />
        </Ornament>
      </Shell>
    );
  }
  if (props.diamondSide) {
    return (
      <Shell props={props} className="mi-back mi-back-blue mi-dia" label="Diamond">
        <Ornament>
          <Lattice stars frameOnly />
          <path className="gem" d="M56 46 L80 78 L56 110 L32 78 Z" />
          <path className="facet" d="M32 78 H80 M56 46 L47 78 L56 110 L65 78 Z" />
        </Ornament>
      </Shell>
    );
  }
  const kind = props.kind ?? 'green';
  const timing = kind === 'blue' && props.timing ? TIMING_WORD[props.timing] : null;
  const diamonds = props.diamonds ?? 0;
  const name = props.name ?? '';
  const large = props.size === 'lg';
  const requirement = props.requirement ?? '';
  const requirementWords = Array.isArray(requirement) ? requirement.join(' ') : requirement;
  const label =
    `${name}, ${KIND[kind].word} character${timing ? ` (${timing})` : ''}, ${props.points ?? 0} power points` +
    (diamonds ? `, ${diamonds} diamond${diamonds > 1 ? 's' : ''}` : '') +
    `, requires ${requirementWords}` +
    (props.ability ? `. Ability: ${props.ability}` : '') +
    (props.activatable ? '. Can be activated now' : '');
  return (
    <Shell props={props} className={`mi-ch2 k-${kind}`} label={label}>
      <div className="mi-ch2-pic" title={name}>
        <Portrait id={props.id} portrait={props.portrait} name={name} />
        <span className="mi-ch2-pts">
          <Icon name="power" size={large ? 15 : 11} />
          {props.points ?? 0}
        </span>
        {diamonds ? (
          <span className="mi-ch2-dia">
            {Array.from({ length: diamonds }, (_, index) => (
              <Icon key={index} name="diamond" size={large ? 15 : 10} />
            ))}
          </span>
        ) : null}
      </div>
      <div className="mi-ch2-req">
        <span className="mi-label">requires</span>
        <RequirementTiles requirement={requirement} />
      </div>
      <div className="mi-ch2-ab">
        <div className="mi-ch2-kind">
          <Icon name={KIND[kind].icon} size={large ? 14 : 10} />
          <span>{timing ?? KIND[kind].word}</span>
        </div>
        {props.ability ? <div className="mi-ch2-text">{props.ability}</div> : null}
      </div>
    </Shell>
  );
}

/** An empty dashed place for a card. */
export function Slot({ size, label = 'Empty' }: { size?: CardSize; label?: string }): ReactElement {
  return (
    <div className={cx('mi-slot', size === 'sm' && 'mi-slot-sm')}>
      <span className="mi-label">{label}</span>
    </div>
  );
}

export interface PileProps {
  kind: 'pearl' | 'character';
  variant?: 'deck' | 'discard';
  count: number;
  top?: PearlCardProps | CharacterCardProps;
  size?: CardSize;
  onClick?: () => void;
}

/** A draw deck or discard pile with its count beneath. */
export function Pile({ kind, variant, count, top, size, onClick }: PileProps): ReactElement {
  const Card = kind === 'character' ? CharacterCard : PearlCard;
  const discard = variant === 'discard';
  let shown: ReactElement;
  if (!count) {
    shown = <Slot size={size} label={discard ? 'Discard' : 'Empty'} />;
  } else if (discard && top) {
    shown = <Card size={size} {...top} />;
  } else {
    shown = <Card faceDown size={size} onClick={onClick} />;
  }
  return (
    <div className={cx('mi-pile', discard && 'mi-pile-discard')}>
      <div className={cx('mi-pile-stack', count > 1 && 'has-depth')}>{shown}</div>
      <div className="mi-pile-cap">
        <b>{count}</b> {discard ? 'discarded' : 'in deck'}
      </div>
    </div>
  );
}

export interface HandProps {
  cards: PearlCardProps[];
  limit?: number;
  size?: CardSize;
  onToggle?: (index: number) => void;
}

/** The local player's pearl cards with the hand-limit line below. */
export function Hand({ cards, limit = 5, size, onToggle }: HandProps): ReactElement {
  const over = cards.length > limit;
  return (
    <div className="mi-hand-wrap">
      <div className="mi-hand">
        {cards.map((card, index) => (
          <PearlCard key={index} size={size} {...card} onClick={onToggle ? () => onToggle(index) : card.onClick} />
        ))}
      </div>
      <div className={cx('mi-hand-limit', over && 'is-over')}>
        {over
          ? `${cards.length} / ${limit} — discard ${cards.length - limit} at the end of your turn`
          : `${cards.length} / ${limit} hand limit`}
      </div>
    </div>
  );
}
