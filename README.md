# Triage Heavy Hitters

A `nanoagent.plugin/v0001` plugin for incident triage. It writes a seeded web
access log with one planted outage, then finds the values of a column (an
endpoint, a client IP, a user or a status) that make up a large share of the
log, or of its 4xx or 5xx responses, with the Misra-Gries algorithm. It keeps
only `ceil(1/epsilon)` counters however long the log is, which is how a triage
agent can watch a stream it cannot store.

## Tools

| Tool | Does | Code |
|---|---|---|
| `generate_traffic` | Writes the access log for a seed and request count to `<destination>/traffic-<seed>-<requests>.csv` and returns its path, row count, columns and SHA-256 | `src/plugin/traffic.py` |
| `heavy_hitters` | One Misra-Gries pass over a column, restricted to a status class: every value whose estimate is at least `(phi - epsilon) * N` | `src/plugin/heavy.py` |

### Tasks

| Task | Does | Runner |
|---|---|---|
| `generate-traffic` | Generates a seeded access log | `tool`, with `generate_traffic` |
| `find-heavy-hitters` | Finds the heavy hitters of a column | `tool`, with `heavy_hitters` |
| `find-error-hotspot` | Finds the endpoint behind the incident's 5xx errors, and whether it is also a heavy hitter of all traffic | `agent`, with `generate_traffic` and `heavy_hitters` |

The log has the columns `ts,client_ip,user_id,endpoint,status,latency_ms`.
Its seed picks one endpoint that fails with 5xx responses 60% of the time
during the middle third of the log, and one scraper IP that sends about 12%
of all requests. The same seed and request count always give the same bytes.

For a stream of length `N` and `k = ceil(1/epsilon)` counters, Misra-Gries
never over-counts and under-counts by at most `N/(k+1) < epsilon * N`. So
reporting every value with an estimate of at least `(phi - epsilon) * N`
reports every value whose true count is at least `phi * N`, and nothing whose
true count is below `(phi - epsilon) * N`.

## Layout

```text
.
├── nanoagent.yaml   # manifest (a slimconfig ManifestConfig): id, runtime, permissions, tools, tasks
├── contract.py      # each tool's and task's typed input and output: slimconfig Output classes
├── README.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .env             # needed environment variable names (none here)
├── src/plugin/      # the MCP server (__main__.py, its IMPLEMENTATIONS table) and the tools
├── tests/
├── ui/              # outputs are drawn from their JSON Schema
├── product/         # the product page a catalog shows: product.yaml and icon.svg
└── verifier/        # deterministic verifier, one module per tool, and hotspot.py for find-error-hotspot
```

`verifier/` imports only the standard library and `contract`. It reads the
log back from the workspace and recounts every column exactly, then checks:

- `generate_traffic`: the file is at `<destination>/traffic-<seed>-<requests>.csv`,
  its SHA-256 is the declared one, its header is the log's, and it holds
  exactly the requested rows.
- `heavy_hitters`: the stream length and counter count are exact; every
  estimate lies in `[f - N/(k+1), f]` for its true count `f` and is at least
  `(phi - epsilon) * N`; no value is listed twice; the order is by estimate;
  and every value with `f >= phi * N` is listed.
- `find-error-hotspot`: the file is the seed's log, the endpoint has the most
  5xx responses (any of them on a tie), the 5xx total is exact, the estimate
  keeps the epsilon 0.02 bound, and `heavy_overall` is true exactly when the
  endpoint has at least 10% of all requests. The score is the share of these
  four checks that pass.

## Develop and run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check .
```

NanoAgent passes the folder the plugin may write to as `NANOAGENT_WORKSPACE`.
Logs are written there; `heavy_hitters` reads a log by its path inside it.
