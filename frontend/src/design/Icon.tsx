import type { ReactElement, SVGProps } from 'react';

/** The glyphs of Molthar Illuminated II (leaf, flame and ring mark the character types); colour them with a concept token on the parent. */
export type IconName =
  | 'power'
  | 'diamond'
  | 'pearl'
  | 'swap'
  | 'portal'
  | 'hand'
  | 'action'
  | 'warning'
  | 'fleuron'
  | 'leaf'
  | 'flame'
  | 'ring';

export interface IconProps {
  name: IconName;
  size?: number;
  /** Only when the icon stands alone; otherwise it is hidden from screen readers. */
  title?: string;
  className?: string;
}

type Part = ['path' | 'circle' | 'rect', SVGProps<SVGElement>];

const STAR8 =
  'M12 2 L13.76 7.75 L19.07 4.93 L16.25 10.24 L22 12 L16.25 13.76 L19.07 19.07 L13.76 16.25 L12 22 L10.24 16.25 L4.93 19.07 L7.75 13.76 L2 12 L7.75 10.24 L4.93 4.93 L10.24 7.75 Z';
const STROKE: SVGProps<SVGElement> = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

const PATHS: Record<IconName, Part[]> = {
  power: [['path', { d: STAR8, fill: 'currentColor' }]],
  diamond: [
    ['path', { d: 'M12 2.5 L19.5 12 L12 21.5 L4.5 12 Z', fill: 'currentColor' }],
    [
      'path',
      { d: 'M4.5 12 H19.5 M12 2.5 L9 12 L12 21.5 L15 12 Z', fill: 'none', stroke: 'rgba(0,0,0,.3)', strokeWidth: 1 },
    ],
  ],
  pearl: [
    ['circle', { cx: 12, cy: 12, r: 8, ...STROKE }],
    ['circle', { cx: 9.5, cy: 9.5, r: 2, fill: 'currentColor' }],
  ],
  swap: [['path', { d: 'M4 8 H17 L13.5 4.5 M20 16 H7 L10.5 19.5', ...STROKE }]],
  portal: [
    ['path', { d: 'M5 21 V12 Q5 6 12 3 Q19 6 19 12 V21 Z', ...STROKE }],
    ['path', { d: 'M9 21 V13 Q9 9.5 12 8 Q15 9.5 15 13 V21', ...STROKE, strokeWidth: 1.5 }],
  ],
  hand: [
    ['rect', { x: 4, y: 6, width: 10, height: 14, rx: 1, ...STROKE }],
    ['path', { d: 'M9 4.5 L18.5 6 A2 2 0 0 1 20 8.3 L18.2 18', ...STROKE }],
  ],
  action: [['circle', { cx: 12, cy: 12, r: 5, fill: 'currentColor' }]],
  warning: [
    ['path', { d: 'M12 3 L22 20 H2 Z', ...STROKE }],
    ['path', { d: 'M12 9.5 V14 M12 16.5 V17', ...STROKE }],
  ],
  fleuron: [
    [
      'path',
      {
        d: 'M12 21 C12 15 12 11 12 6 M12 13 C8 13 5 10 6 6 C9 6 12 9 12 13 M12 13 C16 13 19 10 18 6 C15 6 12 9 12 13 M12 6 C10.5 4.5 10.5 3 12 2 C13.5 3 13.5 4.5 12 6 Z',
        fill: 'currentColor',
        stroke: 'currentColor',
        strokeWidth: 1.2,
        strokeLinejoin: 'round',
      },
    ],
  ],
  leaf: [['path', { d: 'M5 19 C5 10 10 5 19 5 C19 14 14 19 5 19 Z M5 19 L13 11', ...STROKE }]],
  flame: [
    [
      'path',
      {
        d: 'M12 3 C13 7 17 9 17 14 A5 5 0 0 1 7 14 C7 11 9 10 9.5 7.5 C11 9 11.5 10 11.5 11.5 C13 10 12.8 6 12 3 Z',
        fill: 'currentColor',
      },
    ],
  ],
  ring: [
    ['circle', { cx: 12, cy: 12, r: 7.5, ...STROKE }],
    ['path', { d: 'M12 2.5 V6 M12 18 V21.5 M2.5 12 H6 M18 12 H21.5', ...STROKE }],
  ],
};

/** A single-colour glyph drawn with `currentColor`. */
export function Icon({ name, size = 16, title, className }: IconProps): ReactElement {
  return (
    <svg
      className={['mi-icon', className].filter(Boolean).join(' ')}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      {PATHS[name].map(([Tag, props], index) => {
        const Element = Tag as 'path';
        return <Element key={index} {...(props as SVGProps<SVGPathElement>)} />;
      })}
    </svg>
  );
}
