"""Start, inspect or stop this checkout's background Windows development processes."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

import psutil
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".dev" / "run"
RECORD = STATE / "processes.json"


def owned_process(entry):
    try:
        p = psutil.Process(entry["pid"])
        if abs(p.create_time() - entry["created"]) < 0.01 and p.exe().casefold() == entry["exe"].casefold():
            return p
    except (KeyError, psutil.NoSuchProcess):
        pass
    return None


def save(entries):
    path = RECORD.with_suffix(".tmp")
    path.write_text(json.dumps(entries), encoding="utf-8")
    path.replace(RECORD)


def stop(entries, roles):
    for role in roles:
        entry = entries.pop(role, None)
        process = owned_process(entry) if entry else None
        if process:
            # The Windows venv interpreter can launch a child interpreter for the same command.
            children = process.children(recursive=True)
            for p in [*reversed(children), process]:
                try:
                    p.terminate()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs([*children, process], timeout=5)
        save(entries)


def wait_ready(check, process, role, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not process.is_running():
            break
        try:
            if check():
                return
        except (OSError, ConnectionError):
            pass
        time.sleep(0.5)
    raise RuntimeError(f"{role} did not become ready. See {STATE / (role + '.log')}")


def check_free_port(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", int(port)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "status", "stop"])
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("This launcher manages Windows development processes.")
    import msvcrt
    import redis

    os.chdir(ROOT)
    load_dotenv(ROOT / ".env")
    STATE.mkdir(parents=True, exist_ok=True)
    bind = os.getenv("LITEKB_DEV_BIND", "127.0.0.1:8080")
    host, port = bind.rsplit(":", 1)
    if host not in ("127.0.0.1", "localhost"):
        parser.error("Set LITEKB_DEV_BIND to a loopback address for this local launcher.")
    url = f"http://{bind}"
    with (STATE / "control.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        entries = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.exists() else {}
        if args.action == "stop":
            stop(entries, ("worker", "api", "redis"))
            return
        if args.action == "status":
            for role in ("api", "worker", "redis"):
                p = owned_process(entries[role]) if role in entries else None
                label = f"running (PID {p.pid})" if p else "not managed or stopped"
                print(f"{role}: {label}")
            print(url + "/admin/")
            return

        env = dict(os.environ, PYTHONPATH=str(ROOT / "apps"), PYTHONUTF8="1")
        started = []

        def launch(role, cmd, cwd=ROOT, **overrides):
            p = owned_process(entries[role]) if role in entries else None
            if p:
                return p
            with (STATE / f"{role}.log").open("ab") as log:
                child = subprocess.Popen(cmd, cwd=cwd, env={**env, **overrides}, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
            p = psutil.Process(child.pid)
            entries[role] = {"pid": p.pid, "created": p.create_time(), "exe": p.exe()}
            save(entries)
            started.append(role)
            return p

        try:
            redis_exe = env.get("LITEKB_DEV_REDIS_EXE")
            if redis_exe:
                if env.get("MAXKB_REDIS_HOST", "127.0.0.1") not in ("localhost", "127.0.0.1"):
                    parser.error("A managed Redis must use a loopback address.")
                redis_port = int(env.get("MAXKB_REDIS_PORT", "6379"))
                password = env.get("MAXKB_REDIS_PASSWORD")
                if not password:
                    parser.error("Set MAXKB_REDIS_PASSWORD for the managed Redis process.")
                directory = STATE / "redis"
                directory.mkdir(exist_ok=True)
                if "redis" not in entries or not owned_process(entries["redis"]):
                    check_free_port(redis_port)
                config = directory / "redis.conf"
                config.write_text(f'bind 127.0.0.1\nport {redis_port}\nprotected-mode yes\n'
                                  f'requirepass {json.dumps(password)}\nappendonly yes\n', encoding="utf-8")
                process = launch("redis", [str(Path(redis_exe).resolve()), config.name], directory)
                r = redis.Redis(host="127.0.0.1", port=redis_port, password=password, socket_timeout=1)

                def redis_ready():
                    try:
                        return r.ping()
                    except redis.ConnectionError:
                        return False

                wait_ready(redis_ready, process, "redis")
            if "api" not in entries or not owned_process(entries["api"]):
                check_free_port(port)
                subprocess.run([sys.executable, "apps/manage.py", "migrate", "--noinput"], env=env, check=True)
                subprocess.run([sys.executable, "main.py", "collect_static"], env=env, check=True)
            api = launch("api", [sys.executable, "apps/manage.py", "runserver", bind, "--noreload"], SERVER_NAME="web")
            opener = build_opener(ProxyHandler({}))

            def api_ready():
                with opener.open(url + "/health/ready", timeout=2) as response:
                    return response.status == 200

            wait_ready(api_ready, api, "api")
            marker = ROOT / "tmp" / "worker_ready_litekb-native"
            if "worker" not in entries or not owned_process(entries["worker"]):
                marker.unlink(missing_ok=True)
            worker = launch("worker", [sys.executable, "-m", "celery", "-A", "ops.celery:app", "worker", "--pool=solo",
                                       "--concurrency=1", "--queues=celery,model", "--hostname=litekb-native@%h",
                                       "--without-gossip", "--without-mingle", "--loglevel=INFO"], SERVER_NAME="celery")
            wait_ready(marker.exists, worker, "worker")
        except BaseException:
            stop(entries, reversed(started))
            raise
        print(f"LiteKB ready at {url}/admin/ (API {api.pid}, worker {worker.pid}).")


if __name__ == "__main__":
    main()
