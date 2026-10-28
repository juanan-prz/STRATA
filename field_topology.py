"""Read-only field topology metrics. Pure Python, no external dependencies.

Called once per half-breath (every BREATH_PERIOD/2 cycles) from run_report.py and
live_c2.py. Samples both expansion and contraction phases of the breath.
Reads the contraction value and breath count directly from the field — no
hardcoded cycle arithmetic.

Excludes Zero Points from component and clustering metrics — they are universal
apparents that never enter as operands (TMC p.22).

Two depth measures:
- conflict depth: for each conflict construct, the deepest conflict recursion
  on its edges, the quantity the framework caps at the Adsurdic threshold
  (TMC p.41);
- genealogical depth (Genealogy): how many [::] generations separate a
  construct from what the field did not produce itself (percepts, anchors,
  questions), for "Depth implies recursive delay from origin"
  (Understanding_TMC p.72).

Does not mutate the field, seal proofs, or call the model.
"""
from collections import defaultdict


def field_topology(field, cycle=None, zero_points=None, genealogy=None):
    """Compute read-only topology metrics of the field.

    Args:
        field: the ConcordancyField (read-only access to constructs and edges)
        cycle: optional cycle number for trace annotation
        zero_points: set of Zero Point names (use S.ZERO_POINTS.keys())
        genealogy: optional Genealogy kept up to date every cycle; adds the
            genealogical depth of the constructs by layer

    Returns a dict of scalar metrics. Does not modify field.constructs or
    field.edges. No networkx — pure Python for Mac compatibility.

    All tie-breaking uses sorted() for deterministic results across processes.
    """
    if zero_points is None:
        zero_points = set()

    edges = field.edges
    E = len(edges)
    all_nodes = set(field.constructs)
    # Exclude Zero Points from component/clustering analysis
    nodes = all_nodes - zero_points
    V = len(nodes)

    # Adjacency (directed) — only among non-ZP nodes
    adj = defaultdict(set)
    radj = defaultdict(set)  # reverse adjacency for reciprocity
    for e in edges:
        adj[e.src].add(e.tgt)
        radj[e.tgt].add(e.src)

    # Degrees (all edges, including to/from ZPs)
    out_deg = defaultdict(int)
    in_deg = defaultdict(int)
    for e in edges:
        out_deg[e.src] += 1
        in_deg[e.tgt] += 1
    total_deg = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in nodes}

    # Deterministic: sort by degree desc then name asc for tie-breaking
    if total_deg:
        max_deg_entry = max(sorted(total_deg.items()), key=lambda x: (x[1], x[0]))
        max_deg = max_deg_entry[1]
        max_deg_node = max_deg_entry[0]
    else:
        max_deg = 0
        max_deg_node = ""
    max_deg_share = round(max_deg / max(2 * E, 1), 4)

    # --- Weakly connected components (BFS on undirected view, no ZPs) ---
    undir = defaultdict(set)
    for e in edges:
        if e.src in nodes:
            undir[e.src].add(e.tgt)
        if e.tgt in nodes:
            undir[e.tgt].add(e.src)

    visited = set()
    wccs = []
    for start in sorted(nodes):  # deterministic order
        if start in visited:
            continue
        comp = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            for nb in sorted(undir[n]):  # deterministic
                if nb not in comp and nb in nodes:
                    stack.append(nb)
        visited |= comp
        wccs.append(comp)

    wcc_sizes = sorted((len(c) for c in wccs), reverse=True)
    # Deterministic largest: by size desc, then by sorted min-name asc
    largest_wcc = max(wccs, key=lambda c: (len(c), min(c))) if wccs else set()
    largest_wcc_share = round(len(largest_wcc) / max(V, 1), 4) if V else 0.0

    # ZP count (isolated by definition)
    zp_count = len(zero_points & all_nodes)

    # --- Strongly connected components (iterative Tarjan, no ZPs) ---
    sccs = _tarjan_iterative(nodes, adj)

    # SCCs with more than one node -> directed cycles (recursion loops)
    multi_scc = [c for c in sccs if len(c) > 1]

    # --- Reciprocity: fraction of edges that have a reverse edge ---
    recip = 0
    for e in edges:
        # Check if the inverse edge exists (not the same edge)
        if e.src in radj and e.tgt in radj[e.src]:
            recip += 1
    reciprocity = round(recip / max(E, 1), 4)

    # --- Triangles and clustering (undirected, no ZPs) ---
    triangles = 0
    clustering_sum = 0.0
    nodes_with_neighbors = 0
    for v in sorted(nodes):
        neighbors = undir[v] & nodes  # only non-ZP neighbors
        k = len(neighbors)
        if k < 2:
            continue
        nodes_with_neighbors += 1
        tri_v = 0
        neighbor_list = sorted(neighbors)
        for i in range(len(neighbor_list)):
            for j in range(i + 1, len(neighbor_list)):
                a, b = neighbor_list[i], neighbor_list[j]
                if b in undir[a]:
                    tri_v += 1
        triangles += tri_v
        # Each pair counts once; factor of 2 in numerator for undirected
        clustering_sum += (2 * tri_v) / (k * (k - 1))

    # Each triangle counted 3 times (once per vertex)
    triangle_count = triangles // 3
    clustering = round(clustering_sum / max(nodes_with_neighbors, 1), 4) if nodes_with_neighbors else 0.0

    # --- Edges by state ---
    state_counts = defaultdict(int)
    for e in edges:
        state_counts[e.state.name] += 1

    # --- Edges by layer pair ---
    layer_pairs = defaultdict(int)
    for e in edges:
        src_layer = field.constructs.get(e.src)
        tgt_layer = field.constructs.get(e.tgt)
        key = f"{src_layer.layer.name}->{tgt_layer.layer.name}" if src_layer and tgt_layer else "UNKNOWN"
        layer_pairs[key] += 1

    # --- BOTH edges in largest weak component ---
    both_total = sum(1 for e in edges if e.state.name == "BOTH")
    both_in_largest = sum(1 for e in edges
                          if e.state.name == "BOTH"
                          and e.src in largest_wcc
                          and e.tgt in largest_wcc)
    # Proportion of BOTH edges that live in the largest component
    both_largest_share = round(both_in_largest / max(both_total, 1), 4)

    # --- Conflict depth (deepest conflict recursion on each conflict's edges) ---
    edge_depth = defaultdict(int)
    for e in edges:
        d = getattr(e, "concordancy_depth", 0)
        if d > edge_depth[e.src]:
            edge_depth[e.src] = d
        if d > edge_depth[e.tgt]:
            edge_depth[e.tgt] = d
    conflict_hist = defaultdict(int)
    for n in sorted(nodes):
        if getattr(field.constructs[n], "conflict", False):
            conflict_hist[edge_depth[n]] += 1

    result = {
        "constructs": len(all_nodes),
        "edges": E,
        "nodes_excluding_zp": V,
        "zero_points": zp_count,
        "weak_components": len(wccs),
        "largest_wcc_share": largest_wcc_share,
        "wcc_sizes_top5": wcc_sizes[:5] if len(wcc_sizes) > 5 else wcc_sizes,
        "strong_cycles": len(multi_scc),
        "largest_scc_size": max(len(c) for c in multi_scc) if multi_scc else 0,
        "reciprocity": reciprocity,
        "triangles": triangle_count,
        "clustering": clustering,
        "max_degree": max_deg,
        "max_degree_node": max_deg_node[:60] if max_deg_node else "",
        "max_degree_share": max_deg_share,
        "edge_states": dict(state_counts),
        "layer_pairs": dict(layer_pairs),
        "both_total": both_total,
        "both_in_largest_wcc": both_in_largest,
        "both_largest_share": both_largest_share,
        "conflict_constructs": sum(conflict_hist.values()),
        "conflict_depth": {str(d): conflict_hist[d] for d in sorted(conflict_hist)},
    }

    if genealogy is not None:
        result["genealogy"] = genealogy.summary(field, nodes)

    # Annotate with cycle info — breath, contraction and tolerance read from the field
    if cycle is not None:
        result["cycle"] = cycle
        result["breath"] = field.breaths
        result["contraction"] = round(field.contraction, 3)
        result["tolerance"] = round(field.tolerance, 3)

    return result


