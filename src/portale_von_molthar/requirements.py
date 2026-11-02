"""Typed activation requirements and matching against effective pearl values."""

from __future__ import annotations

import enum
import itertools
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from collections.abc import Iterator

_MIN_PEARL_VALUE = 1
_MAX_PEARL_VALUE = 8


class Parity(enum.StrEnum):
    """Parity accepted by a pearl-value requirement."""

    EVEN = "even"
    ODD = "odd"


@dataclass(frozen=True, slots=True)
class ExactValues:
    """Require exactly the listed pearl values."""

    values: tuple[int, ...]

    def __post_init__(self) -> None:
        """Validate that the requirement contains playable pearl values."""
        if not self.values or any(not _is_pearl_value(value) for value in self.values):
            message = "exact-value requirements need pearl values from 1 through 8"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class SameValue:
    """Require a fixed number of pearls sharing one unrestricted value."""

    count: int

    def __post_init__(self) -> None:
        """Validate the required card count."""
        _validate_positive(self.count, "same-value count")


@dataclass(frozen=True, slots=True)
class ParityValues:
    """Require a fixed number of even-valued or odd-valued pearls."""

    count: int
    parity: Parity

    def __post_init__(self) -> None:
        """Validate the required card count."""
        _validate_positive(self.count, "parity count")
        if not isinstance(self.parity, Parity):
            message = "parity must be a Parity member"
            raise TypeError(message)


@dataclass(frozen=True, slots=True)
class FixedCountSum:
    """Require a fixed number of pearls with an exact total value."""

    count: int
    total: int

    def __post_init__(self) -> None:
        """Validate the required card count and total."""
        _validate_positive(self.count, "fixed-sum count")
        _validate_positive(self.total, "fixed-sum total")


@dataclass(frozen=True, slots=True)
class VariableCountSum:
    """Require one or more pearls with an exact total value."""

    total: int

    def __post_init__(self) -> None:
        """Validate the required total."""
        _validate_positive(self.total, "variable-sum total")


@dataclass(frozen=True, slots=True)
class ConsecutiveValues:
    """Require a fixed-length sequence of consecutive pearl values."""

    count: int

    def __post_init__(self) -> None:
        """Validate the sequence length."""
        _validate_positive(self.count, "sequence length")
        if self.count > _MAX_PEARL_VALUE:
            message = "a pearl sequence cannot contain more than eight values"
            raise ValueError(message)


@dataclass(frozen=True, slots=True)
class AllOf:
    """Require every child requirement using disjoint pearl positions."""

    parts: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        """Validate that the conjunction contains requirements."""
        if not self.parts:
            message = "an AND requirement needs at least one part"
            raise ValueError(message)
        if any(not _is_requirement(part) for part in self.parts):
            message = "an AND requirement may only contain requirements"
            raise TypeError(message)


@dataclass(frozen=True, slots=True)
class AnyOf:
    """Require one complete alternative from the listed requirements."""

    alternatives: tuple[Requirement, ...]

    def __post_init__(self) -> None:
        """Validate that the disjunction contains alternatives."""
        if not self.alternatives:
            message = "an OR requirement needs at least one alternative"
            raise ValueError(message)
        if any(not _is_requirement(alternative) for alternative in self.alternatives):
            message = "an OR requirement may only contain requirements"
            raise TypeError(message)


LeafRequirement: TypeAlias = (
    ExactValues | SameValue | ParityValues | FixedCountSum | VariableCountSum | ConsecutiveValues
)
Requirement: TypeAlias = LeafRequirement | AllOf | AnyOf


def _is_requirement(value: object) -> bool:
    """Return whether `value` is one of the supported requirement nodes."""
    return isinstance(
        value,
        (
            ExactValues,
            SameValue,
            ParityValues,
            FixedCountSum,
            VariableCountSum,
            ConsecutiveValues,
            AllOf,
            AnyOf,
        ),
    )


def requirement_matches(requirement: Requirement, values: tuple[int, ...]) -> bool:
    """Return whether `values` satisfy `requirement` exactly.

    Every value represents one effective pearl position. For an ``AllOf``
    requirement, the positions are partitioned between its children so that a
    physical or virtual pearl cannot satisfy two consumed positions.

    Args:
        requirement: Requirement expression to evaluate.
        values: Effective pearl values offered as the complete payment.

    Returns:
        Whether the offered values satisfy the full expression.
    """
    return _matches(requirement, Counter(values))


