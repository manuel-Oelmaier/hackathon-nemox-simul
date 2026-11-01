# BUG-04 — Connection sold as a direct next-day flight

- Date: 2026-10-13
- Reported by: Sales rep, air export
- Channel: in-app feedback
- Module: Quoting
- Severity: medium
- Tags: timing, route, schedule

## What the customer said

RFQ said “ready Friday, must arrive Monday”. nemox offered a cheaper airline and wrote “transit 1 day”. That rate is FRA–IST–DXB, not a direct. With the Friday cutoff already passed for the direct, the connection arrives Wednesday. The customer had asked for Monday. The rep rewrote the schedule before sending. The customer later wrote that the first version “did not read the email”.

## What went wrong

The rate row has an elapsed time or a marketing transit, not the itinerary. Cutoff, cargo-ready date, and connection were not checked against the requested delivery.

## Why the quote was not used

On urgent freight the shipper picks the forwarder who states the arrival day correctly. A wrong transit loses the quote even when the price is fine.
