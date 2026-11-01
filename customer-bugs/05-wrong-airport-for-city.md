# BUG-05 — “London” rated via LHR, customer wanted STN

- Date: 2026-10-15
- Reported by: Sales rep, UK desk
- Channel: in-app feedback
- Module: Quoting
- Severity: high
- Tags: route, lane-match, price

## What the customer said

The mail said “2 pallets, Bishop’s Stortford to Dublin, next week”. nemox built LHR–DUB. The shipper’s forwarder agreement and the trucking tariff are Stansted. LHR trucking from Bishop’s Stortford is a different zone and a higher cost, and the flight times do not match the STN allotment. The draft looked complete, so a junior rep sent it. The customer rejected it the same day: wrong airport, wrong truck price.

## What went wrong

The city was resolved to the largest airport. The pickup postcode, which fixes the airport and the trucking zone, was on the signature address and was not used for the lane.

## Why the quote was not used

The route is a different product. Price and transit are both wrong, and the customer already has the bad offer in writing.
