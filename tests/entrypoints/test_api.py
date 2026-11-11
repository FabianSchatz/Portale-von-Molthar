"""Tests for the HTTP and WebSocket API."""

from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from portale_von_molthar.agents.bots import RandomBot
from portale_von_molthar.entrypoints.api import create_app
from portale_von_molthar.game.molthar import Action
from portale_von_molthar.services.game_service import GameService


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    """Return a client for an app without a built frontend."""
    return TestClient(create_app(GameService(0), frontend_dist=tmp_path / "missing"))


def test_create_app_catalog(client: TestClient) -> None:
    response = client.get("/api/catalog")
    assert response.status_code == 200
    assert response.json()["goblin"]["requirement"] == "One pair"


def test_create_app_create_and_join(client: TestClient) -> None:
    created = client.post("/api/games", json={"name": "Ada"})
    assert created.status_code == 201
    game_id = created.json()["game_id"]
    joined = client.post(f"/api/games/{game_id}/players", json={"name": "Ben"})
    assert joined.json()["seat"] == 1
    missing = client.post("/api/games/NOPE/players", json={"name": "Cy"})
    assert missing.status_code == 409
    invalid = client.post(f"/api/games/{game_id}/players", json={"name": ""})
    assert invalid.status_code == 422


def test_create_app_websocket_game(client: TestClient) -> None:
    host = client.post("/api/games", json={"name": "Ada"}).json()
    guest = client.post(f"/api/games/{host['game_id']}/players", json={"name": "Ben"}).json()
    with (
        client.websocket_connect(f"/ws/{host['game_id']}?token={host['token']}") as ada,
        client.websocket_connect(f"/ws/{host['game_id']}?token={guest['token']}") as ben,
    ):
        assert ada.receive_json()["view"]["players"][0]["connected"] is True
        ada.receive_json()  # Ben connected
        lobby = ben.receive_json()["view"]
        assert lobby["status"] == "lobby"
        assert lobby["you"] == 1

        ben.send_json({"type": "start"})
        assert ben.receive_json() == {
            "type": "error",
            "message": "only the host can start the game",
        }
        ada.send_json({"type": "bogus"})
        assert ada.receive_json() == {"type": "error", "message": "malformed command"}

        ada.send_json({"type": "start"})
        assert ada.receive_json()["view"]["status"] == "playing"
        assert ben.receive_json()["view"]["table"]["prompt"] is None

        ada.send_json({"type": "play", "action": Action.TAKE_PEARL_DECK})
        view = ada.receive_json()["view"]
        ben.receive_json()
        assert len(view["table"]["hand"]) == 1
        assert view["log"][-1]["text"] == "took a hidden pearl"


def test_create_app_websocket_bot_game(tmp_path: Path) -> None:
    service = GameService(0, bot_factory=lambda _players, _level, seed: RandomBot(seed))
    client = TestClient(create_app(service, frontend_dist=tmp_path / "missing", bot_delay=0))
    host = client.post("/api/games", json={"name": "Ada"}).json()
    with client.websocket_connect(f"/ws/{host['game_id']}?token={host['token']}") as ada:
        ada.receive_json()
        ada.send_json({"type": "add_bot", "difficulty": "medium"})
        bot = ada.receive_json()["view"]["players"][1]
        assert (bot["name"], bot["bot"], bot["connected"]) == ("Medium bot 1", "medium", True)
        ada.send_json({"type": "add_bot", "difficulty": "impossible"})
        assert ada.receive_json() == {"type": "error", "message": "malformed command"}

        ada.send_json({"type": "start"})
        ada.receive_json()
        for _ in range(3):
            ada.send_json({"type": "play", "action": Action.TAKE_PEARL_DECK})
            view = ada.receive_json()["view"]
        # The bot plays its whole turn, one view per action, then it is Ada's turn again.
        while view["table"]["current_player"] != 0:
            view = ada.receive_json()["view"]
        assert any(line["player"] == "Medium bot 1" for line in view["log"])


def test_create_app_websocket_rejects_bad_tokens(client: TestClient) -> None:
    host = client.post("/api/games", json={"name": "Ada"}).json()
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(f"/ws/{host['game_id']}?token=wrong") as socket,
    ):
        socket.receive_json()
    assert closed.value.code == status.WS_1008_POLICY_VIOLATION


def test_create_app_serves_the_frontend(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<p>Molthar</p>")
    client = TestClient(create_app(GameService(0), frontend_dist=tmp_path))
    assert client.get("/").text == "<p>Molthar</p>"
