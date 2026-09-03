"""A simplified *Die Portale von Molthar* implemented as an OpenSpiel Python game.

Simplifications with respect to the printed rules (see module constants):

* Only the 14 green (no-special-ability) character cards from
  ``docs/character_cards.md`` are modelled; red (one-shot) and blue
  (permanent) ability cards are not yet implemented.
* Diamonds are tracked as a plain per-player counter rather than as physical
  character cards drawn from the deck, and cannot yet be spent to modify a
  pearl card's value (see RULES.md section 8).
* Pearl cards can only be taken from the face-up display, never blind from the
  draw pile.
* Going over the hand limit is resolved automatically instead of letting the
  player pick which cards to drop.
* Two players; the retail game supports two to five.

Importing this module registers the game under the short name
``python_portale_von_molthar`` so that it can be created with
``pyspiel.load_game("python_portale_von_molthar")``.
"""

from __future__ import annotations

import enum
from collections import Counter
from typing import Any, Final

import pyspiel

from portale_von_molthar.cards import CHARACTERS, find_combination

_NUM_PLAYERS: Final = 2
_PEARL_VALUES: Final = tuple(range(1, 9))
_PEARL_COPIES: Final = 7
_PEARL_DISPLAY_SIZE: Final = 4
_CHAR_DISPLAY_SIZE: Final = 2
_PORTAL_SLOTS: Final = 2
_HAND_LIMIT: Final = 5
_ACTIONS_PER_TURN: Final = 3
_TARGET_POINTS: Final = 12
# Safety net: the simplified game has no forced progress, so two players who
# only ever "pass" would loop forever.
_MAX_NODES: Final = 3000


class Action(enum.IntEnum):
    """The nine distinct player actions; three of them are spent per turn."""

    TAKE_PEARL_0 = 0
    TAKE_PEARL_1 = 1
    TAKE_PEARL_2 = 2
    TAKE_PEARL_3 = 3
    REFRESH_PEARLS = 4
    TAKE_CHARACTER_0 = 5
    TAKE_CHARACTER_1 = 6
    ACTIVATE_0 = 7
    ACTIVATE_1 = 8


_GAME_TYPE: Final = pyspiel.GameType(
    short_name="python_portale_von_molthar",
    long_name="Portale von Molthar (simplified)",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=_NUM_PLAYERS,
    min_num_players=_NUM_PLAYERS,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=True,
)
_GAME_INFO: Final = pyspiel.GameInfo(
    num_distinct_actions=len(Action),
    max_chance_outcomes=max(len(_PEARL_VALUES), len(CHARACTERS)),
    num_players=_NUM_PLAYERS,
    min_utility=-1.0,
    max_utility=1.0,
    utility_sum=0.0,
    max_game_length=_MAX_NODES,
)


