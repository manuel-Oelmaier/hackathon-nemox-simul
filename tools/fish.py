#!/usr/bin/env python3
"""Show a procedural-graph domain as a memory map.

The layout follows the three views of a memory browser: an activity strip that stays
visible, an overview grouped by kind, a radial map, and a history. Node size is how
often the graph has used the node. When the rows include a last-used time, distance
from the center is recency and a node unused for 30 days fades. The publishable read
API returns fitness and visit counts only, so distance falls back to fitness and a
node fades only when it has never been used. A line is drawn only when the caller
passes an edge; the read API does not return co-use edges or episode rows.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import procgraph

INNER_RADIUS = 110
OUTER_RADIUS = 250
STALE_DAYS = 30
VIEW_SIZE = 720
CENTER = VIEW_SIZE / 2


def load_nodes(domain, limit=200):
    """Read the active nodes of one domain.

    :param domain: the graph domain, for example ``bug_triage``.
    :param limit: the maximum number of nodes to keep.
    :returns: node rows from :func:`procgraph.retrieve`.
    :raises procgraph.GraphError: when the graph cannot be reached.
    """
    return procgraph.retrieve(domain, limit)


def _number(value, default=0.0):
    """Return ``value`` as a float, or ``default`` when it is missing or not numeric.

    :param value: a raw field from a node row.
    :param default: the value to use when conversion fails.
    :returns: the numeric value.
    """
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _moment(value):
    """Parse an ISO-8601 timestamp into an aware datetime.

    :param value: a timestamp string, or anything else.
    :returns: an aware datetime, or ``None`` when ``value`` is not a timestamp.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _last_used(node):
    """Return the newest timestamp stored on a node, if any.

    :param node: one graph row.
    :returns: an aware datetime, or ``None``.
    """
    found = [_moment(node.get(key)) for key in ("last_used", "last_used_at", "updated_at")]
    found = [item for item in found if item is not None]
    return max(found) if found else None


def _facts(node):
    """List the readable facts on a node: its description, then each parameter.

    :param node: one graph row.
    :returns: ``(label, text)`` pairs.
    """
    facts = []
    description = str(node.get("description") or "").strip()
    if description:
        facts.append(("description", description))
    parameters = node.get("parameters") or {}
    if isinstance(parameters, dict):
        for key in sorted(parameters):
            facts.append((str(key), json.dumps(parameters[key], ensure_ascii=False) if not isinstance(parameters[key], str) else parameters[key]))
    return facts


def _anchor(node, index):
    """Build a stable HTML id for a node.

    :param node: one graph row.
    :param index: the node's position, used when the row has no id.
    :returns: an id that is safe inside an HTML attribute.
    """
    raw = str(node.get("node_id") or node.get("node_name") or index)
    safe = re.sub(r"[^A-Za-z0-9_-]", "", raw) or f"n{index}"
    return "node-" + safe


def _edge_ends(edge):
    """Read the two ends of an edge record.

    :param edge: a dict with source/target or from/to.
    :returns: ``(source, target)`` strings, or ``(None, None)``.
    """
    if not isinstance(edge, dict):
        return None, None
    source = edge.get("source", edge.get("from", edge.get("source_node_id")))
    target = edge.get("target", edge.get("to", edge.get("target_node_id")))
    if source is None or target is None:
        return None, None
    return str(source), str(target)


