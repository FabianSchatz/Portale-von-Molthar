"""Tests for the simplified *Portale von Molthar* OpenSpiel game."""

from collections import Counter

import numpy as np
import pyspiel
import pytest

from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.decisions import PaymentDecision, RedChoice
from portale_von_molthar.molthar import (
    _HAND_LIMIT,
    _PEARL_COPIES,
    _PEARL_VALUES,
    Action,
)

_TOTAL_PEARLS = len(_PEARL_VALUES) * _PEARL_COPIES


def _character_index(card_id: str) -> int:
    """Return the `CHARACTERS` index of the card with `card_id`."""
    return next(index for index, character in enumerate(CHARACTERS) if character.id == card_id)


def _started(state: pyspiel.State) -> pyspiel.State:
    """Resolve the starting-player chance node of a fresh `state` so that player 0 starts."""
    state.apply_action(0)
    return state


def _resolve_chance(state: pyspiel.State) -> None:
    """Apply the first chance outcome until a player is to move."""
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])


def _play_random_game(seed: int, *, auto_discard: bool = False, players: int = 2) -> pyspiel.State:
    """Play one game with uniformly random actions and return the terminal state."""
    rng = np.random.default_rng(seed)
    name = f"python_portale_von_molthar(auto_discard={str(auto_discard).lower()},players={players})"
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
    # publicly known cards are a lower bound of each hand
    for known, hand in zip(state._known_pearls, state._hands, strict=True):  # noqa: SLF001
        assert known <= hand


@pytest.mark.parametrize("players", [2, 3, 5])
@pytest.mark.parametrize("auto_discard", [False, True])
@pytest.mark.parametrize("seed", range(10))
def test_molthar_game_random_playthrough(seed: int, *, auto_discard: bool, players: int) -> None:
    state = _play_random_game(seed, auto_discard=auto_discard, players=players)
    assert state.is_terminal()
    assert len(state.returns()) == players
    assert sum(state.returns()) == pytest.approx(0.0)
    # Some random players fill their portals with cards they cannot activate.
    max_nodes = state.get_game().max_game_length()
    assert max(state.scores) >= 12 or state._nodes == max_nodes  # noqa: SLF001
    # Scoring ends at a turn boundary; the node cap can interrupt a turn.
    if max(state.scores) >= 12:
        for player, hand in enumerate(state._hands):  # noqa: SLF001
            assert hand.total() <= state._hand_limit(player)  # noqa: SLF001


def test_molthar_game_registration() -> None:
    game = pyspiel.load_game("python_portale_von_molthar")
    assert game.num_players() == 2
    assert game.num_distinct_actions() == 102
    state = game.new_initial_state()
    assert state.is_chance_node()
    assert len(state.observation_tensor(0)) == game.observation_tensor_shape()[0]


@pytest.mark.parametrize("players", [2, 3, 5])
def test_molthar_state_chance_outcomes_pick_the_starting_player(players: int) -> None:
    """The first chance node picks the starting player uniformly."""
    state = pyspiel.load_game(f"python_portale_von_molthar(players={players})").new_initial_state()
    assert state.chance_outcomes() == [(player, 1.0 / players) for player in range(players)]
    starter = players - 1
    assert state.action_to_string(pyspiel.PlayerId.CHANCE, starter) == f"StartingPlayer:p{starter}"
    state.apply_action(starter)
    _resolve_chance(state)
    assert state.current_player() == starter


@pytest.mark.parametrize("players", [2, 3, 4, 5])
def test_molthar_game_players_parameter(players: int) -> None:
    game = pyspiel.load_game(f"python_portale_von_molthar(players={players})")
    assert game.num_players() == players
    state = _started(game.new_initial_state())
    assert len(state._hands) == players  # noqa: SLF001
    for player in range(players):
        assert len(state.observation_tensor(player)) == game.observation_tensor_shape()[0]


@pytest.mark.parametrize("players", [1, 6])
def test_molthar_game_players_parameter_out_of_range(players: int) -> None:
    with pytest.raises(ValueError, match="players"):
        pyspiel.load_game(f"python_portale_von_molthar(players={players})")


