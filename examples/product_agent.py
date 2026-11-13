"""Call a published workflow from a product backend. See docs/product-sdk.md."""
import os

from litekb_client import Client


def answer(client, agent_id, message, request_id, *, session_id=None, on_text=print):
    run = client.start_run(agent_id, message, session_id=session_id, idempotency_key=request_id)
    for chunk in client.stream_text(run["id"]):
        on_text(chunk)
    return client.run(run["id"])


if __name__ == "__main__":
    client = Client(os.environ["LITEKB_URL"], os.environ["LITEKB_KEY"], subject=os.environ["LITEKB_SUBJECT"])
    result = answer(client, os.environ["LITEKB_AGENT_ID"], os.environ["LITEKB_MESSAGE"],
                    os.environ["PRODUCT_REQUEST_ID"], on_text=lambda text: print(text, end="", flush=True))
    print("\n", result["status"], result["session_id"], result.get("result", {}).get("sources", []))
