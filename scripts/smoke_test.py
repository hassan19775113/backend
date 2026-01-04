#!/usr/bin/env python
"""
PraxiApp Smoke Test
===================
Schneller End-to-End-Test für Deployment-Validierung.

Verwendung:
    python scripts/smoke_test.py [--base-url http://localhost:8000]
"""

import argparse
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import json


def test_endpoint(base_url: str, path: str, expected_status: int = 200, description: str = "") -> bool:
    """Testet einen einzelnen Endpoint."""
    url = f"{base_url.rstrip('/')}{path}"
    try:
        req = Request(url, headers={'Accept': 'application/json'})
        response = urlopen(req, timeout=10)
        status = response.status
        if status == expected_status:
            print(f"  [OK] {path} -> {status} {description}")
            return True
        else:
            print(f"  [FAIL] {path} -> {status} (expected {expected_status})")
            return False
    except HTTPError as e:
        if e.code == expected_status:
            print(f"  [OK] {path} -> {e.code} {description}")
            return True
        print(f"  [FAIL] {path} -> HTTP {e.code} (expected {expected_status})")
        return False
    except URLError as e:
        print(f"  [FAIL] {path} -> Connection error: {e.reason}")
        return False
    except Exception as e:
        print(f"  [FAIL] {path} -> {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="PraxiApp Smoke Test")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL des Servers")
    parser.add_argument("--wait", type=int, default=0, help="Sekunden warten vor dem Test")
    args = parser.parse_args()

    if args.wait:
        print(f"Warte {args.wait} Sekunden auf Server-Start...")
        time.sleep(args.wait)

    print("=" * 60)
    print(f"  PraxiApp Smoke Test")
    print(f"  Base URL: {args.base_url}")
    print("=" * 60)

    tests = [
        # (path, expected_status, description)
        ("/", 200, "Healthcheck"),
        ("/admin/", 200, "Admin Login Page"),
        ("/api/auth/login/", 405, "Auth Endpoint (POST only)"),
        ("/api/appointments/", 401, "Appointments (Auth required)"),
        ("/api/operations/", 401, "Operations (Auth required)"),
        ("/api/calendar/week/", 401, "Calendar (Auth required)"),
        ("/api/practice-hours/", 401, "Practice Hours (Auth required)"),
    ]

    print("\n[1] ENDPOINT TESTS")
    print("-" * 60)
    
    results = []
    for path, expected, desc in tests:
        results.append(test_endpoint(args.base_url, path, expected, desc))

    # Summary
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"  ERGEBNIS: {passed}/{total} Tests bestanden")
    print("=" * 60)

    if passed == total:
        print("\n  [SUCCESS] Alle Smoke Tests bestanden!")
        return 0
    else:
        print(f"\n  [FAILED] {total - passed} Tests fehlgeschlagen!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
