# BUG-03 — Sister-company margin applied to the wrong account

- Date: 2026-10-09
- Reported by: Sales lead
- Channel: Slack
- Module: Quoting
- Severity: high
- Tags: price, margin, master-data

## What the customer said

Two accounts share `@nordlicht-group.com`. Key account “Nordlicht Industrial” is on a 8% air margin. Spot account “Nordlicht Parts” is on 18%. A Parts buyer mailed from the group domain. nemox recognised the domain, applied 8%, and drafted the Industrial template, including their contract all-in wording. Parts has no contract. The rep almost sent a contract rate to a spot customer.

## What went wrong

Sender matching stopped at the email domain. Profit category, currency, and quote text are per account, not per domain. The wrong master-data row was selected.

## Why the quote was not used

The price is below the account’s floor. Once a spot customer has seen the key-account rate, the rep cannot walk it back.
