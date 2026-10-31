from collections import Counter
from pathlib import Path

import pytest

from contract import Field, GenerateInput, HeavyInput, StatusClass
from plugin import generate_traffic, heavy_hitters
from plugin.heavy import misra_gries


def test_the_same_seed_gives_the_same_bytes(tmp_path: Path) -> None:
    first = generate_traffic(GenerateInput(seed=7, requests=2000, destination="traffic"), tmp_path)
    data = (tmp_path / first.file).read_bytes()
    second = generate_traffic(GenerateInput(seed=7, requests=2000, destination="traffic"), tmp_path)
    assert first == second and (tmp_path / second.file).read_bytes() == data
    assert first.file == "traffic/traffic-7-2000.csv"
    other = generate_traffic(GenerateInput(seed=8, requests=2000, destination="traffic"), tmp_path)
    assert other.sha256 != first.sha256


@pytest.mark.parametrize(
    ("requests", "destination"),
    [(999, "traffic"), (200_001, "traffic"), (2000, "../out"), (2000, "/tmp/x"), (2000, " ")],
)
def test_refuses_bad_generate_inputs(tmp_path: Path, requests: int, destination: str) -> None:
    with pytest.raises(ValueError):
        generate_traffic(GenerateInput(seed=1, requests=requests, destination=destination), tmp_path)


def test_misra_gries_never_overcounts_and_keeps_its_bound() -> None:
    stream = list("aaaaabbbcccdde" * 10) + list("xyz")
    for counters in range(1, 6):
        kept = misra_gries(stream, counters)
        truth = Counter(stream)
        assert len(kept) <= counters
        for value, estimate in kept.items():
            assert truth[value] - len(stream) / (counters + 1) <= estimate <= truth[value]


def test_finds_the_planted_endpoint_among_5xx(tmp_path: Path) -> None:
    log = generate_traffic(GenerateInput(seed=2, requests=20_000, destination="traffic"), tmp_path)
    found = heavy_hitters(
        HeavyInput(file=log.file, field=Field.ENDPOINT, status_class=StatusClass.SERVER_ERROR, phi=0.2, epsilon=0.02),
        tmp_path,
    )
    assert found.counters == 50 and found.hitters[0].value == "/api/cart"
    assert [hitter.estimate for hitter in found.hitters] == sorted((h.estimate for h in found.hitters), reverse=True)


@pytest.mark.parametrize(("phi", "epsilon"), [(0.0, 0.001), (1.5, 0.1), (0.1, 0.1), (0.1, 0.0005)])
def test_refuses_bad_bounds(tmp_path: Path, phi: float, epsilon: float) -> None:
    log = generate_traffic(GenerateInput(seed=1, requests=1000, destination="traffic"), tmp_path)
    with pytest.raises(ValueError):
        heavy_hitters(
            HeavyInput(file=log.file, field=Field.ENDPOINT, status_class=StatusClass.ANY, phi=phi, epsilon=epsilon),
            tmp_path,
        )


def test_refuses_a_missing_or_foreign_file(tmp_path: Path) -> None:
    given = {"field": Field.ENDPOINT, "status_class": StatusClass.ANY, "phi": 0.1, "epsilon": 0.01}
    with pytest.raises(FileNotFoundError):
        heavy_hitters(HeavyInput(file="traffic/none.csv", **given), tmp_path)
    (tmp_path / "other.csv").write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        heavy_hitters(HeavyInput(file="other.csv", **given), tmp_path)
    with pytest.raises(ValueError):
        heavy_hitters(HeavyInput(file="../outside.csv", **given), tmp_path)
