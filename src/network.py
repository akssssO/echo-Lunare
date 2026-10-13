"""Illustrative fresh-produce network.

Place names and organisations are synthetic labels inspired by Indian geography.
They are not claims about real suppliers, contracts, or freight lanes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SKUS: tuple[str, ...] = ("tomato", "onion", "potato")

# Assumed fraction of on-hand crates lost per day before sales.
# These are modelling assumptions, not measured food waste.
SPOILAGE_RATE: dict[str, float] = {
    "tomato": 0.02,
    "onion": 0.008,
    "potato": 0.003,
}

# Spoilage is applied only where product is waiting to be issued to the next
# buyer. Supplier stocks and in-transit crates are assumed not to spoil inside
# this short horizon. This is a modelling choice, not a measurement.
SPOILAGE_NODE_TYPES = ("hub", "retailer")

CRATE_KG = 20  # illustrative mass only; the model accounts in crates

NODE_TYPES = ("supplier", "warehouse", "hub", "retailer")

# Order-up-to cover, in days of expected outflow.
TARGET_COVER_DAYS: dict[str, float] = {
    "supplier": 0.0,
    "warehouse": 3.0,
    "hub": 3.0,
    "retailer": 3.0,
}

# Donors keep this many days of expected outflow during redistribution.
PROTECT_DAYS = 1.0
AGGRESSIVE_PROTECT_DAYS = 0.35


@dataclass
class Node:
    node_id: str
    name: str
    node_type: str
    place: str


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    lead_time_days: int
    capacity_per_day: float
    cost_per_unit: float
    role: str  # primary, alternate, lateral


@dataclass
class SupplyNetwork:
    nodes: dict[str, Node]
    edges: dict[str, Edge]
    production_capacity: dict[tuple[str, str], float]
    baseline_demand: dict[tuple[str, str], float]
    expected_outflow: dict[tuple[str, str], float]
    initial_inventory: dict[tuple[str, str], float]
    storage_limit: dict[tuple[str, str], float]
    inbound: dict[str, list[Edge]] = field(default_factory=dict)
    outbound: dict[str, list[Edge]] = field(default_factory=dict)

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def produces(self, node_id: str, sku: str) -> bool:
        return self.production_capacity.get((node_id, sku), 0.0) > 0.0


def _edge(
    edge_id: str,
    source: str,
    target: str,
    lead: int,
    capacity: float,
    cost: float,
    role: str,
) -> Edge:
    if lead < 1:
        raise ValueError(f"{edge_id} lead time must be at least 1 day")
    if capacity <= 0 or cost < 0:
        raise ValueError(f"{edge_id} has a non-positive capacity or a negative cost")
    if role not in {"primary", "alternate", "lateral"}:
        raise ValueError(role)
    return Edge(edge_id, source, target, lead, capacity, cost, role)


def build_network() -> SupplyNetwork:
    """Build the fixed synthetic graph. Inventory figures are opening snapshots."""
    node_rows = [
        ("SUP-NSK", "Nashik Grower Collective", "supplier", "Nashik"),
        ("SUP-LSG", "Lasalgaon Onion Desk", "supplier", "Lasalgaon"),
        ("SUP-AGR", "Agra Potato Shed", "supplier", "Agra"),
        ("SUP-IDR", "Indore Potato Buffer", "supplier", "Indore"),
        ("SUP-PUN", "Pune Alternate Co-op", "supplier", "Pune"),
        ("WH-NGP", "Nagpur Consolidation Shed", "warehouse", "Nagpur"),
        ("WH-BPL", "Bhopal Buffer Shed", "warehouse", "Bhopal"),
        ("HUB-DEL", "Delhi Night Hub", "hub", "Delhi"),
        ("HUB-LKO", "Lucknow Night Hub", "hub", "Lucknow"),
        ("HUB-JAI", "Jaipur Night Hub", "hub", "Jaipur"),
        ("RET-DEL", "Chandni Chowk Fresh Counter", "retailer", "Delhi"),
        ("RET-NOI", "Noida Housing Cluster", "retailer", "Noida"),
        ("RET-KNP", "Kanpur Bazaar Counter", "retailer", "Kanpur"),
        ("RET-JAI", "Johari Fresh Counter", "retailer", "Jaipur"),
        ("RET-AGR", "Agra Sadar Counter", "retailer", "Agra"),
        ("RET-GWL", "Gwalior City Counter", "retailer", "Gwalior"),
    ]
    nodes = {row[0]: Node(*row) for row in node_rows}

    edges = [
        _edge("E-NSK-NGP", "SUP-NSK", "WH-NGP", 1, 340, 0.80, "primary"),
        _edge("E-NSK-BPL", "SUP-NSK", "WH-BPL", 2, 140, 1.15, "primary"),
        _edge("E-LSG-NGP", "SUP-LSG", "WH-NGP", 1, 320, 0.75, "primary"),
        _edge("E-LSG-BPL", "SUP-LSG", "WH-BPL", 1, 160, 1.05, "primary"),
        _edge("E-AGR-NGP", "SUP-AGR", "WH-NGP", 2, 280, 0.85, "primary"),
        _edge("E-AGR-BPL", "SUP-AGR", "WH-BPL", 1, 180, 0.70, "primary"),
        _edge("E-PUN-NGP", "SUP-PUN", "WH-NGP", 2, 220, 1.70, "alternate"),
        _edge("E-PUN-BPL", "SUP-PUN", "WH-BPL", 2, 180, 1.85, "alternate"),
        _edge("E-IDR-NGP", "SUP-IDR", "WH-NGP", 2, 140, 1.55, "alternate"),
        _edge("E-IDR-BPL", "SUP-IDR", "WH-BPL", 1, 120, 1.40, "alternate"),
        _edge("E-NGP-DEL", "WH-NGP", "HUB-DEL", 2, 520, 1.55, "primary"),
        _edge("E-NGP-JAI", "WH-NGP", "HUB-JAI", 2, 280, 1.25, "primary"),
        _edge("E-NGP-LKO", "WH-NGP", "HUB-LKO", 2, 180, 1.60, "alternate"),
        _edge("E-BPL-LKO", "WH-BPL", "HUB-LKO", 1, 220, 1.05, "primary"),
        _edge("E-BPL-DEL", "WH-BPL", "HUB-DEL", 2, 240, 1.75, "alternate"),
        _edge("E-BPL-JAI", "WH-BPL", "HUB-JAI", 2, 180, 1.45, "alternate"),
        _edge("E-NGP-BPL", "WH-NGP", "WH-BPL", 1, 110, 0.95, "lateral"),
        _edge("E-BPL-NGP", "WH-BPL", "WH-NGP", 1, 110, 0.95, "lateral"),
        _edge("E-DEL-LKO", "HUB-DEL", "HUB-LKO", 1, 90, 1.05, "lateral"),
        _edge("E-LKO-DEL", "HUB-LKO", "HUB-DEL", 1, 90, 1.05, "lateral"),
        _edge("E-DEL-JAI", "HUB-DEL", "HUB-JAI", 1, 80, 1.15, "lateral"),
        _edge("E-JAI-DEL", "HUB-JAI", "HUB-DEL", 1, 80, 1.15, "lateral"),
        _edge("E-LKO-JAI", "HUB-LKO", "HUB-JAI", 2, 70, 1.35, "lateral"),
        _edge("E-JAI-LKO", "HUB-JAI", "HUB-LKO", 2, 70, 1.35, "lateral"),
        _edge("E-DEL-RDEL", "HUB-DEL", "RET-DEL", 1, 250, 0.40, "primary"),
        _edge("E-DEL-RNOI", "HUB-DEL", "RET-NOI", 1, 160, 0.50, "primary"),
        _edge("E-DEL-RAGR", "HUB-DEL", "RET-AGR", 1, 150, 0.70, "primary"),
        _edge("E-LKO-RKNP", "HUB-LKO", "RET-KNP", 1, 160, 0.50, "primary"),
        _edge("E-LKO-RAGR", "HUB-LKO", "RET-AGR", 1, 120, 0.65, "alternate"),
        _edge("E-JAI-RJAI", "HUB-JAI", "RET-JAI", 1, 150, 0.40, "primary"),
        _edge("E-JAI-RGWL", "HUB-JAI", "RET-GWL", 1, 120, 0.60, "primary"),
        _edge("E-DEL-RGWL", "HUB-DEL", "RET-GWL", 2, 90, 1.05, "alternate"),
    ]
    edge_map = {edge.edge_id: edge for edge in edges}

    demand_rows = {
        "RET-DEL": {"tomato": 68.0, "onion": 58.0, "potato": 50.0},
        "RET-NOI": {"tomato": 36.0, "onion": 32.0, "potato": 28.0},
        "RET-KNP": {"tomato": 34.0, "onion": 30.0, "potato": 30.0},
        "RET-AGR": {"tomato": 26.0, "onion": 24.0, "potato": 36.0},
        "RET-JAI": {"tomato": 32.0, "onion": 28.0, "potato": 26.0},
        "RET-GWL": {"tomato": 20.0, "onion": 18.0, "potato": 22.0},
    }
    baseline: dict[tuple[str, str], float] = {}
    for node_id, sku_map in demand_rows.items():
        for sku, qty in sku_map.items():
            baseline[(node_id, sku)] = float(qty)

    # Primary parent used only to derive expected outflow. Lanes themselves live on edges.
    primary_parent = {
        "RET-DEL": "HUB-DEL",
        "RET-NOI": "HUB-DEL",
        "RET-AGR": "HUB-DEL",
        "RET-KNP": "HUB-LKO",
        "RET-JAI": "HUB-JAI",
        "RET-GWL": "HUB-JAI",
        "HUB-DEL": "WH-NGP",
        "HUB-JAI": "WH-NGP",
        "HUB-LKO": "WH-BPL",
    }
    outflow: dict[tuple[str, str], float] = {}
    for retailer, sku_map in demand_rows.items():
        chain = [retailer]
        while chain[-1] in primary_parent:
            chain.append(primary_parent[chain[-1]])
        for sku, qty in sku_map.items():
            for node_id in chain:
                outflow[(node_id, sku)] = outflow.get((node_id, sku), 0.0) + qty

    production = {
        ("SUP-NSK", "tomato"): 460.0,
        ("SUP-LSG", "onion"): 400.0,
        ("SUP-AGR", "potato"): 440.0,
        ("SUP-IDR", "potato"): 120.0,
        ("SUP-PUN", "tomato"): 190.0,
        ("SUP-PUN", "onion"): 150.0,
    }

    initial: dict[tuple[str, str], float] = {}
    storage: dict[tuple[str, str], float] = {}
    for node in nodes.values():
        for sku in SKUS:
            if node.node_type == "supplier":
                cap = production.get((node.node_id, sku), 0.0)
                initial[(node.node_id, sku)] = cap  # one day of production on hand
                storage[(node.node_id, sku)] = max(4.0 * cap, 1.0)
            else:
                daily = outflow.get((node.node_id, sku), 0.0)
                cover = TARGET_COVER_DAYS[node.node_type]
                initial[(node.node_id, sku)] = cover * daily
                storage[(node.node_id, sku)] = max(8.0 * daily, initial[(node.node_id, sku)], 1.0)

    net = SupplyNetwork(
        nodes=nodes,
        edges=edge_map,
        production_capacity=production,
        baseline_demand=baseline,
        expected_outflow=outflow,
        initial_inventory=initial,
        storage_limit=storage,
    )
    for edge in edges:
        net.inbound.setdefault(edge.target, []).append(edge)
        net.outbound.setdefault(edge.source, []).append(edge)
    validate_network(net)
    return net


def validate_network(net: SupplyNetwork) -> None:
    """Raise if the synthetic graph cannot support the interventions we offer."""
    for edge in net.edges.values():
        if edge.source not in net.nodes or edge.target not in net.nodes:
            raise ValueError(f"Edge {edge.edge_id} references a missing node")
    for (node_id, sku), qty in net.initial_inventory.items():
        if qty < -1e-9:
            raise ValueError(f"Negative opening inventory at {node_id} {sku}")
        if qty - net.storage_limit[(node_id, sku)] > 1e-6:
            raise ValueError(f"Opening inventory exceeds storage at {node_id} {sku}")

    for sku in SKUS:
        producers = [n for n in net.nodes if net.produces(n, sku)]
        if not producers:
            raise ValueError(f"No producer for {sku}")
        for node_id, node in net.nodes.items():
            if node.node_type != "retailer":
                continue
            if net.baseline_demand.get((node_id, sku), 0.0) <= 0:
                continue
            if not _reachable(net, producers, node_id):
                raise ValueError(f"{node_id} cannot receive {sku} from a producer")

    if not any(edge.role == "alternate" for edge in net.edges.values()):
        raise ValueError("Alternative sourcing has no lanes")
    if not any(edge.role == "lateral" for edge in net.edges.values()):
        raise ValueError("Redistribution has no lateral lanes")
    _assert_primary_acyclic(net)


def _reachable(net: SupplyNetwork, origins: list[str], target: str) -> bool:
    seen = set(origins)
    stack = list(origins)
    while stack:
        current = stack.pop()
        if current == target:
            return True
        for edge in net.outbound.get(current, []):
            if edge.target not in seen:
                seen.add(edge.target)
                stack.append(edge.target)
    return False


def _assert_primary_acyclic(net: SupplyNetwork) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ValueError(f"Primary-lane cycle at {node_id}")
        visiting.add(node_id)
        for edge in net.outbound.get(node_id, []):
            if edge.role == "primary":
                visit(edge.target)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in net.nodes:
        visit(node_id)


def descendants(net: SupplyNetwork, origins: list[str]) -> set[str]:
    """Nodes reachable by directed edges, excluding the origins themselves."""
    seen: set[str] = set()
    stack = list(origins)
    while stack:
        current = stack.pop()
        for edge in net.outbound.get(current, []):
            if edge.target not in seen and edge.target not in origins:
                seen.add(edge.target)
                stack.append(edge.target)
    return seen


def upstream_suppliers(net: SupplyNetwork, node_id: str, sku: str) -> list[str]:
    """Suppliers that produce this SKU and can reach the node on primary lanes only."""
    found: list[str] = []
    seen = {node_id}
    stack = [node_id]
    while stack:
        current = stack.pop()
        for edge in net.inbound.get(current, []):
            if edge.role != "primary" or edge.source in seen:
                continue
            seen.add(edge.source)
            if net.produces(edge.source, sku):
                found.append(edge.source)
            stack.append(edge.source)
    return found


def fastest_primary_lead(
    net: SupplyNetwork, node_id: str, delay_by_edge: dict[str, int]
) -> tuple[int | None, int]:
    """Return (lead days, extra delay on that fastest primary lane)."""
    edges = [edge for edge in net.inbound.get(node_id, []) if edge.role == "primary"]
    if not edges:
        return None, 0
    best_lead: int | None = None
    best_extra = 0
    for edge in edges:
        extra = int(delay_by_edge.get(edge.edge_id, 0))
        lead = edge.lead_time_days + extra
        if best_lead is None or lead < best_lead:
            best_lead = lead
            best_extra = extra
    return best_lead, best_extra
