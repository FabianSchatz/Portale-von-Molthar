"""Tests for structured character-card data."""

from portale_von_molthar.abilities import (
    AbilityType,
    GainActionsAbility,
    NeighborActivationAbility,
    PearlValueSubstitutionAbility,
    VirtualPearlAbility,
)
from portale_von_molthar.cards import CHARACTERS
from portale_von_molthar.requirements import AnyOf, ExactValues


def test_character_data_matches_docs() -> None:
    """`CHARACTERS` must contain all currently implemented cards."""
    assert len(CHARACTERS) == 33
    assert sum(character.copies for character in CHARACTERS) == 45
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
    assert cards["golem_1"].requirement == ExactValues((4, 4, 6, 8))
    assert cards["golem_2"].requirement == ExactValues((1, 3, 5, 7))
    for card_id in ("golem_1", "golem_2"):
        assert cards[card_id].ability_type is AbilityType.RED
        assert cards[card_id].ability == GainActionsAbility(3)
