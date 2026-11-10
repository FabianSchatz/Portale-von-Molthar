"""HTTP and WebSocket API for multiplayer games.

Run the development server with::

    uvicorn portale_von_molthar.entrypoints.api:app --reload

REST creates and joins rooms and returns a seat token. Everything after that runs over
``/ws/{game_id}?token=...``: the server sends ``{"type": "view", "view": GameView}``
after every change and ``{"type": "error", "message": str}`` for a rejected command;
clients send the commands defined below. After every command, bots to move play one
action at a time, with a short pause in between so people can follow their moves. When
``frontend/dist`` exists, it is served at ``/`` so one process hosts the whole game.
"""

import asyncio
from pathlib import Path
from typing import Annotated, Final, Literal, TypeAlias

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from portale_von_molthar.agents.bots import Difficulty
from portale_von_molthar.services.catalog import CharacterInfo, character_catalog
from portale_von_molthar.services.game_service import (
    MAX_NAME_LENGTH,
    GameError,
    GameService,
    JoinResult,
)

_FRONTEND_DIST: Final = Path(__file__).resolve().parents[3] / "frontend" / "dist"
BOT_DELAY: Final = 0.7  # seconds between two bot actions


class NameBody(BaseModel):
    """Request body naming the player who creates or joins a game."""

    name: Annotated[str, Field(min_length=1, max_length=MAX_NAME_LENGTH)]


class StartCommand(BaseModel):
    """Host starts the game with everyone seated."""

    type: Literal["start"]


class AddBotCommand(BaseModel):
    """Host seats a bot of the given difficulty in the lobby."""

    type: Literal["add_bot"]
    difficulty: Difficulty


class PlayCommand(BaseModel):
    """Apply one offered move by its action id."""

    type: Literal["play"]
    action: int


class ActivateCommand(BaseModel):
    """Activate a character, paying with the plan at index `plan`."""

    type: Literal["activate"]
    action: int
    plan: int


class DiscardCommand(BaseModel):
    """Discard these pearl values at the hand limit."""

    type: Literal["discard"]
    values: list[int]


Command: TypeAlias = Annotated[
    StartCommand | AddBotCommand | PlayCommand | ActivateCommand | DiscardCommand,
    Field(discriminator="type"),
]
_COMMANDS: Final = TypeAdapter(Command)


class _Connections:
    """Open WebSockets per room and seat, to broadcast views after each change.

    Args:
        service: Game rooms whose views are sent.
        bot_delay: Pause in seconds before each bot action.
    """

    def __init__(self, service: GameService, bot_delay: float) -> None:
        self._service = service
        self._bot_delay = bot_delay
        self._sockets: dict[str, dict[WebSocket, int]] = {}

    def add(self, game_id: str, seat: int, socket: WebSocket) -> None:
        """Register an accepted socket for `seat`."""
        self._sockets.setdefault(game_id, {})[socket] = seat
        self._service.set_connected(game_id, seat, connected=True)

    def remove(self, game_id: str, socket: WebSocket) -> None:
        """Forget a closed socket."""
        seat = self._sockets.get(game_id, {}).pop(socket, None)
        if seat is not None:
            self._service.set_connected(game_id, seat, connected=False)

    async def broadcast(self, game_id: str) -> None:
        """Send every connected seat its own view of the room."""
        for socket, seat in list(self._sockets.get(game_id, {}).items()):
            try:
                await socket.send_json({"type": "view", "view": self._service.view(game_id, seat)})
            except (WebSocketDisconnect, RuntimeError):
                self.remove(game_id, socket)

    async def run_bots(self, game_id: str) -> None:
        """Let bots move one action at a time until a human is to move or the game ends.

        Two loops for the same room (two people sending commands) cannot corrupt it:
        each `GameService.step_bot` call is synchronous and re-checks whose turn it is.
        """
        while self._service.bot_to_move(game_id):
            await asyncio.sleep(self._bot_delay)
            if self._service.step_bot(game_id):
                await self.broadcast(game_id)


def create_app(
    service: GameService | None = None,
    frontend_dist: Path | None = None,
    bot_delay: float = BOT_DELAY,
) -> FastAPI:
    """Return the API around `service`.

    Args:
        service: Game rooms to expose; a fresh in-memory service by default.
        frontend_dist: Built frontend to serve at ``/``; defaults to ``frontend/dist``
            in the repository and is skipped when the folder does not exist.
        bot_delay: Pause in seconds before each bot action.

    Returns:
        The FastAPI application.
    """
    games = service or GameService()
    connections = _Connections(games, bot_delay)
    app = FastAPI(title="Portale von Molthar")

    # The views are TypedDicts already; pydantic needs typing_extensions ones for models.
    @app.get("/api/catalog", response_model=None)
    def catalog() -> dict[str, CharacterInfo]:
        """Return display data of every character card."""
        return character_catalog()

    @app.post("/api/games", status_code=status.HTTP_201_CREATED, response_model=None)
    def create_game(body: NameBody) -> JoinResult:
        """Open a room and seat its host."""
        return games.create_game(body.name)

    @app.post(
        "/api/games/{game_id}/players",
        status_code=status.HTTP_201_CREATED,
        response_model=None,
    )
    def join_game(game_id: str, body: NameBody) -> JoinResult:
        """Seat a new player in a room's lobby."""
        try:
            return games.join_game(game_id, body.name)
        except GameError as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    @app.websocket("/ws/{game_id}")
    async def play(socket: WebSocket, game_id: str, token: str) -> None:
        """Stream views to one seat and apply its commands."""
        await _serve(socket, games, connections, game_id, token)

    dist = frontend_dist or _FRONTEND_DIST
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return app


async def _serve(
    socket: WebSocket,
    games: GameService,
    connections: _Connections,
    game_id: str,
    token: str,
) -> None:
    """Authenticate one socket, then apply its commands until it disconnects."""
    try:
        seat = games.seat_for(game_id, token)
    except GameError:
        await socket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    game_id = games.view(game_id, seat)["game_id"]
    await socket.accept()
    connections.add(game_id, seat, socket)
    await connections.broadcast(game_id)
    try:
        while True:
            message = await socket.receive_json()
            try:
                _apply(games, game_id, seat, _COMMANDS.validate_python(message))
            except (GameError, ValidationError) as error:
                text = str(error) if isinstance(error, GameError) else "malformed command"
                await socket.send_json({"type": "error", "message": text})
                continue
            await connections.broadcast(game_id)
            await connections.run_bots(game_id)
    except WebSocketDisconnect:
        connections.remove(game_id, socket)
        await connections.broadcast(game_id)


def _apply(games: GameService, game_id: str, seat: int, command: Command) -> None:
    """Dispatch one validated command to the service."""
    if isinstance(command, StartCommand):
        games.start_game(game_id, seat)
    elif isinstance(command, AddBotCommand):
        games.add_bot(game_id, seat, command.difficulty)
    elif isinstance(command, PlayCommand):
        games.play(game_id, seat, command.action)
    elif isinstance(command, ActivateCommand):
        games.activate(game_id, seat, command.action, command.plan)
    else:
        games.discard(game_id, seat, command.values)


app: Final = create_app()  # pylint: disable=invalid-name  # uvicorn looks for `app`
