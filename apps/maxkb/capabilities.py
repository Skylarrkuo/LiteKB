"""Process-wide capabilities of the installed LiteKB distribution."""
import os


def enabled(name):
    value = os.environ.get(name, "0").lower()
    if value not in {"0", "1", "false", "true"}:
        raise ValueError(f"{name} must be 0 or 1")
    return value in {"1", "true"}


MEDIA_NODES = enabled("LITEKB_MEDIA_NODES")
LOCAL_MODEL = enabled("LITEKB_LOCAL_MODEL")
EXTENDED_PROVIDERS = enabled("LITEKB_EXTENDED_PROVIDERS")
MEDIA_NODE_TYPES = frozenset({
    "speech-to-text-node", "text-to-speech-node", "image-generate-node",
    "text-to-video-node", "image-to-video-node", "video-understand-node",
})
DISABLED_NODES = {"data-source-web-node"} | (set() if MEDIA_NODES else MEDIA_NODE_TYPES)


MEDIA_MODEL_TYPES = frozenset({"STT", "TTS", "TTI", "TTV", "ITV"})


def model_type_enabled(model_type):
    return MEDIA_NODES or model_type not in MEDIA_MODEL_TYPES


def disabled_workflow_node(graph):
    """Return the first disabled node, including nodes inside loop bodies."""
    graphs = [graph]
    while graphs:
        for node in graphs.pop().get("nodes", []):
            node_type = node.get("type")
            if node_type in DISABLED_NODES:
                return node_type
            properties = node.get("properties") or {}
            data = properties.get("node_data") or {}
            for body in (data.get("loop_body"), properties.get("workflow")):
                if isinstance(body, dict):
                    graphs.append(body)
    return None


def capabilities_view(request):
    from common.result import result

    return result.success({
        "media_nodes": MEDIA_NODES,
        "disabled_nodes": sorted(DISABLED_NODES),
        "local_model": LOCAL_MODEL,
    })
