"""Green character cards and pearl-requirement matching.

Only the 14 green (no-special-ability) character cards from
``docs/character_cards.md`` are modelled here; red (one-shot) and blue
(permanent) ability cards belong in sibling modules once implemented.
"""

import itertools
from collections import Counter
from collections.abc import Iterator
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


def _clause_options(pool: Counter[int], part: RequirementPart) -> Iterator[tuple[int, ...]]:
    """Yield every distinct pearl multiset from `pool` that satisfies `part` on its own.

    Args:
        pool: Multiset of pearl values still available for this clause.
        part: The single requirement clause to satisfy.

    Yields:
        Sorted tuples of pearl values, each a complete payment of `part`.
    """
    if part.kind == "exact":
        needed = Counter(part.values)
        if all(pool[value] >= copies for value, copies in needed.items()):
            yield tuple(sorted(part.values))
        return
    if part.kind == "same":
        yield from ((value,) * part.size for value in sorted(pool) if pool[value] >= part.size)
        return
    cards = sorted(pool.elements())
    if part.kind == "parity":
        cards = [value for value in cards if (value % 2 == 0) == part.even]
        yield from dict.fromkeys(itertools.combinations(cards, part.size))
        return
    yield from dict.fromkeys(  # kind == "sum"
        combination
        for combination in itertools.combinations(cards, part.size)
        if sum(combination) == part.total
    )


def _splits(pool: Counter[int], parts: Requirement) -> bool:
    """Return whether `pool` splits exactly among `parts`, one pearl card per clause position.

    Backtracks over every way a clause can be paid, so a pearl claimed by an
    early clause is given back when a later one cannot be met (RULES.md section
    7.10). `pool` must be consumed completely: it is a candidate payment, not
    the whole hand.

    Args:
        pool: Multiset of pearl values to distribute over `parts`.
        parts: The remaining ANDed requirement clauses.

    Returns:
        Whether such a split exists.
    """
    if not parts:
        return not pool.total()
    head, *rest = parts
    return any(
        _splits(pool - Counter(choice), tuple(rest)) for choice in _clause_options(pool, head)
    )


def payment_options(hand: Counter[int], character: Character) -> list[tuple[int, ...]]:
    """Return every distinct pearl multiset from `hand` that pays `character`'s requirement.

    Which of these to spend is a strategic choice and therefore left to the
    player rather than decided here; see `MoltharState._activate`.

    Args:
        hand: Multiset of pearl values held by the player.
        character: The character card whose requirement must be met.

    Returns:
        The payable pearl-value multisets as sorted tuples, in ascending order;
        empty if the hand cannot pay.
    """
    size = sum(
        len(part.values) if part.kind == "exact" else part.size for part in character.requirement
    )
    # ponytail: brute force over hand subsets; a hand holds at most eight cards.
    return sorted(
        {
            combination
            for combination in itertools.combinations(sorted(hand.elements()), size)
            if _splits(Counter(combination), character.requirement)
        },
    )
