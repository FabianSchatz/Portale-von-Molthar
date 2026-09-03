"""Tests for the OpenSpiel Molthar foundation."""

from collections import Counter

import pyspiel
import pytest

from portale_von_molthar import CharacterCard, MoltharGame, MoltharState, PearlCard


@pytest.mark.parametrize("num_players", [2, 3, 4, 5])
def test_new_initial_state(num_players: int) -> None:
    game = MoltharGame({"players": num_players})

    state = game.new_initial_state()

    assert isinstance(state, MoltharState)
    assert len(state.players) == num_players
    assert all(player.pearl_cards == [] for player in state.players)
    assert all(player.portal == [] for player in state.players)
    assert all(player.activated_characters == [] for player in state.players)
    assert state.current_player() == 0
    assert state.remaining_actions == 3
    assert len(state.pearl_market) == 4
    assert len(state.pearl_deck) == 52
    assert len(state.character_market) == 2
    assert len(state.character_deck) == 52
    assert all(isinstance(card, PearlCard) for card in state.pearl_market + state.pearl_deck)
    pearl_card_counts = Counter(card.value for card in state.pearl_market + state.pearl_deck)
    assert pearl_card_counts == dict.fromkeys(range(1, 9), 7)
    assert all(
        isinstance(card, CharacterCard) for card in state.character_market + state.character_deck
    )
    assert state.legal_actions() == []
    assert not state.is_terminal()
    assert state.returns() == [0.0] * num_players


def test_new_initial_state_uses_independent_card_zones() -> None:
    game = MoltharGame()

    first_state = game.new_initial_state()
    second_state = game.new_initial_state()
    first_state.pearl_deck.pop()

    assert len(second_state.pearl_deck) == 52


def test_game_is_registered_with_open_spiel() -> None:
    game = pyspiel.load_game("python_portale_von_molthar")

    assert isinstance(game, MoltharGame)


@pytest.mark.parametrize("num_players", [1, 6])
def test_init_rejects_invalid_player_count(num_players: int) -> None:
    with pytest.raises(ValueError, match="between 2 and 5"):
        MoltharGame({"players": num_players})
