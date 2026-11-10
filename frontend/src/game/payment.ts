import type { PlanView } from '../api/types';

function sortedKey(values: number[]): string {
  return [...values].sort((left, right) => left - right).join(',');
}

/** The plans that discard exactly the selected hand pearls (diamond or virtual variants included). */
export function matchingPlans(plans: PlanView[], selected: number[]): PlanView[] {
  const key = sortedKey(selected);
  return plans.filter((plan) => sortedKey(plan.cards) === key);
}

/** Distinct card sets that can pay, for one-click suggestions; the cheapest come first. */
export function suggestedCardSets(plans: PlanView[]): number[][] {
  const seen = new Map<string, number[]>();
  for (const plan of [...plans].sort((left, right) => left.diamonds - right.diamonds)) {
    const key = sortedKey(plan.cards);
    if (!seen.has(key)) {
      seen.set(key, [...plan.cards].sort((left, right) => left - right));
    }
  }
  return [...seen.values()];
}

/** Hand indices holding `values`, taking the first unused copy of each value. */
export function indicesForValues(hand: number[], values: number[]): number[] {
  const used = new Set<number>();
  for (const value of values) {
    const index = hand.findIndex((card, position) => card === value && !used.has(position));
    if (index >= 0) {
      used.add(index);
    }
  }
  return [...used];
}