@pytest.mark.parametrize(
    ("scores", "diamonds", "expected"),
    [
        ([12, 5], [0, 0], [1.0, -1.0]),
        ([7, 7], [0, 0], [0.0, 0.0]),
        ([12, 3, 5], [0, 0, 0], [1.0, -0.5, -0.5]),
        ([12, 12, 5, 1], [0, 0, 0, 0], [0.5, 0.5, -0.5, -0.5]),
        ([4, 4, 4], [0, 0, 0], [0.0, 0.0, 0.0]),
        ([12, 12], [1, 2], [-1.0, 1.0]),
        ([12, 12, 5], [3, 3, 9], [0.5, 0.5, -1.0]),
        ([12, 12, 12, 5], [1, 2, 2, 0], [-0.5, 0.5, 0.5, -0.5]),
    ],
)
def test_molthar_state_returns(
    scores: list[int],
    diamonds: list[int],
    expected: list[float],
) -> None:
    """The best (score, diamonds) rank shares +1 and everybody else shares -1."""
    game = pyspiel.load_game(f"python_portale_von_molthar(players={len(scores)})")
    state = _started(game.new_initial_state())
    state._scores = scores  # noqa: SLF001
    state._diamonds = diamonds  # noqa: SLF001
    state._game_over = True  # noqa: SLF001
    assert state.returns() == pytest.approx(expected)


@pytest.mark.parametrize("players", [2, 3, 5])
def test_molthar_state_end_turn_final_turns(players: int) -> None:
    """After the finisher's turn, the others play twice and the finisher once more."""
    game = pyspiel.load_game(f"python_portale_von_molthar(players={players})")
    state = _started(game.new_initial_state())
    finisher = 1
    state._cur_player = finisher  # noqa: SLF001
    state._scores[finisher] = 12  # noqa: SLF001

    state._end_turn()  # noqa: SLF001
    turns = []
    while not state.is_terminal():
        turns.append(state._cur_player)  # noqa: SLF001
        state._end_turn()  # noqa: SLF001

    assert turns == [(finisher + offset) % players for offset in range(1, 2 * players)]
    assert turns.count(finisher) == 1
    assert state._cur_player == finisher  # noqa: SLF001


def test_molthar_state_end_turn_ignores_later_finishers() -> None:
    """Only the first player to reach the target starts the final turns."""
    game = pyspiel.load_game("python_portale_von_molthar(players=3)")
    state = _started(game.new_initial_state())
    state._scores[0] = 12  # noqa: SLF001
    state._end_turn()  # noqa: SLF001
    assert state._final_turns == 5  # noqa: SLF001
    state._scores[1] = 12  # noqa: SLF001
    state._end_turn()  # noqa: SLF001
    assert state._final_turns == 4  # noqa: SLF001
    assert "final_turns=4" in state.observation_string(0)


