"""Self-play PPO agent for *Portale von Molthar*.

One policy-value network is shared by every seat: the observation tensor already
contains a one-hot of the observing player, so a single network can play any seat
and learns from the experience of all of them. Illegal actions are masked out of
the policy before sampling.

Reward per decision of a player (the "shaped" reward):

* the change of the potential ``(own score - mean opponent score) / 12`` between
  this decision and the same player's next decision (potential-based shaping,
  which keeps the optimal strategy unchanged but gives feedback every turn),
* minus a small ``step_cost`` so that stalling is never free,
* plus the game's win/loss return after the player's last decision.

Games that hit ``max_decisions`` are cut off and count as a draw (return 0).

Opponent pool: every ``eval_every`` updates a frozen copy of the network joins a pool
of the last ``pool_size`` snapshots. A ``pool_prob`` share of the training games puts
the learner into one random seat and a sampled snapshot into all others; only the
learner's decisions are trained on. This keeps the policy beating older strategies
instead of cycling. Progress is measured by the greedy win rate against the newest
snapshot: above ``1 / players`` means the policy is still improving.

Requires the optional ``train`` extra (PyTorch). Usage: see ``examples/train_ppo.py``.
"""

import copy
import dataclasses
import logging
import pathlib
import random
import time
from typing import Any, Final

import numpy as np
import pyspiel
import torch
from torch import nn

from portale_von_molthar.game import molthar

GAME_NAME: Final = "python_portale_von_molthar"
_TARGET_POINTS: Final = molthar._TARGET_POINTS  # noqa: SLF001  # score normalisation
_LOGGER: Final = logging.getLogger(__name__)
_MASKED_LOGIT: Final = -1e9


@dataclasses.dataclass(frozen=True)
class PPOConfig:
    """Hyperparameters of the self-play PPO training.

    The defaults train on a laptop CPU; for stronger play increase ``hidden_size``,
    ``steps_per_update`` and the number of updates.
    """

    players: int = 2
    hidden_size: int = 256
    num_envs: int = 16
    steps_per_update: int = 32768
    max_decisions: int = 1500
    epochs: int = 4
    minibatch_size: int = 4096
    learning_rate: float = 3e-4
    gamma: float = 0.995
    gae_lambda: float = 0.95
    clip_coef: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    step_cost: float = 0.002
    eval_every: int = 10
    eval_games: int = 50
    pool_size: int = 20
    pool_prob: float = 0.5
    seed: int = 0


