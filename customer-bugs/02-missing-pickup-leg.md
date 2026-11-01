# BUG-02 — EXW quote priced as airport-to-airport, pickup missing

- Date: 2026-10-08
- Reported by: Sales rep, air export
- Channel: in-app feedback
- Module: Quoting
- Severity: high
- Tags: price, route, incoterm, trucking, quote-unused

## What the customer said

Customer asked EXW Stuttgart, deliver Chicago. nemox pulled a FRA–ORD airline rate and a selling margin, and drafted that as the full offer. No truck Stuttgart–FRA, no export handling. The number looked like a strong airport rate, not a door rate. The rep caught it because the customer’s warehouse is 200 km from FRA. They did not send it.

## What went wrong

Incoterm EXW means the forwarder pays and prices origin pickup. The lane match stopped at the gateway airports. The trucking leg, which is often not on the airline rate sheet, was dropped instead of requested from the trucker.

## Why the quote was not used

The offer is not the product the shipper asked for. If it goes out, the shipper compares it with real door rates and either books a too-cheap quote or treats the forwarder as sloppy.
