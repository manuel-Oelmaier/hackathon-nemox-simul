"""Tests for the procedural-graph memory map. Run: ``python3 -m unittest discover -s tools``."""

import contextlib
import io
import os
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone
from unittest import mock

import fish

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def node(name, **fields):
    """Build one graph row.

    :param name: the node name.
    :param fields: extra columns.
    :returns: a node dict.
    """
    row = {"node_id": "id-" + name, "node_name": name, "node_type": "procedure", "description": name + " does the work.",
           "parameters": {"when_not_to_use": "elsewhere"}, "fitness_score": 0.5, "visit_count": 1}
    row.update(fields)
    return row


class ViewModelTest(unittest.TestCase):
    """Placement, fading, and grouping use only the fields the database returns."""

    def test_fitness_pulls_a_node_toward_the_center_and_visits_make_it_larger(self):
        """Without timestamps, a fitter node sits closer in and a busier node is bigger."""
        view = fish.build_view([
            node("rare", fitness_score=0.1, visit_count=0),
            node("busy", fitness_score=1, visit_count=8),
        ], "bug_triage", now=NOW)
        placed = {item["name"]: item for item in view["nodes"]}
        rare_span = abs(placed["rare"]["x"] - fish.CENTER) + abs(placed["rare"]["y"] - fish.CENTER)
        busy_span = abs(placed["busy"]["x"] - fish.CENTER) + abs(placed["busy"]["y"] - fish.CENTER)
        self.assertGreater(rare_span, busy_span)
        self.assertGreater(placed["busy"]["size"], placed["rare"]["size"])
        self.assertTrue(placed["rare"]["faded"])
        self.assertFalse(placed["busy"]["faded"])
        self.assertEqual(view["mode"], "fitness")

    def test_recency_fades_a_node_after_thirty_days(self):
        """A last-used time replaces fitness: recent nodes move inward, stale ones fade."""
        view = fish.build_view([
            node("fresh", last_used="2026-10-31T00:00:00Z", visit_count=2),
            node("stale", last_used="2026-09-01T00:00:00Z", visit_count=9),
        ], "bug_triage", now=NOW)
        placed = {item["name"]: item for item in view["nodes"]}
        fresh_span = abs(placed["fresh"]["x"] - fish.CENTER) + abs(placed["fresh"]["y"] - fish.CENTER)
        stale_span = abs(placed["stale"]["x"] - fish.CENTER) + abs(placed["stale"]["y"] - fish.CENTER)
        self.assertGreater(stale_span, fresh_span)
        self.assertTrue(placed["stale"]["faded"])
        self.assertFalse(placed["fresh"]["faded"])
        self.assertEqual(view["mode"], "recency")
        self.assertEqual(view["history"][0]["name"], "fresh")

    def test_edges_connect_only_known_nodes(self):
        """A co-use line needs both ends. An unknown end and a self-loop are dropped."""
        view = fish.build_view(
            [node("alpha"), node("beta")],
            "bug_triage",
            edges=[{"source": "alpha", "target": "beta"}, {"source": "alpha", "target": "missing"},
                   {"from": "id-alpha", "to": "id-alpha"}],
            now=NOW,
        )
        self.assertEqual(view["links"], [{"source": "node-id-alpha", "target": "node-id-beta"}])

    def test_overview_groups_follow_node_type(self):
        """Procedures and traps are separate groups, which is the category list for this database."""
        view = fish.build_view([
            node("lookup", node_type="procedure"),
            node("trap", node_type="failure", description="Do not edit fixtures."),
        ], "bug_triage", now=NOW)
        self.assertEqual([group["type"] for group in view["groups"]], ["procedure", "failure"])
        view["open"] = "connections"
        view["caption"] = "After the episode"
        page = fish.render_html(view)
        self.assertIn('id="view-connections" checked', page)
        self.assertIn("After the episode", page)
        self.assertIn("memory failure", page)
        trap = view["groups"][1]["nodes"][0]
        self.assertEqual(trap["facts"][0], ("description", "Do not edit fixtures."))


class PageTest(unittest.TestCase):
    """The page shows the database and does not carry the API key."""

    def test_page_lists_every_view_and_escapes_node_text(self):
        """Overview, connections, and history are present, and a hostile name cannot become markup."""
        hostile = '<img src=x onerror=alert(1)>'
        view = fish.build_view([node(hostile, visit_count=3, fitness_score=1)], "bug_triage", now=NOW)
        page = fish.render_html(view)
        self.assertIn("Overview", page)
        self.assertIn("Connections", page)
        self.assertIn("History", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertNotIn(hostile, page)
        marker = "GRAPH-FISH-KEY-MARKER"
        with mock.patch.dict(os.environ, {"PGRAPH_SUPABASE_KEY": marker}):
            self.assertNotIn(marker, fish.render_html(view))
        text = fish.render_text(view)
        self.assertIn("bug_triage", text)
        self.assertIn("visits=3", text)

    def test_server_returns_the_snapshot(self):
        """The local server publishes the page it was given and nothing else."""
        page = fish.render_html(fish.build_view([node("lookup")], "bug_triage", now=NOW))
        server = fish.serve(page, 0)
        port = server.server_address[1]
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
                body = response.read().decode()
            self.assertIn("lookup", body)
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/missing")
            self.assertEqual(caught.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()


class CommandTest(unittest.TestCase):
    """The command prints the text report from the nodes it loads."""

    def test_text_report_uses_the_loaded_domain(self):
        """A successful read prints the domain and does not write a page unless asked."""
        output = io.StringIO()
        with mock.patch.object(fish, "load_nodes", return_value=[node("lookup", visit_count=4)]) as load, \
                contextlib.redirect_stdout(output):
            code = fish.main(["--domain", "bug_triage"])
        self.assertEqual(code, 0)
        load.assert_called_once_with("bug_triage")
        self.assertIn("lookup", output.getvalue())
        self.assertIn("visits=4", output.getvalue())


if __name__ == "__main__":
    unittest.main()
