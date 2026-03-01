from app.game import GameRoom, Phase, Player, Role


def mk_room(n=8):
    room = GameRoom(code="ABCD", host_token="host")
    for i in range(n):
        room.add_player(Player(id=f"p{i}", name=f"P{i}", token=f"t{i}"))
    return room


def force_roles(room: GameRoom):
    # p0,p1 mimic; p2 captain; p3 doctor; rest crew
    room.players["p0"].role = Role.MIMICOPHASE
    room.players["p1"].role = Role.MIMICOPHASE
    room.players["p2"].role = Role.CAPTAIN
    room.players["p3"].role = Role.DOCTOR
    for pid in room.players:
        if pid not in {"p0", "p1", "p2", "p3"}:
            room.players[pid].role = Role.CREW


def test_doctor_can_protect_self():
    room = mk_room(6)
    force_roles(room)
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, "p3")
    room.set_unanimous_action(Role.CAPTAIN, "p4")  # crew => no mark
    room.set_doctor_action("p3")

    assert room.players["p3"].alive
    assert room.morning_deaths == []


def test_targeting_dead_player_is_invalid():
    room = mk_room(6)
    force_roles(room)
    room.players["p5"].alive = False
    room.phase = Phase.NIGHT_MIMIC

    try:
        room.set_unanimous_action(Role.MIMICOPHASE, "p5")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "living player" in str(exc)


def test_mimic_cannot_target_mimic():
    room = mk_room(6)
    force_roles(room)
    room.phase = Phase.NIGHT_MIMIC

    try:
        room.set_unanimous_action(Role.MIMICOPHASE, "p1")
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "target non-Mimicophase" in str(exc)


def test_captain_inspecting_non_mimic_has_no_effect():
    room = mk_room(6)
    force_roles(room)
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, "p4")
    room.set_unanimous_action(Role.CAPTAIN, "p5")
    room.set_doctor_action("p3")

    assert not room.players["p4"].alive
    assert room.players["p5"].alive


def test_doctor_protection_applies_to_both_kill_types_same_target():
    room = mk_room(6)
    force_roles(room)
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, "p4")
    room.set_unanimous_action(Role.CAPTAIN, "p0")
    room.set_doctor_action("p0")

    assert not room.players["p4"].alive
    assert room.players["p0"].alive


def test_no_deaths_night_when_only_protected_or_no_mark():
    room = mk_room(6)
    force_roles(room)
    room.phase = Phase.NIGHT_MIMIC

    room.set_unanimous_action(Role.MIMICOPHASE, "p4")
    room.set_unanimous_action(Role.CAPTAIN, "p5")  # crew -> no mark
    room.set_doctor_action("p4")

    assert room.morning_deaths == []


def test_nomination_tie_for_second_includes_all_tied():
    room = mk_room(6)
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.NOMINATION

    # votes: p0 gets 2, p1 gets 1, p2 gets 1, p3 gets 1, p4 gets 1
    room.submit_nomination("p0", "p0")
    room.submit_nomination("p1", "p0")
    room.submit_nomination("p2", "p1")
    room.submit_nomination("p3", "p2")
    room.submit_nomination("p4", "p3")
    room.submit_nomination("p5", "p4")

    room.finalize_nominations()
    assert room.phase == Phase.RUNOFF
    assert set(room.runoff_candidates) == {"p0", "p1", "p2", "p3", "p4"}


def test_single_nominee_reject_returns_to_nominations():
    room = mk_room(5)
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.NOMINATION

    room.submit_nomination("p0", "p4")
    room.submit_nomination("p1", "p4")
    room.finalize_nominations()

    # 5 alive => threshold 3, reject wins
    room.submit_runoff_vote("p0", "reject")
    room.submit_runoff_vote("p1", "reject")
    room.submit_runoff_vote("p2", "reject")
    room.submit_runoff_vote("p3", "execute")
    room.submit_runoff_vote("p4", "execute")
    result = room.finalize_runoff()

    assert result is None
    assert room.phase == Phase.NOMINATION


def test_crew_wins_immediately_when_all_mimics_dead():
    room = mk_room(5)
    room.players["p0"].role = Role.MIMICOPHASE
    for pid in ["p1", "p2", "p3", "p4"]:
        room.players[pid].role = Role.CREW
    room.players["p0"].alive = False

    winner = room.check_victory()
    assert winner == "crew"
    assert room.phase == Phase.ENDED


def test_mimics_win_when_mimics_greater_or_equal_crew():
    room = mk_room(4)
    room.players["p0"].role = Role.MIMICOPHASE
    room.players["p1"].role = Role.MIMICOPHASE
    room.players["p2"].role = Role.CREW
    room.players["p3"].role = Role.CREW

    winner = room.check_victory()
    assert winner == "mimicophase"
    assert room.phase == Phase.ENDED
