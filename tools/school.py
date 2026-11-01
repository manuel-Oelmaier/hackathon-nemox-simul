#!/usr/bin/env python3
"""Draw a procedural-graph domain as a school of fish in one SVG image.

Each node is a fish on a radial tree around the domain's red leader fish. The first edge into a
node makes the node a child of the edge's source: a child swims one ring further out, and the
leaves share the outer ring. Color is the node type, length grows with visits, and the gold glow
is fitness. Edges are curved currents. A card plots the episodes in time order with the best
score so far, as the performance panel of the AI-Scientist-v3 run inspector does. The
publishable key reads nodes only; a key that may read the tables adds edges and episodes.
"""

from __future__ import annotations

import argparse
import html
import math
import sys
from collections import Counter
from itertools import accumulate
from typing import NamedTuple

import procgraph

WIDTH, HEIGHT = 1800, 1200
CX, CY = 1200, 600
HUB_RADIUS, LEAF_RADIUS = 110, 340
# The (dark, light) ends of each fish gradient. "hub" is the leader fish at the center.
PALETTE = {"procedure": ("#2563eb", "#93c5fd"), "failure": ("#ef4444", "#fdba74"), "suite": ("#f59e0b", "#fde68a"),
           "test": ("#0d9488", "#5eead4"), "other": ("#db2777", "#f9a8d4"), "hub": ("#dc2626", "#fb7185")}
CURRENTS = {"transitions_to": "#4f46e5", "checked_by": "#f97316", "verified_by": "#0d9488", "contains": "#eab308"}
AGENT_COLORS = ("#f97316", "#2563eb", "#0d9488", "#db2777", "#7c3aed")
STATIC = """<style>
text { font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", "DejaVu Sans", sans-serif; fill: #1e293b; }
.leaf { font-size: 13px; }
.inner { font-size: 14px; font-weight: 700; fill: #1e1b4b; paint-order: stroke; stroke: #fff; stroke-width: 4px; }
.eyebrow { font-size: 14px; font-weight: 700; letter-spacing: .22em; fill: #f97316; }
.title { font: 700 60px Georgia, "DejaVu Serif", serif; fill: #1e1b4b; }
.sub { font-size: 19px; fill: #475569; }
.key { font-size: 16px; }
.note { font-size: 13px; fill: #64748b; }
</style>
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff7ed"/>
<stop offset=".55" stop-color="#ecfeff"/><stop offset="1" stop-color="#a5f3fc"/></linearGradient>
<radialGradient id="sun"><stop offset="0" stop-color="#fb7185" stop-opacity=".5"/>
<stop offset="1" stop-color="#fb7185" stop-opacity="0"/></radialGradient>
<radialGradient id="pool"><stop offset=".55" stop-color="#fff" stop-opacity=".8"/>
<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<radialGradient id="glow"><stop offset="0" stop-color="#facc15" stop-opacity=".9"/>
<stop offset="1" stop-color="#facc15" stop-opacity="0"/></radialGradient>
<linearGradient id="gold" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#facc15" stop-opacity=".45"/>
<stop offset="1" stop-color="#facc15" stop-opacity="0"/></linearGradient>
<g id="fish"><path d="M.5 0C.42-.22-.05-.26-.28-.03L-.5-.2-.42 0-.5.2-.28.03C-.05.26.42.22.5 0Z"/>
<path d="M.07-.18L-.07-.3-.12-.13Z" opacity=".8"/>
<path d="M.32-.1C.18-.16 0-.15-.14-.09" fill="none" stroke="#fff" stroke-opacity=".75" stroke-width=".035"/>
<circle cx=".3" cy="-.05" r=".045" fill="#fff"/><circle cx=".31" cy="-.05" r=".022" fill="#1e1b4b"/></g>
</defs>"""


class Spot(NamedTuple):
    """Where one node swims: its point, its angle from the center in radians, its tree depth, and if it is a leaf."""

    x: float
    y: float
    angle: float
    depth: int
    leaf: bool


def load(domain):
    """Read the nodes of one domain, and its edges and episodes when the key may read the tables.

    :param domain: the graph domain, for example ``bug_triage``.
    :returns: ``(nodes, edges, episodes)``. Edges and episodes are empty for the publishable key.
    :raises procgraph.GraphError: when the nodes cannot be read.
    """
    nodes = procgraph.retrieve(domain, 500)
    try:
        edges = procgraph.select("procedural_edges", {"select": "source_node_id,target_node_id,relation_type",
                                                      "is_active": "eq.true", "domain": f"eq.{domain}"})
        episodes = procgraph.select("episodes", {"select": "agent_id,evaluation_score", "domain": f"eq.{domain}",
                                                 "order": "created_at"})
    except procgraph.GraphError:
        return nodes, [], []
    return nodes, edges, episodes


