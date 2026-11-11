"""Typed pending steps that interrupt the normal turn flow.

A step is either a decision made by a player or a chance draw resolved by
the environment. At most one step is pending at any time.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Final, TypeAlias

import pyspiel

if TYPE_CHECKING:
    from portale_von_molthar.game.payments import PaymentPlan, PearlPayment

_CHANCE: Final = int(pyspiel.PlayerId.CHANCE)


@dataclass(frozen=True, slots=True)
class PaymentDecision:
    """Selection between complete activation payment plans.

    Plan resources are selected in canonical order. This gives each complete
    payment exactly one path through the OpenSpiel tree instead of generating
    a separate history for every permutation of the same pearls. As soon as a
    single plan remains, its forced remainder can be committed automatically.

    Attributes:
        actor: Player choosing and supplying the payment.
        target_owner: Player whose portal contains the target character.
        target_slot: Slot of the target character on that portal.
        plans: Complete plans still consistent with previous choices.
        selected: Canonical resource prefix selected so far.
    """

    actor: int
    target_owner: int
    target_slot: int
    plans: tuple[PaymentPlan, ...]
    selected: tuple[PearlPayment, ...] = ()

    def __post_init__(self) -> None:
        """Validate that the decision has at least one consistent plan."""
        if not self.plans:
            message = "a payment decision needs at least one plan"
            raise ValueError(message)
        if any(plan.pearls[: len(self.selected)] != self.selected for plan in self.plans):
            message = "selected resources must prefix every remaining payment plan"
            raise ValueError(message)
        if any(
            left != right and right.pearls[: len(left.pearls)] == left.pearls
            for left in self.plans
            for right in self.plans
        ):
            message = "payment decisions cannot contain a plan prefixed by a shorter plan"
            raise ValueError(message)

    @property
    def resolved_plan(self) -> PaymentPlan | None:
        """Return the forced plan, or ``None`` while a real choice remains."""
        return self.plans[0] if len(self.plans) == 1 else None

    def options(self) -> tuple[PearlPayment, ...]:
        """Return canonical next choices that distinguish the remaining plans."""
        if self.resolved_plan is not None:
            return ()
        position = len(self.selected)
        choices = {plan.pearls[position] for plan in self.plans}
        return tuple(sorted(choices, key=_option_key))

    def choose(self, option: PearlPayment) -> PaymentDecision:
        """Return the decision state after choosing one offered option.

        Args:
            option: One of the values returned by :meth:`options`.

        Returns:
            A new immutable decision containing only compatible plans.

        Raises:
            ValueError: If ``option`` is not currently offered.
        """
        if option not in self.options():
            message = "payment option is not legal in the current decision"
            raise ValueError(message)
        position = len(self.selected)
        remaining = tuple(plan for plan in self.plans if plan.pearls[position] == option)
        return PaymentDecision(
            self.actor,
            self.target_owner,
            self.target_slot,
            remaining,
            (*self.selected, option),
        )


class RedChoice(StrEnum):
    """Choice required immediately after activating a red character."""

    KEEP_PEARL = "keep_pearl"
    STEAL_TARGET = "steal_target"
    STEAL_PEARL = "steal_pearl"
    DISCARD_TARGET = "discard_target"
    DISCARD_PORTAL = "discard_portal"


@dataclass(frozen=True, slots=True)
class RedAbilityDecision:
    """A red ability choice made by the activating player.

    Attributes:
        actor: Player who activated the character.
        choice: Effect awaiting a choice.
        options: Available player IDs, pearl values, or portal slots; zero means keep none.
        target_player: Selected opponent after a target player choice.
    """

    actor: int
    choice: RedChoice
    options: tuple[int, ...]
    target_player: int | None = None


class BlueChoice(StrEnum):
    """Optional blue ability offered before or after the owner's actions."""

    REDRAW_HAND = "redraw_hand"
    SWAP_PORTAL = "swap_portal"


@dataclass(frozen=True, slots=True)
class BlueAbilityDecision:
    """A turn-boundary blue ability choice that never consumes a turn action.

    The available options follow directly from the public state (portal and
    character display for a swap), so they are not stored here.

    Attributes:
        actor: Player owning the activated blue character.
        choice: Ability awaiting a choice.
    """

    actor: int
    choice: BlueChoice


@dataclass(frozen=True, slots=True)
class HandDrawStep:
    """Chance draws refilling a hand after a Reaper redraw.

    Each draw replaces the step with one whose ``remaining`` is one lower.

    Attributes:
        player: Player whose hand receives the drawn pearls.
        remaining: Pearls still to be drawn.
    """

    player: int
    remaining: int

    def __post_init__(self) -> None:
        """Validate that at least one draw remains."""
        if self.remaining <= 0:
            message = "a hand-draw step needs at least one remaining draw"
            raise ValueError(message)

    @property
    def actor(self) -> int:
        """Return the OpenSpiel chance player, who resolves this step."""
        return _CHANCE


class Pile(StrEnum):
    """Draw pile a player may take the hidden top card from."""

    PEARL = "pearl"
    CHARACTER = "character"


@dataclass(frozen=True, slots=True)
class DeckTakeStep:
    """Chance draw resolving a blind take of the top card of a draw pile.

    The taken pearl goes to the player's hand and the taken character onto
    their portal. Resolving the draw consumes the turn action that started it.

    Attributes:
        player: Player receiving the drawn card.
        pile: Draw pile the card is taken from.
    """

    player: int
    pile: Pile

    @property
    def actor(self) -> int:
        """Return the OpenSpiel chance player, who resolves this step."""
        return _CHANCE


@dataclass(frozen=True, slots=True)
class PeekStep:
    """Chance draw privately revealing the top character card (Dumbledore).

    Attributes:
        player: Player who sees the revealed card.
    """

    player: int

    @property
    def actor(self) -> int:
        """Return the OpenSpiel chance player, who resolves this step."""
        return _CHANCE


PendingStep: TypeAlias = (
    PaymentDecision
    | RedAbilityDecision
    | BlueAbilityDecision
    | HandDrawStep
    | DeckTakeStep
    | PeekStep
)


def _option_key(option: PearlPayment) -> tuple[object, ...]:
    """Return a stable ordering key for payment decision options."""
    return (
        option.source.value,
        option.printed_value or 0,
        option.effective_value,
        option.source_id or "",
        option.diamonds_spent,
        option.modifiers,
        option.discard,
    )
