"""Send the ten customer bugs to a PostHog project as historical events.

Docs: https://posthog.com/docs/api/capture

Uses the capture batch API. Timestamps are the report dates in the bug files.
Session recordings are not created by this script. PostHog only stores a replay
when a browser running posthog-js actually records one.

    export POSTHOG_PROJECT_TOKEN=phc_...
    export POSTHOG_HOST=https://eu.i.posthog.com   # or https://us.i.posthog.com
    python customer-bugs/seed_posthog.py
"""

import json
import os
import urllib.request

HOST = os.environ.get("POSTHOG_HOST", "https://eu.i.posthog.com").rstrip("/")
TOKEN = os.environ["POSTHOG_PROJECT_TOKEN"]

# One quoting session per bug. distinct_id is the rep, not the shipper.
BUGS = [
    {
        "id": "BUG-01",
        "at": "2026-10-06T09:14:00Z",
        "distinct_id": "rep-air-export",
        "name": "Air export rep",
        "channel": "in-app feedback",
        "severity": "high",
        "tags": ["price", "weight", "packing-list", "quote-unused"],
        "lane": "FRA-ORD",
        "outcome": "discarded",
        "draft": "EUR 1.85/kg on 180 kg actual",
        "expected": "volume weight 701 kg",
        "text": "Draft used 180 kg actual and ignored 4.2 cbm. Chargeable weight should be about 701 kg. Deleted the draft.",
    },
    {
        "id": "BUG-02",
        "at": "2026-10-08T11:02:00Z",
        "distinct_id": "rep-air-export",
        "name": "Air export rep",
        "channel": "in-app feedback",
        "severity": "high",
        "tags": ["price", "route", "incoterm", "trucking", "quote-unused"],
        "lane": "STR-FRA-ORD",
        "outcome": "discarded",
        "draft": "FRA-ORD airline rate only, EXW Stuttgart",
        "expected": "pickup Stuttgart-FRA plus export handling",
        "text": "EXW Stuttgart to Chicago was drafted as airport-to-airport. Pickup leg missing. Did not send.",
    },
    {
        "id": "BUG-03",
        "at": "2026-10-09T14:40:00Z",
        "distinct_id": "lead-sales",
        "name": "Sales lead",
        "channel": "slack",
        "severity": "high",
        "tags": ["price", "margin", "master-data"],
        "lane": "group-domain",
        "outcome": "discarded",
        "draft": "8% Nordlicht Industrial margin and contract wording",
        "expected": "18% Nordlicht Parts spot margin",
        "text": "Parts buyer on the group domain got the Industrial 8% margin and contract template.",
    },
    {
        "id": "BUG-04",
        "at": "2026-10-13T08:22:00Z",
        "distinct_id": "rep-air-export",
        "name": "Air export rep",
        "channel": "in-app feedback",
        "severity": "medium",
        "tags": ["timing", "route", "schedule"],
        "lane": "FRA-IST-DXB",
        "outcome": "edited",
        "draft": "transit 1 day",
        "expected": "connection arrives Wednesday, not Monday",
        "text": "Cheaper connection sold as a direct next-day. Customer needed Monday. Rep rewrote the schedule.",
    },
    {
        "id": "BUG-05",
        "at": "2026-10-15T16:05:00Z",
        "distinct_id": "rep-uk",
        "name": "UK desk rep",
        "channel": "in-app feedback",
        "severity": "high",
        "tags": ["route", "lane-match", "price"],
        "lane": "LHR-DUB",
        "outcome": "sent",
        "draft": "LHR-DUB",
        "expected": "STN-DUB from Bishop's Stortford",
        "text": "London resolved to LHR. Shipper and trucking tariff are Stansted. Customer rejected it.",
    },
    {
        "id": "BUG-06",
        "at": "2026-10-16T10:18:00Z",
        "distinct_id": "rep-ocean",
        "name": "Ocean desk rep",
        "channel": "in-app feedback",
        "severity": "medium",
        "tags": ["price", "currency", "template", "ui"],
        "lane": "FCL-20",
        "outcome": "sent",
        "draft": "USD 1840 / 20ft, no PDF",
        "expected": "EUR all-in with BAF, ETS, local charges",
        "text": "USD rate sheet pasted into a EUR account quote. Customer asked why the quote was in dollars.",
    },
    {
        "id": "BUG-07",
        "at": "2026-10-20T09:47:00Z",
        "distinct_id": "rep-shared-inbox",
        "name": "Shared inbox rep",
        "channel": "in-app feedback",
        "severity": "high",
        "tags": ["ui", "draft", "price", "timing"],
        "lane": "MUC-EWR",
        "outcome": "sent",
        "draft": "Outlook still had last week's MUC-ORD draft",
        "expected": "420 kg MUC-EWR at EUR 3.40/kg",
        "text": "Add-in showed today's quote. Outlook reply was yesterday's shipment. Rep sent with Ctrl+Enter.",
    },
    {
        "id": "BUG-08",
        "at": "2026-10-21T13:11:00Z",
        "distinct_id": "rep-air-export",
        "name": "Air export rep",
        "channel": "email",
        "severity": "high",
        "tags": ["price", "weight", "packing-list", "attachments"],
        "lane": "multi-line-hawb",
        "outcome": "discarded",
        "draft": "4 pieces, 86 kg (line 1)",
        "expected": "48 pieces, 1160 kg, 6.8 cbm",
        "text": "Packing list xlsx rated on the first line only. Totals row ignored.",
    },
    {
        "id": "BUG-09",
        "at": "2026-10-23T15:33:00Z",
        "distinct_id": "pricing-manager",
        "name": "Pricing manager",
        "channel": "slack",
        "severity": "high",
        "tags": ["price", "rate-sheet", "allotment"],
        "lane": "FRA-PVG",
        "outcome": "sent",
        "draft": "EUR 2.10/kg expired allotment",
        "expected": "October sheet EUR 2.65/kg",
        "text": "Allotment ended 30 September. Two quotes sent on 23 October at the old rate. One accepted.",
    },
    {
        "id": "BUG-10",
        "at": "2026-10-28T12:26:00Z",
        "distinct_id": "rep-air-export",
        "name": "Air export rep",
        "channel": "in-app feedback",
        "severity": "medium",
        "tags": ["price", "route", "trucking", "agent-reply"],
        "lane": "FRA-JFK",
        "outcome": "discarded",
        "draft": "EUR 185/kg on the air leg, pickup blank",
        "expected": "EUR 185 flat trucking Stuttgart-FRA",
        "text": "Trucker reply of EUR 185 all-in was written onto the air kg rate. Pickup line left empty.",
    },
]


