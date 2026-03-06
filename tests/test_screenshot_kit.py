from app.game import Phase
from app.main import app
from app.store import store
from fastapi.testclient import TestClient

from screenshot_kit import ScreenshotKit


client = TestClient(app)


def setup_function():
    store.rooms.clear()
    store.sessions.clear()
    store.last_seen.clear()


def test_create_phase_screenshot_kit_folder():
    create = client.post('/api/room/create', json={'host_name': 'Host'}).json()
    code = create['code']
    host_token = create['token']

    for name in ['Alice', 'Bob', 'Cara', 'Dan']:
        client.post('/api/room/join', json={'code': code, 'name': name})

    room = store.rooms[code]

    kit = ScreenshotKit()
    phases = [
        Phase.LOBBY,
        Phase.NIGHT_MIMIC,
        Phase.NIGHT_CAPTAIN,
        Phase.NIGHT_DOCTOR,
        Phase.MORNING,
        Phase.DISCUSSION,
        Phase.NOMINATION,
        Phase.RUNOFF,
    ]

    for index, phase in enumerate(phases, start=1):
        room.phase = phase
        kit.capture_phase(
            client,
            code=code,
            host_token=host_token,
            phase=phase,
            sequence=index,
        )

    summary_path = kit.finalize()

    assert summary_path.exists()
    assert summary_path.parent.name.startswith('run_')
