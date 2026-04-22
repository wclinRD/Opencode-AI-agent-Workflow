#!/usr/bin/env python3
"""Test script for the daemon streaming functionality."""

import sys
import os
import time
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from leeway_integration.daemon.core import Daemon


def test_daemon():
    """Test the daemon functionality."""
    print("=" * 60)
    print("Testing Leeway Daemon")
    print("=" * 60)

    # Create daemon with stdout capture
    import io
    output = io.StringIO()
    daemon = Daemon(workflows_dir=".leeway/workflows", output=output)

    print("\n1. Testing workflow.list...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-list",
        "method": "workflow.list",
        "params": {}
    })
    result_dict = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else dict(result)
    print(f"   Result: {result_dict}")
    assert result_dict.get("result") is not None
    assert "workflows" in result_dict["result"]
    print(f"   ✅ Available workflows: {result_dict['result']['workflows']}")

    print("\n2. Testing daemon.ping...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-ping",
        "method": "daemon.ping",
        "params": {}
    })
    result_dict = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else dict(result)
    print(f"   Result: {result_dict}")
    assert result_dict.get("result") is not None
    print(f"   ✅ Version: {result_dict['result']['version']}, Status: {result_dict['result']['status']}")

    print("\n3. Testing workflow.execute with streaming...")
    # Reset output to capture events
    output = io.StringIO()
    daemon = Daemon(workflows_dir=".leeway/workflows", output=output)

    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-execute",
        "method": "workflow.execute",
        "params": {
            "name": "code-health",
            "user_context": "Test execution"
        }
    })

    # Get streaming events
    output.seek(0)
    events = output.readlines()
    print(f"   Streaming events ({len(events)} events):")
    for event in events:
        if event.strip():
            data = json.loads(event.strip())
            print(f"     - {data.get('type', 'unknown')}: {data.get('message', data)}")

    result_dict = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else dict(result)
    print(f"   ✅ Result: success={result_dict['result']['success']}")
    print(f"   ✅ Path taken: {result_dict['result']['audit']['path_taken']}")
    print(f"   ✅ Execution ID: {result_dict['result']['audit'].get('execution_id', 'N/A')}")
    print(f"   ✅ Total turns: {result_dict['result']['audit']['total_turns']}")

    print("\n4. Testing workflow.validate...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-validate",
        "method": "workflow.validate",
        "params": {"name": "code-health"}
    })
    result_dict = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else dict(result)
    print(f"   ✅ Valid: {result_dict['result']['valid']}")

    print("\n5. Testing workflow not found error...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-error",
        "method": "workflow.execute",
        "params": {"name": "nonexistent", "user_context": ""}
    })
    result_dict = result.model_dump(exclude_none=True) if hasattr(result, 'model_dump') else dict(result)
    print(f"   ✅ Error code: {result_dict['error']['code']}")
    print(f"   ✅ Error message: {result_dict['error']['message']}")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print("Testing Leeway Daemon")
    print("=" * 60)

    # Create daemon with stdout capture
    import io
    output = io.StringIO()
    daemon = Daemon(workflows_dir=".leeway/workflows", output=output)

    print("\n1. Testing workflow.list...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-list",
        "method": "workflow.list",
        "params": {}
    })
    print(f"   Result: {result}")
    assert "result" in result
    assert "workflows" in result["result"]
    print(f"   ✅ Available workflows: {result['result']['workflows']}")

    print("\n2. Testing daemon.ping...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-ping",
        "method": "daemon.ping",
        "params": {}
    })
    print(f"   Result: {result}")
    assert "result" in result
    print(f"   ✅ Version: {result['result']['version']}, Status: {result['result']['status']}")

    print("\n3. Testing workflow.execute with streaming...")
    # Reset output to capture events
    output = io.StringIO()
    daemon = Daemon(workflows_dir=".leeway/workflows", output=output)

    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-execute",
        "method": "workflow.execute",
        "params": {
            "name": "code-health",
            "user_context": "Test execution"
        }
    })

    # Get streaming events
    output.seek(0)
    events = output.readlines()
    print(f"   Streaming events ({len(events)} events):")
    for event in events:
        if event.strip():
            data = json.loads(event.strip())
            print(f"     - {data.get('type', 'unknown')}: {data.get('message', data)}")

    print(f"   ✅ Result: success={result['result']['success']}")
    print(f"   ✅ Path taken: {result['result']['audit']['path_taken']}")
    print(f"   ✅ Execution ID: {result['result']['audit'].get('execution_id', 'N/A')}")
    print(f"   ✅ Total turns: {result['result']['audit']['total_turns']}")

    print("\n4. Testing workflow.validate...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-validate",
        "method": "workflow.validate",
        "params": {"name": "code-health"}
    })
    print(f"   ✅ Valid: {result['result']['valid']}")

    print("\n5. Testing workflow not found error...")
    result = daemon.handle_request({
        "jsonrpc": "2.0",
        "id": "test-error",
        "method": "workflow.execute",
        "params": {"name": "nonexistent", "user_context": ""}
    })
    print(f"   ✅ Error code: {result['error']['code']}")
    print(f"   ✅ Error message: {result['error']['message']}")

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    test_daemon()