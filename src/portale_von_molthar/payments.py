"""Payment resources and complete plans for character activation."""

from __future__ import annotations

import enum
import itertools
from collections import Counter
from dataclasses import dataclass
from typing import TypeAlias

from portale_von_molthar.requirements import (
    Requirement,
    required_card_counts,
    requirement_matches,
)


class PearlSource(enum.StrEnum):
    """Source from which an effective pearl value is supplied."""

    HAND = "hand"
    VIRTUAL = "virtual"


@dataclass(frozen=True, slots=True)
class PearlPayment:
    """One pearl position used by an activation payment.

    ``printed_value`` and ``effective_value`` are separate because diamonds
    and persistent abilities may change how a physical card satisfies a
    requirement. Virtual pearls name their providing activated character in
    ``source_id`` and are never discarded.

    Attributes:
        source: Whether the pearl comes from the hand or an activated ability.
        effective_value: Value used while matching the activation requirement.
        printed_value: Value printed on a physical pearl card.
        source_id: Stable identifier of a virtual pearl's providing ability.
        diamonds_spent: Diamonds used to modify this physical pearl.
        modifiers: Stable identifiers of abilities affecting this use.
        discard: Whether the physical pearl enters the discard pile on payment.
    """

    source: PearlSource
    effective_value: int
    printed_value: int | None = None
    source_id: str | None = None
    diamonds_spent: int = 0
    modifiers: tuple[str, ...] = ()
    discard: bool = True

    def __post_init__(self) -> None:
        """Validate resource provenance and effective value."""
        if not isinstance(self.source, PearlSource):
            message = "pearl source must be a PearlSource member"
            raise TypeError(message)
        if not 1 <= self.effective_value <= 8:
            message = "effective pearl value must be from 1 through 8"
            raise ValueError(message)
        if self.diamonds_spent < 0:
            message = "diamonds spent must not be negative"
            raise ValueError(message)
        if self.source is PearlSource.HAND:
            if self.printed_value is None or not 1 <= self.printed_value <= 8:
                message = "a hand pearl needs a printed value from 1 through 8"
                raise ValueError(message)
            if self.source_id is not None:
                message = "a hand pearl cannot name a virtual source"
                raise ValueError(message)
            return
        if self.printed_value is not None or self.diamonds_spent or self.discard:
            message = "a virtual pearl cannot be printed, discarded, or diamond-modified"
            raise ValueError(message)
        if self.source_id is None:
            message = "a virtual pearl needs its providing ability as source_id"
            raise ValueError(message)


ResourceOptions: TypeAlias = tuple[tuple[PearlPayment, ...], ...]


@dataclass(frozen=True, slots=True)
class PaymentPlan:
    """A complete, provenance-preserving activation payment.

    Attributes:
        pearls: Physical and virtual pearl positions satisfying the requirement.
        required_diamonds: Diamonds printed directly inside the requirement.
    """

    pearls: tuple[PearlPayment, ...]
    required_diamonds: int = 0

    def __post_init__(self) -> None:
        """Validate the fixed diamond cost."""
        if self.required_diamonds < 0:
            message = "required diamonds must not be negative"
            raise ValueError(message)

    @property
    def diamonds_spent(self) -> int:
        """Return fixed and pearl-modification diamonds consumed by the plan."""
        return self.required_diamonds + sum(pearl.diamonds_spent for pearl in self.pearls)

    @property
    def discarded_values(self) -> tuple[int, ...]:
        """Return printed values of physical pearls discarded by the plan."""
        return tuple(
            pearl.printed_value
            for pearl in self.pearls
            if pearl.source is PearlSource.HAND
            and pearl.discard
            and pearl.printed_value is not None
        )


def hand_resource_options(hand: Counter[int]) -> ResourceOptions:
    """Return one base resource group for every physical pearl in `hand`.

    A group contains mutually exclusive interpretations of one resource.
    Currently each hand card has only its printed value. Diamond and ability
    implementations can add transformed alternatives to the corresponding
    group without changing the payment planner.

    Args:
        hand: Multiset of printed pearl values in a player's hand.

    Returns:
        Resource groups in ascending printed-value order.
    """
    groups: list[tuple[PearlPayment, ...]] = []
    for value in sorted(hand):
        if not 1 <= value <= 8 or hand[value] < 0:
            message = "a hand may only contain nonnegative counts of pearl values 1 through 8"
            raise ValueError(message)
        groups.extend(
            (PearlPayment(PearlSource.HAND, value, printed_value=value),)
            for _ in range(hand[value])
        )
    return tuple(groups)