def _reaches(top, node, parent):
    """Tell whether ``top`` is ``node`` or one of its ancestors, so that a new link would close a loop.

    :param top: the node that would become a child.
    :param node: the node that would become its parent.
    :param parent: the parent links chosen so far.
    :returns: ``True`` when the link must be skipped.
    """
    while node is not None:
        if node == top:
            return True
        node = parent.get(node)
    return False


def layout(nodes, edges):
    """Place the nodes on a radial tree around the center.

    :param nodes: node rows with ``node_id`` and ``node_name``.
    :param edges: edge rows with ``source_node_id`` and ``target_node_id``.
    :returns: a :class:`Spot` for each node id.
    """
    ids = [n["node_id"] for n in sorted(nodes, key=lambda n: n["node_name"])]
    rank = {i: k for k, i in enumerate(ids)}
    children, parent = {i: [] for i in ids}, {}
    for e in edges:
        source, target = e["source_node_id"], e["target_node_id"]
        if source in rank and target in rank and target not in parent and not _reaches(target, source, parent):
            parent[target] = source
            children[source].append(target)
    order, depth, slots = [], {}, []

    def walk(i, d):
        order.append(i)
        depth[i] = d
        if not children[i]:
            slots.append(i)
        for child in sorted(children[i], key=rank.get):
            walk(child, d + 1)

    for root in (i for i in ids if i not in parent):
        walk(root, 0)
        slots.append(None)  # an empty slot keeps neighbouring trees apart
    angle = {i: 2 * math.pi * k / len(slots) - math.pi / 2 for k, i in enumerate(slots) if i is not None}
    for i in reversed(order):
        if children[i]:
            angle[i] = sum(angle[c] for c in children[i]) / len(children[i])
    ring = (LEAF_RADIUS - HUB_RADIUS) / (max(depth.values(), default=0) + 1)
    spots = {}
    for i in order:
        leaf = not children[i]
        r = LEAF_RADIUS if leaf else HUB_RADIUS + ring * (depth[i] + 1)
        spots[i] = Spot(CX + r * math.cos(angle[i]), CY + r * math.sin(angle[i]), angle[i], depth[i], leaf)
    return spots


def _label(name, limit=30):
    """Turn a node name into a short label: no ``test_`` prefix, spaces for underscores, cut at ``limit``.

    :param name: the node name.
    :param limit: the longest label, in characters.
    :returns: the escaped label.
    """
    text = name.removeprefix("test_").replace("_", " ")
    return html.escape(text if len(text) <= limit else text[: limit - 1] + "…")


def _fish(x, y, heading, length, kind, glow=0.0):
    """Draw one fish that swims toward ``heading``, over a gold glow.

    :param x: the x of the fish center.
    :param y: the y of the fish center.
    :param heading: the swim direction in radians.
    :param length: the fish length in pixels.
    :param kind: the :data:`PALETTE` entry for the fill.
    :param glow: the opacity of the glow, from 0 to 1.
    :returns: SVG elements.
    """
    halo = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{length * .85:.1f}" fill="url(#glow)" opacity="{glow:.2f}"/>'
            if glow else "")
    return (halo + f'<use href="#fish" fill="url(#fill-{kind})" '
            f'transform="translate({x:.1f} {y:.1f}) rotate({math.degrees(heading):.1f}) scale({length:.1f})"/>')


def _current(a, b, color):
    """Draw an edge as a current that bends like a radial tree link.

    :param a: the source spot.
    :param b: the target spot.
    :param color: the stroke color.
    :returns: one SVG path.
    """
    mid = (math.hypot(a.x - CX, a.y - CY) + math.hypot(b.x - CX, b.y - CY)) / 2
    c1 = (CX + mid * math.cos(a.angle), CY + mid * math.sin(a.angle))
    c2 = (CX + mid * math.cos(b.angle), CY + mid * math.sin(b.angle))
    return (f'<path d="M{a.x:.1f} {a.y:.1f}C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {b.x:.1f} {b.y:.1f}" '
            f'stroke="{color}"/>')


