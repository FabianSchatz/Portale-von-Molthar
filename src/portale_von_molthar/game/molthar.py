"""*Portale von Molthar* implemented as an OpenSpiel Python game.

Implementation notes with respect to the printed rules (see module constants):

* Diamonds are tracked as a plain per-player counter rather than as physical
  character cards drawn from the deck. A diamond pays an explicit requirement
  or raises one paid physical pearl by 1 (Amazon also allows lowering it by 1).
  A pearl already reinterpreted by Rumpelstiltskin or Peter Pan cannot also be
  diamond-modified.
* Discarded character cards are never reshuffled into the character deck.
* Going over the hand limit is resolved by the player, who picks one pearl
  value to drop per decision node at the end of the turn; loading the game
  with ``auto_discard=true`` drops them by a built-in heuristic instead.
* Once a player ends a turn with at least 12 points, every other player gets
  two more turns and that player one more; the game stops right before the
  finisher's second extra turn. The highest score wins, ties go to the player
  with more diamonds, and players still tied share the win.

Two to five players are supported via the ``players`` parameter (default 2).
Importing this module registers the game under the short name
``python_portale_von_molthar`` so that it can be created with
``pyspiel.load_game("python_portale_von_molthar(players=4)")``.
"""

import enum
from collections import Counter
from typing import Any, Final, TypeVar

import pyspiel

from portale_von_molthar.game.abilities import (
    AbilityTiming,
    DiamondDecreaseAbility,
    DiscardPortalAbility,
    GainActionsAbility,
    HandLimitAbility,
    KeepPearlAbility,
    NeighborActivationAbility,
    NextPlayerActionAbility,
    PearlToDiamondAbility,
    PearlValueSubstitutionAbility,
    PeekCharacterDeckAbility,
    PortalMarketSwapAbility,
    RedrawHandAbility,
    StealPearlAbility,
    TurnActionsAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.game.cards import CHARACTERS, Character
from portale_von_molthar.game.decisions import (
    BlueAbilityDecision,
    BlueChoice,
    DeckTakeStep,
    HandDrawStep,
    PaymentDecision,
    PeekStep,
    PendingStep,
    Pile,
    RedAbilityDecision,
    RedChoice,
)
from portale_von_molthar.game.payments import (
    PaymentPlan,
    PearlPayment,
    PearlSource,
    ResourceOptions,
    hand_resource_options,
    payment_plans,
)
from portale_von_molthar.game.requirements import (
    ExactValues,
    Parity,
    ParityValues,
    SameValue,
    leaf_requirements,
)

_MIN_PLAYERS: Final = 2
_MAX_PLAYERS: Final = 5
_DEFAULT_PLAYERS: Final = 2
_PEARL_VALUES: Final = tuple(range(1, 9))
_PEARL_COPIES: Final = 7
_PEARL_DISPLAY_SIZE: Final = 4
_CHAR_DISPLAY_SIZE: Final = 2
_PORTAL_SLOTS: Final = 2
# A character is taken from a display slot or, as the last source, blind from the deck.
_CHAR_DECK_SOURCE: Final = _CHAR_DISPLAY_SIZE
_CHAR_SOURCES: Final = _CHAR_DISPLAY_SIZE + 1
_HAND_LIMIT: Final = 5
_ACTIONS_PER_TURN: Final = 3
_MAX_REMAINING_ACTIONS: Final = (
    _ACTIONS_PER_TURN
    + sum(
        character.copies * (character.ability.actions - 1)
        for character in CHARACTERS
        if isinstance(character.ability, GainActionsAbility)
    )
    + sum(
        character.copies * character.ability.actions
        for character in CHARACTERS
        if isinstance(character.ability, TurnActionsAbility)
    )
    + 1
)  # Dementor can add one action to the next player's turn.
_TARGET_POINTS: Final = 12
# Safety net: the game has no forced progress, so players who only
# ever "pass" would loop forever. Discards add up to three more nodes per turn,
# so a random game needs noticeably more of them than the actions alone. The
# cap scales with the player count because every player needs their own turns.
_MAX_NODES_PER_PLAYER: Final = 10000
_AbilityT = TypeVar("_AbilityT")


class Action(enum.IntEnum):
    """The distinct player actions.

    Taking, refreshing, placing, and activating are turn actions. Discard
    actions name a pearl value dropped at the end of a turn. Payment actions
    have stable meanings and never consume an additional turn action. Pearl
    conversion and the Reaper and Mad Hatter choices are free moves.
    ``MAD_HATTER_SWAP_<portal>_<display>`` exchanges a portal slot with a
    character-display slot. ``TAKE_PEARL_DECK`` and ``TAKE_CHARACTER_DECK``
    take the hidden top card of a draw pile. On a full portal,
    ``REPLACE_PORTAL_<portal>_<source>`` discards that portal slot's character
    and takes a new one from a character-display slot or the deck.
    ``ACTIVATE_NEIGHBOR_<slot>`` targets the next player's portal and
    ``ACTIVATE_PREVIOUS_NEIGHBOR_<slot>`` the previous player's portal; the
    latter is only offered with three or more players, when the two differ.
    """

    TAKE_PEARL_0 = 0
    TAKE_PEARL_1 = 1
    TAKE_PEARL_2 = 2
    TAKE_PEARL_3 = 3
    TAKE_PEARL_DECK = 4
    REFRESH_PEARLS = 5
    TAKE_CHARACTER_0 = 6
    TAKE_CHARACTER_1 = 7
    TAKE_CHARACTER_DECK = 8
    REPLACE_PORTAL_0_0 = 9
    REPLACE_PORTAL_0_1 = 10
    REPLACE_PORTAL_0_DECK = 11
    REPLACE_PORTAL_1_0 = 12
    REPLACE_PORTAL_1_1 = 13
    REPLACE_PORTAL_1_DECK = 14
    ACTIVATE_0 = 15
    ACTIVATE_1 = 16
    DISCARD_1 = 17
    DISCARD_2 = 18
    DISCARD_3 = 19
    DISCARD_4 = 20
    DISCARD_5 = 21
    DISCARD_6 = 22
    DISCARD_7 = 23
    DISCARD_8 = 24
    PAY_HAND_1 = 25
    PAY_HAND_2 = 26
    PAY_HAND_3 = 27
    PAY_HAND_4 = 28
    PAY_HAND_5 = 29
    PAY_HAND_6 = 30
    PAY_HAND_7 = 31
    PAY_HAND_8 = 32
    USE_BARBARIAN_1 = 33
    USE_BARBARIAN_2 = 34
    USE_BARBARIAN_3 = 35
    USE_BARBARIAN_4 = 36
    USE_BARBARIAN_5 = 37
    USE_BARBARIAN_6 = 38
    USE_BARBARIAN_7 = 39
    USE_FUCHUR_AS_1 = 40
    USE_FUCHUR_AS_2 = 41
    USE_FUCHUR_AS_3 = 42
    USE_FUCHUR_AS_4 = 43
    USE_FUCHUR_AS_5 = 44
    USE_FUCHUR_AS_6 = 45
    USE_FUCHUR_AS_7 = 46
    USE_FUCHUR_AS_8 = 47
    USE_PHOENIX_AS_8 = 48
    PAY_HAND_3_AS_1_RUMPELSTILTSKIN = 49
    PAY_HAND_3_AS_2_RUMPELSTILTSKIN = 50
    PAY_HAND_3_AS_4_RUMPELSTILTSKIN = 51
    PAY_HAND_3_AS_5_RUMPELSTILTSKIN = 52
    PAY_HAND_3_AS_6_RUMPELSTILTSKIN = 53
    PAY_HAND_3_AS_7_RUMPELSTILTSKIN = 54
    PAY_HAND_3_AS_8_RUMPELSTILTSKIN = 55
    PAY_HAND_1_AS_8_PETER_PAN = 56
    ACTIVATE_NEIGHBOR_0 = 57
    ACTIVATE_NEIGHBOR_1 = 58
    KEEP_NONE = 59
    KEEP_3 = 60
    KEEP_4 = 61
    KEEP_5 = 62
    STEAL_1 = 63
    STEAL_2 = 64
    STEAL_3 = 65
    STEAL_4 = 66
    STEAL_5 = 67
    STEAL_6 = 68
    STEAL_7 = 69
    STEAL_8 = 70
    DISCARD_PORTAL_0 = 71
    DISCARD_PORTAL_1 = 72
    TARGET_PLAYER_0 = 73
    TARGET_PLAYER_1 = 74
    TARGET_PLAYER_2 = 75
    TARGET_PLAYER_3 = 76
    TARGET_PLAYER_4 = 77
    PAY_HAND_1_PLUS_DIAMOND = 78
    PAY_HAND_2_PLUS_DIAMOND = 79
    PAY_HAND_3_PLUS_DIAMOND = 80
    PAY_HAND_4_PLUS_DIAMOND = 81
    PAY_HAND_5_PLUS_DIAMOND = 82
    PAY_HAND_6_PLUS_DIAMOND = 83
    PAY_HAND_7_PLUS_DIAMOND = 84
    PAY_HAND_2_MINUS_DIAMOND_AMAZON = 85
    PAY_HAND_3_MINUS_DIAMOND_AMAZON = 86
    PAY_HAND_4_MINUS_DIAMOND_AMAZON = 87
    PAY_HAND_5_MINUS_DIAMOND_AMAZON = 88
    PAY_HAND_6_MINUS_DIAMOND_AMAZON = 89
    PAY_HAND_7_MINUS_DIAMOND_AMAZON = 90
    PAY_HAND_8_MINUS_DIAMOND_AMAZON = 91
    CONVERT_2_TO_DIAMOND_SNOW_WHITE = 92
    REAPER_KEEP_HAND = 93
    REAPER_REDRAW_HAND = 94
    MAD_HATTER_SKIP = 95
    MAD_HATTER_SWAP_0_0 = 96
    MAD_HATTER_SWAP_0_1 = 97
    MAD_HATTER_SWAP_1_0 = 98
    MAD_HATTER_SWAP_1_1 = 99
    ACTIVATE_PREVIOUS_NEIGHBOR_0 = 100
    ACTIVATE_PREVIOUS_NEIGHBOR_1 = 101


_NEIGHBOR_ACTIONS: Final = frozenset(
    {
        Action.ACTIVATE_NEIGHBOR_0,
        Action.ACTIVATE_NEIGHBOR_1,
        Action.ACTIVATE_PREVIOUS_NEIGHBOR_0,
        Action.ACTIVATE_PREVIOUS_NEIGHBOR_1,
    },
)
_HAND_PAYMENT_ACTIONS: Final = {value: Action.PAY_HAND_1 + value - 1 for value in _PEARL_VALUES}
_VIRTUAL_PAYMENT_ACTIONS: Final = {
    **{(f"barbarian_{value}", value): Action.USE_BARBARIAN_1 + value - 1 for value in range(1, 8)},
    **{("fuchur", value): Action.USE_FUCHUR_AS_1 + value - 1 for value in _PEARL_VALUES},
    ("phoenix", 8): Action.USE_PHOENIX_AS_8,
}
_SUBSTITUTED_PAYMENT_ACTIONS: Final[dict[tuple[str | None, int, int], int]] = {
    ("rumpelstiltskin", 3, 1): Action.PAY_HAND_3_AS_1_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 2): Action.PAY_HAND_3_AS_2_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 4): Action.PAY_HAND_3_AS_4_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 5): Action.PAY_HAND_3_AS_5_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 6): Action.PAY_HAND_3_AS_6_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 7): Action.PAY_HAND_3_AS_7_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 8): Action.PAY_HAND_3_AS_8_RUMPELSTILTSKIN,
    ("peter_pan", 1, 8): Action.PAY_HAND_1_AS_8_PETER_PAN,
}
# Keys are (decreasing ability or None for the base +1, printed value, effective value).
_DIAMOND_PAYMENT_ACTIONS: Final[dict[tuple[str | None, int, int], int]] = {
    **{
        (None, value, value + 1): Action.PAY_HAND_1_PLUS_DIAMOND + value - 1
        for value in range(1, 8)
    },
    **{
        ("amazon", value, value - 1): Action.PAY_HAND_2_MINUS_DIAMOND_AMAZON + value - 2
        for value in range(2, 9)
    },
}
_CONVERSION_ACTIONS: Final = {("snow_white", 2): Action.CONVERT_2_TO_DIAMOND_SNOW_WHITE}
_CONVERSION_KEYS: Final[dict[int, tuple[str, int]]] = {
    action: key for key, action in _CONVERSION_ACTIONS.items()
}
_CHARACTER_INDEX_BY_ID: Final = {character.id: index for index, character in enumerate(CHARACTERS)}


