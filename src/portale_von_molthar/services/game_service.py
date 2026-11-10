"""Multiplayer game rooms: seats, commands, chance resolution, and the Chronicle.

The service is transport-agnostic: entrypoints (the FastAPI app, tests, a future CLI
or bot runner) call it with a game id and a seat, and send the returned views to
their clients. All methods are synchronous and assume a single thread, which holds
for an asyncio server.
"""

import random
import secrets
from collections import Counter
from dataclasses import dataclass, field
from typing import Final, Literal, TypeAlias, TypedDict

import pyspiel

from portale_von_molthar import molthar  # noqa: F401  (registers the game)
from portale_von_molthar.decisions import PaymentDecision
from portale_von_molthar.molthar import Action, MoltharState
from portale_von_molthar.services.catalog import character_name
from portale_von_molthar.services.views import (
    ACTIVATION_ACTIONS,
    TURN_ACTIONS,
    LogEntry,
    LogTone,
    PlayerView,
    TableView,
    activation_character,
    activation_plans,
    describe_action,
    player_views,
    table_view,
)

GameStatus: TypeAlias = Literal["lobby", "playing", "finished"]

MIN_PLAYERS: Final = 2
MAX_PLAYERS: Final = 5
MAX_NAME_LENGTH: Final = 20
_GAME_ID_ALPHABET: Final = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_GAME_ID_LENGTH: Final = 5


class GameError(Exception):
    """A command that is not allowed now; the message is shown to the player."""


class JoinResult(TypedDict):
    """Credentials of a seat; the token authenticates every later command."""

    game_id: str
    seat: int
    token: str


class ResultView(TypedDict):
    """The outcome of a finished game.

    Attributes:
        winners: Seats with the most power points, ties broken by diamonds.
    """

    winners: list[int]


class GameView(TypedDict):
    """Everything one seat sees; sent after every change.

    Attributes:
        game_id: Room code to share with other players.
        status: Lobby, running, or finished game.
        you: The viewing seat.
        players: Public information of every seat.
        table: The table as the viewer sees it, ``None`` in the lobby.
        log: The Chronicle, oldest line first.
        round: Round number, counted from the start player's turns.
        actions_taken: Actions used so far in the current turn.
        result: The winners once the game is finished.
    """

    game_id: str
    status: GameStatus
    you: int
    players: list[PlayerView]
    table: TableView | None
    log: list[LogEntry]
    round: int
    actions_taken: int
    result: ResultView | None


@dataclass
class _Seat:
    """A joined player."""

    name: str
    token: str
    connections: int = 0


@dataclass
class _Room:
    """One game from lobby to result."""

    game_id: str
    rng: random.Random
    seats: list[_Seat] = field(default_factory=list)
    state: MoltharState | None = None
    log: list[LogEntry] = field(default_factory=list)
    round: int = 1
    turn_player: int = 0
    turn_actions: int = 0


