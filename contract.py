"""Each tool's and task's typed input and output (see nanoagent.plugin.v0001.contract): declarations only."""

from dataclasses import dataclass
from enum import Enum
from typing import Annotated

from slimconfig import Output


class Tool(Enum):
    GENERATE_TRAFFIC = "generate_traffic"
    HEAVY_HITTERS = "heavy_hitters"


class Task(Enum):
    GENERATE_TRAFFIC = "generate-traffic"
    FIND_HEAVY_HITTERS = "find-heavy-hitters"
    FIND_ERROR_HOTSPOT = "find-error-hotspot"


class Field(Enum):
    ENDPOINT = "endpoint"
    CLIENT_IP = "client_ip"
    USER_ID = "user_id"
    STATUS = "status"


class StatusClass(Enum):
    ANY = "any"
    SUCCESS = "2xx"
    CLIENT_ERROR = "4xx"
    SERVER_ERROR = "5xx"


SEED = "The scenario's seed: the same seed and request count always give the same file, byte for byte"
REQUESTS = "How many requests the access log holds, 1000 to 200000"
DESTINATION = "The folder relative to the plugin workspace the log is saved in, e.g. traffic"
FILE = "The access log, relative to the plugin workspace: <destination>/traffic-<seed>-<requests>.csv"
SHA256 = "The SHA-256 of the file's bytes, lowercase hex"


@dataclass
class GenerateInput(Output):
    seed: Annotated[int, SEED]
    requests: Annotated[int, REQUESTS]
    destination: Annotated[str, DESTINATION]


@dataclass
class GenerateOutput(Output):
    file: Annotated[str, FILE]
    requests: Annotated[int, "How many request rows the file holds, after its header"]
    columns: Annotated[list[str], "The CSV header's column names, in order"]
    sha256: Annotated[str, SHA256]


@dataclass
class HeavyInput(Output):
    file: Annotated[str, "An access log CSV relative to the plugin workspace, e.g. traffic/traffic-7-20000.csv"]
    field: Annotated[Field, "The column whose values are counted"]
    status_class: Annotated[StatusClass, "Only rows whose status is in this class are counted; any counts every row"]
    phi: Annotated[float, "The heavy-hitter threshold: values with at least phi times the stream length, 0 < phi <= 1"]
    epsilon: Annotated[float, "The allowed error as a share of the stream, 0.001 <= epsilon < phi"]


@dataclass
class Hitter(Output):
    value: Annotated[str, "The column value"]
    estimate: Annotated[int, "Its Misra-Gries count: never above its true count, and below it by at most N/(k+1)"]


@dataclass
class HeavyOutput(Output):
    file: Annotated[str, "The access log, as given"]
    field: Annotated[Field, "The column counted"]
    status_class: Annotated[StatusClass, "The status class counted"]
    phi: Annotated[float, "The threshold, as given"]
    epsilon: Annotated[float, "The allowed error, as given"]
    stream_length: Annotated[int, "N: how many rows matched the status class"]
    counters: Annotated[int, "k: how many Misra-Gries counters were kept, ceil(1/epsilon)"]
    hitters: Annotated[
        list[Hitter],
        "Every value whose estimate is at least (phi - epsilon) * N, highest estimate first, ties by value."
        " Every value with a true count of at least phi * N is among them",
    ]


@dataclass
class HotspotInput(Output):
    seed: Annotated[int, SEED]
    requests: Annotated[int, REQUESTS]


@dataclass
class HotspotOutput(Output):
    file: Annotated[
        str, "The access log generated for the seed and request count, traffic/traffic-<seed>-<requests>.csv"
    ]
    endpoint: Annotated[str, "The endpoint that served the most 5xx responses"]
    error_requests: Annotated[int, "How many requests in the log got a 5xx response"]
    endpoint_errors_estimate: Annotated[
        int, "The endpoint's 5xx count as heavy_hitters estimated it with epsilon 0.02 over 5xx rows"
    ]
    heavy_overall: Annotated[bool, "Whether the endpoint received at least 10% of all requests, whatever their status"]


TOOLS = {
    Tool.GENERATE_TRAFFIC: (GenerateInput, GenerateOutput),
    Tool.HEAVY_HITTERS: (HeavyInput, HeavyOutput),
}
TASKS = {
    Task.GENERATE_TRAFFIC: (GenerateInput, GenerateOutput),
    Task.FIND_HEAVY_HITTERS: (HeavyInput, HeavyOutput),
    Task.FIND_ERROR_HOTSPOT: (HotspotInput, HotspotOutput),
}
