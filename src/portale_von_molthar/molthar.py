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
import itertools
from collections import Counter
from typing import Any, Final, NamedTuple, TypeAlias

import pyspiel

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


class RequirementPart(NamedTuple):
    """One clause of a character's pearl-card activation requirement.

    Several parts combine with logical AND (see RULES.md section 7.10); a
    physical pearl card matched by one part is unavailable to the next.

    Attributes:
        kind: One of "exact", "same", "parity" or "sum".
        values: Exact multiset of pearl values required; used when `kind` is
            "exact".
        size: Number of pearl cards required; used by every kind but "exact".
        even: Whether a "parity" clause needs even (True) or odd (False)
            values.
        total: Target sum of the chosen cards; used when `kind` is "sum".
    """

    kind: str
    values: tuple[int, ...] = ()
    size: int = 0
    even: bool = False
    total: int = 0


Requirement: TypeAlias = tuple[RequirementPart, ...]


def _exact_values(*values: int) -> RequirementPart:
    """Require exactly these pearl values (RULES.md section 7.1)."""
    return RequirementPart("exact", values=values)


def _count_same(size: int) -> RequirementPart:
    """Require `size` pearls of one, unrestricted, shared value (section 7.2)."""
    return RequirementPart("same", size=size)


def _count_odd(size: int) -> RequirementPart:
    """Require `size` pearls with odd values (section 7.5)."""
    return RequirementPart("parity", size=size, even=False)


def _count_even(size: int) -> RequirementPart:
    """Require `size` pearls with even values (section 7.4)."""
    return RequirementPart("parity", size=size, even=True)


def _count_sum(size: int, total: int) -> RequirementPart:
    """Require exactly `size` pearls summing to `total` (section 7.6)."""
    return RequirementPart("sum", size=size, total=total)


class Character(NamedTuple):
    """A green character card: no red or blue special ability.

    Attributes:
        id: Stable identifier matching `docs/character_cards.md`.
        requirement: ANDed pearl requirement clauses paid on activation.
        points: Power points awarded on activation.
        copies: Number of copies of this card in the character deck.
        diamonds: Diamonds awarded to the player on activation.
        diamonds_cost: Diamonds the player must additionally pay to activate
            (RULES.md section 8.2), on top of `requirement`.
    """

    id: str
    requirement: Requirement
    points: int
    copies: int
    diamonds: int = 0
    diamonds_cost: int = 0


# Green cards from docs/character_cards.md; copies sum to 23 as documented there.
_CHARACTERS: Final = (
    Character("goblin", (_count_same(2),), points=1, copies=3),
    Character("fluffy", (_count_same(3),), points=2, copies=2),
    Character("lion", (_exact_values(8, 8, 8, 8),), points=5, copies=1),
    Character("dwarf", (_exact_values(6, 6, 8, 8),), points=3, copies=3),
    Character("hansel_and_gretel", (_exact_values(8, 8),), points=2, copies=2),
    Character("frau_holle", (_exact_values(7, 7, 7, 7),), points=4, copies=2),
    Character("groot", (_count_same(4),), points=3, copies=1),
    Character("bilbo_odd", (_count_odd(3),), points=1, copies=1, diamonds=1),
    Character("bilbo_even", (_count_even(3),), points=1, copies=1, diamonds=1),
    Character(
        "gnome",
        (_count_same(2), _exact_values(6, 6)),
        points=2,
        copies=2,
        diamonds=1,
    ),
    Character(
        "captain_hook",
        (_exact_values(2, 2, 2),),
        points=3,
        copies=1,
        diamonds_cost=1,
    ),
    Character("terminator", (_count_sum(3, 20),), points=2, copies=1),
    Character("unicorn", (_exact_values(1, 2, 3, 4),), points=1, copies=1, diamonds=2),
    Character("trump", (_exact_values(7, 7, 8, 8),), points=3, copies=2, diamonds=1),
)


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
    max_chance_outcomes=max(len(_PEARL_VALUES), len(_CHARACTERS)),
    num_players=_NUM_PLAYERS,
    min_utility=-1.0,
    max_utility=1.0,
    utility_sum=0.0,
    max_game_length=_MAX_NODES,
)


def _match_exact(hand: Counter[int], values: tuple[int, ...]) -> list[int] | None:
    """Match an "exact" clause: every value in `values` must be present in `hand`."""
    needed = Counter(values)
    if all(hand[value] >= copies for value, copies in needed.items()):
        return list(values)
    return None


