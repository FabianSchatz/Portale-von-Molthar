"""Tests for the multiplayer game service."""

import random
from collections import Counter

import pytest

from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.molthar import Action, MoltharState
from portale_von_molthar.services.game_service import GameError, GameService


def _started(players: int = 2, seed: int = 0) -> tuple[GameService, str]:
    """Return a service with one started game of `players` seats."""
    service = GameService(seed)
    game_id = service.create_game("Ada")["game_id"]
    for index in range(1, players):
        service.join_game(game_id, f"Player {index}")
    service.start_game(game_id, 0)
    return service, game_id


def _state(service: GameService, game_id: str) -> MoltharState:
    """Return the engine state of a started game."""
    state = service._rooms[game_id].state  # noqa: SLF001
    assert state is not None
    return state


def test_create_game() -> None:
    service = GameService(0)
    joined = service.create_game("  Ada ")
    assert joined["seat"] == 0
    view = service.view(joined["game_id"], 0)
    assert view["status"] == "lobby"
    assert view["players"][0]["name"] == "Ada"
    assert view["table"] is None


def test_join_game() -> None:
    service = GameService(0)
    game_id = service.create_game("Ada")["game_id"]
    joined = service.join_game(game_id.lower(), "Ben")
    assert joined["seat"] == 1
    assert service.seat_for(game_id, joined["token"]) == 1


@pytest.mark.parametrize("name", ["", "   ", "x" * 21])
def test_join_game_rejects_bad_names(name: str) -> None:
    service = GameService(0)
    game_id = service.create_game("Ada")["game_id"]
    with pytest.raises(GameError, match="names"):
        service.join_game(game_id, name)


def test_join_game_rejects_full_and_running_games() -> None:
    service = GameService(0)
    game_id = service.create_game("Ada")["game_id"]
    for index in range(4):
        service.join_game(game_id, f"P{index}")
    with pytest.raises(GameError, match="already has 5"):
        service.join_game(game_id, "Late")
    service.start_game(game_id, 0)
    with pytest.raises(GameError, match="started"):
        service.join_game(game_id, "Late")


def test_seat_for_rejects_unknown_tokens() -> None:
    service = GameService(0)
    game_id = service.create_game("Ada")["game_id"]
    with pytest.raises(GameError, match="unknown player"):
        service.seat_for(game_id, "nope")
    with pytest.raises(GameError, match="no game"):
        service.seat_for("ZZZZZ", "nope")


def test_start_game() -> None:
    service = GameService(0)
    game_id = service.create_game("Ada")["game_id"]
    with pytest.raises(GameError, match="at least 2"):
        service.start_game(game_id, 0)
    service.join_game(game_id, "Ben")
    with pytest.raises(GameError, match="only the host"):
        service.start_game(game_id, 1)
    service.start_game(game_id, 0)
    view = service.view(game_id, 1)
    assert view["status"] == "playing"
    assert view["table"] is not None
    assert len(view["table"]["pearl_display"]) == 4
    assert view["table"]["current_player"] == 0


def test_play() -> None:
    service, game_id = _started()
    with pytest.raises(GameError, match="not your turn"):
        service.play(game_id, 1, Action.TAKE_PEARL_0)
    pearl = _state(service, game_id).pearl_display[0]
    service.play(game_id, 0, Action.TAKE_PEARL_0)
    view = service.view(game_id, 0)
    assert view["table"] is not None
    assert view["table"]["hand"] == [pearl]
    assert view["log"][-1]["text"] == f"took pearl {pearl}"
    assert view["log"][-1]["action"] == 1


def test_play_rejects_activations_and_illegal_actions() -> None:
    service, game_id = _started()
    with pytest.raises(GameError, match="not available"):
        service.play(game_id, 0, Action.ACTIVATE_0)
    with pytest.raises(GameError, match="not available"):
        service.play(game_id, 0, Action.DISCARD_1)


@pytest.mark.parametrize("plan", [0, 1, 2, 3])
def test_activate(plan: int) -> None:
    service, game_id = _started()
    state = _state(service, game_id)
    bilbo = next(index for index, card in enumerate(CHARACTERS) if card.id == "bilbo_odd")
    state._portals[0] = [bilbo]  # noqa: SLF001
    state._hands[0] = Counter({1: 1, 3: 1, 5: 1, 7: 1})  # noqa: SLF001
    table = service.view(game_id, 0)["table"]
    assert table is not None
    (activation,) = table["activations"]
    paid = activation["plans"][plan]["cards"]

    service.activate(game_id, 0, activation["action"], plan)
    assert sorted((Counter({1: 1, 3: 1, 5: 1, 7: 1}) - Counter(paid)).elements()) == state.hands[0]
    assert state.activated_characters[0] == ["bilbo_odd"]
    entry = service.view(game_id, 1)["log"][-1]
    assert (entry["text"], entry["highlight"], entry["tone"]) == ("activated Bilbo", "+1", "power")


def test_activate_rejects_bad_plans() -> None:
    service, game_id = _started()
    with pytest.raises(GameError, match="cannot activate"):
        service.activate(game_id, 0, Action.ACTIVATE_0, 0)
    state = _state(service, game_id)
    state._portals[0] = [0]  # noqa: SLF001  # goblin: one pair
    state._hands[0] = Counter({4: 2})  # noqa: SLF001
    with pytest.raises(GameError, match="does not fit"):
        service.activate(game_id, 0, Action.ACTIVATE_0, 1)


def test_discard() -> None:
    service, game_id = _started()
    state = _state(service, game_id)
    state._hands[0] = Counter({2: 4, 3: 3})  # noqa: SLF001
    with pytest.raises(GameError, match="do not have to discard"):
        service.discard(game_id, 0, [2, 2])
    state._actions_left = 0  # noqa: SLF001
    with pytest.raises(GameError, match="exactly 2"):
        service.discard(game_id, 0, [2])
    with pytest.raises(GameError, match="exactly 2"):
        service.discard(game_id, 0, [8, 8])
    service.discard(game_id, 0, [2, 3])
    assert state.hands[0] == [2, 2, 2, 3, 3]
    assert state.current_player() == 1
    entry = service.view(game_id, 0)["log"][-1]
    assert (entry["text"], entry["highlight"]) == ("discarded pearls", "2, 3")


@pytest.mark.parametrize("players", [2, 3])
def test_view_after_random_play(players: int) -> None:
    """Random commands keep every view consistent until the game ends."""
    rng = random.Random(players)  # noqa: S311  (test randomness, not crypto)
    service, game_id = _started(players, seed=players)
    for _ in range(300):
        view = service.view(game_id, 0)
        if view["status"] == "finished":
            assert view["result"] is not None
            break
        assert view["table"] is not None
        mover = view["table"]["current_player"]
        assert mover is not None
        table = service.view(game_id, mover)["table"]
        assert table is not None
        assert table["prompt"] is not None
        if table["prompt"]["kind"] == "discard":
            service.discard(game_id, mover, rng.sample(table["hand"], table["prompt"]["count"]))
        elif table["activations"]:
            activation = rng.choice(table["activations"])
            service.activate(game_id, mover, activation["action"], 0)
        else:
            service.play(game_id, mover, rng.choice(table["moves"])["action"])
    assert all(len(_state(service, game_id).hands[seat]) <= 8 for seat in range(players))
