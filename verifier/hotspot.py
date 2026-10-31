"""find-error-hotspot's check: the submitted endpoint and numbers, against exact counts from the seed's log."""

from contract import Field, StatusClass

from .checks import counters_for, exact_counts, read_log, result
from .generate import expected_file

HOTSPOT_EPSILON = 0.02
HEAVY_SHARE = 0.1


def verify_task(arguments, output, reference, workspace):
    """``output``: a contract HotspotOutput for the log generated from ``arguments``' seed and request count."""
    expected = expected_file("traffic", arguments.seed, arguments.requests)
    if output.file != expected:
        return result(False, f"file is {output.file!r}, not the seed's log {expected}")
    rows = read_log(workspace, expected)
    if isinstance(rows, str):
        return result(False, rows)
    if len(rows) != arguments.requests:
        return result(False, f"{expected} holds {len(rows)} requests, not {arguments.requests}")
    errors, error_total = exact_counts(rows, Field.ENDPOINT, StatusClass.SERVER_ERROR)
    traffic, total = exact_counts(rows, Field.ENDPOINT, StatusClass.ANY)
    if not errors:
        return result(False, "the log has no 5xx responses, so it has no hotspot")
    most = max(errors.values())
    hotspots = sorted(endpoint for endpoint, count in errors.items() if count == most)
    true = errors.get(output.endpoint, 0)
    slack = error_total / (counters_for(HOTSPOT_EPSILON) + 1)
    checks = {
        "endpoint": output.endpoint in hotspots,
        "error_requests": output.error_requests == error_total,
        "endpoint_errors_estimate": true - slack <= output.endpoint_errors_estimate <= true and true > 0,
        "heavy_overall": output.heavy_overall == (traffic.get(output.endpoint, 0) >= HEAVY_SHARE * total),
    }
    failed = [name for name, passed in checks.items() if not passed]
    details = {
        "hotspots": hotspots,
        "endpoint_5xx": most,
        "error_requests": error_total,
        "endpoint_share": round(traffic.get(hotspots[0], 0) / total, 4),
        "failed": failed,
    }
    score = (len(checks) - len(failed)) / len(checks)
    if failed:
        return result(False, f"wrong {', '.join(failed)}", score=score, **details)
    return result(True, f"{output.endpoint} served the most 5xx responses ({most} of {error_total})", **details)
