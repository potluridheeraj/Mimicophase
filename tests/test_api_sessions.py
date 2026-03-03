from fastapi.testclient import TestClient

from app.main import app
from app.store import store
from app.game import Phase


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
