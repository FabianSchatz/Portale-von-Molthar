"""Tests for player-owned state."""

from portale_von_molthar import CharacterCard, PlayerState


def test_power_points() -> None:
    player = PlayerState(
        activated_characters=[
            CharacterCard("First", (1,), 2),
            CharacterCard("Second", (2,), 3),
        ],
    )

    assert player.power_points == 5


def test_player_state_uses_independent_card_lists() -> None:
    first_player = PlayerState()
    second_player = PlayerState()

    first_player.activated_characters.append(CharacterCard("First", (1,), 2))

    assert second_player.activated_characters == []
