"""Tests for structured character-card data."""

from portale_von_molthar.cards import CHARACTERS


def test_character_data_matches_docs() -> None:
    """`CHARACTERS` must mirror the green-card table in docs/character_cards.md."""
    assert len(CHARACTERS) == 14
    assert sum(character.copies for character in CHARACTERS) == 23
    assert len({character.id for character in CHARACTERS}) == 14
