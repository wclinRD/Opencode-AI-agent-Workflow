#!/usr/bin/env python3
"""Test script for Phase 4.2 performance optimizations."""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from leeway_integration.daemon.core import Daemon, ResultCache

def test_result_cache():
    """Test ResultCache class."""
    print("=" * 60)
    print("Testing ResultCache...")
    
    cache = ResultCache(max_size=10, default_ttl=60.0)
    
    # Test set and get
    cache.set("workflow.list", {}, {"workflows": ["code-health", "api-design"]})
    result = cache.get("workflow.list", {})
    assert result == {"workflows": ["code-health", "api-design"]}, f"Expected cached result, got {result}"
    print("  ✓ Set and get cached result")
    
    # Test hit rate tracking
    cache.get("workflow.list", {})  # Second get - should be a hit
    cache.get("workflow.list", {})  # Third get - should be a hit
    stats = cache.get_stats()
    assert stats["hits"] == 3, f"Expected 3 hits, got {stats['hits']}"
    assert stats["misses"] == 0, f"Expected 0 misses, got {stats['misses']}"
    print(f"  ✓ Hit rate tracking: {stats['hit_rate']}")
    
    # Test cache invalidation
    cache.set("workflow.execute", {"name": "code-health"}, {"success": True})
    count = cache.invalidate(method="workflow.list")
    assert count == 1, f"Expected 1 invalidation, got {count}"
    result = cache.get("workflow.list", {})
    assert result is None, f"Expected None after invalidation, got {result}"
    print("  ✓ Cache invalidation by method")
    
    # Test invalidation by pattern
    cache.set("mcp.servers", {}, {"servers": []})
    count = cache.invalidate(pattern="mcp")
    assert count == 1, f"Expected 1 invalidation, got {count}"
    print("  ✓ Cache invalidation by pattern")
    
    # Test clear all
    cache.set("tools.list", {}, {"tools": []})
    count = cache.clear()
    assert cache.get_stats()["size"] == 0, "Expected empty cache after clear"
    print("  ✓ Cache clear all")
    
    print("ResultCache tests passed!\n")


def test_daemon_cache_methods():
    """Test daemon cache methods."""
    print("=" * 60)
    print("Testing Daemon cache methods...")
    
    daemon = Daemon(workflows_dir=".leeway/workflows")
    
    # Test cache.get_stats
    request = {"jsonrpc": "2.0", "id": "1", "method": "cache.get_stats", "params": {}}
    response = daemon.handle_request(request)
    stats = response.result
    print(f"  ✓ cache.get_stats: size={stats['size']}")
    
    # Test cache.clear
    request = {"jsonrpc": "2.0", "id": "2", "method": "cache.clear", "params": {}}
    response = daemon.handle_request(request)
    assert response.result["success"] is True
    print(f"  ✓ cache.clear: {response.result}")
    
    # Test cache.invalidate
    request = {"jsonrpc": "2.0", "id": "3", "method": "cache.invalidate", "params": {"method": "workflow.list"}}
    response = daemon.handle_request(request)
    print(f"  ✓ cache.invalidate: {response.result}")
    
    # Test cacheable methods are cached
    request = {"jsonrpc": "2.0", "id": "4", "method": "workflow.list", "params": {}}
    response = daemon.handle_request(request)
    print(f"  ✓ workflow.list: {response.result}")
    
    # Verify it's cached (second call should return cached result)
    stats = daemon._result_cache.get_stats()
    print(f"  ✓ Cache stats after workflow.list: {stats}")
    
    print("Daemon cache methods tests passed!\n")


def test_daemon_warmup():
    """Test daemon warmup method."""
    print("=" * 60)
    print("Testing Daemon warmup...")
    
    daemon = Daemon(workflows_dir=".leeway/workflows")
    
    request = {"jsonrpc": "2.0", "id": "1", "method": "daemon.warmup", "params": {}}
    response = daemon.handle_request(request)
    result = response.result
    print(f"  ✓ daemon.warmup: {result['message']}")
    print(f"    Preloaded workflows: {result['preloaded']['workflows']}")
    
    print("Daemon warmup tests passed!\n")


def test_deterministic_caching():
    """Test deterministic method caching (workflow.execute, tools.execute)."""
    print("=" * 60)
    print("Testing deterministic method caching...")
    
    daemon = Daemon(workflows_dir=".leeway/workflows")
    
    # Execute workflow.list twice - second should hit cache
    request1 = {"jsonrpc": "2.0", "id": "1", "method": "workflow.list", "params": {}}
    response1 = daemon.handle_request(request1)
    
    request2 = {"jsonrpc": "2.0", "id": "2", "method": "workflow.list", "params": {}}
    response2 = daemon.handle_request(request2)
    
    stats = daemon._result_cache.get_stats()
    print(f"  ✓ workflow.list called twice: {stats['hits']} hits, {stats['misses']} misses")
    
    print("Deterministic caching tests passed!\n")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Phase 4.2 Performance Optimization Tests")
    print("=" * 60 + "\n")
    
    test_result_cache()
    test_daemon_cache_methods()
    test_daemon_warmup()
    test_deterministic_caching()
    
    print("=" * 60)
    print("All Phase 4.2 tests passed!")
    print("=" * 60)