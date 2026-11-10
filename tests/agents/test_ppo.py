"""Smoke tests for the self-play PPO trainer (skipped without PyTorch)."""

import dataclasses
import pathlib
import random

import numpy as np
import pyspiel
import pytest

torch = pytest.importorskip("torch")

from portale_von_molthar.agents import bots, ppo  # noqa: E402  # after the torch availability check

_TINY = ppo.PPOConfig(
    hidden_size=16,
    num_envs=2,
    steps_per_update=64,
    max_decisions=40,
    minibatch_size=32,
    epochs=1,
    eval_games=2,
)


@pytest.mark.parametrize("players", [2, 3])
def test_train(players: int, tmp_path: pathlib.Path) -> None:
    config = dataclasses.replace(_TINY, players=players)
    checkpoint = tmp_path / "net.pt"
    net = ppo.train(config, updates=1, checkpoint=checkpoint)
    loaded, loaded_config = ppo.load_checkpoint(checkpoint)
    assert loaded_config == config
    for key, value in net.state_dict().items():
        assert (loaded.state_dict()[key] == value).all()


@pytest.mark.parametrize("with_opponent", [False, True])
def test_evaluate(with_opponent: bool) -> None:  # noqa: FBT001  # pytest parameter
    net = ppo._build_net(_TINY)  # noqa: SLF001
    opponent = ppo._build_net(_TINY) if with_opponent else None  # noqa: SLF001
    assert 0.0 <= ppo.evaluate(net, _TINY, num_games=4, opponent=opponent) <= 1.0


def test_collect_rollouts_with_pool() -> None:
    """With every game against the pool, only one seat per game is trained on."""
    config = dataclasses.replace(_TINY, pool_prob=1.0)
    game = pyspiel.load_game(f"{ppo.GAME_NAME}(players=2)")
    net = ppo._build_net(config)  # noqa: SLF001
    opponent = ppo._build_net(config)  # noqa: SLF001
    rng = random.Random(0)  # noqa: S311  # nosec B311  # game simulation
    trajectories, stats = ppo.collect_rollouts(game, net, config, rng, [opponent])
    assert sum(1 for trajectory in trajectories if trajectory) <= stats["games"]


def test_export_policy(tmp_path: pathlib.Path) -> None:
    """The numpy policy scores actions exactly like the torch network it came from."""
    net = ppo._build_net(_TINY)  # noqa: SLF001
    path = tmp_path / "policy.npz"
    ppo.export_policy(path, net, _TINY)
    policy = bots.MLPPolicy.load(path)
    state = pyspiel.load_game(f"{ppo.GAME_NAME}(players=2)").new_initial_state()
    obs = state.observation_tensor(0)
    mask = torch.ones(1, len(policy.logits(np.asarray(obs, dtype=np.float32))), dtype=torch.bool)
    expected = net(torch.tensor([obs]), mask)[0][0].detach().numpy()
    actual = policy.logits(np.asarray(obs, dtype=np.float32))
    assert policy.players == _TINY.players
    np.testing.assert_allclose(actual, expected, rtol=1e-5, atol=1e-5)
