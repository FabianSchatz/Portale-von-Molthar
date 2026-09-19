"""Tests for the simplified *Portale von Molthar* OpenSpiel game."""

from collections import Counter

import numpy as np
import pyspiel
import pytest

from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.decisions import RedChoice
from portale_von_molthar.molthar import (
    _HAND_LIMIT,
    _MAX_NODES,
    _NUM_PLAYERS,
    _PEARL_COPIES,
    _PEARL_VALUES,
    Action,
)

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
    # Some random players fill their portals with cards they cannot activate.
    assert max(state.scores) >= 12 or state._nodes == _MAX_NODES  # noqa: SLF001
    # Scoring ends at a turn boundary; the node cap can interrupt a turn.
    if max(state.scores) >= 12:
        for hand in state._hands:  # noqa: SLF001
            assert hand.total() <= _HAND_LIMIT


def test_molthar_game_registration() -> None:
    game = pyspiel.load_game("python_portale_von_molthar")
    assert game.num_players() == 2
    assert game.num_distinct_actions() == 70
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
    assert state._activated_characters[0] == [card]  # noqa: SLF001


@pytest.mark.parametrize(
    ("card_id", "value"),
    [
        ("irrlicht_1", 3),
        ("irrlicht_1", 6),
        ("irrlicht_2", 4),
        ("irrlicht_2", 5),
    ],
)
def test_molthar_state_neighbor_can_activate_irrlicht(card_id: str, value: int) -> None:
    """A payable Irrlicht on the neighboring portal is a distinct activation."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index(card_id)
    state._portals[1] = [card]  # noqa: SLF001
    state._hands[0] = Counter({value: 3})  # noqa: SLF001
    state._pearl_display = [1, 2, 7, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    assert Action.ACTIVATE_NEIGHBOR_0 in state.legal_actions()
    assert state.action_to_string(0, Action.ACTIVATE_NEIGHBOR_0) == (f"ActivateNeighbor:{card_id}")
    state.apply_action(Action.ACTIVATE_NEIGHBOR_0)

    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._portals[1] == []  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001
    assert state.scores[0] == 3
    assert state.scores[1] == 0
    assert state._actions_left == 2  # noqa: SLF001


def test_molthar_state_irrlicht_payment_keeps_foreign_target() -> None:
    """A pending Irrlicht payment retains the owner of the target portal."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index("irrlicht_1")
    state._portals[1] = [card]  # noqa: SLF001
    state._hands[0] = Counter({3: 3, 6: 3})  # noqa: SLF001
    state._pearl_display = [1, 2, 7, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_NEIGHBOR_0)

    decision = state._pending_decision  # noqa: SLF001
    assert decision is not None
    assert decision.actor == 0
    assert decision.target_owner == 1
    assert decision.target_slot == 0
    assert state.legal_actions() == [Action.PAY_HAND_3, Action.PAY_HAND_6]
    assert "payment_target=p1:0" in state.observation_string(0)

    state.apply_action(Action.PAY_HAND_3)

    assert state._pending_decision is None  # noqa: SLF001
    assert state._hands[0] == Counter({6: 3})  # noqa: SLF001
    assert state._portals[1] == []  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001


def test_molthar_state_neighbor_actions_distinguish_portal_slots() -> None:
    """Only the slot containing Irrlicht receives a neighboring activation action."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    golem = _character_index("golem_1")
    irrlicht = _character_index("irrlicht_1")
    state._portals[1] = [golem, irrlicht]  # noqa: SLF001
    state._hands[0] = Counter({3: 3, 4: 2, 6: 1, 8: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 5]  # noqa: SLF001
    state._character_display = [golem, irrlicht]  # noqa: SLF001

    assert Action.ACTIVATE_NEIGHBOR_0 not in state.legal_actions()
    assert Action.ACTIVATE_NEIGHBOR_1 in state.legal_actions()
    assert state.action_to_string(0, Action.ACTIVATE_NEIGHBOR_1) == ("ActivateNeighbor:irrlicht_1")


@pytest.mark.parametrize(
    ("card_id", "hand"),
    [
        ("golem_1", Counter({4: 2, 6: 1, 8: 1})),
        ("golem_2", Counter({1: 1, 3: 1, 5: 1, 7: 1})),
    ],
)
def test_molthar_state_golem_grants_three_actions(
    card_id: str,
    hand: Counter[int],
) -> None:
    """Activating a Golem immediately adds three actions to the current turn."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index(card_id)
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = hand  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 5]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)

    assert state._actions_left == 5  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001
    assert state.scores[0] == 2