def _leaf_label(spot, name):
    """Write a leaf's label along its radius, outside the outer ring, and never upside down.

    :param spot: the leaf's spot.
    :param name: the node name.
    :returns: one SVG text element.
    """
    flip = math.cos(spot.angle) < 0
    x, y = CX + (LEAF_RADIUS + 34) * math.cos(spot.angle), CY + (LEAF_RADIUS + 34) * math.sin(spot.angle)
    turn = math.degrees(spot.angle) + (180 if flip else 0)
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="leaf" dominant-baseline="middle" '
            f'text-anchor="{"end" if flip else "start"}" transform="rotate({turn:.1f} {x:.1f} {y:.1f})">'
            f'{_label(name)}</text>')


def _waves():
    """Draw three waves and rising bubbles along the bottom. The pattern is fixed, so every run draws the same.

    :returns: SVG elements.
    """
    parts = []
    for k, (fill, opacity) in enumerate((("#fff", .55), ("#67e8f9", .3), ("#22d3ee", .25))):
        y, swell = HEIGHT - 190 + 55 * k, 40 if k % 2 else -40
        parts.append(f'<path d="M0 {y}C300 {y + swell} 600 {y - swell} 900 {y}S1500 {y + swell} {WIDTH} {y}'
                     f'V{HEIGHT}H0Z" fill="{fill}" opacity="{opacity}"/>')
    for k in range(1, 30):
        x, y = k * 0.618034 % 1 * WIDTH, HEIGHT - 30 - k * 0.381966 % 1 * 380
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{2 + k % 5}" fill="none" stroke="#fff" stroke-width="1.5"/>')
    return "".join(parts)


def _legend(nodes, edges, top):
    """List the node types with their counts, then the edge relations, each with its color.

    :param nodes: the node rows.
    :param edges: the drawn edge rows.
    :param top: the y of the first line.
    :returns: SVG elements.
    """
    parts, y = [], top
    for kind, count in Counter(n["node_type"] for n in nodes).most_common():
        parts.append(_fish(88, y, 0, 42, kind if kind in PALETTE else "other")
                     + f'<text x="122" y="{y + 6}" class="key">{html.escape(kind)} · {count}</text>')
        y += 42
    for relation in sorted({e["relation_type"] for e in edges}):
        parts.append(f'<path d="M68 {y}H108" stroke="{CURRENTS.get(relation, "#64748b")}" stroke-width="4" '
                     f'stroke-linecap="round"/><text x="122" y="{y + 6}" class="key">{html.escape(relation)}</text>')
        y += 34
    parts.append(f'<text x="66" y="{y + 16}" class="note">fish length = visits · gold glow = fitness</text>')
    return "".join(parts)


