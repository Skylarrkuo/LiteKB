from pathlib import Path

from celery.signals import heartbeat_sent, worker_ready, worker_shutdown

from maxkb.const import PROJECT_DIR

_worker_state_dir = Path(PROJECT_DIR) / 'tmp'


def _touch_worker_state(signal, name):
    _worker_state_dir.mkdir(parents=True, exist_ok=True)
    (_worker_state_dir / f'worker_{signal}_{name}').touch()


@heartbeat_sent.connect
def heartbeat(sender, **kwargs):
    worker_name = sender.eventer.hostname.split('@')[0]
    _touch_worker_state('heartbeat', worker_name)


@worker_ready.connect
def worker_ready(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    _touch_worker_state('ready', worker_name)


@worker_shutdown.connect
def worker_shutdown(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    for signal in ['ready', 'heartbeat']:
        path = _worker_state_dir / f'worker_{signal}_{worker_name}'
        path.unlink(missing_ok=True)
