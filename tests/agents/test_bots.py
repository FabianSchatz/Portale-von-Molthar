"""Tests for the bots that choose moves for a seat."""

import itertools
import pathlib
import random

import numpy as np
import pyspiel
import pytest

from portale_von_molthar import molthar  # noqa: F401  (registers the game)
from portale_von_molthar.agents.bots import (
    Bot,
    MLPPolicy,
    PolicyBot,
    RandomBot,
    make_bot,
)
from portale_von_molthar.molthar import MoltharState

_HIDDEN = 8


def _state(players: int) -> MoltharState:
    """Return a new game with its chance draws resolved."""
    state = pyspiel.load_game(f"python_portale_von_molthar(players={players})").new_initial_state()
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    return state


def _policy(players: int, seed: int = 0) -> MLPPolicy:
    """Return a random two-layer policy with the game's observation and action sizes."""
    game = pyspiel.load_game(f"python_portale_von_molthar(players={players})")
    rng = np.random.default_rng(seed)
    sizes = [game.observation_tensor_shape()[0], _HIDDEN, game.num_distinct_actions()]
    weights = [rng.normal(size=(out, inp)) for inp, out in itertools.pairwise(sizes)]
    biases = [rng.normal(size=out) for out in sizes[1:]]
    return MLPPolicy(weights, biases, players)


def _bot(bot_type: type[Bot], players: int) -> Bot:
    """Return an instance of `bot_type` for `players`."""
    if bot_type is PolicyBot:
        return PolicyBot(_policy(players), temperature=1.0, seed=0)
    return bot_type(0)  # type: ignore[call-arg]


@pytest.mark.parametrize("bot_type", [RandomBot, PolicyBot])
@pytest.mark.parametrize("players", [2, 4])
def test_choose(bot_type: type[Bot], players: int) -> None:
    """Every bot answers every decision of a game with a legal action."""
    bot = _bot(bot_type, players)
    rng = random.Random(0)  # noqa: S311  (test randomness, not crypto)
    state = _state(players)
    for _ in range(500):
        if state.is_terminal():
            break
        if state.is_chance_node():
            outcomes, weights = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(outcomes, weights=weights)[0])
            continue
        seat = state.current_player()
        action = bot.choose(state, seat)
        assert action in state.legal_actions(seat)
        state.apply_action(action)


def test_choose_policy_bot_greedy_plays_best_legal_action() -> None:
    policy = _policy(2)
    state = _state(2)
    legal = state.legal_actions(0)
    logits = policy.logits(np.asarray(state.observation_tensor(0), dtype=np.float32))
    expected = max(legal, key=lambda action: logits[action])
    assert PolicyBot(policy).choose(state, 0) == expected


def test_choose_policy_bot_rejects_other_player_counts() -> None:
    with pytest.raises(ValueError, match="trained for 3 players"):
        PolicyBot(_policy(3)).choose(_state(2), 0)


def test_load(tmp_path: pathlib.Path) -> None:
    policy = _policy(2)
    path = tmp_path / "policy.npz"
    arrays = {"players": np.array(2)}
    for index, (weight, bias) in enumerate(zip(policy._weights, policy._biases, strict=True)):  # noqa: SLF001
        arrays[f"weight_{index}"] = weight
        arrays[f"bias_{index}"] = bias
    np.savez(path, **arrays)
    loaded = MLPPolicy.load(path)
    obs = np.asarray(_state(2).observation_tensor(0), dtype=np.float32)
    assert loaded.players == 2
    np.testing.assert_allclose(loaded.logits(obs), policy.logits(obs))


def test_make_bot(tmp_path: pathlib.Path) -> None:
    assert isinstance(make_bot(2, "hard", seed=0, model_dir=tmp_path), RandomBot)
    policy = _policy(2)
    np.savez(
        tmp_path / "policy_2p.npz",
        players=np.array(2),
        weight_0=policy._weights[0],  # noqa: SLF001
        bias_0=policy._biases[0],  # noqa: SLF001
        weight_1=policy._weights[1],  # noqa: SLF001
        bias_1=policy._biases[1],  # noqa: SLF001
    )
    assert isinstance(make_bot(2, "hard", seed=0, model_dir=tmp_path), PolicyBot)
    assert isinstance(make_bot(3, "hard", seed=0, model_dir=tmp_path), RandomBot)
