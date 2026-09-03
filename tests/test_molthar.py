"""Tests for the simplified *Portale von Molthar* OpenSpiel game."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pyspiel
import pytest

from portale_von_molthar.molthar import (
    _CHARACTERS,
    _HAND_LIMIT,
    _PEARL_COPIES,
    _PEARL_VALUES,
    Character,
    find_combination,
)

_TOTAL_PEARLS = len(_PEARL_VALUES) * _PEARL_COPIES


def _character(card_id: str) -> Character:
    """Return the green character card with `card_id` from `_CHARACTERS`."""
    return next(character for character in _CHARACTERS if character.id == card_id)


def _character_index(card_id: str) -> int:
    """Return the `_CHARACTERS` index of the card with `card_id`."""
    return next(index for index, character in enumerate(_CHARACTERS) if character.id == card_id)


def _play_random_game(seed: int) -> pyspiel.State:
    """Play one game with uniformly random actions and return the terminal state."""
    rng = np.random.default_rng(seed)
    state = pyspiel.load_game("python_portale_von_molthar").new_initial_state()
    while not state.is_terminal():
        if state.is_chance_node():
            outcomes, probabilities = zip(*state.chance_outcomes(), strict=True)
            action = rng.choice(outcomes, p=probabilities)
        else:
            action = rng.choice(state.legal_actions())
        _assert_pearls_conserved(state)
        state.apply_action(int(action))
    return state


def _assert_pearls_conserved(state: pyspiel.State) -> None:
    """No pearl card may be created or lost by any transition."""
    held = sum(hand.total() for hand in state._hands)  # noqa: SLF001
    total = (
        state._pearl_deck.total()  # noqa: SLF001
        + state._pearl_discard.total()  # noqa: SLF001
        + len(state._pearl_display)  # noqa: SLF001
        + held
    )
    assert total == _TOTAL_PEARLS


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
    """`_CHARACTERS` must mirror the green-card table in docs/character_cards.md."""
    assert len(_CHARACTERS) == 14
    assert sum(character.copies for character in _CHARACTERS) == 23
    assert len({character.id for character in _CHARACTERS}) == 14


@pytest.mark.parametrize("seed", range(10))
def test_molthar_game_random_playthrough(seed: int) -> None:
    state = _play_random_game(seed)
    assert state.is_terminal()
    assert sum(state.returns()) == 0.0
    # Random play must actually finish by scoring, not by hitting the node cap.
    assert max(state.scores) >= 12
    # Hands are trimmed at the end of every turn.
    for hand in state._hands:  # noqa: SLF001
        assert hand.total() <= _HAND_LIMIT


def test_molthar_game_registration() -> None:
    game = pyspiel.load_game("python_portale_von_molthar")
    assert game.num_players() == 2
    assert game.num_distinct_actions() == 9
    state = game.new_initial_state()
    assert state.is_chance_node()
    assert len(state.observation_tensor(0)) == game.observation_tensor_shape()[0]


def test_molthar_state_activation_scores() -> None:
    """Activating a character pays its pearls, awards points, and awards diamonds."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index("bilbo_odd")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert 7 in state.legal_actions()
    state.apply_action(7)
    assert state.scores[0] == _CHARACTERS[card].points
    assert state._diamonds[0] == _CHARACTERS[card].diamonds  # noqa: SLF001
    assert state._hands[0].total() == 0  # noqa: SLF001
    assert state._portals[0] == []  # noqa: SLF001


def test_molthar_state_diamond_cost_gates_activation() -> None:
    """A character with a diamond cost cannot be activated without a diamond in hand."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index("captain_hook")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({2: 3})  # noqa: SLF001
    state._pearl_display = [1, 3, 4, 5]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert 7 not in state.legal_actions()
    state._diamonds[0] = 1  # noqa: SLF001
    assert 7 in state.legal_actions()
    state.apply_action(7)
    assert state._diamonds[0] == 0  # noqa: SLF001
    assert state.scores[0] == _CHARACTERS[card].points
