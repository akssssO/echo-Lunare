"""Text that the product must not contradict."""

BANNER = "DEMO MODE — Synthetic data; not connected to live supply chains."

ASSUMPTIONS = [
    "The network is a synthetic, illustrative fresh-produce graph with Indian place labels. It is not a map of real contracts, mandis, or routes.",
    "The time step is one day. The unit is a crate, illustratively about 20 kg. Nothing is denominated in rupees.",
    "Unmet demand is lost sales. It is not backlogged into later days.",
    "Requested demand is generated exogenously. Observed sales can be lower during a stockout; the risk engine never treats that sales dip as a fall in demand.",
    "A shipment dispatched at the end of a day arrives at the start of day + lead time. It is not available the same day.",
    "Supplier production, route capacity, storage, and on-hand stock are hard limits. Inventory is not allowed to go negative, and the same crates are not issued twice.",
    "Spoilage is an assumed daily fraction of hub and retailer on-hand stock (tomato 2%, onion 0.8%, potato 0.3%). Supplier stock and in-transit crates do not spoil in this short horizon. Figures are estimates, not weighed waste.",
    "Early-warning scores use fixed weights: cover 0.50, delay 0.20, demand deviation 0.15, upstream capacity 0.15. An alert fires on a hard cover shortfall or when the score reaches 0.40. The threshold baseline flags on-hand cover below 2 days and ignores pipeline, delay, and supplier capacity.",
    "The detector sees only that morning's stock, pipeline, trailing requested demand, lead time already in force, and upstream capacity already in force.",
    "Alternative sourcing draws primary lanes first, then an alternate lane if the source still has stock and the route has capacity. Redistribution moves surplus only after the donor keeps 1.0 day of expected outflow (0.35 days in the aggressive stress policy).",
    "Recommendations are advisory. They are not dispatch instructions.",
    "The warm-up history illustrates requested demand. The forward simulation restarts from the documented opening inventory so warm-up stock is not counted twice.",
]
