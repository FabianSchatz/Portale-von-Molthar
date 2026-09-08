"""Tests for provenance-preserving activation payment plans."""

from collections import Counter

import pytest

from portale_von_molthar.cards import CHARACTERS, Character
from portale_von_molthar.payments import (
    PearlPayment,
    PearlSource,
    hand_resource_options,
    payment_plans,
)
from portale_von_molthar.requirements import ExactValues


def _character(card_id: str) -> Character:
    """Return the character card with `card_id` from `CHARACTERS`."""
    return next(character for character in CHARACTERS if character.id == card_id)


@pytest.mark.parametrize(
    ("hand", "card_id", "expected"),
    [
        ({3: 2}, "goblin", ((3, 3),)),
        ({3: 1, 4: 1}, "goblin", ()),
        ({3: 2, 4: 2}, "goblin", ((3, 3), (4, 4))),
        ({7: 3}, "fluffy", ((7, 7, 7),)),
        ({8: 4}, "lion", ((8, 8, 8, 8),)),
        ({8: 3}, "lion", ()),
        ({6: 2, 8: 2}, "dwarf", ((6, 6, 8, 8),)),
        ({1: 1, 3: 1, 5: 1}, "bilbo_odd", ((1, 3, 5),)),
        ({1: 1, 3: 1, 5: 1}, "bilbo_even", ()),
        ({2: 1, 4: 1, 6: 1}, "bilbo_even", ((2, 4, 6),)),
        (
            {1: 1, 3: 1, 5: 1, 7: 1},
            "bilbo_odd",
            ((1, 3, 5), (1, 3, 7), (1, 5, 7), (3, 5, 7)),
        ),
        ({3: 2, 6: 2}, "gnome", ((3, 3, 6, 6),)),
        ({6: 2, 7: 2}, "gnome", ((6, 6, 7, 7),)),
        ({3: 2, 4: 2, 6: 2}, "gnome", ((3, 3, 6, 6), (4, 4, 6, 6))),
        ({6: 4}, "gnome", ((6, 6, 6, 6),)),
        ({6: 2}, "gnome", ()),
        ({8: 1, 7: 1, 5: 1}, "terminator", ((5, 7, 8),)),
        ({8: 1, 7: 1, 4: 1}, "terminator", ()),
    ],
)
def test_payment_plans_with_hand_resources(
    hand: dict[int, int],
    card_id: str,
    expected: tuple[tuple[int, ...], ...],
) -> None:
    character = _character(card_id)
    resources = hand_resource_options(Counter(hand))
    plans = payment_plans(resources, character.requirement)
    assert tuple(plan.discarded_values for plan in plans) == expected


def test_payment_plans_track_diamond_modification() -> None:
    printed = PearlPayment(PearlSource.HAND, 3, printed_value=3)
    increased = PearlPayment(
        PearlSource.HAND,
        4,
        printed_value=3,
        diamonds_spent=1,
    )
    plans = payment_plans(
        ((printed, increased),),
        ExactValues((4,)),
        available_diamonds=1,
    )
    assert len(plans) == 1
    assert plans[0].pearls == (increased,)
    assert plans[0].diamonds_spent == 1
    assert plans[0].discarded_values == (3,)


def test_payment_plans_track_virtual_source() -> None:
    physical = PearlPayment(PearlSource.HAND, 1, printed_value=1)
    virtual = PearlPayment(
        PearlSource.VIRTUAL,
        8,
        source_id="phoenix",
        discard=False,
    )
    plans = payment_plans(((physical,), (virtual,)), ExactValues((1, 8)))
    assert len(plans) == 1
    assert plans[0].pearls == (physical, virtual)
    assert plans[0].discarded_values == (1,)
