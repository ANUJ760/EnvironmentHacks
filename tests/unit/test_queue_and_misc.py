import json
from uuid import uuid4

import pytest
from shapely.geometry import box, mapping

from ecotwin.errors import TwinError
from ecotwin.jobs.sqs_queue import SQSQueue
from ecotwin.models.runoff import runoff_volume
from ecotwin.models.solar_pv import solar_energy
from ecotwin.spatial.geometry import geometry, project, validate_area
from ecotwin.telemetry.logging import redact


def test_sqs_hint_contract():
    calls = []

    class Client:
        def send_message(self, **kwargs):
            calls.append(kwargs)

        def receive_message(self, **kwargs):
            return {"Messages": [{"ReceiptHandle": "receipt"}]}

        def delete_message(self, **kwargs):
            calls.append(kwargs)

    queue = SQSQueue("url", "region", client=Client())
    identifier = uuid4()
    queue.publish(identifier)
    assert json.loads(calls[0]["MessageBody"]) == {"job_id": str(identifier)}
    assert queue.poll()[0]["ReceiptHandle"] == "receipt"
    queue.acknowledge("receipt")
    assert calls[-1]["ReceiptHandle"] == "receipt"
    with pytest.raises(ValueError):
        queue.publish("invalid")


def test_worker_once_and_sqs_reconciliation(monkeypatch):
    import ecotwin.jobs.worker as worker
    from ecotwin.config import Settings

    settings = Settings(_env_file=None, ecotwin_queue_backend="sqs", ecotwin_sqs_queue_url="url")

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class Queue:
        def __init__(self, *args):
            self.url = "url"

        def poll(self):
            return [{"ReceiptHandle": "receipt"}]

        def acknowledge(self, *args):
            raise OSError("transient")

    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "session_factory", lambda: Session)
    monkeypatch.setattr(worker, "claim", lambda *args: None)
    monkeypatch.setattr(worker.time, "sleep", lambda seconds: None)
    import ecotwin.jobs.sqs_queue as sqs

    monkeypatch.setattr(sqs, "SQSQueue", Queue)
    worker.run_worker(once=True)

    class Broken(Queue):
        def poll(self):
            raise OSError("network")

    monkeypatch.setattr(sqs, "SQSQueue", Broken)
    worker.run_worker(once=True)


def test_redaction_nested():
    assert redact(
        None, None, {"Authorization": "secret", "payload": [{"api_key": "secret", "safe": 1}]}
    ) == {"Authorization": "[REDACTED]", "payload": [{"api_key": "[REDACTED]", "safe": 1}]}


@pytest.mark.parametrize(
    "function,args",
    [
        (runoff_volume, ({10: -1}, 50, {10: 0.1})),
        (runoff_volume, ({10: 1}, 50, {10: 2})),
        (solar_energy, (1, [])),
        (solar_energy, (-1, [1])),
        (solar_energy, (1, [-1])),
        (solar_energy, (1, [1], 0)),
    ],
)
def test_invalid_scientific_inputs(function, args):
    with pytest.raises(TwinError):
        function(*args)


def test_geometry_protection():
    for value in [
        {"type": "Point", "coordinates": [0, 0]},
        mapping(box(0, 0, 1, 1)) | {"coordinates": []},
        {"type": "Polygon", "coordinates": [[[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1]]]},
    ]:
        with pytest.raises(TwinError):
            geometry(value)
    with pytest.raises(TwinError):
        project(box(0, 0, 1, 1), 4326)
    with pytest.raises(TwinError):
        validate_area(box(0, 0, 1, 1), 32631)
