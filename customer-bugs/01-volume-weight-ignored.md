# BUG-01 — Air quote uses actual kg and ignores volume

- Date: 2026-10-06
- Reported by: Sales rep, shared quoting inbox
- Channel: in-app feedback
- Module: Quoting
- Severity: high
- Tags: price, weight, packing-list, quote-unused

## What the customer said

RFQ: 12 cartons, 180 kg actual, 4.2 cbm, FRA–ORD, airport-to-airport. nemox drafted €1.85/kg on 180 kg. Chargeable weight on air is the higher of actual and volume weight (4.2 cbm × 167 kg ≈ 701 kg). The draft was about a quarter of the sell rate. The rep deleted it and built the quote by hand. Same thing three times this week on loose cartons.

## What went wrong

The packing list was read. Actual weight was used as the rating weight. Volume (cbm, or L×W×H) was not converted to volume weight, so the margin was applied to the wrong base.

## Why the quote was not used

Sending it would undercharge the customer and miss the airline cost. Reps stop trusting the draft on any shipment that is not dense cargo.
