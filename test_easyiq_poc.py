#!/usr/bin/env python3
"""Probe the EasyIQ Skoleportal Ugeplan browser flow.

Usage:
    python3 test_easyiq_poc.py --token '<widget-token>' \
        --child athe0231 --login-id 1945154

The login ID is optional when AuthenticateAulaUser returns JSON. It can be
provided manually to separate calendar endpoint testing from login ID discovery.
"""

import argparse
import datetime
import json
import sys

import requests


BASE_URL = "https://skoleportal.easyiqcloud.dk"
WIDGET_PATH = "/UgeplanWidget"
AUTH_PATH = "/AuthenticateAulaUser"
EVENTS_PATH = "/Calendar/CalendarGetWeekplanEvents"


def parse_args():
    parser = argparse.ArgumentParser(description="Test the EasyIQ Ugeplan API")
    parser.add_argument("--token", required=True, help="Raw widget 0128 token")
    parser.add_argument("--child", default="athe0231", help="Child UniLogin ID")
    parser.add_argument("--login", default="mart40w8", help="Guardian UniLogin ID")
    parser.add_argument(
        "--institutions",
        default="G11453,281815",
        help="Comma-separated institution codes",
    )
    parser.add_argument(
        "--children",
        default="linu1396,athe0231",
        help="Comma-separated child UniLogin IDs",
    )
    parser.add_argument(
        "--login-id",
        help="Known EasyIQ loginId, useful when auth returns the HTML shell",
    )
    parser.add_argument(
        "--date",
        help="Week start date, YYYY-MM-DD; defaults to today",
    )
    return parser.parse_args()


def json_events(response):
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return (
            payload.get("Events")
            or payload.get("events")
            or payload.get("data")
            or payload.get("items")
            or payload.get("WeekPlan")
            or []
        )
    return None


def main():
    args = parse_args()
    token = args.token.removeprefix("Bearer ").strip()
    auth_header = "Bearer " + token
    target_date = args.date or datetime.date.today().strftime("%Y-%m-%dT00:00:00")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Authorization": auth_header,
        "X-Login": args.login,
        "X-InstitutionFilter": args.institutions,
        "X-UserProfile": "guardian",
        "X-ChildFilter": args.children,
        "X-Child": args.child,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE_URL + WIDGET_PATH,
        "Origin": BASE_URL,
    }

    session = requests.Session()
    session.headers.update(headers)

    print("[1] GET /UgeplanWidget?token=<redacted>")
    widget_response = session.get(
        BASE_URL + WIDGET_PATH,
        params={"token": token},
        allow_redirects=True,
        timeout=15,
    )
    print(f"    status={widget_response.status_code}")
    print(f"    content_type={widget_response.headers.get('Content-Type')}")
    print(f"    cookies={sorted(session.cookies.keys())}")

    print("[2] POST /AuthenticateAulaUser (empty body)")
    auth_response = session.post(
        BASE_URL + AUTH_PATH,
        headers={"Content-Length": "0"},
        data=None,
        allow_redirects=True,
        timeout=15,
    )
    print(f"    status={auth_response.status_code}")
    print(f"    content_type={auth_response.headers.get('Content-Type')}")
    print(f"    cookies={sorted(session.cookies.keys())}")
    print(f"    body_prefix={auth_response.text[:80]!r}")

    login_id = args.login_id
    activity_filter = None
    try:
        auth_json = auth_response.json()
    except ValueError:
        auth_json = None

    if isinstance(auth_json, dict):
        login_id = (
            auth_json.get("loginId")
            or auth_json.get("LoginId")
            or auth_json.get("id")
            or login_id
        )
        activity_filter = (
            auth_json.get("activityFilter")
            or auth_json.get("ActivityFilter")
            or auth_json.get("activityId")
        )

    if not login_id:
        print("    RESULT: no loginId returned; stop before calendar request")
        print("    Re-run with --login-id <known EasyIQ loginId> to test events")
        return 2

    print(f"    login_id={login_id}")
    if activity_filter:
        print(f"    activity_filter={activity_filter}")

    params = {
        "loginId": str(login_id),
        "date": target_date,
        "courseFilter": "-1",
        "textFilter": "",
        "ownWeekPlan": "false",
    }
    if activity_filter:
        params["activityFilter"] = str(activity_filter)

    print("[3] GET /Calendar/CalendarGetWeekplanEvents")
    events_response = session.get(
        BASE_URL + EVENTS_PATH,
        params=params,
        allow_redirects=True,
        timeout=15,
    )
    print(f"    status={events_response.status_code}")
    print(f"    content_type={events_response.headers.get('Content-Type')}")

    events = json_events(events_response)
    if events is None:
        print(f"    body_prefix={events_response.text[:200]!r}")
        print("    RESULT: no JSON events")
        return 1

    print(f"    RESULT: received {len(events)} JSON events")
    for index, event in enumerate(events[:5], 1):
        if not isinstance(event, dict):
            print(f"    event_{index}={event!r}")
            continue
        print(
            f"    event_{index}: "
            f"{event.get('StartTime') or event.get('start')} - "
            f"{event.get('EndTime') or event.get('end')}: "
            f"{event.get('CoursesDisplay') or event.get('Title') or 'Ugeplan'}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
