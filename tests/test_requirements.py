"""Tests for typed activation requirement expressions."""

import pytest

from portale_von_molthar.requirements import (
    AllOf,
    AnyOf,
    ConsecutiveValues,
    ExactValues,
    FixedCountSum,
    Parity,
    ParityValues,
    Requirement,
    SameValue,
    VariableCountSum,
    required_card_counts,
    requirement_matches,
)


@pytest.mark.parametrize(
    ("requirement", "values", "expected"),
    [
        (ExactValues((1, 2, 3)), (1, 2, 3), True),
        (ExactValues((1, 2, 3)), (1, 2, 4), False),
        (SameValue(3), (6, 6, 6), True),
        (SameValue(3), (5, 6, 6), False),
        (ParityValues(3, Parity.ODD), (1, 3, 7), True),
        (ParityValues(3, Parity.EVEN), (2, 3, 4), False),
        (FixedCountSum(3, 20), (5, 7, 8), True),
        (FixedCountSum(3, 20), (6, 6, 8, 8), False),
        (VariableCountSum(10), (2, 8), True),
        (VariableCountSum(10), (1, 2, 3, 4), True),
        (ConsecutiveValues(3), (3, 4, 5), True),
        (ConsecutiveValues(3), (7, 8, 1), False),
        (AnyOf((ExactValues((3, 3, 3)), ExactValues((6, 6, 6)))), (6, 6, 6), True),
        (AnyOf((ExactValues((3, 3, 3)), ExactValues((6, 6, 6)))), (5, 5, 5), False),
        (AllOf((SameValue(2), ExactValues((6, 6)))), (6, 6, 7, 7), True),
    ],
)
def test_requirement_matches(
    requirement: Requirement,
    values: tuple[int, ...],
    *,
    expected: bool,
) -> None:
    assert requirement_matches(requirement, values) is expected


@pytest.mark.parametrize(
    ("requirement", "maximum", "expected"),
    [
        (VariableCountSum(10), 4, frozenset({1, 2, 3, 4})),
        (
            AnyOf((ExactValues((1,)), ExactValues((1, 2, 3)))),
            4,
            frozenset({1, 3}),
        ),
        (
            AllOf((SameValue(2), ExactValues((6, 6)))),
            4,
            frozenset({4}),
        ),
    ],
)
def test_required_card_counts(
    requirement: Requirement,
    maximum: int,
    expected: frozenset[int],
) -> None:
    assert required_card_counts(requirement, maximum) == expected
