"""Tests for the character display catalog."""

import pytest

from portale_von_molthar.game.cards import CHARACTERS
from portale_von_molthar.services.catalog import character_catalog, character_name


def test_character_catalog_covers_every_card() -> None:
    catalog = character_catalog()
    assert set(catalog) == {character.id for character in CHARACTERS}
    for info in catalog.values():
        assert (info["ability"] is None) == (info["kind"] == "green")
        assert (info["timing"] is not None) == (info["kind"] == "blue")
        assert info["ability"] is None or len(info["ability"]) <= 60


@pytest.mark.parametrize(
    ("card_id", "requirement"),
    [
        ("dwarf", [6, 6, 8, 8]),
        ("irrlicht_1", [3, 3, 3, "or", 6, 6, 6]),
        ("captain_hook", [2, 2, 2, "and", "diamond"]),
        ("goblin", "One pair"),
        ("dementor", "Two pairs"),
        ("gnome", "One pair + 6, 6"),
        ("bilbo_odd", "3 odd cards"),
        ("terminator", "3 cards totalling 20"),
        ("flying_monkey", "Any cards totalling 10"),
        ("mad_hatter", "Run of 5"),
    ],
)
def test_character_catalog_requirement(card_id: str, requirement: str | list[int | str]) -> None:
    assert character_catalog()[card_id]["requirement"] == requirement


@pytest.mark.parametrize(
    ("card_id", "ability", "timing"),
    [
        ("golem_1", "Gain 3 extra actions now.", None),
        ("fuchur", "A wildcard pearl for every activation.", "during_turn"),
        ("barbarian_4", "A virtual 4 for every activation.", "during_turn"),
        ("rumpelstiltskin", "Any 3 counts as any value.", "during_turn"),
        ("peter_pan", "Any 1 may count as 8.", "during_turn"),
        ("reaper", "You may redraw your whole hand.", "after_turn"),
        ("little_red_riding_hood", "Gain 1 extra action now and every turn.", "persistent"),
    ],
)
def test_character_catalog_ability(card_id: str, ability: str, timing: str | None) -> None:
    info = character_catalog()[card_id]
    assert info["ability"] == ability
    assert info["timing"] == timing


@pytest.mark.parametrize(
    ("card_id", "name"),
    [
        ("irrlicht_2", "Irrlicht"),
        ("bilbo_even", "Bilbo"),
        ("frau_holle", "Frau Holle"),
        ("hansel_and_gretel", "Hansel and Gretel"),
        ("puss_in_boots", "Puss in Boots"),
        ("little_red_riding_hood", "Little Red Riding Hood"),
    ],
)
def test_character_name(card_id: str, name: str) -> None:
    assert character_name(card_id) == name
