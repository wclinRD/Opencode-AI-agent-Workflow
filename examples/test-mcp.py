#!/usr/bin/env python3
"""Test MCP integration functionality."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leeway_integration.daemon.core import Daemon


def test_mcp_servers():
    """Test mcp.servers method."""
    print("Testing mcp.servers...")
    daemon = Daemon(workflows_dir=".leeway/workflows")

    # Call mcp.servers method directly
    result = daemon._mcp_servers({})
    print(f"  Result: {result}")

    # Check servers are configured
    assert "servers" in result
    print(f"  Servers: {result['servers']}")
    print("  ✅ mcp.servers works!")


def test_workflow_list():
    """Test workflow.list method."""
    print("\nTesting workflow.list...")
    daemon = Daemon(workflows_dir=".leeway/workflows")

    result = daemon._workflow_list({})
    print(f"  Result: {result}")

    assert "workflows" in result
    print(f"  Workflows: {result['workflows']}")
    print("  ✅ workflow.list works!")


def test_methods_registered():
    """Test that MCP methods are registered."""
    print("\nTesting method registration...")

    daemon = Daemon(workflows_dir=".leeway/workflows")
    methods = list(daemon._methods.keys())
    print(f"  Available methods: {methods}")

    mcp_methods = [m for m in methods if m.startswith("mcp.")]
    print(f"  MCP methods: {mcp_methods}")

    assert "mcp.servers" in methods
    assert "mcp.start" in methods
    assert "mcp.stop" in methods
    assert "mcp.list_tools" in methods
    assert "mcp.execute" in methods
    print("  ✅ All MCP methods registered!")


def test_json_rpc():
    """Test JSON-RPC request handling."""
    print("\nTesting JSON-RPC request...")

    daemon = Daemon(workflows_dir=".leeway/workflows")

    # Create a JSON-RPC request
    request = {
        "jsonrpc": "2.0",
        "id": "test-1",
        "method": "mcp.servers",
        "params": {}
    }

    response = daemon.handle_request(request)
    print(f"  Response: {response.model_dump(exclude_none=True)}")

    assert response.result is not None
    assert "servers" in response.result
    print("  ✅ JSON-RPC request handling works!")


def test_new_workflows():
    """Test that new MCP workflows are available."""
    print("\nTesting new MCP workflows...")

    daemon = Daemon(workflows_dir=".leeway/workflows")
    result = daemon._workflow_list({})

    workflows = result["workflows"]
    print(f"  Available workflows: {workflows}")

    # Check for new MCP workflows
    new_workflows = ["github-search", "research-assistant"]
    for wf in new_workflows:
        if wf in workflows:
            print(f"  ✅ {wf} is available")
        else:
            print(f"  ⚠️  {wf} not found")


def main():
    print("=" * 50)
    print("MCP Integration Test Suite")
    print("=" * 50)

    test_mcp_servers()
    test_workflow_list()
    test_methods_registered()
    test_json_rpc()
    test_new_workflows()

    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()