class GameService:
    """Creates rooms and applies players' commands to their games.

    Args:
        seed: Seed for game ids, tokens are always cryptographically random. Shuffles
            use one `random.Random` per room seeded from this; ``None`` seeds randomly.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)  # noqa: S311  (shuffling, not crypto)  # nosec B311
        self._rooms: dict[str, _Room] = {}

    # region public methods

    def activate(self, game_id: str, seat: int, action: int, plan: int) -> None:
        """Activate a character and pay for it with one complete plan.

        Args:
            game_id: Room to play in.
            seat: Player activating; must be the player to move.
            action: One of the activation actions offered in the view.
            plan: Index into the offered plans of that activation.

        Raises:
            GameError: If the activation or the plan is not available.
        """
        room, state = self._playing(game_id, seat)
        if action not in ACTIVATION_ACTIONS or action not in state.legal_actions(seat):
            message = "you cannot activate that character now"
            raise GameError(message)
        plans = activation_plans(state, seat, action)
        if not 0 <= plan < len(plans):
            message = "that payment does not fit the requirement"
            raise GameError(message)
        character = activation_character(state, seat, action)
        chosen = plans[plan]
        self._log(
            room,
            seat,
            action,
            f"activated {character_name(character.id)}",
            highlight=f"+{character.points}" if character.points else None,
            tone="power" if character.points else None,
        )
        state.apply_action(action)
        # The engine narrows the plans one pearl at a time in the plans' canonical order.
        while isinstance(step := state.pending_step, PaymentDecision):
            option = chosen.pearls[len(step.selected)]
            state.apply_action(MoltharState._payment_action(option))  # noqa: SLF001
        self._advance(room)

    def create_game(self, name: str) -> JoinResult:
        """Open a new room and seat its creator as host (seat 0).

        Args:
            name: Display name of the host.

        Returns:
            The new room's id and the host's credentials.
        """
        game_id = "".join(self._rng.choice(_GAME_ID_ALPHABET) for _ in range(_GAME_ID_LENGTH))
        while game_id in self._rooms:
            game_id = "".join(self._rng.choice(_GAME_ID_ALPHABET) for _ in range(_GAME_ID_LENGTH))
        room_seed = self._rng.getrandbits(64)
        self._rooms[game_id] = _Room(game_id, random.Random(room_seed))  # noqa: S311  # nosec B311
        return self.join_game(game_id, name)

    def discard(self, game_id: str, seat: int, values: list[int]) -> None:
        """Discard pearls at the end of the turn until the hand limit holds.

        Args:
            game_id: Room to play in.
            seat: Player over the hand limit.
            values: Printed values of the pearls to discard, exactly as many as owed.

        Raises:
            GameError: If no discard is owed, the count is wrong, or a pearl is missing.
        """
        room, state = self._playing(game_id, seat)
        owed = len(state.hands[seat]) - state.hand_limits[seat]
        if state.pending_step is not None or state.actions_left or owed <= 0:
            message = "you do not have to discard now"
            raise GameError(message)
        if len(values) != owed or Counter(values) - Counter(state.hands[seat]):
            message = f"choose exactly {owed} pearl{'s' if owed > 1 else ''} from your hand"
            raise GameError(message)
        listed = ", ".join(str(value) for value in sorted(values))
        text = f"discarded pearl{'s' if owed > 1 else ''}"
        self._log(room, seat, Action.DISCARD_1, text, highlight=listed)
        for value in values:
            state.apply_action(Action.DISCARD_1 + value - 1)
        self._advance(room)

    def join_game(self, game_id: str, name: str) -> JoinResult:
        """Seat a new player in a room that has not started yet.

        Args:
            game_id: Room to join.
            name: Display name; surrounding whitespace is removed.

        Returns:
            The room's id and the new seat's credentials.

        Raises:
            GameError: If the room is unknown, running, full, or the name is invalid.
        """
        room = self._room(game_id)
        name = name.strip()
        if not 1 <= len(name) <= MAX_NAME_LENGTH:
            message = f"names have 1 to {MAX_NAME_LENGTH} characters"
            raise GameError(message)
        if room.state is not None:
            message = "this game has already started"
            raise GameError(message)
        if len(room.seats) >= MAX_PLAYERS:
            message = f"this game already has {MAX_PLAYERS} players"
            raise GameError(message)
        room.seats.append(_Seat(name, secrets.token_urlsafe(16)))
        return JoinResult(
            game_id=room.game_id,
            seat=len(room.seats) - 1,
            token=room.seats[-1].token,
        )

    def play(self, game_id: str, seat: int, action: int) -> None:
        """Apply one offered move: a take, a display refresh, or a decision.

        Args:
            game_id: Room to play in.
            seat: Player to move.
            action: Action id of one of the view's moves.

        Raises:
            GameError: If the action is not offered; activations use `activate` and
                hand-limit discards use `discard`.
        """
        room, state = self._playing(game_id, seat)
        legal = state.legal_actions(seat)
        if action in ACTIVATION_ACTIONS or action not in legal:
            message = "that move is not available now"
            raise GameError(message)
        _, text = describe_action(state, seat, action, self._names(room))
        self._log(room, seat, action, text)
        state.apply_action(action)
        self._advance(room)

    def seat_for(self, game_id: str, token: str) -> int:
        """Return the seat a token belongs to.

        Args:
            game_id: Room the token was issued for.
            token: Secret returned by `create_game` or `join_game`.

        Returns:
            The seat index.

        Raises:
            GameError: If the room is unknown or the token does not belong to it.
        """
        room = self._room(game_id)
        for seat, player in enumerate(room.seats):
            if secrets.compare_digest(player.token, token):
                return seat
        message = "unknown player for this game"
        raise GameError(message)

    def set_connected(self, game_id: str, seat: int, *, connected: bool) -> None:
        """Count one connection of a seat opening or closing.

        Args:
            game_id: Room of the seat.
            seat: Seat whose connection changed.
            connected: ``True`` when a connection opened, ``False`` when it closed.
        """
        player = self._room(game_id).seats[seat]
        player.connections = max(0, player.connections + (1 if connected else -1))

    def start_game(self, game_id: str, seat: int) -> None:
        """Deal the displays and begin the first turn; only the host may start.

        Args:
            game_id: Room to start.
            seat: Seat asking to start.

        Raises:
            GameError: If `seat` is not the host, the game runs, or too few joined.
        """
        room = self._room(game_id)
        if seat != 0:
            message = "only the host can start the game"
            raise GameError(message)
        if room.state is not None:
            message = "this game has already started"
            raise GameError(message)
        if len(room.seats) < MIN_PLAYERS:
            message = f"at least {MIN_PLAYERS} players are needed"
            raise GameError(message)
        game = pyspiel.load_game(f"python_portale_von_molthar(players={len(room.seats)})")
        room.state = game.new_initial_state()
        self._resolve_chance(room)

    def view(self, game_id: str, seat: int) -> GameView:
        """Return everything `seat` may see of its room.

        Args:
            game_id: Room to look at.
            seat: Viewing seat.

        Returns:
            The seat's view; `table` is ``None`` in the lobby.
        """
        room = self._room(game_id)
        state = room.state
        names = self._names(room)
        connected = [player.connections > 0 for player in room.seats]
        result: ResultView | None = None
        if state is not None and state.is_terminal():
            returns = state.returns()
            result = ResultView(
                winners=[player for player, value in enumerate(returns) if value == max(returns)],
            )
        status: GameStatus = "lobby" if state is None else "finished" if result else "playing"
        return GameView(
            game_id=room.game_id,
            status=status,
            you=seat,
            players=player_views(state, names, connected),
            table=None if state is None else table_view(state, seat, names),
            log=room.log,
            round=room.round,
            actions_taken=room.turn_actions,
            result=result,
        )

    # endregion

    # region private methods

    def _room(self, game_id: str) -> _Room:
        """Return a room by id (case-insensitive)."""
        room = self._rooms.get(game_id.strip().upper())
        if room is None:
            message = f"there is no game {game_id}"
            raise GameError(message)
        return room

    def _playing(self, game_id: str, seat: int) -> tuple[_Room, MoltharState]:
        """Return a running room and its state, checking that `seat` is to move."""
        room = self._room(game_id)
        state = room.state
        if state is None or state.is_terminal():
            message = "the game is not running"
            raise GameError(message)
        if state.current_player() != seat:
            message = "it is not your turn"
            raise GameError(message)
        return room, state

    @staticmethod
    def _names(room: _Room) -> list[str]:
        """Return the player name per seat."""
        return [player.name for player in room.seats]

    @staticmethod
    def _log(  # noqa: PLR0913  # the Chronicle line's fields
        room: _Room,
        seat: int,
        action: int,
        text: str,
        *,
        highlight: str | None = None,
        tone: LogTone | None = None,
    ) -> None:
        """Append a Chronicle line, numbering actions that use up one of the turn's."""
        number: int | None = None
        if action in TURN_ACTIONS:
            room.turn_actions += 1
            number = room.turn_actions
        room.log.append(
            LogEntry(
                player=room.seats[seat].name,
                text=text,
                highlight=highlight,
                tone=tone,
                action=number,
            ),
        )

    def _advance(self, room: _Room) -> None:
        """Resolve chance draws and track turn changes after a command."""
        self._resolve_chance(room)
        state = room.state
        if state is None or state.is_terminal():
            return
        mover = state.current_player()
        if mover != room.turn_player:
            if mover == 0:
                room.round += 1
            room.turn_player = mover
            room.turn_actions = 0

    @staticmethod
    def _resolve_chance(room: _Room) -> None:
        """Draw cards until a player is to move or the game is over."""
        state = room.state
        while state is not None and state.is_chance_node():
            outcomes, weights = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(room.rng.choices(outcomes, weights=weights)[0])

    # endregion
