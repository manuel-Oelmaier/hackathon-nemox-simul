#!/usr/bin/env python3
"""Procedural-graph client for Cursor cloud agents.

A Cursor automation reads the procedures of its domain before it works (``retrieve``) and records
each run as one incident episode with at most one mutation (``report``). The client calls the same
Supabase RPCs as the ``pgraph`` CLI, so fitness updates and candidate mutations follow the same rules.
Promotion stays with the database gate ``evaluate_mutation_promotions``, which this key cannot call.

Environment: ``PGRAPH_SUPABASE_URL`` (project URL), ``PGRAPH_SUPABASE_KEY`` (a key allowed to call
the graph RPCs) and ``PGRAPH_AGENT`` (the agent name in episodes, default ``cursor-automation``).
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request

# One run, one episode: the marker holds the report of the current run (each cloud run starts clean).
MARKER = os.path.join(tempfile.gettempdir(), "procgraph-report.json")
INCIDENT_FIELDS = ("bug_id", "summary", "evidence", "root_cause", "fix")
SCORE_SOURCES = ("self", "mechanical", "user")
MUTATIONS = ("NO_STRUCTURAL_CHANGE", "PARAMETER_MUTATION", "WEIGHT_MUTATION", "STRUCTURAL_MUTATION", "CROSSOVER")
SECRET_RE = re.compile(
    r"eyJ[\w-]{10,}\.[\w-]{10,}\.|sb_(?:secret|publishable)_[\w-]{10,}|sbp_[0-9a-f]{20,}|sk-[\w-]{16,}"
    r"|gh[pousr]_\w{20,}|github_pat_\w{20,}|xox[abprs]-[\w-]{10,}|AKIA[0-9A-Z]{16}|ph[cx]_\w{20,}"
    r"|pylf_v\d+_\w{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----")


class GraphError(Exception):
    """A report or request that the client or the graph refused."""


def rpc(name, body):
    """Call one graph RPC through PostgREST.

    :param name: the RPC name, for example ``retrieve_subgraph``.
    :param body: the JSON arguments of the RPC.
    :returns: the parsed JSON answer.
    :raises GraphError: when the configuration is missing or the call fails.
    """
    url, key = os.environ.get("PGRAPH_SUPABASE_URL"), os.environ.get("PGRAPH_SUPABASE_KEY")
    if not (url and key):
        raise GraphError("set PGRAPH_SUPABASE_URL and PGRAPH_SUPABASE_KEY")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # legacy JWT keys go in both headers; the new sb_ keys only in apikey
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{url.rstrip('/')}/rest/v1/rpc/{name}", data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        raise GraphError(f"HTTP {e.code} from {name}: {e.read().decode('utf-8', 'replace')[:400]}") from e
    except urllib.error.URLError as e:
        raise GraphError(f"cannot reach the graph: {e.reason}") from e


def retrieve(domain, k):
    """Return the active nodes of a domain, best first.

    The RPC ranks domain and meta nodes in one list, so the client asks for a wide slice
    and keeps the domain's own nodes.

    :param domain: the graph domain, for example ``bug_triage``.
    :param k: the number of nodes to return.
    :returns: node rows with ``node_id``, ``node_name``, ``node_type``, ``description`` and ``parameters``.
    :raises GraphError: when the call fails.
    """
    rows = rpc("retrieve_subgraph", {"p_domain": domain, "p_top_k": max(4 * k, 80)}) or []
    return [r for r in rows if r["domain"] == domain][:k]


def format_nodes(nodes):
    """Render nodes as short text for the agent's context.

    :param nodes: rows from :func:`retrieve`.
    :returns: one block per node, or a note that the domain has no nodes yet.
    """
    if not nodes:
        return "(no nodes yet: a STRUCTURAL_MUTATION adds the first one)"
    blocks = []
    for n in nodes:
        block = (f"- {n['node_name']} [{n['node_type']}] fitness={n['fitness_score']:.2f} "
                 f"visits={n['visit_count']}\n    {n['description']}")
        if n.get("parameters"):
            block += "\n    params: " + json.dumps(n["parameters"], ensure_ascii=False)
        blocks.append(block)
    return "\n".join(blocks)


def parse_json(raw, option):
    """Parse a JSON option; a value that starts with ``@`` names a file with the JSON.

    :param raw: the option value, or ``None``.
    :param option: the option name, for error messages.
    :returns: the parsed value, or ``None`` when the option is empty.
    :raises GraphError: when the text is not valid JSON.
    """
    if not raw:
        return None
    if raw.startswith("@"):
        with open(raw[1:], encoding="utf-8") as f:
            raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise GraphError(f"--{option} is not valid JSON: {e}") from e


def split_names(raw):
    """Split a comma list of node names.

    :param raw: the option value, or ``None``.
    :returns: the non-empty names.
    """
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def build_report(a, nodes):
    """Check a run report and build the ``commit_evolutionary_turn`` arguments.

    :param a: the parsed ``report`` options.
    :param nodes: the domain nodes from :func:`retrieve`, to resolve node names to ids.
    :returns: the RPC body.
    :raises GraphError: when the report breaks a rule of the graph.
    """
    if not 0.0 <= a.score <= 1.0:
        raise GraphError("--score must be between 0 and 1")
    incident = parse_json(a.incident, "incident")
    if not isinstance(incident, dict):
        raise GraphError("--incident must be a JSON object")
    missing = [f for f in INCIDENT_FIELDS if not incident.get(f)]
    if missing:
        raise GraphError("--incident misses " + ", ".join(missing))
    telemetry = {"incident": incident, "score_source": a.score_source, "client": "procgraph-cursor/1"}
    if a.score_source == "mechanical" and not a.verified_scope:
        raise GraphError("a mechanical score needs --verified-scope K/N, for example passed/total tests")
    if a.verified_scope:
        m = re.fullmatch(r"(\d+)/(\d+)", a.verified_scope)
        if not m or int(m[1]) > int(m[2]) or int(m[2]) == 0:
            raise GraphError("--verified-scope must be K/N with 0 <= K <= N and N > 0")
        if a.score > int(m[1]) / int(m[2]) + 1e-9:
            raise GraphError(f"--score {a.score} is above the verified scope {a.verified_scope}")
        telemetry["verified_scope"] = {"k": int(m[1]), "n": int(m[2])}
    for option, allowed in (("node", "PARAMETER_MUTATION"), ("edge", "WEIGHT_MUTATION"),
                            ("new_node_name", "STRUCTURAL_MUTATION CROSSOVER"), ("parents", "CROSSOVER")):
        if getattr(a, option) and a.mutation not in allowed.split():
            raise GraphError(f"--{option.replace('_', '-')} needs --mutation {' or '.join(allowed.split())}")
    if a.mutation != "NO_STRUCTURAL_CHANGE" and not a.rationale:
        raise GraphError(f"{a.mutation} needs --rationale: hypothesis, metric, baseline and threshold")
    ids = {n["node_name"]: n["node_id"] for n in nodes}
    used, parents = split_names(a.used), split_names(a.parents)
    unknown = [n for n in used + parents if n not in ids]
    if unknown:
        raise GraphError(f"not nodes of '{a.domain}': {', '.join(unknown)}")
    payload = {"rationale": a.rationale or "Run recorded; no structural change."}
    new_node = {"node_type": a.new_node_type, "name": a.new_node_name, "description": a.new_node_desc,
                "method": "cursor-incident", "parameters": parse_json(a.new_node_params, "new-node-params") or {}}
    if a.mutation == "PARAMETER_MUTATION":
        if not (a.node and a.param and a.value):
            raise GraphError("PARAMETER_MUTATION needs --node, --param and --value")
        payload.update(target_node_name=a.node, parameter=a.param, new_value=parse_json(a.value, "value"))
    elif a.mutation == "WEIGHT_MUTATION":
        src, _, dst = (a.edge or "").partition(":")
        if src not in ids or dst not in ids or a.weight is None:
            raise GraphError("WEIGHT_MUTATION needs --edge SRC:DST between nodes of the domain and --weight")
        payload.update(source_node_id=ids[src], target_node_id=ids[dst], new_weight=a.weight)
    elif a.mutation in ("STRUCTURAL_MUTATION", "CROSSOVER"):
        if not (a.new_node_name and a.new_node_type and a.new_node_desc):
            raise GraphError(f"{a.mutation} needs --new-node-name, --new-node-type and --new-node-desc")
        if a.mutation == "STRUCTURAL_MUTATION":
            payload["new_node"] = new_node
        elif len(parents) < 2:
            raise GraphError("CROSSOVER needs --parents A,B")
        else:
            # The RPC logs CROSSOVER without applying it; the proposal stays in telemetry for the curator.
            payload.update(parents=parents, new_child=new_node)
            telemetry["proposal"] = {"parents": parents, "new_child": new_node}
    for name, value in (("task", a.task), ("rationale", a.rationale), ("telemetry", telemetry), ("payload", payload)):
        if SECRET_RE.search(json.dumps(value)):
            raise GraphError(f"refused: the {name} looks like it holds a secret")
    return {"p_agent": os.environ.get("PGRAPH_AGENT", "cursor-automation"), "p_domain": a.domain,
            "p_task": a.task, "p_retrieved_nodes": [ids[n] for n in used], "p_telemetry": telemetry,
            "p_outcome": a.outcome, "p_eval_score": a.score, "p_mutation_type": a.mutation,
            "p_mutation_payload": payload}


def stop_hook_answer(event, reported, configured):
    """Answer Cursor's ``stop`` hook: ask once for the graph report when this run has none.

    :param event: the hook input, with ``status`` and ``loop_count``.
    :param reported: whether this run already recorded its episode.
    :param configured: whether the graph secrets are set; sessions without them stay quiet.
    :returns: the hook output; a ``followup_message`` gives the agent one more turn.
    """
    if reported or not configured or event.get("loop_count", 0) > 0 or event.get("status") == "aborted":
        return {}
    return {"followup_message": "Before you finish, record this run in the procedural graph with "
                                "`python3 tools/procgraph.py report ...` (step 5 of the automation prompt)."}


def main(argv=None):
    """Run the command line.

    :param argv: the arguments without the program name; ``None`` means ``sys.argv[1:]``.
    :returns: the process exit code.
    """
    p = argparse.ArgumentParser(description="Procedural-graph client for Cursor cloud agents.")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("retrieve", help="print the procedures of a domain")
    r.add_argument("--domain", required=True)
    r.add_argument("--k", type=int, default=12)
    c = sub.add_parser("report", help="record this run as one incident episode with at most one mutation")
    c.add_argument("--domain", required=True)
    c.add_argument("--task", required=True, help="one line: the bug ID and what happened")
    c.add_argument("--outcome", required=True, choices=("success", "failure", "neutral"))
    c.add_argument("--score", required=True, type=float)
    c.add_argument("--score-source", default="self", choices=SCORE_SOURCES)
    c.add_argument("--verified-scope", help="K/N units that passed a mechanical check, e.g. 7/7 tests")
    c.add_argument("--incident", required=True, help="JSON object or @file with " + ", ".join(INCIDENT_FIELDS))
    c.add_argument("--used", help="comma list of the node names you applied")
    c.add_argument("--mutation", default="NO_STRUCTURAL_CHANGE", choices=MUTATIONS)
    c.add_argument("--weight", type=float)
    for option in ("--rationale", "--node", "--param", "--value", "--edge", "--parents",
                   "--new-node-name", "--new-node-type", "--new-node-desc", "--new-node-params"):
        c.add_argument(option)
    c.add_argument("--dry-run", action="store_true", help="print the RPC body and send nothing")
    sub.add_parser("stop-hook", help="Cursor stop hook: ask once for the report when this run has none")
    a = p.parse_args(argv)
    try:
        if a.cmd == "retrieve":
            print(format_nodes(retrieve(a.domain, a.k)))
            return 0
        if a.cmd == "stop-hook":
            event = json.loads(sys.stdin.read() or "{}")
            configured = bool(os.environ.get("PGRAPH_SUPABASE_URL"))
            print(json.dumps(stop_hook_answer(event, os.path.exists(MARKER), configured)))
            return 0
        if os.path.exists(MARKER) and not a.dry_run:
            raise GraphError(f"this run already recorded its episode ({MARKER}); one run, one episode")
        body = build_report(a, retrieve(a.domain, 200))
        if a.dry_run:
            print(json.dumps(body, indent=2, ensure_ascii=False))
            return 0
        res = rpc("commit_evolutionary_turn", body)
        with open(MARKER, "w", encoding="utf-8") as f:
            json.dump(res, f)
        print(f"episode {res['episode_id']}  mutation {res['mutation_id']}  "
              f"effect={res['effect']}  status={res['promotion_status']}")
        return 0
    except GraphError as e:
        print(f"procgraph: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
