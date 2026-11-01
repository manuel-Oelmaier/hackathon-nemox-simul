# BUG-09 — Expired allotment sold as the live rate

- Date: 2026-10-23
- Reported by: Pricing manager
- Channel: Slack
- Module: Quoting
- Severity: high
- Tags: price, rate-sheet, allotment

## What the customer said

A contract allotment FRA–PVG at €2.10/kg ended on 30 September. The October sheet has €2.65/kg. On 23 October nemox still drafted €2.10 and marked it as the allotment. Sales sent two quotes before pricing noticed. One customer accepted. The airline invoice will not match, and the accepted quote is already in the TMS.

## What went wrong

“Rate sheet live within hours” still served the previous file. Validity-to on the allotment row was not compared with the cargo-ready date. A quote counted once, so regenerating did not refresh the rate that was already sitting on the draft.

## Why the quote was not used

When it is sent, the forwarder is stuck with a rate the carrier will not honour. Pricing then tells sales to stop using nemox on contract lanes until the sheet is trusted.
