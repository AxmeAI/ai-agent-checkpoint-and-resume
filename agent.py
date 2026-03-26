"""
Pipeline agent - runs a multi-step data pipeline with durable checkpoints.

Each step is tracked as a durable intent. If the agent crashes mid-pipeline,
restarting it picks up from the last completed step automatically.

Usage:
    export AXME_API_KEY="<agent-key>"
    python agent.py
"""

import os
import sys
import time

sys.stdout.reconfigure(line_buffering=True)

from axme import AxmeClient, AxmeClientConfig


AGENT_ADDRESS = "pipeline-agent-demo"


def handle_intent(client, intent_id):
    """Run a multi-step pipeline and resume with results."""
    intent_data = client.get_intent(intent_id)
    intent = intent_data.get("intent", intent_data)
    payload = intent.get("payload", {})
    if "parent_payload" in payload:
        payload = payload["parent_payload"]

    pipeline = payload.get("pipeline", "unknown")
    source = payload.get("source", "unknown")
    destination = payload.get("destination", "unknown")
    steps = payload.get("steps", ["extract", "validate", "transform", "load"])
    total_rows = payload.get("total_rows", 0)

    print(f"  Pipeline: {pipeline}")
    print(f"  Source: {source} -> Destination: {destination}")
    print(f"  Steps: {steps}")
    print(f"  Total rows: {total_rows}\n")

    completed_steps = []
    rows_processed = 0

    for i, step in enumerate(steps):
        step_num = i + 1
        print(f"  [{step_num}/{len(steps)}] {step.upper()}...")

        # Simulate step processing
        if step == "extract":
            time.sleep(1)
            rows_processed = total_rows
            print(f"    Extracted {rows_processed} rows from {source}")
        elif step == "validate":
            time.sleep(1)
            invalid = int(total_rows * 0.002)
            rows_processed = total_rows - invalid
            print(f"    Validated: {rows_processed} valid, {invalid} rejected")
        elif step == "transform":
            time.sleep(1)
            print(f"    Transformed {rows_processed} rows (normalized, deduped)")
        elif step == "load":
            time.sleep(1)
            print(f"    Loaded {rows_processed} rows into {destination}")

        completed_steps.append(step)
        print(f"    Checkpoint saved: {len(completed_steps)}/{len(steps)} steps done")

    result = {
        "action": "complete",
        "pipeline": pipeline,
        "status": "success",
        "steps_completed": completed_steps,
        "rows_processed": rows_processed,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    client.resume_intent(intent_id, result)
    print(f"\n  Pipeline complete: {rows_processed} rows processed in {len(steps)} steps")


def main():
    api_key = os.environ.get("AXME_API_KEY", "")
    if not api_key:
        print("Error: AXME_API_KEY not set.")
        print("Run the scenario first: axme scenarios apply scenario.json")
        print("Then get the agent key from ~/.config/axme/scenario-agents.json")
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print(f"Agent listening on {AGENT_ADDRESS}...")
    print("Waiting for intents (Ctrl+C to stop)\n")

    for delivery in client.listen(AGENT_ADDRESS):
        intent_id = delivery.get("intent_id", "")
        status = delivery.get("status", "")

        if not intent_id:
            continue

        if status in ("DELIVERED", "CREATED", "IN_PROGRESS"):
            print(f"[{status}] Intent received: {intent_id}")
            try:
                handle_intent(client, intent_id)
            except Exception as e:
                print(f"  Error processing intent: {e}")


if __name__ == "__main__":
    main()
