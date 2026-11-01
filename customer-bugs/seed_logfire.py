"""Send one quoting-agent trace per customer bug to the linked Logfire project.

Docs: https://pydantic.dev/docs/logfire/get-started/first-trace
Spans follow the Pydantic AI shape: an agent-run span, then a model-request
span with gen_ai.input.messages / gen_ai.output.messages.
https://pydantic.dev/docs/ai/integrations/logfire/

Logfire drops records older than 24 hours
(https://pydantic.dev/docs/logfire/reference/limits/). The October report date
is stored as the attribute reported_at. The span time is "now".

    uvx logfire-cli auth
    # Project -> Settings -> Write tokens, or `uvx logfire-cli init` in this directory
    export LOGFIRE_TOKEN=...
    uv run --with logfire customer-bugs/seed_logfire.py
"""

import json
import os

import logfire

logfire.configure(service_name="nemox-quoting", token=os.environ.get("LOGFIRE_TOKEN"))

TRACES = [
    {
        "bug_id": "BUG-01",
        "reported_at": "2026-10-06",
        "severity": "high",
        "user_prompt": "Quote 12 cartons, 180 kg, 4.2 cbm, FRA-ORD, airport to airport.",
        "tool": "rate_air_leg",
        "tool_args": {"actual_kg": 180, "cbm": 4.2, "origin": "FRA", "destination": "ORD"},
        "tool_result": {"chargeable_kg": 180, "volume_weight_kg": None, "rate_eur_per_kg": 1.85},
        "assistant": "Draft: EUR 1.85/kg on 180 kg.",
        "failure": "Volume weight not computed. 4.2 cbm should rate at about 701 kg.",
    },
    {
        "bug_id": "BUG-02",
        "reported_at": "2026-10-08",
        "severity": "high",
        "user_prompt": "EXW Stuttgart, deliver Chicago.",
        "tool": "match_lane",
        "tool_args": {"incoterm": "EXW", "pickup": "Stuttgart", "deliver": "Chicago"},
        "tool_result": {"legs": ["FRA-ORD"], "pickup_leg": None},
        "assistant": "Offer is the FRA-ORD airline rate.",
        "failure": "EXW pickup Stuttgart-FRA was dropped.",
    },
    {
        "bug_id": "BUG-03",
        "reported_at": "2026-10-09",
        "severity": "high",
        "user_prompt": "Quote from a Nordlicht Parts buyer, from @nordlicht-group.com.",
        "tool": "lookup_account",
        "tool_args": {"email_domain": "nordlicht-group.com"},
        "tool_result": {"account": "Nordlicht Industrial", "air_margin_pct": 8},
        "assistant": "Applied the Industrial contract template at 8%.",
        "failure": "Domain match selected the sister account. Parts is 18% spot.",
    },
    {
        "bug_id": "BUG-04",
        "reported_at": "2026-10-13",
        "severity": "medium",
        "user_prompt": "Ready Friday, must arrive Monday. FRA to DXB.",
        "tool": "pick_schedule",
        "tool_args": {"ready": "Friday", "deliver_by": "Monday"},
        "tool_result": {"itinerary": "FRA-IST-DXB", "transit_label": "1 day"},
        "assistant": "Transit 1 day on the cheaper airline.",
        "failure": "Connection arrives Wednesday. Label is marketing transit, not the itinerary.",
    },
    {
        "bug_id": "BUG-05",
        "reported_at": "2026-10-15",
        "severity": "high",
        "user_prompt": "2 pallets, Bishop's Stortford to Dublin, next week.",
        "tool": "resolve_airport",
        "tool_args": {"city": "London", "postcode": None},
        "tool_result": {"airport": "LHR"},
        "assistant": "Built LHR-DUB.",
        "failure": "Postcode on the signature fixes Stansted, not LHR.",
    },
    {
        "bug_id": "BUG-06",
        "reported_at": "2026-10-16",
        "severity": "medium",
        "user_prompt": "FCL quote for the EUR all-in account.",
        "tool": "render_quote",
        "tool_args": {"rate_sheet_currency": "USD", "account_currency": "EUR"},
        "tool_result": {"body": "USD 1840 / 20ft", "pdf": None},
        "assistant": "Pasted the carrier USD rate into the mail body.",
        "failure": "Account currency, FX, surcharges, and PDF template were not applied.",
    },
    {
        "bug_id": "BUG-07",
        "reported_at": "2026-10-20",
        "severity": "high",
        "user_prompt": "420 kg, MUC-EWR, ready next Monday.",
        "tool": "update_outlook_draft",
        "tool_args": {"panel": "MUC-EWR 420kg EUR 3.40", "existing_reply": "MUC-ORD 900kg"},
        "tool_result": {"panel_updated": True, "outlook_draft_replaced": False},
        "assistant": "Add-in shows the new quote.",
        "failure": "Existing Outlook reply on the thread was left in place.",
    },
    {
        "bug_id": "BUG-08",
        "reported_at": "2026-10-21",
        "severity": "high",
        "user_prompt": "Please quote. Packing list attached, 6 lines, one HAWB.",
        "tool": "extract_packing_list",
        "tool_args": {"lines": 6, "pieces": 48, "kg": 1160, "cbm": 6.8},
        "tool_result": {"pieces": 4, "kg": 86, "stopped_after_row": 1},
        "assistant": "Quoted 4 pieces and 86 kg.",
        "failure": "Extraction stopped at the first item row. Totals were not reconciled.",
    },
    {
        "bug_id": "BUG-09",
        "reported_at": "2026-10-23",
        "severity": "high",
        "user_prompt": "FRA-PVG contract allotment, cargo ready 23 October.",
        "tool": "lookup_allotment",
        "tool_args": {"lane": "FRA-PVG", "ready": "2026-10-23"},
        "tool_result": {"rate_eur_per_kg": 2.10, "valid_to": "2026-09-30", "checked_validity": False},
        "assistant": "Drafted EUR 2.10/kg as the live allotment.",
        "failure": "Validity-to is 30 September. October sheet is EUR 2.65/kg.",
    },
    {
        "bug_id": "BUG-10",
        "reported_at": "2026-10-28",
        "severity": "medium",
        "user_prompt": "Trucker replied: EUR 185 all-in, next-day Stuttgart to FRA.",
        "tool": "apply_carrier_reply",
        "tool_args": {"request_leg": "pickup", "amount_eur": 185, "unit": "flat"},
        "tool_result": {"air_rate_eur_per_kg": 185, "pickup_line": None},
        "assistant": "Set the air freight rate to 185. Pickup still on request.",
        "failure": "Flat trucking amount was written onto the air kg rate.",
    },
]


