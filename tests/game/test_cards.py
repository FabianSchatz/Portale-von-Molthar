"""Tests for structured character-card data."""

import pytest

from portale_von_molthar.game.abilities import (
    AbilityType,
    CharacterAbility,
    DiamondDecreaseAbility,
    GainActionsAbility,
    HandLimitAbility,
    NeighborActivationAbility,
    PearlToDiamondAbility,
    PearlValueSubstitutionAbility,
    PeekCharacterDeckAbility,
    PortalMarketSwapAbility,
    RedrawHandAbility,
    TurnActionsAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.game.cards import CHARACTERS
from portale_von_molthar.game.requirements import (
    AnyOf,
    ConsecutiveValues,
    ExactValues,
    Requirement,
    VariableCountSum,
)


def test_character_data_matches_docs() -> None:
    """`CHARACTERS` must contain all 54 base-game character cards."""
    assert len(CHARACTERS) == 40
    assert sum(character.copies for character in CHARACTERS) == 54
    assert len({character.id for character in CHARACTERS}) == len(CHARACTERS)


def test_character_data_models_virtual_pearl_providers() -> None:
    providers = {
        character.id: character
        for character in CHARACTERS
        if isinstance(character.ability, VirtualPearlAbility)
    }
    assert set(providers) == {
        "barbarian_1",
        "barbarian_2",
        "barbarian_3",
        "barbarian_4",
        "barbarian_5",
        "barbarian_6",
        "barbarian_7",
        "fuchur",
        "phoenix",
    }
    assert all(character.ability_type is AbilityType.BLUE for character in providers.values())
    assert providers["fuchur"].ability == VirtualPearlAbility(tuple(range(1, 9)))
    assert providers["phoenix"].ability == VirtualPearlAbility((8,))


def test_character_data_models_pearl_value_substitutions() -> None:
    substitutions = {
        character.id: character.ability
        for character in CHARACTERS
        if isinstance(character.ability, PearlValueSubstitutionAbility)
    }
    assert substitutions == {
        "rumpelstiltskin": PearlValueSubstitutionAbility(3, (1, 2, 4, 5, 6, 7, 8)),
        "peter_pan": PearlValueSubstitutionAbility(1, (8,)),
    }


def test_character_data_models_irrlicht_cards() -> None:
    cards = {character.id: character for character in CHARACTERS}
    assert cards["irrlicht_1"].requirement == AnyOf(
        (ExactValues((3, 3, 3)), ExactValues((6, 6, 6))),
    )
    assert cards["irrlicht_2"].requirement == AnyOf(
        (ExactValues((4, 4, 4)), ExactValues((5, 5, 5))),
    )
    for card_id in ("irrlicht_1", "irrlicht_2"):
        assert cards[card_id].ability_type is AbilityType.RED
        assert cards[card_id].ability == NeighborActivationAbility()


def test_character_data_models_golem_cards() -> None:
    cards = {character.id: character for character in CHARACTERS}
    assert cards["golem_1"].requirement == ExactValues((2, 4, 6, 8))
    assert cards["golem_2"].requirement == ExactValues((1, 3, 5, 7))
    for card_id in ("golem_1", "golem_2"):
        assert cards[card_id].ability_type is AbilityType.RED
        assert cards[card_id].ability == GainActionsAbility(3)


@pytest.mark.parametrize(
    ("card_id", "requirement", "points", "copies", "diamonds", "ability"),
    [
        ("reaper", ExactValues((1, 8)), 1, 1, 0, RedrawHandAbility()),
        (
            "little_red_riding_hood",
            ExactValues((4, 5, 6, 7, 8)),
            1,
            1,
            0,
            TurnActionsAbility(1),
        ),
        ("amazon", ExactValues((3, 5, 7)), 1, 1, 1, DiamondDecreaseAbility()),
        ("snow_white", ExactValues((2,)), 0, 1, 1, PearlToDiamondAbility(2)),
        ("mad_hatter", ConsecutiveValues(5), 2, 1, 0, PortalMarketSwapAbility()),
        ("dumbledore", ConsecutiveValues(3), 1, 1, 0, PeekCharacterDeckAbility()),
        ("flying_monkey", VariableCountSum(10), 1, 3, 0, HandLimitAbility(1)),
    ],
)
def test_character_data_models_turn_and_resource_blue_cards(  # noqa: PLR0913
    card_id: str,
    requirement: Requirement,
    points: int,
    copies: int,
    diamonds: int,
    ability: CharacterAbility,
) -> None:
    character = next(character for character in CHARACTERS if character.id == card_id)
    assert character.requirement == requirement
    assert character.points == points
    assert character.copies == copies
    assert character.diamonds == diamonds
    assert character.ability_type is AbilityType.BLUE
    assert character.ability == ability
