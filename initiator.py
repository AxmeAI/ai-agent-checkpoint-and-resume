"""
Initiator - sends a data pipeline job through the AXME durable execution layer.

Submits a multi-step pipeline intent and observes the lifecycle.
If the agent crashes mid-pipeline, the intent stays in its current state.
Restarting the agent picks up from the last checkpoint.

Usage:
    export AXME_API_KEY="your-key"
    python initiator.py
"""

from __future__ import annotations

import json
import os
import sys

from axme import AxmeClient, AxmeClientConfig


PIPELINE_CONFIG = {
    "pipeline": "etl-customers",
    "source": "postgres-prod",
    "destination": "bigquery-analytics",
    "steps": ["extract", "validate", "transform", "load"],
    "total_rows": 500000,
}


def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print("Sending pipeline intent...")
    intent_id = client.send_intent({
        "intent_type": "intent.pipeline.process.v1",
        "to_agent": "agent://myorg/production/pipeline-agent",
        "payload": PIPELINE_CONFIG,
    })
    print(f"Intent created: {intent_id}")
    print("Observing lifecycle events...\n")
    print("Try killing the agent mid-pipeline (Ctrl+C on agent terminal).")
    print("Then restart it - the intent will be redelivered.\n")

    for event in client.observe(intent_id):
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})
        print(f"  [{event_type}] {json.dumps(data, indent=2)[:200]}")

        if event_type in ("intent.completed", "intent.failed", "intent.cancelled"):
            break

    final = client.get_intent(intent_id)
    print(f"\nFinal status: {final.get('status')}")
    print(f"Result: {json.dumps(final.get('result', {}), indent=2)}")


if __name__ == "__main__":
    main()
