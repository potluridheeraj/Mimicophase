from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from app.game import Phase, Role


client = TestClient(app)


def setup_function():
    store.rooms.clear()
    store.sessions.clear()
    store.last_seen.clear()


def test_host_kick_player():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    joined = client.post('/api/room/join', json={'code': code, 'name': 'Alice'}).json()

    state = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    alice_id = [p['id'] for p in state['players'] if p['name'] == 'Alice'][0]

    resp = client.post('/api/host/kick', json={'token': host_token, 'target': alice_id})
    assert resp.status_code == 200

    state2 = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    assert all(p['name'] != 'Alice' for p in state2['players'])

    # kicked token can no longer nominate even in nomination phase
    room = store.rooms[code]
    room.phase = Phase.NOMINATION
    bad = client.post('/api/day/nominate', json={'token': joined['token'], 'target': state2['players'][0]['id']})
    assert bad.status_code >= 400


def test_host_reset_game_mid_match():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    for n in ['A', 'B', 'C', 'D']:
        client.post('/api/room/join', json={'code': code, 'name': n})

    assert client.post('/api/host/start', json={'token': host_token, 'target': ''}).status_code == 200
    room = store.rooms[code]
    assert room.phase == Phase.NIGHT_MIMIC

    assert client.post('/api/host/reset', json={'token': host_token, 'target': ''}).status_code == 200
    assert room.phase == Phase.LOBBY
    assert room.cycle == 0
    assert all(p.role is None for p in room.players.values() if not p.kicked)


def test_vote_auto_finalizes_when_all_connected_vote():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    p1 = client.post('/api/room/join', json={'code': code, 'name': 'A'}).json()
    p2 = client.post('/api/room/join', json={'code': code, 'name': 'B'}).json()

    room = store.rooms[code]
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.RUNOFF
    ids = [pid for pid in room.order if not room.players[pid].kicked]
    room.runoff_candidates = ids[:2]

    client.post('/api/day/vote', json={'token': host_token, 'choice': ids[0]})
    client.post('/api/day/vote', json={'token': p1['token'], 'choice': ids[0]})
    last = client.post('/api/day/vote', json={'token': p2['token'], 'choice': ids[1]}).json()

    assert last['auto_finalized'] is True
    assert room.phase in (Phase.NIGHT_MIMIC, Phase.ENDED)


def test_disconnected_players_are_skipped_in_voting_count():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    p1 = client.post('/api/room/join', json={'code': code, 'name': 'A'}).json()
    p2 = client.post('/api/room/join', json={'code': code, 'name': 'B'}).json()

    room = store.rooms[code]
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.RUNOFF
    ids = [pid for pid in room.order if not room.players[pid].kicked]
    room.runoff_candidates = ids[:2]

    # Simulate disconnect of player B
    store.last_seen[p2['token']] = 0
    store.refresh_connections(room)

    assert len(room.active_living_player_ids()) == 2
    client.post('/api/day/vote', json={'token': host_token, 'choice': ids[0]})
    res = client.post('/api/day/vote', json={'token': p1['token'], 'choice': ids[0]}).json()
    assert res['auto_finalized'] is True


def test_host_timer_settings_before_start():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']

    res = client.post('/api/host/settings', json={
        'token': host_token,
        'morning_s': 20,
        'discussion_s': 100,
        'nomination_s': 50,
        'runoff_s': 60,
    })
    assert res.status_code == 200
    room = store.rooms[code]
    assert room.phase_durations[Phase.MORNING] == 20
    assert room.phase_durations[Phase.DISCUSSION] == 100
