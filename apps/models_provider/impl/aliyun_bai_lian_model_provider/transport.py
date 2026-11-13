"""Stateless DashScope HTTP requests; credentials and endpoints belong to each model instance."""
import time
from urllib.parse import quote

from common.utils.provider_request import provider_request


COMPAT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
NATIVE = "https://dashscope.aliyuncs.com/api/v1"


def endpoint(base, *, compatible=False):
    suffix = "/compatible-mode/v1" if compatible else "/api/v1"
    base = (base or (COMPAT if compatible else NATIVE)).strip().rstrip("/")
    for known in ("/compatible-mode/v1", "/api/v1"):
        if base.endswith(known):
            return base[:-len(known)] + suffix
    return base


def request(base, key, path, payload=None, *, asynchronous=False, params=None):
    headers = {"Authorization": f"Bearer {key}"}
    if asynchronous:
        headers["X-DashScope-Async"] = "enable"
    response = provider_request("POST" if payload is not None else "GET", f"{base}/{path}", headers=headers,
                                json=payload, params=params, timeout=(10, 120))
    body = response.json()
    if body.get("code") or "output" not in body:
        raise ValueError(f"DashScope response error: {body.get('code', 'missing output')}")
    return body["output"]


def check_catalog(base, key, model):
    output = request(endpoint(base), key, "models", params={"model": model, "page_no": 1, "page_size": 1})
    if not any(row.get("model") == model for row in output.get("models", [])):
        raise ValueError("Model unavailable in the selected Model Studio region or workspace.")


def generate_async(base, key, path, payload):
    task = request(base, key, path, payload, asynchronous=True)
    task_id = task["task_id"]
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        task = request(base, key, f"tasks/{quote(task_id, safe='')}")
        status = task.get("task_status")
        if status == "SUCCEEDED":
            return task
        if status not in ("PENDING", "RUNNING"):
            raise ValueError(f"DashScope task {status}: {task.get('code', 'unknown')}")
        time.sleep(5)
    raise TimeoutError(f"DashScope task {task_id} is still pending")
