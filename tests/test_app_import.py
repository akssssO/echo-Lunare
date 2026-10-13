"""The app module imports without opening a browser or a network connection."""

import ast
from pathlib import Path


def test_app_and_pages_parse():
    root = Path(__file__).resolve().parents[1]
    files = [root / "app.py", *sorted((root / "app_pages").glob("*.py"))]
    assert files[0].exists()
    for path in files:
        ast.parse(path.read_text(encoding="utf-8"))


def test_core_modules_import():
    from src.evaluation import evaluate_suite
    from src.network import build_network
    from src.scenario import default_scenario

    net = build_network()
    scenario = default_scenario()
    assert scenario.kind == "transport_delay"
    assert "HUB-DEL" in net.nodes
    assert callable(evaluate_suite)
