"""Green character cards and pearl-requirement matching.

Only the 14 green (no-special-ability) character cards from
``docs/character_cards.md`` are modelled here; red (one-shot) and blue
(permanent) ability cards belong in sibling modules once implemented.
"""

import itertools
from collections import Counter
from typing import Final, NamedTuple, TypeAlias


class RequirementPart(NamedTuple):
    """One clause of a character's pearl-card activation requirement.

    Several parts combine with logical AND (see RULES.md section 7.10); a
    physical pearl card matched by one part is unavailable to the next.

    Attributes:
        kind: One of "exact", "same", "parity" or "sum".
        values: Exact multiset of pearl values required; used when `kind` is
            "exact".
        size: Number of pearl cards required; used by every kind but "exact".
        even: Whether a "parity" clause needs even (True) or odd (False)
            values.
        total: Target sum of the chosen cards; used when `kind` is "sum".
    """

    kind: str
    values: tuple[int, ...] = ()
    size: int = 0
    even: bool = False
    total: int = 0


Requirement: TypeAlias = tuple[RequirementPart, ...]


def _exact_values(*values: int) -> RequirementPart:
    """Require exactly these pearl values (RULES.md section 7.1)."""
    return RequirementPart("exact", values=values)


def _count_same(size: int) -> RequirementPart:
    """Require `size` pearls of one, unrestricted, shared value (section 7.2)."""
    return RequirementPart("same", size=size)


def _count_odd(size: int) -> RequirementPart:
    """Require `size` pearls with odd values (section 7.5)."""
    return RequirementPart("parity", size=size, even=False)


def _count_even(size: int) -> RequirementPart:
    """Require `size` pearls with even values (section 7.4)."""
    return RequirementPart("parity", size=size, even=True)


def _count_sum(size: int, total: int) -> RequirementPart:
    """Require exactly `size` pearls summing to `total` (section 7.6)."""
    return RequirementPart("sum", size=size, total=total)


class Character(NamedTuple):
    """A green character card: no red or blue special ability.

    Attributes:
        id: Stable identifier matching `docs/character_cards.md`.
        requirement: ANDed pearl requirement clauses paid on activation.
        points: Power points awarded on activation.
        copies: Number of copies of this card in the character deck.
        diamonds: Diamonds awarded to the player on activation.
        diamonds_cost: Diamonds the player must additionally pay to activate
            (RULES.md section 8.2), on top of `requirement`.
    """

    id: str
    requirement: Requirement
    points: int
    copies: int
    diamonds: int = 0
    diamonds_cost: int = 0


# Green cards from docs/character_cards.md; copies sum to 23 as documented there.
CHARACTERS: Final = (
    Character("goblin", (_count_same(2),), points=1, copies=3),
    Character("fluffy", (_count_same(3),), points=2, copies=2),
    Character("lion", (_exact_values(8, 8, 8, 8),), points=5, copies=1),
    Character("dwarf", (_exact_values(6, 6, 8, 8),), points=3, copies=3),
    Character("hansel_and_gretel", (_exact_values(8, 8),), points=2, copies=2),
    Character("frau_holle", (_exact_values(7, 7, 7, 7),), points=4, copies=2),
    Character("groot", (_count_same(4),), points=3, copies=1),
    Character("bilbo_odd", (_count_odd(3),), points=1, copies=1, diamonds=1),
    Character("bilbo_even", (_count_even(3),), points=1, copies=1, diamonds=1),
    Character(
        "gnome",
        (_count_same(2), _exact_values(6, 6)),
        points=2,
        copies=2,
        diamonds=1,
    ),
    Character(
        "captain_hook",
        (_exact_values(2, 2, 2),),
        points=3,
        copies=1,
        diamonds_cost=1,
    ),
    Character("terminator", (_count_sum(3, 20),), points=2, copies=1),
    Character("unicorn", (_exact_values(1, 2, 3, 4),), points=1, copies=1, diamonds=2),
    Character("trump", (_exact_values(7, 7, 8, 8),), points=3, copies=2, diamonds=1),
)


def _match_exact(hand: Counter[int], values: tuple[int, ...]) -> list[int] | None:
    """Match an "exact" clause: every value in `values` must be present in `hand`."""
    needed = Counter(values)
    if all(hand[value] >= copies for value, copies in needed.items()):
        return list(values)
    return None


def _match_same(hand: Counter[int], count: int) -> list[int] | None:
    """Match a "same" clause with the lowest value that has enough copies."""
    for value in sorted(hand):
        if hand[value] >= count:
            return [value] * count
    return None


def _match_parity(hand: Counter[int], count: int, *, even: bool) -> list[int] | None:
    """Match a "parity" clause with the `count` lowest cards of matching parity."""
    pool = [value for value in sorted(hand.elements()) if (value % 2 == 0) == even]
    if len(pool) < count:
        return None
    return pool[:count]


def _match_sum(hand: Counter[int], count: int, total: int) -> list[int] | None:
    """Match a "sum" clause with the lexicographically lowest fitting combination."""
    cards = sorted(hand.elements())
    for combination in itertools.combinations(cards, count):
        if sum(combination) == total:
            return list(combination)
    return None


def _match_part(hand: Counter[int], part: RequirementPart) -> list[int] | None:
    """Match one requirement clause against `hand`, or return None if it cannot be paid."""
    if part.kind == "exact":
        return _match_exact(hand, part.values)
    if part.kind == "same":
        return _match_same(hand, part.size)
    if part.kind == "parity":
        return _match_parity(hand, part.size, even=part.even)
    return _match_sum(hand, part.size, part.total)  # kind == "sum"


def find_combination(hand: Counter[int], character: Character) -> list[int] | None:
    """Find pearl values from `hand` that satisfy every clause of `character`'s requirement.

    Clauses are matched greedily in the order they are declared, each consuming
    the pearls it needs before the next clause is tried. This is deterministic
    and, for every requirement currently in `CHARACTERS`, also complete: no
    green card's clauses can consume the same pearl in two conflicting ways.

    Args:
        hand: Multiset of pearl values held by the player.
        character: The character card whose requirement must be met.

    Returns:
        The pearl values to discard, or None if the hand cannot pay.
    """
    working = Counter(hand)
    combination: list[int] = []
    for part in character.requirement:
        found = _match_part(working, part)
        if found is None:
            return None
        working.subtract(found)
        combination.extend(found)
    return combination