class PolicyValueNet(nn.Module):
    """MLP with a shared trunk, a masked policy head and a value head."""

    def __init__(self, obs_size: int, num_actions: int, hidden_size: int) -> None:
        super().__init__()
        self.trunk = nn.Sequential(
            nn.Linear(obs_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
        )
        self.policy_head = nn.Linear(hidden_size, num_actions)
        self.value_head = nn.Linear(hidden_size, 1)

    def forward(self, obs: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return masked action logits and state values.

        Args:
            obs: Observations, shape ``(batch, obs_size)``.
            mask: Boolean legal-action mask, shape ``(batch, num_actions)``.

        Returns:
            Logits of shape ``(batch, num_actions)`` with illegal actions set to a huge
            negative number, and values of shape ``(batch,)`` estimating the acting
            player's discounted shaped return.
        """
        hidden = self.trunk(obs)
        logits = self.policy_head(hidden).masked_fill(~mask, _MASKED_LOGIT)
        return logits, self.value_head(hidden).squeeze(-1)


@dataclasses.dataclass
class _Transition:
    """One decision of one player, with the reward it earned until its next decision."""

    obs: list[float]
    mask: np.ndarray
    action: int
    log_prob: float
    value: float
    reward: float


@dataclasses.dataclass
class _Episode:
    """A running game together with each player's trajectory so far."""

    state: pyspiel.State
    trajectories: list[list[_Transition]]
    potentials: list[float]
    decisions: int = 0
    opponent: "PolicyValueNet | None" = None
    learner_seat: int = 0


@dataclasses.dataclass(frozen=True)
class _Batch:
    """Flattened rollout tensors; the first dimension indexes transitions."""

    obs: torch.Tensor
    masks: torch.Tensor
    actions: torch.Tensor
    log_probs: torch.Tensor
    advantages: torch.Tensor
    returns: torch.Tensor


def _potential(state: pyspiel.State, player: int) -> float:
    """Return ``(own score - mean opponent score) / target points`` of `player`."""
    scores = state.scores
    others = [score for index, score in enumerate(scores) if index != player]
    return (scores[player] - sum(others) / len(others)) / _TARGET_POINTS


def _resolve_chance(state: pyspiel.State, rng: random.Random) -> None:
    """Sample chance outcomes until a player has to decide or the game is over."""
    while state.is_chance_node():
        outcomes, probs = zip(*state.chance_outcomes(), strict=True)
        state.apply_action(rng.choices(outcomes, weights=probs)[0])


def _legal_mask(state: pyspiel.State, num_actions: int) -> np.ndarray:
    """Return a boolean mask of the current player's legal actions."""
    mask = np.zeros(num_actions, dtype=bool)
    mask[state.legal_actions()] = True
    return mask


def _new_episode(
    game: pyspiel.Game,
    rng: random.Random,
    pool: list[PolicyValueNet] | None = None,
    pool_prob: float = 0.0,
) -> _Episode:
    """Start a game; with probability `pool_prob` a pool snapshot plays all but one seat."""
    state = game.new_initial_state()
    _resolve_chance(state, rng)
    players = game.num_players()
    episode = _Episode(state, [[] for _ in range(players)], [0.0] * players)
    if pool and rng.random() < pool_prob:
        episode.opponent = rng.choice(pool)
        episode.learner_seat = rng.randrange(players)
    return episode


def _finish(episode: _Episode) -> None:
    """Add the last potential change and the win/loss return to every trajectory."""
    returns = episode.state.returns()  # all zeros for a game cut off before its end
    for player, trajectory in enumerate(episode.trajectories):
        if trajectory:
            potential = _potential(episode.state, player)
            trajectory[-1].reward += potential - episode.potentials[player] + returns[player]


def _override_opponent_actions(
    episodes: list[_Episode],
    players: list[int],
    obs: list[list[float]],
    masks: np.ndarray,
    actions: torch.Tensor,
) -> None:
    """Replace, in place, the sampled `actions` of opponent seats by their snapshot's choice.

    Episodes sharing a snapshot are evaluated as one batch.

    Args:
        episodes: Running games, aligned with the other arguments.
        players: Player to move in each game.
        obs: Observation of the player to move, one per game.
        masks: Legal-action masks, shape ``(games, num_actions)``.
        actions: Actions sampled by the learner, shape ``(games,)``; overwritten.
    """
    by_opponent: dict[int, tuple[PolicyValueNet, list[int]]] = {}
    for index, (episode, player) in enumerate(zip(episodes, players, strict=True)):
        if episode.opponent is not None and player != episode.learner_seat:
            by_opponent.setdefault(id(episode.opponent), (episode.opponent, []))[1].append(index)
    for opponent, indices in by_opponent.values():
        logits, _ = opponent(
            torch.tensor([obs[index] for index in indices]),
            torch.from_numpy(masks[indices]),
        )
        actions[indices] = torch.distributions.Categorical(logits=logits).sample()


def collect_rollouts(
    game: pyspiel.Game,
    net: PolicyValueNet,
    config: PPOConfig,
    rng: random.Random,
    pool: list[PolicyValueNet] | None = None,
) -> tuple[list[list[_Transition]], dict[str, float]]:
    """Play games with `net` until enough decisions are collected.

    Most games are pure self-play; a ``config.pool_prob`` share pits `net` in one seat
    against a snapshot from `pool` in the others (see the module docstring).

    ``config.num_envs`` games run in lockstep so that the network evaluates one batch
    per step. Games are always played to their end (or cut-off), so every returned
    trajectory is complete.

    Args:
        game: The loaded Molthar game.
        net: Network sampling the actions of all players.
        config: Training configuration.
        rng: Random source for chance outcomes and opponent sampling.
        pool: Frozen earlier networks to sample opponents from; none if empty.

    Returns:
        One trajectory per player and game, and statistics of the finished games.
    """
    num_actions = game.num_distinct_actions()
    episodes = [_new_episode(game, rng, pool, config.pool_prob) for _ in range(config.num_envs)]
    finished: list[list[_Transition]] = []
    collected = 0
    games = cut_off = 0
    decisions_total = 0
    scores_total = 0.0
    while episodes:
        players = [episode.state.current_player() for episode in episodes]
        obs = [
            episode.state.observation_tensor(player)
            for episode, player in zip(episodes, players, strict=True)
        ]
        masks = np.stack([_legal_mask(episode.state, num_actions) for episode in episodes])
        with torch.no_grad():
            logits, values = net(torch.tensor(obs), torch.from_numpy(masks))
            dist = torch.distributions.Categorical(logits=logits)
            actions = dist.sample()
            log_probs = dist.log_prob(actions)
            _override_opponent_actions(episodes, players, obs, masks, actions)
        running: list[_Episode] = []
        for index, (episode, player) in enumerate(zip(episodes, players, strict=True)):
            action = int(actions[index])
            if episode.opponent is None or player == episode.learner_seat:
                trajectory = episode.trajectories[player]
                potential = _potential(episode.state, player)
                if trajectory:
                    trajectory[-1].reward += potential - episode.potentials[player]
                episode.potentials[player] = potential
                trajectory.append(
                    _Transition(
                        obs[index],
                        masks[index],
                        action,
                        float(log_probs[index]),
                        float(values[index]),
                        -config.step_cost,
                    ),
                )
                collected += 1
            episode.state.apply_action(action)
            _resolve_chance(episode.state, rng)
            episode.decisions += 1
            if episode.state.is_terminal() or episode.decisions >= config.max_decisions:
                _finish(episode)
                finished.extend(episode.trajectories)  # opponent seats stay empty
                games += 1
                cut_off += not episode.state.is_terminal()
                decisions_total += episode.decisions
                scores_total += sum(episode.state.scores) / len(episode.state.scores)
                if collected < config.steps_per_update:
                    running.append(_new_episode(game, rng, pool, config.pool_prob))
            else:
                running.append(episode)
        episodes = running
    stats = {
        "games": float(games),
        "cut_off_rate": cut_off / games,
        "decisions_per_game": decisions_total / games,
        "mean_score": scores_total / games,
    }
    return finished, stats


def _to_batch(trajectories: list[list[_Transition]], config: PPOConfig) -> _Batch:
    """Compute GAE advantages per trajectory and flatten everything into tensors."""
    advantages: list[float] = []
    for trajectory in trajectories:
        last = 0.0
        reversed_adv: list[float] = []
        for index in reversed(range(len(trajectory))):
            step = trajectory[index]
            next_value = trajectory[index + 1].value if index + 1 < len(trajectory) else 0.0
            delta = step.reward + config.gamma * next_value - step.value
            last = delta + config.gamma * config.gae_lambda * last
            reversed_adv.append(last)
        advantages.extend(reversed(reversed_adv))
    steps = [step for trajectory in trajectories for step in trajectory]
    adv = torch.tensor(advantages, dtype=torch.float32)
    values = torch.tensor([step.value for step in steps], dtype=torch.float32)
    return _Batch(
        obs=torch.tensor([step.obs for step in steps], dtype=torch.float32),
        masks=torch.from_numpy(np.stack([step.mask for step in steps])),
        actions=torch.tensor([step.action for step in steps]),
        log_probs=torch.tensor([step.log_prob for step in steps], dtype=torch.float32),
        advantages=adv,
        returns=adv + values,
    )


def ppo_update(
    net: PolicyValueNet,
    optimizer: torch.optim.Optimizer,
    trajectories: list[list[_Transition]],
    config: PPOConfig,
) -> dict[str, float]:
    """Run the clipped PPO optimisation on the collected trajectories.

    Args:
        net: Network to improve in place.
        optimizer: Optimizer over the parameters of `net`.
        trajectories: Complete per-player trajectories from `collect_rollouts`.
        config: Training configuration.

    Returns:
        Losses and the policy entropy of the last minibatch.
    """
    batch = _to_batch(trajectories, config)
    count = len(batch.actions)
    metrics: dict[str, float] = {}
    for _ in range(config.epochs):
        order = torch.randperm(count)
        for start in range(0, count, config.minibatch_size):
            idx = order[start : start + config.minibatch_size]
            logits, values = net(batch.obs[idx], batch.masks[idx])
            dist = torch.distributions.Categorical(logits=logits)
            ratio = (dist.log_prob(batch.actions[idx]) - batch.log_probs[idx]).exp()
            adv = batch.advantages[idx]
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
            clipped = ratio.clamp(1 - config.clip_coef, 1 + config.clip_coef)
            policy_loss = -torch.min(ratio * adv, clipped * adv).mean()
            value_loss = (values - batch.returns[idx]).pow(2).mean()
            entropy = dist.entropy().mean()
            loss = policy_loss + config.value_coef * value_loss - config.entropy_coef * entropy
            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 0.5)
            optimizer.step()
            metrics = {
                "policy_loss": policy_loss.item(),
                "value_loss": value_loss.item(),
                "entropy": entropy.item(),
            }
    return metrics


def evaluate(
    net: PolicyValueNet,
    config: PPOConfig,
    num_games: int,
    opponent: PolicyValueNet | None = None,
    seed: int = 1,
) -> float:
    """Return the win rate of the greedy agent against `opponent` in all other seats.

    The agent takes every seat in turn. A shared win counts as a fraction, a cut-off
    game as no win.

    Args:
        net: Trained network; it plays its most likely legal action.
        config: Configuration providing the player count and the game cut-off.
        num_games: Number of evaluation games.
        opponent: Network for the other seats, also greedy; uniform-random if ``None``.
        seed: Random seed for chance and the random opponents.

    Returns:
        Average share of the win, in ``[0, 1]``. ``1 / players`` means equal strength.
    """
    rng = random.Random(seed)  # noqa: S311  # nosec B311  # game simulation
    game = pyspiel.load_game(f"{GAME_NAME}(players={config.players})")
    num_actions = game.num_distinct_actions()
    wins = 0.0
    for game_index in range(num_games):
        agent_seat = game_index % config.players
        state = game.new_initial_state()
        _resolve_chance(state, rng)
        for _ in range(config.max_decisions):
            if state.is_terminal():
                break
            player = state.current_player()
            actor = net if player == agent_seat else opponent
            if actor is None:
                action = rng.choice(state.legal_actions())
            else:
                obs = torch.tensor([state.observation_tensor(player)])
                mask = torch.from_numpy(_legal_mask(state, num_actions)[None])
                with torch.no_grad():
                    action = int(actor(obs, mask)[0].argmax())
            state.apply_action(action)
            _resolve_chance(state, rng)
        returns = state.returns()
        if returns[agent_seat] > 0:
            wins += 1 / sum(1 for value in returns if value > 0)
    return wins / num_games


def save_checkpoint(path: pathlib.Path, net: PolicyValueNet, config: PPOConfig) -> None:
    """Store the network weights together with the configuration that built it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": dataclasses.asdict(config), "model": net.state_dict()}, path)


def load_checkpoint(path: pathlib.Path) -> tuple[PolicyValueNet, PPOConfig]:
    """Load a network and its configuration stored by `save_checkpoint`."""
    data = torch.load(path, weights_only=True)
    config = PPOConfig(**data["config"])
    net = _build_net(config)
    net.load_state_dict(data["model"])
    return net, config


def export_policy(path: pathlib.Path, net: PolicyValueNet, config: PPOConfig) -> None:
    """Store the policy part of `net` as plain numpy arrays for `bots.MLPPolicy`.

    Layer ``index`` is stored as ``weight_<index>`` with shape ``(out, in)`` and
    ``bias_<index>`` with shape ``(out,)``: first the trunk layers (each followed by a
    ReLU), last the policy head. The value head is not needed to play and is dropped,
    so the server can run the policy without PyTorch.

    Args:
        path: Target ``.npz`` file; parent folders are created.
        net: Trained network.
        config: Configuration `net` was trained with; stores the player count.
    """
    layers = [module for module in net.trunk if isinstance(module, nn.Linear)]
    layers.append(net.policy_head)
    arrays: dict[str, Any] = {"players": np.array(config.players)}
    for index, layer in enumerate(layers):
        arrays[f"weight_{index}"] = layer.weight.detach().numpy().astype(np.float32)
        arrays[f"bias_{index}"] = layer.bias.detach().numpy().astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **arrays)


def _build_net(config: PPOConfig) -> PolicyValueNet:
    game = pyspiel.load_game(f"{GAME_NAME}(players={config.players})")
    obs_size = game.observation_tensor_shape()[0]
    return PolicyValueNet(obs_size, game.num_distinct_actions(), config.hidden_size)


def train(
    config: PPOConfig,
    updates: int,
    checkpoint: pathlib.Path | None = None,
    net: PolicyValueNet | None = None,
) -> PolicyValueNet:
    """Train the shared self-play network with PPO.

    Args:
        config: Training configuration.
        updates: Number of collect-and-optimise iterations.
        checkpoint: File the network is saved to after every evaluation, if given.
        net: Network to continue training; a fresh one is built if ``None``.

    Returns:
        The trained network.
    """
    torch.manual_seed(config.seed)
    rng = random.Random(config.seed)  # noqa: S311  # nosec B311  # game simulation
    game = pyspiel.load_game(f"{GAME_NAME}(players={config.players})")
    net = net or _build_net(config)
    optimizer = torch.optim.Adam(net.parameters(), lr=config.learning_rate)
    pool = [copy.deepcopy(net).eval()]
    for update in range(1, updates + 1):
        start = time.perf_counter()
        trajectories, stats = collect_rollouts(game, net, config, rng, pool)
        metrics = ppo_update(net, optimizer, trajectories, config)
        steps = sum(len(trajectory) for trajectory in trajectories)
        _LOGGER.info(
            f"update {update}: {steps / (time.perf_counter() - start):.0f} decisions/s "
            f"games={stats['games']:.0f} cut_off={stats['cut_off_rate']:.2f} "
            f"len={stats['decisions_per_game']:.0f} score={stats['mean_score']:.2f} "
            f"entropy={metrics['entropy']:.2f} value_loss={metrics['value_loss']:.3f}",
        )
        if update % config.eval_every == 0 or update == updates:
            vs_random = evaluate(net, config, config.eval_games)
            vs_pool = evaluate(net, config, config.eval_games, opponent=pool[-1])
            _LOGGER.info(
                f"update {update}: win rate vs random = {vs_random:.2f}, "
                f"vs last snapshot = {vs_pool:.2f} (equal = {1 / config.players:.2f})",
            )
            pool = [*pool, copy.deepcopy(net).eval()][-config.pool_size :]
            if checkpoint is not None:
                save_checkpoint(checkpoint, net, config)
    return net