def build_view(nodes, domain, *, edges=None, now=None):
    """Turn graph rows into the memory-map model.

    :param nodes: rows from :func:`load_nodes`.
    :param domain: the domain shown at the center.
    :param edges: optional ``{source, target}`` records. Names and node ids both match.
    :param now: the clock for recency. Defaults to the current UTC time.
    :returns: a JSON-serialisable view model.
    """
    now = now or datetime.now(timezone.utc)
    rows = [dict(node) for node in nodes if isinstance(node, dict)]
    dated = any(_last_used(node) is not None for node in rows)
    prepared = []
    for index, node in enumerate(sorted(rows, key=lambda item: str(item.get("node_name") or ""))):
        visits = max(0, int(_number(node.get("visit_count"), 0)))
        fitness = min(1.0, max(0.0, _number(node.get("fitness_score"), 0)))
        last = _last_used(node)
        if dated:
            days = None if last is None else max(0.0, (now - last).total_seconds() / 86400)
            distance = 1.0 if days is None else min(days / STALE_DAYS, 1.0)
            faded = days is not None and days >= STALE_DAYS
        else:
            days = None
            distance = 1.0 - fitness
            faded = visits == 0
        prepared.append({
            "anchor": _anchor(node, index),
            "id": str(node.get("node_id") or ""),
            "name": str(node.get("node_name") or "untitled"),
            "type": str(node.get("node_type") or "node"),
            "fitness": round(fitness, 4),
            "visits": visits,
            "facts": _facts(node),
            "last_used": last.isoformat() if last else None,
            "days_ago": None if days is None else round(days, 2),
            "distance": distance,
            "faded": faded,
            "size": round(min(64.0, 16.0 + 12.0 * math.log1p(visits)), 2),
        })
    count = max(len(prepared), 1)
    for index, item in enumerate(prepared):
        angle = (2 * math.pi * index / count) - (math.pi / 2)
        radius = INNER_RADIUS + (OUTER_RADIUS - INNER_RADIUS) * item["distance"]
        item["x"] = round(CENTER + radius * math.cos(angle), 2)
        item["y"] = round(CENTER + radius * math.sin(angle), 2)
    by_id = {}
    for item in prepared:
        by_id.setdefault(item["name"], item["anchor"])
        if item["id"]:
            by_id.setdefault(item["id"], item["anchor"])
    seen = set()
    links = []
    for edge in edges or []:
        source, target = _edge_ends(edge)
        if source is None or source not in by_id or target not in by_id or source == target:
            continue
        key = tuple(sorted((by_id[source], by_id[target])))
        if key in seen or key[0] == key[1]:
            continue
        seen.add(key)
        links.append({"source": key[0], "target": key[1]})
    type_order = {"procedure": 0, "failure": 1}
    groups = []
    for kind in sorted({item["type"] for item in prepared}, key=lambda kind: (type_order.get(kind, 2), kind)):
        members = [item for item in prepared if item["type"] == kind]
        members.sort(key=lambda item: (-item["visits"], -item["fitness"], item["name"]))
        groups.append({"type": kind, "nodes": members})
    history = sorted(prepared, key=lambda item: (item["last_used"] is None, item["last_used"] or "", item["name"]), reverse=True)
    peak = max((item["visits"] for item in prepared), default=0)
    return {
        "domain": domain,
        "mode": "recency" if dated else "fitness",
        "node_count": len(prepared),
        "visit_total": sum(item["visits"] for item in prepared),
        "peak_visits": peak,
        "groups": groups,
        "nodes": prepared,
        "links": links,
        "history": history,
        "has_timestamps": dated,
        "has_edges": bool(links),
    }


def _heat(visits, peak):
    """Blend a quiet water color toward amber as visits approach the peak.

    :param visits: the node's visit count.
    :param peak: the highest visit count in the view.
    :returns: a ``#rrggbb`` color.
    """
    share = 0 if peak <= 0 else visits / peak
    start, end = (36, 72, 80), (240, 180, 90)
    channels = tuple(round(start[i] + (end[i] - start[i]) * share) for i in range(3))
    return "#%02x%02x%02x" % channels


def _esc(value):
    """Escape text for HTML.

    :param value: any value.
    :returns: escaped text.
    """
    return html.escape(str(value), quote=True)


