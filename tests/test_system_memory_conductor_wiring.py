from tests.host_lifespan_helpers import run_isolated_host


def test_system_memory_is_wired_into_room_conductor_and_rearms_across_lifespans(tmp_path):
    run_isolated_host('from starlette.testclient import TestClient\nimport main\nwith TestClient(main.app):\n    conductor = main.app.state.room_conductor\n    system_memory = main.app.state.system_memory\n    assert conductor._system_memory is system_memory\n    assert system_memory._conn is not None\n\nassert system_memory._conn is None\n\n# The app singleton deliberately does not run the full boot twice. The\n# connection-owning SystemMemory must therefore re-arm independently.\nwith TestClient(main.app):\n    assert main.app.state.room_conductor is conductor\n    assert main.app.state.system_memory is system_memory\n    assert system_memory._conn is not None\n\nassert system_memory._conn is None', tmp_path)
