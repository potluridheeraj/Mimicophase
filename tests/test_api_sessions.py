from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from app.game import Phase, Role


client = TestClient(app)


def setup_function():
    store.rooms.clear()
    store.sessions.clear()
    store.last_seen.clear()


def test_join_and_rejoin_sticky_session():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    join = client.post('/api/room/join', json={'code': code, 'name': 'Alice'}).json()
    token = join['token']

    state = client.get(f'/api/state/{code}', params={'token': token}).json()
    assert state['you']['name'] == 'Alice'

    resp = client.post('/api/room/rejoin', json={'code': code, 'token': token})
    assert resp.status_code == 200

    state2 = client.get(f'/api/state/{code}', params={'token': token}).json()
    assert state2['you']['name'] == 'Alice'
    assert state2['phase'] == 'lobby'


def test_host_can_reorder_seats():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    j1 = client.post('/api/room/join', json={'code': code, 'name': 'A'}).json()
    j2 = client.post('/api/room/join', json={'code': code, 'name': 'B'}).json()

    state = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    ids = [p['id'] for p in state['players']]
    reordered = [ids[0], ids[2], ids[1]]
    resp = client.post('/api/host/seats', json={'token': host_token, 'ordered_ids': reordered})
    assert resp.status_code == 200

    state2 = client.get(f'/api/state/{code}', params={'token': j1['token']}).json()
    assert [p['id'] for p in state2['players']] == reordered


def test_host_announcement_for_night_phases():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    for n in ['A', 'B', 'C', 'D']:
        client.post('/api/room/join', json={'code': code, 'name': n})

    room = store.rooms[code]
    room.assign_roles()

    state = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    assert state['host_announcement']['open_eyes'] == 'Mimicophase'
    assert state['host_announcement']['action'] == 'Choose one non-Mimicophase player to eliminate.'

    room.phase = Phase.NIGHT_CAPTAIN
    state = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    assert state['host_announcement']['close_eyes'] == 'Mimicophase'
    assert state['host_announcement']['open_eyes'] == 'Captain'


def test_host_announcement_includes_close_eyes_prompt_for_morning():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    room = store.rooms[code]
    room.phase = Phase.MORNING

    state = client.get(f'/api/state/{code}', params={'token': host_token}).json()
    announcement = state['host_announcement']

    assert announcement['close_eyes'] == 'Doctor'
    assert announcement['open_eyes'] == 'Everyone'
    assert 'close your eyes' in announcement['text']


def test_night_actions_require_unanimous_multi_actor_votes():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    joins = [
        client.post('/api/room/join', json={'code': code, 'name': name}).json()
        for name in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    ]
    room = store.rooms[code]

    # force a 2-mimic / 2-captain setup so unanimity is required in both phases
    pids = room.order
    mimic_ids = pids[:2]
    captain_ids = pids[2:4]
    doctor_id = pids[4]
    for pid in pids:
        if pid in mimic_ids:
            room.players[pid].role = Role.MIMICOPHASE
        elif pid in captain_ids:
            room.players[pid].role = Role.CAPTAIN
        elif pid == doctor_id:
            room.players[pid].role = Role.DOCTOR
        else:
            room.players[pid].role = Role.CREW
    room.phase = Phase.NIGHT_MIMIC

    token_by_pid = {j['player_id']: j['token'] for j in joins}
    # include host player token for forced role list above
    token_by_pid[store.sessions[host_token].player_id] = host_token

    non_mimics = [pid for pid in pids if pid not in mimic_ids]
    t1, t2 = non_mimics[0], non_mimics[1]

    r = client.post('/api/night/mimic', json={'token': token_by_pid[mimic_ids[0]], 'target': t1})
    assert r.status_code == 200
    assert room.phase == Phase.NIGHT_MIMIC

    r = client.post('/api/night/mimic', json={'token': token_by_pid[mimic_ids[1]], 'target': t2})
    assert r.status_code == 200
    assert room.phase == Phase.NIGHT_MIMIC

    r = client.post('/api/night/mimic', json={'token': token_by_pid[mimic_ids[1]], 'target': t1})
    assert r.status_code == 200
    assert room.phase == Phase.NIGHT_CAPTAIN


def test_finalize_vote_returns_400_when_votes_missing():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']
    j1 = client.post('/api/room/join', json={'code': code, 'name': 'A'}).json()
    j2 = client.post('/api/room/join', json={'code': code, 'name': 'B'}).json()

    room = store.rooms[code]
    for p in room.players.values():
        p.role = Role.CREW
    room.phase = Phase.RUNOFF
    room.runoff_candidates = [store.sessions[j1['token']].player_id, store.sessions[j2['token']].player_id]

    # only one vote in; host finalization should now return 400 instead of raising 500
    client.post('/api/day/vote', json={'token': j1['token'], 'choice': room.runoff_candidates[0]})
    resp = client.post('/api/host/finalize-vote', json={'token': host_token, 'target': ''})
    assert resp.status_code == 400
    assert 'All connected living players must vote' in resp.text
