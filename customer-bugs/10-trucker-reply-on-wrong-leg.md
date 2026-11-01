# BUG-10 — Trucker’s pickup rate written onto the air leg

- Date: 2026-10-28
- Reported by: Sales rep, air export
- Channel: in-app feedback
- Module: Quoting
- Severity: medium
- Tags: price, route, trucking, agent-reply

## What the customer said

No door rate was on file, so the rep sent the one-click request to the Stuttgart trucker. The trucker replied “€185 all-in, next-day to FRA, incl. fuel”. nemox put 185 on the air freight kg rate and left the pickup line blank. The customer-facing draft showed €185/kg FRA–JFK plus “pickup: on request”. The rep had to rebuild both legs. They have stopped using the trucker-request button.

## What went wrong

The reply was matched to the open quote, then to the wrong charge line. A flat trucking amount was read as the air rate the quote was still missing. The leg the request was sent for stayed empty.

## Why the quote was not used

Both numbers are unusable: the air rate is absurd, and the pickup is still missing. The rep goes back to asking the trucker from their own mailbox and typing the rate in.