class Genealogy:
    """Genealogical depth of the field's constructs, read-only.

    Depth 0 is anything the field did not produce by [::]: percepts, anchors,
    questions. The product z of x::y (a concordancy or a conflict) has depth
    1 + max(depth(x), depth(y)).

    The parent -> product edges are pruned as they weaken, so depth cannot be
    read from the edges at sampling time. Call update() after every cycle: it
    reads that cycle's operations from ConcordancyOperator.ops_log(), which
    records x, y and z for each one, and keeps depths only for the constructs
    still in the field (a name that concludes and returns later starts afresh).
    """

    def __init__(self):
        self.depth = {}

    def update(self, concordancy, cycle, field):
        """concordancy: the session's ConcordancyOperator (ss.concordancy)."""
        ops_log = getattr(concordancy, "ops_log", None) or []   # a property: the live list
        for op in ops_log:                      # read only; in execution order
            if op.get("cycle") != cycle:
                continue
            x, y, z = op.get("x"), op.get("y"), op.get("z")
            if z:
                self.depth[z] = 1 + max(self.depth.get(x, 0), self.depth.get(y, 0))
        live = field.constructs
        self.depth = {n: d for n, d in self.depth.items() if n in live}

    def summary(self, field, nodes):
        """Depth by layer (n, mean, max) and overall histogram, over `nodes`."""
        by_layer = defaultdict(list)
        hist = defaultdict(int)
        for n in sorted(nodes):
            d = self.depth.get(n, 0)
            by_layer[field.constructs[n].layer.name].append(d)
            hist[d] += 1
        layers = {}
        for layer in sorted(by_layer):
            ds = by_layer[layer]
            produced = [d for d in ds if d > 0]     # leaves out percepts, anchors, questions
            layers[layer] = {"n": len(ds), "mean": round(sum(ds) / len(ds), 3), "max": max(ds),
                             "products": len(produced),
                             "mean_products": round(sum(produced) / len(produced), 3) if produced else 0.0}
        return {"by_layer": layers,
                "histogram": {str(d): hist[d] for d in sorted(hist)}}


