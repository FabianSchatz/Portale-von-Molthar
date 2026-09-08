"""Tests for typed character abilities."""

import pytest

from portale_von_molthar.abilities import AbilityTiming, VirtualPearlAbility


@pytest.mark.parametrize("values", [(), (0,), (9,), (1, 1)])
def test_virtual_pearl_ability_rejects_invalid_values(values: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="virtual pearl values"):
        VirtualPearlAbility(values)


def test_virtual_pearl_ability_defaults_to_during_turn() -> None:
    ability = VirtualPearlAbility((1, 8))
    assert ability.timing is AbilityTiming.DURING_TURN
