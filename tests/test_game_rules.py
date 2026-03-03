from app.game import GameRoom, Player, Role, Phase


def _room_with_players(n=8):
    room = GameRoom(code="ABCD", host_token="h")
    for i in range(n):
        room.add_player(Player(id=f"p{i}", name=f"P{i}", token=f"t{i}"))
    return room


def test_assign_roles_and_start_phase():
    room = _room_with_players(8)
    room.assign_roles()
    assert room.phase == Phase.NIGHT_MIMIC
    assert len(room.alive_by_role(Role.DOCTOR)) == 1
    assert len(room.alive_by_role(Role.CAPTAIN)) >= 1


def test_night_resolution_doctor_protects():
    room = _room_with_players(6)
    # force roles
    room.players['p0'].role = Role.MIMICOPHASE
    room.players['p1'].role = Role.CAPTAIN
    room.players['p2'].role = Role.DOCTOR
    for pid in ['p3', 'p4', 'p5']:
        room.players[pid].role = Role.CREW
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, 'p3')
    room.set_unanimous_action(Role.CAPTAIN, 'p0')
    room.set_doctor_action('p3')

    assert room.players['p3'].alive
    assert not room.players['p0'].alive
    assert room.phase in (Phase.MORNING, Phase.ENDED)


def test_adjacent_players_circle_uses_living():
    room = _room_with_players(5)
    for p in room.players.values():
        p.role = Role.CREW
    room.players['p2'].alive = False
    assert room.adjacent_players('p1') == ['p0', 'p3']


def test_runoff_tie_requires_revote():
    room = _room_with_players(6)
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.RUNOFF
    room.runoff_candidates = ['p0', 'p1']
    for i, pid in enumerate(room.living_player_ids()):
        room.submit_runoff_vote(pid, 'p0' if i < 3 else 'p1')
    assert room.finalize_runoff() is None
    assert room.phase == Phase.RUNOFF

def test_mimics_must_be_unanimous_before_captain_phase():
    room = _room_with_players(6)
    room.players['p0'].role = Role.MIMICOPHASE
    room.players['p1'].role = Role.MIMICOPHASE
    room.players['p2'].role = Role.CAPTAIN
    room.players['p3'].role = Role.DOCTOR
    room.players['p4'].role = Role.CREW
    room.players['p5'].role = Role.CREW
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, 'p4', actor_id='p0')
    assert room.phase == Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, 'p5', actor_id='p1')
    assert room.phase == Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, 'p4', actor_id='p1')
    assert room.phase == Phase.NIGHT_CAPTAIN


def test_captains_must_be_unanimous_before_doctor_phase():
    room = _room_with_players(9)
    room.players['p0'].role = Role.MIMICOPHASE
    room.players['p1'].role = Role.MIMICOPHASE
    room.players['p2'].role = Role.CAPTAIN
    room.players['p3'].role = Role.CAPTAIN
    room.players['p4'].role = Role.DOCTOR
    for pid in ['p5', 'p6', 'p7', 'p8']:
        room.players[pid].role = Role.CREW
    room.phase = Phase.NIGHT_CAPTAIN

    room.set_unanimous_action(Role.CAPTAIN, 'p0', actor_id='p2')
    assert room.phase == Phase.NIGHT_CAPTAIN

    room.set_unanimous_action(Role.CAPTAIN, 'p1', actor_id='p3')
    assert room.phase == Phase.NIGHT_CAPTAIN

    room.set_unanimous_action(Role.CAPTAIN, 'p0', actor_id='p3')
    assert room.phase == Phase.NIGHT_DOCTOR
