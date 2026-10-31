"""heavy_hitters: one Misra-Gries pass over an access log column, keeping ceil(1/epsilon) counters."""

import csv
import math
from pathlib import Path

from contract import HeavyInput, HeavyOutput, Hitter, StatusClass
from plugin.traffic import COLUMNS

MIN_EPSILON = 0.001


def check_bounds(phi: float, epsilon: float) -> None:
    if not 0 < phi <= 1:
        raise ValueError(f"phi must be in (0, 1], got {phi}")
    if not MIN_EPSILON <= epsilon < phi:
        raise ValueError(f"epsilon must be at least {MIN_EPSILON} and below phi, got {epsilon}")


def read_log(workspace: Path, file: str) -> list[dict[str, str]]:
    path = Path(file)
    if path.is_absolute() or ".." in path.parts or path.suffix != ".csv":
        raise ValueError(f"file {file!r} must be a .csv inside the plugin workspace")
    target = workspace / path
    if not target.is_file():
        raise FileNotFoundError(f"{file} is not in the workspace: generate it with generate_traffic first")
    with target.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{file} does not have the access log columns {','.join(COLUMNS)}")
        return list(reader)


def matches(status: str, wanted: StatusClass) -> bool:
    return wanted is StatusClass.ANY or status[:1] == wanted.value[0]


def misra_gries(values: list[str], counters: int) -> dict[str, int]:
    """Each value's count, under-counted by at most len(values) / (counters + 1)."""
    kept: dict[str, int] = {}
    for value in values:
        if value in kept:
            kept[value] += 1
        elif len(kept) < counters:
            kept[value] = 1
        else:
            for key in list(kept):
                kept[key] -= 1
                if kept[key] == 0:
                    del kept[key]
    return kept


def heavy_hitters(given: HeavyInput, workspace: Path) -> HeavyOutput:
    check_bounds(given.phi, given.epsilon)
    stream = [
        row[given.field.value] for row in read_log(workspace, given.file) if matches(row["status"], given.status_class)
    ]
    counters = math.ceil(1 / given.epsilon)
    kept = misra_gries(stream, counters)
    floor = (given.phi - given.epsilon) * len(stream)
    hitters = sorted(
        (Hitter(value=value, estimate=count) for value, count in kept.items() if count >= floor and count > 0),
        key=lambda hitter: (-hitter.estimate, hitter.value),
    )
    return HeavyOutput(
        file=given.file,
        field=given.field,
        status_class=given.status_class,
        phi=given.phi,
        epsilon=given.epsilon,
        stream_length=len(stream),
        counters=counters,
        hitters=hitters,
    )
