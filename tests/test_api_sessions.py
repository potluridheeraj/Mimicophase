from fastapi.testclient import TestClient

from app.main import app
from app.store import store


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
