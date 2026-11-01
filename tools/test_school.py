"""Tests for the fish-school drawing. Run: ``python3 -m unittest discover -s tools``."""

import math
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

import procgraph
import school

SVG = "{http://www.w3.org/2000/svg}"


def node(name, kind="procedure"):
    """Build one node row.

    :param name: the node name; the id is derived from it.
    :param kind: the node type.
    :returns: a node dict.
    """
    return {"node_id": "id-" + name, "node_name": name, "node_type": kind, "description": name + " does the work.",
            "fitness_score": 0.5, "visit_count": 1}


def edge(source, target):
    """Build one edge row between two node names.

    :param source: the source node name.
    :param target: the target node name.
    :returns: an edge dict.
    """
    return {"source_node_id": "id-" + source, "target_node_id": "id-" + target, "relation_type": "transitions_to"}


def radius(spot):
    """Return how far a placed node is from the center.

    :param spot: a :class:`school.Spot`.
    :returns: the distance in pixels.
    """
    return math.hypot(spot.x - school.CX, spot.y - school.CY)


class LayoutTest(unittest.TestCase):
    """The radial tree."""

    def test_children_swim_further_out_and_leaves_share_the_outer_ring(self):
        """A chain a -> b -> c steps outward, and its leaf c sits on the same ring as the lone node d."""
        spots = school.layout([node("a"), node("b"), node("c"), node("d")], [edge("a", "b"), edge("b", "c")])
        self.assertLess(radius(spots["id-a"]), radius(spots["id-b"]))
        self.assertLess(radius(spots["id-b"]), radius(spots["id-c"]))
        self.assertAlmostEqual(radius(spots["id-c"]), school.LEAF_RADIUS)
        self.assertAlmostEqual(radius(spots["id-d"]), school.LEAF_RADIUS)

    def test_a_loop_of_edges_still_places_every_node(self):
        """Edges a -> b -> a and a self-loop cannot make a node its own ancestor: a stays the root."""
        spots = school.layout([node("a"), node("b")], [edge("a", "b"), edge("b", "a"), edge("a", "a")])
        self.assertEqual({i: s.depth for i, s in spots.items()}, {"id-a": 0, "id-b": 1})


class RenderTest(unittest.TestCase):
    """The SVG document."""

    def test_a_hostile_name_stays_text_and_the_image_is_valid_xml(self):
        """Markup in a node name is escaped in the label and the hover text, so the SVG still parses."""
        svg = school.render("bug_triage", [node("x<script>&y")], [], [])
        ET.fromstring(svg)
        self.assertNotIn("<script>", svg)

    def test_gold_line_is_the_best_score_so_far(self):
        """Scores 0.5, 1.0, 0.2 put the gold line at 0.5, 1.0, 1.0: it never drops."""
        episodes = [{"agent_id": "cursor", "evaluation_score": s} for s in (0.5, 1.0, 0.2)]
        root = ET.fromstring(school.render("bug_triage", [node("a")], [], episodes))
        heights = [float(p.split(",")[1]) for p in root.find(f".//{SVG}polyline").get("points").split()]
        self.assertLess(heights[1], heights[0])
        self.assertEqual(heights[1], heights[2])


class LoadTest(unittest.TestCase):
    """Reading the graph."""

    def test_publishable_key_draws_nodes_without_edges_or_episodes(self):
        """When the key may not read the tables, the nodes still load and edges and episodes stay empty."""
        with mock.patch.object(procgraph, "retrieve", return_value=[node("a")]), \
                mock.patch.object(procgraph, "select", side_effect=procgraph.GraphError("HTTP 401")):
            self.assertEqual(school.load("bug_triage"), ([node("a")], [], []))


if __name__ == "__main__":
    unittest.main()