def test_molthar_state_previous_neighbor_can_activate_irrlicht() -> None:
    """With three players, Irrlicht is also payable from the previous player's portal."""
    game = pyspiel.load_game("python_portale_von_molthar(players=3)")
    state = _started(game.new_initial_state())
    card = _character_index("irrlicht_1")
    state._portals[1] = [card]  # noqa: SLF001
    state._portals[2] = [card]  # noqa: SLF001
    state._hands[0] = Counter({3: 3})  # noqa: SLF001
    state._pearl_display = [1, 2, 7, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    legal = state.legal_actions()
    assert Action.ACTIVATE_NEIGHBOR_0 in legal
    assert Action.ACTIVATE_PREVIOUS_NEIGHBOR_0 in legal
    label = state.action_to_string(0, Action.ACTIVATE_PREVIOUS_NEIGHBOR_0)
    assert label == "ActivatePreviousNeighbor:irrlicht_1"
    state.apply_action(Action.ACTIVATE_PREVIOUS_NEIGHBOR_0)

    assert state._portals[2] == []  # noqa: SLF001
    assert state._portals[1] == [card]  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001
    assert state.scores == [3, 0, 0]


def test_molthar_state_two_players_have_no_previous_neighbor_action() -> None:
    """With two players both neighbors are the same, so only one action is offered."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
    card = _character_index("irrlicht_1")
    state._portals[1] = [card]  # noqa: SLF001
    state._hands[0] = Counter({3: 3})  # noqa: SLF001
    state._pearl_display = [1, 2, 7, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    legal = state.legal_actions()
    assert Action.ACTIVATE_NEIGHBOR_0 in legal
    assert Action.ACTIVATE_PREVIOUS_NEIGHBOR_0 not in legal


def test_molthar_state_activation_scores() -> None:
    """Activating a character pays its pearls, awards points, and awards diamonds."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
    card = _character_index("bilbo_odd")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
    card = _character_index("irrlicht_1")
    state._portals[1] = [card]  # noqa: SLF001
    state._hands[0] = Counter({3: 3, 6: 3})  # noqa: SLF001
    state._pearl_display = [1, 2, 7, 8]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_NEIGHBOR_0)

    decision = state._pending_step  # noqa: SLF001
    assert decision is not None
    assert decision.actor == 0
    assert decision.target_owner == 1
    assert decision.target_slot == 0
    assert state.legal_actions() == [Action.PAY_HAND_3, Action.PAY_HAND_6]
    assert "payment_target=p1:0" in state.observation_string(0)

    state.apply_action(Action.PAY_HAND_3)

    assert state._pending_step is None  # noqa: SLF001
    assert state._hands[0] == Counter({6: 3})  # noqa: SLF001
    assert state._portals[1] == []  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001


def test_molthar_state_neighbor_actions_distinguish_portal_slots() -> None:
    """Only the slot containing Irrlicht receives a neighboring activation action."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
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
        ("golem_1", Counter({2: 1, 4: 1, 6: 1, 8: 1})),
        ("golem_2", Counter({1: 1, 3: 1, 5: 1, 7: 1})),
    ],
)
def test_molthar_state_golem_grants_three_actions(
    card_id: str,
    hand: Counter[int],
) -> None:
    """Activating a Golem immediately adds three actions to the current turn."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
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
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
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
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
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
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
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
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
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
    state = _started(game.new_initial_state())
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._hands[0] = Counter({5: 1, 6: 1, 7: 2, 8: 1})  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001
    state.apply_action(0)  # take the pearl of value 1, giving a hand of six
    assert state.is_chance_node()  # the display is refilled before the discard
    state.apply_action(2)
    assert state.current_player() == 0
    assert state.legal_actions() == [
        Action.DISCARD_1,
        Action.DISCARD_5,
        Action.DISCARD_6,
        Action.DISCARD_7,
        Action.DISCARD_8,
    ]
    assert state.action_to_string(0, Action.DISCARD_8) == "Discard:8"
    state.apply_action(Action.DISCARD_8)
    assert state._hands[0] == Counter({1: 1, 5: 1, 6: 1, 7: 2})  # noqa: SLF001
    assert state._pearl_discard[8] == 1  # noqa: SLF001
    # The hand is at the limit again, so the turn passes on.
    assert state._cur_player == 1  # noqa: SLF001
    assert state._actions_left == 3  # noqa: SLF001


def test_molthar_state_auto_discard_trims_the_hand() -> None:
    """With `auto_discard`, the hand is trimmed by the heuristic and never by an action."""
    game = pyspiel.load_game("python_portale_von_molthar(auto_discard=true)")
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
    card = _character_index("captain_hook")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({2: 3})  # noqa: SLF001
    state._pearl_display = [1, 3, 4, 5]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert Action.ACTIVATE_0 not in state.legal_actions()
    state._diamonds[0] = 1  # noqa: SLF001
    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._diamonds[0] == 0  # noqa: SLF001
    assert state.scores[0] == CHARACTERS[card].points


