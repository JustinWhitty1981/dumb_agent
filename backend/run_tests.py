#!/usr/bin/env python3
"""
Agent-Friendly Test Runner & Regression Suite.
Runs pytest test cases, formats output for human & agent consumption,
and saves structured execution results to test_results.json.
"""

import sys
import os
import time
import json

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import pytest


class AgentTestCollector:
    """Pytest plugin to collect detailed test results for agent consumption."""
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.failed):
            duration = getattr(report, "duration", 0.0)
            status = "PASSED" if report.passed else ("SKIPPED" if report.skipped else "FAILED")
            
            error_message = None
            if report.failed:
                error_message = str(report.longrepr)

            self.results.append({
                "node_id": report.nodeid,
                "test_name": report.location[2] if report.location else report.nodeid,
                "status": status,
                "duration_seconds": round(duration, 3),
                "error": error_message
            })


def main():
    print("=" * 70)
    print("J.A.D.A AGENT REGRESSION & UNIT TEST SUITE")
    print("=" * 70)

    test_file = os.path.join(BACKEND_DIR, "tests", "test_agent_suite.py")
    collector = AgentTestCollector()

    # Run pytest programmatically with collector plugin
    start_time = time.time()
    exit_code = pytest.main(["-v", test_file], plugins=[collector])
    total_duration = round(time.time() - start_time, 2)

    passed = [r for r in collector.results if r["status"] == "PASSED"]
    failed = [r for r in collector.results if r["status"] == "FAILED"]
    skipped = [r for r in collector.results if r["status"] == "SKIPPED"]

    print("\n" + "=" * 70)
    print("TEST SUMMARY RESULTS")
    print("=" * 70)
    print(f"Total Tests Run : {len(collector.results)}")
    print(f"Passed           : {len(passed)}")
    print(f"Failed           : {len(failed)}")
    print(f"Skipped          : {len(skipped)}")
    print(f"Total Duration   : {total_duration} seconds")
    print("-" * 70)

    for item in collector.results:
        badge = "[PASS]" if item["status"] == "PASSED" else ("[SKIP]" if item["status"] == "SKIPPED" else "[FAIL]")
        print(f"{badge} {item['test_name']} ({item['duration_seconds']}s)")
        if item["error"]:
            print(f"   └─ Error: {item['error'].splitlines()[-1]}")

    print("=" * 70)

    # Save structured JSON results for automated agent inspection
    summary_json = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(collector.results),
        "passed": len(passed),
        "failed": len(failed),
        "skipped": len(skipped),
        "duration_seconds": total_duration,
        "exit_code": int(exit_code),
        "tests": collector.results
    }

    report_path = os.path.join(BACKEND_DIR, "test_results.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary_json, f, indent=2)

    print(f"\nDetailed report saved to: {report_path}\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
