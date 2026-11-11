"""Tests for the per-seat game views."""

from collections import Counter

import pyspiel

from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.decisions import RedAbilityDecision, RedChoice
from portale_von_molthar.molthar import Action, MoltharState
from portale_von_molthar.services.views import (
    activation_plans,
    activation_target,
    describe_action,
    player_views,
    table_view,
)

_NAMES = ["Ada", "Ben", "Cy"]


def _character_index(card_id: str) -> int:
    """Return the `CHARACTERS` index of the card with `card_id`."""
    return next(index for index, character in enumerate(CHARACTERS) if character.id == card_id)


def _started(state: pyspiel.State) -> pyspiel.State:
    """Resolve the starting-player chance node of a fresh `state` so that player 0 starts."""
    state.apply_action(0)
    return state


def _state(players: int = 2) -> MoltharState:
    """Return a dealt state with a fixed display, player 0 to move."""
    state = _started(
        pyspiel.load_game(f"python_portale_von_molthar(players={players})").new_initial_state(),
    )
    state._pearl_display = [1, 2, 3, 4]  # noqa: SLF001
    goblin = _character_index("goblin")
    state._character_display = [goblin, _character_index("lion")]  # noqa: SLF001
    return state


def test_player_views_hide_hands() -> None:
    state = _state()
    state._hands[1] = Counter({5: 2, 3: 1})  # noqa: SLF001
    views = player_views(state, _NAMES[:2], [True, False], [None, "hard"])
    assert views[1]["hand_size"] == 3
    assert "hand" not in views[1]
    assert views[1]["connected"] is False
    assert views[1]["bot"] == "hard"


def test_player_views_lobby() -> None:
    views = player_views(None, _NAMES, [True, True, True], [None, None, None])
    assert [view["name"] for view in views] == _NAMES
    assert all(view["points"] == 0 for view in views)


def test_table_view_only_the_mover_gets_options() -> None:
    state = _state()
    state._hands[0] = Counter({7: 1})  # noqa: SLF001
    state._hands[1] = Counter({5: 2})  # noqa: SLF001
    mine = table_view(state, 0, _NAMES[:2])
    theirs = table_view(state, 1, _NAMES[:2])
    assert mine["hand"] == [7]
    assert theirs["hand"] == [5, 5]
    assert mine["prompt"] == {"kind": "turn", "count": 0, "target": None}
    assert theirs["prompt"] is None
    assert not theirs["moves"]
    take = next(move for move in mine["moves"] if move["action"] == Action.TAKE_PEARL_2)
    assert take == {
        "action": Action.TAKE_PEARL_2,
        "kind": "take_pearl",
        "text": "Take pearl 3",
        "slot": 2,
        "replace": None,
    }


def test_table_view_replace_moves_name_both_slots() -> None:
    state = _state()
    goblin = _character_index("goblin")
    state._portals[0] = [goblin, goblin]  # noqa: SLF001
    moves = table_view(state, 0, _NAMES[:2])["moves"]
    replace = next(move for move in moves if move["action"] == Action.REPLACE_PORTAL_1_0)
    assert replace["kind"] == "take_character"
    assert (replace["slot"], replace["replace"]) == (0, 1)
    assert replace["text"] == "Replace Goblin with Goblin"


def test_table_view_activation_lists_every_plan() -> None:
    state = _state()
    state._portals[0] = [_character_index("bilbo_odd")]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1, 7: 1})  # noqa: SLF001
    (activation,) = table_view(state, 0, _NAMES[:2])["activations"]
    assert activation["character"] == "bilbo_odd"
    assert (activation["owner"], activation["slot"]) == (0, 0)
    assert sorted(plan["cards"] for plan in activation["plans"]) == [
        [1, 3, 5],
        [1, 3, 7],
        [1, 5, 7],
        [3, 5, 7],
    ]


def test_table_view_discard_prompt() -> None:
    state = _state()
    state._hands[0] = Counter({2: 7})  # noqa: SLF001
    state._actions_left = 0  # noqa: SLF001
    prompt = table_view(state, 0, _NAMES[:2])["prompt"]
    assert prompt is not None
    assert (prompt["kind"], prompt["count"]) == ("discard", 2)


def test_table_view_steal_targets_the_chosen_hand() -> None:
    state = _state(3)
    state._hands[2] = Counter({4: 1, 6: 1})  # noqa: SLF001
    state._pending_step = RedAbilityDecision(0, RedChoice.STEAL_PEARL, (4, 6), 2)  # noqa: SLF001
    view = table_view(state, 0, _NAMES)
    assert view["prompt"] == {"kind": "steal_pearl", "count": 0, "target": 2}
    texts = [move["text"] for move in view["moves"]]
    assert texts == ["Take pearl 4 from Cy", "Take pearl 6 from Cy"]
    assert table_view(state, 1, _NAMES)["prompt"] is None


def test_activation_target_neighbors() -> None:
    state = _state(3)
    assert activation_target(state, 0, Action.ACTIVATE_1) == (0, 1)
    assert activation_target(state, 0, Action.ACTIVATE_NEIGHBOR_0) == (1, 0)
    assert activation_target(state, 0, Action.ACTIVATE_PREVIOUS_NEIGHBOR_1) == (2, 1)


def test_activation_plans_include_diamond_modifications() -> None:
    state = _state()
    state._portals[0] = [_character_index("hansel_and_gretel")]  # noqa: SLF001
    state._hands[0] = Counter({7: 1, 8: 1})  # noqa: SLF001
    state._diamonds[0] = 1  # noqa: SLF001
    (plan,) = activation_plans(state, 0, Action.ACTIVATE_0)
    assert plan.diamonds_spent == 1
    assert sorted(plan.discarded_values) == [7, 8]


def test_describe_action_steal() -> None:
    state = _state(3)
    state._hands[2] = Counter({4: 1})  # noqa: SLF001
    state._pending_step = RedAbilityDecision(0, RedChoice.STEAL_PEARL, (4,), 2)  # noqa: SLF001
    assert describe_action(state, 0, Action.STEAL_4, _NAMES) == (
        "Take pearl 4 from Cy",
        "took pearl 4 from Cy",
    )


def test_describe_action_turn_actions() -> None:
    state = _state()
    assert describe_action(state, 0, Action.TAKE_PEARL_DECK, _NAMES) == (
        "Take a hidden pearl",
        "took a hidden pearl",
    )
    assert describe_action(state, 0, Action.REFRESH_PEARLS, _NAMES) == (
        "Replace the pearl display",
        "replaced the pearl display",
    )
    assert describe_action(state, 0, Action.TAKE_CHARACTER_1, _NAMES) == ("Take Lion", "took Lion")
