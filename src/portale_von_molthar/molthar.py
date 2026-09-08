"""A simplified *Die Portale von Molthar* implemented as an OpenSpiel Python game.

Simplifications with respect to the printed rules (see module constants):

* The 14 green characters and blue characters that provide or reinterpret
  pearl values are modelled; other red and blue abilities are not yet implemented.
* Diamonds are tracked as a plain per-player counter rather than as physical
  character cards drawn from the deck. They can pay explicit requirements but
  cannot yet modify a pearl card's value (see RULES.md section 8).
* Pearl cards can only be taken from the face-up display, never blind from the
  draw pile.
* Going over the hand limit is resolved by the player, who picks one pearl
  value to drop per decision node at the end of the turn; loading the game
  with ``auto_discard=true`` drops them by a built-in heuristic instead.
* Two players; the retail game supports two to five.

Importing this module registers the game under the short name
``python_portale_von_molthar`` so that it can be created with
``pyspiel.load_game("python_portale_von_molthar")``.
"""

import enum
from collections import Counter
from typing import Any, Final

import pyspiel

from portale_von_molthar.abilities import (
    AbilityTiming,
    PearlValueSubstitutionAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.cards import CHARACTERS, Character
from portale_von_molthar.decisions import PaymentDecision, PendingDecision
from portale_von_molthar.payments import (
    PaymentPlan,
    PearlPayment,
    PearlSource,
    ResourceOptions,
    hand_resource_options,
    payment_plans,
)
from portale_von_molthar.requirements import (
    ExactValues,
    Parity,
    ParityValues,
    SameValue,
    leaf_requirements,
)

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
# only ever "pass" would loop forever. Discards add up to three more nodes per
# turn, so a random game needs noticeably more of them than the actions alone.
_MAX_NODES: Final = 12000


class Action(enum.IntEnum):
    """The distinct player actions.

    The first nine are turn actions, three of which are spent per normal turn.
    Discard actions name a pearl value dropped at the end of a turn. Payment
    actions have stable meanings and never consume an additional turn action.
    """

    TAKE_PEARL_0 = 0
    TAKE_PEARL_1 = 1
    TAKE_PEARL_2 = 2
    TAKE_PEARL_3 = 3
    REFRESH_PEARLS = 4
    TAKE_CHARACTER_0 = 5
    TAKE_CHARACTER_1 = 6
    ACTIVATE_0 = 7
    ACTIVATE_1 = 8
    DISCARD_1 = 9
    DISCARD_2 = 10
    DISCARD_3 = 11
    DISCARD_4 = 12
    DISCARD_5 = 13
    DISCARD_6 = 14
    DISCARD_7 = 15
    DISCARD_8 = 16
    PAY_HAND_1 = 17
    PAY_HAND_2 = 18
    PAY_HAND_3 = 19
    PAY_HAND_4 = 20
    PAY_HAND_5 = 21
    PAY_HAND_6 = 22
    PAY_HAND_7 = 23
    PAY_HAND_8 = 24
    USE_BARBARIAN_1 = 25
    USE_BARBARIAN_2 = 26
    USE_BARBARIAN_3 = 27
    USE_BARBARIAN_4 = 28
    USE_BARBARIAN_5 = 29
    USE_BARBARIAN_6 = 30
    USE_BARBARIAN_7 = 31
    USE_FUCHUR_AS_1 = 32
    USE_FUCHUR_AS_2 = 33
    USE_FUCHUR_AS_3 = 34
    USE_FUCHUR_AS_4 = 35
    USE_FUCHUR_AS_5 = 36
    USE_FUCHUR_AS_6 = 37
    USE_FUCHUR_AS_7 = 38
    USE_FUCHUR_AS_8 = 39
    USE_PHOENIX_AS_8 = 40
    PAY_HAND_3_AS_1_RUMPELSTILTSKIN = 41
    PAY_HAND_3_AS_2_RUMPELSTILTSKIN = 42
    PAY_HAND_3_AS_4_RUMPELSTILTSKIN = 43
    PAY_HAND_3_AS_5_RUMPELSTILTSKIN = 44
    PAY_HAND_3_AS_6_RUMPELSTILTSKIN = 45
    PAY_HAND_3_AS_7_RUMPELSTILTSKIN = 46
    PAY_HAND_3_AS_8_RUMPELSTILTSKIN = 47
    PAY_HAND_1_AS_8_PETER_PAN = 48


_HAND_PAYMENT_ACTIONS: Final = {value: Action.PAY_HAND_1 + value - 1 for value in _PEARL_VALUES}
_VIRTUAL_PAYMENT_ACTIONS: Final = {
    **{(f"barbarian_{value}", value): Action.USE_BARBARIAN_1 + value - 1 for value in range(1, 8)},
    **{("fuchur", value): Action.USE_FUCHUR_AS_1 + value - 1 for value in _PEARL_VALUES},
    ("phoenix", 8): Action.USE_PHOENIX_AS_8,
}
_SUBSTITUTED_PAYMENT_ACTIONS: Final = {
    ("rumpelstiltskin", 3, 1): Action.PAY_HAND_3_AS_1_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 2): Action.PAY_HAND_3_AS_2_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 4): Action.PAY_HAND_3_AS_4_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 5): Action.PAY_HAND_3_AS_5_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 6): Action.PAY_HAND_3_AS_6_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 7): Action.PAY_HAND_3_AS_7_RUMPELSTILTSKIN,
    ("rumpelstiltskin", 3, 8): Action.PAY_HAND_3_AS_8_RUMPELSTILTSKIN,
    ("peter_pan", 1, 8): Action.PAY_HAND_1_AS_8_PETER_PAN,
}
_CHARACTER_INDEX_BY_ID: Final = {character.id: index for index, character in enumerate(CHARACTERS)}


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
    parameter_specification={"auto_discard": False},
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
        self._activated_characters: list[list[int]] = [[] for _ in range(_NUM_PLAYERS)]
        self._scores: list[int] = [0] * _NUM_PLAYERS
        self._diamonds: list[int] = [0] * _NUM_PLAYERS
        self._auto_discard = bool(game.get_parameters().get("auto_discard", False))
        self._cur_player = 0
        self._pending_decision: PendingDecision | None = None
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
            activated = [CHARACTERS[card].id for card in self._activated_characters[player]]
            hand = sorted(self._hands[player].elements())
            lines.append(
                f"p{player}: score={self._scores[player]} diamonds={self._diamonds[player]} "
                f"portal={portal} activated={activated} hand={hand}",
            )
        lines.append(f"turn=p{self._cur_player} actions_left={self._actions_left}")
        return "\n".join(lines)

    # endregion

    # region public methods

    def current_player(self) -> int:
        """Return the mover: a player id, or the terminal/chance sentinel."""
        if self._game_over:
            return pyspiel.PlayerId.TERMINAL
        if self._pending_decision is not None:
            return self._pending_decision.actor
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
        activated = [
            [CHARACTERS[card].id for card in self._activated_characters[other]]
            for other in range(_NUM_PLAYERS)
        ]
        paid = self._selected_payment_labels()
        return (
            f"p{player} hand={hand} "
            f"pearls={self._pearl_display} "
            f"chars={[CHARACTERS[card].id for card in self._character_display]} "
            f"portals={portals} activated={activated} scores={self._scores} "
            f"diamonds={self._diamonds} to_move=p{self._cur_player} "
            f"left={self._actions_left} paid={list(paid)}"
        )

    def observation_tensor(self, player: int) -> list[float]:
        """Return the flat observation of `player`.

        Args:
            player: Player receiving the imperfect-information observation.

        Returns:
            Flat tensor ordered as observing-player one-hot, own-hand counts,
            pearl-display slots, character-display slots, portal slots,
            activated-character counts, scores, diamonds, remaining actions,
            and pending-payment details. Each card slot uses an empty/card-type
            one-hot; count-valued sections use ascending card or pearl value.
        """
        planes: list[float] = []
        # one-hot encoding of the player receiving this observation
        planes.extend(1.0 if player == index else 0.0 for index in range(_NUM_PLAYERS))
        # count of each pearl value in the player's hand
        planes.extend(float(self._hands[player][value]) for value in _PEARL_VALUES)
        for slot in range(_PEARL_DISPLAY_SIZE):
            # for each pearl card slot, one-hot encoding of the value ("0" is an empty slot)
            value = self._pearl_display[slot] if slot < len(self._pearl_display) else 0
            planes.extend(1.0 if value == option else 0.0 for option in (0, *_PEARL_VALUES))
        for slot in range(_CHAR_DISPLAY_SIZE):
            planes.extend(self._character_one_hot(self._character_display, slot))
        for other in range(_NUM_PLAYERS):
            for slot in range(_PORTAL_SLOTS):
                planes.extend(self._character_one_hot(self._portals[other], slot))
        for other in range(_NUM_PLAYERS):
            activated = Counter(self._activated_characters[other])
            planes.extend(float(activated[card]) for card in range(len(CHARACTERS)))
        planes.extend(score / _TARGET_POINTS for score in self._scores)
        planes.extend(float(diamonds) for diamonds in self._diamonds)
        planes.extend(
            1.0 if self._actions_left == step + 1 else 0.0 for step in range(_ACTIONS_PER_TURN)
        )
        # Pending activation data is public. Printed and effective counts are
        # separate because abilities and diamonds may modify physical pearls.
        decision = self._pending_decision
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
        planes.extend(1.0 if other == target_owner else 0.0 for other in range(_NUM_PLAYERS))
        planes.extend(1.0 if slot == slot_paid else 0.0 for slot in range(_PORTAL_SLOTS))
        planes.extend(float(Counter(printed_values)[value]) for value in _PEARL_VALUES)
        planes.extend(float(Counter(effective_values)[value]) for value in _PEARL_VALUES)
        planes.extend(float(virtual_sources[card]) for card in range(len(CHARACTERS)))
        planes.append(float(diamonds_spent))
        return planes

    # endregion

    # region private methods

    def _legal_actions(self, player: int) -> list[int]:
        """Return the sorted legal actions for `player`."""
        if self._pending_decision is not None:
            return self._pending_decision_actions(player, self._pending_decision)
        if self._must_discard(player):
            return [
                Action.DISCARD_1 + value - 1
                for value in _PEARL_VALUES
                if self._hands[player][value]
            ]
        actions: list[int] = list(range(len(self._pearl_display)))
        if self._pearl_display:
            actions.append(Action.REFRESH_PEARLS)
        if len(self._portals[player]) < _PORTAL_SLOTS:
            actions.extend(
                Action.TAKE_CHARACTER_0 + slot for slot in range(len(self._character_display))
            )
        for slot, card in enumerate(self._portals[player]):
            character = CHARACTERS[card]
            if self._activation_plans(player, character):
                actions.append(Action.ACTIVATE_0 + slot)
        # A player is never stuck: refreshing an empty display is a legal pass.
        return sorted(actions) if actions else [int(Action.REFRESH_PEARLS)]

    def _apply_action(self, action: int) -> None:
        """Apply `action`, which is a chance outcome on chance nodes."""
        self._nodes += 1
        if self._pending_decision is not None:
            self._apply_pending_decision(
                self._pending_decision.actor,
                self._pending_decision,
                action,
            )
            if self._pending_decision is None:
                self._end_action()
        elif (deck := self._pending_refill()) is not None:
            self._draw(deck, action)
        elif self._must_discard(self._cur_player):
            self._discard(self._cur_player, action - Action.DISCARD_1 + 1)
            if not self._must_discard(self._cur_player):
                self._end_turn()
        else:
            self._apply_player_action(action)
            if self._pending_decision is None:
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
            pearl = len(self._pearl_display) < _PEARL_DISPLAY_SIZE and self._pearl_deck.total()
            label = f"DealPearl:{action}" if pearl else f"DealCharacter:{CHARACTERS[action].id}"
        elif action <= Action.TAKE_PEARL_3:
            label = f"TakePearl:{self._pearl_display[action]}"
        elif action == Action.REFRESH_PEARLS:
            label = "RefreshPearls"
        elif action <= Action.TAKE_CHARACTER_1:
            slot = action - Action.TAKE_CHARACTER_0
            label = f"TakeCharacter:{CHARACTERS[self._character_display[slot]].id}"
        elif action <= Action.ACTIVATE_1:
            slot = action - Action.ACTIVATE_0
            label = f"Activate:{CHARACTERS[self._portals[player][slot]].id}"
        elif action <= Action.DISCARD_8:
            value = action - Action.DISCARD_1 + 1
            label = f"Discard:{value}"
        elif isinstance(self._pending_decision, PaymentDecision):
            option = self._payment_option_for_action(self._pending_decision, action)
            label = self._payment_label(option)
        else:
            message = f"action {action} is not meaningful in the current state"
            raise ValueError(message)
        return label

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
        elif action <= Action.ACTIVATE_1:
            self._activate(player, action - Action.ACTIVATE_0)
        else:
            message = f"action {action} is not a normal turn action"
            raise ValueError(message)

    def _activate(self, player: int, slot: int) -> None:
        """Start paying for the character in `slot` (RULES.md section 6.4).

        The planner separates matching from mutation and preserves the source
        and effective value of every resource. A pending decision is only
        created when more than one complete plan is possible.
        """
        character = CHARACTERS[self._portals[player][slot]]
        plans = self._activation_plans(player, character)
        if not plans:
            message = f"cannot activate {character.id} with the current hand"
            raise ValueError(message)
        decision = PaymentDecision(player, player, slot, plans)
        plan = decision.resolved_plan
        if plan is not None:
            self._resolve_activation(player, player, slot, plan)
            return
        self._pending_decision = decision

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

    def _pending_decision_actions(
        self,
        player: int,
        decision: PendingDecision,
    ) -> list[int]:
        """Map semantic options of `decision` to OpenSpiel action identifiers."""
        if player != decision.actor:
            return []
        return sorted({self._payment_action(option) for option in decision.options()})

    def _apply_pending_decision(
        self,
        player: int,
        decision: PendingDecision,
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
            self._pending_decision = updated
            return
        self._pending_decision = None
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
        self._hands[player] = +self._hands[player]  # drop zero counts
        self._portals[target_owner].pop(slot)
        self._activated_characters[player].append(character_index)
        self._scores[player] += character.points
        self._diamonds[player] += character.diamonds - plan.diamonds_spent

    @staticmethod
    def _payment_action(payment: PearlPayment) -> int:
        """Return the stable OpenSpiel action for one payment resource."""
        if payment.source is PearlSource.HAND:
            if payment.printed_value is None or payment.diamonds_spent or not payment.discard:
                message = "this physical payment interpretation has no action identifier"
                raise RuntimeError(message)
            if not payment.modifiers and payment.printed_value == payment.effective_value:
                return int(_HAND_PAYMENT_ACTIONS[payment.printed_value])
            if len(payment.modifiers) == 1:
                key = (payment.modifiers[0], payment.printed_value, payment.effective_value)
                try:
                    return int(_SUBSTITUTED_PAYMENT_ACTIONS[key])
                except KeyError as error:
                    message = "this substituted payment has no action identifier"
                    raise RuntimeError(message) from error
            message = "this physical payment interpretation has no action identifier"
            raise RuntimeError(message)
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
            if payment.modifiers:
                return (
                    f"PayHand:{payment.printed_value}As{payment.effective_value}:"
                    f"{payment.modifiers[0]}"
                )
            return f"PayHand:{payment.printed_value}"
        return f"UseVirtual:{payment.source_id}As{payment.effective_value}"

    def _selected_payment_labels(self) -> tuple[str, ...]:
        """Return public labels of resources selected for a pending payment."""
        decision = self._pending_decision
        if not isinstance(decision, PaymentDecision):
            return ()
        return tuple(self._payment_label(payment) for payment in decision.selected)

    def _selected_physical_values(self) -> tuple[int, ...]:
        """Return publicly selected physical pearl values in a pending payment."""
        decision = self._pending_decision
        if not isinstance(decision, PaymentDecision):
            return ()
        return tuple(
            payment.printed_value
            for payment in decision.selected
            if payment.source is PearlSource.HAND and payment.printed_value is not None
        )

    def _end_action(self) -> None:
        """Consume one action and hand over the turn once three have been spent."""
        self._actions_left -= 1
        if self._actions_left:
            return
        if self._auto_discard:
            self._trim_hand(self._cur_player)
        if not self._must_discard(self._cur_player):
            self._end_turn()

    def _end_turn(self) -> None:
        """Hand the turn to the next player and end the game once the target is reached."""
        self._cur_player = (self._cur_player + 1) % _NUM_PLAYERS
        self._actions_left = _ACTIONS_PER_TURN
        # The round is played to the end so that every player had equal turns.
        if self._cur_player == 0 and max(self._scores) >= _TARGET_POINTS:
            self._game_over = True

    def _must_discard(self, player: int) -> bool:
        """Return whether `player` still owes a discard before the turn can pass on.

        A player is over the hand limit only after having spent all three of
        their actions, so `_actions_left` doubles as the discard phase flag.
        """
        return (
            not self._auto_discard
            and not self._actions_left
            and self._hands[player].total() > _HAND_LIMIT
        )

    def _discard(self, player: int, value: int) -> None:
        """Move one pearl card of `value` from the hand of `player` to the discard pile."""
        hand = self._hands[player]
        if not hand[value]:
            message = f"player {player} holds no pearl card of value {value}"
            raise ValueError(message)
        hand[value] -= 1
        self._pearl_discard[value] += 1
        self._hands[player] = +hand  # drop zero counts

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
            + _NUM_PLAYERS * len(CHARACTERS)  # activated-character counts
            + _NUM_PLAYERS  # scores
            + _NUM_PLAYERS  # diamonds
            + _ACTIONS_PER_TURN
            + 1  # whether a payment decision is pending
            + _NUM_PLAYERS  # owner of its target character
            + _PORTAL_SLOTS  # portal slot of a half-paid activation
            + len(_PEARL_VALUES)  # printed values selected towards it
            + len(_PEARL_VALUES)  # corresponding effective values
            + len(CHARACTERS)  # selected virtual-source character counts
            + 1,  # diamonds committed by selected pearl modifications
        ]


pyspiel.register_game(_GAME_TYPE, MoltharGame)
