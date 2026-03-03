from __future__ import annotations

import logging
from pathlib import Path
import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .game import Phase, Role
from .store import store

app = FastAPI(title="Mimicophase Local")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

_action_logger = logging.getLogger("mimicophase.actions")
if not _action_logger.handlers:
    _action_logger.setLevel(logging.INFO)
    _log_path = Path(__file__).resolve().parent / "action.log"
    _file_handler = logging.FileHandler(_log_path, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    _action_logger.addHandler(_file_handler)


def _log_action(*, action: str, token: str | None = None, room_code: str | None = None, target: str | None = None, details: str | None = None) -> None:
    actor = "Unknown"
    code = room_code
    if token:
        info = store.sessions.get(token)
        if info:
            code = code or info.room_code
            if info.player_id:
                room = store.rooms.get(info.room_code)
                player = room.players.get(info.player_id) if room else None
                actor = player.name if player else info.player_id
            elif info.is_host:
                actor = "Host"

    parts = [f"room={code or 'UNKNOWN'}", f"actor={actor}", f"action={action}"]
    if target:
        parts.append(f"target={target}")
    if details:
        parts.append(f"details={details}")
    _action_logger.info(" | ".join(parts))


class CreateRoomIn(BaseModel):
    host_name: str


class JoinRoomIn(BaseModel):
    code: str
    name: str


class RejoinIn(BaseModel):
    code: str
    token: str


class ActionIn(BaseModel):
    token: str
    target: str


class VoteIn(BaseModel):
    token: str
    choice: str


class SeatsIn(BaseModel):
    token: str
    ordered_ids: list[str]


class TimerSettingsIn(BaseModel):
    token: str
    morning_s: int
    discussion_s: int
    nomination_s: int
    runoff_s: int


def _host_announcement(room) -> dict:
    close_eyes = ""
    open_eyes = ""
    action = ""

    if room.phase == Phase.NIGHT_MIMIC:
        open_eyes = "Mimicophase"
        action = "Choose one non-Mimicophase player to eliminate."
    elif room.phase == Phase.NIGHT_CAPTAIN:
        close_eyes = "Mimicophase"
        open_eyes = "Captain"
        action = "Inspect one player."
    elif room.phase == Phase.NIGHT_DOCTOR:
        close_eyes = "Captain"
        open_eyes = "Doctor"
        action = "Protect one player."
    elif room.phase == Phase.MORNING:
        close_eyes = "Doctor"
        open_eyes = "Everyone"
        action = "Announce morning results."
    elif room.phase == Phase.DISCUSSION:
        open_eyes = "Everyone"
        action = "Start open discussion."
    elif room.phase == Phase.NOMINATION:
        open_eyes = "Everyone"
        action = "Ask for nominations."
    elif room.phase == Phase.RUNOFF:
        open_eyes = "Everyone"
        action = "Run the vote between the nominated players."
    elif room.phase == Phase.SINGLE_NOMINEE:
        open_eyes = "Everyone"
        action = "Vote to execute or reject the single nominee."
    elif room.phase == Phase.ENDED:
        open_eyes = "Everyone"
        action = f"Game ended. Winner: {room.winner or 'unknown'}."

    parts = []
    if close_eyes:
        parts.append(f"{close_eyes}, close your eyes.")
    if open_eyes:
        parts.append(f"{open_eyes}, open your eyes.")
    if action:
        parts.append(action)

    return {
        "close_eyes": close_eyes,
        "open_eyes": open_eyes,
        "action": action,
        "text": " ".join(parts),
    }


def _room_state(code: str, token: str) -> dict:
    room = store.rooms[code]
    store.refresh_connections(room)
    room.tick()
    info = store.get_info(token)
    viewer_id = info.player_id
    player = room.players[viewer_id] if viewer_id else None

    players = [
        {
            "id": p.id,
            "name": p.name,
            "alive": p.alive,
            "connected": p.connected,
            "kicked": p.kicked,
            "seat": p.seat,
        }
        for p in [room.players[pid] for pid in room.order]
        if not p.kicked
    ]

    role = player.role.value if player and player.role else None
    teammates = []
    if player and player.role == Role.MIMICOPHASE:
        teammates = [room.players[mid].name for mid in room.alive_by_role(Role.MIMICOPHASE) if mid != player.id]

    return {
        "code": code,
        "phase": room.phase.value,
        "cycle": room.cycle,
        "winner": room.winner,
        "phase_deadline": room.phase_deadline,
        "seconds_left": max(0, int(room.phase_deadline - time.time())) if room.phase_deadline else None,
        "players": players,
        "you": {
            "id": viewer_id,
            "name": player.name if player else "Host",
            "role": role,
            "alive": player.alive if player else True,
            "connected": player.connected if player else True,
            "is_host": info.is_host,
            "token": token,
            "teammates": teammates,
        },
        "morning_deaths": [room.players[pid].name for pid in room.morning_deaths],
        "runoff_candidates": [{"id": pid, "name": room.players[pid].name} for pid in room.runoff_candidates],
        "host_announcement": _host_announcement(room),
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/host", response_class=HTMLResponse)
def host_page(request: Request):
    return templates.TemplateResponse("host.html", {"request": request})


@app.get("/play", response_class=HTMLResponse)
def player_page(request: Request):
    return templates.TemplateResponse("player.html", {"request": request})


@app.post("/api/room/create")
def create_room(payload: CreateRoomIn):
    room, token = store.create_room(payload.host_name.strip() or "Host")
    _log_action(action="room.create", token=token, room_code=room.code, details=f"host_name={payload.host_name.strip() or 'Host'}")
    return {"code": room.code, "token": token}


@app.post("/api/room/join")
def join_room(payload: JoinRoomIn):
    try:
        room, token, player_id = store.join_room(payload.code.strip().upper(), payload.name.strip() or "Crew")
        _log_action(action="room.join", token=token, room_code=room.code, details=f"player_id={player_id}")
        return {"code": room.code, "token": token, "player_id": player_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/room/rejoin")
def rejoin_room(payload: RejoinIn):
    try:
        room = store.rejoin_room(payload.code.strip().upper(), payload.token)
        _log_action(action="room.rejoin", token=payload.token, room_code=room.code)
        return {"code": room.code}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ping")
def ping(payload: ActionIn):
    store.touch_session(payload.token)
    return {"ok": True}


@app.get("/api/state/{code}")
def state(code: str, token: str):
    code = code.upper()
    try:
        store.touch_session(token)
        return _room_state(code, token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_host(token: str):
    info = store.get_info(token)
    if not info.is_host:
        raise HTTPException(status_code=403, detail="Host only")
    room = store.rooms[info.room_code]
    store.refresh_connections(room)
    return room


@app.post("/api/host/start")
def start_game(payload: ActionIn):
    room = _require_host(payload.token)
    try:
        room.assign_roles()
        _log_action(action="host.start", token=payload.token, room_code=room.code)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/host/reset")
def reset_game(payload: ActionIn):
    room = _require_host(payload.token)
    room.reset_game()
    _log_action(action="host.reset", token=payload.token, room_code=room.code)
    return {"ok": True}


@app.post("/api/host/kick")
def kick_player(payload: ActionIn):
    room = _require_host(payload.token)
    room.kick_player(payload.target)
    _log_action(action="host.kick", token=payload.token, room_code=room.code, target=payload.target)
    return {"ok": True}


@app.post("/api/host/settings")
def set_settings(payload: TimerSettingsIn):
    room = _require_host(payload.token)
    room.set_phase_durations(payload.morning_s, payload.discussion_s, payload.nomination_s, payload.runoff_s)
    _log_action(
        action="host.settings",
        token=payload.token,
        room_code=room.code,
        details=(
            f"morning_s={payload.morning_s},discussion_s={payload.discussion_s},"
            f"nomination_s={payload.nomination_s},runoff_s={payload.runoff_s}"
        ),
    )
    return {"ok": True}


@app.post("/api/host/seats")
def set_seats(payload: SeatsIn):
    room = _require_host(payload.token)
    room.reorder_by_seats(payload.ordered_ids)
    _log_action(action="host.seats", token=payload.token, room_code=room.code, details=f"ordered_ids={','.join(payload.ordered_ids)}")
    return {"ok": True}


@app.post("/api/night/mimic")
def mimic_action(payload: ActionIn):
    room = store.get_room_for_token(payload.token)
    info = store.get_info(payload.token)
    player = room.players[info.player_id]
    if player.role != Role.MIMICOPHASE:
        raise HTTPException(status_code=403, detail="Mimicophase only")
    if room.phase != Phase.NIGHT_MIMIC:
        raise HTTPException(status_code=400, detail="Wrong phase")
    room.set_unanimous_action(Role.MIMICOPHASE, payload.target, actor_id=info.player_id)
    _log_action(action="night.mimic", token=payload.token, room_code=room.code, target=payload.target)
    return {"ok": True}


@app.post("/api/night/captain")
def captain_action(payload: ActionIn):
    room = store.get_room_for_token(payload.token)
    info = store.get_info(payload.token)
    player = room.players[info.player_id]
    if player.role != Role.CAPTAIN:
        raise HTTPException(status_code=403, detail="Captain only")
    if room.phase != Phase.NIGHT_CAPTAIN:
        raise HTTPException(status_code=400, detail="Wrong phase")
    room.set_unanimous_action(Role.CAPTAIN, payload.target, actor_id=info.player_id)
    _log_action(action="night.captain", token=payload.token, room_code=room.code, target=payload.target)
    return {"ok": True}


@app.post("/api/night/doctor")
def doctor_action(payload: ActionIn):
    room = store.get_room_for_token(payload.token)
    info = store.get_info(payload.token)
    player = room.players[info.player_id]
    if player.role != Role.DOCTOR:
        raise HTTPException(status_code=403, detail="Doctor only")
    if room.phase != Phase.NIGHT_DOCTOR:
        raise HTTPException(status_code=400, detail="Wrong phase")
    room.set_doctor_action(payload.target)
    _log_action(action="night.doctor", token=payload.token, room_code=room.code, target=payload.target)
    return {"ok": True}


@app.post("/api/host/advance")
def advance(payload: ActionIn):
    room = _require_host(payload.token)
    if room.phase in (Phase.MORNING, Phase.DISCUSSION):
        room.advance_day()
    _log_action(action="host.advance", token=payload.token, room_code=room.code, details=f"new_phase={room.phase.value}")
    return {"ok": True, "phase": room.phase.value}


@app.post("/api/day/nominate")
def nominate(payload: ActionIn):
    try:
        room = store.get_room_for_token(payload.token)
        info = store.get_info(payload.token)
        room.submit_nomination(info.player_id, payload.target)
        _log_action(action="day.nominate", token=payload.token, room_code=room.code, target=payload.target)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/host/finalize-nominations")
def finalize_nominations(payload: ActionIn):
    room = _require_host(payload.token)
    room.finalize_nominations()
    _log_action(action="host.finalize_nominations", token=payload.token, room_code=room.code, details=f"new_phase={room.phase.value}")
    return {"ok": True, "phase": room.phase.value}


@app.post("/api/day/vote")
def vote(payload: VoteIn):
    try:
        room = store.get_room_for_token(payload.token)
        info = store.get_info(payload.token)
        room.submit_runoff_vote(info.player_id, payload.choice)
        _log_action(action="day.vote", token=payload.token, room_code=room.code, target=payload.choice)
        auto_finalized = False
        if len(room.runoff_votes) >= len(room.active_living_player_ids()):
            room.finalize_runoff()
            auto_finalized = True
            _log_action(action="day.vote.auto_finalize", token=payload.token, room_code=room.code, details=f"new_phase={room.phase.value}")
        return {"ok": True, "auto_finalized": auto_finalized, "phase": room.phase.value}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/host/finalize-vote")
def finalize_vote(payload: ActionIn):
    room = _require_host(payload.token)
    try:
        eliminated = room.finalize_runoff()
        _log_action(action="host.finalize_vote", token=payload.token, room_code=room.code, target=eliminated, details=f"new_phase={room.phase.value}")
        return {"ok": True, "eliminated": eliminated, "phase": room.phase.value}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