def test_molthar_state_activation_payment_choice() -> None:
    """With several payable pearl sets, the player picks which cards to hand over."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
    card = _character_index("bilbo_odd")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1, 7: 1})  # noqa: SLF001
    state._pearl_display = [2, 2, 4, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    state.apply_action(Action.ACTIVATE_0)
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
    state = _started(game.new_initial_state())
    card = _character_index("gnome")
    state._portals[0] = [card]  # noqa: SLF001
    # Greedy clause matching would spend the sixes on the pair and refuse this.
    state._hands[0] = Counter({6: 2, 7: 2})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    assert Action.ACTIVATE_0 in state.legal_actions()
    state.apply_action(Action.ACTIVATE_0)
    assert state._pending_step is None  # noqa: SLF001
    assert state._hands[0].total() == 0  # noqa: SLF001
    assert state.scores[0] == CHARACTERS[card].points


def test_molthar_state_virtual_pearl_enables_activation_and_is_reusable() -> None:
    """An activated provider contributes a reusable virtual pearl."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    tail = 1 + game.num_players() + 8 + len(RedChoice)
    virtual_sources = observation[-(len(CHARACTERS) + tail) : -tail]
    assert virtual_sources[barbarian_one] == 1.0
    assert sum(virtual_sources) == 1.0
    assert "paid=['UseVirtual:barbarian_1As1']" in state.observation_string(0)


def test_molthar_state_peter_pan_allows_one_to_pay_as_eight() -> None:
    """Peter Pan adds an effective 8 interpretation to every physical 1."""
    game = pyspiel.load_game("python_portale_von_molthar")
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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
    state = _started(game.new_initial_state())
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


def test_molthar_state_diamond_raises_paid_pearl() -> None:
    """One diamond raises a paid physical pearl by one (RULES.md section 8.1)."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    state._portals[0] = [goblin]  # noqa: SLF001
    state._hands[0] = Counter({3: 1, 4: 2})  # noqa: SLF001
    state._pearl_display = [1, 2, 5, 6]  # noqa: SLF001
    state._character_display = [goblin, goblin]  # noqa: SLF001
    state._diamonds[0] = 1  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    raised = Action.PAY_HAND_3_PLUS_DIAMOND
    assert state.legal_actions() == [Action.PAY_HAND_4, raised]
    assert state.action_to_string(0, raised) == "PayHand:3As4:diamond"
    state.apply_action(raised)
    assert state._hands[0] == Counter({4: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({3: 1, 4: 1})  # noqa: SLF001
    assert state._diamonds[0] == 0  # noqa: SLF001


@pytest.mark.parametrize(
    ("activated_ids", "value", "expected"),
    [
        ((), 3, {4}),
        ((), 8, set()),
        (("amazon",), 8, {7}),
        (("amazon",), 1, {2}),
        (("amazon",), 5, {4, 6}),
        (("rumpelstiltskin",), 3, set()),
    ],
)
def test_molthar_state_diamond_options(
    activated_ids: tuple[str, ...],
    value: int,
    expected: set[int],
) -> None:
    """Diamonds stay within 1-8, Amazon adds -1, and free reinterpretations skip diamonds."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index(card) for card in activated_ids]  # noqa: SLF001
    state._hands[0] = Counter({value: 1})  # noqa: SLF001
    state._diamonds[0] = 1  # noqa: SLF001
    (group,) = state._activation_resources(0)  # noqa: SLF001
    assert {payment.effective_value for payment in group if payment.diamonds_spent} == expected


def test_molthar_state_amazon_lowers_paid_pearl() -> None:
    """With Amazon, a diamond may lower a paid pearl by one instead."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    barbarian = _character_index("barbarian_2")
    state._activated_characters[0] = [_character_index("amazon")]  # noqa: SLF001
    state._portals[0] = [barbarian]  # noqa: SLF001
    state._hands[0] = Counter({2: 2, 3: 1})  # noqa: SLF001
    state._pearl_display = [1, 4, 5, 6]  # noqa: SLF001
    state._character_display = [barbarian, barbarian]  # noqa: SLF001
    state._diamonds[0] = 1  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)
    assert state.legal_actions() == [Action.PAY_HAND_2]
    state.apply_action(Action.PAY_HAND_2)
    lowered = Action.PAY_HAND_3_MINUS_DIAMOND_AMAZON
    assert state.legal_actions() == [Action.PAY_HAND_2, lowered]
    assert state.action_to_string(0, lowered) == "PayHand:3As2:amazon:diamond"
    state.apply_action(lowered)
    assert state._hands[0] == Counter({2: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({2: 1, 3: 1})  # noqa: SLF001
    assert state._diamonds[0] == 0  # noqa: SLF001


def test_molthar_state_snow_white_converts_twos_for_free() -> None:
    """Snow White converts any number of 2s into diamonds without spending actions."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index("snow_white")]  # noqa: SLF001
    state._hands[0] = Counter({2: 2, 5: 1})  # noqa: SLF001
    state._pearl_display = [1, 3, 4, 6]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    convert = Action.CONVERT_2_TO_DIAMOND_SNOW_WHITE

    for converted in (1, 2):
        assert convert in state.legal_actions()
        assert state.action_to_string(0, convert) == "ConvertToDiamond:2:snow_white"
        state.apply_action(convert)
        assert state._diamonds[0] == converted  # noqa: SLF001
        assert state._actions_left == 3  # noqa: SLF001
    assert convert not in state.legal_actions()
    assert state._hands[0] == Counter({5: 1})  # noqa: SLF001
    assert state._pearl_discard == Counter({2: 2})  # noqa: SLF001