def required_card_counts(requirement: Requirement, maximum: int) -> frozenset[int]:
    """Return possible numbers of pearl positions consumed by `requirement`.

    Args:
        requirement: Requirement expression to inspect.
        maximum: Maximum number of resources available to a variable-size
            requirement.

    Returns:
        Every possible consumed pearl count up to ``maximum``.
    """
    if maximum < 0:
        message = "maximum resource count must not be negative"
        raise ValueError(message)
    if isinstance(requirement, ExactValues):
        return _bounded_count(len(requirement.values), maximum)
    if isinstance(requirement, (SameValue, ParityValues, FixedCountSum, ConsecutiveValues)):
        return _bounded_count(requirement.count, maximum)
    if isinstance(requirement, VariableCountSum):
        return frozenset(range(1, maximum + 1))
    if isinstance(requirement, AnyOf):
        return frozenset().union(
            *(
                required_card_counts(alternative, maximum)
                for alternative in requirement.alternatives
            ),
        )

    counts = frozenset({0})
    for part in requirement.parts:
        part_counts = required_card_counts(part, maximum)
        counts = frozenset(
            current + added
            for current in counts
            for added in part_counts
            if current + added <= maximum
        )
    return counts


def leaf_requirements(requirement: Requirement) -> Iterator[LeafRequirement]:
    """Yield all leaf requirements contained in an expression.

    Args:
        requirement: Requirement expression to traverse.

    Yields:
        Leaf requirements in declaration order. Alternatives are all exposed;
        callers using this helper must decide how to combine their hints.
    """
    if isinstance(requirement, AllOf):
        for part in requirement.parts:
            yield from leaf_requirements(part)
        return
    if isinstance(requirement, AnyOf):
        for alternative in requirement.alternatives:
            yield from leaf_requirements(alternative)
        return
    yield requirement


def _matches(requirement: Requirement, pool: Counter[int]) -> bool:
    """Match a requirement against a complete multiset of effective values."""
    if isinstance(requirement, ExactValues):
        matches = pool == Counter(requirement.values)
    elif isinstance(requirement, SameValue):
        matches = pool.total() == requirement.count and len(pool) == 1
    elif isinstance(requirement, ParityValues):
        wants_even = requirement.parity is Parity.EVEN
        matches = pool.total() == requirement.count and all(
            (value % 2 == 0) == wants_even for value in pool.elements()
        )
    elif isinstance(requirement, FixedCountSum):
        matches = pool.total() == requirement.count and _counter_sum(pool) == requirement.total
    elif isinstance(requirement, VariableCountSum):
        matches = bool(pool.total()) and _counter_sum(pool) == requirement.total
    elif isinstance(requirement, ConsecutiveValues):
        values = sorted(pool.elements())
        matches = len(values) == requirement.count and all(
            right == left + 1 for left, right in itertools.pairwise(values)
        )
    elif isinstance(requirement, AnyOf):
        matches = any(_matches(alternative, pool) for alternative in requirement.alternatives)
    else:
        matches = _matches_all(pool, requirement.parts)
    return matches


def _matches_all(pool: Counter[int], parts: tuple[Requirement, ...]) -> bool:
    """Backtrack over disjoint allocations for an AND expression."""
    if not parts:
        return not pool.total()
    head, *tail = parts
    cards = sorted(pool.elements())
    for count in required_card_counts(head, len(cards)):
        for values in dict.fromkeys(itertools.combinations(cards, count)):
            choice = Counter(values)
            if _matches(head, choice) and _matches_all(pool - choice, tuple(tail)):
                return True
    return False


def _bounded_count(count: int, maximum: int) -> frozenset[int]:
    """Return `count` when it does not exceed `maximum`."""
    return frozenset({count}) if count <= maximum else frozenset()


def _counter_sum(values: Counter[int]) -> int:
    """Return the sum of all values in a multiset, including repetitions."""
    return sum(value * count for value, count in values.items())


def _is_pearl_value(value: int) -> bool:
    """Return whether `value` is printed on a pearl card."""
    return _MIN_PEARL_VALUE <= value <= _MAX_PEARL_VALUE


def _validate_positive(value: int, name: str) -> None:
    """Raise ``ValueError`` when `value` is not positive."""
    if value <= 0:
        message = f"{name} must be positive"
        raise ValueError(message)
