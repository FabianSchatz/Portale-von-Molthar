"""Tests for Molthar card values."""

import pytest

from portale_von_molthar import CharacterCard, PearlCard


@pytest.mark.parametrize("value", [1, 4, 8])
def test_pearl_card(value: int) -> None:
    assert PearlCard(value).value == value


@pytest.mark.parametrize("value", [0, 9])
def test_pearl_card_invalid_value(value: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 8"):
        PearlCard(value)


def test_character_card() -> None:
    card = CharacterCard("Plain character", (2, 5), 3)

    assert card.requirements == (2, 5)
    assert card.power_points == 3