@pytest.mark.parametrize("monkeys", [1, 2, 3])
def test_molthar_state_flying_monkeys_stack_the_hand_limit(monkeys: int) -> None:
    """Every activated Flying Monkey raises the end-of-turn hand limit by one."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index("flying_monkey")] * monkeys  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001
    state._hands[0] = Counter({5: _HAND_LIMIT + monkeys + 1})  # noqa: SLF001
    assert state._hand_limit(0) == _HAND_LIMIT + monkeys  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    _resolve_chance(state)
    assert state.legal_actions() == [Action.DISCARD_5]
    state.apply_action(Action.DISCARD_5)
    assert state._cur_player == 1  # noqa: SLF001
    assert state._hands[0].total() == _HAND_LIMIT + monkeys  # noqa: SLF001


def test_molthar_state_little_red_riding_hood_adds_an_action_on_activation() -> None:
    """Activating Little Red Riding Hood also adds an action to the current turn."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    card = _character_index("little_red_riding_hood")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({4: 1, 5: 1, 6: 1, 7: 1, 8: 1})  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 5]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001

    state.apply_action(Action.ACTIVATE_0)

    assert state._actions_left == 3  # noqa: SLF001
    assert state._activated_characters[0] == [card]  # noqa: SLF001


def test_molthar_state_little_red_riding_hood_adds_an_action_every_turn() -> None:
    """Little Red Riding Hood's owner starts each turn with one extra action."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[1] = [_character_index("little_red_riding_hood")]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    assert state._cur_player == 1  # noqa: SLF001
    assert state._actions_left == 4  # noqa: SLF001
    _resolve_chance(state)
    for _ in range(4):
        state.apply_action(Action.REFRESH_PEARLS)
        _resolve_chance(state)
    assert state._cur_player == 0  # noqa: SLF001
    assert state._actions_left == 3  # noqa: SLF001
    assert len(state.observation_tensor(1)) == state.get_game().observation_tensor_shape()[0]


@pytest.mark.parametrize("redraw", [False, True])
def test_molthar_state_reaper_may_redraw_the_hand(*, redraw: bool) -> None:
    """After the final action, Reaper may swap the whole hand for fresh pearls."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index("reaper")]  # noqa: SLF001
    state._hands[0] = Counter({1: 2, 5: 1})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 6]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    _resolve_chance(state)  # the display is refilled before the after-turn choice
    assert state.current_player() == 0
    assert state.legal_actions() == [Action.REAPER_KEEP_HAND, Action.REAPER_REDRAW_HAND]
    choice = Action.REAPER_REDRAW_HAND if redraw else Action.REAPER_KEEP_HAND
    state.apply_action(choice)
    if redraw:
        assert state._hands[0] == Counter()  # noqa: SLF001
        assert state._pearl_discard[1] == 2  # noqa: SLF001
        assert state._pearl_discard[5] == 1  # noqa: SLF001
        for _ in range(3):
            assert state.is_chance_node()
            state.apply_action(state.chance_outcomes()[0][0])
    else:
        assert not state.is_chance_node()
    assert state._hands[0].total() == 3  # noqa: SLF001
    assert state._cur_player == 1  # noqa: SLF001
    assert state._actions_left == 3  # noqa: SLF001