class MoltharState(pyspiel.State):  # type: ignore[misc]
    """State of a simplified *Portale von Molthar* game."""

    def __init__(self, game: pyspiel.Game) -> None:
        super().__init__(game)
        self._pearl_deck: Counter[int] = Counter(dict.fromkeys(_PEARL_VALUES, _PEARL_COPIES))
        self._pearl_discard: Counter[int] = Counter()
        self._pearl_display: list[int] = []
        self._character_deck: Counter[int] = Counter(
            {index: character.copies for index, character in enumerate(CHARACTERS)},
        )
        self._character_display: list[int] = []
        self._hands: list[Counter[int]] = [Counter() for _ in range(_NUM_PLAYERS)]
        self._portals: list[list[int]] = [[] for _ in range(_NUM_PLAYERS)]
        self._scores: list[int] = [0] * _NUM_PLAYERS
        self._diamonds: list[int] = [0] * _NUM_PLAYERS
        self._cur_player = 0
        self._actions_left = _ACTIONS_PER_TURN
        self._nodes = 0
        self._game_over = False

    # region properties

    @property
    def scores(self) -> list[int]:
        """Power points collected by each player so far."""
        return list(self._scores)

    # endregion

    # region magic methods

    def __str__(self) -> str:
        """Return a human readable dump of the full (perfect information) state."""
        lines = [
            f"pearls={self._pearl_display} deck={self._pearl_deck.total()}",
            f"characters={[CHARACTERS[card].id for card in self._character_display]}",
        ]
        for player in range(_NUM_PLAYERS):
            portal = [CHARACTERS[card].id for card in self._portals[player]]
            hand = sorted(self._hands[player].elements())
            lines.append(
                f"p{player}: score={self._scores[player]} diamonds={self._diamonds[player]} "
                f"portal={portal} hand={hand}",
            )
        lines.append(f"turn=p{self._cur_player} actions_left={self._actions_left}")
        return "\n".join(lines)

    # endregion

    # region public methods

    def current_player(self) -> int:
        """Return the mover: a player id, or the terminal/chance sentinel."""
        if self._game_over:
            return pyspiel.PlayerId.TERMINAL
        if self._pending_refill() is not None:
            return pyspiel.PlayerId.CHANCE
        return self._cur_player

    def chance_outcomes(self) -> list[tuple[int, float]]:
        """Return (outcome, probability) pairs for the pending display refill.

        Cards are drawn as a weighted choice over the *remaining counts* of the
        deck, which is equivalent to drawing from a shuffled pile but avoids
        modelling the pile order.
        """
        deck = self._pending_refill()
        if deck is None:
            raise ValueError("chance_outcomes called on a non-chance node")
        total = deck.total()
        return [(key, count / total) for key, count in sorted(deck.items()) if count]

    def is_terminal(self) -> bool:
        """Return whether the game has ended."""
        return self._game_over

    def returns(self) -> list[float]:
        """Return the zero-sum payoff: +1 for the higher score, 0 on a draw."""
        if not self._game_over or self._scores[0] == self._scores[1]:
            return [0.0, 0.0]
        winner = 0 if self._scores[0] > self._scores[1] else 1
        return [1.0 if player == winner else -1.0 for player in range(_NUM_PLAYERS)]

    def observation_string(self, player: int) -> str:
        """Return the state as seen by `player` (own hand, public everything else)."""
        hand = sorted(self._hands[player].elements())
        portals = [
            [CHARACTERS[card].id for card in self._portals[other]] for other in range(_NUM_PLAYERS)
        ]
        return (
            f"p{player} hand={hand} "
            f"pearls={self._pearl_display} "
            f"chars={[CHARACTERS[card].id for card in self._character_display]} "
            f"portals={portals} scores={self._scores} diamonds={self._diamonds} "
            f"to_move=p{self._cur_player} left={self._actions_left}"
        )

    def observation_tensor(self, player: int) -> list[float]:
        """Return the flat observation of `player`; see `observation_shape` for the layout."""
        planes: list[float] = []
        planes.extend(1.0 if player == index else 0.0 for index in range(_NUM_PLAYERS))
        planes.extend(
            self._hands[player][value] / (_HAND_LIMIT + _ACTIONS_PER_TURN)
            for value in _PEARL_VALUES
        )
        for slot in range(_PEARL_DISPLAY_SIZE):
            value = self._pearl_display[slot] if slot < len(self._pearl_display) else 0
            planes.extend(1.0 if value == option else 0.0 for option in (0, *_PEARL_VALUES))
        for slot in range(_CHAR_DISPLAY_SIZE):
            planes.extend(self._character_one_hot(self._character_display, slot))
        for other in range(_NUM_PLAYERS):
            for slot in range(_PORTAL_SLOTS):
                planes.extend(self._character_one_hot(self._portals[other], slot))
        planes.extend(score / _TARGET_POINTS for score in self._scores)
        planes.extend(float(diamonds) for diamonds in self._diamonds)
        planes.extend(
            1.0 if self._actions_left == step + 1 else 0.0 for step in range(_ACTIONS_PER_TURN)
        )
        return planes

    # endregion

    # region private methods

    def _legal_actions(self, player: int) -> list[int]:
        """Return the sorted legal actions for `player`."""
        actions: list[int] = list(range(len(self._pearl_display)))
        if self._pearl_display:
            actions.append(Action.REFRESH_PEARLS)
        if len(self._portals[player]) < _PORTAL_SLOTS:
            actions.extend(
                Action.TAKE_CHARACTER_0 + slot for slot in range(len(self._character_display))
            )
        for slot, card in enumerate(self._portals[player]):
            character = CHARACTERS[card]
            if self._diamonds[player] < character.diamonds_cost:
                continue
            if find_combination(self._hands[player], character) is not None:
                actions.append(Action.ACTIVATE_0 + slot)
        # A player is never stuck: refreshing an empty display is a legal pass.
        return sorted(actions) if actions else [int(Action.REFRESH_PEARLS)]

    def _apply_action(self, action: int) -> None:
        """Apply `action`, which is a chance outcome on chance nodes."""
        self._nodes += 1
        deck = self._pending_refill()
        if deck is not None:
            self._draw(deck, action)
        else:
            self._apply_player_action(action)
            self._end_action()
        if not self._pearl_deck.total():
            # ponytail: instant reshuffle of the discard pile; the real game
            # shuffles once, which only matters for card counting.
            self._pearl_deck += self._pearl_discard
            self._pearl_discard.clear()
        if self._nodes >= _MAX_NODES:
            self._game_over = True

    def _action_to_string(self, player: int, action: int) -> str:
        """Return a label for `action` as taken by `player`."""
        if player == pyspiel.PlayerId.CHANCE:
            if len(self._pearl_display) < _PEARL_DISPLAY_SIZE and self._pearl_deck.total():
                return f"DealPearl:{action}"
            return f"DealCharacter:{CHARACTERS[action].id}"
        if action <= Action.TAKE_PEARL_3:
            return f"TakePearl:{self._pearl_display[action]}"
        if action == Action.REFRESH_PEARLS:
            return "RefreshPearls"
        if action <= Action.TAKE_CHARACTER_1:
            slot = action - Action.TAKE_CHARACTER_0
            return f"TakeCharacter:{CHARACTERS[self._character_display[slot]].id}"
        slot = action - Action.ACTIVATE_0
        return f"Activate:{CHARACTERS[self._portals[player][slot]].id}"

    def _pending_refill(self) -> Counter[int] | None:
        """Return the deck that must be drawn from before the next player move."""
        if len(self._pearl_display) < _PEARL_DISPLAY_SIZE and self._pearl_deck.total():
            return self._pearl_deck
        if len(self._character_display) < _CHAR_DISPLAY_SIZE and self._character_deck.total():
            return self._character_deck
        return None

    def _draw(self, deck: Counter[int], outcome: int) -> None:
        """Move the drawn card from `deck` to the display it belongs to."""
        deck[outcome] -= 1
        if deck is self._pearl_deck:
            self._pearl_display.append(outcome)
        else:
            self._character_display.append(outcome)

    def _apply_player_action(self, action: int) -> None:
        """Apply one of the three per-turn actions of the current player."""
        player = self._cur_player
        if action <= Action.TAKE_PEARL_3:
            self._hands[player][self._pearl_display.pop(action)] += 1
        elif action == Action.REFRESH_PEARLS:
            self._pearl_discard += Counter(self._pearl_display)
            self._pearl_display.clear()
        elif action <= Action.TAKE_CHARACTER_1:
            self._portals[player].append(
                self._character_display.pop(action - Action.TAKE_CHARACTER_0),
            )
        else:
            self._activate(player, action - Action.ACTIVATE_0)

    def _activate(self, player: int, slot: int) -> None:
        """Pay the requirement of the character in `slot` and score its rewards."""
        character = CHARACTERS[self._portals[player][slot]]
        combination = find_combination(self._hands[player], character)
        if combination is None or self._diamonds[player] < character.diamonds_cost:
            message = f"cannot activate {character.id} with the current hand"
            raise ValueError(message)
        for value in combination:
            self._hands[player][value] -= 1
            self._pearl_discard[value] += 1
        self._hands[player] = +self._hands[player]  # drop zero counts
        self._portals[player].pop(slot)
        self._scores[player] += character.points
        self._diamonds[player] += character.diamonds - character.diamonds_cost

    def _end_action(self) -> None:
        """Consume one action and hand over the turn once three have been spent."""
        self._actions_left -= 1
        if self._actions_left:
            return
        self._trim_hand(self._cur_player)
        self._cur_player = (self._cur_player + 1) % _NUM_PLAYERS
        self._actions_left = _ACTIONS_PER_TURN
        # The round is played to the end so that every player had equal turns.
        if self._cur_player == 0 and max(self._scores) >= _TARGET_POINTS:
            self._game_over = True

    def _trim_hand(self, player: int) -> None:
        """Discard down to the hand limit, dropping the least useful pearls first."""
        hand = self._hands[player]
        wanted = self._wanted_values(player)
        while hand.total() > _HAND_LIMIT:
            spare = [value for value in hand.elements() if value not in wanted]
            value = min(spare) if spare else min(hand.elements())
            hand[value] -= 1
            self._pearl_discard[value] += 1
        self._hands[player] = +hand

    def _wanted_values(self, player: int) -> set[int]:
        """Return the pearl values that best progress the player's portal characters.

        Used only to pick which pearls to drop at the hand limit, so the
        heuristic does not need to find an actual valid activation.
        """
        hand = self._hands[player]
        wanted: set[int] = set()
        for card in self._portals[player]:
            for part in CHARACTERS[card].requirement:
                if part.kind == "exact":
                    wanted.update(part.values)
                elif part.kind == "same":
                    wanted.add(max(_PEARL_VALUES, key=hand.__getitem__))
                elif part.kind == "parity":
                    wanted.update(value for value in _PEARL_VALUES if (value % 2 == 0) == part.even)
                else:  # "sum": no single value is more useful than another
                    wanted.update(_PEARL_VALUES)
        return wanted

    @staticmethod
    def _character_one_hot(cards: list[int], slot: int) -> list[float]:
        """Return a one-hot over "empty" plus the character types for `cards[slot]`."""
        card = cards[slot] if slot < len(cards) else None
        return [1.0 if card is None else 0.0] + [
            1.0 if card == index else 0.0 for index in range(len(CHARACTERS))
        ]

    # endregion


class MoltharGame(pyspiel.Game):  # type: ignore[misc]
    """The simplified *Portale von Molthar* game."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        super().__init__(_GAME_TYPE, _GAME_INFO, params or {})

    def new_initial_state(self) -> MoltharState:
        """Return a state with empty displays; chance fills them first."""
        return MoltharState(self)

    def observation_tensor_shape(self) -> list[int]:
        """Return the flat observation length (see `MoltharState.observation_tensor`)."""
        return [
            _NUM_PLAYERS
            + len(_PEARL_VALUES)
            + _PEARL_DISPLAY_SIZE * (1 + len(_PEARL_VALUES))
            + (_CHAR_DISPLAY_SIZE + _NUM_PLAYERS * _PORTAL_SLOTS) * (1 + len(CHARACTERS))
            + _NUM_PLAYERS  # scores
            + _NUM_PLAYERS  # diamonds
            + _ACTIONS_PER_TURN,
        ]


pyspiel.register_game(_GAME_TYPE, MoltharGame)
