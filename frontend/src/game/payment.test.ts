import { describe, expect, it } from 'vitest';
import type { PlanView } from '../api/types';
import { indicesForValues, matchingPlans, suggestedCardSets } from './payment';

const plans: PlanView[] = [
  { index: 0, cards: [1, 3, 5], labels: ['1', '3', '5'], diamonds: 0 },
  { index: 1, cards: [3, 5, 7], labels: ['3', '5', '7'], diamonds: 0 },
  { index: 2, cards: [5, 7], labels: ['5', '7', 'Fuchur as 3'], diamonds: 0 },
  { index: 3, cards: [7, 5], labels: ['5 as 6 (diamond)', '7'], diamonds: 1 },
  { index: 4, cards: [], labels: ['Fuchur as 1'], diamonds: 0 },
];

describe('matchingPlans', () => {
  it('matches the selected cards in any order', () => {
    expect(matchingPlans(plans, [5, 3, 1]).map((plan) => plan.index)).toEqual([0]);
  });
  it('returns every variant paying with the same cards', () => {
    expect(matchingPlans(plans, [7, 5]).map((plan) => plan.index)).toEqual([2, 3]);
  });
  it('matches virtual-only plans with an empty selection', () => {
    expect(matchingPlans(plans, []).map((plan) => plan.index)).toEqual([4]);
  });
  it('rejects selections that fit no plan', () => {
    expect(matchingPlans(plans, [1, 5])).toEqual([]);
  });
});

describe('suggestedCardSets', () => {
  it('lists each card set once, sorted', () => {
    expect(suggestedCardSets(plans)).toEqual([[1, 3, 5], [3, 5, 7], [5, 7], []]);
  });
});

describe('indicesForValues', () => {
  it('uses each hand card at most once', () => {
    expect(indicesForValues([3, 5, 3, 7], [3, 3])).toEqual([0, 2]);
    expect(indicesForValues([3, 5], [3, 3])).toEqual([0]);
  });
});
