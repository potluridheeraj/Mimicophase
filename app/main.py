from __future__ import annotations

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


def _room_state(code: str, token: str) -> dict:
    room = store.rooms[code]
    info = store.get_info(token)
    viewer_id = info.player_id
    player = room.players[viewer_id] if viewer_id else None

    players = [
        {
            "id": p.id,
            "name": p.name,
            "alive": p.alive,
            "connected": p.connected,
            "seat": p.seat,
        }
        for p in [room.players[pid] for pid in room.order]
    ]

    role = player.role.value if player and player.role else None
    teammates = []
    if player and player.role == Role.MIMICOPHASE:
        teammates = [room.players[pid].name for pid in room.alive_by_role(Role.MIMICOPHASE) if pid != player.id]

    return {
        "code": code,
        "phase": room.phase.value,
        "cycle": room.cycle,
        "winner": room.winner,
        "players": players,
        "you": {
            "id": viewer_id,
            "name": player.name if player else "Host",
            "role": role,
            "alive": player.alive if player else True,
            "is_host": info.is_host,
            "teammates": teammates,
        },
        "morning_deaths": [room.players[pid].name for pid in room.morning_deaths],
        "runoff_candidates": [{"id": pid, "name": room.players[pid].name} for pid in room.runoff_candidates],
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
    return {"code": room.code, "token": token}


@app.post("/api/room/join")
def join_room(payload: JoinRoomIn):
    try:
        room, token, player_id = store.join_room(payload.code.strip().upper(), payload.name.strip() or "Crew")
        return {"code": room.code, "token": token, "player_id": player_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/room/rejoin")
def rejoin_room(payload: RejoinIn):
    try:
        room = store.rejoin_room(payload.code.strip().upper(), payload.token)
        return {"code": room.code}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/state/{code}")
def state(code: str, token: str):
    code = code.upper()
    try:
        return _room_state(code, token)
    except Exception as exc:  # broad for lightweight app API mapping
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _require_host(token: str):
    info = store.get_info(token)
    if not info.is_host:
        raise HTTPException(status_code=403, detail="Host only")
    return store.rooms[info.room_code]


@app.post("/api/host/start")
def start_game(payload: ActionIn):
    room = _require_host(payload.token)
    try:
        room.assign_roles()
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/host/seats")
def set_seats(payload: SeatsIn):
    room = _require_host(payload.token)
    room.reorder_by_seats(payload.ordered_ids)
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
    room.set_unanimous_action(Role.MIMICOPHASE, payload.target)
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
    room.set_unanimous_action(Role.CAPTAIN, payload.target)
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
    return {"ok": True}


@app.post("/api/host/advance")
def advance(payload: ActionIn):
    room = _require_host(payload.token)
    if room.phase in (Phase.MORNING, Phase.DISCUSSION):
        room.advance_day()
    return {"ok": True, "phase": room.phase.value}


@app.post("/api/day/nominate")
def nominate(payload: ActionIn):
    room = store.get_room_for_token(payload.token)
    info = store.get_info(payload.token)
    room.submit_nomination(info.player_id, payload.target)
    return {"ok": True}


@app.post("/api/host/finalize-nominations")
def finalize_nominations(payload: ActionIn):
    room = _require_host(payload.token)
    room.finalize_nominations()
    return {"ok": True, "phase": room.phase.value}


@app.post("/api/day/vote")
def vote(payload: VoteIn):
    room = store.get_room_for_token(payload.token)
    info = store.get_info(payload.token)
    room.submit_runoff_vote(info.player_id, payload.choice)
    return {"ok": True}


@app.post("/api/host/finalize-vote")
def finalize_vote(payload: ActionIn):
    room = _require_host(payload.token)
    eliminated = room.finalize_runoff()
    return {"ok": True, "eliminated": eliminated, "phase": room.phase.value}
