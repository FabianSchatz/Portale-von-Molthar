"""Plays a random game of OpenSpiel's built-in Python Tic-Tac-Toe.

Demonstrates the core pyspiel.Game / pyspiel.State API that every Python
game (including a future custom one) implements: load_game, legal_actions,
apply_action, is_terminal, returns.

Source of the game itself: .venv/lib/python3.11/site-packages/open_spiel/
python/games/tic_tac_toe.py
"""

import random

import pyspiel
from open_spiel.python.games import tic_tac_toe  # noqa: F401  (registers "python_tic_tac_toe")


def play_random_game(seed: int | None = None) -> list[float]:
    """Play one game with uniform-random actions and return the final returns."""
    rng = random.Random(seed)  # noqa: S311  (game simulation, not crypto)
    game = pyspiel.load_game("python_tic_tac_toe")
    state = game.new_initial_state()

    while not state.is_terminal():
        action = rng.choice(state.legal_actions())
        print(f"\n{state.action_to_string(state.current_player(), action)}")
        state.apply_action(action)
        print(state)

    return state.returns()


if __name__ == "__main__":
    returns = play_random_game()
    print(f"\nFinal returns: {returns}")
    assert sum(returns) == 0, "tic-tac-toe is zero-sum"  # noqa: S101  (demo sanity check)
    assert set(returns) <= {1.0, -1.0, 0.0}  # noqa: S101
