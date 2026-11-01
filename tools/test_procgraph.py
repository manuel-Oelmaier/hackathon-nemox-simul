"""Tests for the Cursor procedural-graph client. Run: ``python3 -m unittest discover -s tools``."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import procgraph

NODES = [{"node_name": "lookup_evidence_by_report_id", "node_id": "n1"},
         {"node_name": "failing_test_before_fix", "node_id": "n2"}]
INCIDENT = {"bug_id": "BUG-01", "summary": "Air quote ignores volume weight.", "evidence": ["span 1"],
            "root_cause": "Chargeable weight uses actual kg only.", "fix": "quoting/air_weight.py"}
NEW_NODE = {"new_node_name": "chargeable_weight_rule", "new_node_type": "procedure",
            "new_node_desc": "Rate air freight on the higher of actual and volume weight.",
            "rationale": "hypothesis; metric; baseline; threshold"}


def report(**options):
    """Return valid ``report`` options, changed by ``options``.

    :param options: option values that replace the defaults.
    :returns: an object with the attributes of the parsed options.
    """
    a = {"domain": "bug_triage", "task": "BUG-01: air quote ignores volume weight", "outcome": "success",
         "score": 0.75, "score_source": "mechanical", "verified_scope": "3/4", "incident": json.dumps(INCIDENT),
         "used": "lookup_evidence_by_report_id", "mutation": "NO_STRUCTURAL_CHANGE", "rationale": None,
         "node": None, "param": None, "value": None, "edge": None, "weight": None, "parents": None,
         "new_node_name": None, "new_node_type": None, "new_node_desc": None, "new_node_params": None}
    a.update(options)
    return SimpleNamespace(**a)


class BuildReportTest(unittest.TestCase):
    """The report checks and the RPC body."""

    def test_structural_report_matches_the_rpc_contract(self):
        """A new node goes to the RPC in the payload shape that ``pgraph`` uses, with resolved node ids."""
        body = procgraph.build_report(report(mutation="STRUCTURAL_MUTATION", **NEW_NODE), NODES)
        self.assertEqual(set(body), {"p_agent", "p_domain", "p_task", "p_retrieved_nodes", "p_telemetry",
                                     "p_outcome", "p_eval_score", "p_mutation_type", "p_mutation_payload"})
        self.assertEqual(body["p_retrieved_nodes"], ["n1"])
        self.assertEqual(body["p_mutation_payload"]["new_node"]["name"], "chargeable_weight_rule")
        self.assertEqual(body["p_telemetry"]["incident"], INCIDENT)
        self.assertEqual(body["p_telemetry"]["verified_scope"], {"k": 3, "n": 4})

    def test_crossover_keeps_the_proposal_for_the_curator(self):
        """The RPC logs CROSSOVER without applying it, so the parents and the child go into telemetry."""
        parents = "lookup_evidence_by_report_id,failing_test_before_fix"
        body = procgraph.build_report(report(mutation="CROSSOVER", parents=parents, **NEW_NODE), NODES)
        proposal = body["p_telemetry"]["proposal"]
        self.assertEqual(proposal["parents"], parents.split(","))
        self.assertEqual(proposal["new_child"]["name"], "chargeable_weight_rule")

    def test_reports_that_break_a_rule_are_refused(self):
        """Each broken rule raises GraphError before anything is sent."""
        fake_key = "sk-" + "x" * 24  # built at run time, so secret scanners do not flag this file
        cases = {
            "secret in the incident": report(incident=json.dumps({**INCIDENT, "evidence": fake_key})),
            "incident without root cause": report(incident=json.dumps({**INCIDENT, "root_cause": ""})),
            "score above the verified scope": report(score=0.8),
            "mechanical score without scope": report(verified_scope=None),
            "unknown node in --used": report(used="no_such_node"),
            "mutation without rationale": report(mutation="PARAMETER_MUTATION", node="failing_test_before_fix",
                                                 param="k", value="1"),
            "new node without a structural mutation": report(**NEW_NODE),
        }
        for name, options in cases.items():
            with self.subTest(name), self.assertRaises(procgraph.GraphError):
                procgraph.build_report(options, NODES)


class RpcTest(unittest.TestCase):
    """The HTTP call to PostgREST."""

    def test_bearer_header_only_for_jwt_keys(self):
        """New sb_ keys go in apikey only; legacy JWT keys also go in Authorization."""
        for key, bearer in (("sb_publishable_example", False), ("eyJexample.payload.signature", True)):
            env = {"PGRAPH_SUPABASE_URL": "https://example.supabase.co", "PGRAPH_SUPABASE_KEY": key}
            with self.subTest(key=key), mock.patch.dict(os.environ, env), \
                    mock.patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = b"[]"
                self.assertEqual(procgraph.rpc("retrieve_subgraph", {}), [])
                request = urlopen.call_args.args[0]
                self.assertEqual(request.get_header("Apikey"), key)
                self.assertEqual(request.has_header("Authorization"), bearer)


class MainTest(unittest.TestCase):
    """The command line."""

    def test_second_report_in_one_run_is_refused(self):
        """One run records one episode: a report after a recorded one stops before any call."""
        err = io.StringIO()
        with tempfile.NamedTemporaryFile() as marker, mock.patch.object(procgraph, "MARKER", marker.name), \
                mock.patch.object(procgraph, "rpc") as rpc, contextlib.redirect_stderr(err):
            code = procgraph.main(["report", "--domain", "bug_triage", "--task", "t", "--outcome", "neutral",
                                   "--score", "0.5", "--incident", json.dumps(INCIDENT)])
        self.assertEqual(code, 1)
        self.assertIn("one run, one episode", err.getvalue())
        rpc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
