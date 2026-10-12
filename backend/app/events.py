from datetime import datetime, timezone
from copy import deepcopy


def emit(run: dict, kind: str, stage: str = 'task', payload: dict | None = None):
    events = run.setdefault('events', [])
    event = {'event_id': len(events) + 1, 'task_id': run['id'], 'type': kind,
             'timestamp': datetime.now(timezone.utc).isoformat(), 'stage': stage,
             'status': run['status'], 'payload': deepcopy(payload or {})}
    events.append(event)
    return event
