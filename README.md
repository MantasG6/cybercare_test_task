# CyberCare event services

Two Python services:

- **Propagator** (`propagator/`) sends a random event from an events file to an HTTP endpoint every N seconds.
- **Consumer** (`consumer/`) accepts events on `POST /event`, validates them and stores valid ones in MongoDB.

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker (for MongoDB and for the tests)

## Quickstart

```sh
make install   # install dependencies
make run       # start MongoDB, the consumer and the propagator
```

`make run` starts MongoDB in Docker, then runs both services side by side. Press Ctrl+C to stop them; `docker compose down` stops MongoDB.
The propagator may log one failed send at startup if the consumer is not listening yet. It keeps going.

Other targets:

| Target | What it does |
|---|---|
| `make mongo` | Start MongoDB in Docker (`docker compose up -d mongo`) |
| `make consumer` | Run the consumer |
| `make propagator` | Run the propagator |
| `make test` | Run the tests (Testcontainers starts its own MongoDB) |

## Configuration

Each service reads a TOML file. Pass a different one with `--config PATH`, for example `poetry run python -m propagator --config my.toml`.

`config/propagator.toml`

| Key | Meaning |
|---|---|
| `interval_seconds` | Seconds between two sent events |
| `endpoint_url` | URL the events are POSTed to |
| `events_file` | Path to the JSON array of events to choose from |
| `max_backoff_seconds` | Longest wait before resending an event the consumer rejected with `429` or `503` (default `30`) |

`config/consumer.toml`

| Key | Meaning |
|---|---|
| `host`, `port` | Address the HTTP API listens on |
| `mongo.uri` | MongoDB connection string |
| `mongo.database`, `mongo.collection` | Where events are stored |
| `rate_limit.requests_per_second` | Rate at which `POST /event` allows requests, shared by all clients (default `10`) |
| `rate_limit.burst` | Requests allowed at once before the rate applies (default `20`) |
| `concurrency.max_in_flight` | `POST /event` events stored at the same time; also the size of the worker thread pool (default `40`) |

## API

`POST /event` accepts **one** event per request:

```json
{"event_type": "message", "event_payload": "hello"}
```

Both fields must be strings, and no other fields are allowed. Valid events get `201` and are stored with a `received_at` timestamp; anything else gets `422`.
Requests over the rate limit get `429` with a `Retry-After` header (whole seconds until the next request is allowed) and nothing is stored. The limit is checked before validation, so invalid requests count too.
When `max_in_flight` valid events are already being stored, the next one gets `503` with `Retry-After: 1` straight away and nothing is stored. Only the store call takes a slot, so requests that are still uploading or that get `422` never hold one. The rate limit is checked first, so a request rejected with `429` does not take a slot.
The task shows the template inside `[ ]`. That is read as "an event looks like this", because the propagator sends one event at a time.

An optional `Idempotency-Key` header identifies one send. A request that repeats a stored key also gets `201`, but the event is not stored again. The key is saved as `idempotency_key`. Requests without the header are stored every time, without that field.
The propagator sends a new UUID4 key with every event. The key travels only in the header, so the body stays as above.
If a send gets `429` or `503`, the propagator backs off and resends the same event with the same key. It waits for `Retry-After` seconds if given, otherwise `interval_seconds` doubled on each rejection in a row, never longer than `max_backoff_seconds`. Any other failure is logged and the next event is sent after the normal interval.

To see what has been stored:

```sh
docker compose exec mongo mongosh events --eval 'db.events.find()'
```
