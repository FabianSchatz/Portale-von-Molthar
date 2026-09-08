"""Structured character-card data.

Only the 14 green (no-special-ability) character cards from
``docs/character_cards.md`` are modelled here; red (one-shot) and blue
(permanent) ability cards belong in sibling modules once implemented.
"""

from typing import Final, NamedTuple

from portale_von_molthar.requirements import (
    AllOf,
    ExactValues,
    FixedCountSum,
    Parity,
    ParityValues,
    Requirement,
    SameValue,
)


def _exact_values(*values: int) -> ExactValues:
    """Require exactly these pearl values (RULES.md section 7.1)."""
    return ExactValues(values)


def _count_same(size: int) -> SameValue:
    """Require `size` pearls of one, unrestricted, shared value (section 7.2)."""
    return SameValue(size)


def _count_odd(size: int) -> ParityValues:
    """Require `size` pearls with odd values (section 7.5)."""
    return ParityValues(size, Parity.ODD)


def _count_even(size: int) -> ParityValues:
    """Require `size` pearls with even values (section 7.4)."""
    return ParityValues(size, Parity.EVEN)


def _count_sum(size: int, total: int) -> FixedCountSum:
    """Require exactly `size` pearls summing to `total` (section 7.6)."""
    return FixedCountSum(size, total)


class Character(NamedTuple):
    """A character card with rewards and a typed activation requirement.

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
    Character("goblin", _count_same(2), points=1, copies=3),
    Character("fluffy", _count_same(3), points=2, copies=2),
    Character("lion", _exact_values(8, 8, 8, 8), points=5, copies=1),
    Character("dwarf", _exact_values(6, 6, 8, 8), points=3, copies=3),
    Character("hansel_and_gretel", _exact_values(8, 8), points=2, copies=2),
    Character("frau_holle", _exact_values(7, 7, 7, 7), points=4, copies=2),
    Character("groot", _count_same(4), points=3, copies=1),
    Character("bilbo_odd", _count_odd(3), points=1, copies=1, diamonds=1),
    Character("bilbo_even", _count_even(3), points=1, copies=1, diamonds=1),
    Character(
        "gnome",
        AllOf((_count_same(2), _exact_values(6, 6))),
        points=2,
        copies=2,
        diamonds=1,
    ),
    Character(
        "captain_hook",
        _exact_values(2, 2, 2),
        points=3,
        copies=1,
        diamonds_cost=1,
    ),
    Character("terminator", _count_sum(3, 20), points=2, copies=1),
    Character("unicorn", _exact_values(1, 2, 3, 4), points=1, copies=1, diamonds=2),
    Character("trump", _exact_values(7, 7, 8, 8), points=3, copies=2, diamonds=1),
)
