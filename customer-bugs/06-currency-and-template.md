# BUG-06 — USD rate sheet pasted into a EUR customer quote

- Date: 2026-10-16
- Reported by: Sales rep, ocean desk
- Channel: in-app feedback
- Module: Quoting
- Severity: medium
- Tags: price, currency, template, ui

## What the customer said

The account quotes in EUR, all-in, with their logo and the agreed surcharge list (BAF, ETS, local charges). nemox dropped the carrier USD FCL rate into the mail body as “USD 1,840 / 20ft” and skipped the customer PDF. No FX, no local charges. In the add-in the rate looks finished because a number is there. The rep did not notice the currency until the customer asked why this quote was in dollars and missing the usual lines.

## What went wrong

The rate-sheet currency was kept. The per-customer quote currency, FX rule, surcharge set, and PDF template were not applied after the lane matched.

## Why the quote was not used

The customer cannot compare it with the last offer. They treat a partial draft as the forwarder forgetting their agreement.