def test_molthar_state_reaper_redraw_reshuffles_an_empty_deck() -> None:
    """The redraw step lets the discard pile, including the old hand, be reshuffled."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index("reaper")]  # noqa: SLF001
    state._hands[0] = Counter({1: 2, 5: 1})  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 6]  # noqa: SLF001
    state._pearl_deck = Counter()  # noqa: SLF001
    state._pearl_discard = Counter({7: 5})  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    # The pending choice blocks the reshuffle, so the empty display waits.
    assert state._pearl_deck == Counter()  # noqa: SLF001
    assert state.legal_actions() == [Action.REAPER_KEEP_HAND, Action.REAPER_REDRAW_HAND]
    state.apply_action(Action.REAPER_REDRAW_HAND)
    assert state._pearl_deck.total() == 12  # noqa: SLF001
    _resolve_chance(state)
    assert len(state._pearl_display) == 4  # noqa: SLF001
    assert state._hands[0].total() == 3  # noqa: SLF001
    assert state._pending_step is None  # noqa: SLF001
    assert state._cur_player == 1  # noqa: SLF001


def test_molthar_state_reaper_is_skipped_with_an_empty_hand() -> None:
    """Reaper offers nothing when there is no hand to redraw."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._activated_characters[0] = [_character_index("reaper")]  # noqa: SLF001
    state._pearl_display = [2, 3, 4, 6]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    assert state._pending_step is None  # noqa: SLF001
    assert state._cur_player == 1  # noqa: SLF001


def test_molthar_state_mad_hatter_swaps_before_the_turn() -> None:
    """Before acting, Mad Hatter's owner may swap a portal and a display character."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    fluffy = _character_index("fluffy")
    lion = _character_index("lion")
    state._activated_characters[1] = [_character_index("mad_hatter")]  # noqa: SLF001
    state._portals[1] = [goblin]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [fluffy, lion]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    _resolve_chance(state)
    assert state.current_player() == 1
    swap = Action.MAD_HATTER_SWAP_0_1
    assert state.legal_actions() == [Action.MAD_HATTER_SKIP, Action.MAD_HATTER_SWAP_0_0, swap]
    assert state.action_to_string(1, swap) == "MadHatterSwap:goblin<->lion"
    assert "blue_choice=swap_portal" in state.observation_string(0)
    state.apply_action(swap)
    assert state._portals[1] == [lion]  # noqa: SLF001
    assert state._character_display == [fluffy, goblin]  # noqa: SLF001
    assert state._actions_left == 3  # noqa: SLF001
    assert state._pending_step is None  # noqa: SLF001


def test_molthar_state_dumbledore_peeks_at_the_next_character() -> None:
    """Dumbledore privately sees the top character, which then refills the display."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    lion = _character_index("lion")
    state._activated_characters[1] = [_character_index("dumbledore")]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, lion]  # noqa: SLF001
    state._actions_left = 1  # noqa: SLF001

    state.apply_action(Action.REFRESH_PEARLS)
    for _ in range(4):
        state.apply_action(state.chance_outcomes()[0][0])
    assert state.is_chance_node()
    assert state.action_to_string(pyspiel.PlayerId.CHANCE, goblin) == "PeekCharacter:goblin"
    state.apply_action(goblin)
    assert state.current_player() == 1
    assert "peeked_character=goblin" in state.observation_string(1)
    assert "peeked_character=None" in state.observation_string(0)

    state.apply_action(Action.TAKE_CHARACTER_0)
    assert state.chance_outcomes() == [(goblin, 1.0)]
    state.apply_action(goblin)
    assert state._character_display == [lion, goblin]  # noqa: SLF001
    assert "peeked_character=None" in state.observation_string(1)


