#!/usr/bin/env python3
"""Test script for Leeway daemon.

Run with: PYTHONPATH=src uv run python examples/test-daemon.py
"""

import sys
import json
import threading
import time

sys.path.insert(0, "src")

from leeway_integration.daemon.core import Daemon
from leeway_integration.protocol import JsonRpcRequest


def send_request(d: Daemon, method: str, params: dict = None, id: str = None) -> dict:
    """Send a request and return the response as dict."""
    req = JsonRpcRequest(id=id or f"req-{time.time()}", method=method, params=params or {})
    resp = d.handle_request(req)
    return json.loads(json.dumps(resp.model_dump(exclude_none=True)))


def main():
    print("Starting Leeway daemon test...\n")

    # Create daemon
    d = Daemon(workflows_dir=".leeway/workflows")

    # Test 1: Ping
    print("1. Pinging daemon...")
    resp = send_request(d, "daemon.ping", {}, "test-ping")
    assert resp.get("result"), f"Ping failed: {resp}"
    assert resp["result"]["status"] == "healthy"
    print(f"   ✅ Version: {resp['result']['version']}")
    print(f"   ✅ Status: {resp['result']['status']}\n")

    # Test 2: List workflows
    print("2. Listing workflows...")
    resp = send_request(d, "workflow.list", {}, "test-list")
    assert resp.get("result"), f"List failed: {resp}"
    workflows = resp["result"]["workflows"]
    print(f"   ✅ Available: {', '.join(workflows)}\n")

    # Test 3: Execute workflow
    print("3. Executing 'code-health' workflow...")
    resp = send_request(
        d,
        "workflow.execute",
        {"name": "code-health", "user_context": "Test execution"},
        "test-execute",
    )
    assert resp.get("result"), f"Execute failed: {resp}"
    result = resp["result"]
    print(f"   ✅ Success: {result['success']}")
    print(f"   ✅ Output: {result['final_output'][:50]}...")
    if result.get("audit"):
        print(f"   ✅ Path: {result['audit']['path_taken']}")
        print(f"   ✅ Total turns: {result['audit']['total_turns']}")
    print()

    # Test 4: Validate workflow
    print("4. Validating 'code-health' workflow...")
    resp = send_request(d, "workflow.validate", {"name": "code-health"}, "test-validate")
    assert resp.get("result"), f"Validate failed: {resp}"
    print(f"   ✅ Valid: {resp['result']['valid']}")
    print()

    # Test 5: Workflow not found
    print("5. Testing workflow not found...")
    resp = send_request(
        d, "workflow.execute", {"name": "nonexistent", "user_context": "test"}, "test-notfound"
    )
    assert resp.get("error"), f"Should have errored: {resp}"
    print(f"   ✅ Error code: {resp['error']['code']}")
    print(f"   ✅ Error message: {resp['error']['message']}")
    print()

    print("✅ All tests passed!")


if __name__ == "__main__":
    main()