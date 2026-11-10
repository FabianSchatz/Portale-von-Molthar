// Card ornament of Molthar Illuminated: frames, vines, rosettes and back lattices,
// all drawn in a 112 × 156 viewBox and stretched over the card.
import type { ReactElement, ReactNode } from 'react';

const ROTATE = 'rotate(180 56 78)';
const TILE_CORNERS = ['', 'translate(60 0) scale(-1 1)', 'translate(0 60) scale(1 -1)', 'translate(60 60) scale(-1 -1)'];
const STAR =
  'M0 -3.2 L0.54 -1.29 L2.26 -2.26 L1.29 -0.54 L3.2 0 L1.29 0.54 L2.26 2.26 L0.54 1.29 L0 3.2 L-0.54 1.29 L-2.26 2.26 L-1.29 0.54 L-3.2 0 L-1.29 -0.54 L-2.26 -2.26 L-0.54 -1.29 Z';

export function Ornament({ children }: { children: ReactNode }): ReactElement {
  return (
    <svg className="mi-orn" viewBox="0 0 112 156" preserveAspectRatio="none" aria-hidden>
      {children}
    </svg>
  );
}

/** The double rule: vermilion outside, verdigris inside. */
export function Frame(): ReactElement {
  return (
    <>
      <rect className="fr-out" x={3.5} y={3.5} width={105} height={149} rx={5} />
      <rect className="fr-in" x={7} y={7} width={98} height={142} rx={3} />
    </>
  );
}

function Leaf({ x, y, rotate, scale = 1 }: { x: number; y: number; rotate: number; scale?: number }): ReactElement {
  return (
    <path
      className="leaf"
      d="M0 0 C1.5 -3.5 5.5 -4.5 8 -2.5 C7 1 3.5 2.5 0 0 Z"
      transform={`translate(${x} ${y}) rotate(${rotate}) scale(${scale})`}
    />
  );
}

function Rosette({ x, y, className }: { x: number; y: number; className: string }): ReactElement {
  const petals = Array.from({ length: 5 }, (_, index) => {
    const angle = (index * 2 * Math.PI) / 5 - Math.PI / 2;
    return (
      <circle
        key={index}
        className={className}
        cx={(x + 2.3 * Math.cos(angle)).toFixed(2)}
        cy={(y + 2.3 * Math.sin(angle)).toFixed(2)}
        r={1.9}
      />
    );
  });
  return (
    <g>
      {petals}
      <circle className="fl-eye" cx={x} cy={y} r={1.2} />
    </g>
  );
}

/** A climbing vine with leaves, a red and a blue rosette (pearl cards). */
export function Vine({ rotated = false }: { rotated?: boolean }): ReactElement {
  return (
    <g transform={rotated ? ROTATE : undefined}>
      <path className="vine" d="M15 147 C11 134 23 126 19 112 C15 100 11 92 17 80 C21 72 21 62 15 52" />
      <path className="vine" d="M19 112 C24 110 26 104 23 101 C21 99 18 101 20 103" />
      <path className="vine" d="M17 80 C12 78 10 73 12 70" />
      <Leaf x={17} y={131} rotate={-60} />
      <Leaf x={14} y={104} rotate={160} />
      <Leaf x={20} y={91} rotate={-40} />
      <Leaf x={16} y={66} rotate={170} />
      <Leaf x={16} y={54} rotate={-100} scale={0.9} />
      <Rosette x={21} y={124} className="fl-red" />
      <Rosette x={12.5} y={88} className="fl-blue" />
    </g>
  );
}

/** The gold lozenge lattice of a card back, with dots (pearls) or stars (characters). */
export function Lattice({ stars, frameOnly = false }: { stars: boolean; frameOnly?: boolean }): ReactElement {
  const cells: ReactElement[] = [];
  const columns = 5;
  const rows = 6;
  const width = 92 / columns;
  const height = 136 / rows;
  if (!frameOnly) {
    for (let row = 0; row < rows; row += 1) {
      for (let column = 0; column < columns; column += 1) {
        const cx = 10 + width * (column + 0.5);
        const cy = 10 + height * (row + 0.5);
        cells.push(
          <path
            key={`l${row}${column}`}
            className="lat"
            d={`M${cx} ${cy - height / 2} L${cx + width / 2} ${cy} L${cx} ${cy + height / 2} L${cx - width / 2} ${cy} Z`}
          />,
          stars ? (
            <path key={`s${row}${column}`} className="dot" d={STAR} transform={`translate(${cx.toFixed(2)} ${cy.toFixed(2)})`} />
          ) : (
            <circle key={`s${row}${column}`} className="dot" cx={cx.toFixed(2)} cy={cy.toFixed(2)} r={1.5} />
          ),
        );
      }
    }
  }
  return (
    <>
      {cells}
      <rect className="frame" x={4} y={4} width={104} height={148} rx={5} />
      <rect className="frame2" x={8} y={8} width={96} height={140} rx={3} />
    </>
  );
}

/** Gilt corner curls inside the lapis numeral tile of a pearl card. */
export function TileOrnament(): ReactElement {
  return (
    <svg viewBox="0 0 60 60" aria-hidden>
      {TILE_CORNERS.map((transform, index) => (
        <g key={index} transform={transform || undefined}>
          <path d="M6 16 C6 10 10 6 16 6" />
          <path d="M16 6 C14 9 12 10 10 10" />
          <circle className="f" cx={10.5} cy={10.5} r={1.3} />
        </g>
      ))}
    </svg>
  );
}