def _short(name, limit=22):
    """Shorten a node name for the map and the activity strip.

    :param name: the stored node name.
    :param limit: the maximum length, including the ellipsis.
    :returns: the name with spaces instead of underscores, trimmed when it is long.
    """
    text = str(name).replace("_", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def render_text(view):
    """Render the view as plain text.

    :param view: a model from :func:`build_view`.
    :returns: a short report of every node.
    """
    kinds = ", ".join(f"{len(group['nodes'])} {group['type']}" for group in view["groups"]) or "no nodes"
    lines = [f"{view['domain']}  {view['node_count']} nodes  {kinds}  {view['visit_total']} visits  mode={view['mode']}"]
    for node in view["nodes"]:
        when = node["last_used"] or "no timestamp"
        faded = " faded" if node["faded"] else ""
        lines.append(f"  {node['name']}  {node['type']}  visits={node['visits']}  fitness={node['fitness']:.2f}  {when}{faded}")
    if view["links"]:
        lines.append(f"  {len(view['links'])} edges")
    else:
        lines.append("  no edges in the read result")
    return "\n".join(lines)


def render_html(view):
    """Render the view as one self-contained HTML page.

    :param view: a model from :func:`build_view`.
    :returns: the page.
    """
    if view["mode"] == "recency":
        legend = ("Closer to the center means used more recently. Larger means more visits. "
                  "A faded node has not been used for 30 days.")
    else:
        legend = ("Closer to the center means higher fitness. Larger means more visits. "
                  "A faded node has never been used. This read API does not return last-used times.")
    if view["has_edges"]:
        legend += " Lines join nodes the database links."
    else:
        legend += " No co-use edges were returned, so the map draws none."
    strip = []
    if view["nodes"]:
        for node in view["nodes"]:
            strip.append(
                f'<div class="cell" title="{_esc(node["name"])}" style="background:{_heat(node["visits"], view["peak_visits"])}">'
                f'<span>{node["visits"]}</span><small>{_esc(_short(node["name"]))}</small></div>'
            )
    else:
        strip.append('<p class="empty">This domain has no nodes yet.</p>')
    overview = []
    for group in view["groups"]:
        cards = []
        for node in group["nodes"]:
            facts = "".join(f"<li><strong>{_esc(label)}</strong> {_esc(text)}</li>" for label, text in node["facts"])
            when = _esc(node["last_used"]) if node["last_used"] else "no timestamp"
            faded = '<em class="tag">faded</em>' if node["faded"] else ""
            fitness = _esc(f"{node['fitness']:.2f}")
            fact_count = len(node["facts"])
            css = "card faded" if node["faded"] else "card"
            cards.append(
                f'<article id="{node["anchor"]}" class="{css}">'
                f'<header><h3>{_esc(node["name"])}</h3>{faded}</header>'
                f'<p class="meta">{fact_count} facts · {node["visits"]} visits · fitness {fitness} · {when}</p>'
                f'<ul>{facts}</ul></article>'
            )
        overview.append(f'<section class="group"><h2>{_esc(group["type"])}</h2>{"".join(cards)}</section>')
    if not overview:
        overview.append('<p class="empty">Nothing is stored for this domain.</p>')
    lines = []
    points = {node["anchor"]: node for node in view["nodes"]}
    for link in view["links"]:
        a, b = points[link["source"]], points[link["target"]]
        lines.append(f'<line x1="{a["x"]}" y1="{a["y"]}" x2="{b["x"]}" y2="{b["y"]}" />')
    marks = []
    for node in view["nodes"]:
        kind = node["type"] if node["type"] in ("procedure", "failure") else "other"
        css = f"memory {kind}" + (" faded" if node["faded"] else "")
        label = _esc(_short(node["name"]))
        marks.append(
            f'<a class="{css}" href="#{node["anchor"]}">'
            f'<title>{_esc(node["name"])}</title>'
            f'<circle cx="{node["x"]}" cy="{node["y"]}" r="{node["size"] / 2}" />'
            f'<text x="{node["x"]}" y="{node["y"] + node["size"] / 2 + 16}">{label}</text></a>'
        )
    history = []
    for node in view["history"]:
        when = _esc(node["last_used"]) if node["last_used"] else "no timestamp on this row"
        summary = _esc(node["facts"][0][1]) if node["facts"] else ""
        history.append(
            f'<li><span class="when">{when}</span> <strong>{_esc(node["name"])}</strong> '
            f'<span class="meta">{_esc(node["type"])} · {node["visits"]} visits</span>'
            f'<p>{summary}</p></li>'
        )
    if not history:
        history.append("<li>No reads or writes are visible. Episode rows are not part of the node read API.</li>")
    title = _esc(view["domain"])
    caption = _esc(view.get("caption") or "")
    selected = view.get("open") if view.get("open") in ("overview", "connections", "history") else "overview"
    checked = {name: (" checked" if name == selected else "") for name in ("overview", "connections", "history")}
    subtitle = f"<p class=\"caption\">{caption}</p>" if caption else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Graph fish — {title}</title>
<style>
:root {{ color-scheme: dark; --bg:#102126; --panel:#173239; --ink:#e8f4f2; --muted:#9bb8b4; --line:#2d565e; --amber:#f0b45a; --procedure:#7fd1c3; --failure:#e08b84; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font:16px/1.45 Georgia, "Iowan Old Style", Palatino, serif; color:var(--ink);
  background:radial-gradient(circle at 50% -10%, #1d4650, var(--bg) 58%); }}
header, .strip, .shell {{ width:min(1080px, calc(100% - 32px)); margin:0 auto; }}
header {{ padding:28px 0 8px; }}
.eyebrow {{ margin:0; letter-spacing:.14em; text-transform:uppercase; font:12px/1.2 ui-sans-serif, sans-serif; color:var(--amber); }}
h1 {{ margin:6px 0; font-size:40px; font-weight:500; }}
.caption {{ margin:0 0 8px; font:600 18px/1.3 ui-sans-serif, sans-serif; color:var(--amber); }}
.lede, .legend, .meta, .empty {{ color:var(--muted); }}
.strip {{ display:flex; gap:8px; overflow:auto; padding:8px 0 18px; }}
.cell {{ min-width:92px; min-height:72px; border-radius:12px; padding:8px; display:flex; flex-direction:column; justify-content:space-between; color:#102126; }}
.cell span {{ font:600 18px/1 ui-sans-serif, sans-serif; }}
.cell small {{ font:11px/1.2 ui-sans-serif, sans-serif; }}
.tabs {{ display:flex; gap:8px; margin:8px 0 16px; }}
.tabs label {{ font:14px/1 ui-sans-serif, sans-serif; border:1px solid var(--line); border-radius:999px; padding:8px 14px; cursor:pointer; }}
input[name="view"] {{ position:absolute; opacity:0; pointer-events:none; }}
.panel {{ display:none; }}
#view-overview:checked ~ .tabs label[for="view-overview"],
#view-connections:checked ~ .tabs label[for="view-connections"],
#view-history:checked ~ .tabs label[for="view-history"] {{ background:var(--amber); color:#102126; border-color:var(--amber); }}
#view-overview:checked ~ .overview, #view-connections:checked ~ .connections, #view-history:checked ~ .history {{ display:block; }}
.group {{ margin:0 0 22px; }}
h2, h3 {{ font-weight:500; }}
h2 {{ margin:0 0 10px; text-transform:capitalize; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:16px; padding:14px 16px; margin:0 0 10px; }}
.card.faded {{ opacity:.55; }}
.card header {{ display:flex; justify-content:space-between; align-items:baseline; padding:0; }}
.card h3 {{ margin:0; font-family:ui-sans-serif, sans-serif; font-size:16px; }}
.tag {{ font:12px/1 ui-sans-serif, sans-serif; color:var(--amber); }}
.card ul {{ margin:8px 0 0; padding-left:18px; }}
.map {{ width:100%; height:auto; background:rgba(8, 22, 26, .45); border:1px solid var(--line); border-radius:24px; }}
.memory circle {{ fill:var(--procedure); stroke:#102126; stroke-width:2; }}
.memory.failure circle {{ fill:var(--failure); }}
.memory.other circle {{ fill:#d7d3c2; }}
.memory.faded circle {{ fill:#6f8b86; }}
.memory text {{ fill:var(--ink); font:12px ui-sans-serif, sans-serif; text-anchor:middle; }}
line {{ stroke:var(--amber); stroke-opacity:.8; }}
.fish {{ fill:var(--amber); }}
.history {{ list-style:none; padding:0; }}
.history li {{ border-top:1px solid var(--line); padding:12px 0; }}
.when {{ font:13px/1 ui-sans-serif, sans-serif; color:var(--amber); }}
.legend {{ font:14px/1.4 ui-sans-serif, sans-serif; }}
</style>
</head>
<body>
<header>
<p class="eyebrow">Procedural memory</p>
<h1>{title}</h1>
{subtitle}
<p class="lede">{view["node_count"]} nodes · {view["visit_total"]} visits · distance by {view["mode"]}. Episode rows are not in the node read API.</p>
</header>
<div class="strip" aria-label="Visits per node">{"".join(strip)}</div>
<div class="shell">
<input type="radio" name="view" id="view-overview"{checked["overview"]}>
<input type="radio" name="view" id="view-connections"{checked["connections"]}>
<input type="radio" name="view" id="view-history"{checked["history"]}>
<nav class="tabs">
<label for="view-overview">Overview</label>
<label for="view-connections">Connections</label>
<label for="view-history">History</label>
</nav>
<section class="panel overview">{"".join(overview)}</section>
<section class="panel connections">
<svg class="map" viewBox="0 0 {VIEW_SIZE} {VIEW_SIZE}" role="img" aria-label="Memory map">
<g class="fish" transform="translate({CENTER} {CENTER})">
<ellipse cx="-6" cy="0" rx="34" ry="22"/>
<polygon points="24,-4 52,-18 52,18 24,4"/>
<circle cx="-18" cy="-4" r="3" fill="#102126"/>
</g>
{"".join(lines)}
{"".join(marks)}
</svg>
<p class="legend">{_esc(legend)}</p>
</section>
<section class="panel history"><ol class="history">{"".join(history)}</ol>
<p class="legend">A write or a read appears here when the row carries a timestamp. Otherwise each line is a stored node and its visit count.</p>
</section>
</div>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    """Serve one HTML snapshot. The page is stored on the class."""

    page = b""

    def do_GET(self):
        """Return the snapshot for ``/`` and 404 for every other path."""
        if self.path.split("?", 1)[0] not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = type(self).page
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """Drop the default access log."""


def serve(page, port):
    """Serve ``page`` on localhost until the process is stopped.

    :param page: the HTML document.
    :param port: the TCP port. ``0`` asks the OS for a free port.
    :returns: the listening server. The caller keeps it running.
    """
    _Handler.page = page.encode()
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main(argv=None):
    """Load one domain and print it, write the page, or serve the page.

    :param argv: arguments without the program name. ``None`` uses ``sys.argv``.
    :returns: the process exit code.
    """
    parser = argparse.ArgumentParser(description="Show a procedural-graph domain as a memory map.")
    parser.add_argument("--domain", default="bug_triage")
    parser.add_argument("--html", help="Write the page to this path. Use - for stdout.")
    parser.add_argument("--serve", nargs="?", const=8765, type=int, help="Serve the page on 127.0.0.1 (default port 8765).")
    parser.add_argument("--json", action="store_true", help="Print the view model as JSON.")
    args = parser.parse_args(argv)
    try:
        view = build_view(load_nodes(args.domain), args.domain)
    except procgraph.GraphError as exc:
        print(f"fish: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return 0
    page = render_html(view)
    if args.html == "-":
        print(page)
    elif args.html:
        with open(args.html, "w", encoding="utf-8") as handle:
            handle.write(page)
        print(args.html)
    if args.serve is not None:
        server = serve(page, args.serve)
        host, port = server.server_address
        print(f"http://{host}:{port}")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            server.shutdown()
        return 0
    if not args.html:
        print(render_text(view))
    return 0


if __name__ == "__main__":
    sys.exit(main())
