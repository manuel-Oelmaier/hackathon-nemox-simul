# BUG-08 — Multi-line packing list rated on the first line only

- Date: 2026-10-21
- Reported by: Sales rep, air export
- Channel: email to support
- Module: Quoting
- Severity: high
- Tags: price, weight, packing-list, attachments

## What the customer said

The RFQ mail was two lines: “please quote, packing list attached”. The xlsx had 6 lines, 48 pieces, 1,160 kg, 6.8 cbm, one HAWB. nemox quoted 4 pieces and 86 kg, which is line 1, and ignored the totals row. The draft read as a small courier shipment. The rep checked the attachment only because the price was far below the usual lane. Without that check it would have gone out.

## What went wrong

Extraction took the first item row and stopped. The sheet total, the piece count, and the sum of line weights were not reconciled. A one-line body plus a multi-line attachment is a normal RFQ, not an edge case.

## Why the quote was not used

The offer describes a different shipment. The customer would read it as the forwarder not opening the file.
