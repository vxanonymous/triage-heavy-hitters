from __future__ import annotations

from pathlib import Path

import pytest
from slimconfig import build_output, plain_output

import verifier
from contract import TASKS, TOOLS, GenerateInput, HeavyInput, Task, Tool
from plugin import generate_traffic, heavy_hitters

HEADER = "ts,client_ip,user_id,endpoint,status,latency_ms\n"


# The verifier gets contract instances, as NanoAgent's sandbox builds them from JSON.
def verify_input(tool: str, value: dict) -> dict:
    return verifier.verify_input(tool, build_output(value, TOOLS[Tool(tool)][0]))


def verify_output(tool: str, given: dict, made: dict, workspace: Path) -> dict:
    classes = TOOLS[Tool(tool)]
    return verifier.verify_output(tool, build_output(given, classes[0]), build_output(made, classes[1]), str(workspace))


def verify_task(task: str, arguments: dict, output: dict, workspace: Path) -> dict:
    given, made = TASKS[Task(task)]
    return verifier.verify_task(task, build_output(arguments, given), build_output(output, made), None, str(workspace))


def generated(workspace: Path, seed: int = 2, requests: int = 20_000) -> tuple[dict, dict]:
    given = {"seed": seed, "requests": requests, "destination": "traffic"}
    return given, plain_output(generate_traffic(GenerateInput(**given), workspace))


def heavy(workspace: Path, file: str, status_class: str, phi: float, epsilon: float) -> tuple[dict, dict]:
    given = {"file": file, "field": "endpoint", "status_class": status_class, "phi": phi, "epsilon": epsilon}
    built = build_output(given, HeavyInput)
    return given, plain_output(heavy_hitters(built, workspace))


# generate_traffic


def test_approves_a_generated_log(tmp_path: Path) -> None:
    given, made = generated(tmp_path)
    assert verify_output("generate_traffic", given, made, tmp_path)["valid"] is True
    assert verify_task("generate-traffic", given, made, tmp_path)["valid"] is True


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"file": "traffic/traffic-3-20000.csv"}, "not saved as"),
        ({"sha256": "0" * 64}, "sha256"),
        ({"requests": 19_999}, "requests"),
        ({"columns": ["ts"]}, "columns"),
    ],
)
def test_refuses_a_wrong_generate_output(tmp_path: Path, changes: dict, message: str) -> None:
    given, made = generated(tmp_path)
    verdict = verify_output("generate_traffic", given, made | changes, tmp_path)
    assert verdict["valid"] is False and message in verdict["message"]


def test_refuses_a_missing_or_tampered_log(tmp_path: Path) -> None:
    given, made = generated(tmp_path)
    target = tmp_path / made["file"]
    target.write_text(target.read_text() + "2026-11-01T00:00:00Z,10.0.0.1,u0001,/api/x,200,5\n")
    assert "sha256" in verify_output("generate_traffic", given, made, tmp_path)["message"]
    target.unlink()
    assert "not in the workspace" in verify_output("generate_traffic", given, made, tmp_path)["message"]


# heavy_hitters


@pytest.mark.parametrize(
    ("status_class", "phi", "epsilon"), [("5xx", 0.2, 0.02), ("any", 0.1, 0.01), ("4xx", 1.0, 0.5)]
)
def test_approves_heavy_hitters_that_keep_the_guarantees(tmp_path: Path, status_class, phi, epsilon) -> None:
    _, log = generated(tmp_path)
    given, made = heavy(tmp_path, log["file"], status_class, phi, epsilon)
    assert verify_output("heavy_hitters", given, made, tmp_path)["valid"] is True
    assert verify_task("find-heavy-hitters", given, made, tmp_path)["valid"] is True


def test_refuses_heavy_hitters_that_break_the_guarantees(tmp_path: Path) -> None:
    _, log = generated(tmp_path)
    given, made = heavy(tmp_path, log["file"], "5xx", 0.2, 0.02)
    first = made["hitters"][0]
    cases = {
        "missing": made | {"hitters": made["hitters"][1:]},
        "over-counted": made | {"hitters": [first | {"estimate": first["estimate"] + 10_000}]},
        "under-counted": made | {"hitters": [first | {"estimate": 1}]},
        "invented": made | {"hitters": [*made["hitters"], {"value": "/api/none", "estimate": 1000}]},
        "duplicated": made | {"hitters": [first, first]},
        "length": made | {"stream_length": made["stream_length"] + 1},
        "counters": made | {"counters": 10},
        "echo": made | {"phi": 0.3},
    }
    for name, output in cases.items():
        assert verify_output("heavy_hitters", given, output, tmp_path)["valid"] is False, name


def test_refuses_a_low_estimate_listed_as_heavy(tmp_path: Path) -> None:
    _, log = generated(tmp_path)
    given, made = heavy(tmp_path, log["file"], "any", 0.1, 0.01)
    low = {"value": "/api/health", "estimate": 1}
    verdict = verify_output("heavy_hitters", given, made | {"hitters": [*made["hitters"], low]}, tmp_path)
    assert verdict["valid"] is False


def test_an_empty_stream_has_no_heavy_hitters(tmp_path: Path) -> None:
    (tmp_path / "ok.csv").write_text(HEADER + "2026-10-31T12:00:00Z,10.0.0.1,u0001,/api/a,200,5\n")
    given, made = heavy(tmp_path, "ok.csv", "5xx", 0.5, 0.1)
    assert made["stream_length"] == 0 and made["hitters"] == []
    assert verify_output("heavy_hitters", given, made, tmp_path)["valid"] is True
    invented = made | {"hitters": [{"value": "/api/a", "estimate": 1}]}
    assert verify_output("heavy_hitters", given, invented, tmp_path)["valid"] is False