def events_for(bug: dict) -> list[dict]:
    base = {
        "bug_id": bug["id"],
        "severity": bug["severity"],
        "tags": bug["tags"],
        "lane": bug["lane"],
        "channel": bug["channel"],
        "module": "quoting",
        "$session_id": bug["id"].lower(),
        "$current_url": "https://app.nemox.ai/inbox",
        "$set": {"name": bug["name"], "role": "nemox sales"},
    }
    return [
        {
            "event": "rfq_opened",
            "distinct_id": bug["distinct_id"],
            "timestamp": bug["at"],
            "properties": base,
        },
        {
            "event": "quote_drafted",
            "distinct_id": bug["distinct_id"],
            "timestamp": bug["at"],
            "properties": {**base, "draft": bug["draft"], "expected": bug["expected"]},
        },
        {
            "event": "quote_outcome",
            "distinct_id": bug["distinct_id"],
            "timestamp": bug["at"],
            "properties": {**base, "outcome": bug["outcome"]},
        },
        {
            "event": "feedback_submitted",
            "distinct_id": bug["distinct_id"],
            "timestamp": bug["at"],
            "properties": {**base, "feedback": bug["text"]},
        },
    ]


def main() -> None:
    batch = [event for bug in BUGS for event in events_for(bug)]
    body = json.dumps(
        {"api_key": TOKEN, "historical_migration": True, "batch": batch}
    ).encode()
    request = urllib.request.Request(
        f"{HOST}/batch/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        print(response.status, response.read().decode())
    print(f"sent {len(batch)} events for {len(BUGS)} bugs")


if __name__ == "__main__":
    main()
