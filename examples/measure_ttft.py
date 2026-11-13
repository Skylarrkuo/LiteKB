"""Measure submit-to-first-visible-text over HTTP, including the actual worker queue."""
import argparse
import json
import math
import os
import time
import uuid

from litekb_client import Client


def measure(client, agent_id, message):
    started = time.perf_counter()
    run = client.start_run(agent_id, message, idempotency_key=str(uuid.uuid4()))
    accepted = time.perf_counter()
    first_text = None
    for event in client.events(run["id"]):
        if first_text is None and event.kind == "answer.delta" and event.data.get("text", "").strip():
            first_text = time.perf_counter()
    completed = time.perf_counter()
    state = client.run(run["id"])
    return {
        "run_id": run["id"], "status": state["status"], "error": state["error"],
        "submit_ms": round((accepted - started) * 1000, 2),
        "ttft_ms": None if first_text is None else round((first_text - started) * 1000, 2),
        "done_ms": round((completed - started) * 1000, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--message", default="How long is the warranty?")
    args = parser.parse_args()
    if args.samples < 1 or args.warmup < 0:
        parser.error("samples must be positive and warmup must be nonnegative")
    client = Client(os.environ["LITEKB_URL"], os.environ["LITEKB_KEY"], subject="latency-evaluation")
    agent_id = os.environ["LITEKB_AGENT_ID"]
    for _ in range(args.warmup):
        measure(client, agent_id, args.message)
    samples = [measure(client, agent_id, args.message) for _ in range(args.samples)]
    valid = [s for s in samples if s["status"] == "succeeded" and s["ttft_ms"] is not None]
    summary = {}
    for name in ("submit_ms", "ttft_ms", "done_ms"):
        values = sorted(s[name] for s in valid)
        if values:
            summary[name] = {f"p{p}": values[math.ceil(len(values) * p / 100) - 1] for p in (50, 95)}
    print(json.dumps({"warmups_excluded": args.warmup, "samples": samples, "successful_with_text": len(valid),
                      "nearest_rank": summary}, indent=2))
    return int(len(samples) != len(valid))


if __name__ == "__main__":
    raise SystemExit(main())
