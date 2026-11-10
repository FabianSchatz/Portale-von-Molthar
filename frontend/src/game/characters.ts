import type { Catalog } from '../api/types';
import type { CharacterCardProps } from '../design';

/** Card props for a character id: portrait, ring, requirement and ability all come from the catalog. */
export function characterProps(catalog: Catalog, id: string): CharacterCardProps {
  const info = catalog[id];
  if (!info) {
    return { id, name: id };
  }
  return {
    id,
    name: info.name,
    kind: info.kind,
    requirement: info.requirement,
    points: info.points,
    diamonds: info.diamonds,
    ability: info.ability,
    timing: info.timing,
  };
}

export function characterName(catalog: Catalog, id: string): string {
  return catalog[id]?.name ?? id;
}
