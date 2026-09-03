"""Plays a random game of the simplified *Portale von Molthar*.

Same pattern as tic_tac_toe_demo.py, but for our own game: chance nodes
(display refills) are interleaved automatically with the two players'
action-taking turns.
"""

import random

import pyspiel

from portale_von_molthar import molthar  # noqa: F401  (registers "python_portale_von_molthar")


def play_random_game(seed: int | None = None) -> list[float]:
    """Play one game with uniform-random actions and return the final returns."""
    rng = random.Random(seed)  # noqa: S311  (game simulation, not crypto)
    game = pyspiel.load_game("python_portale_von_molthar")
    state = game.new_initial_state()

    while not state.is_terminal():
        if state.current_player() == pyspiel.PlayerId.CHANCE:
            outcomes, probs = zip(*state.chance_outcomes(), strict=True)
            action = rng.choices(outcomes, weights=probs)[0]
        else:
            action = rng.choice(state.legal_actions())
        print(f"\n{state.action_to_string(state.current_player(), action)}")
        state.apply_action(action)
        print(state)

    return state.returns()


if __name__ == "__main__":
    returns = play_random_game(seed=0)
    print(f"\nFinal returns: {returns}")
