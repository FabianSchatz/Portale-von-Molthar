"""Train a self-play PPO agent for *Portale von Molthar* and export it for the server.

Needs the ``train`` extra: ``uv sync --extra train``. Examples::

    python examples/train_ppo.py --updates 200
    python examples/train_ppo.py --updates 200 --resume checkpoints/ppo_2p.pt

The full training state goes to ``checkpoints/ppo_<players>p.pt`` (to resume), the
playable policy to ``models/policy_<players>p.npz``, where the server's bots find it.
"""

import argparse
import logging
import pathlib

from portale_von_molthar.agents import ppo


def main() -> None:
    """Parse the command line, train, and export the policy."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--updates", type=int, default=100)
    parser.add_argument("--players", type=int, default=2, help="ignored with --resume")
    parser.add_argument("--hidden-size", type=int, default=256, help="ignored with --resume")
    parser.add_argument("--checkpoint", type=pathlib.Path, default=None)
    parser.add_argument("--export", type=pathlib.Path, default=None)
    parser.add_argument("--resume", type=pathlib.Path, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    net = None
    config = ppo.PPOConfig(players=args.players, hidden_size=args.hidden_size)
    if args.resume is not None:
        net, config = ppo.load_checkpoint(args.resume)
    checkpoint = args.checkpoint or pathlib.Path(f"checkpoints/ppo_{config.players}p.pt")
    export = args.export or pathlib.Path(f"models/policy_{config.players}p.npz")
    net = ppo.train(config, args.updates, checkpoint=checkpoint, net=net)
    ppo.export_policy(export, net, config)
    logging.getLogger(__name__).info(f"exported the policy to {export}")


if __name__ == "__main__":
    main()