def test_molthar_state_puss_in_boots_keeps_paid_pearl() -> None:
    """Puss can return one used physical pearl to the player's hand."""
    state = pyspiel.load_game("python_portale_von_molthar").new_initial_state()
    card = _character_index("puss_in_boots")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({3: 1, 4: 1, 5: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 6, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert set(state.legal_actions()) == {
        Action.KEEP_NONE,
        Action.KEEP_3,
        Action.KEEP_4,
        Action.KEEP_5,
    }
    state.apply_action(Action.KEEP_4)
    assert state._hands[0] == Counter({4: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({3: 1, 5: 1})  # noqa: SLF001
    assert state._actions_left == 2  # noqa: SLF001


def test_molthar_state_dementor_bonuses_next_turn() -> None:
    """Dementor gives the next player an extra action on their next turn."""
    state = pyspiel.load_game("python_portale_von_molthar").new_initial_state()
    card = _character_index("dementor")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({2: 2, 4: 2})  # noqa: SLF001
    state._pearl_display = [1, 3, 5, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state.current_player() == 1
    assert state._actions_left == 4  # noqa: SLF001
    assert state._next_turn_bonus[1] == 0  # noqa: SLF001


def test_molthar_state_tinkerbell_steals_visible_choice() -> None:
    """Only Tinkerbell's actor sees the hand and chooses a card to take."""
    state = pyspiel.load_game("python_portale_von_molthar").new_initial_state()
    card = _character_index("tinkerbell")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({5: 1, 6: 1, 7: 1})  # noqa: SLF001
    state._hands[1] = Counter({2: 1, 8: 1})  # noqa: SLF001
    state._pearl_display = [1, 3, 4, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state.legal_actions() == [Action.TARGET_PLAYER_1]
    state.apply_action(Action.TARGET_PLAYER_1)
    assert set(state.legal_actions()) == {Action.STEAL_2, Action.STEAL_8}
    assert "revealed_hand=[2, 8]" in state.observation_string(0)
    assert "revealed_hand=None" in state.observation_string(1)
    tail = len(RedChoice)
    assert state.observation_tensor(0)[-tail - 8 : -tail] == [
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        1.0,
    ]
    assert state.observation_tensor(1)[-tail - 8 : -tail] == [0.0] * 8
    state.apply_action(Action.STEAL_8)
    assert state._hands[0] == Counter({8: 1})  # noqa: SLF001
    assert state._hands[1] == Counter({2: 1})  # noqa: SLF001


def test_molthar_state_medusa_discards_opposing_portal_card() -> None:
    """Medusa chooses which opposing portal card is discarded."""
    state = pyspiel.load_game("python_portale_von_molthar").new_initial_state()
    card = _character_index("medusa")
    goblin = _character_index("goblin")
    fluffy = _character_index("fluffy")
    state._portals[0] = [card]  # noqa: SLF001
    state._portals[1] = [goblin, fluffy]  # noqa: SLF001
    state._hands[0] = Counter({1: 2, 5: 1})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state.legal_actions() == [Action.TARGET_PLAYER_1]
    state.apply_action(Action.TARGET_PLAYER_1)
    assert set(state.legal_actions()) == {Action.DISCARD_PORTAL_0, Action.DISCARD_PORTAL_1}
    state.apply_action(Action.DISCARD_PORTAL_1)
    assert state._portals[1] == [goblin]  # noqa: SLF001
    assert state._character_discard[fluffy] == 1  # noqa: SLF001
    assert len(state.observation_tensor(0)) == state.get_game().observation_tensor_shape()[0]


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


def test_molthar_state_activation_payment_choice() -> None:
    """With several payable pearl sets, the player picks which cards to hand over."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index("bilbo_odd")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1, 7: 1})  # noqa: SLF001
    state._pearl_display = [2, 2, 4, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    state.apply_action(7)
    # Canonical ordering gives each payment set only one path through the tree.
    assert state.legal_actions() == [Action.PAY_HAND_1, Action.PAY_HAND_3]
    assert state.action_to_string(0, Action.PAY_HAND_1) == "PayHand:1"
    state.apply_action(Action.PAY_HAND_1)
    assert state.legal_actions() == [Action.PAY_HAND_3, Action.PAY_HAND_5]
    state.apply_action(Action.PAY_HAND_5)
    # The only remaining plan is 1, 5, 7, so its remainder is automatic.
    assert state._hands[0] == Counter({3: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({1: 1, 5: 1, 7: 1})  # noqa: SLF001
    assert state.scores[0] == CHARACTERS[card].points
    assert state._actions_left == 2  # noqa: SLF001


def test_molthar_state_activation_pays_a_forced_remainder() -> None:
    """A payment with no choice left is handed over without asking the player."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    card = _character_index("gnome")
    state._portals[0] = [card]  # noqa: SLF001
    # Greedy clause matching would spend the sixes on the pair and refuse this.
    state._hands[0] = Counter({6: 2, 7: 2})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert 7 in state.legal_actions()
    state.apply_action(7)
    assert state._pending_decision is None  # noqa: SLF001
    assert state._hands[0].total() == 0  # noqa: SLF001
    assert state.scores[0] == CHARACTERS[card].points


def test_molthar_state_virtual_pearl_enables_activation_and_is_reusable() -> None:
    """An activated provider contributes a reusable virtual pearl."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    barbarian = _character_index("barbarian_1")
    goblin = _character_index("goblin")
    state._portals[0] = [barbarian]  # noqa: SLF001
    state._hands[0] = Counter({1: 3})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [goblin, goblin]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state._activated_characters[0] == [barbarian]  # noqa: SLF001
    assert state._hands[0] == Counter({1: 1})  # noqa: SLF001

    state._portals[0] = [goblin]  # noqa: SLF001
    state.apply_action(Action.ACTIVATE_0)
    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._pearl_discard == Counter({1: 3})  # noqa: SLF001
    assert state._activated_characters[0] == [barbarian, goblin]  # noqa: SLF001

    state._portals[0] = [goblin]  # noqa: SLF001
    state._hands[0] = Counter({1: 1})  # noqa: SLF001
    state.apply_action(Action.ACTIVATE_0)
    assert state._pearl_discard == Counter({1: 4})  # noqa: SLF001
    assert state._activated_characters[0] == [barbarian, goblin, goblin]  # noqa: SLF001


def test_molthar_state_fuchur_is_one_resource_per_activation() -> None:
    """Fuchur may represent any value but cannot fill two pearl positions at once."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    fuchur = _character_index("fuchur")
    barbarian = _character_index("barbarian_1")
    state._activated_characters[0] = [fuchur]  # noqa: SLF001
    state._portals[0] = [barbarian]  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [barbarian, barbarian]  # noqa: SLF001

    assert Action.ACTIVATE_0 not in state.legal_actions()
    state._hands[0] = Counter({1: 1})  # noqa: SLF001
    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._pearl_discard == Counter({1: 1})  # noqa: SLF001


@pytest.mark.parametrize(
    ("value", "target_id"),
    [
        (1, "barbarian_1"),
        (2, "barbarian_2"),
        (3, "barbarian_3"),
        (4, "barbarian_4"),
        (5, "barbarian_5"),
        (6, "barbarian_6"),
        (7, "barbarian_7"),
        (8, "hansel_and_gretel"),
    ],
)
def test_molthar_state_fuchur_can_represent_each_value(value: int, target_id: str) -> None:
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    fuchur = _character_index("fuchur")
    target = _character_index(target_id)
    state._activated_characters[0] = [fuchur]  # noqa: SLF001
    state._portals[0] = [target]  # noqa: SLF001
    state._hands[0] = Counter({value: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [target, target]  # noqa: SLF001

    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._pearl_discard == Counter({value: 1})  # noqa: SLF001


def test_molthar_state_two_phoenixes_supply_two_virtual_pearls() -> None:
    """Separate activated copies each provide their own virtual pearl."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    phoenix = _character_index("phoenix")
    hansel_and_gretel = _character_index("hansel_and_gretel")
    state._activated_characters[0] = [phoenix, phoenix]  # noqa: SLF001
    state._portals[0] = [hansel_and_gretel]  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [phoenix, phoenix]  # noqa: SLF001

    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._pearl_discard == Counter()  # noqa: SLF001
    assert state._activated_characters[0] == [phoenix, phoenix, hansel_and_gretel]  # noqa: SLF001


def test_molthar_state_payment_actions_distinguish_virtual_sources() -> None:
    """A payment decision exposes stable actions for hand, Barbarian, and Fuchur."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    barbarian = _character_index("barbarian_1")
    fuchur = _character_index("fuchur")
    goblin = _character_index("goblin")
    state._activated_characters[0] = [barbarian, fuchur]  # noqa: SLF001
    state._portals[0] = [goblin]  # noqa: SLF001
    state._hands[0] = Counter({1: 1})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [goblin, goblin]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state.legal_actions() == [Action.PAY_HAND_1, Action.USE_BARBARIAN_1]
    state.apply_action(Action.PAY_HAND_1)
    assert state.legal_actions() == [Action.USE_BARBARIAN_1, Action.USE_FUCHUR_AS_1]
    assert state.action_to_string(0, Action.USE_FUCHUR_AS_1) == "UseVirtual:fuchurAs1"
    assert "paid=['PayHand:1']" in state.observation_string(0)

    state.apply_action(Action.USE_FUCHUR_AS_1)
    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._pearl_discard == Counter({1: 1})  # noqa: SLF001


def test_molthar_state_observation_tracks_selected_virtual_source() -> None:
    """Pending-payment observations identify the virtual provider already selected."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    barbarian_one = _character_index("barbarian_1")
    barbarian_three = _character_index("barbarian_3")
    fuchur = _character_index("fuchur")
    bilbo_odd = _character_index("bilbo_odd")
    state._activated_characters[0] = [barbarian_one, barbarian_three, fuchur]  # noqa: SLF001
    state._portals[0] = [bilbo_odd]  # noqa: SLF001
    state._pearl_display = [2, 4, 6, 8]  # noqa: SLF001
    state._character_display = [bilbo_odd, bilbo_odd]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    state.apply_action(Action.USE_BARBARIAN_1)
    observation = state.observation_tensor(0)
    tail = 1 + _NUM_PLAYERS + 8 + len(RedChoice)
    virtual_sources = observation[-(len(CHARACTERS) + tail) : -tail]
    assert virtual_sources[barbarian_one] == 1.0
    assert sum(virtual_sources) == 1.0
    assert "paid=['UseVirtual:barbarian_1As1']" in state.observation_string(0)


def test_molthar_state_peter_pan_allows_one_to_pay_as_eight() -> None:
    """Peter Pan adds an effective 8 interpretation to every physical 1."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    peter_pan = _character_index("peter_pan")
    hansel_and_gretel = _character_index("hansel_and_gretel")
    state._portals[0] = [hansel_and_gretel]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 8: 1})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [peter_pan, peter_pan]  # noqa: SLF001

    assert Action.ACTIVATE_0 not in state.legal_actions()
    state._activated_characters[0] = [peter_pan]  # noqa: SLF001
    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._pearl_discard == Counter({1: 1, 8: 1})  # noqa: SLF001


@pytest.mark.parametrize(
    ("value", "target_id"),
    [
        (1, "barbarian_1"),
        (2, "barbarian_2"),
        (3, "barbarian_3"),
        (4, "barbarian_4"),
        (5, "barbarian_5"),
        (6, "barbarian_6"),
        (7, "barbarian_7"),
        (8, "hansel_and_gretel"),
    ],
)
def test_molthar_state_rumpelstiltskin_can_reinterpret_three(
    value: int,
    target_id: str,
) -> None:
    """Rumpelstiltskin lets each physical 3 represent every pearl value."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    rumpelstiltskin = _character_index("rumpelstiltskin")
    target = _character_index(target_id)
    state._activated_characters[0] = [rumpelstiltskin]  # noqa: SLF001
    state._portals[0] = [target]  # noqa: SLF001
    state._hands[0] = Counter((3, value))  # noqa: SLF001
    state._pearl_display = [1, 2, 4, 5]  # noqa: SLF001
    state._character_display = [target, target]  # noqa: SLF001

    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._pearl_discard == Counter((3, value))  # noqa: SLF001


def test_molthar_state_rumpelstiltskin_can_reinterpret_each_three() -> None:
    """Every physical 3 receives its own mutually exclusive interpretations."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    rumpelstiltskin = _character_index("rumpelstiltskin")
    dwarf = _character_index("dwarf")
    state._activated_characters[0] = [rumpelstiltskin]  # noqa: SLF001
    state._portals[0] = [dwarf]  # noqa: SLF001
    state._hands[0] = Counter({3: 4})  # noqa: SLF001
    state._pearl_display = [1, 2, 4, 5]  # noqa: SLF001
    state._character_display = [dwarf, dwarf]  # noqa: SLF001

    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._hands[0] == Counter()  # noqa: SLF001
    assert state._pearl_discard == Counter({3: 4})  # noqa: SLF001


def test_molthar_state_payment_action_selects_rumpelstiltskin_interpretation() -> None:
    """The player can choose a stable action for a transformed physical pearl."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    rumpelstiltskin = _character_index("rumpelstiltskin")
    goblin = _character_index("goblin")
    state._activated_characters[0] = [rumpelstiltskin]  # noqa: SLF001
    state._portals[0] = [goblin]  # noqa: SLF001
    state._hands[0] = Counter({3: 1, 4: 2})  # noqa: SLF001
    state._pearl_display = [1, 2, 5, 6]  # noqa: SLF001
    state._character_display = [goblin, goblin]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    transformed = Action.PAY_HAND_3_AS_4_RUMPELSTILTSKIN
    assert state.legal_actions() == [Action.PAY_HAND_4, transformed]
    assert state.action_to_string(0, transformed) == "PayHand:3As4:rumpelstiltskin"
    state.apply_action(transformed)
    assert state._hands[0] == Counter({4: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({3: 1, 4: 1})  # noqa: SLF001


def test_molthar_state_payment_action_selects_peter_pan_interpretation() -> None:
    """Peter Pan's substitution remains distinct from paying a printed 8."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()
    peter_pan = _character_index("peter_pan")
    hansel_and_gretel = _character_index("hansel_and_gretel")
    state._activated_characters[0] = [peter_pan]  # noqa: SLF001
    state._portals[0] = [hansel_and_gretel]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 8: 2})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 5]  # noqa: SLF001
    state._character_display = [peter_pan, peter_pan]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    transformed = Action.PAY_HAND_1_AS_8_PETER_PAN
    assert state.legal_actions() == [Action.PAY_HAND_8, transformed]
    assert state.action_to_string(0, transformed) == "PayHand:1As8:peter_pan"
    state.apply_action(transformed)
    assert state._hands[0] == Counter({8: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({1: 1, 8: 1})  # noqa: SLF001
