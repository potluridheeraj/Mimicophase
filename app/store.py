from __future__ import annotations

import secrets
import string
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .game import GameRoom, Player


@dataclass
class SessionInfo:
    room_code: str
    player_id: Optional[str] = None
    is_host: bool = False


class GameStore:
    def __init__(self) -> None:
        self.rooms: Dict[str, GameRoom] = {}
        self.sessions: Dict[str, SessionInfo] = {}
        self.last_seen: Dict[str, float] = {}
        self.disconnect_timeout_s = 15

    def create_room(self, host_name: str) -> tuple[GameRoom, str]:
        code = self._new_code()
        host_token = self._new_token()
        room = GameRoom(code=code, host_token=host_token)
        host_player = Player(id=self._new_id(), name=host_name, token=host_token)
        room.add_player(host_player)
        self.rooms[code] = room
        self.sessions[host_token] = SessionInfo(room_code=code, player_id=host_player.id, is_host=True)
        self.last_seen[host_token] = time.time()
        return room, host_token

    def join_room(self, code: str, name: str) -> tuple[GameRoom, str, str]:
        room = self._get_room(code)
        normalized_name = name.strip().casefold()
        active_names = {
            player.name.strip().casefold()
            for player in room.players.values()
            if not player.kicked
        }
        if normalized_name in active_names:
            raise ValueError("Player name is already taken")
        token = self._new_token()
        player = Player(id=self._new_id(), name=name, token=token)
        room.add_player(player)
        self.sessions[token] = SessionInfo(room_code=room.code, player_id=player.id, is_host=False)
        self.last_seen[token] = time.time()
        return room, token, player.id

    def rejoin_room(self, code: str, token: str) -> GameRoom:
        room = self._get_room(code)
        info = self.sessions.get(token)
        if not info or info.room_code != code:
            raise ValueError("Invalid session token")
        if info.player_id:
            room.players[info.player_id].connected = True
        self.last_seen[token] = time.time()
        return room

    def touch_session(self, token: str) -> None:
        info = self.sessions.get(token)
        if not info:
            return
        self.last_seen[token] = time.time()
        room = self._get_room(info.room_code)
        if info.player_id and info.player_id in room.players:
            p = room.players[info.player_id]
            if not p.kicked:
                p.connected = True

    def refresh_connections(self, room: GameRoom) -> None:
        now = time.time()
        for token, info in self.sessions.items():
            if info.room_code != room.code or not info.player_id:
                continue
            player = room.players.get(info.player_id)
            if not player or player.kicked:
                continue
            player.connected = (now - self.last_seen.get(token, 0)) <= self.disconnect_timeout_s

    def get_room_for_token(self, token: str) -> GameRoom:
        info = self.sessions.get(token)
        if not info:
            raise ValueError("Unknown session")
        self.touch_session(token)
        room = self._get_room(info.room_code)
        self.refresh_connections(room)
        return room

    def get_info(self, token: str) -> SessionInfo:
        info = self.sessions.get(token)
        if not info:
            raise ValueError("Unknown session")
        return info

    def _get_room(self, code: str) -> GameRoom:
        room = self.rooms.get(code.upper())
        if not room:
            raise ValueError("Room not found")
        return room

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(4))
            if code not in self.rooms:
                return code

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def _new_id() -> str:
        return secrets.token_hex(6)


store = GameStore()
