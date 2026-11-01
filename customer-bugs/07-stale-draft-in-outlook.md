# BUG-07 — Add-in shows today’s quote, Outlook draft is yesterday’s

- Date: 2026-10-20
- Reported by: Sales rep, shared inbox
- Channel: in-app feedback
- Module: Quoting
- Severity: high
- Tags: ui, draft, price, timing

## What the customer said

The side panel said the quote was ready: 420 kg, MUC–EWR, €3.40/kg, ready date next Monday. The open reply in Outlook still had an older draft for the same sender from last week: 900 kg, MUC–ORD, a lower kg rate, arrival “this Friday”. The rep sent with Ctrl+Enter from the reading pane. The customer received the old shipment. They answered “this is not what we asked” and requested the quote from another forwarder.

## What went wrong

Background processing updated the add-in. It did not replace the existing reply draft on the thread. The panel and the message the user sends are two different texts, and the send button is Outlook’s, not the panel’s.

## Why the quote was not used

The customer never saw the correct offer. The rep now copies the panel into a new mail by hand, which removes the reason to use the draft.