_GAME_TYPE: Final = pyspiel.GameType(
    short_name="python_portale_von_molthar",
    long_name="Portale von Molthar",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.ZERO_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=_MAX_PLAYERS,
    min_num_players=_MIN_PLAYERS,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={"auto_discard": False, "players": _DEFAULT_PLAYERS},
)


class MoltharState(pyspiel.State):  # type: ignore[misc]
    """State of a *Portale von Molthar* game."""

    def __init__(self, game: pyspiel.Game) -> None:
        super().__init__(game)
        self._num_players: int = game.num_players()
        self._max_nodes: int = game.max_game_length()
        self._pearl_deck: Counter[int] = Counter(dict.fromkeys(_PEARL_VALUES, _PEARL_COPIES))
        self._pearl_discard: Counter[int] = Counter()
        self._pearl_display: list[int] = []
        self._character_deck: Counter[int] = Counter(
            {index: character.copies for index, character in enumerate(CHARACTERS)},
        )
        self._character_display: list[int] = []
        self._character_discard: Counter[int] = Counter()
        self._hands: list[Counter[int]] = [Counter() for _ in range(self._num_players)]
        # Lower bound of each hand that all players know: cards taken face up and not
        # provably spent since. Feeds the observation, so agents need no move history.
        self._known_pearls: list[Counter[int]] = [Counter() for _ in range(self._num_players)]
        self._portals: list[list[int]] = [[] for _ in range(self._num_players)]
        self._activated_characters: list[list[int]] = [[] for _ in range(self._num_players)]
        self._scores: list[int] = [0] * self._num_players
        self._diamonds: list[int] = [0] * self._num_players
        self._auto_discard = bool(game.get_parameters().get("auto_discard", False))
        self._cur_player = 0
        # The starting player is the first chance outcome of the game.
        self._starter_drawn = False
        # The player decision or chance draw (Reaper, Dumbledore) to resolve next.
        self._pending_step: PendingStep | None = None
        self._actions_left = _ACTIONS_PER_TURN
        self._next_turn_bonus: list[int] = [0] * self._num_players
        # Top character card known to `_peeked_by`; it is the next card drawn.
        self._peeked_character: int | None = None
        self._peeked_by: int | None = None
        self._nodes = 0
        # Turns still to be played once a player reached the target, else None.
        self._final_turns: int | None = None
        self._game_over = False

    # region properties

    @property
    def actions_left(self) -> int:
        """Actions the current player still has this turn."""
        return self._actions_left

    @property
    def activated_characters(self) -> list[list[str]]:
        """Character ids in each player's activated area, in activation order."""
        return [[CHARACTERS[card].id for card in cards] for cards in self._activated_characters]

    @property
    def character_deck_size(self) -> int:
        """Number of hidden cards left in the character draw deck."""
        return self._character_deck.total()

    @property
    def character_discard_size(self) -> int:
        """Number of cards on the character discard pile."""
        return self._character_discard.total()

    @property
    def character_display(self) -> list[str]:
        """Character ids of the face-up character display, by slot."""
        return [CHARACTERS[card].id for card in self._character_display]

    @property
    def diamonds(self) -> list[int]:
        """Diamonds owned by each player."""
        return list(self._diamonds)

    @property
    def final_turns(self) -> int | None:
        """Turns left once the end of the game was triggered, else ``None``."""
        return self._final_turns

    @property
    def hand_limits(self) -> list[int]:
        """End-of-turn pearl hand limit of each player, including ability bonuses."""
        return [self._hand_limit(player) for player in range(self._num_players)]

    @property
    def hands(self) -> list[list[int]]:
        """Sorted pearl values in each player's hand; private information of each player."""
        return [sorted(hand.elements()) for hand in self._hands]

    @property
    def pearl_deck_size(self) -> int:
        """Number of hidden cards left in the pearl draw deck."""
        return self._pearl_deck.total()

    @property
    def pearl_discard_size(self) -> int:
        """Number of cards on the pearl discard pile."""
        return self._pearl_discard.total()

    @property
    def pearl_display(self) -> list[int]:
        """Pearl values of the face-up pearl display, by slot."""
        return list(self._pearl_display)

    @property
    def peeked_character(self) -> tuple[int, str] | None:
        """``(player, character id)`` of a top character known to that player, else ``None``."""
        if self._peeked_character is None or self._peeked_by is None:
            return None
        return self._peeked_by, CHARACTERS[self._peeked_character].id

    @property
    def pending_step(self) -> PendingStep | None:
        """The immutable decision or chance draw to resolve next, if any."""
        return self._pending_step

    @property
    def portals(self) -> list[list[str]]:
        """Character ids on each player's portal, by slot."""
        return [[CHARACTERS[card].id for card in cards] for cards in self._portals]

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
        for player in range(self._num_players):
            portal = [CHARACTERS[card].id for card in self._portals[player]]
            activated = [CHARACTERS[card].id for card in self._activated_characters[player]]
            hand = sorted(self._hands[player].elements())
            lines.append(
                f"p{player}: score={self._scores[player]} diamonds={self._diamonds[player]} "
                f"portal={portal} activated={activated} hand={hand}",
            )
        peeked = None if self._peeked_character is None else CHARACTERS[self._peeked_character].id
        lines.append(
            f"turn=p{self._cur_player} actions_left={self._actions_left} peeked_character={peeked}",
        )
        return "\n".join(lines)

    # endregion

    # region public methods

    def current_player(self) -> int:
        """Return the mover: a player id, or the terminal/chance sentinel."""
        if self._game_over:
            return pyspiel.PlayerId.TERMINAL
        # Display refills come first so that turn-boundary choices see the new cards.
        if not self._starter_drawn or self._pending_refill() is not None:
            return pyspiel.PlayerId.CHANCE
        if self._pending_step is not None:
            return self._pending_step.actor
        return self._cur_player

    def chance_outcomes(self) -> list[tuple[int, float]]:
        """Return (outcome, probability) pairs for the pending draw.

        Cards are drawn as a weighted choice over the *remaining counts* of the
        deck, which is equivalent to drawing from a shuffled pile but avoids
        modelling the pile order. A character peeked at by Dumbledore is the
        top card, so it is the next character drawn, whether it refills the
        display or is taken blind. The very first chance node picks the
        starting player uniformly.
        """
        if not self._starter_drawn:
            return [(player, 1.0 / self._num_players) for player in range(self._num_players)]
        deck = self._pending_refill()
        if deck is None:
            raise ValueError("chance_outcomes called on a non-chance node")
        # A peek only starts while nothing is peeked, so this never forces the peek itself.
        if deck is self._character_deck and self._peeked_character is not None:
            return [(self._peeked_character, 1.0)]
        total = deck.total()
        return [(key, count / total) for key, count in sorted(deck.items()) if count]

    def is_terminal(self) -> bool:
        """Return whether the game has ended."""
        return self._game_over

    def returns(self) -> list[float]:
        """Return the zero-sum payoff.

        Players are ranked by score, then by diamonds. The players tied for
        the best rank share +1 and all other players share -1. Two players
        thus get +1/-1, and a tie among everyone is 0.
        """
        ranks = list(zip(self._scores, self._diamonds, strict=True))
        best = max(ranks)
        winners = ranks.count(best)
        if not self._game_over or winners == self._num_players:
            return [0.0] * self._num_players
        losers = self._num_players - winners
        return [1.0 / winners if rank == best else -1.0 / losers for rank in ranks]

    def observation_string(self, player: int) -> str:
        """Return the state as seen by `player` (own hand, public everything else)."""
        hand = sorted(self._hands[player].elements())
        portals = [
            [CHARACTERS[card].id for card in self._portals[other]]
            for other in range(self._num_players)
        ]
        activated = [
            [CHARACTERS[card].id for card in self._activated_characters[other]]
            for other in range(self._num_players)
        ]
        paid = self._selected_payment_labels()
        decision = self._pending_step
        red_target = decision.target_player if isinstance(decision, RedAbilityDecision) else None
        revealed_hand = (
            sorted(self._hands[decision.target_player].elements())
            if isinstance(decision, RedAbilityDecision)
            and decision.choice is RedChoice.STEAL_PEARL
            and decision.actor == player
            and decision.target_player is not None
            else None
        )
        payment_target = (
            f"p{decision.target_owner}:{decision.target_slot}"
            if isinstance(decision, PaymentDecision)
            else "none"
        )
        peeked = self._visible_peeked_character(player)
        return (
            f"p{player} hand={hand} "
            f"pearls={self._pearl_display} "
            f"chars={[CHARACTERS[card].id for card in self._character_display]} "
            f"portals={portals} activated={activated} scores={self._scores} "
            f"character_discard={dict(self._character_discard)} "
            f"diamonds={self._diamonds} next_turn_bonus={self._next_turn_bonus} "
            f"final_turns={self._final_turns} "
            f"to_move=p{self._cur_player} "
            f"left={self._actions_left} payment_target={payment_target} paid={list(paid)} "
            f"red_choice={decision.choice if isinstance(decision, RedAbilityDecision) else None} "
            f"red_target={red_target} "
            f"revealed_hand={revealed_hand} "
            f"hand_limits={[self._hand_limit(other) for other in range(self._num_players)]} "
            f"peeked_character={None if peeked is None else CHARACTERS[peeked].id} "
            f"blue_choice={decision.choice if isinstance(decision, BlueAbilityDecision) else None}"
        )

    def observation_tensor(self, player: int) -> list[float]:
        """Return the flat observation of `player`.

        Args:
            player: Player receiving the imperfect-information observation.

        Returns:
            Flat tensor ordered as observing-player one-hot, own-hand counts,
            pearl-display slots, character-display slots, portal slots,
            activated-character counts, character-discard counts, hand sizes,
            publicly known hand cards per player (cards taken face up and not
            spent since), pearl-discard counts, pearl- and character-deck sizes, scores,
            diamonds, queued action bonuses, remaining final turns (0 before
            the end is triggered), remaining actions, the top
            character card if this player peeked at it, the pending blue
            choice kind, and pending-payment details. Each card slot uses an
            empty/card-type one-hot; count-valued sections use ascending card
            or pearl value.
        """
        planes: list[float] = []
        # one-hot encoding of the player receiving this observation
        planes.extend(1.0 if player == index else 0.0 for index in range(self._num_players))
        # count of each pearl value in the player's hand
        planes.extend(float(self._hands[player][value]) for value in _PEARL_VALUES)
        for slot in range(_PEARL_DISPLAY_SIZE):
            # for each pearl card slot, one-hot encoding of the value ("0" is an empty slot)
            value = self._pearl_display[slot] if slot < len(self._pearl_display) else 0
            planes.extend(1.0 if value == option else 0.0 for option in (0, *_PEARL_VALUES))
        for slot in range(_CHAR_DISPLAY_SIZE):
            planes.extend(self._character_one_hot(self._character_display, slot))
        for other in range(self._num_players):
            for slot in range(_PORTAL_SLOTS):
                planes.extend(self._character_one_hot(self._portals[other], slot))
        for other in range(self._num_players):
            activated = Counter(self._activated_characters[other])
            planes.extend(float(activated[card]) for card in range(len(CHARACTERS)))
        planes.extend(float(self._character_discard[card]) for card in range(len(CHARACTERS)))
        # public pearl information that otherwise only the move history would reveal
        planes.extend(float(hand.total()) for hand in self._hands)
        for known in self._known_pearls:
            planes.extend(float(known[value]) for value in _PEARL_VALUES)
        planes.extend(float(self._pearl_discard[value]) for value in _PEARL_VALUES)
        planes.append(float(self._pearl_deck.total()))
        planes.append(float(self._character_deck.total()))
        planes.extend(score / _TARGET_POINTS for score in self._scores)
        planes.extend(float(diamonds) for diamonds in self._diamonds)
        planes.extend(float(bonus) for bonus in self._next_turn_bonus)
        # remaining final turns, 0 while the end of the game is not triggered
        planes.append(0.0 if self._final_turns is None else float(self._final_turns))
        planes.extend(
            1.0 if self._actions_left == step + 1 else 0.0 for step in range(_MAX_REMAINING_ACTIONS)
        )
        peeked = self._visible_peeked_character(player)
        planes.extend(self._character_one_hot([] if peeked is None else [peeked], 0))
        decision = self._pending_step
        planes.extend(
            1.0 if isinstance(decision, BlueAbilityDecision) and decision.choice is choice else 0.0
            for choice in BlueChoice
        )
        # Pending activation data is public. Printed and effective counts are
        # separate because abilities and diamonds may modify physical pearls.
        payment_pending = isinstance(decision, PaymentDecision)
        target_owner = decision.target_owner if payment_pending else None
        slot_paid = decision.target_slot if payment_pending else None
        selected = decision.selected if payment_pending else ()
        printed_values = self._selected_physical_values()
        effective_values = tuple(payment.effective_value for payment in selected)
        diamonds_spent = sum(payment.diamonds_spent for payment in selected)
        virtual_sources = Counter(
            _CHARACTER_INDEX_BY_ID[payment.source_id]
            for payment in selected
            if payment.source is PearlSource.VIRTUAL and payment.source_id is not None
        )
        planes.append(float(payment_pending))
        planes.extend(1.0 if other == target_owner else 0.0 for other in range(self._num_players))
        planes.extend(1.0 if slot == slot_paid else 0.0 for slot in range(_PORTAL_SLOTS))
        planes.extend(float(Counter(printed_values)[value]) for value in _PEARL_VALUES)
        planes.extend(float(Counter(effective_values)[value]) for value in _PEARL_VALUES)
        planes.extend(float(virtual_sources[card]) for card in range(len(CHARACTERS)))
        planes.append(float(diamonds_spent))
        # Only the Tinkerbell actor may inspect the opposing hand while choosing.
        revealed = (
            self._hands[decision.target_player]
            if isinstance(decision, RedAbilityDecision)
            and decision.choice is RedChoice.STEAL_PEARL
            and decision.actor == player
            and decision.target_player is not None
            else Counter()
        )
        planes.extend(
            1.0
            if isinstance(decision, RedAbilityDecision) and decision.target_player == other
            else 0.0
            for other in range(self._num_players)
        )
        planes.extend(float(revealed[value]) for value in _PEARL_VALUES)
        planes.extend(
            1.0 if isinstance(decision, RedAbilityDecision) and decision.choice is choice else 0.0
            for choice in RedChoice
        )
        return planes

    # endregion

    # region private methods

    def _legal_actions(self, player: int) -> list[int]:
        """Return the sorted legal actions for `player`."""
        decision = self._pending_step
        if isinstance(decision, BlueAbilityDecision):
            return self._blue_choice_actions(player, decision)
        if isinstance(decision, RedAbilityDecision):
            return self._red_choice_actions(player, decision)
        if isinstance(decision, PaymentDecision):
            return self._pending_decision_actions(player, decision)
        if self._must_discard(player):
            return [
                Action.DISCARD_1 + value - 1
                for value in _PEARL_VALUES
                if self._hands[player][value]
            ]
        return self._turn_actions(player)

    def _turn_actions(self, player: int) -> list[int]:
        """Return the sorted turn actions and free moves for `player` without a decision."""
        actions: list[int] = list(range(len(self._pearl_display)))
        if self._pearl_display:
            actions.append(Action.REFRESH_PEARLS)
        if self._pearl_deck.total():
            actions.append(Action.TAKE_PEARL_DECK)
        actions.extend(self._character_take_actions(player))
        for slot, card in enumerate(self._portals[player]):
            character = CHARACTERS[card]
            if self._activation_plans(player, character):
                actions.append(Action.ACTIVATE_0 + slot)
        actions.extend(self._neighbor_activation_actions(player))
        for card_id, ability in self._owned_abilities(player, PearlToDiamondAbility):
            if self._hands[player][ability.printed_value]:
                actions.append(_CONVERSION_ACTIONS[(card_id, ability.printed_value)])
        # A player is never stuck: refreshing an empty display is a legal pass.
        return sorted(actions) if actions else [int(Action.REFRESH_PEARLS)]

    def _neighbor_activation_actions(self, player: int) -> list[int]:
        """Return the actions activating a payable Irrlicht on a neighboring portal."""
        first_actions = [Action.ACTIVATE_NEIGHBOR_0]
        if self._num_players > _MIN_PLAYERS:  # with two players both neighbors coincide
            first_actions.append(Action.ACTIVATE_PREVIOUS_NEIGHBOR_0)
        actions: list[int] = []
        for first_action in first_actions:
            target_owner, _ = self._neighbor_target(player, first_action)
            for slot, card in enumerate(self._portals[target_owner]):
                character = CHARACTERS[card]
                if isinstance(
                    character.ability,
                    NeighborActivationAbility,
                ) and self._activation_plans(player, character):
                    actions.append(first_action + slot)
        return actions

    def _neighbor_target(self, player: int, action: int) -> tuple[int, int]:
        """Return the ``(portal owner, portal slot)`` addressed by a neighbor activation.

        Args:
            player: Player activating the neighbor's character.
            action: An ``ACTIVATE_NEIGHBOR_<slot>`` or ``ACTIVATE_PREVIOUS_NEIGHBOR_<slot>``.

        Returns:
            The next or previous player in turn order and the slot on their portal.
        """
        if action <= Action.ACTIVATE_NEIGHBOR_1:
            return (player + 1) % self._num_players, action - Action.ACTIVATE_NEIGHBOR_0
        return (player - 1) % self._num_players, action - Action.ACTIVATE_PREVIOUS_NEIGHBOR_0

    def _character_take_actions(self, player: int) -> list[int]:
        """Return the actions putting a display or deck character on `player`'s portal.

        A portal with a free slot takes the character directly. A full portal
        first discards one of its characters, so every portal slot is combined
        with every available source.
        """
        sources = list(range(len(self._character_display)))
        if self._character_deck.total():
            sources.append(_CHAR_DECK_SOURCE)
        if len(self._portals[player]) < _PORTAL_SLOTS:
            return [self._take_character_action(source) for source in sources]
        return [
            int(Action.REPLACE_PORTAL_0_0 + portal_slot * _CHAR_SOURCES + source)
            for portal_slot in range(_PORTAL_SLOTS)
            for source in sources
        ]

    def _apply_action(self, action: int) -> None:
        """Apply `action`, which is a chance outcome on chance nodes."""
        self._nodes += 1
        step = self._pending_step
        if not self._starter_drawn:
            self._cur_player = action
            self._starter_drawn = True
        elif (deck := self._pending_refill()) is not None:
            self._draw(deck, action)
        elif isinstance(step, (PaymentDecision, RedAbilityDecision, BlueAbilityDecision)):
            self._apply_decision(step, action)
        elif self._must_discard(self._cur_player):
            self._discard(self._cur_player, action - Action.DISCARD_1 + 1)
            if not self._must_discard(self._cur_player):
                self._end_turn()
        elif action in _CONVERSION_KEYS:
            self._convert_pearl_to_diamond(self._cur_player, action)
        else:
            self._apply_player_action(action)
            if self._pending_step is None:
                self._end_action()
        # Player decisions block the reshuffle (Puss in Boots takes back a
        # discarded pearl); chance steps may need the reshuffled cards.
        step = self._pending_step
        player_decision = step is not None and not isinstance(
            step,
            (HandDrawStep, DeckTakeStep, PeekStep),
        )
        if not player_decision and not self._pearl_deck.total():
            # ponytail: instant reshuffle of the discard pile; the real game
            # shuffles once, which only matters for card counting.
            self._pearl_deck += self._pearl_discard
            self._pearl_discard.clear()
        if self._nodes >= self._max_nodes:
            self._game_over = True

    def _apply_decision(
        self,
        decision: PaymentDecision | RedAbilityDecision | BlueAbilityDecision,
        action: int,
    ) -> None:
        """Apply `action` to the pending player decision.

        Payment and red choices belong to the activation action and consume it
        once resolved; blue turn-boundary choices never consume an action.
        """
        if isinstance(decision, BlueAbilityDecision):
            self._apply_blue_choice(decision, action)
            return
        if isinstance(decision, RedAbilityDecision):
            self._apply_red_choice(decision, action)
        else:
            self._apply_pending_decision(decision.actor, decision, action)
        if self._pending_step is None:
            self._end_action()

    def _action_to_string(self, player: int, action: int) -> str:
        """Return a label for `action` as taken by `player`."""
        if player == pyspiel.PlayerId.CHANCE:
            label = self._chance_label(action)
        elif action <= Action.TAKE_PEARL_3:
            label = f"TakePearl:{self._pearl_display[action]}"
        elif action == Action.TAKE_PEARL_DECK:
            label = "TakePearlDeck"
        elif action == Action.REFRESH_PEARLS:
            label = "RefreshPearls"
        elif action <= Action.TAKE_CHARACTER_1:
            slot = action - Action.TAKE_CHARACTER_0
            label = f"TakeCharacter:{CHARACTERS[self._character_display[slot]].id}"
        elif action == Action.TAKE_CHARACTER_DECK:
            label = "TakeCharacterDeck"
        elif action <= Action.REPLACE_PORTAL_1_DECK:
            portal_slot, source = divmod(action - Action.REPLACE_PORTAL_0_0, _CHAR_SOURCES)
            old_id = CHARACTERS[self._portals[player][portal_slot]].id
            new_id = (
                "deck"
                if source == _CHAR_DECK_SOURCE
                else CHARACTERS[self._character_display[source]].id
            )
            label = f"ReplaceCharacter:{old_id}->{new_id}"
        elif action <= Action.ACTIVATE_1:
            slot = action - Action.ACTIVATE_0
            label = f"Activate:{CHARACTERS[self._portals[player][slot]].id}"
        elif action in _NEIGHBOR_ACTIONS:
            target_owner, slot = self._neighbor_target(player, action)
            character = CHARACTERS[self._portals[target_owner][slot]]
            previous = "Previous" if action >= Action.ACTIVATE_PREVIOUS_NEIGHBOR_0 else ""
            label = f"Activate{previous}Neighbor:{character.id}"
        else:
            label = self._choice_label(action)
        return label

    def _chance_label(self, action: int) -> str:
        """Return the label for a chance outcome at the pending draw.

        The branches mirror the resolution order of `_draw`.
        """
        if not self._starter_drawn:
            return f"StartingPlayer:p{action}"
        blind_take = isinstance(self._pending_step, DeckTakeStep)
        if self._pending_refill() is self._pearl_deck:
            if len(self._pearl_display) < _PEARL_DISPLAY_SIZE or not blind_take:
                return f"DealPearl:{action}"
            return f"TakeTopPearl:{action}"
        if len(self._character_display) < _CHAR_DISPLAY_SIZE:
            return f"DealCharacter:{CHARACTERS[action].id}"
        if blind_take:
            return f"TakeTopCharacter:{CHARACTERS[action].id}"
        return f"PeekCharacter:{CHARACTERS[action].id}"

    def _choice_label(self, action: int) -> str:
        """Return the label for a decision, discard, or free-move action."""
        decision = self._pending_step
        if isinstance(decision, BlueAbilityDecision):
            return self._blue_choice_label(decision.actor, action)
        if action in _CONVERSION_KEYS:
            card_id, value = _CONVERSION_KEYS[action]
            return f"ConvertToDiamond:{value}:{card_id}"
        if isinstance(decision, RedAbilityDecision):
            return self._red_choice_label(decision.choice, action)
        if action <= Action.DISCARD_8:
            return f"Discard:{action - Action.DISCARD_1 + 1}"
        if isinstance(decision, PaymentDecision):
            return self._payment_label(self._payment_option_for_action(decision, action))
        message = f"action {action} is not meaningful in the current state"
        raise ValueError(message)

    def _pending_refill(self) -> Counter[int] | None:
        """Return the deck that must be drawn from before the next player move.

        Display refills come first, then a pending chance step (Reaper hand
        draw, blind take from a draw pile, or Dumbledore peek). A hand draw
        always finds cards because its player's discarded hand is reshuffled
        in when the deck runs out, a blind take is only offered while its pile
        holds cards, and a peek is dropped when a refill empties the character
        deck.
        """
        if len(self._pearl_display) < _PEARL_DISPLAY_SIZE and self._pearl_deck.total():
            return self._pearl_deck
        if len(self._character_display) < _CHAR_DISPLAY_SIZE and self._character_deck.total():
            return self._character_deck
        if isinstance(self._pending_step, HandDrawStep):
            return self._pearl_deck
        if isinstance(self._pending_step, DeckTakeStep):
            pearl = self._pending_step.pile is Pile.PEARL
            return self._pearl_deck if pearl else self._character_deck
        if isinstance(self._pending_step, PeekStep):
            return self._character_deck
        return None

    def _draw(self, deck: Counter[int], outcome: int) -> None:
        """Resolve the chance `outcome` drawn from `deck`, in `_pending_refill` order."""
        step = self._pending_step
        if deck is self._pearl_deck and len(self._pearl_display) < _PEARL_DISPLAY_SIZE:
            deck[outcome] -= 1
            self._pearl_display.append(outcome)
        elif deck is self._character_deck and len(self._character_display) < _CHAR_DISPLAY_SIZE:
            deck[outcome] -= 1
            self._character_display.append(outcome)
            # chance_outcomes forces a peeked card to be the next one drawn.
            self._peeked_character = None
            self._peeked_by = None
            if isinstance(step, PeekStep) and not deck.total():
                self._pending_step = None
                self._offer_portal_swap()
        elif isinstance(step, HandDrawStep):
            deck[outcome] -= 1
            self._hands[step.player][outcome] += 1
            if step.remaining > 1:
                self._pending_step = HandDrawStep(step.player, step.remaining - 1)
                return
            self._pending_step = None
            self._finish_turn()
        elif isinstance(step, DeckTakeStep):
            deck[outcome] -= 1
            if step.pile is Pile.PEARL:
                self._hands[step.player][outcome] += 1
            else:
                self._portals[step.player].append(outcome)
                self._peeked_character = None
                self._peeked_by = None
            self._pending_step = None
            self._end_action()  # the blind take was the action that started this draw
        elif isinstance(step, PeekStep):
            # Peeking leaves the card on top of the deck.
            self._peeked_character = outcome
            self._peeked_by = step.player
            self._pending_step = None
            self._offer_portal_swap()
        else:
            message = "no chance draw is pending"
            raise RuntimeError(message)

    def _apply_player_action(self, action: int) -> None:
        """Apply one of the three per-turn actions of the current player."""
        player = self._cur_player
        if action <= Action.TAKE_PEARL_3:
            value = self._pearl_display.pop(action)
            self._hands[player][value] += 1
            self._known_pearls[player][value] += 1
        elif action == Action.TAKE_PEARL_DECK:
            self._pending_step = DeckTakeStep(player, Pile.PEARL)
        elif action == Action.REFRESH_PEARLS:
            self._pearl_discard += Counter(self._pearl_display)
            self._pearl_display.clear()
        elif action <= Action.TAKE_CHARACTER_1:
            self._take_character(player, action - Action.TAKE_CHARACTER_0)
        elif action == Action.TAKE_CHARACTER_DECK:
            self._take_character(player, _CHAR_DECK_SOURCE)
        elif action <= Action.REPLACE_PORTAL_1_DECK:
            portal_slot, source = divmod(action - Action.REPLACE_PORTAL_0_0, _CHAR_SOURCES)
            self._character_discard[self._portals[player].pop(portal_slot)] += 1
            self._take_character(player, source)
        elif action <= Action.ACTIVATE_1:
            self._activate(player, player, action - Action.ACTIVATE_0)
        elif action in _NEIGHBOR_ACTIONS:
            self._activate(player, *self._neighbor_target(player, action))
        else:
            message = f"action {action} is not a normal turn action"
            raise ValueError(message)

    @staticmethod
    def _take_character_action(source: int) -> int:
        """Return the action putting a character from `source` on a portal with a free slot.

        Args:
            source: Character-display slot, or `_CHAR_DECK_SOURCE` for the deck.

        Returns:
            ``TAKE_CHARACTER_<slot>`` for a display slot, otherwise ``TAKE_CHARACTER_DECK``.
        """
        if source == _CHAR_DECK_SOURCE:
            return int(Action.TAKE_CHARACTER_DECK)
        return int(Action.TAKE_CHARACTER_0 + source)

    def _take_character(self, player: int, source: int) -> None:
        """Put a character from `source` onto `player`'s portal.

        A display card moves immediately and the display is refilled by the
        next chance node. A deck card is unknown, so a chance step resolves it
        and finishes the action.

        Args:
            player: Player whose portal receives the character.
            source: Character-display slot, or `_CHAR_DECK_SOURCE` for the deck.
        """
        if source == _CHAR_DECK_SOURCE:
            self._pending_step = DeckTakeStep(player, Pile.CHARACTER)
        else:
            self._portals[player].append(self._character_display.pop(source))

    def _activate(self, player: int, target_owner: int, slot: int) -> None:
        """Start paying for a character on `target_owner`'s portal.

        The planner separates matching from mutation and preserves the source
        and effective value of every resource. A pending decision is only
        created when more than one complete plan is possible.
        """
        character = CHARACTERS[self._portals[target_owner][slot]]
        if player != target_owner and not isinstance(
            character.ability,
            NeighborActivationAbility,
        ):
            message = f"cannot activate {character.id} from another player's portal"
            raise ValueError(message)
        plans = self._activation_plans(player, character)
        if not plans:
            message = f"cannot activate {character.id} with the current hand"
            raise ValueError(message)
        decision = PaymentDecision(player, target_owner, slot, plans)
        plan = decision.resolved_plan
        if plan is not None:
            self._resolve_activation(player, target_owner, slot, plan)
            return
        self._pending_step = decision

    def _activation_plans(self, player: int, character: Character) -> tuple[PaymentPlan, ...]:
        """Return complete currently available plans for activating `character`."""
        return payment_plans(
            self._activation_resources(player),
            character.requirement,
            available_diamonds=self._diamonds[player],
            required_diamonds=character.diamonds_cost,
        )

    def _activation_resources(self, player: int) -> ResourceOptions:
        """Return physical and persistent virtual resources available to `player`."""
        resources: list[tuple[PearlPayment, ...]] = []
        decreasers = self._owned_abilities(player, DiamondDecreaseAbility)
        for group in hand_resource_options(self._hands[player]):
            base_payment = group[0]
            options = list(group)
            for card in self._activated_characters[player]:
                character = CHARACTERS[card]
                ability = character.ability
                if not isinstance(ability, PearlValueSubstitutionAbility):
                    continue
                if ability.timing is not AbilityTiming.DURING_TURN:
                    continue
                if base_payment.printed_value != ability.printed_value:
                    continue
                options.extend(
                    PearlPayment(
                        PearlSource.HAND,
                        value,
                        printed_value=ability.printed_value,
                        modifiers=(character.id,),
                    )
                    for value in ability.effective_values
                )
            if self._diamonds[player]:
                options.extend(self._diamond_options(base_payment, options, decreasers))
            resources.append(tuple(options))
        for card in self._activated_characters[player]:
            character = CHARACTERS[card]
            ability = character.ability
            if not isinstance(ability, VirtualPearlAbility):
                continue
            if ability.timing is not AbilityTiming.DURING_TURN:
                continue
            resources.append(
                tuple(
                    PearlPayment(
                        PearlSource.VIRTUAL,
                        value,
                        source_id=character.id,
                        discard=False,
                    )
                    for value in ability.values
                ),
            )
        return tuple(resources)

    @staticmethod
    def _diamond_options(
        base_payment: PearlPayment,
        options: list[PearlPayment],
        decreasers: list[tuple[str, DiamondDecreaseAbility]],
    ) -> list[PearlPayment]:
        """Return diamond-modified interpretations of one physical pearl.

        One diamond raises the printed value by 1 (RULES.md section 8.1), or
        lowers it by 1 when a decreasing ability such as Amazon is active. A
        value already reachable without a diamond is skipped as dominated.

        Args:
            base_payment: Unmodified use of the physical pearl at its printed value.
            options: Interpretations already offered for this pearl.
            decreasers: Activated ``(character id, ability)`` pairs allowing -1.

        Returns:
            Additional mutually exclusive interpretations, each spending one diamond.
        """
        value = base_payment.effective_value
        free_values = {option.effective_value for option in options}
        modified: list[tuple[int, tuple[str, ...]]] = [(value + 1, ())]
        modified.extend((value - 1, (card_id,)) for card_id, _ in decreasers)
        return [
            PearlPayment(
                PearlSource.HAND,
                effective,
                printed_value=value,
                diamonds_spent=1,
                modifiers=modifiers,
            )
            for effective, modifiers in modified
            if 1 <= effective <= 8 and effective not in free_values
        ]

    def _pending_decision_actions(
        self,
        player: int,
        decision: PaymentDecision,
    ) -> list[int]:
        """Map semantic options of `decision` to OpenSpiel action identifiers."""
        if player != decision.actor:
            return []
        return sorted({self._payment_action(option) for option in decision.options()})

    def _apply_pending_decision(
        self,
        player: int,
        decision: PaymentDecision,
        action: int,
    ) -> None:
        """Apply one OpenSpiel action to a pending semantic decision."""
        if player != decision.actor:
            message = "only the decision actor may choose a payment"
            raise ValueError(message)
        option = self._payment_option_for_action(decision, action)
        updated = decision.choose(option)
        plan = updated.resolved_plan
        if plan is None:
            self._pending_step = updated
            return
        self._pending_step = None
        self._resolve_activation(
            player,
            updated.target_owner,
            updated.target_slot,
            plan,
        )

    def _resolve_activation(
        self,
        player: int,
        target_owner: int,
        slot: int,
        plan: PaymentPlan,
    ) -> None:
        """Commit `plan`, move the target to the activated area, and grant rewards."""
        character_index = self._portals[target_owner][slot]
        character = CHARACTERS[character_index]
        for value in plan.discarded_values:
            self._hands[player][value] -= 1
            self._pearl_discard[value] += 1
            self._forget_known(player, value)
        self._hands[player] = +self._hands[player]  # drop zero counts
        self._portals[target_owner].pop(slot)
        self._activated_characters[player].append(character_index)
        self._scores[player] += character.points
        self._diamonds[player] += character.diamonds - plan.diamonds_spent
        if isinstance(character.ability, (GainActionsAbility, TurnActionsAbility)):
            # Turn-action characters also pay out in the turn they are activated.
            self._actions_left += character.ability.actions
        elif isinstance(character.ability, NextPlayerActionAbility):
            self._next_turn_bonus[(player + 1) % self._num_players] += 1
        elif isinstance(character.ability, KeepPearlAbility):
            values = tuple(sorted(set(plan.discarded_values)))
            if values:
                self._pending_step = RedAbilityDecision(
                    player,
                    RedChoice.KEEP_PEARL,
                    (0, *values),
                )
        elif isinstance(character.ability, StealPearlAbility):
            targets = tuple(
                other
                for other in range(self._num_players)
                if other != player and self._hands[other].total()
            )
            if targets:
                self._pending_step = RedAbilityDecision(player, RedChoice.STEAL_TARGET, targets)
        elif isinstance(character.ability, DiscardPortalAbility):
            targets = tuple(
                other
                for other in range(self._num_players)
                if other != player and self._portals[other]
            )
            if targets:
                self._pending_step = RedAbilityDecision(
                    player,
                    RedChoice.DISCARD_TARGET,
                    targets,
                )

    @staticmethod
    def _red_choice_action(choice: RedChoice, value: int) -> int:
        """Map one red ability option to its stable OpenSpiel action."""
        if choice in (RedChoice.STEAL_TARGET, RedChoice.DISCARD_TARGET):
            return int(Action.TARGET_PLAYER_0 + value)
        if choice is RedChoice.KEEP_PEARL:
            return int(Action.KEEP_NONE if value == 0 else Action.KEEP_3 + value - 3)
        if choice is RedChoice.STEAL_PEARL:
            return int(Action.STEAL_1 + value - 1)
        return int(Action.DISCARD_PORTAL_0 + value)

    def _red_choice_actions(self, player: int, decision: RedAbilityDecision) -> list[int]:
        """Return actions available to the red ability's actor."""
        if player != decision.actor:
            return []
        return [self._red_choice_action(decision.choice, value) for value in decision.options]

    @staticmethod
    def _red_choice_label(choice: RedChoice, action: int) -> str:
        """Return the visible label for one red ability action."""
        if choice in (RedChoice.STEAL_TARGET, RedChoice.DISCARD_TARGET):
            return f"TargetPlayer:{action - Action.TARGET_PLAYER_0}"
        if choice is RedChoice.KEEP_PEARL:
            value = action - Action.KEEP_3 + 3
            return "KeepNoPearl" if action == Action.KEEP_NONE else f"KeepPearl:{value}"
        if choice is RedChoice.STEAL_PEARL:
            return f"StealPearl:{action - Action.STEAL_1 + 1}"
        return f"DiscardPortal:{action - Action.DISCARD_PORTAL_0}"

    def _apply_red_choice(self, decision: RedAbilityDecision, action: int) -> None:
        """Resolve a red ability choice without consuming another turn action."""
        if action not in self._red_choice_actions(decision.actor, decision):
            message = "red ability action is not currently offered"
            raise ValueError(message)
        value = next(
            option
            for option in decision.options
            if self._red_choice_action(decision.choice, option) == action
        )
        if decision.choice is RedChoice.STEAL_TARGET:
            values = tuple(pearl for pearl in _PEARL_VALUES if self._hands[value][pearl])
            self._pending_step = RedAbilityDecision(
                decision.actor,
                RedChoice.STEAL_PEARL,
                values,
                value,
            )
            return
        if decision.choice is RedChoice.DISCARD_TARGET:
            slots = tuple(range(len(self._portals[value])))
            self._pending_step = RedAbilityDecision(
                decision.actor,
                RedChoice.DISCARD_PORTAL,
                slots,
                value,
            )
            return
        other = decision.target_player
        if decision.choice is RedChoice.KEEP_PEARL and value:
            self._pearl_discard[value] -= 1
            self._pearl_discard = +self._pearl_discard
            self._hands[decision.actor][value] += 1
            self._known_pearls[decision.actor][value] += 1
        elif decision.choice is RedChoice.STEAL_PEARL:
            if other is None:
                raise RuntimeError("steal decision has no target player")
            self._hands[other][value] -= 1
            self._hands[other] = +self._hands[other]
            self._hands[decision.actor][value] += 1
            self._forget_known(other, value)
            self._known_pearls[decision.actor][value] += 1  # the stolen value is announced
        elif decision.choice is RedChoice.DISCARD_PORTAL:
            if other is None:
                raise RuntimeError("discard decision has no target player")
            card = self._portals[other].pop(value)
            self._character_discard[card] += 1
        self._pending_step = None

    def _blue_choice_actions(self, player: int, decision: BlueAbilityDecision) -> list[int]:
        """Return actions available to the blue ability's owner."""
        if player != decision.actor:
            return []
        if decision.choice is BlueChoice.REDRAW_HAND:
            return [int(Action.REAPER_KEEP_HAND), int(Action.REAPER_REDRAW_HAND)]
        return [int(Action.MAD_HATTER_SKIP)] + [
            int(Action.MAD_HATTER_SWAP_0_0 + portal_slot * _CHAR_DISPLAY_SIZE + display_slot)
            for portal_slot in range(len(self._portals[player]))
            for display_slot in range(len(self._character_display))
        ]

    def _blue_choice_label(self, player: int, action: int) -> str:
        """Return the visible label for one blue ability action."""
        if action == Action.REAPER_KEEP_HAND:
            return "ReaperKeepHand"
        if action == Action.REAPER_REDRAW_HAND:
            return "ReaperRedrawHand"
        if action == Action.MAD_HATTER_SKIP:
            return "MadHatterSkip"
        portal_slot, display_slot = divmod(action - Action.MAD_HATTER_SWAP_0_0, _CHAR_DISPLAY_SIZE)
        portal_id = CHARACTERS[self._portals[player][portal_slot]].id
        display_id = CHARACTERS[self._character_display[display_slot]].id
        return f"MadHatterSwap:{portal_id}<->{display_id}"

    def _apply_blue_choice(self, decision: BlueAbilityDecision, action: int) -> None:
        """Resolve a Reaper or Mad Hatter choice without consuming a turn action."""
        if action not in self._blue_choice_actions(decision.actor, decision):
            message = "blue ability action is not currently offered"
            raise ValueError(message)
        self._pending_step = None
        player = decision.actor
        if decision.choice is BlueChoice.SWAP_PORTAL:
            if action != Action.MAD_HATTER_SKIP:
                portal_slot, display_slot = divmod(
                    action - Action.MAD_HATTER_SWAP_0_0,
                    _CHAR_DISPLAY_SIZE,
                )
                portal = self._portals[player]
                display = self._character_display
                portal[portal_slot], display[display_slot] = (
                    display[display_slot],
                    portal[portal_slot],
                )
            return
        if action == Action.REAPER_REDRAW_HAND:
            # The discarded hand is in the discard pile, so the deck plus the
            # discard pile always hold enough cards for every redraw.
            self._pending_step = HandDrawStep(player, self._hands[player].total())
            self._pearl_discard += self._hands[player]
            self._hands[player] = Counter()
            self._known_pearls[player] = Counter()
            return
        self._finish_turn()

    def _convert_pearl_to_diamond(self, player: int, action: int) -> None:
        """Turn one hand pearl into a diamond as a free move (Snow White)."""
        if action not in self._legal_actions(player):
            message = "pearl conversion is not currently offered"
            raise ValueError(message)
        _, value = _CONVERSION_KEYS[action]
        self._discard(player, value)
        self._diamonds[player] += 1

    def _owned_abilities(
        self,
        player: int,
        kind: type[_AbilityT],
    ) -> list[tuple[str, _AbilityT]]:
        """Return ``(character id, ability)`` for `player`'s activated `kind` abilities."""
        return [
            (CHARACTERS[card].id, ability)
            for card in self._activated_characters[player]
            if isinstance(ability := CHARACTERS[card].ability, kind)
        ]

    def _visible_peeked_character(self, player: int) -> int | None:
        """Return the peeked top character card if `player` is the one who peeked."""
        return self._peeked_character if self._peeked_by == player else None

    @staticmethod
    def _payment_action(payment: PearlPayment) -> int:
        """Return the stable OpenSpiel action for one payment resource."""
        if payment.source is PearlSource.HAND:
            if (
                payment.printed_value is None
                or payment.diamonds_spent > 1
                or len(payment.modifiers) > 1
                or not payment.discard
            ):
                message = "this physical payment interpretation has no action identifier"
                raise RuntimeError(message)
            unmodified = payment.printed_value == payment.effective_value
            if not payment.modifiers and not payment.diamonds_spent and unmodified:
                return int(_HAND_PAYMENT_ACTIONS[payment.printed_value])
            modifier = payment.modifiers[0] if payment.modifiers else None
            key = (modifier, payment.printed_value, payment.effective_value)
            table = (
                _DIAMOND_PAYMENT_ACTIONS if payment.diamonds_spent else _SUBSTITUTED_PAYMENT_ACTIONS
            )
            try:
                return int(table[key])
            except KeyError as error:
                message = "this modified payment has no action identifier"
                raise RuntimeError(message) from error
        if payment.source_id is None:
            message = "a virtual payment needs a source identifier"
            raise RuntimeError(message)
        try:
            return int(_VIRTUAL_PAYMENT_ACTIONS[(payment.source_id, payment.effective_value)])
        except KeyError as error:
            message = "this virtual payment interpretation has no action identifier"
            raise RuntimeError(message) from error

    @classmethod
    def _payment_option_for_action(
        cls,
        decision: PaymentDecision,
        action: int,
    ) -> PearlPayment:
        """Return the unique currently offered payment represented by `action`."""
        matching = tuple(
            option for option in decision.options() if cls._payment_action(option) == action
        )
        if len(matching) != 1:
            message = "payment action does not identify exactly one offered resource"
            raise ValueError(message)
        return matching[0]

    @staticmethod
    def _payment_label(payment: PearlPayment) -> str:
        """Return a human-readable label for a physical or virtual payment."""
        if payment.source is PearlSource.HAND:
            tags = (*payment.modifiers, *(("diamond",) if payment.diamonds_spent else ()))
            if tags:
                return (
                    f"PayHand:{payment.printed_value}As{payment.effective_value}:{':'.join(tags)}"
                )
            return f"PayHand:{payment.printed_value}"
        return f"UseVirtual:{payment.source_id}As{payment.effective_value}"

    def _selected_payment_labels(self) -> tuple[str, ...]:
        """Return public labels of resources selected for a pending payment."""
        decision = self._pending_step
        if not isinstance(decision, PaymentDecision):
            return ()
        return tuple(self._payment_label(payment) for payment in decision.selected)

    def _selected_physical_values(self) -> tuple[int, ...]:
        """Return publicly selected physical pearl values in a pending payment."""
        decision = self._pending_step
        if not isinstance(decision, PaymentDecision):
            return ()
        return tuple(
            payment.printed_value
            for payment in decision.selected
            if payment.source is PearlSource.HAND and payment.printed_value is not None
        )

    def _end_action(self) -> None:
        """Consume one action and start the end of the turn after the last one."""
        self._actions_left -= 1
        if not self._actions_left:
            self._after_turn()

    def _after_turn(self) -> None:
        """Offer after-turn abilities (Reaper) before the hand limit applies."""
        player = self._cur_player
        if self._hands[player].total() and self._owned_abilities(player, RedrawHandAbility):
            self._pending_step = BlueAbilityDecision(player, BlueChoice.REDRAW_HAND)
            return
        self._finish_turn()

    def _finish_turn(self) -> None:
        """Enforce the hand limit and pass the turn once the hand fits."""
        if self._auto_discard:
            self._trim_hand(self._cur_player)
        if not self._must_discard(self._cur_player):
            self._end_turn()

    def _end_turn(self) -> None:
        """Hand the turn to the next player and run the final turns once the target is reached.

        The player ending a turn with at least `_TARGET_POINTS` triggers
        ``2 * players - 1`` final turns: two for everybody else and one for
        the finisher, so the game stops right before the finisher's next turn.
        Only the active player can gain points, so the trigger is checked here.
        """
        if self._final_turns is None:
            if self._scores[self._cur_player] >= _TARGET_POINTS:
                self._final_turns = 2 * self._num_players - 1
        else:
            self._final_turns -= 1
        self._cur_player = (self._cur_player + 1) % self._num_players
        player = self._cur_player
        self._actions_left = (
            _ACTIONS_PER_TURN
            + self._next_turn_bonus[player]
            + sum(
                ability.actions for _, ability in self._owned_abilities(player, TurnActionsAbility)
            )
        )
        self._next_turn_bonus[player] = 0
        if self._final_turns == 0:
            self._game_over = True
            return
        self._before_turn()

    def _before_turn(self) -> None:
        """Start before-turn abilities: the Dumbledore peek, then the Mad Hatter swap."""
        player = self._cur_player
        if (
            self._owned_abilities(player, PeekCharacterDeckAbility)
            and self._peeked_character is None
            and self._character_deck.total()
        ):
            self._pending_step = PeekStep(player)  # resolving it then offers the swap
            return
        self._offer_portal_swap()

    def _offer_portal_swap(self) -> None:
        """Offer the Mad Hatter swap when the current player can make one."""
        player = self._cur_player
        if (
            self._owned_abilities(player, PortalMarketSwapAbility)
            and self._portals[player]
            and self._character_display
        ):
            self._pending_step = BlueAbilityDecision(player, BlueChoice.SWAP_PORTAL)

    def _hand_limit(self, player: int) -> int:
        """Return `player`'s end-of-turn hand limit, including stacking bonuses."""
        return _HAND_LIMIT + sum(
            ability.bonus for _, ability in self._owned_abilities(player, HandLimitAbility)
        )

    def _must_discard(self, player: int) -> bool:
        """Return whether `player` still owes a discard before the turn can pass on.

        A player is over the hand limit only after having spent all of their
        actions, so `_actions_left` doubles as the discard phase flag.
        """
        return (
            not self._auto_discard
            and not self._actions_left
            and self._hands[player].total() > self._hand_limit(player)
        )

    def _forget_known(self, player: int, value: int) -> None:
        """Drop one known card of `value` after `player` publicly gave up such a card.

        Observers cannot tell whether the known card or a hidden card of the same value
        left the hand, so the public lower bound shrinks by one either way.
        """
        if self._known_pearls[player][value]:
            self._known_pearls[player][value] -= 1
            self._known_pearls[player] = +self._known_pearls[player]

    def _discard(self, player: int, value: int) -> None:
        """Move one pearl card of `value` from the hand of `player` to the discard pile."""
        hand = self._hands[player]
        if not hand[value]:
            message = f"player {player} holds no pearl card of value {value}"
            raise ValueError(message)
        hand[value] -= 1
        self._pearl_discard[value] += 1
        self._forget_known(player, value)
        self._hands[player] = +hand  # drop zero counts

    def _trim_hand(self, player: int) -> None:
        """Discard down to the hand limit, dropping the least useful pearls first."""
        hand = self._hands[player]
        wanted = self._wanted_values(player)
        while hand.total() > self._hand_limit(player):
            spare = [value for value in hand.elements() if value not in wanted]
            value = min(spare) if spare else min(hand.elements())
            hand[value] -= 1
            self._pearl_discard[value] += 1
            self._forget_known(player, value)
        self._hands[player] = +hand

    def _wanted_values(self, player: int) -> set[int]:
        """Return the pearl values that best progress the player's portal characters.

        Used only to pick which pearls to drop at the hand limit, so the
        heuristic does not need to find an actual valid activation.
        """
        hand = self._hands[player]
        wanted: set[int] = set()
        for card in self._portals[player]:
            for part in leaf_requirements(CHARACTERS[card].requirement):
                if isinstance(part, ExactValues):
                    wanted.update(part.values)
                elif isinstance(part, SameValue):
                    wanted.add(max(_PEARL_VALUES, key=hand.__getitem__))
                elif isinstance(part, ParityValues):
                    wants_even = part.parity is Parity.EVEN
                    wanted.update(
                        value for value in _PEARL_VALUES if (value % 2 == 0) == wants_even
                    )
                else:
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
    """The *Portale von Molthar* game."""

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        params = params or {}
        num_players = int(params.get("players", _DEFAULT_PLAYERS))
        if not _MIN_PLAYERS <= num_players <= _MAX_PLAYERS:
            message = f"players must be in [{_MIN_PLAYERS}, {_MAX_PLAYERS}], got {num_players}"
            raise ValueError(message)
        info = pyspiel.GameInfo(
            num_distinct_actions=len(Action),
            max_chance_outcomes=max(len(_PEARL_VALUES), len(CHARACTERS)),
            num_players=num_players,
            min_utility=-1.0,
            max_utility=1.0,
            utility_sum=0.0,
            max_game_length=_MAX_NODES_PER_PLAYER * num_players,
        )
        super().__init__(_GAME_TYPE, info, params)

    def new_initial_state(self) -> MoltharState:
        """Return a state with empty displays; chance fills them first."""
        return MoltharState(self)

    def observation_tensor_shape(self) -> list[int]:
        """Return the flat observation length (see `MoltharState.observation_tensor`)."""
        num_players = self.num_players()
        return [
            num_players
            + len(_PEARL_VALUES)
            + _PEARL_DISPLAY_SIZE * (1 + len(_PEARL_VALUES))
            + (_CHAR_DISPLAY_SIZE + num_players * _PORTAL_SLOTS) * (1 + len(CHARACTERS))
            + num_players * len(CHARACTERS)  # activated-character counts
            + len(CHARACTERS)  # discarded-character counts
            + num_players  # hand sizes
            + num_players * len(_PEARL_VALUES)  # publicly known hand cards
            + len(_PEARL_VALUES)  # pearl-discard counts
            + 2  # pearl- and character-deck sizes
            + num_players  # scores
            + num_players  # diamonds
            + num_players  # queued action bonuses
            + 1  # remaining final turns
            + _MAX_REMAINING_ACTIONS
            + 1
            + len(CHARACTERS)  # top character card, if this player peeked at it
            + len(BlueChoice)  # pending blue choice kind
            + 1  # whether a payment decision is pending
            + num_players  # owner of its target character
            + _PORTAL_SLOTS  # portal slot of a half-paid activation
            + len(_PEARL_VALUES)  # printed values selected towards it
            + len(_PEARL_VALUES)  # corresponding effective values
            + len(CHARACTERS)  # selected virtual-source character counts
            + 1  # diamonds committed by selected pearl modifications
            + num_players  # selected red ability target
            + len(_PEARL_VALUES)  # opposing hand revealed to a Tinkerbell actor
            + len(RedChoice),  # red choice kind
        ]


pyspiel.register_game(_GAME_TYPE, MoltharGame)
