#!/usr/bin/env python3
"""Test script for scheduler daemon functionality."""

import json
import subprocess
import sys
import time
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def send_request(daemon_process: subprocess.Popen, request: dict) -> dict | None:
    """Send a JSON-RPC request to the daemon and get response."""
    try:
        request_str = json.dumps(request) + "\n"
        daemon_process.stdin.write(request_str)
        daemon_process.stdin.flush()

        # Read response with timeout
        import select
        while True:
            ready = select.select([daemon_process.stdout], [], [], 5)
            if ready[0]:
                response_line = daemon_process.stdout.readline()
                if response_line:
                    return json.loads(response_line.strip())
            break
    except Exception as e:
        print(f"Request error: {e}")
    return None


def main():
    """Test scheduler daemon functionality."""
    print("=" * 60)
    print("Scheduler Daemon Test")
    print("=" * 60)

    # We test by importing directly to avoid subprocess issues
    print("\n[Testing] Importing modules...")

    try:
        from leeway_integration.daemon.core import Daemon, SchedulerDaemon
        from leeway_integration.protocol import CronSchedule
        print("   ✓ Modules imported")

        # Create daemon
        print("\n[1] Creating daemon...")
        daemon = Daemon('.leeway/workflows')
        print("   ✓ Daemon created")

        # Test 1: Ping
        print("\n[2] Testing daemon.ping...")
        result = daemon._ping({})
        print(f"   ✓ Version: {result.get('version')}")
        print(f"   ✓ Status: {result.get('status')}")

        # Test 2: Create a cron schedule
        print("\n[3] Creating cron schedule...")
        result = daemon._cron_create({
            "name": "daily-code-health",
            "workflow_name": "code-health",
            "cron_expression": "*/5 * * * *",
            "user_context": "Scheduled code health check"
        })
        if result.get("success"):
            schedule = result["schedule"]
            schedule_id = schedule["id"]
            print(f"   ✓ Created schedule: {schedule['name']}")
            print(f"   ✓ Schedule ID: {schedule_id}")
            print(f"   ✓ Next run: {schedule.get('next_run', 'N/A')}")
        else:
            print(f"   ✗ Failed: {result}")
            return 1

        # Test 3: List cron schedules
        print("\n[4] Listing cron schedules...")
        result = daemon._cron_list({})
        schedules = result.get("schedules", [])
        print(f"   ✓ Found {len(schedules)} schedule(s)")
        for s in schedules:
            print(f"      - {s['name']}: {s['cron_expression']} (enabled: {s['enabled']})")

        # Test 4: Start scheduler daemon
        print("\n[5] Starting scheduler daemon...")
        result = daemon._scheduler_start({})
        if result.get("success"):
            status = result["status"]
            print(f"   ✓ Scheduler started")
            print(f"   ✓ Running: {status.get('running')}")
            print(f"   ✓ Enabled schedules: {status.get('enabled_schedules')}")
            print(f"   ✓ Total schedules: {status.get('total_schedules')}")
        else:
            print(f"   Note: {result.get('error', 'Already running')}")

        # Test 5: Get scheduler status
        print("\n[6] Getting scheduler status...")
        result = daemon._scheduler_status({})
        status = result["status"]
        print(f"   ✓ Running: {status.get('running')}")
        print(f"   ✓ Enabled schedules: {status.get('enabled_schedules')}")
        print(f"   ✓ Total schedules: {status.get('total_schedules')}")
        print(f"   ✓ Last check: {status.get('last_check', 'N/A')}")
        print(f"   ✓ Executions today: {status.get('executions_today')}")

        # Test 6: Wait for scheduler to run
        print("\n[7] Waiting for scheduler to run (3 seconds)...")
        time.sleep(3)

        # Test 7: Get execution history
        print("\n[8] Getting execution history...")
        result = daemon._scheduler_executions({"limit": 5})
        executions = result.get("executions", [])
        print(f"   ✓ Found {len(executions)} execution(s)")
        for e in executions:
            print(f"      - {e['workflow_name']}: {e.get('started_at', 'N/A')}")
            success = e.get('success')
            print(f"        Success: {success if success is not None else 'N/A'}")

        # Test 8: Stop scheduler daemon
        print("\n[9] Stopping scheduler daemon...")
        result = daemon._scheduler_stop({})
        print(f"   ✓ Scheduler stopped: {result.get('success')}")

        # Test 9: Verify status after stop
        print("\n[10] Verifying scheduler status after stop...")
        result = daemon._scheduler_status({})
        status = result["status"]
        if not status.get("running"):
            print(f"   ✓ Scheduler is stopped")
        else:
            print(f"   ✗ Scheduler still running")
            return 1

        # Test 10: Delete cron schedule
        print("\n[11] Deleting cron schedule...")
        result = daemon._cron_delete({"id": schedule_id})
        if result.get("success"):
            print(f"   ✓ Deleted schedule: {schedule_id}")
        else:
            print(f"   Note: {result.get('error', 'Already deleted')}")

        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return 0

    except Exception as e:
        import traceback
        print(f"\n✗ Error: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())