def test_molthar_state_take_top_pearl() -> None:
    """Taking the top pearl blind is a chance draw into the hand that costs one action."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._pearl_deck = Counter({7: 2, 8: 1})  # noqa: SLF001
    assert Action.TAKE_PEARL_DECK in state.legal_actions()
    assert state.action_to_string(0, Action.TAKE_PEARL_DECK) == "TakePearlDeck"

    state.apply_action(Action.TAKE_PEARL_DECK)
    assert state.is_chance_node()
    assert state.chance_outcomes() == [(7, 2 / 3), (8, 1 / 3)]
    assert state.action_to_string(pyspiel.PlayerId.CHANCE, 7) == "TakeTopPearl:7"
    state.apply_action(7)
    assert state._hands[0] == Counter({7: 1})  # noqa: SLF001
    assert state._pearl_deck == Counter({7: 1, 8: 1})  # noqa: SLF001
    assert state._pearl_display == [1, 2, 3, 4]  # noqa: SLF001
    assert state._actions_left == 2  # noqa: SLF001
    assert state.current_player() == 0


def test_molthar_state_take_top_character() -> None:
    """Taking the top character blind puts the drawn card on the portal."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    lion = _character_index("lion")
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, lion]  # noqa: SLF001
    state._character_deck = Counter({goblin: 1, lion: 1})  # noqa: SLF001
    assert Action.TAKE_CHARACTER_DECK in state.legal_actions()

    state.apply_action(Action.TAKE_CHARACTER_DECK)
    assert state.chance_outcomes() == sorted([(goblin, 0.5), (lion, 0.5)])
    label = state.action_to_string(pyspiel.PlayerId.CHANCE, goblin)
    assert label == "TakeTopCharacter:goblin"
    state.apply_action(goblin)
    assert state._portals[0] == [goblin]  # noqa: SLF001
    assert state._character_display == [lion, lion]  # noqa: SLF001
    assert state._character_deck == Counter({lion: 1})  # noqa: SLF001
    assert state._actions_left == 2  # noqa: SLF001


def test_molthar_state_deck_takes_need_cards() -> None:
    """Blind takes are not offered from an empty draw pile."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [0, 0]  # noqa: SLF001
    state._pearl_deck = Counter()  # noqa: SLF001
    state._character_deck = Counter()  # noqa: SLF001
    legal = state.legal_actions()
    assert Action.TAKE_PEARL_DECK not in legal
    assert Action.TAKE_CHARACTER_DECK not in legal


def test_molthar_state_full_portal_offers_replacements() -> None:
    """A full portal offers every portal-slot/source replacement instead of plain takes."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    fluffy = _character_index("fluffy")
    lion = _character_index("lion")
    state._portals[0] = [goblin, fluffy]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, lion]  # noqa: SLF001
    legal = state.legal_actions()
    assert not {
        Action.TAKE_CHARACTER_0,
        Action.TAKE_CHARACTER_1,
        Action.TAKE_CHARACTER_DECK,
    } & set(legal)
    replacements = range(Action.REPLACE_PORTAL_0_0, Action.REPLACE_PORTAL_1_DECK + 1)
    assert set(replacements) <= set(legal)
    label = state.action_to_string(0, Action.REPLACE_PORTAL_1_0)
    assert label == "ReplaceCharacter:fluffy->lion"
    label = state.action_to_string(0, Action.REPLACE_PORTAL_0_DECK)
    assert label == "ReplaceCharacter:goblin->deck"


@pytest.mark.parametrize(
    ("action", "from_deck"),
    [
        (Action.REPLACE_PORTAL_0_0, False),
        (Action.REPLACE_PORTAL_0_1, False),
        (Action.REPLACE_PORTAL_0_DECK, True),
    ],
)
def test_molthar_state_replace_portal_discards_the_old_character(
    action: Action,
    *,
    from_deck: bool,
) -> None:
    """Replacing discards the chosen portal character and takes the new one."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    fluffy = _character_index("fluffy")
    lion = _character_index("lion")
    medusa = _character_index("medusa")
    state._portals[0] = [goblin, fluffy]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, medusa]  # noqa: SLF001
    state._character_deck = Counter({goblin: 1})  # noqa: SLF001

    state.apply_action(action)
    assert state._character_discard == Counter({goblin: 1})  # noqa: SLF001
    assert state.is_chance_node()  # a deck draw or the display refill
    state.apply_action(goblin)
    expected = goblin if from_deck else [lion, medusa][action - Action.REPLACE_PORTAL_0_0]
    assert state._portals[0] == [fluffy, expected]  # noqa: SLF001
    assert len(state._character_display) == 2  # noqa: SLF001
    assert state._actions_left == 2  # noqa: SLF001


def test_molthar_state_dumbledore_peek_fixes_the_blind_take() -> None:
    """A blind character take draws the card Dumbledore peeked at."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    goblin = _character_index("goblin")
    lion = _character_index("lion")
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, lion]  # noqa: SLF001
    state._peeked_character = goblin  # noqa: SLF001
    state._peeked_by = 1  # noqa: SLF001

    state.apply_action(Action.TAKE_CHARACTER_DECK)
    assert state.chance_outcomes() == [(goblin, 1.0)]
    state.apply_action(goblin)
    assert state._portals[0] == [goblin]  # noqa: SLF001
    assert state._peeked_character is None  # noqa: SLF001