def messages(trace: dict) -> str:
    return json.dumps(
        [
            {"role": "user", "parts": [{"type": "text", "content": trace["user_prompt"]}]},
            {
                "role": "assistant",
                "parts": [
                    {
                        "type": "tool_call",
                        "name": trace["tool"],
                        "arguments": trace["tool_args"],
                    }
                ],
            },
        ]
    )


def main() -> None:
    for trace in TRACES:
        with logfire.span(
            "agent run {bug_id}",
            bug_id=trace["bug_id"],
            _span_name="agent run",
            reported_at=trace["reported_at"],
            severity=trace["severity"],
        ) as span:
            span.set_attribute("pydantic_ai.all_messages", messages(trace))
            with logfire.span(
                "chat quoting-model",
                _span_name="chat quoting-model",
                bug_id=trace["bug_id"],
                **{
                    "gen_ai.input.messages": messages(trace),
                    "gen_ai.output.messages": json.dumps(
                        [
                            {
                                "role": "assistant",
                                "parts": [{"type": "text", "content": trace["assistant"]}],
                            }
                        ]
                    ),
                    "gen_ai.system": "quoting",
                    "gen_ai.request.model": "quoting-model",
                },
            ):
                logfire.info(
                    "tool {tool} returned",
                    tool=trace["tool"],
                    result=trace["tool_result"],
                )
            logfire.warn(
                "{bug_id} {failure}",
                bug_id=trace["bug_id"],
                failure=trace["failure"],
            )
    logfire.force_flush()
    print(f"sent {len(TRACES)} traces")


if __name__ == "__main__":
    main()
