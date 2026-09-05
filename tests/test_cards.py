"""Tests for green character card data and pearl-requirement matching."""

from collections import Counter

import pytest

from portale_von_molthar.cards import CHARACTERS, Character, find_combination


def _character(card_id: str) -> Character:
    """Return the green character card with `card_id` from `CHARACTERS`."""
    return next(character for character in CHARACTERS if character.id == card_id)


@pytest.mark.parametrize(
    ("hand", "card_id", "expected"),
    [
        ({3: 2}, "goblin", [3, 3]),
        ({3: 1, 4: 1}, "goblin", None),
        ({7: 3}, "fluffy", [7, 7, 7]),
        ({8: 4}, "lion", [8, 8, 8, 8]),
        ({8: 3}, "lion", None),
        ({6: 2, 8: 2}, "dwarf", [6, 6, 8, 8]),
        ({1: 1, 3: 1, 5: 1}, "bilbo_odd", [1, 3, 5]),
        ({1: 1, 3: 1, 5: 1}, "bilbo_even", None),
        ({2: 1, 4: 1, 6: 1}, "bilbo_even", [2, 4, 6]),
        ({3: 2, 6: 2}, "gnome", [3, 3, 6, 6]),
        ({6: 4}, "gnome", [6, 6, 6, 6]),
        ({6: 2}, "gnome", None),
        ({8: 1, 7: 1, 5: 1}, "terminator", [5, 7, 8]),
        ({8: 1, 7: 1, 4: 1}, "terminator", None),
    ],
)
def test_find_combination(
    hand: dict[int, int],
    card_id: str,
    expected: list[int] | None,
) -> None:
    result = find_combination(Counter(hand), _character(card_id))
    assert (sorted(result) if result is not None else None) == expected


def test_character_data_matches_docs() -> None:
    """`CHARACTERS` must mirror the green-card table in docs/character_cards.md."""
    assert len(CHARACTERS) == 14
    assert sum(character.copies for character in CHARACTERS) == 23
    assert len({character.id for character in CHARACTERS}) == 14
