"""Read-only field topology metrics. Pure Python, no external dependencies.

Called once per breath (every BREATH_PERIOD cycles) from run_report.py and
live_c2.py. Does not mutate the field, seal proofs, or call the model.
"""
from collections import defaultdict


def field_topology(field):
    """Compute read-only topology metrics of the field.

    Returns a dict of scalar metrics. Does not modify field.constructs or
    field.edges. No networkx — pure Python for Mac compatibility.
    """
    edges = field.edges
    E = len(edges)
    V = len(field.constructs)
    nodes = set(field.constructs)

    # Adjacency (directed)
    adj = defaultdict(set)
    radj = defaultdict(set)  # reverse for weak components
    for e in edges:
        adj[e.src].add(e.tgt)
        radj[e.tgt].add(e.src)

    # Degrees
    out_deg = defaultdict(int)
    in_deg = defaultdict(int)
    for e in edges:
        out_deg[e.src] += 1
        in_deg[e.tgt] += 1
    total_deg = {n: in_deg.get(n, 0) + out_deg.get(n, 0) for n in nodes}

    max_deg = max(total_deg.values()) if total_deg else 0
    max_deg_node = max(total_deg, key=total_deg.get) if total_deg else ""
    max_deg_share = round(max_deg / max(2 * E, 1), 4)

    # --- Weakly connected components (BFS on undirected view) ---
    undir = defaultdict(set)
    for e in edges:
        undir[e.src].add(e.tgt)
        undir[e.tgt].add(e.src)
    visited = set()
    wccs = []
    for start in nodes:
        if start in visited:
            continue
        comp = set()
        stack = [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            for nb in undir[n]:
                if nb not in comp:
                    stack.append(nb)
        visited |= comp
        wccs.append(comp)

    wcc_sizes = sorted((len(c) for c in wccs), reverse=True)
    largest_wcc_share = round(wcc_sizes[0] / max(V, 1), 4) if wcc_sizes else 0.0

    # --- Strongly connected components (Tarjan's) ---
    index_counter = [0]
    stack = []
    on_stack = set()
    indices = {}
    lowlinks = {}
    sccs = []

    def strongconnect(v):
        indices[v] = index_counter[0]
        lowlinks[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack.add(v)

        for w in adj[v]:
            if w not in indices:
                strongconnect(w)
                lowlinks[v] = min(lowlinks[v], lowlinks[w])
            elif w in on_stack:
                lowlinks[v] = min(lowlinks[v], indices[w])

        if lowlinks[v] == indices[v]:
            comp = set()
            while True:
                w = stack.pop()
                on_stack.discard(w)
                comp.add(w)
                if w == v:
                    break
            sccs.append(comp)

    for n in nodes:
        if n not in indices:
            strongconnect(n)

    # SCCs with more than one node → directed cycles
    multi_scc = [c for c in sccs if len(c) > 1]

    # --- Reciprocity ---
    recip = 0
    for e in edges:
        if e.src in adj and e.tgt in adj[e.src]:
            recip += 1
    reciprocity = round(recip / max(E, 1), 4)

    # --- Triangles and clustering (undirected) ---
    edges_set = set()
    for e in edges:
        edges_set.add((e.src, e.tgt))
        edges_set.add((e.tgt, e.src))

    triangles = 0
    clustering_sum = 0.0
    for v in nodes:
        neighbors = undir[v]
        k = len(neighbors)
        if k < 2:
            continue
        tri_v = 0
        for i, a in enumerate(neighbors):
            for b in list(neighbors)[i + 1:]:
                if b in undir[a]:
                    tri_v += 1
        triangles += tri_v
        clustering_sum += tri_v / (k * (k - 1))

    # Each triangle counted 3 times (once per vertex)
    triangle_count = triangles // 3
    clustering = round(clustering_sum / max(V, 1), 4)

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
    largest_wcc = wccs[0] if wccs else set()
    both_in_largest = sum(1 for e in edges
                          if e.state.name == "BOTH"
                          and e.src in largest_wcc
                          and e.tgt in largest_wcc)
    both_largest_share = round(both_in_largest / max(E, 1), 4)

    return {
        "constructs": V,
        "edges": E,
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
        "both_in_largest_wcc": both_in_largest,
        "both_largest_share": both_largest_share,
    }
