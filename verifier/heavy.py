"""heavy_hitters' checks: the Misra-Gries guarantees, against exact counts recomputed from the file."""

from .checks import bounds_problem, counters_for, exact_counts, path_problem, read_log, result


def verify_input(value):
    problem = path_problem(value.file, ".csv") or bounds_problem(value.phi, value.epsilon)
    if problem:
        return result(False, problem)
    return result(True, "input is valid")


def guarantee_problems(input_value, output_value, rows):
    """Every way ``output_value`` breaks the heavy-hitter guarantees for ``rows``; empty when it keeps them."""
    counts, length = exact_counts(rows, input_value.field, input_value.status_class)
    counters = counters_for(input_value.epsilon)
    problems = []
    asked = (input_value.file, input_value.field, input_value.status_class, input_value.phi, input_value.epsilon)
    echoed = (output_value.file, output_value.field, output_value.status_class, output_value.phi, output_value.epsilon)
    if echoed != asked:
        problems.append("file, field, status_class, phi or epsilon is not the one asked for")
    if output_value.stream_length != length:
        problems.append(f"stream_length is {output_value.stream_length}, but {length} rows match")
    if output_value.counters != counters:
        problems.append(f"counters is {output_value.counters}, not ceil(1/epsilon) = {counters}")
    values = [hitter.value for hitter in output_value.hitters]
    if len(set(values)) != len(values):
        problems.append("a value is listed twice")
    order = sorted(output_value.hitters, key=lambda hitter: (-hitter.estimate, hitter.value))
    if [hitter.value for hitter in order] != values:
        problems.append("hitters are not ordered by estimate, then value")
    slack = length / (counters + 1)
    floor = (input_value.phi - input_value.epsilon) * length
    for hitter in output_value.hitters:
        true = counts.get(hitter.value, 0)
        if true == 0:
            problems.append(f"{hitter.value!r} never occurs in the stream")
        elif not true - slack <= hitter.estimate <= true:
            problems.append(f"{hitter.value!r} estimate {hitter.estimate} is outside [{true} - N/(k+1), {true}]")
        if hitter.estimate < floor:
            problems.append(f"{hitter.value!r} estimate {hitter.estimate} is below (phi - epsilon) * N")
    missing = sorted(
        value for value, true in counts.items() if true >= input_value.phi * length and value not in values
    )
    if missing:
        problems.append(f"heavy hitters missing: {', '.join(missing)}")
    return problems


def verify_output(input_value, output_value, workspace):
    rows = read_log(workspace, input_value.file)
    if isinstance(rows, str):
        return result(False, rows)
    problems = guarantee_problems(input_value, output_value, rows)
    if problems:
        return result(False, problems[0], problems=problems)
    return result(True, f"{len(output_value.hitters)} heavy hitters keep the Misra-Gries guarantees")
