"""Optional pytest plugin to retain warning categories for release review."""
from collections import Counter
import json
import os
from pathlib import Path

warnings_seen = []


def pytest_warning_recorded(warning_message, when, nodeid, location):
    warnings_seen.append({"category": warning_message.category.__name__,
        "message": str(warning_message.message), "when": when, "test": nodeid,
        "source": Path(warning_message.filename).name})


def pytest_unconfigure(config):
    output = os.environ.get("PUBCAST_WARNING_AUDIT")
    if output:
        Path(output).write_text(json.dumps({
            "counts": dict(Counter(item["category"] for item in warnings_seen)),
            "warnings": warnings_seen}, indent=2))
