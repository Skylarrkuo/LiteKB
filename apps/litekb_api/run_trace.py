"""Map existing workflow details to stable references in the stored ChatRecord."""

import math


def trace_steps(details, path=(), iteration=None):
    if not isinstance(details, dict):
        return
    for runtime_id, detail in details.items():
        if not isinstance(detail, dict):
            continue
        location = (*path, runtime_id)
        node_type = str(detail.get("type") or detail.get("step_type") or runtime_id)
        elapsed = detail.get("run_time")
        if not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            elapsed = 0
        status = "succeeded"
        if detail.get("status") == 500:
            status = "failed"
        elif node_type == "form-node" and detail.get("is_submit") is False:
            status = "waiting_input"
        yield {
            "node_id": str(detail.get("node_id") or runtime_id),
            "node_type": node_type[:128],
            "execution_path": list(location),
            "iteration": iteration,
            "status": status,
            "elapsed_seconds": elapsed,
        }
        for index, body in enumerate(detail.get("loop_node_data") or []):
            yield from trace_steps(body, (*location, "loop_node_data", index), index)
        if node_type == "tool-workflow-lib-node":
            yield from trace_steps(detail.get("details"), (*location, "details"), iteration)


def sse_frame(event):
    import json

    payload = json.dumps(event["data"], separators=(",", ":"), ensure_ascii=False)
    return f"id: {event['sequence']}\nevent: {event['kind']}\ndata: {payload}\n\n"


def record_steps(record, prefix=(), ancestors=()):
    """Keep a reference into the owning chat record, even across nested application calls."""
    from application.models import ChatRecord
    from application.flow.step_node.application_node.impl.base_application_node import string_to_uuid

    for step in trace_steps(record.details):
        path = step["execution_path"]
        detail = record.details
        for key in path:
            detail = detail[key]
        step["unhandled_error"] = step["status"] == "failed" and not detail.get("enableException")
        step["sources"] = [
            {"knowledge_base_id": row["knowledge_id"], "document_id": row["document_id"], "paragraph_id": row["id"]}
            for row in detail.get("paragraph_list") or []
            if isinstance(row, dict) and row.get("knowledge_id") and row.get("document_id") and row.get("id")
        ]
        step["output_ref"] = {"chat_record_id": str(record.pk), "path": path, "start_time": detail.get("start_time")}
        step["execution_path"] = [*prefix, *path]
        yield step
        if step["node_type"] != "application-node":
            continue
        app_id = (detail.get("info") or {}).get("application_id")
        if not app_id:
            continue
        child_chat = string_to_uuid(str(record.chat_id) + str(app_id))
        refs = (detail.get("application_node_dict") or {}).values()
        record_ids = {r["chat_record_id"] for r in refs if r.get("chat_record_id")}
        for child in ChatRecord.objects.filter(pk__in=record_ids, chat_id=child_chat).order_by("create_time"):
            if child.pk not in ancestors and child.pk != record.pk:
                yield from record_steps(
                    child, (*step["execution_path"], "chat_record", str(child.pk)), (*ancestors, record.pk)
                )
