"""Typed pending player decisions that interrupt the normal turn flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from portale_von_molthar.payments import PaymentPlan, PearlPayment


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


PendingDecision: TypeAlias = PaymentDecision | RedAbilityDecision


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