def _tarjan_iterative(nodes, adj):
    """Iterative Tarjan's SCC algorithm. Handles large graphs without stack overflow.

    Args:
        nodes: iterable of node names
        adj: dict mapping node -> set of successors

    Returns list of sets, each set being one SCC.
    """
    index_counter = [0]
    stack = []
    on_stack = set()
    indices = {}
    lowlinks = {}
    sccs = []

    for root in sorted(nodes):
        if root in indices:
            continue
        # Iterative DFS with explicit call stack
        # Each frame: (node, neighbor_iterator, phase)
        # phase 0 = entering, phase 1 = returning from child
        call_stack = [(root, iter(sorted(adj[root])), 0, None)]
        indices[root] = index_counter[0]
        lowlinks[root] = index_counter[0]
        index_counter[0] += 1
        stack.append(root)
        on_stack.add(root)

        while call_stack:
            v, nbr_iter, phase, child = call_stack[-1]

            if child is not None and phase == 1:
                # Returning from child -- update lowlink
                lowlinks[v] = min(lowlinks[v], lowlinks[child])
                call_stack[-1] = (v, nbr_iter, 0, None)

            # Continue iterating neighbors
            found_child = False
            for w in nbr_iter:
                if w not in nodes:
                    continue
                if w not in indices:
                    # Unvisited -- push child frame
                    indices[w] = index_counter[0]
                    lowlinks[w] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(w)
                    on_stack.add(w)
                    call_stack[-1] = (v, nbr_iter, 1, w)
                    call_stack.append((w, iter(sorted(adj[w])), 0, None))
                    found_child = True
                    break
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if not found_child:
                # All neighbors processed -- check if SCC root
                if lowlinks[v] == indices[v]:
                    comp = set()
                    while True:
                        w = stack.pop()
                        on_stack.discard(w)
                        comp.add(w)
                        if w == v:
                            break
                    sccs.append(comp)
                call_stack.pop()

    return sccs