def payment_plans(
    resources: ResourceOptions,
    requirement: Requirement,
    *,
    available_diamonds: int = 0,
    required_diamonds: int = 0,
) -> tuple[PaymentPlan, ...]:
    """Return every distinct resource plan satisfying `requirement`.

    Each outer entry in ``resources`` represents one physical or virtual
    resource. Its inner entries are mutually exclusive interpretations, such
    as a printed 3 used as 3, changed to 4 by a diamond, or treated as another
    value by an activated ability. At most one interpretation per group can be
    selected in one plan.

    Args:
        resources: Mutually exclusive effective-value options per resource.
        requirement: Pearl requirement to satisfy exactly.
        available_diamonds: Diamonds the player can spend on this activation.
        required_diamonds: Diamonds explicitly printed in the requirement.

    Returns:
        Canonically sorted, duplicate-free complete payment plans.
    """
    if available_diamonds < 0 or required_diamonds < 0:
        message = "available and required diamond counts must not be negative"
        raise ValueError(message)
    if any(not group for group in resources):
        message = "each payment resource group needs at least one interpretation"
        raise ValueError(message)
    if required_diamonds > available_diamonds:
        return ()

    plans: dict[tuple[tuple[object, ...], ...], PaymentPlan] = {}
    for count in required_card_counts(requirement, len(resources)):
        for groups in itertools.combinations(resources, count):
            for pearls in itertools.product(*groups):
                ordered = tuple(sorted(pearls, key=_pearl_key))
                plan = PaymentPlan(ordered, required_diamonds)
                if plan.diamonds_spent > available_diamonds:
                    continue
                effective_values = tuple(pearl.effective_value for pearl in ordered)
                if requirement_matches(requirement, effective_values):
                    plans.setdefault(_plan_key(plan), plan)
    return _remove_dominated_plans(tuple(sorted(plans.values(), key=_plan_key)))


def payment_plans_from_hand(
    hand: Counter[int],
    requirement: Requirement,
    *,
    available_diamonds: int = 0,
    required_diamonds: int = 0,
) -> tuple[PaymentPlan, ...]:
    """Return payment plans using unmodified physical pearls from `hand`.

    Args:
        hand: Multiset of printed pearl values in the player's hand.
        requirement: Pearl requirement to satisfy exactly.
        available_diamonds: Diamonds available to pay explicit costs.
        required_diamonds: Diamonds explicitly printed in the requirement.

    Returns:
        Complete payment plans available with the current green-card rules.
    """
    return payment_plans(
        hand_resource_options(hand),
        requirement,
        available_diamonds=available_diamonds,
        required_diamonds=required_diamonds,
    )


def _pearl_key(pearl: PearlPayment) -> tuple[object, ...]:
    """Return the canonical comparison key for one pearl use."""
    return (
        pearl.source.value,
        pearl.printed_value or 0,
        pearl.effective_value,
        pearl.source_id or "",
        pearl.diamonds_spent,
        pearl.modifiers,
        pearl.discard,
    )


def _plan_key(plan: PaymentPlan) -> tuple[tuple[object, ...], ...]:
    """Return a canonical key including all strategically relevant costs."""
    pearls = tuple(_pearl_key(pearl) for pearl in plan.pearls)
    diamonds = (("required_diamonds", plan.required_diamonds),)
    return pearls + diamonds


def _remove_dominated_plans(plans: tuple[PaymentPlan, ...]) -> tuple[PaymentPlan, ...]:
    """Remove plans that spend a strict superset of another plan's resources.

    All plans activate the same character and therefore have the same reward.
    Additional pearls or diamonds cannot improve that outcome under the
    documented rules, so a strict resource superset is never a useful choice.
    """
    return tuple(
        plan
        for plan in plans
        if not any(
            alternative is not plan and _dominates(alternative, plan) for alternative in plans
        )
    )


def _dominates(alternative: PaymentPlan, plan: PaymentPlan) -> bool:
    """Return whether `alternative` consumes a proper subset of `plan`."""
    alternative_pearls = Counter(alternative.pearls)
    plan_pearls = Counter(plan.pearls)
    pearls_are_subset = not alternative_pearls - plan_pearls
    costs_less = (
        alternative_pearls != plan_pearls or alternative.diamonds_spent < plan.diamonds_spent
    )
    return pearls_are_subset and alternative.diamonds_spent <= plan.diamonds_spent and costs_less