def _match_same(hand: Counter[int], count: int) -> list[int] | None:
    """Match a "same" clause with the lowest value that has enough copies."""
    for value in sorted(hand):
        if hand[value] >= count:
            return [value] * count
    return None


def _match_parity(hand: Counter[int], count: int, *, even: bool) -> list[int] | None:
    """Match a "parity" clause with the `count` lowest cards of matching parity."""
    pool = [value for value in sorted(hand.elements()) if (value % 2 == 0) == even]
    if len(pool) < count:
        return None
    return pool[:count]


def _match_sum(hand: Counter[int], count: int, total: int) -> list[int] | None:
    """Match a "sum" clause with the lexicographically lowest fitting combination."""
    cards = sorted(hand.elements())
    for combination in itertools.combinations(cards, count):
        if sum(combination) == total:
            return list(combination)
    return None


def _match_part(hand: Counter[int], part: RequirementPart) -> list[int] | None:
    """Match one requirement clause against `hand`, or return None if it cannot be paid."""
    if part.kind == "exact":
        return _match_exact(hand, part.values)
    if part.kind == "same":
        return _match_same(hand, part.size)
    if part.kind == "parity":
        return _match_parity(hand, part.size, even=part.even)
    return _match_sum(hand, part.size, part.total)  # kind == "sum"


def find_combination(hand: Counter[int], character: Character) -> list[int] | None:
    """Find pearl values from `hand` that satisfy every clause of `character`'s requirement.

    Clauses are matched greedily in the order they are declared, each consuming
    the pearls it needs before the next clause is tried. This is deterministic
    and, for every requirement currently in `_CHARACTERS`, also complete: no
    green card's clauses can consume the same pearl in two conflicting ways.

    Args:
        hand: Multiset of pearl values held by the player.
        character: The character card whose requirement must be met.

    Returns:
        The pearl values to discard, or None if the hand cannot pay.
    """
    working = Counter(hand)
    combination: list[int] = []
    for part in character.requirement:
        found = _match_part(working, part)
        if found is None:
            return None
        working.subtract(found)
        combination.extend(found)
    return combination


class MoltharState(pyspiel.State):  # type: ignore[misc]
    """State of a simplified *Portale von Molthar* game."""

    def __init__(self, game: pyspiel.Game) -> None:
        super().__init__(game)
        self._pearl_deck: Counter[int] = Counter(dict.fromkeys(_PEARL_VALUES, _PEARL_COPIES))
        self._pearl_discard: Counter[int] = Counter()
        self._pearl_display: list[int] = []
        self._character_deck: Counter[int] = Counter(
            {index: character.copies for index, character in enumerate(_CHARACTERS)},
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
            f"characters={[_CHARACTERS[card].id for card in self._character_display]}",
        ]
        for player in range(_NUM_PLAYERS):
            portal = [_CHARACTERS[card].id for card in self._portals[player]]
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
            [_CHARACTERS[card].id for card in self._portals[other]] for other in range(_NUM_PLAYERS)
        ]
        return (
            f"p{player} hand={hand} "
            f"pearls={self._pearl_display} "
            f"chars={[_CHARACTERS[card].id for card in self._character_display]} "
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
            character = _CHARACTERS[card]
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
            return f"DealCharacter:{_CHARACTERS[action].id}"
        if action <= Action.TAKE_PEARL_3:
            return f"TakePearl:{self._pearl_display[action]}"
        if action == Action.REFRESH_PEARLS:
            return "RefreshPearls"
        if action <= Action.TAKE_CHARACTER_1:
            slot = action - Action.TAKE_CHARACTER_0
            return f"TakeCharacter:{_CHARACTERS[self._character_display[slot]].id}"
        slot = action - Action.ACTIVATE_0
        return f"Activate:{_CHARACTERS[self._portals[player][slot]].id}"

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
        character = _CHARACTERS[self._portals[player][slot]]
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
            for part in _CHARACTERS[card].requirement:
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
            1.0 if card == index else 0.0 for index in range(len(_CHARACTERS))
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
            + (_CHAR_DISPLAY_SIZE + _NUM_PLAYERS * _PORTAL_SLOTS) * (1 + len(_CHARACTERS))
            + _NUM_PLAYERS  # scores
            + _NUM_PLAYERS  # diamonds
            + _ACTIONS_PER_TURN,
        ]


pyspiel.register_game(_GAME_TYPE, MoltharGame)
