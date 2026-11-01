# Cursor automation "Fix bugs reported in Slack" with the procedural graph

The automation reads its procedures from a procedural graph before it works, and records every run
as one incident episode with at most one mutation. This is the same cycle that our Claude Code and
Codex agents run with `pgraph`, on a separate Supabase project for this hackathon.

    Slack report ─> Cursor agent ─ retrieve ─> procedures of bug_triage
                        │ investigate, fix, test
                        ├─ report ─> episode + mutation (candidate) ─> graph
                        └─ reply in the Slack thread, with the episode ID
    stop hook (.cursor/hooks.json): one follow-up turn if a run ends without a report

## Set up (once)

1. Cursor dashboard → Cloud Agents → the environment of the automation → secrets:
   - `PGRAPH_SUPABASE_URL`: the URL of the graph project.
   - `PGRAPH_SUPABASE_KEY`: the publishable key of the graph project. Never commit it: this repo is public.
   - `PGRAPH_AGENT`: `cursor-fix-slack-bugs`, the agent name in the episodes.
2. Automation config:
   - Replace the prompt with `cursor/fix-slack-bugs.prompt.md`.
   - Set `"memoryEnabled": false`. The graph is the memory; `MEMORIES.md` would be a second one.
   - Keep `readSlack` and `slack`. Remove the Runway MCP, or add a step to the prompt that uses it.
3. Check it from a shell with the three variables set:
   `python3 tools/procgraph.py retrieve --domain bug_triage` prints the procedures.

## What the agent can change

The publishable key can call only `retrieve_subgraph`, `retrieve_subgraph_text` and
`commit_evolutionary_turn`. It cannot read or change tables, and it cannot promote anything.

| Mutation | What the graph does |
|---|---|
| none (`NO_STRUCTURAL_CHANGE`) | updates visits and fitness of the `--used` nodes |
| `PARAMETER_MUTATION` | changes one node parameter, as a candidate |
| `WEIGHT_MUTATION` | changes the weight of an existing edge, as a candidate |
| `STRUCTURAL_MUTATION` | adds a procedure or trap node, as a candidate |
| `CROSSOVER` | logs the proposal only; the curator applies it |

Our local setup runs LLM mutation operators and judges through our model proxy. Cursor has no access
to it, so here the agent proposes at most one mutation per run, and the database gate
`evaluate_mutation_promotions` decides. The gate counts only mechanical scores (`--verified-scope`
from tests) and user verdicts; self scores never count. The curator holds the service key and runs
the gate, applies CROSSOVER, deactivates nodes and adds edges with `pgraph`.

## Tests

    python3 -m unittest discover -s tools
