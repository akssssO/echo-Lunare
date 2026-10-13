"""Scenario definitions for the synthetic disruption lab.

A scenario changes supplier capacity, retailer demand, or one route's lead time
for a half-open day window [start_day, end_day) on the forward horizon.
Day 0 is the first simulated decision day. Negative days are history only.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Scenario:
    """One reproducible what-if applied to the synthetic network."""

    name: str
    kind: str
    seed: int = 42
    horizon: int = 14
    history_days: int = 21
    supplier_id: str | None = None
    route_id: str | None = None
    capacity_factor: float = 1.0
    demand_factor: float = 1.0
    extra_lead_days: int = 0
    start_day: int = 1
    end_day: int = 12
    demand_node_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        allowed = {"none", "capacity_loss", "demand_surge", "transport_delay"}
        if self.kind not in allowed:
            raise ValueError(f"Unknown scenario kind: {self.kind}")
        self.seed = int(self.seed)
        self.horizon = max(1, int(self.horizon))
        self.history_days = max(0, int(self.history_days))
        self.capacity_factor = float(min(1.0, max(0.0, self.capacity_factor)))
        self.demand_factor = float(max(0.0, self.demand_factor))
        self.extra_lead_days = max(0, int(self.extra_lead_days))
        self.start_day = max(0, int(self.start_day))
        self.end_day = max(0, int(self.end_day))
        if self.end_day <= self.start_day:
            self.end_day = min(self.horizon, self.start_day + 1)
        if self.demand_node_ids is not None:
            self.demand_node_ids = tuple(self.demand_node_ids)

    def active(self, day: int) -> bool:
        return self.kind != "none" and self.start_day <= day < self.end_day

    def label(self) -> str:
        return {
            "none": "No disruption",
            "capacity_loss": "Supplier capacity loss",
            "demand_surge": "Demand surge",
            "transport_delay": "Transport delay",
        }[self.kind]


def default_scenario() -> Scenario:
    """Opening demo: the Nagpur–Delhi lane slows, so Delhi-side stock thins."""
    return Scenario(
        name="Nagpur–Delhi transport delay",
        kind="transport_delay",
        route_id="E-NGP-DEL",
        extra_lead_days=4,
        start_day=1,
        end_day=12,
        seed=42,
        horizon=14,
        history_days=21,
    )


def preset_scenario(preset: str, seed: int = 42, horizon: int = 14) -> Scenario:
    """Named presets used by the disruption lab. All are synthetic."""
    horizon = max(1, int(horizon))
    end = min(horizon, 12) if horizon > 2 else horizon
    start = 1 if horizon > 2 else 0
    if preset == "none":
        return Scenario(name="No disruption", kind="none", seed=seed, horizon=horizon, start_day=0, end_day=horizon)
    if preset == "capacity_loss":
        return Scenario(
            name="Nashik tomato capacity loss",
            kind="capacity_loss",
            supplier_id="SUP-NSK",
            capacity_factor=0.20,
            start_day=start,
            end_day=end,
            seed=seed,
            horizon=horizon,
        )
    if preset == "demand_surge":
        return Scenario(
            name="Delhi demand surge",
            kind="demand_surge",
            demand_factor=1.9,
            demand_node_ids=("RET-DEL", "RET-NOI"),
            start_day=start,
            end_day=end,
            seed=seed,
            horizon=horizon,
        )
    if preset == "transport_delay":
        return Scenario(
            name="Nagpur–Delhi transport delay",
            kind="transport_delay",
            route_id="E-NGP-DEL",
            extra_lead_days=4,
            start_day=start,
            end_day=end,
            seed=seed,
            horizon=horizon,
        )
    raise ValueError(f"Unknown preset: {preset}")
