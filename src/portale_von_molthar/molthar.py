"""Minimal OpenSpiel foundation for Die Portale von Molthar."""

from collections.abc import Mapping

import pyspiel

from portale_von_molthar.cards import CharacterCard, PearlCard
from portale_von_molthar.player_state import PlayerState

MIN_PLAYERS = 2
MAX_PLAYERS = 5
PEARL_CARD_COPIES = 7
PEARL_MARKET_SIZE = 4
CHARACTER_CARD_COUNT = 54
CHARACTER_MARKET_SIZE = 2
ACTIONS_PER_TURN = 3

_GAME_TYPE = pyspiel.GameType(
    short_name="python_portale_von_molthar",
    long_name="Die Portale von Molthar",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=MAX_PLAYERS,
    min_num_players=MIN_PLAYERS,
    provides_information_state_string=False,
    provides_information_state_tensor=False,
    provides_observation_string=False,
    provides_observation_tensor=False,
    parameter_specification={"players": MIN_PLAYERS},
)


class MoltharState(pyspiel.State):  # type: ignore[misc]
    """The players and card zones of a Molthar game."""

    def __init__(self, game: "MoltharGame") -> None:
        """Create the initial players, decks, markets, and turn state.

        Args:
            game: Game that owns this state.
        """
        super().__init__(game)
        self.players = [PlayerState() for _ in range(game.num_players())]
        pearl_cards = [PearlCard(value) for _ in range(PEARL_CARD_COPIES) for value in range(1, 9)]
        character_cards = [
            CharacterCard(
                name=f"Character {card_number}",
                requirements=((card_number - 1) % 8 + 1,),
                power_points=(card_number - 1) % 4 + 1,
            )
            for card_number in range(1, CHARACTER_CARD_COUNT + 1)
        ]
        self.pearl_market = pearl_cards[:PEARL_MARKET_SIZE]
        self.pearl_deck = pearl_cards[PEARL_MARKET_SIZE:]
        self.character_market = character_cards[:CHARACTER_MARKET_SIZE]
        self.character_deck = character_cards[CHARACTER_MARKET_SIZE:]
        self.remaining_actions = ACTIONS_PER_TURN
        self._current_player = 0

    def __str__(self) -> str:
        """Return a concise representation of the state."""
        return (
            f"MoltharState(players={len(self.players)}, current_player={self._current_player}, "
            f"remaining_actions={self.remaining_actions}, pearl_market={len(self.pearl_market)}, "
            f"pearl_deck={len(self.pearl_deck)}, "
            f"character_market={len(self.character_market)}, "
            f"character_deck={len(self.character_deck)})"
        )

    def _apply_action(self, action: int) -> None:
        """Reject actions because gameplay is not implemented.

        Args:
            action: OpenSpiel action identifier.

        Raises:
            ValueError: Always, because this foundation defines no actions.
        """
        message = f"Game actions are not implemented; cannot apply action {action}."
        raise ValueError(message)

    def _legal_actions(self, player: int) -> list[int]:
        """Return no actions for the inert state.

        Args:
            player: Player whose available actions were requested.

        Returns:
            An empty action list.
        """
        del player
        return []

    def current_player(self) -> int:
        """Return the player whose turn it is."""
        return self._current_player

    def is_terminal(self) -> bool:
        """Return whether the initial game state is terminal."""
        return False

    def returns(self) -> list[float]:
        """Return each player's current power points."""
        return [float(player.power_points) for player in self.players]


class MoltharGame(pyspiel.Game):  # type: ignore[misc]
    """OpenSpiel game metadata and state factory for Molthar."""

    def __init__(self, params: Mapping[str, int] | None = None) -> None:
        """Create a game for two to five players.

        Args:
            params: OpenSpiel parameters. ``players`` selects the player count.

        Raises:
            ValueError: If the player count is outside the supported range.
        """
        game_params = dict(params or {})
        num_players = game_params.get("players", MIN_PLAYERS)
        if not MIN_PLAYERS <= num_players <= MAX_PLAYERS:
            message = f"The number of players must be between {MIN_PLAYERS} and {MAX_PLAYERS}."
            raise ValueError(message)

        game_info = pyspiel.GameInfo(
            num_distinct_actions=0,
            max_chance_outcomes=0,
            num_players=num_players,
            min_utility=0.0,
            max_utility=float("inf"),
            utility_sum=None,
            max_game_length=0,
        )
        super().__init__(_GAME_TYPE, game_info, game_params)

    def new_initial_state(self) -> MoltharState:
        """Return a new initialized Molthar state."""
        return MoltharState(self)


pyspiel.register_game(_GAME_TYPE, MoltharGame)
