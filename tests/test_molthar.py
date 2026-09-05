"""Tests for the simplified *Portale von Molthar* OpenSpiel game."""

from collections import Counter

import numpy as np
import pyspiel
import pytest

from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.molthar import _HAND_LIMIT, _PEARL_COPIES, _PEARL_VALUES

_TOTAL_PEARLS = len(_PEARL_VALUES) * _PEARL_COPIES


def _character_index(card_id: str) -> int:
    """Return the `CHARACTERS` index of the card with `card_id`."""
    return next(index for index, character in enumerate(CHARACTERS) if character.id == card_id)


def _play_random_game(seed: int, *, auto_discard: bool = False) -> pyspiel.State:
    """Play one game with uniformly random actions and return the terminal state."""
    rng = np.random.default_rng(seed)
    name = f"python_portale_von_molthar(auto_discard={str(auto_discard).lower()})"
    state = pyspiel.load_game(name).new_initial_state()
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


@pytest.mark.parametrize("auto_discard", [False, True])
@pytest.mark.parametrize("seed", range(10))
def test_molthar_game_random_playthrough(seed: int, *, auto_discard: bool) -> None:
    state = _play_random_game(seed, auto_discard=auto_discard)
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
    assert game.num_distinct_actions() == 17
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
    assert state.scores[0] == CHARACTERS[card].points
    assert state._diamonds[0] == CHARACTERS[card].diamonds  # noqa: SLF001
    assert state._hands[0].total() == 0  # noqa: SLF001
    assert state._portals[0] == []  # noqa: SLF001


def test_molthar_state_discard_choice() -> None:
    """Over the hand limit, the player picks which pearl cards to drop."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._hands[0] = Counter({5: 1, 6: 1, 7: 2, 8: 1})  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001
    state.apply_action(0)  # take the pearl of value 1, giving a hand of six
    assert state.is_chance_node()  # the display is refilled before the discard
    state.apply_action(2)
    assert state.current_player() == 0
    assert state.legal_actions() == [9, 13, 14, 15, 16]  # discard a 1, 5, 6, 7 or 8
    assert state.action_to_string(0, 16) == "Discard:8"
    state.apply_action(16)
    assert state._hands[0] == Counter({1: 1, 5: 1, 6: 1, 7: 2})  # noqa: SLF001
    assert state._pearl_discard[8] == 1  # noqa: SLF001
    # The hand is at the limit again, so the turn passes on.
    assert state._cur_player == 1  # noqa: SLF001
    assert state._actions_left == 3  # noqa: SLF001


def test_molthar_state_auto_discard_trims_the_hand() -> None:
    """With `auto_discard`, the hand is trimmed by the heuristic and never by an action."""
    game = pyspiel.load_game("python_portale_von_molthar(auto_discard=true)")
    state = game.new_initial_state()
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._hands[0] = Counter({5: 1, 6: 1, 7: 2, 8: 1})  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001
    state.apply_action(0)
    assert state._hands[0].total() == _HAND_LIMIT  # noqa: SLF001
    assert state._cur_player == 1  # noqa: SLF001


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
    assert state.scores[0] == CHARACTERS[card].points