def test_molthar_state_public_properties() -> None:
    """The read-only properties expose copies of the state with character ids."""
    state = _started(pyspiel.load_game("python_portale_von_molthar(players=3)").new_initial_state())
    goblin = _character_index("goblin")
    lion = _character_index("lion")
    monkey = _character_index("flying_monkey")
    state._hands[1] = Counter({5: 2, 2: 1})  # noqa: SLF001
    state._portals[0] = [goblin]  # noqa: SLF001
    state._activated_characters[2] = [monkey]  # noqa: SLF001
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    state._character_display = [lion, goblin]  # noqa: SLF001
    state._diamonds = [0, 2, 1]  # noqa: SLF001
    state._pearl_discard = Counter({7: 3})  # noqa: SLF001
    state._character_discard = Counter({lion: 2})  # noqa: SLF001

    assert state.hands == [[], [2, 5, 5], []]
    assert state.portals == [["goblin"], [], []]
    assert state.activated_characters == [[], [], ["flying_monkey"]]
    assert state.pearl_display == [1, 2, 3, 4]
    assert state.character_display == ["lion", "goblin"]
    assert state.diamonds == [0, 2, 1]
    assert state.hand_limits == [_HAND_LIMIT, _HAND_LIMIT, _HAND_LIMIT + 1]
    assert state.pearl_deck_size == _TOTAL_PEARLS
    assert state.pearl_discard_size == 3
    assert state.character_discard_size == 2
    assert state.character_deck_size == sum(character.copies for character in CHARACTERS)
    assert state.actions_left == 3
    assert state.final_turns is None
    assert state.peeked_character is None
    assert state.pending_step is None
    state.hands[1].clear()
    state.portals[0].clear()
    assert state.hands[1] == [2, 5, 5]
    assert state.portals[0] == ["goblin"]


def test_molthar_state_peeked_character() -> None:
    """The peeked top character names the player who knows it."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    state._peeked_character = _character_index("lion")  # noqa: SLF001
    state._peeked_by = 1  # noqa: SLF001
    assert state.peeked_character == (1, "lion")


def test_molthar_state_pending_step() -> None:
    """A payment with several plans is visible as the pending step."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    card = _character_index("bilbo_odd")
    state._portals[0] = [card]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1, 7: 1})  # noqa: SLF001
    state._pearl_display = [2, 2, 4, 4]  # noqa: SLF001
    state._character_display = [card, card]  # noqa: SLF001
    state.apply_action(Action.ACTIVATE_0)
    assert isinstance(state.pending_step, PaymentDecision)
    assert state.pending_step.target_slot == 0


def test_molthar_state_observation_tensor_tracks_known_pearls() -> None:
    """Pearls taken face up stay visible to everyone until such a value is discarded."""
    state = _started(pyspiel.load_game("python_portale_von_molthar").new_initial_state())
    _resolve_chance(state)
    hidden = state._hands[0].total()  # noqa: SLF001
    value = state._pearl_display[0]  # noqa: SLF001
    state.apply_action(Action.TAKE_PEARL_0)
    assert state._known_pearls[0] == Counter({value: 1})  # noqa: SLF001
    assert state._hands[0].total() == hidden + 1  # noqa: SLF001
    state._discard(0, value)  # noqa: SLF001
    assert not state._known_pearls[0]  # noqa: SLF001
