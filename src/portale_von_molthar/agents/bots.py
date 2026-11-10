"""Bots that choose moves for one seat: a uniform-random bot and a trained policy.

Bots act on raw engine actions, including payment, discard and ability decisions, and
only look at what their seat may see: ``observation_tensor(seat)`` and the seat's legal
actions. Trained policies run as plain numpy MLPs exported by
`portale_von_molthar.agents.ppo.export_policy`, so playing needs no PyTorch.
"""

import abc
import functools
import logging
import os
import pathlib
import random
from typing import Final, Literal, TypeAlias

import numpy as np

from portale_von_molthar.molthar import MoltharState

Difficulty: TypeAlias = Literal["easy", "medium", "hard"]

DIFFICULTIES: Final[tuple[Difficulty, ...]] = ("easy", "medium", "hard")
MODEL_DIR_ENV: Final = "MOLTHAR_MODEL_DIR"
_DEFAULT_MODEL_DIR: Final = pathlib.Path(__file__).resolve().parents[3] / "models"
# Softmax temperature per difficulty. "hard" keeps a little randomness: it wins as often
# as always playing the favourite move, but cannot get stuck repeating the same move.
_TEMPERATURES: Final[dict[Difficulty, float]] = {"easy": 2.0, "medium": 0.7, "hard": 0.3}
_LOGGER: Final = logging.getLogger(__name__)


class Bot(abc.ABC):
    """Chooses the move of a seat whenever that seat has to decide."""

    @abc.abstractmethod
    def choose(self, state: MoltharState, seat: int) -> int:
        """Return a legal action for `seat`.

        Args:
            state: Running game in which `seat` is the player to move.
            seat: The bot's seat.

        Returns:
            One of ``state.legal_actions(seat)``.
        """


class RandomBot(Bot):
    """Plays a uniformly random legal action; the fallback without a trained model.

    Args:
        seed: Seed of the bot's own random source.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)  # noqa: S311  # nosec B311  # game play, not crypto

    def choose(self, state: MoltharState, seat: int) -> int:  # noqa: D102  # docstring from parent
        return self._rng.choice(state.legal_actions(seat))


class MLPPolicy:
    """Policy network as numpy arrays: ReLU hidden layers followed by a logit layer.

    Args:
        weights: Layer weights, each of shape ``(out, in)``; the last one yields logits.
        biases: Layer biases, each of shape ``(out,)``.
        players: Player count the policy was trained for; it fixes the observation size.
    """

    def __init__(self, weights: list[np.ndarray], biases: list[np.ndarray], players: int) -> None:
        self.players = players
        self._weights = weights
        self._biases = biases

    @classmethod
    def load(cls, path: pathlib.Path) -> "MLPPolicy":
        """Load a policy stored by `portale_von_molthar.agents.ppo.export_policy`."""
        with np.load(path) as data:
            layers = sum(1 for key in data.files if key.startswith("weight_"))
            weights = [data[f"weight_{index}"] for index in range(layers)]
            biases = [data[f"bias_{index}"] for index in range(layers)]
            players = int(data["players"])
        return cls(weights, biases, players)

    def logits(self, obs: np.ndarray) -> np.ndarray:
        """Return the unnormalised action scores.

        Args:
            obs: Flat observation tensor of the acting seat, shape ``(obs_size,)``.

        Returns:
            One score per distinct action, shape ``(num_actions,)``; illegal actions are
            not masked here.
        """
        hidden = obs
        for weight, bias in zip(self._weights[:-1], self._biases[:-1], strict=True):
            hidden = np.maximum(weight @ hidden + bias, 0.0)
        return self._weights[-1] @ hidden + self._biases[-1]


class PolicyBot(Bot):
    """Plays a trained policy, restricted to the legal actions.

    Args:
        policy: Trained policy for the game's player count.
        temperature: Softmax temperature over the legal actions' logits; ``0`` always
            plays the best-scored action, higher values play more randomly.
        seed: Seed of the sampling random source.
    """

    def __init__(
        self,
        policy: MLPPolicy,
        temperature: float = 0.0,
        seed: int | None = None,
    ) -> None:
        self._policy = policy
        self._temperature = temperature
        self._rng = np.random.default_rng(seed)

    def choose(self, state: MoltharState, seat: int) -> int:  # noqa: D102  # docstring from parent
        if state.num_players() != self._policy.players:
            message = (
                f"policy was trained for {self._policy.players} players, "
                f"the game has {state.num_players()}"
            )
            raise ValueError(message)
        legal = np.array(state.legal_actions(seat))
        obs = np.asarray(state.observation_tensor(seat), dtype=np.float32)
        logits = self._policy.logits(obs)[legal]
        if self._temperature <= 0:
            return int(legal[np.argmax(logits)])
        weights = np.exp((logits - logits.max()) / self._temperature)
        return int(self._rng.choice(legal, p=weights / weights.sum()))


def make_bot(
    players: int,
    difficulty: Difficulty,
    seed: int | None = None,
    model_dir: pathlib.Path | None = None,
) -> Bot:
    """Return the bot for a table size and difficulty.

    Uses ``<model_dir>/policy_<players>p.npz`` when it exists and a `RandomBot`
    otherwise, so bot seats work before any model is trained.

    Args:
        players: Player count of the game the bot joins.
        difficulty: How greedily the policy is played, see `_TEMPERATURES`.
        seed: Seed of the bot's random source.
        model_dir: Folder of exported policies; defaults to the ``MOLTHAR_MODEL_DIR``
            environment variable, else ``models/`` in the repository.

    Returns:
        A fresh bot; bots keep no state between moves, but each owns its random source.
    """
    directory = model_dir or pathlib.Path(os.environ.get(MODEL_DIR_ENV, _DEFAULT_MODEL_DIR))
    path = directory / f"policy_{players}p.npz"
    if not path.is_file():
        _LOGGER.warning(f"no model at {path}, using a random bot")
        return RandomBot(seed)
    return PolicyBot(_load_policy(path), _TEMPERATURES[difficulty], seed)


@functools.cache
def _load_policy(path: pathlib.Path) -> MLPPolicy:
    """Load each policy file once per process; a new model needs a server restart."""
    return MLPPolicy.load(path)