def test_refuses_a_malformed_log(tmp_path: Path) -> None:
    given = {"file": "bad.csv", "field": "endpoint", "status_class": "any", "phi": 0.5, "epsilon": 0.1}
    made = given | {"stream_length": 0, "counters": 10, "hitters": []}
    (tmp_path / "bad.csv").write_text("not,a,log\n")
    assert "header" in verify_output("heavy_hitters", given, made, tmp_path)["message"]
    (tmp_path / "bad.csv").write_text(HEADER + "2026-10-31T12:00:00Z,10.0.0.1,/api/a,200\n")
    assert "columns" in verify_output("heavy_hitters", given, made, tmp_path)["message"]
    (tmp_path / "bad.csv").unlink()
    assert "not in the workspace" in verify_output("heavy_hitters", given, made, tmp_path)["message"]


def test_checks_what_the_types_cannot_say() -> None:
    good = {"file": "traffic/t.csv", "field": "endpoint", "status_class": "any", "phi": 0.1, "epsilon": 0.01}
    assert verify_input("heavy_hitters", good)["valid"] is True
    assert verify_input("heavy_hitters", good | {"phi": 1.0, "epsilon": 0.001})["valid"] is True
    for bad in (
        {"phi": 0.0},
        {"phi": 1.01},
        {"epsilon": 0.1},
        {"epsilon": 0.0009},
        {"file": "../t.csv"},
        {"file": "t.txt"},
    ):
        assert verify_input("heavy_hitters", good | bad)["valid"] is False, bad
    generate = {"seed": 1, "requests": 1000, "destination": "traffic"}
    assert verify_input("generate_traffic", generate)["valid"] is True
    assert verify_input("generate_traffic", generate | {"requests": 200_000})["valid"] is True
    for bad in ({"requests": 999}, {"requests": 200_001}, {"destination": "/abs"}, {"destination": "../x"}):
        assert verify_input("generate_traffic", generate | bad)["valid"] is False, bad


# find-error-hotspot


def hotspot(workspace: Path, seed: int = 2, requests: int = 20_000) -> tuple[dict, dict]:
    """What a correct agent submits: generate, then the two heavy_hitters calls the instructions name."""
    _, log = generated(workspace, seed, requests)
    _, errors = heavy(workspace, log["file"], "5xx", 0.2, 0.02)
    _, overall = heavy(workspace, log["file"], "any", 0.1, 0.01)
    top = errors["hitters"][0]
    listed = {hitter["value"]: hitter["estimate"] for hitter in overall["hitters"]}
    output = {
        "file": log["file"],
        "endpoint": top["value"],
        "error_requests": errors["stream_length"],
        "endpoint_errors_estimate": top["estimate"],
        "heavy_overall": listed.get(top["value"], 0) >= 0.1 * overall["stream_length"],
    }
    return {"seed": seed, "requests": requests}, output


@pytest.mark.parametrize(("seed", "endpoint", "heavy_overall"), [(2, "/api/cart", True), (7, "/api/checkout", False)])
def test_approves_the_right_hotspot(tmp_path: Path, seed: int, endpoint: str, heavy_overall: bool) -> None:
    arguments, output = hotspot(tmp_path, seed)
    assert output["endpoint"] == endpoint and output["heavy_overall"] is heavy_overall
    verdict = verify_task("find-error-hotspot", arguments, output, tmp_path)
    assert verdict["valid"] is True and verdict["score"] == 1.0


@pytest.mark.parametrize(
    ("changes", "failed"),
    [
        # Another endpoint's estimate is wrong for it too.
        ({"endpoint": "/api/search"}, ["endpoint", "endpoint_errors_estimate"]),
        ({"error_requests": 1}, ["error_requests"]),
        ({"endpoint_errors_estimate": 1}, ["endpoint_errors_estimate"]),
        ({"heavy_overall": False}, ["heavy_overall"]),
    ],
)
def test_refuses_a_wrong_hotspot_and_scores_what_is_right(tmp_path: Path, changes: dict, failed: list) -> None:
    arguments, output = hotspot(tmp_path)
    verdict = verify_task("find-error-hotspot", arguments, output | changes, tmp_path)
    assert verdict["valid"] is False and verdict["details"]["failed"] == failed
    assert verdict["score"] == (4 - len(failed)) / 4


def test_refuses_a_hotspot_from_another_log_or_none(tmp_path: Path) -> None:
    arguments, output = hotspot(tmp_path)
    assert (
        "not the seed's log" in verify_task("find-error-hotspot", arguments | {"seed": 3}, output, tmp_path)["message"]
    )
    (tmp_path / output["file"]).unlink()
    assert "not in the workspace" in verify_task("find-error-hotspot", arguments, output, tmp_path)["message"]


def test_a_tie_accepts_either_endpoint(tmp_path: Path) -> None:
    rows = ["2026-10-31T12:00:00Z,10.0.0.1,u0001,/api/a,500,5", "2026-10-31T12:00:01Z,10.0.0.1,u0001,/api/b,503,5"]
    rows += ["2026-10-31T12:00:02Z,10.0.0.1,u0001,/api/c,200,5"] * 998
    (tmp_path / "traffic").mkdir()
    (tmp_path / "traffic" / "traffic-0-1000.csv").write_text(HEADER + "\n".join(rows) + "\n")
    output = {"file": "traffic/traffic-0-1000.csv", "error_requests": 2, "endpoint_errors_estimate": 1}
    for endpoint in ("/api/a", "/api/b"):
        submitted = output | {"endpoint": endpoint, "heavy_overall": False}
        assert verify_task("find-error-hotspot", {"seed": 0, "requests": 1000}, submitted, tmp_path)["valid"] is True
