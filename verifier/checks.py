"""Checks shared by the tool verifiers. Pure functions of their arguments and the files on disk."""

import math
from collections import Counter
from pathlib import Path

COLUMNS = ["ts", "client_ip", "user_id", "endpoint", "status", "latency_ms"]
MIN_REQUESTS, MAX_REQUESTS = 1000, 200000
MIN_EPSILON = 0.001


def result(valid, message, *, score=None, **details):
    return {
        "valid": valid,
        "score": float(valid) if score is None else score,
        "message": message,
        "details": details,
    }


def path_problem(relative, suffix=None):
    path = Path(relative)
    if not relative.strip() or path.is_absolute() or ".." in path.parts:
        return f"{relative!r} must stay inside the plugin workspace"
    if suffix and path.suffix != suffix:
        return f"{relative!r} must be a {suffix} file"
    return None


def bounds_problem(phi, epsilon):
    if not 0 < phi <= 1:
        return "phi must be in (0, 1]"
    if not MIN_EPSILON <= epsilon < phi:
        return f"epsilon must be at least {MIN_EPSILON} and below phi"
    return None


def read_log(workspace, relative):
    """The log's rows as dicts, or a string saying why it cannot be read."""
    target = Path(workspace) / relative
    if not target.is_file():
        return f"{relative} is not in the workspace"
    lines = target.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].split(",") != COLUMNS:
        return f"{relative} does not start with the header {','.join(COLUMNS)}"
    rows = []
    for number, line in enumerate(lines[1:], start=2):
        cells = line.split(",")
        if len(cells) != len(COLUMNS):
            return f"{relative} line {number} does not have {len(COLUMNS)} columns"
        rows.append(dict(zip(COLUMNS, cells)))
    return rows


def in_class(status, status_class):
    """``status_class``: a contract StatusClass member."""
    return status_class.value == "any" or status[:1] == status_class.value[0]


def exact_counts(rows, field, status_class):
    """The true count of each value of ``field`` over the rows in ``status_class``, and the stream length."""
    stream = [row[field.value] for row in rows if in_class(row["status"], status_class)]
    return Counter(stream), len(stream)


def counters_for(epsilon):
    return math.ceil(1 / epsilon)
