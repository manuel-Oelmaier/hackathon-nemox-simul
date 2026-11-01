# Automatic ticketing

Turn product feedback into a ticket: classify it, pick an owner, and either draft a fix or hand it to the right person.

## Data sources

- Slack
- Report feedback button (date, user)
- Agent traces (Logfire)
- PostHog session video and user traces
- Git issues

## Flow

1. Classify the feedback. Tags: topic and severity.
2. Find the best person from past and related git issues (RAG).
3. Offer a solution PR draft, or the contact person.
4. Assign that person.
5. Notify them in Slack, with a description and a video of the change.

## Open questions

- Connect this to the agent eval idea?
- Health monitoring?