def _episodes(episodes, x, y, w, h):
    """Plot each episode's score in time order, with the gold line of the best score so far.

    :param episodes: rows with ``agent_id`` and ``evaluation_score``, oldest first.
    :param x: the left edge of the plot.
    :param y: the top edge of the plot.
    :param w: the plot width.
    :param h: the plot height.
    :returns: SVG elements.
    """
    if not episodes:
        return f'<text x="{x}" y="{y + h / 2:.0f}" class="note">No episode rows: this key reads nodes only.</text>'
    scores = [float(e["evaluation_score"] or 0) for e in episodes]
    color = {a: AGENT_COLORS[k % len(AGENT_COLORS)] for k, a in enumerate(sorted({e["agent_id"] for e in episodes}))}
    step = w / max(len(scores) - 1, 1)
    best = " ".join(f"{x + k * step:.1f},{y + h * (1 - s):.1f}" for k, s in enumerate(accumulate(scores, max)))
    parts = [f'<path d="M{x} {y + h}H{x + w}" stroke="#94a3b8"/>',
             f'<text x="{x - 10}" y="{y + 5}" class="note" text-anchor="end">1</text>',
             f'<text x="{x - 10}" y="{y + h + 4}" class="note" text-anchor="end">0</text>',
             f'<polygon points="{x},{y + h} {best} {x + w},{y + h}" fill="url(#gold)"/>',
             f'<polyline points="{best}" fill="none" stroke="#eab308" stroke-width="3" stroke-linejoin="round"/>']
    parts += [f'<circle cx="{x + k * step:.1f}" cy="{y + h * (1 - s):.1f}" r="5.5" fill="{color[e["agent_id"]]}" '
              f'stroke="#fff" stroke-width="1.5"/>' for k, (s, e) in enumerate(zip(scores, episodes))]
    for k, (agent, fill) in enumerate(color.items()):
        ax, ay = x + 220 * (k % 2), y + h + 36 + 24 * (k // 2)
        parts.append(f'<circle cx="{ax + 6}" cy="{ay - 4}" r="5.5" fill="{fill}"/>'
                     f'<text x="{ax + 18}" y="{ay}" class="note">{html.escape(agent)}</text>')
    return "".join(parts)


def render(domain, nodes, edges, episodes):
    """Draw one domain as an SVG document.

    :param domain: the domain name, for the title and the leader fish.
    :param nodes: node rows from :func:`load`.
    :param edges: edge rows from :func:`load`.
    :param episodes: episode rows from :func:`load`, oldest first.
    :returns: the SVG text.
    """
    spots = layout(nodes, edges)
    edges = [e for e in edges if e["source_node_id"] in spots and e["target_node_id"] in spots]
    gradients = "".join(f'<linearGradient id="fill-{kind}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" '
                        f'stop-color="{light}"/><stop offset="1" stop-color="{dark}"/></linearGradient>'
                        for kind, (dark, light) in PALETTE.items())
    rings = sorted({round(math.hypot(s.x - CX, s.y - CY)) for s in spots.values()})
    hub = Spot(CX, CY, 0.0, -1, False)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
           STATIC, f"<defs>{gradients}</defs>", f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#sky)"/>',
           f'<circle cx="{WIDTH - 150}" cy="130" r="300" fill="url(#sun)"/>',
           f'<circle cx="{CX}" cy="{CY}" r="620" fill="url(#pool)"/>', _waves()]
    out += [f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="#38bdf8" stroke-opacity=".45" '
            f'stroke-dasharray="2 9"/>' for r in rings]
    out.append('<g fill="none" stroke-width="2" stroke-dasharray="1 7" stroke-linecap="round">')
    out += [_current(hub._replace(angle=s.angle), s, "#94a3b8") for s in spots.values() if s.depth == 0]
    out.append('</g><g fill="none" stroke-width="2.6" stroke-opacity=".7" stroke-linecap="round">')
    out += [_current(spots[e["source_node_id"]], spots[e["target_node_id"]], CURRENTS.get(e["relation_type"], "#64748b"))
            for e in edges]
    out.append("</g>")
    for n in nodes:
        s = spots[n["node_id"]]
        kind = n["node_type"] if n["node_type"] in PALETTE else "other"
        title = html.escape(f"{n['node_name']} [{n['node_type']}] fitness {n['fitness_score']:.2f}, "
                            f"visits {n['visit_count']}\n{n['description']}")
        length = 40 + 12 * math.log1p(n["visit_count"])
        out.append(f"<g><title>{title}</title>{_fish(s.x, s.y, s.angle + math.pi / 2, length, kind, n['fitness_score'])}"
                   "</g>")
        out.append(_leaf_label(s, n["node_name"]) if s.leaf else
                   f'<text x="{s.x:.1f}" y="{s.y + length / 2 + 16:.1f}" class="inner" text-anchor="middle">'
                   f'{_label(n["node_name"])}</text>')
    visits = sum(n["visit_count"] for n in nodes)
    out += [_fish(CX, CY, 0.0, 120, "hub", 1.0),
            f'<text x="{CX}" y="{CY + 56}" class="inner" text-anchor="middle">{html.escape(domain)}</text>',
            '<text x="64" y="96" class="eyebrow">PROCEDURAL MEMORY · SCHOOL OF FISH</text>',
            f'<text x="60" y="166" class="title">{html.escape(domain)}</text>',
            f'<text x="64" y="208" class="sub">{len(nodes)} nodes · {len(edges)} edges · {len(episodes)} episodes · '
            f'{visits} visits</text>', _legend(nodes, edges, 280),
            '<rect x="40" y="860" width="540" height="300" rx="24" fill="#fff" fill-opacity=".86" stroke="#bae6fd"/>',
            '<text x="70" y="904" class="key" font-weight="700">Episodes, oldest first</text>',
            '<text x="70" y="928" class="note">dot = one run, colored by agent · gold line = best score so far</text>',
            _episodes(episodes, 96, 952, 450, 110), "</svg>"]
    return "\n".join(out)


def main(argv=None):
    """Load one domain and write its school as SVG.

    :param argv: the command-line arguments; ``None`` reads ``sys.argv``.
    :returns: the exit code.
    """
    parser = argparse.ArgumentParser(description="Draw a procedural-graph domain as a school of fish (SVG).")
    parser.add_argument("--domain", default="bug_triage")
    parser.add_argument("--out", default="-", help="the SVG file to write; - writes to stdout")
    args = parser.parse_args(argv)
    try:
        svg = render(args.domain, *load(args.domain))
    except procgraph.GraphError as e:
        print(f"school: {e}", file=sys.stderr)
        return 1
    if args.out == "-":
        sys.stdout.write(svg)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(svg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
