"""Tests for typed character abilities."""

import pytest

from portale_von_molthar.abilities import (
    AbilityTiming,
    GainActionsAbility,
    PearlValueSubstitutionAbility,
    VirtualPearlAbility,
)


@pytest.mark.parametrize("values", [(), (0,), (9,), (1, 1)])
def test_virtual_pearl_ability_rejects_invalid_values(values: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="virtual pearl values"):
        VirtualPearlAbility(values)


def test_virtual_pearl_ability_defaults_to_during_turn() -> None:
    ability = VirtualPearlAbility((1, 8))
    assert ability.timing is AbilityTiming.DURING_TURN


@pytest.mark.parametrize(
    ("printed_value", "effective_values", "error"),
    [
        (0, (1,), "printed pearl value"),
        (9, (1,), "printed pearl value"),
        (1, (), "effective pearl values"),
        (1, (0,), "effective pearl values"),
        (1, (9,), "effective pearl values"),
        (1, (1, 8), "different from the printed value"),
        (1, (8, 8), "must be unique"),
    ],
)
def test_pearl_value_substitution_ability_rejects_invalid_values(
    printed_value: int,
    effective_values: tuple[int, ...],
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        PearlValueSubstitutionAbility(printed_value, effective_values)


def test_pearl_value_substitution_ability_defaults_to_during_turn() -> None:
    ability = PearlValueSubstitutionAbility(1, (8,))
    assert ability.timing is AbilityTiming.DURING_TURN


@pytest.mark.parametrize("actions", [-1, 0])
def test_gain_actions_ability_rejects_nonpositive_count(actions: int) -> None:
    with pytest.raises(ValueError, match="at least one action"):
        GainActionsAbility(actions)
