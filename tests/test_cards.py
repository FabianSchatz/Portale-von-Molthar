"""Tests for structured character-card data."""

from portale_von_molthar.abilities import (
    AbilityType,
    PearlValueSubstitutionAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.cards import CHARACTERS


def test_character_data_matches_docs() -> None:
    """`CHARACTERS` must contain green cards and implemented virtual providers."""
    assert len(CHARACTERS) == 25
    assert sum(character.copies for character in CHARACTERS) == 35
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
